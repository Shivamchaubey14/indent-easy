"""
Idempotency middleware.

Prevents duplicate record creation when a POST request is retried (e.g. after a
network error, a double-click, or an impatient user re-submitting a form).

How it works
------------
The client generates a unique key once per logical operation and sends it on the
POST as the ``X-Idempotency-Key`` HTTP header. The *same* key is reused on any
retry of that same operation.

* First time we see a key  -> we run the view, then store its (success) response.
* A retry with the same key -> we replay the stored response WITHOUT running the
  view again, so no second record is ever created.
* A retry that arrives while the first is still running -> we return HTTP 409 so
  the client waits instead of creating a duplicate.

Requests without the header are completely unaffected, so this middleware is a
no-op for every endpoint that does not opt in.

Placed after AuthenticationMiddleware so ``request.user`` is available (a stored
response is only ever replayed to the same user that created it).
"""

import base64
import hashlib
import logging
from datetime import timedelta

from django.db import IntegrityError, transaction
from django.http import HttpResponse, JsonResponse
from django.utils import timezone

logger = logging.getLogger(__name__)

# Header the client sends. Django exposes "X-Idempotency-Key" as this META key.
_HEADER_KEYS = ("HTTP_X_IDEMPOTENCY_KEY", "HTTP_IDEMPOTENCY_KEY")
_MAX_KEY_LEN = 255
# A PROCESSING record older than this is treated as abandoned (its request crashed
# before the response could be stored) and is allowed to re-run, so a stuck record
# never blocks the key forever.
_PROCESSING_STALE_SECONDS = 120


def _extract_key(request):
    # 1) AJAX / fetch clients send it as a header.
    for meta_key in _HEADER_KEYS:
        value = request.META.get(meta_key)
        if value:
            return value.strip()[:_MAX_KEY_LEN]
    # 2) Plain HTML form submits send it as a hidden field. Only look at request.POST
    #    for form-encoded/multipart bodies (JSON bodies never populate request.POST and
    #    we must not touch request.body here for multipart uploads).
    content_type = (request.content_type or "").lower()
    if content_type.startswith("multipart/") or "application/x-www-form-urlencoded" in content_type:
        value = request.POST.get("idempotency_key")
        if value:
            return value.strip()[:_MAX_KEY_LEN]
    return None


def _fingerprint(request):
    """
    sha256 of the JSON body. Only computed for application/json requests: reading
    request.body on a multipart/form-data upload would break file parsing, so we
    skip fingerprinting for those (empty fingerprint == "not checked").
    """
    content_type = (request.content_type or "").lower()
    if "application/json" not in content_type:
        return ""
    try:
        body = request.body or b""
    except Exception:
        return ""
    return hashlib.sha256(body).hexdigest()


def _is_replayable(response):
    """Only plain (non-streaming) responses can be stored and replayed."""
    if getattr(response, "streaming", False):
        return False
    return hasattr(response, "content")


def _is_text_response(content_type):
    ct = (content_type or "").lower()
    return (
        ct.startswith("text/")
        or "application/json" in ct
        or "application/xml" in ct
        or "+json" in ct
        or "+xml" in ct
        or "javascript" in ct
        or ct == ""
    )


def _build_replay(record):
    if record.response_is_base64:
        body = base64.b64decode(record.response_body or "")
    else:
        body = record.response_body
    response = HttpResponse(
        body,
        status=record.response_status_code or 200,
        content_type=record.response_content_type or "application/json",
    )
    if record.response_location:
        response["Location"] = record.response_location
    response["Idempotent-Replayed"] = "true"
    return response


class IdempotencyMiddleware:
    def __init__(self, get_response):
        self.get_response = get_response

    def __call__(self, request):
        if request.method != "POST":
            return self.get_response(request)

        key = _extract_key(request)
        if not key:
            return self.get_response(request)

        # Import here to avoid AppRegistryNotReady at import time.
        from .models import IdempotencyRecord

        user = getattr(request, "user", None)
        user_id = user.id if getattr(user, "is_authenticated", False) else None
        fingerprint = _fingerprint(request)

        # -- Atomically claim the key -------------------------------------------------
        try:
            with transaction.atomic():
                record = IdempotencyRecord.objects.create(
                    key=key,
                    method=request.method,
                    path=request.path[:500],
                    user_id=user_id,
                    request_fingerprint=fingerprint,
                    status=IdempotencyRecord.STATUS_PROCESSING,
                )
            created = True
        except IntegrityError:
            created = False
            record = IdempotencyRecord.objects.filter(key=key).first()
            if record is None:
                # Extremely rare race: row vanished between insert-fail and read.
                return self.get_response(request)

        if not created:
            replay = self._handle_existing(record, request, fingerprint, user_id)
            if replay is not None:
                return replay
            # FAILED record -> allow this attempt to re-run under the same key.
            record.status = IdempotencyRecord.STATUS_PROCESSING
            record.request_fingerprint = fingerprint
            record.user_id = user_id
            record.save(update_fields=["status", "request_fingerprint", "user", "updated_at"])

        # -- Run the view once --------------------------------------------------------
        try:
            response = self.get_response(request)
        except Exception:
            self._mark_failed(record)
            raise

        self._store_response(record, response)
        return response

    # ---------------------------------------------------------------------------------
    def _handle_existing(self, record, request, fingerprint, user_id):
        """Return a response to short-circuit with, or None to allow a re-run."""
        from .models import IdempotencyRecord

        # A stored result is only ever replayed to the same user that created it.
        if record.user_id is not None and user_id is not None and record.user_id != user_id:
            return JsonResponse(
                {"success": False,
                 "error": "This idempotency key belongs to a different user."},
                status=409,
            )

        if record.status == IdempotencyRecord.STATUS_COMPLETED:
            if (record.request_fingerprint and fingerprint
                    and record.request_fingerprint != fingerprint):
                return JsonResponse(
                    {"success": False,
                     "error": "Idempotency key was already used with a different request."},
                    status=422,
                )
            logger.info("Idempotency: replaying stored response for key %s", record.key)
            return _build_replay(record)

        if record.status == IdempotencyRecord.STATUS_PROCESSING:
            age = timezone.now() - record.updated_at
            if age < timedelta(seconds=_PROCESSING_STALE_SECONDS):
                return JsonResponse(
                    {"success": False,
                     "message": "This request is already being processed. Please wait — do not resubmit."},
                    status=409,
                )
            # Stale PROCESSING record: the original attempt was abandoned. Fall
            # through and let this attempt re-run under the same key.
            logger.warning("Idempotency: re-running stale PROCESSING key %s (age %s)", record.key, age)
            return None

        # STATUS_FAILED -> let the caller re-run under the same key.
        return None

    def _store_response(self, record, response):
        from .models import IdempotencyRecord

        success = 200 <= response.status_code < 400
        if success and _is_replayable(response):
            content_type = response.get("Content-Type", "application/json")
            raw = response.content or b""
            if _is_text_response(content_type):
                body = raw.decode(response.charset or "utf-8", errors="replace")
                is_base64 = False
            else:
                # Binary response (e.g. a generated PDF): store base64 so replay is
                # byte-identical instead of a corrupted text decode.
                body = base64.b64encode(raw).decode("ascii")
                is_base64 = True
            record.status = IdempotencyRecord.STATUS_COMPLETED
            record.response_status_code = response.status_code
            record.response_body = body
            record.response_is_base64 = is_base64
            record.response_content_type = content_type
            record.response_location = response.get("Location", "") or ""
            record.save(update_fields=[
                "status", "response_status_code", "response_body", "response_is_base64",
                "response_content_type", "response_location", "updated_at",
            ])
        else:
            # Error (or non-replayable) response -> mark FAILED so a later retry
            # with the same key is allowed to try again.
            self._mark_failed(record)

    def _mark_failed(self, record):
        from .models import IdempotencyRecord
        try:
            record.status = IdempotencyRecord.STATUS_FAILED
            record.save(update_fields=["status", "updated_at"])
        except Exception:
            logger.exception("Idempotency: failed to mark record %s FAILED", record.key)

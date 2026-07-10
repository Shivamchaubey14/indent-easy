"""
Hands-free cycle management.

Finance used to create each month's cycles and flip the active one by hand,
and a forgotten click stalled everything cycle-driven. This module keeps the
calendar current on its own:

  * ensures THIS month's MonthlyCycle (+ the three standard sub-cycles) exists,
  * pre-creates NEXT month's the same way, so the new month never starts bare,
  * keeps the cycle whose date range covers *today* active — one active cycle
    at a time, same exclusivity rule as the manual toggle.

CycleAutoMiddleware runs the check on the first request after each CHECK_EVERY
window (per process), so no cron / scheduled task is needed. A manually
activated old cycle will be flipped back to the current one at the next check.
"""

import logging
import threading
from datetime import timedelta

from django.contrib.auth import get_user_model
from django.db import IntegrityError
from django.utils import timezone

logger = logging.getLogger(__name__)

CHECK_EVERY = timedelta(hours=1)   # per-process gate between checks

_lock = threading.Lock()
_last_check = None


def _ensure_month(day):
    """Make sure the month containing `day` has a MonthlyCycle with cycles."""
    from .models import MonthlyCycle
    from .views import create_default_cycles

    month, year = day.strftime("%B"), day.year
    mc = MonthlyCycle.objects.filter(month=month, year=year).first()
    if mc is None:
        creator = (get_user_model().objects
                   .filter(is_superuser=True, is_active=True)
                   .order_by("id").first())
        if creator is None:
            return None
        try:
            mc = MonthlyCycle.objects.create(
                month=month, year=year,
                name=f"{month} {year} Cycles",
                description="Auto-created",
                created_by=creator,
            )
        except IntegrityError:   # another process created it first
            return MonthlyCycle.objects.filter(month=month, year=year).first()
        create_default_cycles(mc, year, month)
        logger.info("Auto-created monthly cycle %s %s with standard cycles", month, year)
    elif not mc.cycles.exists():
        create_default_cycles(mc, year, month)
        logger.info("Auto-created standard cycles for existing month %s %s", month, year)
    return mc


def _activate_current(today):
    """Keep the cycle covering `today` active (exclusive, like the manual toggle)."""
    from .models import Cycle

    active = Cycle.objects.filter(is_active=True).first()
    if active and active.start_date <= today <= active.end_date:
        return   # already on the right cycle
    current = (Cycle.objects
               .filter(start_date__lte=today, end_date__gte=today)
               .order_by("id").first())
    if current is None:
        return
    Cycle.objects.filter(is_active=True).exclude(id=current.id).update(is_active=False)
    if not current.is_active:
        current.is_active = True
        current.save(update_fields=["is_active"])
    logger.info("Auto-activated cycle %s", current)


def ensure_cycles_current(force=False):
    """Create this + next month's cycles if missing and activate today's cycle.
    Rate-limited to one run per CHECK_EVERY per process unless `force`."""
    global _last_check
    now = timezone.now()
    with _lock:
        if not force and _last_check is not None and now - _last_check < CHECK_EVERY:
            return
        _last_check = now
    try:
        today = timezone.now().date()   # USE_TZ is off; localdate() would raise on naive now()
        next_month = (today.replace(day=1) + timedelta(days=32)).replace(day=1)
        _ensure_month(today)
        _ensure_month(next_month)
        _activate_current(today)
    except Exception:
        logger.exception("Cycle auto-maintenance failed")


class CycleAutoMiddleware:
    """Piggybacks the cycle check onto normal traffic; a no-op inside the gate window."""

    def __init__(self, get_response):
        self.get_response = get_response

    def __call__(self, request):
        ensure_cycles_current()
        return self.get_response(request)

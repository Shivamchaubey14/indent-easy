import os
import re

from django.conf import settings
from django.core.management.base import BaseCommand

from main_app.models import StockTransferNote
from main_app.views import _archive_stn_attachment_pdf


class Command(BaseCommand):
    help = (
        "Archive the receipt / shortfall proof of already-received STNs into "
        "media/grn_against_stn/<employee_code>/ next to their GRN copy, so they "
        "show up in the GRN Against STN Files document searches. Only STNs whose "
        "GRN PDF is already archived are touched; the rest are reported."
    )

    def add_arguments(self, parser):
        parser.add_argument(
            "--dry-run",
            action="store_true",
            help="Only report what would be archived, write nothing.",
        )

    def handle(self, *args, **options):
        dry_run = options["dry_run"]
        done = skipped = 0

        stns = StockTransferNote.objects.filter(is_received=True).exclude(grn_number=None)
        for stn in stns:
            if not (stn.receipt or stn.proof):
                continue

            emp_code = str(getattr(stn.received_by, "employee_code", "") or "").strip() or "unknown"
            folder = os.path.join(settings.MEDIA_ROOT, "grn_against_stn", emp_code)
            if not os.path.isdir(folder):
                self.stdout.write(f"SKIP {stn.stn_number}: no archive folder for {emp_code}")
                skipped += 1
                continue

            # The attachments reuse the archived GRN copy's timestamp so the
            # whole group filters identically by date.
            pattern = re.compile(
                re.escape(f"{stn.grn_number}_{stn.stn_number}_") + r"(\d{14})\.pdf$"
            )
            stamp = next(
                (m.group(1) for m in map(pattern.match, os.listdir(folder)) if m),
                None,
            )
            if not stamp:
                self.stdout.write(f"SKIP {stn.stn_number}: no archived GRN copy found")
                skipped += 1
                continue

            existing = set(os.listdir(folder))
            for field, marker in ((stn.receipt, "Receipt"), (stn.proof, "Shortfall")):
                if not field or not field.name:
                    continue
                base = f"{stn.grn_number}_{stn.stn_number}_{marker}_{stamp}"
                if any(n.startswith(base) for n in existing):
                    self.stdout.write(f"OK   {stn.stn_number}: {marker} already archived")
                    continue
                if dry_run:
                    self.stdout.write(f"WOULD {stn.stn_number}: archive {marker} ({field.name})")
                    done += 1
                    continue
                _archive_stn_attachment_pdf(field, folder, base)
                if any(n.startswith(base) for n in os.listdir(folder)):
                    self.stdout.write(self.style.SUCCESS(f"DONE {stn.stn_number}: archived {marker}"))
                    done += 1
                else:
                    self.stdout.write(self.style.ERROR(f"FAIL {stn.stn_number}: {marker} could not be archived"))

        verb = "would archive" if dry_run else "archived"
        self.stdout.write(f"\nBackfill finished: {verb} {done}, skipped {skipped}")

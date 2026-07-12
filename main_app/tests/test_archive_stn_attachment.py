import io
import os
import shutil
import tempfile

from django.core.files.storage import FileSystemStorage
from django.test import SimpleTestCase
from PIL import Image

from main_app.views import _archive_stn_attachment_pdf


class FakeFieldFile:
    """Stands in for a FileField value: just a name and a storage."""

    def __init__(self, storage, name):
        self.storage = storage
        self.name = name

    def __bool__(self):
        return bool(self.name)


class ArchiveStnAttachmentPdfTests(SimpleTestCase):
    """The receipt / shortfall-proof archive copy made on STN receipt."""

    def setUp(self):
        self.media_dir = tempfile.mkdtemp()
        self.archive_dir = tempfile.mkdtemp()
        self.storage = FileSystemStorage(location=self.media_dir)
        self.addCleanup(shutil.rmtree, self.media_dir, ignore_errors=True)
        self.addCleanup(shutil.rmtree, self.archive_dir, ignore_errors=True)

    def _upload(self, name, content):
        with open(os.path.join(self.media_dir, name), "wb") as fh:
            fh.write(content)
        return FakeFieldFile(self.storage, name)

    def test_pdf_upload_is_copied_verbatim(self):
        pdf_bytes = b"%PDF-1.4 fake receipt"
        field = self._upload("receipt.pdf", pdf_bytes)
        _archive_stn_attachment_pdf(field, self.archive_dir, "GRNSTN-000001_STN-000001_Receipt_20260712000000")
        target = os.path.join(self.archive_dir, "GRNSTN-000001_STN-000001_Receipt_20260712000000.pdf")
        with open(target, "rb") as fh:
            self.assertEqual(fh.read(), pdf_bytes)

    def test_photo_upload_is_converted_to_pdf(self):
        buf = io.BytesIO()
        Image.new("RGB", (40, 30), color=(200, 120, 50)).save(buf, "PNG")
        field = self._upload("receipt.png", buf.getvalue())
        _archive_stn_attachment_pdf(field, self.archive_dir, "GRNSTN-000002_STN-000002_Receipt_20260712000000")
        target = os.path.join(self.archive_dir, "GRNSTN-000002_STN-000002_Receipt_20260712000000.pdf")
        with open(target, "rb") as fh:
            self.assertEqual(fh.read(5), b"%PDF-")

    def test_missing_upload_does_not_raise_or_write(self):
        field = FakeFieldFile(self.storage, "does-not-exist.jpg")
        _archive_stn_attachment_pdf(field, self.archive_dir, "GRNSTN-000003_STN-000003_Receipt_20260712000000")
        self.assertEqual(os.listdir(self.archive_dir), [])

    def test_empty_field_is_ignored(self):
        _archive_stn_attachment_pdf(None, self.archive_dir, "ignored")
        _archive_stn_attachment_pdf(FakeFieldFile(self.storage, ""), self.archive_dir, "ignored")
        self.assertEqual(os.listdir(self.archive_dir), [])

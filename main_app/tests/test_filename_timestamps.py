from datetime import datetime

from django.test import SimpleTestCase

from main_app.views import extract_timestamp_from_filename


class ExtractTimestampFromFilenameTests(SimpleTestCase):
    """Filename timestamp parsing that drives the document-search date filter."""

    def test_full_14_digit_timestamp(self):
        self.assertEqual(
            extract_timestamp_from_filename("GRNSTN-000006_STN-000015_20260711143455.pdf"),
            datetime(2026, 7, 11, 14, 34, 55),
        )

    def test_attachment_names_carry_the_same_stamp(self):
        self.assertEqual(
            extract_timestamp_from_filename("GRNSTN-000006_STN-000015_Receipt_20260711143455.pdf"),
            extract_timestamp_from_filename("GRNSTN-000006_STN-000015_20260711143455.pdf"),
        )

    def test_8_digit_date_only(self):
        self.assertEqual(
            extract_timestamp_from_filename("report_20231225.xlsx"),
            datetime(2023, 12, 25),
        )

    def test_no_timestamp_returns_none(self):
        self.assertIsNone(extract_timestamp_from_filename("receipt-final.pdf"))

    def test_garbage_digits_return_none(self):
        # 8 digits that are not a valid date must not crash the listing.
        self.assertIsNone(extract_timestamp_from_filename("scan_99999999.pdf"))

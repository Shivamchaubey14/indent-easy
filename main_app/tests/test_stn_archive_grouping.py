from django.test import SimpleTestCase

from main_app.views import _split_stn_archive_attachments


class SplitStnArchiveAttachmentsTests(SimpleTestCase):
    """Grouping of receipt / shortfall-proof copies under their GRN entry."""

    def test_attachments_group_under_their_grn_copy(self):
        files = [
            "GRNSTN-000007_STN-000123_20260711143045.pdf",
            "GRNSTN-000007_STN-000123_Receipt_20260711143045.pdf",
            "GRNSTN-000007_STN-000123_Shortfall_20260711143045.pdf",
        ]
        main, attachments = _split_stn_archive_attachments(files)
        self.assertEqual(main, ["GRNSTN-000007_STN-000123_20260711143045.pdf"])
        self.assertEqual(attachments, {
            "GRNSTN-000007_STN-000123_20260711143045.pdf": {
                "receipt": "GRNSTN-000007_STN-000123_Receipt_20260711143045.pdf",
                "proof": "GRNSTN-000007_STN-000123_Shortfall_20260711143045.pdf",
            },
        })

    def test_unconverted_photo_still_groups_by_base_name(self):
        # Conversion fallback keeps the original extension; the pairing must
        # not depend on both files being .pdf.
        files = [
            "GRNSTN-000008_STN-000124_20260711150000.pdf",
            "GRNSTN-000008_STN-000124_Receipt_20260711150000.jpeg",
        ]
        main, attachments = _split_stn_archive_attachments(files)
        self.assertEqual(main, ["GRNSTN-000008_STN-000124_20260711150000.pdf"])
        self.assertEqual(
            attachments["GRNSTN-000008_STN-000124_20260711150000.pdf"]["receipt"],
            "GRNSTN-000008_STN-000124_Receipt_20260711150000.jpeg",
        )

    def test_orphan_attachment_is_listed_on_its_own(self):
        files = ["GRNSTN-000009_STN-000125_Receipt_20260711160000.pdf"]
        main, attachments = _split_stn_archive_attachments(files)
        self.assertEqual(main, files)
        self.assertEqual(attachments, {})

    def test_legacy_files_pass_through_untouched(self):
        # Pre-existing archives (older naming schemes) have no markers and must
        # all stay listed as main files.
        files = [
            "20260120132853_GRN_STN_STN-000002.pdf",
            "20260120132853_MERGED_GRN_STN_STN-000002.pdf",
        ]
        main, attachments = _split_stn_archive_attachments(files)
        self.assertEqual(main, files)
        self.assertEqual(attachments, {})

    def test_empty_listing(self):
        self.assertEqual(_split_stn_archive_attachments([]), ([], {}))

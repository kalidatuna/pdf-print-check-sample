import hashlib
import io
import json
from pathlib import Path
import subprocess
import tempfile
import unittest

from PIL import Image
from reportlab.pdfgen.canvas import Canvas
from reportlab.lib.utils import ImageReader

from pdf_print_check import edge_statistics, inspect_pdf, parse_images


def make_pdf(path, gray=255, ppi=72, pages=1, vector=False):
    canvas = Canvas(str(path), pagesize=(144, 144))
    canvas.setTitle("SYNTHETIC PRINT CHECK DEMO")
    for _ in range(pages):
        if vector:
            canvas.drawString(12, 70, "Synthetic text")
        else:
            image = Image.new("RGB", (ppi * 2, ppi * 2), (gray, gray, gray))
            canvas.drawImage(ImageReader(image), 0, 0, width=144, height=144)
            canvas.drawString(12, 70, "Synthetic text")
        canvas.showPage()
    canvas.save()


class PreflightTests(unittest.TestCase):
    def setUp(self):
        self.temp = tempfile.TemporaryDirectory()
        self.path = Path(self.temp.name) / "fixture.pdf"

    def tearDown(self):
        self.temp.cleanup()

    def test_gray_low_resolution_pdf(self):
        make_pdf(self.path, gray=210, ppi=72)
        report = inspect_pdf(self.path)
        self.assertTrue(report["background_check"]["possible_gray_background"])
        self.assertEqual(report["embedded_images"][0]["x_ppi"], 72)
        self.assertTrue(report["embedded_images"][0]["below_150_ppi"])

    def test_white_high_resolution_pdf(self):
        make_pdf(self.path, ppi=300)
        report = inspect_pdf(self.path)
        self.assertFalse(report["background_check"]["possible_gray_background"])
        self.assertFalse(report["embedded_images"][0]["below_150_ppi"])

    def test_source_preserved(self):
        make_pdf(self.path)
        before = self.path.read_bytes()
        report = inspect_pdf(self.path)
        self.assertEqual(before, self.path.read_bytes())
        self.assertEqual(report["source_sha256"], hashlib.sha256(before).hexdigest())

    def test_vector_pdf_has_no_images(self):
        make_pdf(self.path, vector=True)
        self.assertEqual(inspect_pdf(self.path)["embedded_images"], [])

    def test_explicit_second_page(self):
        make_pdf(self.path, pages=2)
        report = inspect_pdf(self.path, page=2)
        self.assertEqual(report["page"], 2)
        self.assertEqual(report["total_pages"], 2)
        self.assertTrue(all(x["page"] == 2 for x in report["embedded_images"]))

    def test_outside_page(self):
        make_pdf(self.path)
        with self.assertRaisesRegex(ValueError, "outside"):
            inspect_pdf(self.path, 2)

    def test_zero_page(self):
        make_pdf(self.path)
        with self.assertRaisesRegex(ValueError, "positive"):
            inspect_pdf(self.path, 0)

    def test_bad_pdf(self):
        self.path.write_text("This is not a PDF")
        with self.assertRaisesRegex(ValueError, "could not read"):
            inspect_pdf(self.path)

    def test_missing_file(self):
        with self.assertRaises(FileNotFoundError):
            inspect_pdf(self.path)

    def test_empty_image_listing(self):
        self.assertEqual(parse_images("page num type width height\n--------------------\n"), [])

    def test_unrecognized_listing_fails(self):
        with self.assertRaisesRegex(ValueError, "Unrecognized"):
            parse_images("1 0 image invalid\n")

    def test_dark_border_needs_review(self):
        stats = edge_statistics(Image.new("RGB", (30, 30), "black"))
        self.assertTrue(stats["possible_gray_background"])
        self.assertIn("borders", stats["basis"])

    def test_cli_json_and_error_status(self):
        make_pdf(self.path)
        script = str(Path(__file__).with_name("pdf_print_check.py"))
        ok = subprocess.run(["python3", script, str(self.path)], capture_output=True, text=True)
        self.assertEqual(ok.returncode, 0)
        self.assertTrue(json.loads(ok.stdout)["human_review_required"])
        bad = subprocess.run(["python3", script, str(self.path), "--page", "0"], capture_output=True, text=True)
        self.assertEqual(bad.returncode, 2)
        self.assertFalse(json.loads(bad.stderr)["repair_performed"])


if __name__ == "__main__":
    unittest.main()

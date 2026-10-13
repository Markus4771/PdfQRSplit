"""Regression tests for distinct, non-overwriting output names."""
import tempfile
import unittest
from pathlib import Path
from output_naming import output_stem

class OutputNamingTest(unittest.TestCase):
    def test_original_name_when_available(self):
        with tempfile.TemporaryDirectory() as folder:
            self.assertEqual(output_stem("scan", folder, "abcdef1234567890"), "scan")
    def test_existing_original_uses_job_suffix(self):
        with tempfile.TemporaryDirectory() as folder:
            (Path(folder)/"scan_0001.pdf").write_bytes(b"old")
            self.assertEqual(output_stem("scan", folder, "abcdef1234567890"),
                             "scan_neu_abcdef123456")
            self.assertEqual((Path(folder)/"scan_0001.pdf").read_bytes(), b"old")
    def test_replays_have_unique_names(self):
        with tempfile.TemporaryDirectory() as folder:
            self.assertNotEqual(output_stem("scan", folder, "abcdef123456", 1),
                                output_stem("scan", folder, "abcdef123456", 2))
            self.assertEqual(output_stem("scan", folder, "abcdef123456", 1),
                             "scan_wiederholung_abcdef123456_1")
if __name__=="__main__":unittest.main()

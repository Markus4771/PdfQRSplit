"""Basic DATEV handoff regression tests (no Windows agent needed)."""
import sqlite3
import tempfile
import unittest
from pathlib import Path
from datev_handoff import publish_datev

class DatevTest(unittest.TestCase):
    def test_duplicate_never_released_again(self):
        with tempfile.TemporaryDirectory() as root:
            root=Path(root); dest=root/"datev";dest.mkdir()
            registry=root/"datev.sqlite3";staging=dest/"stage";staging.mkdir()
            a=staging/"a.pdf";a.write_bytes(b"%PDF-1.4\nexample\n")
            one=publish_datev([(a,dest/"a.pdf")],dest,registry,"scanner")
            two=publish_datev([(a,dest/"b.pdf")],dest,registry,"scanner")
            self.assertEqual(len(one["outputs"]),1)
            self.assertEqual(len(two["outputs"]),0)
            self.assertEqual(len(two["duplicates"]),1)
            with sqlite3.connect(registry) as con:
                self.assertEqual(con.execute("SELECT count(*) FROM datev_invoices").fetchone()[0],1)
    def test_missing_handoff_file_still_never_released_again(self):
        with tempfile.TemporaryDirectory() as root:
            root=Path(root);dest=root/"datev";dest.mkdir()
            registry=root/"db.sqlite3";a=dest/"source.pdf";a.write_bytes(b"pdf1")
            one=publish_datev([(a,a)],dest,registry,"scan") 
            Path(one["outputs"][0]).unlink()
            two=publish_datev([(a,a)],dest,registry,"scan")
            self.assertEqual(two["outputs"],[])
if __name__=="__main__":unittest.main()

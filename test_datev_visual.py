"""Visual duplicate detection: rescanned PDFs should be held."""
import tempfile
import unittest
from pathlib import Path
import pymupdf
from datev_visual import fingerprints,near
from datev_handoff import publish_datev

class VisualDuplicateTests(unittest.TestCase):
    def make_pdf(self,path,text):
        with pymupdf.open() as doc:
            page=doc.new_page()
            page.insert_text((70,120),text,fontsize=20)
            doc.save(path)
    def test_resaved_scan_held(self):
        with tempfile.TemporaryDirectory() as temp:
            root=Path(temp);out=root/"out";out.mkdir()
            a=root/"a.pdf";b=root/"b.pdf";db=root/"registry.db"
            self.make_pdf(a,"Invoice ABC-123 Amount 275 EUR")
            self.make_pdf(b,"Invoice ABC-123 Amount 275 EUR")
            self.assertTrue(near(fingerprints(a),fingerprints(b)))
            self.assertEqual(len(publish_datev([(a,out/"a.pdf")],out,db,a)["outputs"]),1)
            with self.assertRaisesRegex(ValueError,"DATEV-Dublettenverdacht"):
                publish_datev([(b,out/"b.pdf")],out,db,b)
    def test_different_page_count_is_not_match(self):
        self.assertFalse(near(["0"*64],["0"*64,"0"*64]))
if __name__=="__main__":unittest.main()

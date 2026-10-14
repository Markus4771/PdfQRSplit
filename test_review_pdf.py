import sqlite3
import tempfile
import unittest
from pathlib import Path
from review_pdf import source_for_case,prepare_draft

class ReviewPDFTests(unittest.TestCase):
    def setUp(self):
        self.temp=tempfile.TemporaryDirectory()
        self.root=Path(self.temp.name)
        self.input=self.root/"shares"
        self.input.mkdir()
        self.archive=self.root/"archive"
        self.archive.mkdir()
        self.db=sqlite3.connect(":memory:")
        self.db.execute("CREATE TABLE company_profile_links(company_id INTEGER,doc_type TEXT,profile_id INTEGER)")
        self.db.execute("CREATE TABLE jobs(signature TEXT,profile_id INTEGER,file TEXT,details TEXT)")
        self.db.execute("INSERT INTO company_profile_links VALUES(1,'Kasse',5)")
        self.signature="a"*64
        import fitz
        pdf=fitz.open()
        pdf.new_page()
        pdf.new_page()
        pdf.save(self.input/"test.pdf")
        pdf.close()
        self.db.execute("INSERT INTO jobs VALUES(?,?,?,?)",(self.signature,5,str(self.input/"test.pdf"),"{}"))
    def tearDown(self):
        self.db.close()
        self.temp.cleanup()
    def test_restricted_source_and_draft(self):
        self.assertEqual(source_for_case(self.db,self.signature,self.input,self.archive),self.input/"test.pdf")
        result=prepare_draft(self.db,self.signature,self.root/"drafts",self.input,self.archive,"2",90)
        import fitz
        with fitz.open(result) as pdf:
            self.assertEqual(pdf.page_count,1)
            self.assertEqual(pdf[0].rotation,90)
        with self.assertRaises(ValueError):
            prepare_draft(self.db,self.signature,self.root/"drafts",self.input,self.archive,"3",0)
    def test_rejects_foreign_source(self):
        self.db.execute("UPDATE jobs SET file=?",(str(self.root/"foreign.pdf"),))
        with self.assertRaises(FileNotFoundError):
            source_for_case(self.db,self.signature,self.input,self.archive)

if __name__=="__main__":unittest.main()

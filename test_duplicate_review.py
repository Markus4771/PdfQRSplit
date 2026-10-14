import sqlite3
import tempfile
import unittest
from pathlib import Path
from duplicate_review import cases,decision,inspected_pdf

class DuplicateReviewTests(unittest.TestCase):
    def setUp(self):
        self.db=sqlite3.connect(":memory:")
        self.db.executescript("""CREATE TABLE datev_suspects(digest TEXT,source TEXT,matching_digest TEXT,review_path TEXT,created_at TEXT);
           CREATE TABLE datev_invoices(digest TEXT,filename TEXT);
           INSERT INTO datev_invoices VALUES('bbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbb','beleg.pdf');""")
        self.tmp=tempfile.TemporaryDirectory()
        self.root=Path(self.tmp.name)
        self.private=self.root/"private"
        self.private.mkdir()
        self.suspect=self.private/"verdacht.pdf"
        self.suspect.write_bytes(b"%PDF-1.4\n")
        self.digest="a"*64
        self.db.execute("INSERT INTO datev_suspects VALUES(?,?,?,?,?)",(self.digest,"/input/scan.pdf","b"*64,str(self.suspect),"2026-10-14"))
    def tearDown(self):
        self.db.close()
        self.tmp.cleanup()
    def test_readonly_and_decision(self):
        rows=cases(self.db,"/input/scan.pdf")
        self.assertEqual(len(rows),1)
        self.assertEqual(rows[0][3],"")
        decision(self.db,self.digest,"confirmed","Already sent")
        self.assertEqual(cases(self.db,"/input/scan.pdf")[0][3],"confirmed")
        self.assertEqual(inspected_pdf(self.db,self.digest,"suspect",self.private,self.root),self.suspect)
    def test_invalid_decision(self):
        with self.assertRaises(ValueError):
            decision(self.db,self.digest,"independent","")
        with self.assertRaises(ValueError):
            decision(self.db,self.digest,"release","unsafe")
        with self.assertRaises(ValueError):
            inspected_pdf(self.db,"../evil","suspect",self.private,self.root)

if __name__=="__main__":unittest.main()

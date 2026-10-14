import sqlite3
import unittest
from review_queue import migrate,records,set_case

class ReviewQueueTests(unittest.TestCase):
    def setUp(self):
        self.db=sqlite3.connect(":memory:")
        self.db.executescript("""
        CREATE TABLE companies(id INTEGER PRIMARY KEY,code TEXT);
        CREATE TABLE company_profile_links(company_id INTEGER,doc_type TEXT,profile_id INTEGER);
        CREATE TABLE jobs(signature TEXT,profile_id INTEGER,file TEXT,status TEXT,details TEXT,updated_at TEXT);
        INSERT INTO companies VALUES(1,'10001'),(2,'10002');
        INSERT INTO company_profile_links VALUES(1,'Kasse',3),(2,'Rechnungseingang',4);
        """)
        self.sig="a"*64
        self.db.execute("INSERT INTO jobs VALUES (?,?,?,?,?,?)",(self.sig,3,"/input/invoice.pdf","error","OCR failed","2026-10-14"))
        self.db.execute("INSERT INTO jobs VALUES (?,?,?,?,?,?)",("b"*64,4,"/input/other.pdf","error","QR-Trennung fehlt","2026-10-14"))
        migrate(self.db)
    def tearDown(self):self.db.close()
    def test_company_separation_and_state(self):
        self.assertEqual(len(records(self.db,"1")),1)
        self.assertEqual(records(self.db,"1")[0]["filename"],"invoice.pdf")
        set_case(self.db,self.sig,"in_progress","OCR erneut prüfen")
        self.assertEqual(records(self.db,"1")[0]["note"],"OCR erneut prüfen")
        set_case(self.db,self.sig,"resolved","Behoben")
        self.assertEqual(len(records(self.db,"1")),0)
        self.assertEqual(len(records(self.db,"1",state="resolved")),1)
        self.assertEqual(len(records(self.db,"2")),1)
    def test_invalid_updates(self):
        for sig,state in (("../invalid","resolved"),(self.sig,"uploaded")):
            with self.assertRaises(ValueError):set_case(self.db,sig,state,"test")
        with self.assertRaises(ValueError):set_case(self.db,self.sig,"resolved","x"*1001)
if __name__=="__main__":unittest.main()

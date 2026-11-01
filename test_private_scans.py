import sqlite3
import unittest
from private_scans import create,migrate,change_mapping

class PrivateScanTests(unittest.TestCase):
    def setUp(self):
        self.db=sqlite3.connect(":memory:")
        self.db.execute("CREATE TABLE smb_accounts(username TEXT PRIMARY KEY)")
        self.db.execute("INSERT INTO smb_accounts VALUES('anna')")
        self.db.execute("""CREATE TABLE profiles(
          id INTEGER PRIMARY KEY,name TEXT,input_share TEXT,output_share TEXT,
          qr_split INTEGER,remove_separators INTEGER,remove_blank INTEGER,
          crop INTEGER,ocr INTEGER,blank_threshold REAL,ocr_languages TEXT,
          ocr_output TEXT,ocr_rotate INTEGER,ocr_deskew INTEGER,
          datev_mode INTEGER,archive_share TEXT)""")
        migrate(self.db)
        self.shares=[{"name":n,"user":"anna","writable":True,"datev_protected":False} for n in ("A","B","C")]
    def tearDown(self):self.db.close()
    def test_multiple_profiles_and_no_datev(self):
        create(self.db,"anna","Briefe","A","B",self.shares)
        create(self.db,"anna","Vertraege","C","B",self.shares)
        self.assertEqual(self.db.execute("SELECT COUNT(*) FROM private_scan_profiles").fetchone()[0],2)
        self.assertEqual(self.db.execute("SELECT DISTINCT datev_mode FROM profiles").fetchall(),[(0,)])
    def test_reject_protected_and_duplicate(self):
        create(self.db,"anna","Scan","A","B",self.shares)
        with self.assertRaises(ValueError):create(self.db,"anna","Again","A","B",self.shares)
        protected=[dict(s,datev_protected=(s["name"]=="C")) for s in self.shares]
        with self.assertRaises(ValueError):create(self.db,"anna","Invalid","A","C",protected)
    def test_mapping_change_preserves_datev_isolation(self):
        ident=create(self.db,"anna","Briefe","A","B",self.shares)
        change_mapping(self.db,ident,"anna","C","B",self.shares)
        self.assertEqual(self.db.execute("SELECT input_share,output_share FROM profiles WHERE id=?",(ident,)).fetchone(),("C","B"))
        with self.assertRaises(ValueError):
            change_mapping(self.db,ident,"anna","C","C",self.shares)
        restricted=[dict(item,datev_protected=(item["name"]=="A")) for item in self.shares]
        with self.assertRaises(ValueError):
            change_mapping(self.db,ident,"anna","A","B",restricted)

    def test_unknown_user(self):
        with self.assertRaises(ValueError):create(self.db,"other","Briefe","A","B",self.shares)

if __name__=="__main__":unittest.main()

import sqlite3
import unittest
from company_admin import migrate,save_company,share_name
from company_processing import DEFAULT,effective,save,sync_profiles,profile_name

class CompanyProcessingTest(unittest.TestCase):
    def setUp(self):
        self.db=sqlite3.connect(":memory:")
        self.db.execute("""CREATE TABLE profiles(id INTEGER PRIMARY KEY,name TEXT UNIQUE NOT NULL,input_share TEXT,
          output_share TEXT,qr_split INTEGER,remove_separators INTEGER,remove_blank INTEGER,crop INTEGER,
          ocr INTEGER,datev_mode INTEGER,archive_share TEXT)""")
        migrate(self.db)
        self.cid=save_company(self.db,"10001","Demo",["Rechnungseingang"])
        self.shares={share_name("10001","Rechnungseingang",x) for x in ("Eingang","Archiv","Ausgang","LOG")}

    def tearDown(self):self.db.close()

    def test_defaults_and_overrides(self):
        self.assertEqual(effective(self.db,self.cid,"Rechnungseingang"),DEFAULT)
        default=dict(DEFAULT,ocr=False)
        save(self.db,self.cid,"",default)
        self.assertFalse(effective(self.db,self.cid,"Rechnungseingang")["ocr"])
        specific=dict(default,ocr=True)
        save(self.db,self.cid,"Rechnungseingang",specific)
        self.assertTrue(effective(self.db,self.cid,"Rechnungseingang")["ocr"])

    def test_datev_requires_qr(self):
        with self.assertRaises(ValueError):
            save(self.db,self.cid,"",dict(DEFAULT,qr_split=False))

    def test_managed_profiles_created_and_updated(self):
        self.assertEqual(sync_profiles(self.db,self.cid,self.shares),1)
        row=self.db.execute("SELECT id,name,archive_share,datev_mode FROM profiles").fetchone()
        self.assertEqual(row[1],profile_name(self.cid,"Rechnungseingang"))
        self.assertEqual(row[2],share_name("10001","Rechnungseingang","Archiv"))
        save(self.db,self.cid,"",dict(DEFAULT,ocr=False))
        self.assertEqual(sync_profiles(self.db,self.cid,self.shares),1)
        self.assertEqual(self.db.execute("SELECT COUNT(*) FROM profiles").fetchone()[0],1)
        self.assertEqual(self.db.execute("SELECT ocr FROM profiles").fetchone()[0],0)

    def test_never_take_over_existing_profile(self):
        self.db.execute("INSERT INTO profiles(name,input_share,output_share) VALUES (?,?,?)",
            ("legacy",share_name("10001","Rechnungseingang","Eingang"),"legacy-out"))
        with self.assertRaises(ValueError):
            sync_profiles(self.db,self.cid,self.shares)

    def test_missing_shares(self):
        with self.assertRaises(ValueError):
            sync_profiles(self.db,self.cid,set())

if __name__=="__main__":unittest.main()

import sqlite3
import unittest
from private_scans import create,migrate,change_mapping,update,render,render_user

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

    def test_advanced_private_profile_settings(self):
        ident=create(self.db,"anna","Documents","A","B",self.shares)
        update(self.db,ident,"Archive",True,True,False,True,
               remove_separators=True,crop=True,ocr_rotate=True,ocr_deskew=True,
               blank_threshold=1.0,ocr_languages="deu",ocr_output="pdfa")
        row=self.db.execute("""SELECT qr_split,remove_separators,crop,ocr_rotate,ocr_deskew,
                 blank_threshold,ocr_languages,ocr_output,datev_mode FROM profiles WHERE id=?""",(ident,)).fetchone()
        self.assertEqual(row,(1,1,1,1,1,1.0,"deu","pdfa",0))
        page=render(self.db,self.shares)
        self.assertIn("ocr_languages",page)
        self.assertIn("private-smb-password",page)
        with self.assertRaises(ValueError):
            update(self.db,ident,"Bad",False,False,False,False,blank_threshold=3.0)

    def test_private_user_page_is_scoped(self):
        create(self.db,"anna","Anna-Archiv","A","B",self.shares)
        self.db.execute("INSERT INTO smb_accounts VALUES('bob')")
        create(self.db,"bob","Bob-Geheim","B","C",[dict(x,user="bob") for x in self.shares])
        view=render_user(self.db,"anna","read")
        self.assertIn("Anna-Archiv",view)
        self.assertNotIn("Bob-Geheim",view)
        self.assertNotIn("private-update",view)
        self.assertIn("private-update",render_user(self.db,"anna","manage"))

    def test_no_datev_input_output_or_archive_overlap(self):
        self.db.execute("""INSERT INTO profiles(name,input_share,output_share,datev_mode,archive_share)
            VALUES ('datev','A','B',1,'C')""")
        extra=self.shares+[{"name":"D","user":"anna","writable":True,"datev_protected":False}]
        for source,dest in (("A","D"),("D","A"),("B","D"),("D","B"),("C","D"),("D","C")):
            with self.subTest(source=source,dest=dest):
                with self.assertRaises(ValueError):
                    create(self.db,"anna","Forbidden",source,dest,extra)
        self.assertEqual(self.db.execute("SELECT COUNT(*) FROM private_scan_profiles").fetchone()[0],0)

    def test_photo_mode_keeps_pdf_ocr(self):
        pid=create(self.db,"anna","Mixed","A","B",self.shares,ocr=True,photo_mode=True)
        self.assertEqual(self.db.execute("SELECT ocr,remove_blank FROM profiles WHERE id=?",(pid,)).fetchone(),(1,1))

    def test_unknown_user(self):
        with self.assertRaises(ValueError):create(self.db,"other","Briefe","A","B",self.shares)

if __name__=="__main__":unittest.main()

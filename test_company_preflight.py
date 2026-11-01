import sqlite3
import unittest
from company_admin import migrate,save_company,change_access,share_name,FUNCTIONS
from company_preflight import inspect,render

class PreflightTests(unittest.TestCase):
    def setUp(self):
        self.db=sqlite3.connect(":memory:")
        migrate(self.db)
        self.db.executescript("""CREATE TABLE profiles(
          id INTEGER PRIMARY KEY,name TEXT,input_share TEXT,output_share TEXT,
          datev_mode INTEGER NOT NULL DEFAULT 0,qr_split INTEGER NOT NULL DEFAULT 1);
        """)
        self.cid=save_company(self.db,"10001","Beispiel",["Kasse"])
        self.db.execute("INSERT INTO smb_accounts(username,email) VALUES('anna','anna@example.org')")
        change_access(self.db,self.cid,"anna","read")
    def tearDown(self):
        self.db.close()
    def test_read_only_and_missing_config(self):
        before=self.db.total_changes
        report=inspect(self.db,{"ok":False})
        self.assertEqual(self.db.total_changes,before)
        self.assertEqual(report[0]["users"][0][0],"anna")
        self.assertTrue(any("nicht prüfbar" in issue for issue in report[0]["types"][0]["issues"]))
        self.assertIn("Systemübersicht",render(self.db,{"ok":False}))
    def test_complete_share_listing_still_flags_missing_profile(self):
        names=[share_name("10001","Kasse",item) for item in FUNCTIONS]
        result=inspect(self.db,{"ok":True,"shares":[{"name":x} for x in names]})
        issues=result[0]["types"][0]["issues"]
        self.assertTrue(any("Verarbeitungsprofil" in x for x in issues))
        self.assertFalse(any("Fehlende Samba-Freigaben" in x for x in issues))
    def test_company_isolation_and_empty_email(self):
        other=save_company(self.db,"10002","Zweite Firma",["Sonstige"])
        self.db.execute("INSERT INTO smb_accounts(username,email) VALUES('ben','')")
        change_access(self.db,other,"ben","input")
        reports=inspect(self.db,{"ok":False})
        self.assertEqual(len(reports),2)
        self.assertEqual([u[0] for u in reports[0]["users"]],["anna"])
        self.assertEqual([u[0] for u in reports[1]["users"]],["ben"])
        self.assertTrue(any("E-Mail-Adresse" in x for x in reports[1]["findings"]))

if __name__=="__main__":
    unittest.main()

import sqlite3
import unittest

from company_admin import TYPES, FUNCTIONS, migrate, save_company, change_access, share_specs, share_name

from company_admin import save_user_selection
class TestCompanyAdmin(unittest.TestCase):
    def setUp(self):
        self.db=sqlite3.connect(":memory:")
        migrate(self.db)

    def tearDown(self):
        self.db.close()

    def test_schema_and_five_types(self):
        cid=save_company(self.db,"10001","Beispiel GmbH",TYPES)
        self.db.execute("INSERT INTO smb_accounts(username) VALUES (?)",("Markus",))
        change_access(self.db,cid,"Markus","admin")
        specs=share_specs(self.db,cid)
        self.assertEqual(len(specs),20)
        self.assertEqual(len({x["name"] for x in specs}),20)
        for x in specs:
            self.assertEqual(x["protected"],not x["name"].endswith("-Eingang"))
            if x["protected"]:self.assertEqual(x["writers"],[])

    def test_checkbox_selection_persists_and_updates(self):
        cid=save_company(self.db,"10001","Test",["Kasse"])
        self.db.execute("INSERT INTO smb_accounts(username) VALUES ('anna')")
        self.db.execute("INSERT INTO smb_accounts(username) VALUES ('ben')")
        self.assertEqual(save_user_selection(self.db,cid,["anna","ben"],"write"),2)
        self.assertEqual(dict(self.db.execute("SELECT username,role FROM company_access WHERE company_id=?",(cid,))),{"anna":"write","ben":"write"})
        save_user_selection(self.db,cid,["anna"],"admin")
        self.assertEqual(dict(self.db.execute("SELECT username,role FROM company_access WHERE company_id=?",(cid,))),{"anna":"admin"})
        with self.assertRaises(ValueError):
            save_user_selection(self.db,cid,[],"admin")

    def test_company_status_shares_and_profiles(self):
        from company_admin import render_company_status
        cid=save_company(self.db,"10001","Test",["Kasse"])
        self.db.execute("INSERT INTO smb_accounts(username) VALUES ('anna')")
        change_access(self.db,cid,"anna","admin")
        names=[share_name("10001","Kasse",fn) for fn in FUNCTIONS]
        status={"ok":True,"shares":[{"name":name} for name in names]}
        html=render_company_status(self.db,cid,"10001",["Kasse"],[("anna","admin")],status,str)
        self.assertIn("4/4",html)
        self.assertIn("Fehlt oder abweichend",html)
        html=render_company_status(self.db,cid,"10001",["Kasse"],[("anna","admin")],{"ok":False},str)
        self.assertIn("Nicht pruefbar",html)

    def test_invalid_name_and_types(self):
        with self.assertRaises(ValueError):
            save_company(self.db,"unzulässig!","Bad",["Kasse"])
        with self.assertRaises(ValueError):
            share_name("10001","Invalid","Eingang")
        with self.assertRaises(ValueError):
            share_name("10001","Rechnungseingang","Invalid")

    def test_firm_isolation(self):
        a=save_company(self.db,"10001","A",["Rechnungseingang"])
        b=save_company(self.db,"10002","B",["Kasse"])
        self.db.execute("INSERT INTO smb_accounts(username) VALUES (?)",("Markus",))
        change_access(self.db,a,"Markus","admin")
        with self.assertRaises(ValueError):
            share_specs(self.db,b)
        self.assertEqual(len(share_specs(self.db,a)),4)

    def test_access_changes(self):
        cid=save_company(self.db,"10001","A",["Kasse"])
        self.db.execute("INSERT INTO smb_accounts(username) VALUES (?)",("Markus",))
        change_access(self.db,cid,"Markus","read")
        self.assertEqual(share_specs(self.db,cid)[0]["writers"],[])
        change_access(self.db,cid,"Markus","input")
        specs=share_specs(self.db,cid)
        self.assertEqual(sum(bool(s["writers"]) for s in specs),1)
        change_access(self.db,cid,"Markus","none")
        with self.assertRaises(ValueError):
            share_specs(self.db,cid)


    def test_checkbox_multiple_users(self):
        cid=save_company(self.db,"10003","Test",["Rechnungseingang"])
        for user in ("Markus","Buchhaltung"):
            self.db.execute("INSERT INTO smb_accounts(username) VALUES (?)",(user,))
            change_access(self.db,cid,user,"write")
        specs=share_specs(self.db,cid)
        entry=[x for x in specs if x["name"].endswith("-Eingang")][0]
        self.assertEqual(set(entry["writers"]),{"Markus","Buchhaltung"})

    def test_company_html_contains_delete_and_checkboxes(self):
        from company_admin import render
        cid=save_company(self.db,"10004","Test",["Kasse"])
        self.db.execute("INSERT INTO smb_accounts(username) VALUES (?)",("Markus",))
        html=render(self.db)
        self.assertIn("action='/company-users-save'",html)
        self.assertIn("action='/company-delete'",html)
        self.assertIn("action='/company-user-delete'",html)
        self.assertIn("name='username' value='Markus'",html)

if __name__=="__main__":
    unittest.main()

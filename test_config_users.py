import sqlite3
import unittest
from config_users import render

class ConfigurationUserTests(unittest.TestCase):
    def test_user_scope_and_escaping(self):
        con=sqlite3.connect(":memory:")
        con.execute("CREATE TABLE smb_accounts(username TEXT PRIMARY KEY,email TEXT)")
        con.execute("CREATE TABLE company_access(username TEXT,company_id INTEGER,role TEXT)")
        con.execute("CREATE TABLE companies(id INTEGER PRIMARY KEY,code TEXT,display_name TEXT)")
        con.execute("CREATE TABLE private_scan_profiles(username TEXT)")
        con.execute("INSERT INTO smb_accounts VALUES('anna','anna@example.org')")
        con.execute("INSERT INTO companies VALUES(1,'MUSTER','Muster GmbH')")
        con.execute("INSERT INTO company_access VALUES('anna',1,'read')")
        con.execute("INSERT INTO private_scan_profiles VALUES('anna')")
        page=render(con,[{"name":"Anna-Eingang","user":"anna"}])
        self.assertIn("anna@example.org",page)
        self.assertIn("Anna-Eingang",page)
        self.assertIn("Muster GmbH",page)
        self.assertIn("MUSTER, read",page)
        self.assertIn("config-user-email",page)
        con.close()

if __name__=="__main__":
    unittest.main()

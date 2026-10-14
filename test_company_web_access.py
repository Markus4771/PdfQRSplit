import sqlite3
import base64
import unittest
from company_web_access import set_password,authenticate,owns_job
class CompanyWebAccessTests(unittest.TestCase):
    def setUp(self):
        self.con=sqlite3.connect(":memory:")
        self.con.executescript("""CREATE TABLE smb_accounts(username TEXT);
            CREATE TABLE company_access(company_id INTEGER,username TEXT,role TEXT);
            CREATE TABLE company_profile_links(company_id INTEGER,profile_id INTEGER);
            CREATE TABLE jobs(signature TEXT,profile_id INTEGER);
            INSERT INTO smb_accounts VALUES('anna');
            INSERT INTO company_access VALUES(1,'anna','read');
            INSERT INTO company_profile_links VALUES(1,3);
            INSERT INTO jobs VALUES('aaa',3),('bbb',4);""")
    def tearDown(self):self.con.close()
    def test_login_and_access(self):
        set_password(self.con,"anna","correct-pass-1234")
        header="Basic "+base64.b64encode(b"anna:correct-pass-1234").decode()
        self.assertEqual(authenticate(self.con,header),("anna",{1}))
        self.assertFalse(authenticate(self.con,"Basic "+base64.b64encode(b"anna:wrongpassword").decode()))
        self.assertTrue(owns_job(self.con,"aaa",{1}))
        self.assertFalse(owns_job(self.con,"bbb",{1}))
if __name__=="__main__":unittest.main()

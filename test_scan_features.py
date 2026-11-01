import sqlite3
import tempfile
from pathlib import Path
import unittest
from scan_features import permitted_profiles,find_document,valid_recipient,business_card_vcard

class ScanFeatureTests(unittest.TestCase):
    def setUp(self):
        self.con=sqlite3.connect(":memory:")
        self.con.executescript("""CREATE TABLE profiles(id INTEGER,name TEXT,output_share TEXT);
          CREATE TABLE private_scan_profiles(profile_id INTEGER,username TEXT);
          CREATE TABLE company_profile_links(profile_id INTEGER,company_id INTEGER);
          CREATE TABLE company_access(company_id INTEGER,username TEXT,role TEXT);
          INSERT INTO profiles VALUES(1,'Privat','private_out'),(2,'Firma','firm_out');
          INSERT INTO private_scan_profiles VALUES(1,'anna');
          INSERT INTO company_profile_links VALUES(2,10);
          INSERT INTO company_access VALUES(10,'bob','read');""")
    def tearDown(self):self.con.close()
    def test_tenant_scope(self):
        self.assertEqual([x[0] for x in permitted_profiles(self.con,'anna')],[1])
        self.assertEqual([x[0] for x in permitted_profiles(self.con,'bob')],[2])
        self.assertEqual(len(permitted_profiles(self.con,'nobody')),0)
    def test_file_access_and_traversal(self):
        with tempfile.TemporaryDirectory() as tmp:
            d=Path(tmp)/'private_out';d.mkdir()
            (d/'scan.pdf').write_bytes(b'%PDF-demo')
            self.assertEqual(find_document(self.con,'anna',False,1,'scan.pdf',tmp).name,'scan.pdf')
            with self.assertRaises(PermissionError):find_document(self.con,'bob',False,1,'scan.pdf',tmp)
            with self.assertRaises(ValueError):find_document(self.con,'anna',False,1,'../scan.pdf',tmp)
            (d/'escape.pdf').symlink_to('/etc/passwd')
            with self.assertRaises(FileNotFoundError):find_document(self.con,'anna',False,1,'escape.pdf',tmp)
    def test_vcard_and_recipients(self):
        self.assertTrue(valid_recipient('name@example.com'))
        self.assertFalse(valid_recipient('name\r\n@example.com'))
        self.assertIn('BEGIN:VCARD',business_card_vcard('Anna','Firma','anna@example.com','123'))
        with self.assertRaises(ValueError):business_card_vcard('A\r\nINJECT','F','','')
if __name__=='__main__':unittest.main()

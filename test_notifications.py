import sqlite3
import unittest
from unittest.mock import patch
import notifications

class NotificationTests(unittest.TestCase):
    def setUp(self):
        self.db=sqlite3.connect(":memory:")
        self.db.executescript("""CREATE TABLE companies(id INTEGER,code TEXT);
            CREATE TABLE company_profile_links(company_id INTEGER,doc_type TEXT,profile_id INTEGER);
            INSERT INTO companies VALUES(1,'10001');
            INSERT INTO company_profile_links VALUES(1,'Kasse',5);""")
        self.db.execute("CREATE TABLE smb_accounts(username TEXT,email TEXT)")
        self.db.execute("CREATE TABLE company_access(company_id INTEGER,username TEXT,role TEXT)")
        self.db.execute("INSERT INTO smb_accounts VALUES ('anna','anna@example.org')")
        self.db.execute("INSERT INTO company_access VALUES (1,'anna','admin')")
        notifications.save(self.db,dict(host="smtp.example.org",port=587,username="user",secret="secret",sender="a@example.org",recipient="b@example.org",mode="starttls",enabled=1))
    def tearDown(self):self.db.close()
    def test_one_critical_mail_per_event(self):
        with patch("notifications.send") as sender:
            self.assertTrue(notifications.notify(self.db,"a"*64,5,"error","OCR fehlgeschlagen","/share/scan.pdf"))
            self.assertFalse(notifications.notify(self.db,"a"*64,5,"error","OCR fehlgeschlagen","/share/scan.pdf"))
            self.assertFalse(notifications.notify(self.db,"b"*64,5,"done",'{"outputs":["test.pdf"]}',"/share/scan.pdf"))
            self.assertTrue(notifications.notify(self.db,"c"*64,5,"done",'{"archive_warning":"Archiv fehlt"}',"/share/scan.pdf"))
            self.assertEqual(sender.call_count,2)
    def test_other_company_user_receives_no_mail(self):
        self.db.execute("INSERT INTO smb_accounts VALUES ('ben','ben@example.org')")
        self.db.execute("INSERT INTO company_access VALUES (2,'ben','read')")
        with patch("notifications.send") as sender:
            notifications.notify(self.db,"e"*64,5,"error","OCR failed","/share/scan.pdf")
            self.assertEqual(sender.call_count,1)
            self.assertEqual(sender.call_args.args[0]["recipient"],"anna@example.org")

    def test_failed_send_is_not_recorded(self):
        with patch("notifications.send",side_effect=OSError("offline")):
            with self.assertRaises(OSError):notifications.notify(self.db,"d"*64,5,"error","OCR fehlgeschlagen","test.pdf")
        self.assertFalse(self.db.execute("SELECT 1 FROM notification_sent WHERE signature=?",("d"*64,)).fetchone())
    def test_tls_required(self):
        with self.assertRaises(ValueError):
            notifications.validate(dict(notifications.config(self.db),mode="plain"))
if __name__=="__main__":unittest.main()

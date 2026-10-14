import sqlite3
import unittest
from company_monitor import classify,summary

class CompanyMonitorTests(unittest.TestCase):
    def test_classification(self):
        self.assertEqual(classify("error","DATEV-Dublettenverdacht")[0],"duplicate")
        self.assertEqual(classify("error","OCR failed")[0],"ocr")
        self.assertEqual(classify("done",'{"archive_warning":"Archiv nicht erreichbar"}')[1],"Warnung")
        self.assertEqual(classify("done",'{"outputs":["beleg.pdf"]}')[1],"Erfolgreich")

    def test_company_scoping(self):
        con=sqlite3.connect(":memory:")
        con.execute("CREATE TABLE company_profile_links(company_id INTEGER,doc_type TEXT,profile_id INTEGER)")
        con.execute("CREATE TABLE jobs(file TEXT,status TEXT,details TEXT,updated_at TEXT,profile_id INTEGER)")
        con.executemany("INSERT INTO company_profile_links VALUES (?,?,?)",[(1,"Kasse",5),(2,"Kasse",6)])
        con.executemany("INSERT INTO jobs VALUES (?,?,?,?,?)",[("/a/a.pdf","error","OCR failed","2026-01-01",5),("/b/b.pdf","error","PDF failed","2026-01-02",6)])
        counts,problems=summary(con,1)
        self.assertEqual(counts["error"],1)
        self.assertEqual(len(problems),1)
        self.assertEqual(problems[0]["file"],"a.pdf")
        con.close()

if __name__=="__main__":unittest.main()

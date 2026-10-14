import json
import sqlite3
import tempfile
import unittest
from pathlib import Path
from profile_logs import write_job

class TestProfileLogs(unittest.TestCase):
    def test_only_linked_profile_has_log(self):
        with tempfile.TemporaryDirectory() as folder:
            con=sqlite3.connect(":memory:")
            con.execute("CREATE TABLE companies(id INTEGER,code TEXT)")
            con.execute("CREATE TABLE company_profile_links(company_id INTEGER,doc_type TEXT,profile_id INTEGER)")
            con.execute("INSERT INTO companies VALUES (1,'10001')")
            con.execute("INSERT INTO company_profile_links VALUES (1,'Kasse',7)")
            log=Path(folder)
            shares={"10001-Kasse-LOG":log}
            signature="a"*64
            self.assertTrue(write_job(con,7,shares,signature,"done","/input/test.pdf",{"outputs":1}))
            data=json.loads((log/("job_"+signature+".json")).read_text())
            self.assertEqual(data["status"],"done")
            self.assertEqual(data["source_file"],"test.pdf")
            self.assertFalse(write_job(con,8,shares,signature,"done","/input/test.pdf"))
            with self.assertRaises(ValueError):
                write_job(con,7,shares,"../bad","done","/input/test.pdf")

if __name__=="__main__": unittest.main()

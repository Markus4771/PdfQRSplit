"""Regression checks for missing-file flags and retention cleanup."""
import json
import sqlite3
import tempfile
import unittest
from datetime import datetime,timedelta,timezone
from pathlib import Path
from jobs_ui import ensure,outputs_from_details,file_flags,save_retention,retention_days,cleanup_jobs

class HistoryTest(unittest.TestCase):
    def test_file_states(self):
        with tempfile.TemporaryDirectory() as tmp:
            base=Path(tmp);src=base/"input.pdf";out=base/"output.pdf"
            src.write_bytes(b"source");out.write_bytes(b"output")
            details=json.dumps({"outputs":[str(out)]})
            self.assertEqual(file_flags("done",str(src),details),(False,0,1))
            out.unlink()
            self.assertEqual(file_flags("done",str(src),details),(False,1,1))
            src.unlink()
            self.assertEqual(file_flags("done",str(src),details),(True,1,1))
    def test_old_repr_manifest(self):
        self.assertEqual(outputs_from_details("{'outputs': ['/tmp/a.pdf']}"),["/tmp/a.pdf"])
    def test_retention_preserves_fingerprint(self):
        with tempfile.TemporaryDirectory() as tmp:
            db=Path(tmp)/"test.db"
            with sqlite3.connect(db) as con:
                con.execute("CREATE TABLE jobs (signature TEXT PRIMARY KEY,profile_id INTEGER,file TEXT,status TEXT,details TEXT,updated_at TEXT)")
                ensure(con)
                old=(datetime.now(timezone.utc)-timedelta(days=200)).strftime("%Y-%m-%d %H:%M:%S")
                con.execute("INSERT INTO jobs(signature,profile_id,file,status,details,updated_at) VALUES (?,?,?,?,?,?)",("a"*64,1,"/tmp/a.pdf","done","",old))
                con.commit()
                self.assertEqual(cleanup_jobs(con),1)
                self.assertEqual(con.execute("SELECT COUNT(*) FROM jobs").fetchone()[0],0)
                self.assertEqual(con.execute("SELECT COUNT(*) FROM archived_signatures").fetchone()[0],1)
            save_retention(db,30)
            with sqlite3.connect(db) as con:
                self.assertEqual(retention_days(con),30)
if __name__=="__main__":unittest.main()

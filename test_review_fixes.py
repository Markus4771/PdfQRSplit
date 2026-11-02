"""Regression tests for the review findings of 2026-11-01.

Each test pins one defect that was reproduced before the fix.
"""
import base64
import contextlib
import hashlib
import json
import os
import sqlite3
import tempfile
import unittest
from pathlib import Path

import app
import company_monitor
import datev_handoff
import duplicate_review
import worker


class OriginCheckTests(unittest.TestCase):
    """The origin check rejected the https origin of a TLS reverse proxy."""

    def test_https_origin_of_same_host_is_allowed(self):
        self.assertTrue(app.origin_allowed("https://scan.firma.de", "scan.firma.de"))

    def test_http_origin_of_same_host_is_allowed(self):
        self.assertTrue(app.origin_allowed("http://scan.firma.de", "scan.firma.de"))

    def test_trailing_slash_is_allowed(self):
        self.assertTrue(app.origin_allowed("https://scan.firma.de/", "scan.firma.de"))

    def test_port_is_part_of_the_host(self):
        self.assertTrue(app.origin_allowed("https://scan.firma.de:8443", "scan.firma.de:8443"))

    def test_different_port_is_rejected(self):
        self.assertFalse(app.origin_allowed("https://scan.firma.de:8443", "scan.firma.de"))

    def test_default_port_matches_implicit_port(self):
        self.assertTrue(app.origin_allowed("https://scan.firma.de:443", "scan.firma.de"))
        self.assertTrue(app.origin_allowed("http://scan.firma.de:80", "scan.firma.de"))

    def test_invalid_port_is_rejected(self):
        self.assertFalse(app.origin_allowed("https://scan.firma.de:bad", "scan.firma.de"))

    def test_userinfo_trick_is_rejected(self):
        self.assertFalse(app.origin_allowed("https://scan.firma.de@evil.com", "scan.firma.de"))

    def test_foreign_host_is_rejected(self):
        self.assertFalse(app.origin_allowed("https://evil.example", "scan.firma.de"))

    def test_other_scheme_is_rejected(self):
        self.assertFalse(app.origin_allowed("ftp://scan.firma.de", "scan.firma.de"))

    def test_origin_with_path_is_rejected(self):
        self.assertFalse(app.origin_allowed("https://scan.firma.de/evil", "scan.firma.de"))

    def test_subdomain_is_not_the_same_host(self):
        self.assertFalse(app.origin_allowed("https://other.scan.firma.de", "scan.firma.de"))

    def test_trusted_origins_from_environment(self):
        previous=os.environ.get("QRSCAN_TRUSTED_ORIGINS")
        os.environ["QRSCAN_TRUSTED_ORIGINS"]="https://proxy.firma.de, https://alt.firma.de/"
        try:
            self.assertIn("https://proxy.firma.de", app.trusted_origins())
            self.assertIn("https://alt.firma.de", app.trusted_origins())
        finally:
            if previous is None:os.environ.pop("QRSCAN_TRUSTED_ORIGINS",None)
            else:os.environ["QRSCAN_TRUSTED_ORIGINS"]=previous


class SambaFailClosedTests(unittest.TestCase):
    """A Samba outage silently skipped the revocation of share access."""

    def setUp(self):
        self.original=app.samba_call

    def tearDown(self):
        app.samba_call=self.original

    def test_samba_shares_raises_when_service_is_down(self):
        app.samba_call=lambda payload:{"ok":False,"error":"Samba-Verwaltungsdienst nicht erreichbar"}
        with self.assertRaises(ValueError):
            app.samba_shares()

    def test_samba_shares_returns_names(self):
        app.samba_call=lambda payload:{"ok":True,"shares":[{"name":"A"},{"name":"B"}]}
        self.assertEqual(app.samba_shares(),{"A","B"})

    def test_samba_shares_rejects_malformed_entries(self):
        app.samba_call=lambda payload:{"ok":True,"shares":[{"name":"A"},"broken"]}
        self.assertEqual(app.samba_shares(),{"A"})


class DuplicateSourcePathTests(unittest.TestCase):
    """datev_suspects.source pointed at a temporary snapshot, not at jobs.file."""

    def test_registry_source_matches_the_job_file(self):
        with tempfile.TemporaryDirectory() as root:
            root=Path(root)
            input_share=root/"shares";input_share.mkdir()
            destination=root/"datev";destination.mkdir()
            registry=root/"datev.sqlite3"
            source=input_share/"scan.pdf"
            import pymupdf
            with pymupdf.open() as doc:
                doc.new_page().insert_text((80,100),"Invoice TEST 1 EUR")
                doc.save(source)
            # The worker reads a snapshot but must register the original path.
            snapshot=root/"scanjob-123"/"scan.pdf"
            snapshot.parent.mkdir()
            snapshot.write_bytes(source.read_bytes())
            options={"qr_split":False,"remove_separators":False,"remove_blank":False,
                     "crop":False,"ocr":False,"datev_mode":True,"datev_registry":str(registry)}
            result=worker.run(snapshot,destination,"SCAN-TRENNUNG-001",options,origin=source)
            self.assertEqual(result["source"],str(source))
            with contextlib.closing(sqlite3.connect(registry)) as con:
                rows=con.execute("SELECT source FROM datev_invoices").fetchall()
            self.assertEqual([row[0] for row in rows],[str(source)])

    def test_duplicate_review_finds_the_case_by_job_file(self):
        with tempfile.TemporaryDirectory() as root:
            root=Path(root)
            registry=root/"datev.sqlite3"
            with contextlib.closing(sqlite3.connect(registry)) as con:
                datev_handoff.ensure(con)
                con.execute("""INSERT INTO datev_suspects
                    (digest,source,matching_digest,visual,review_path) VALUES (?,?,?,?,?)""",
                    ("a"*64,"/srv/samba-shares/FIRMA/scan.pdf","b"*64,datev_handoff.encode([0]*256),"/tmp/review.pdf"))
                con.commit()
            with contextlib.closing(sqlite3.connect(registry)) as con:
                cases=duplicate_review.cases(con,"/srv/samba-shares/FIRMA/scan.pdf")
            self.assertEqual(len(cases),1)


class SqliteSessionTests(unittest.TestCase):
    """Connections were not closed, so every request leaked a file descriptor."""

    def test_session_closes_the_connection(self):
        with tempfile.TemporaryDirectory() as root:
            path=Path(root)/"test.sqlite3"
            with app.sqlite_util.session(path) as con:
                con.execute("CREATE TABLE t(x)")
                connection=con
            with self.assertRaises(sqlite3.ProgrammingError):
                connection.execute("SELECT 1")

    def test_session_commits_on_success(self):
        with tempfile.TemporaryDirectory() as root:
            path=Path(root)/"test.sqlite3"
            with app.sqlite_util.session(path) as con:
                con.execute("CREATE TABLE t(x)")
                con.execute("INSERT INTO t VALUES (1)")
            with contextlib.closing(sqlite3.connect(path)) as con:
                self.assertEqual(con.execute("SELECT COUNT(*) FROM t").fetchone()[0],1)

    def test_session_rolls_back_on_error(self):
        with tempfile.TemporaryDirectory() as root:
            path=Path(root)/"test.sqlite3"
            with contextlib.closing(sqlite3.connect(path)) as con:
                con.execute("CREATE TABLE t(x)")
                con.commit()
            with self.assertRaises(RuntimeError):
                with app.sqlite_util.session(path) as con:
                    con.execute("INSERT INTO t VALUES (1)")
                    raise RuntimeError("abbruch")
            with contextlib.closing(sqlite3.connect(path)) as con:
                self.assertEqual(con.execute("SELECT COUNT(*) FROM t").fetchone()[0],0)

    def test_autocommit_session_keeps_its_semantics(self):
        # isolation_level=None commits every statement on its own. The helper
        # must not change that; the DATEV handoff relies on explicit commits.
        with tempfile.TemporaryDirectory() as root:
            path=Path(root)/"test.sqlite3"
            with app.sqlite_util.session(path,isolation_level=None) as con:
                con.execute("CREATE TABLE t(x)")
                con.execute("INSERT INTO t VALUES (1)")
            with contextlib.closing(sqlite3.connect(path)) as con:
                self.assertEqual(con.execute("SELECT COUNT(*) FROM t").fetchone()[0],1)

    def test_app_db_session_closes_the_connection(self):
        with tempfile.TemporaryDirectory() as root:
            previous=app.DB
            app.DB=Path(root)/"profiles.sqlite3"
            try:
                with app.db_session() as con:
                    connection=con
                with self.assertRaises(sqlite3.ProgrammingError):
                    connection.execute("SELECT 1")
            finally:
                app.DB=previous


class RouteSmokeTests(unittest.TestCase):
    """Every page must render without a runtime error.

    A wrongly indented connection block once made the overview page fail with
    an UnboundLocalError that no existing test caught.
    """

    def setUp(self):
        self.previous={name:getattr(app,name) for name in ("DATA","DB","AUTH")}
        self.tmp=tempfile.TemporaryDirectory()
        root=Path(self.tmp.name)
        app.DATA=root; app.DB=root/"profiles.sqlite3"; app.AUTH=root/"auth.json"
        salt=os.urandom(16)
        digest=hashlib.pbkdf2_hmac("sha256",b"Test123456789!",salt,200000).hex()
        app.AUTH.write_text(json.dumps({"salt":salt.hex(),"digest":digest,"rounds":200000,"must_change":False}))
        self.credential="Basic "+base64.b64encode(b"admin:Test123456789!").decode()
        with app.db_session():pass
        import watcher
        previous_watcher_db=watcher.DB
        watcher.DB=app.DB
        try:
            with watcher.connect():pass
        finally:
            watcher.DB=previous_watcher_db

    def tearDown(self):
        for name,value in self.previous.items():setattr(app,name,value)
        self.tmp.cleanup()

    def render(self,path):
        handler=app.Handler.__new__(app.Handler)
        handler.path=path
        handler.command="GET"
        handler.headers={"Authorization":self.credential}
        handler._actor_cache=app._UNSET
        pages=[]
        handler.page=lambda content,status=200,unauthorized=False:pages.append((content,status)) or status
        handler.send_response=lambda *a,**k:None
        handler.send_header=lambda *a,**k:None
        handler.end_headers=lambda *a,**k:None
        app.Handler.do_GET(handler)
        return pages

    def test_overview_page_renders(self):
        pages=self.render("/")
        self.assertTrue(pages)
        self.assertEqual(pages[-1][1],200)
        self.assertIn("Übersicht",pages[-1][0])

    def test_jobs_page_renders(self):
        pages=self.render("/jobs")
        self.assertTrue(pages)
        self.assertEqual(pages[-1][1],200)
        self.assertIn("Auftragsübersicht",pages[-1][0])

    def test_review_page_renders(self):
        pages=self.render("/review")
        self.assertTrue(pages)
        self.assertEqual(pages[-1][1],200)

    def test_actor_cache_is_used_within_one_request(self):
        handler=app.Handler.__new__(app.Handler)
        handler.headers={"Authorization":""}
        handler._actor_cache=app._UNSET
        calls={"n":0}
        original=app.company_web_access.authenticate
        def counting(con,header):
            calls["n"]+=1
            return original(con,header)
        app.company_web_access.authenticate=counting
        try:
            handler.actor();handler.actor();handler.actor()
        finally:
            app.company_web_access.authenticate=original
        self.assertEqual(calls["n"],1)


class DuplicateMessageTests(unittest.TestCase):
    """A duplicate warning without text produced an empty review reason."""

    def test_duplicate_warning_names_the_reason(self):
        category,severity,message=company_monitor.classify("done",'{"duplicates":["beleg_x.pdf"]}')
        self.assertEqual(category,"duplicate")
        self.assertEqual(severity,"Warnung")
        self.assertTrue(message.strip())

    def test_existing_message_is_kept(self):
        _,_,message=company_monitor.classify("done",'{"duplicates":["x"],"message":"Eigener Text"}')
        self.assertEqual(message,"Eigener Text")


if __name__=="__main__":unittest.main()

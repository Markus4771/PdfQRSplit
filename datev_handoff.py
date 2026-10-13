"""Fail-closed DATEV handoff. Exact-byte deduplication; not a DATEV upload receipt."""
import hashlib
import os
import sqlite3
from pathlib import Path

def ensure(con):
    con.execute("""CREATE TABLE IF NOT EXISTS datev_invoices(
        digest TEXT PRIMARY KEY,
        filename TEXT NOT NULL UNIQUE,
        source TEXT,
        state TEXT NOT NULL DEFAULT 'reserved',
        created_at TEXT NOT NULL DEFAULT CURRENT_TIMESTAMP
    )""")

def publish_datev(generated,destination,registry,source):
    """Permanently reserve before publication; uncertain crash states do not resend."""
    destination=Path(destination)
    registry=Path(registry)
    sent=[]; duplicates=[]
    with sqlite3.connect(registry,timeout=30,isolation_level=None) as con:
        con.execute("PRAGMA synchronous=FULL")
        ensure(con)
        for staged,_ in generated:
            staged=Path(staged)
            if not staged.is_file() or staged.stat().st_size==0:
                raise ValueError("Leere DATEV-Ausgabe")
            with staged.open("rb") as stream:
                digest=hashlib.file_digest(stream,"sha256").hexdigest()
            filename=f"beleg_{digest}.pdf"
            target=destination/filename
            con.execute("BEGIN IMMEDIATE")
            try:
                existing=con.execute("SELECT state FROM datev_invoices WHERE digest=?",(digest,)).fetchone()
                if existing:
                    if existing[0] != "published":
                        raise RuntimeError(f"DATEV-Übergabe unklar (reserviert): {filename}; manuelle Kontrolle erforderlich")
                    duplicates.append(filename)
                    con.commit()
                    continue
                if target.exists() or target.is_symlink():
                    raise FileExistsError(f"DATEV-Datei existiert ohne Registereintrag: {target}")
                con.execute("INSERT INTO datev_invoices(digest,filename,source,state) VALUES (?,?,?,'reserved')",(digest,filename,str(source)))
                con.commit()
            except BaseException:
                con.rollback()
                raise
            # From here on, a failure is deliberately NOT auto-retried as a new handoff.
            # Operators reconcile reserved entries manually before any release.
            os.link(staged,target,follow_symlinks=False)
            fd=os.open(destination,os.O_RDONLY|os.O_DIRECTORY)
            try:os.fsync(fd)
            finally:os.close(fd)
            con.execute("UPDATE datev_invoices SET state='published' WHERE digest=?",(digest,))
            con.commit()
            sent.append(str(target))
    return {"outputs":sent,"duplicates":duplicates}

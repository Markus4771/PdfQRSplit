"""Fail-closed DATEV handoff for byte-identical individual invoice PDFs.

The registry is durable and independent of normal job retention. The handoff
folder MUST NOT be used as a regular QR profile output directory.
"""
import hashlib
import os
import sqlite3
from pathlib import Path

def ensure(con):
    con.execute("""CREATE TABLE IF NOT EXISTS datev_invoices(
        digest TEXT PRIMARY KEY,
        filename TEXT NOT NULL UNIQUE,
        source TEXT,
        created_at TEXT NOT NULL DEFAULT CURRENT_TIMESTAMP
    )""")

def publish_datev(generated,destination,registry,source):
    """Publish complete PDFs exactly once per SHA256; never overwrite.

    Database write lock serializes competing workers. Existing handoff file with
    no registry record is treated as a conflict rather than overwritten.
    """
    destination=Path(destination)
    registry=Path(registry)
    sent=[]; duplicates=[]
    with sqlite3.connect(registry,timeout=30) as con:
        con.execute("BEGIN IMMEDIATE")
        ensure(con)
        for staged,_ in generated:
            staged=Path(staged)
            if not staged.is_file() or staged.stat().st_size==0:
                raise ValueError("Leere DATEV-Ausgabe")
            digest=hashlib.file_digest(staged.open("rb"),"sha256").hexdigest()
            filename=f"beleg_{digest}.pdf"
            target=destination/filename
            if con.execute("SELECT 1 FROM datev_invoices WHERE digest=?",(digest,)).fetchone():
                duplicates.append(filename)
                continue
            if target.exists() or target.is_symlink():
                raise FileExistsError(f"DATEV-Datei existiert ohne Registereintrag: {target}")
            # No partial PDF appears in the folder and existing files are safe.
            os.link(staged,target,follow_symlinks=False)
            con.execute("INSERT INTO datev_invoices(digest,filename,source) VALUES (?,?,?)",(digest,filename,str(source)))
            sent.append(str(target))
        con.commit()
    return {"outputs":sent,"duplicates":duplicates}

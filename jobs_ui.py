"""Shared job listing and explicit retry controls for QR Scan Manager."""
import sqlite3
from pathlib import Path

def ensure(con):
    con.execute("""CREATE TABLE IF NOT EXISTS jobs (
        signature TEXT PRIMARY KEY,
        profile_id INTEGER,
        file TEXT NOT NULL,
        status TEXT NOT NULL,
        details TEXT,
        updated_at TEXT DEFAULT CURRENT_TIMESTAMP
    )""")
    columns={x[1] for x in con.execute("PRAGMA table_info(jobs)")}
    if "attempts" not in columns:
        con.execute("ALTER TABLE jobs ADD COLUMN attempts INTEGER NOT NULL DEFAULT 0")
    if "next_retry" not in columns:
        con.execute("ALTER TABLE jobs ADD COLUMN next_retry TEXT")
    con.commit()

def dashboard(database):
    with sqlite3.connect(database, timeout=10) as con:
        ensure(con)
        totals=dict(con.execute("SELECT status, COUNT(*) FROM jobs GROUP BY status").fetchall())
        rows=con.execute("""SELECT j.signature,j.file,j.status,j.details,j.attempts,
            j.updated_at,COALESCE(p.name,'Profil entfernt')
            FROM jobs j LEFT JOIN profiles p ON p.id=j.profile_id
            ORDER BY j.updated_at DESC,j.rowid DESC LIMIT 100""").fetchall()
    return totals,rows

def request_retry(database,signature):
    if len(signature)!=64 or any(c not in "0123456789abcdef" for c in signature):
        return False,"Ungültige Auftragskennung"
    with sqlite3.connect(database,timeout=10) as con:
        ensure(con)
        row=con.execute("SELECT status,file FROM jobs WHERE signature=?",(signature,)).fetchone()
        if not row or row[0] not in ("error","interrupted"):
            return False,"Auftrag nicht im Zustand Fehler/Unterbrochen"
        if not Path(row[1]).is_file():
            return False,"Quelldatei nicht mehr vorhanden"
        # The PDF worker refuses existing filenames. This protects outputs on replay.
        updated=con.execute("""UPDATE jobs SET status='retry',attempts=0,next_retry=NULL,
            details='Manuell zur Wiederholung freigegeben – vorhandene Ausgaben bleiben geschützt',
            updated_at=CURRENT_TIMESTAMP WHERE signature=?
            AND status IN ('error','interrupted')""",(signature,))
        con.commit()
    return updated.rowcount==1, "Zur erneuten Prüfung freigegeben"

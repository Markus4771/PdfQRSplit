"""Safe read-only duplicate comparison and explicit review decisions.

Decisions never modify the DATEV publication registry or publish an invoice.
"""
import sqlite3
from pathlib import Path

DECISIONS=("confirmed","independent")
def ensure(con):
    con.execute("""CREATE TABLE IF NOT EXISTS duplicate_decisions (
        digest TEXT PRIMARY KEY, decision TEXT NOT NULL,
        note TEXT NOT NULL, decided_at TEXT DEFAULT CURRENT_TIMESTAMP)""")

def cases(con,source):
    exists=con.execute("SELECT 1 FROM sqlite_master WHERE type='table' AND name='duplicate_decisions'").fetchone()
    join="LEFT JOIN duplicate_decisions d ON d.digest=s.digest" if exists else "LEFT JOIN (SELECT NULL AS digest, NULL AS decision, NULL AS note) d ON 1=0"
    return con.execute("""SELECT s.digest,s.matching_digest,s.review_path,
          COALESCE(d.decision,''),COALESCE(d.note,''),
          COALESCE(i.filename,'')
          FROM datev_suspects s
          """+join+""" LEFT JOIN datev_invoices i ON i.digest=s.matching_digest
          WHERE s.source=? ORDER BY s.created_at DESC""",(source,)).fetchall()

def decision(con,digest,choice,note):
    if len(digest)!=64 or any(x not in "0123456789abcdef" for x in digest):
        raise ValueError("Ungültige Dublettensignatur")
    if choice not in DECISIONS:raise ValueError("Ungültige Entscheidung")
    if not note.strip() or len(note)>1000:raise ValueError("Eine Begründung mit höchstens 1000 Zeichen ist erforderlich")
    ensure(con)
    if not con.execute("SELECT 1 FROM datev_suspects WHERE digest=?",(digest,)).fetchone():
        raise ValueError("Dublette nicht im Prüfregister")
    con.execute("""INSERT INTO duplicate_decisions(digest,decision,note)
        VALUES (?,?,?) ON CONFLICT(digest) DO UPDATE SET
        decision=excluded.decision,note=excluded.note,decided_at=CURRENT_TIMESTAMP""",
        (digest,choice,note.strip()))

def inspected_pdf(con,digest,kind,private_root,samba_root):
    if len(digest)!=64 or any(x not in "0123456789abcdef" for x in digest):
        raise ValueError("Ungültige Dublettensignatur")
    row=con.execute("""SELECT s.review_path,i.filename FROM datev_suspects s
         LEFT JOIN datev_invoices i ON i.digest=s.matching_digest WHERE s.digest=?""",
         (digest,)).fetchone()
    if not row:raise ValueError("Dublette nicht vorhanden")
    if kind=="suspect":
        path=Path(row[0] or "")
        allowed=Path(private_root).resolve()
    elif kind=="matching":
        if not row[1]:raise FileNotFoundError("Vergleichsbeleg nicht im DATEV-Ausgang registriert")
        path=Path(samba_root)/row[1]
        allowed=Path(samba_root).resolve()
    else:raise ValueError("Ungültiger Vorschautyp")
    resolved=path.resolve(strict=True)
    if path.is_symlink() or not resolved.is_relative_to(allowed) or not resolved.is_file() or resolved.suffix.lower()!=".pdf":
        raise ValueError("Unsichere PDF-Pfadzuordnung")
    return resolved

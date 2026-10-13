#!/usr/bin/env python3
"""Grant minimal ACL rights for configured, manager-owned profile folders.
Run manually as root after adding/changing profiles. Never recurses into files.
"""
import os
import sqlite3
import subprocess
import sys
from pathlib import Path
from watcher import get_shares, DB, ROOT

def main():
    if os.geteuid()!=0:
        raise SystemExit("Als root ausführen")
    if not DB.is_file():
        raise SystemExit("Profil-Datenbank fehlt")
    with sqlite3.connect(f"file:{DB}?mode=ro",uri=True) as db:
        rows=db.execute("SELECT input_share,output_share FROM profiles").fetchall()
    shares=get_shares()
    assignments={}
    for inp,out in rows:
        if inp not in shares or out not in shares or inp==out:
            raise SystemExit(f"Nicht zugeordnete/ungültige Freigabe: {inp} -> {out}")
        assignments.setdefault(inp,set()).add("rx")
        assignments.setdefault(out,set()).add("rwx")
    for name,access in sorted(assignments.items()):
        directory=shares[name]
        # May include input and output roles; maximum rights apply.
        rights="rwx" if "rwx" in access else "rx"
        if directory.is_symlink() or directory.resolve().parent!=ROOT:
            raise SystemExit(f"Unsicherer Freigabepfad: {directory}")
        # Directory ACL and default ACL for new files; no recursive changes.
        # Default ACL for input allows QR worker to read new SMB-created files.
        args=[["setfacl","-m",f"u:qrscan:{rights}",str(directory)],
              ["setfacl","-m",f"d:u:qrscan:{rights}",str(directory)]]
        for cmd in args:
            subprocess.run(cmd,check=True)
        print(f"{name}: qrscan={rights} -> {directory}")
    print("Wichtig: Vorhandene Dateien benötigen ggf. eigene ACLs; keine rekursive Änderung durchgeführt.")

if __name__=="__main__":main()

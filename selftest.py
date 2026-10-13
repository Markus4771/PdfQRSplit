#!/usr/bin/env python3
"""Non-destructive installation and integration checks for a Debian QR Scan Manager host."""
import importlib
import os
import sqlite3
import subprocess
import sys
import tempfile
from pathlib import Path

BASE=Path("/opt/qrscan")
DATA=Path("/var/lib/qrscan")
FAIL=[]
def check(label,fn):
    try:
        result=fn()
        if result is False:raise RuntimeError("Prüfung fehlgeschlagen")
        print("[OK] "+label)
    except Exception as exc:
        print("[FEHLER] "+label+": "+str(exc))
        FAIL.append(label)

def command(*args):
    subprocess.run(args,check=True,stdout=subprocess.PIPE,stderr=subprocess.PIPE,timeout=15)

def syntax():
    for filename in ("app.py","watcher.py","worker.py","jobs_ui.py","sync_permissions.py"):
        path=BASE/filename
        compile(path.read_bytes(),str(path),"exec")
    return True

def pdf_deps():
    for name in ("fitz","PIL","pyzbar","scan_pdf_cleaner","pypdf","pypdfium2"):
        importlib.import_module(name)

def db_check():
    path=DATA/"profiles.sqlite3"
    if not path.exists():return False
    with sqlite3.connect(f"file:{path}?mode=ro",uri=True) as db:
        names={x[0] for x in db.execute("SELECT name FROM sqlite_master WHERE type='table'")}
    return {"profiles","settings"}.issubset(names)

def samba_check():
    # The app requires existing managed shares. In a fresh install this can be absent.
    p=Path("/etc/samba/share-manager.conf")
    if not p.exists():raise RuntimeError("Noch keine verwalteten Freigaben vorhanden – Samba-GUI-Integration ausstehend")
    return True

def test_service(name):
    command("systemctl","is-active","--quiet",name)

def permissions():
    u=__import__("pwd").getpwnam("qrscan")
    return u.pw_uid>=0 and (DATA/"auth.json").is_file()

def main():
    check("Python-Syntax aller Anwendungsmodule",syntax)
    check("PDF-/QR-Bibliotheken",pdf_deps)
    check("OCRmyPDF verfügbar",lambda: command("ocrmypdf","--version"))
    check("Tesseract verfügbar",lambda: command("tesseract","--version"))
    check("Samba-Konfiguration gültig",lambda:command("testparm","-s"))
    check("Datenbank-Schema",db_check)
    check("Dienstkonto und Zugangsdaten",permissions)
    check("Webdienst läuft",lambda:test_service("qrscan-web"))
    check("Verarbeitungsdienst läuft",lambda:test_service("qrscan-watcher"))
    check("Verwaltete Samba-Freigaben vorhanden",samba_check)
    print("\nErgebnis:",len(FAIL),"fehlgeschlagene Prüfungen")
    return 1 if FAIL else 0
if __name__=="__main__":
    sys.exit(main())

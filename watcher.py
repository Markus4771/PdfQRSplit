#!/usr/bin/env python3
"""Monitor Samba input shares and execute profile-based PDF processing."""
import hashlib
import logging
import os
import signal
import sqlite3
import sys
import time
from pathlib import Path

from worker import run

DATA=Path(os.getenv("QRSCAN_DATA","/var/lib/qrscan"))
DB=DATA/"profiles.sqlite3"
SAMBA=Path(os.getenv("QRSCAN_SAMBA_CONFIG","/etc/samba/share-manager.conf"))
ROOT=Path(os.getenv("QRSCAN_SHARE_ROOT","/srv/samba-shares")).resolve()
INTERVAL=max(2,int(os.getenv("QRSCAN_POLL_SECONDS","5")))
MIN_AGE=max(15,int(os.getenv("QRSCAN_STABILITY_SECONDS","30")))
STOP=False

def stop(*_):
    global STOP
    STOP=True

def get_shares():
    if not SAMBA.is_file():return {}
    result={}; name=None; attrs={}
    def save():
        if name is None:return
        path=Path(attrs.get("path",""))
        try:
            if path.is_dir() and not path.is_symlink() and path.resolve().parent==ROOT:
                result[name]=path
        except OSError:pass
    for row in SAMBA.read_text(errors="replace").splitlines():
        row=row.strip()
        if row.startswith("[") and row.endswith("]"):
            save();name=row[1:-1];attrs={}
        elif name and "=" in row:
            k,v=row.split("=",1);attrs[k.strip().lower()]=v.strip()
    save()
    return result

def connect():
    con=sqlite3.connect(DB,timeout=10)
    con.execute("""CREATE TABLE IF NOT EXISTS jobs (
       signature TEXT PRIMARY KEY, profile_id INTEGER, file TEXT NOT NULL,
       status TEXT NOT NULL, details TEXT, updated_at TEXT DEFAULT CURRENT_TIMESTAMP
    )""")
    con.commit()
    return con

def configs(con):
    return con.execute("SELECT id,name,input_share,output_share,qr_split,remove_separators,remove_blank,crop,ocr FROM profiles ORDER BY id").fetchall()

def fingerprint(path, st, profile_id):
    # A stable file identity, avoids repeat processing after watcher restart.
    digest=hashlib.sha256()
    digest.update(str(profile_id).encode())
    with path.open("rb") as f:
        for chunk in iter(lambda:f.read(1024*1024),b""):digest.update(chunk)
    return digest.hexdigest()

def once(con,profile,shares,seen):
    ident,name,in_share,out_share,*switches=profile
    source=shares.get(in_share);destination=shares.get(out_share)
    if source is None or destination is None or source==destination:
        logging.warning("Profile %s: invalid/inaccessible share mapping",name);return
    if not os.access(source,os.R_OK|os.X_OK) or not os.access(destination,os.W_OK|os.X_OK):
        logging.warning("Profile %s: missing filesystem permissions",name);return
    for path in sorted(source.glob("*.pdf")):
        try:
            if path.is_symlink() or not path.is_file():continue
            stat=path.stat()
            key=(ident,str(path))
            signature=(stat.st_size,stat.st_mtime_ns)
            previous=seen.get(key)
            seen[key]=(signature,time.monotonic()) if previous is None or previous[0]!=signature else previous
            if stat.st_size==0 or time.monotonic()-seen[key][1]<MIN_AGE or time.time()-stat.st_mtime<MIN_AGE:continue
            # Check PDF structure before processing or declaring job finished.
            import fitz
            with fitz.open(path) as doc:
                if doc.page_count<1:continue
            digest=fingerprint(path,stat,ident)
            row=con.execute("SELECT status FROM jobs WHERE signature=?",(digest,)).fetchone()
            if row:continue
            opts=dict(zip(("qr_split","remove_separators","remove_blank","crop","ocr"),map(bool,switches)))
            qr=con.execute("SELECT value FROM settings WHERE key='qr_text'").fetchone()[0]
            con.execute("INSERT INTO jobs(signature,profile_id,file,status) VALUES (?,?,?,'running')",(digest,ident,str(path)))
            con.commit()
            logging.info("Processing %s with profile %s",path,name)
            try:
                # Re-check source just before using it; source is never deleted.
                fresh=path.stat()
                if (fresh.st_size,fresh.st_mtime_ns)!=signature:raise RuntimeError("Source changed during preparation")
                result=run(path,destination,qr,opts)
                con.execute("UPDATE jobs SET status='done',details=?,updated_at=CURRENT_TIMESTAMP WHERE signature=?",(str(result),digest))
                logging.info("Completed %s: %s outputs",path,len(result["outputs"]))
            except Exception as ex:
                con.execute("UPDATE jobs SET status='error',details=?,updated_at=CURRENT_TIMESTAMP WHERE signature=?",(str(ex)[:1000],digest))
                logging.exception("Processing failed: %s",path)
            con.commit()
        except (OSError,sqlite3.Error,ValueError) as exc:
            logging.error("Unable to inspect %s: %s",path,exc)

def main():
    DATA.mkdir(parents=True,exist_ok=True)
    signal.signal(signal.SIGTERM,stop);signal.signal(signal.SIGINT,stop)
    logging.basicConfig(level=logging.INFO,format="%(asctime)s %(levelname)s %(message)s")
    seen={}
    logging.info("Profile watcher started; sources preserved; interval=%ss",INTERVAL)
    while not STOP:
        try:
            with connect() as con:
                shares=get_shares()
                profiles=configs(con)
                active={(p[0],str(shares[p[2]]/file.name)) for p in profiles if p[2] in shares for file in shares[p[2]].glob("*.pdf")}
                for key in list(seen):
                    if key not in active:seen.pop(key,None)
                for p in profiles:
                    if STOP:break
                    once(con,p,shares,seen)
        except Exception:
            logging.exception("Watcher loop failed")
        if not STOP:time.sleep(INTERVAL)
    logging.info("Watcher stopped")
if __name__=="__main__":main()

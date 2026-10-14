"""Per-company per-document-type job status exports to the dedicated LOG share."""
import json
import os
import tempfile
from datetime import datetime,timezone
from pathlib import Path

def log_directory(con,profile_id,shares):
    try:
        row=con.execute("""SELECT co.code,ln.doc_type FROM company_profile_links ln
             JOIN companies co ON co.id=ln.company_id WHERE ln.profile_id=?""",(profile_id,)).fetchone()
    except Exception:
        return None
    if not row:return None
    from company_admin import share_name
    return shares.get(share_name(row[0],row[1],"LOG"))

def write_job(con,profile_id,shares,signature,status,source,details=None):
    root=log_directory(con,profile_id,shares)
    if root is None:return False
    root=Path(root)
    if root.is_symlink() or not root.is_dir():raise ValueError("LOG-Freigabe nicht verfügbar")
    if not isinstance(signature,str) or len(signature)!=64 or any(c not in "0123456789abcdef" for c in signature):
        raise ValueError("Ungültige Auftragssignatur")
    payload={"signature":signature,"status":status,"source_file":Path(source).name,
             "timestamp":datetime.now(timezone.utc).isoformat(),
             "details":details or {}}
    fd,tmp=tempfile.mkstemp(prefix=".qrscan-log-",suffix=".tmp",dir=root)
    try:
        with os.fdopen(fd,"w",encoding="utf-8") as stream:
            json.dump(payload,stream,ensure_ascii=False,indent=2,default=str)
            stream.flush();os.fsync(stream.fileno())
        os.chmod(tmp,0o660)
        os.replace(tmp,root/("job_"+signature+".json"))
    finally:
        Path(tmp).unlink(missing_ok=True)
    return True

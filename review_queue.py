"""Review queue metadata for failed/warning PDF jobs; never releases DATEV documents."""
import sqlite3
from datetime import datetime, timezone
from pathlib import Path
from company_monitor import classify

STATES=("open","in_progress","resolved","dismissed")
def migrate(con):
    con.execute("""CREATE TABLE IF NOT EXISTS review_cases (
      signature TEXT PRIMARY KEY, state TEXT NOT NULL DEFAULT 'open',
      note TEXT NOT NULL DEFAULT '', updated_at TEXT NOT NULL DEFAULT CURRENT_TIMESTAMP)""")
    con.execute("""CREATE TABLE IF NOT EXISTS review_events (
      id INTEGER PRIMARY KEY AUTOINCREMENT, signature TEXT NOT NULL,
      event_at TEXT NOT NULL, actor TEXT NOT NULL,
      old_state TEXT, new_state TEXT NOT NULL,
      old_note TEXT NOT NULL, new_note TEXT NOT NULL)""")
    con.execute("CREATE INDEX IF NOT EXISTS ix_review_events_signature ON review_events(signature,id)")
def records(con,company="",doctype="",state="active",limit=150,allowed_companies=None):
    migrate(con)
    sql="""SELECT j.signature,j.file,j.status,j.details,j.updated_at,c.id,c.code,l.doc_type,
                 COALESCE(r.state,'open'),COALESCE(r.note,'')
          FROM jobs j JOIN company_profile_links l ON l.profile_id=j.profile_id
          JOIN companies c ON c.id=l.company_id
          LEFT JOIN review_cases r ON r.signature=j.signature
          WHERE j.status IN ('error','retry','interrupted','done')"""
    args=[]
    if allowed_companies is not None:
        if not allowed_companies:return []
        sql+=" AND c.id IN ("+",".join("?" for _ in allowed_companies)+")"
        args.extend(sorted(allowed_companies))
    if company:
        sql+=" AND c.id=?";args.append(int(company))
    if doctype:
        sql+=" AND l.doc_type=?";args.append(doctype)
    sql+=" ORDER BY j.updated_at DESC LIMIT 1000"
    out=[]
    for sig,path,status,details,when,cid,code,typ,case_state,note in con.execute(sql,args):
        category,severity,message=classify(status,details)
        if severity=="Erfolgreich":continue
        if state=="active" and case_state in ("resolved","dismissed"):continue
        if state in STATES and case_state!=state:continue
        out.append(dict(signature=sig,filename=Path(path).name,status=status,category=category,
            severity=severity,message=message,updated=str(when),cid=cid,company=code,
            doctype=typ,state=case_state,note=note))
        if len(out)>=limit:break
    return out
def history(con, signature, limit=25):
    migrate(con)
    if not isinstance(signature,str) or len(signature)!=64 or any(c not in "0123456789abcdef" for c in signature):
        raise ValueError("Ungültige Auftragssignatur")
    return [dict(timestamp=t,actor=a,old_state=o,new_state=n,old_note=on,new_note=nn)
            for t,a,o,n,on,nn in con.execute("""SELECT event_at,actor,old_state,new_state,old_note,new_note
                FROM review_events WHERE signature=? ORDER BY id DESC LIMIT ?""",(signature,max(1,min(int(limit),100))))]
def set_case(con,signature,state,note,actor="admin"):
    migrate(con)
    if state not in STATES:raise ValueError("Ungültiger Prüfstatus")
    if len(signature)!=64 or any(c not in "0123456789abcdef" for c in signature):
        raise ValueError("Ungültige Auftragssignatur")
    if len(note)>1000:raise ValueError("Notiz zu lang")
    if not isinstance(actor,str) or not actor.strip() or len(actor)>100:raise ValueError("Ungültiger Bearbeiter")
    row=con.execute("""SELECT j.status,j.details FROM jobs j JOIN company_profile_links l
        ON l.profile_id=j.profile_id WHERE j.signature=?""",(signature,)).fetchone()
    if not row:raise ValueError("Auftrag nicht vorhanden oder nicht firmenverwaltet")
    if classify(*row)[1]=="Erfolgreich":raise ValueError("Kein Prüfproblem in diesem Auftrag")
    previous=con.execute("SELECT state,note FROM review_cases WHERE signature=?",(signature,)).fetchone()
    if previous is not None and previous==(state,note):return
    con.execute("""INSERT INTO review_cases(signature,state,note) VALUES (?,?,?)
      ON CONFLICT(signature) DO UPDATE SET state=excluded.state,note=excluded.note,
      updated_at=CURRENT_TIMESTAMP""",(signature,state,note))
    con.execute("""INSERT INTO review_events(signature,event_at,actor,old_state,new_state,old_note,new_note)
        VALUES (?,?,?,?,?,?,?)""",(signature,datetime.now(timezone.utc).isoformat(),actor,
        previous[0] if previous else "open",state,previous[1] if previous else "",note))

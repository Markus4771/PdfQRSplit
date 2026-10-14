"""Review queue metadata for failed/warning PDF jobs; never releases DATEV documents."""
import sqlite3
from pathlib import Path
from company_monitor import classify

STATES=("open","in_progress","resolved","dismissed")
def migrate(con):
    con.execute("""CREATE TABLE IF NOT EXISTS review_cases (
      signature TEXT PRIMARY KEY, state TEXT NOT NULL DEFAULT 'open',
      note TEXT NOT NULL DEFAULT '', updated_at TEXT NOT NULL DEFAULT CURRENT_TIMESTAMP)""")
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
def set_case(con,signature,state,note):
    migrate(con)
    if state not in STATES:raise ValueError("Ungültiger Prüfstatus")
    if len(signature)!=64 or any(c not in "0123456789abcdef" for c in signature):
        raise ValueError("Ungültige Auftragssignatur")
    if len(note)>1000:raise ValueError("Notiz zu lang")
    row=con.execute("""SELECT j.status,j.details FROM jobs j JOIN company_profile_links l
        ON l.profile_id=j.profile_id WHERE j.signature=?""",(signature,)).fetchone()
    if not row:raise ValueError("Auftrag nicht vorhanden oder nicht firmenverwaltet")
    if classify(*row)[1]=="Erfolgreich":raise ValueError("Kein Prüfproblem in diesem Auftrag")
    con.execute("""INSERT INTO review_cases(signature,state,note) VALUES (?,?,?)
      ON CONFLICT(signature) DO UPDATE SET state=excluded.state,note=excluded.note,
      updated_at=CURRENT_TIMESTAMP""",(signature,state,note))

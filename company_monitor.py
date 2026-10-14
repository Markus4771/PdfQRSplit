"""Classify existing PDF job outcomes without inventing OCR confidence."""
import json

CATEGORIES=(
 ("duplicate",("dubletten","dublette","duplicate","bereits verarbeitet")),
 ("qr",("qr-trenn","qr-code","trennseite","trennblatt")),
 ("ocr",("ocr","tesseract","ghostscript")),
 ("pdf",("pdf","verschlüsselt","password","beschädigt","damaged","page count")),
 ("archive",("archiv","original","sha256")),
 ("output",("datev","freigabe","schreib","ausgabedatei","speicherplatz")),
)
TITLES={"duplicate":"Dublette","qr":"QR-Trennung","ocr":"OCR","pdf":"PDF-Datei","archive":"Archivierung","output":"DATEV / Ausgabe","other":"Sonstiges"}

def classify(status,details):
    try:
        data=json.loads(details) if isinstance(details,str) else details
    except (ValueError,TypeError):
        data=details
    if not isinstance(data,dict):data={"message":str(data or "")}
    message=str(data.get("message") or data.get("error") or data.get("archive_warning") or (details if not isinstance(details,dict) else "") or "")
    low=message.lower()
    category=next((category for category,words in CATEGORIES if any(word in low for word in words)),"other")
    warning=bool(status=="done" and (data.get("archive_warning") or data.get("duplicates")))
    if warning and data.get("duplicates"):category="duplicate"
    if warning and data.get("archive_warning"):category="archive"
    return category,("Warnung" if warning else "Fehler" if status in ("error","interrupted") else "Wiederholung" if status=="retry" else "Erfolgreich"),message

def summary(con,company_id,limit=12):
    rows=con.execute("""SELECT j.file,j.status,j.details,j.updated_at,l.doc_type
       FROM jobs j JOIN company_profile_links l ON l.profile_id=j.profile_id
       WHERE l.company_id=? ORDER BY j.updated_at DESC LIMIT 250""",(company_id,)).fetchall()
    counters={"done":0,"error":0,"retry":0,"interrupted":0,"warning":0}
    problems=[]
    for filename,status,details,updated,doctype in rows:
        category,severity,message=classify(status,details)
        if status in counters:counters[status]+=1
        if severity=="Warnung":counters["warning"]+=1
        if severity!="Erfolgreich" and len(problems)<limit:
            from pathlib import Path
            problems.append({"file":Path(filename).name,"status":status,"category":TITLES[category],
                             "severity":severity,"message":message[:260],"time":str(updated),"type":doctype})
    return counters,problems

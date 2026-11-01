"""Shared scan actions with strict profile/tenant scoping."""
import re
from pathlib import Path

ADDRESS=re.compile(r"^[^\s@,;<>]+@[^\s@,;<>]+\.[^\s@,;<>]+$")

def permitted_profiles(con,username,admin=False):
    if admin:
        return con.execute("SELECT id,name,output_share FROM profiles ORDER BY name").fetchall()
    return con.execute("""SELECT DISTINCT p.id,p.name,p.output_share
      FROM profiles p WHERE EXISTS(
        SELECT 1 FROM private_scan_profiles x WHERE x.profile_id=p.id AND x.username=?)
      OR EXISTS(
        SELECT 1 FROM company_profile_links l JOIN company_access a ON a.company_id=l.company_id
          WHERE l.profile_id=p.id AND a.username=? AND a.role IN ('read','input','write','admin'))
      ORDER BY p.name""",(username,username)).fetchall()

def find_document(con,username,admin,profile_id,filename,root):
    profiles={p[0]:p[2] for p in permitted_profiles(con,username,admin)}
    if profile_id not in profiles:raise PermissionError("Profil nicht freigegeben")
    if not isinstance(filename,str) or filename in (".","..") or Path(filename).name!=filename or not filename or "/" in filename or "\\" in filename:
        raise ValueError("Ungültiger Dateiname")
    directory=Path(root).resolve()/profiles[profile_id]
    if directory.is_symlink() or not directory.is_dir() or directory.resolve().parent!=Path(root).resolve():
        raise PermissionError("Ungültiges Ausgangsverzeichnis")
    target=directory/filename
    if target.is_symlink() or not target.is_file() or target.resolve().parent!=directory:
        raise FileNotFoundError("Datei fehlt oder ist unzulässig")
    if target.suffix.lower() not in (".pdf",".jpg",".jpeg",".png",".vcf"):
        raise ValueError("Dateityp nicht freigegeben")
    if target.stat().st_size>20*1024*1024:raise ValueError("Datei größer als 20 MB")
    return target

def valid_recipient(address):
    return isinstance(address,str) and len(address)<=254 and bool(ADDRESS.fullmatch(address))

def business_card_vcard(name,company,email,phone):
    fields=(name,company,email,phone)
    if any(not isinstance(x,str) or len(x)>256 or any(c in x for c in "\r\n\0") for x in fields):
        raise ValueError("Ungültige Visitenkartenfelder")
    if email and not valid_recipient(email):raise ValueError("Ungültige E-Mail")
    esc=lambda x:x.replace("\\","\\\\").replace(";","\\;").replace(",","\\,")
    return "BEGIN:VCARD\r\nVERSION:3.0\r\nFN:"+esc(name)+"\r\nORG:"+esc(company)+"\r\nEMAIL:"+email+"\r\nTEL:"+esc(phone)+"\r\nEND:VCARD\r\n"

def send_scan(settings,path,recipient):
    """Explicit SMTP send of one checked attachment; never deletes source."""
    import smtplib
    import ssl
    from email.message import EmailMessage
    if not valid_recipient(recipient):raise ValueError("Ungültige Empfängeradresse")
    if settings.get("mode") not in ("ssl","starttls") or not settings.get("host") or not settings.get("sender"):
        raise ValueError("SMTP muss zunächst konfiguriert werden")
    content=path.read_bytes()
    if len(content)>20*1024*1024:raise ValueError("Datei zu groß")
    mail=EmailMessage()
    mail["From"]=settings["sender"]
    mail["To"]=recipient
    mail["Subject"]="Scan: "+path.name
    mail.set_content("Im Anhang befindet sich der angeforderte Scan.")
    kinds={".pdf":("application","pdf"),".jpg":("image","jpeg"),".jpeg":("image","jpeg"),".png":("image","png"),".vcf":("text","vcard")}
    kind=kinds[path.suffix.lower()]
    mail.add_attachment(content,maintype=kind[0],subtype=kind[1],filename=path.name)
    context=ssl.create_default_context()
    if settings["mode"]=="ssl":
        with smtplib.SMTP_SSL(settings["host"],int(settings["port"]),timeout=15,context=context) as smtp:
            if settings.get("username"):smtp.login(settings["username"],settings["secret"])
            smtp.send_message(mail)
    else:
        with smtplib.SMTP(settings["host"],int(settings["port"]),timeout=15) as smtp:
            smtp.ehlo()
            smtp.starttls(context=context)
            smtp.ehlo()
            if settings.get("username"):smtp.login(settings["username"],settings["secret"])
            smtp.send_message(mail)

def parse_card_text(text):
    """Heuristic OCR draft only; user must confirm before exporting."""
    if not isinstance(text,str):raise ValueError("Ungültiger OCR-Text")
    lines=[line.strip()[:256] for line in text.splitlines() if line.strip()][:20]
    email_match=re.search(r"[A-Za-z0-9._%+-]+@[A-Za-z0-9.-]+\\.[A-Za-z]{2,}",text)
    email=email_match.group(0) if email_match else ""
    phone_match=re.search(r"(?:\\+?\\d[\\d ()/.-]{6,}\\d)",text)
    phone=phone_match.group(0).strip()[:64] if phone_match else ""
    return {"name":lines[0] if lines else "","company":lines[1] if len(lines)>1 else "","email":email,"phone":phone}

def read_business_card(path):
    """OCR a scanned JPEG/PNG business card using installed Tesseract."""
    import subprocess
    if path.suffix.lower() not in (".jpg",".jpeg",".png"):
        raise ValueError("Visitenkarten-OCR erwartet JPEG/PNG")
    proc=subprocess.run(["tesseract",str(path),"stdout","-l","deu+eng","--psm","6"],
                        text=True,capture_output=True,timeout=25,check=False)
    if proc.returncode:raise ValueError("OCR nicht verfügbar oder fehlgeschlagen")
    return parse_card_text(proc.stdout)

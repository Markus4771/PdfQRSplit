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

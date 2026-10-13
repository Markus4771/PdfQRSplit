#!/usr/bin/env python3
"""QR Scan Manager: protected LAN web UI and profile configuration."""
import base64
import hashlib
import hmac
import html
import json
import os
import re
import secrets
import sqlite3
import subprocess
from http.server import BaseHTTPRequestHandler, ThreadingHTTPServer
from pathlib import Path
from urllib.parse import parse_qs

DATA=Path(os.getenv("QRSCAN_DATA","/var/lib/qrscan"))
ROOT=Path(os.getenv("QRSCAN_SHARE_ROOT","/srv/samba-shares")).resolve()
AUTH=DATA/"auth.json"
DB=DATA/"profiles.sqlite3"
PORT=int(os.getenv("QRSCAN_PORT","8086"))
NAME=re.compile(r"^[A-Za-z][A-Za-z0-9_-]{0,39}$")
FIELDS=("qr_split","remove_separators","remove_blank","crop","ocr")
def db():
    c=sqlite3.connect(DB)
    c.execute("""CREATE TABLE IF NOT EXISTS profiles(
    id INTEGER PRIMARY KEY, name TEXT UNIQUE NOT NULL, input_share TEXT NOT NULL,
    output_share TEXT NOT NULL, qr_split INTEGER NOT NULL DEFAULT 1,
    remove_separators INTEGER NOT NULL DEFAULT 0, remove_blank INTEGER NOT NULL DEFAULT 0,
    crop INTEGER NOT NULL DEFAULT 0, ocr INTEGER NOT NULL DEFAULT 0)""")
    c.execute("""CREATE TABLE IF NOT EXISTS settings(key TEXT PRIMARY KEY, value TEXT NOT NULL)""")
    c.execute("INSERT OR IGNORE INTO settings VALUES ('qr_text','SCAN-TRENNUNG-001')")
    c.commit()
    return c

def shares():
    """Only manager-owned shares under designated root, never arbitrary filesystem paths."""
    p=Path(os.getenv("QRSCAN_SAMBA_CONFIG","/etc/samba/share-manager.conf"))
    if not p.is_file(): return []
    results=[]
    current=None; params={}
    def collect():
        if not current or not NAME.fullmatch(current): return
        path=params.get("path","")
        try:
            d=Path(path)
            if d.is_symlink() or not d.is_dir() or d.resolve().parent!=ROOT: return
        except (OSError, ValueError): return
        results.append(current)
    for line in p.read_text(errors="replace").splitlines():
        line=line.strip()
        if line.startswith("[") and line.endswith("]"):
            collect(); current=line[1:-1]; params={}
        elif "=" in line and current:
            k,v=line.split("=",1); params[k.strip().lower()]=v.strip()
    collect()
    return sorted(results)

def encode_password(password):
    salt=secrets.token_bytes(16)
    return {"salt":salt.hex(),"rounds":600000,"digest":hashlib.pbkdf2_hmac("sha256",password.encode(),salt,600000).hex()}
def valid_auth(value):
    try:
        raw=base64.b64decode(value.removeprefix("Basic "),validate=True).decode()
        username,password=raw.split(":",1)
        a=json.loads(AUTH.read_text())
        hashed=hashlib.pbkdf2_hmac("sha256",password.encode(),bytes.fromhex(a["salt"]),a["rounds"]).hex()
        return username=="admin" and hmac.compare_digest(hashed,a["digest"])
    except (OSError,ValueError,KeyError,UnicodeError): return False

STYLE="""<style>body{font:15px system-ui;background:#f5f6f8;color:#26292e;max-width:1080px;margin:35px auto;padding:0 16px}header{display:flex;justify-content:space-between;align-items:center}section{background:white;border:1px solid #ddd;border-radius:12px;padding:22px;margin:18px 0}input,select{width:100%;box-sizing:border-box;padding:10px;margin:6px 0 14px;border:1px solid #ccc;border-radius:7px}input[type=checkbox]{width:auto;margin:0 7px 0 0}label{display:block;margin:8px 0}button{background:#26292e;color:white;padding:11px 17px;border:0;border-radius:8px;cursor:pointer}.row{display:grid;grid-template-columns:1fr 1fr;gap:16px}.small{color:#666;font-size:13px}.notice{color:#964514}@media(max-width:700px){.row{grid-template-columns:1fr}}</style>"""

class Handler(BaseHTTPRequestHandler):
    def page(self, content, status=200, unauthorized=False):
        payload=("<!doctype html><html lang='de'><meta charset='utf-8'><meta name='viewport' content='width=device-width,initial-scale=1'>"+STYLE+"<title>QR Scan Manager</title>"+content+"</html>").encode()
        self.send_response(status)
        self.send_header("Content-Type","text/html; charset=utf-8")
        self.send_header("Content-Length",str(len(payload)))
        self.send_header("Cache-Control","no-store")
        self.send_header("X-Frame-Options","DENY")
        self.send_header("Content-Security-Policy","default-src 'none'; style-src 'unsafe-inline'; form-action 'self'")
        if unauthorized:self.send_header("WWW-Authenticate",'Basic realm="QR Scan Manager"')
        self.end_headers();self.wfile.write(payload)
    def guard(self):
        if not valid_auth(self.headers.get("Authorization","")):
            self.page("<h1>Anmeldung erforderlich</h1>",401,True);return False
        return True
    def password_needed(self):
        return bool(json.loads(AUTH.read_text()).get("must_change"))
    def password_form(self,msg=""):
        self.page("<h1>Administratorpasswort ändern</h1><p>"+html.escape(msg)+"</p><section><form method='post' action='/password'><label>Neues Passwort (mindestens 12 Zeichen)</label><input type='password' name='password' minlength='12' required><label>Wiederholen</label><input type='password' name='confirm' minlength='12' required><button>Passwort ändern</button></form></section>")
    def do_GET(self):
        if not self.guard():return
        if self.path!="/":return self.page("Nicht gefunden",404)
        if self.password_needed():return self.password_form()
        s=shares()
        with db() as c:
            profiles=c.execute("SELECT id,name,input_share,output_share,qr_split,remove_separators,remove_blank,crop,ocr FROM profiles ORDER BY name").fetchall()
            qr=c.execute("SELECT value FROM settings WHERE key='qr_text'").fetchone()[0]
        options="".join("<option value='"+html.escape(n,quote=True)+"'>"+html.escape(n)+"</option>" for n in s)
        rows=""
        for p in profiles:
            checked=", ".join(k for k,v in zip(FIELDS,p[4:]) if v) or "Keine"
            rows+="<p><b>"+html.escape(p[1])+"</b>: "+html.escape(p[2])+" → "+html.escape(p[3])+"<br><span class='small'>"+html.escape(checked)+"</span></p><form method='post' action='/delete'><input type='hidden' name='id' value='"+str(p[0])+"'><button>Profil entfernen</button></form><hr>"
        msg="<p class='notice'>Keine kompatiblen Samba-Freigaben gefunden. Zuerst Freigaben im bestehenden Samba-Manager anlegen.</p>" if not s else ""
        self.page("<header><h1>QR Scan Manager</h1><span>Konfiguration</span></header><section><h2>QR-Trenncode</h2><form method='post' action='/qr'><input name='qr' maxlength='256' value='"+html.escape(qr,quote=True)+"' required><button>QR-Code speichern</button></form></section><section><h2>Neues Verarbeitungsprofil</h2>"+msg+"<form method='post' action='/add'><label>Name</label><input name='name' required maxlength='40'><div class='row'><div><label>Eingangsfreigabe</label><select name='input'>"+options+"</select></div><div><label>Ausgangsfreigabe</label><select name='output'>"+options+"</select></div></div>"+"".join("<label><input type='checkbox' name='"+k+"'"+(" checked" if k=="qr_split" else "")+">"+title+"</label>" for k,title in [("qr_split","QR-Code-Trennung"),("remove_separators","QR-Trennblätter entfernen"),("remove_blank","Leerseiten entfernen (Scan PDF Cleaner)"),("crop","Ränder beschneiden (Scan PDF Cleaner)"),("ocr","OCRmyPDF am Schluss")])+"<button>Profil anlegen</button></form></section><section><h2>Profile</h2>"+(rows or "Keine Profile angelegt")+"</section><p class='small'>Samba-Benutzer und Passwörter bleiben im separaten Samba-Manager. Der PDF-Worker ist noch nicht aktiviert. GUI nur im geschützten LAN betreiben.</p>")
    def do_POST(self):
        if not self.guard():return
        if self.path not in ("/password","/qr","/add","/delete"):return self.page("Nicht gefunden",404)
        origin=self.headers.get("Origin")
        if origin and origin != "http://"+self.headers.get("Host",""):return self.page("Ungültiger Ursprung",403)
        try:
            length=int(self.headers.get("Content-Length","0"))
            if length>8192 or length<1:raise ValueError()
            data=parse_qs(self.rfile.read(length).decode(),keep_blank_values=True)
            get=lambda k:data.get(k,[""])[0]
        except (ValueError,UnicodeDecodeError):return self.page("Ungültige Eingabe",400)
        if self.path=="/password":
            if not self.password_needed():return self.page("Bereits eingerichtet",403)
            value=get("password")
            if value!=get("confirm") or len(value)<12 or len(value)>256:return self.password_form("Passwörter stimmen nicht überein oder sind zu kurz.")
            new=encode_password(value);new["must_change"]=False
            tmp=AUTH.with_suffix(".tmp");tmp.write_text(json.dumps(new));os.chmod(tmp,0o600);os.replace(tmp,AUTH)
            self.page("<h1>Passwort gespeichert</h1><p>Bitte Browseranmeldung neu durchführen.</p>");return
        if self.password_needed():return self.password_form()
        with db() as c:
            if self.path=="/qr":
                value=get("qr").strip()
                if not value or len(value)>256:return self.page("Ungültiger QR-Inhalt",400)
                c.execute("UPDATE settings SET value=? WHERE key='qr_text'",(value,))
            elif self.path=="/add":
                name=get("name").strip();inp=get("input");out=get("output")
                if not NAME.fullmatch(name) or inp not in shares() or out not in shares() or inp==out:return self.page("Ungültige Profil- oder Freigabenauswahl",400)
                values=[int(k in data) for k in FIELDS]
                try:c.execute("INSERT INTO profiles(name,input_share,output_share,qr_split,remove_separators,remove_blank,crop,ocr) VALUES (?,?,?,?,?,?,?,?)",(name,inp,out,*values))
                except sqlite3.IntegrityError:return self.page("Profilname schon vorhanden",409)
            elif self.path=="/delete":
                try:ident=int(get("id"))
                except ValueError:return self.page("Ungültige ID",400)
                c.execute("DELETE FROM profiles WHERE id=?",(ident,))
        self.send_response(303);self.send_header("Location","/");self.end_headers()

if __name__=="__main__":
    DATA.mkdir(parents=True,exist_ok=True)
    if not AUTH.exists():raise SystemExit("Auth-Datei fehlt. Installer ausführen.")
    with db():pass
    ThreadingHTTPServer((os.getenv("QRSCAN_BIND","127.0.0.1"),PORT),Handler).serve_forever()

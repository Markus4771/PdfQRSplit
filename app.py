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
import socket
import sqlite3
import subprocess
from http.server import BaseHTTPRequestHandler, ThreadingHTTPServer
from pathlib import Path
from urllib.parse import parse_qs
from jobs_ui import dashboard,request_retry,file_flags,save_retention
from profile_settings import migrate,check,controls,SELECT

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
    migrate(c)
    c.commit()
    return c

def shares():
    """Only manager-owned shares under designated root, never arbitrary filesystem paths."""
    p=Path(os.getenv("QRSCAN_SAMBA_CONFIG","/etc/samba/qrscan-shares.conf"))
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

def samba_call(payload):
    try:
        with socket.socket(socket.AF_UNIX,socket.SOCK_STREAM) as conn:
            conn.settimeout(50)
            conn.connect("/run/qrscan/samba.sock")
            conn.sendall(json.dumps(payload).encode())
            conn.shutdown(socket.SHUT_WR)
            reply=b""
            while len(reply)<65536:
                data=conn.recv(4096)
                if not data:break
                reply+=data
        return json.loads(reply)
    except (OSError,ValueError):
        return {"ok":False,"error":"Samba-Verwaltungsdienst nicht erreichbar"}


def ensure_datev_samba_protection(name):
    """Require an explicitly selected DATEV output and switch SMB clients to read-only."""
    response=samba_call({"action":"list"})
    if not response.get("ok"):
        raise ValueError("Samba-Manager nicht erreichbar: "+response.get("error","Unbekannter Fehler"))
    match=next((x for x in response.get("shares",[]) if x.get("name")==name),None)
    if match is None:
        raise ValueError("DATEV-Ausgang ist keine verwaltete Samba-Freigabe")
    if not match.get("datev_protected") or match.get("writable"):
        change=samba_call({"action":"protect-datev","name":name})
        if not change.get("ok"):
            raise ValueError("DATEV-Schutz konnte nicht aktiviert werden: "+change.get("error","Unbekannter Fehler"))

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
        if self.path not in ("/","/jobs","/datev-review"):return self.page("Nicht gefunden",404)
        if self.password_needed():return self.password_form()
        if self.path=="/datev-review":
            entries=[]
            registry=DATA/"datev.sqlite3"
            if registry.is_file():
                with sqlite3.connect("file:"+str(registry)+"?mode=ro",uri=True) as con:
                    tables={r[0] for r in con.execute("SELECT name FROM sqlite_master WHERE type='table'")}
                    if "datev_suspects" in tables:
                        columns={r[1] for r in con.execute("PRAGMA table_info(datev_suspects)")}
                        if "review_path" in columns:
                            entries=con.execute("SELECT digest,source,matching_digest,review_path FROM datev_suspects ORDER BY created_at DESC LIMIT 200").fetchall()
            lines=[]
            for digest,source,match,path in entries:
                present=bool(path and Path(path).is_file())
                lines.append("<p><b>"+html.escape(digest[:16])+"</b> | Quelle: "+html.escape(source or "")+
                             " | Vergleich: "+html.escape((match or "")[:16])+
                             " | "+("Prüfdatei vorhanden: " if present else "Prüfdatei fehlt: ")+html.escape(path or "")+"</p>")
            return self.page("<header><h1>DATEV-Prüfbereich</h1><a href='/jobs'>Aufträge & Fehler</a></header><section>"+
                ("".join(lines) or "Keine Verdachtsfälle")+"</section>")
        if self.path=="/jobs":
            with db(): pass
            totals,rows,retention=dashboard(DB)
            counts="".join("<b>"+html.escape(k)+": "+str(v)+"</b> &nbsp; " for k,v in sorted(totals.items()))
            lines=[]
            for signature,filename,status,details,attempts,updated,profile in rows:
                entry="<article><p><b>"+html.escape(status)+"</b> · "+html.escape(profile)+" · "+html.escape(updated or "")+"</p>"
                entry+="<p>"+html.escape(filename)+"</p><p class='small'>Versuche: "+str(attempts or 0)+" · "+html.escape(str(details or "")[:1000])+"</p>"
                source_missing,missing_outputs,total_outputs=file_flags(status,filename,details)
                if source_missing:
                    entry+="<p class='notice'>Quelle fehlt – Wiederholung nicht möglich</p>"
                if missing_outputs is not None:
                    if missing_outputs:
                        entry+="<p class='notice'>Ausgabe fehlt: "+str(missing_outputs)+" von "+str(total_outputs)+" Datei(en)</p>"
                    else:
                        entry+="<p class='small'>Ausgabedateien vorhanden: "+str(total_outputs)+"</p>"
                if not source_missing and status in ("done","error","interrupted"):
                    entry+=("<form method='post' action='/retry'>"
                           "<input type='hidden' name='signature' value='"+signature+"'>"
                           "<button>Verarbeitung wiederholen</button></form>")
                lines.append(entry+"</article><hr>")
            return self.page("<header><h1>Auftragsübersicht</h1><a href='/'>Zur Konfiguration</a> · <a href='/datev-review'>DATEV-Prüfbereich</a></header>"
                             "<section><h2>Status</h2>"+(counts or "Keine Aufträge")+"</section>"
                             "<section><h2>Datenbank-Aufbewahrung</h2><form method='post' action='/retention'><label>Abgeschlossene und fehlgeschlagene Aufträge nach Tagen entfernen (7–3650)</label><input type='number' min='7' max='3650' name='days' value='"+str(retention)+"' required><button>Aufbewahrung speichern</button></form><p class='small'>Standard: 90 Tage. Nur Auftragseinträge werden bereinigt; PDFs bleiben unverändert. Die Bereinigung erfolgt automatisch durch den Watcher.</p></section>"
                             "<section><h2>Letzte 100 Aufträge</h2>"+("".join(lines) or "Noch keine Aufträge")+"</section>"
                             "<p class='small'>Bei Wiederholung abgeschlossener Aufträge werden neue Ausgabedateien mit eigenem Namenszusatz erstellt. "
                             "Bei Konflikten bleibt der Auftrag fehlgeschlagen.</p>")
        s=shares()
        with db() as c:
            profiles=c.execute("SELECT "+SELECT+" FROM profiles ORDER BY name").fetchall()
            qr=c.execute("SELECT value FROM settings WHERE key='qr_text'").fetchone()[0]
        options="".join("<option value='"+html.escape(n,quote=True)+"'>"+html.escape(n)+"</option>" for n in s)
        rows=""
        for p in profiles:
            checked=", ".join(k for k,v in zip(FIELDS,p[4:]) if v) or "Keine"
            rows+=controls(p,s,"/profile-update")+"<p><b>"+html.escape(p[1])+"</b>: "+html.escape(p[2])+" → "+html.escape(p[3])+"<br><span class='small'>"+html.escape(checked)+"</span></p><form method='post' action='/delete'><input type='hidden' name='id' value='"+str(p[0])+"'><button>Profil entfernen</button></form><hr>"
        msg="<p class='notice'>Keine kompatiblen Samba-Freigaben gefunden. Zuerst Freigaben im bestehenden Samba-Manager anlegen.</p>" if not s else ""
        result=samba_call({"action":"list"})
        smb_html="<section><h2>Samba-Freigaben</h2><form method='post' action='/smb-create'><label>Freigabename</label><input name='name' required><label>SMB-Benutzer</label><input name='user' required><label>SMB-Passwort (mind. 12 Zeichen)</label><input name='password' type='password' minlength='12' required><label><input type='checkbox' name='writable' checked> Schreibzugriff</label><label><input type='checkbox' name='datev_protected'> DATEV-Übergabe: Windows nur lesen</label><button>Freigabe anlegen</button></form>"
        for entry in result.get("shares",[]):
            safe=html.escape(entry["name"],quote=True)
            smb_html+="<h3>"+safe+"</h3><p>Benutzer: "+html.escape(entry.get("user",""))+"</p>"
            if entry.get("datev_protected"):
                smb_html+="<p><b>DATEV geschützt: SMB nur lesen</b></p>"
            else:
                smb_html+="<form method='post' action='/smb-protect-datev'><input type='hidden' name='name' value='"+safe+"'><button>Als DATEV-Übergabe schützen (Windows nur lesen)</button></form>"
            smb_html+="<form method='post' action='/smb-update'><input type='hidden' name='name' value='"+safe+"'><label>Auf vorhandenen SMB-Benutzer umstellen (optional)</label><input name='user' placeholder='Bestehender SMB-Benutzer'><label>Passwort dieses Benutzers</label><input name='password' type='password' placeholder='Nur bei Benutzerwechsel'><label>Zugriff</label><select name='writable'><option value='yes'>Lesen/Schreiben</option><option value='no'>Nur lesen</option></select><button>Freigabe speichern</button></form>"
            smb_html+="<form method='post' action='/smb-password'><input type='hidden' name='name' value='"+safe+"'><input type='password' name='password' minlength='12' required placeholder='Neues SMB-Passwort'><button>Passwort ändern</button></form>"
            smb_html+="<form method='post' action='/smb-delete'><input type='hidden' name='name' value='"+safe+"'><button>Freigabe entfernen (Dateien bleiben)</button></form>"
        smb_html+="</section>"
        if not result.get("ok"): smb_html="<p class='notice'>"+html.escape(result.get("error","Samba-Fehler"))+"</p>"+smb_html
        self.page("<header><h1>QR Scan Manager</h1><a href='/jobs'>Aufträge & Fehler</a></header><section><h2>QR-Trenncode</h2><form method='post' action='/qr'><input name='qr' maxlength='256' value='"+html.escape(qr,quote=True)+"' required><button>QR-Code speichern</button></form></section><section><h2>Neues Verarbeitungsprofil</h2>"+msg+"<form method='post' action='/add'><label>Name</label><input name='name' required maxlength='40'><div class='row'><div><label>Eingangsfreigabe</label><select name='input'>"+options+"</select></div><div><label>Ausgangsfreigabe</label><select name='output'>"+options+"</select></div></div>"+"".join("<label><input type='checkbox' name='"+k+"'"+(" checked" if k=="qr_split" else "")+">"+title+"</label>" for k,title in [("qr_split","QR-Code-Trennung"),("remove_separators","QR-Trennblätter entfernen"),("remove_blank","Leerseiten entfernen (Scan PDF Cleaner)"),("crop","Ränder beschneiden (Scan PDF Cleaner)"),("ocr","OCRmyPDF am Schluss"),("datev_mode","DATEV-Sicherheitsmodus (eigene Ausgangsfreigabe verwenden)")])+"<label>Original-Archiv (separate Samba-Freigabe)</label><select name='archive_share'><option value=''>Internes Archiv (bisher)</option>"+options+"</select>"+"<button>Profil anlegen</button></form></section>"+smb_html+"<section><h2>Profile</h2>"+(rows or "Keine Profile angelegt")+"</section><p class='small'>Samba-Benutzer und Passwörter bleiben im separaten Samba-Manager. Der PDF-Worker ist noch nicht aktiviert. GUI nur im geschützten LAN betreiben.</p>")
    def do_POST(self):
        if not self.guard():return
        if self.path not in ("/password","/qr","/add","/delete","/retry","/smb-create","/smb-update","/smb-password","/smb-delete","/smb-protect-datev","/profile-update","/retention"):return self.page("Nicht gefunden",404)
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
        if self.path=="/retention":
            try:
                save_retention(DB,int(get("days")))
            except ValueError:
                return self.page("Ungültige Aufbewahrungsdauer (7–3650 Tage)",400)
            self.send_response(303);self.send_header("Location","/jobs");self.end_headers()
            return
        if self.path=="/retry":
            ok,message=request_retry(DB,get("signature"))
            if not ok:
                return self.page("<h1>Wiederholung nicht möglich</h1><p>"+html.escape(message)+"</p>",409)
            self.send_response(303);self.send_header("Location","/jobs");self.end_headers()
            return
        if self.path.startswith("/smb-"):
            action=self.path[5:]
            payload={"action":action,"name":get("name")}
            if action=="create":payload.update(user=get("user"),password=get("password"),writable="writable" in data,datev_protected="datev_protected" in data)
            if action=="password":payload["password"]=get("password")
            if action=="update":payload.update(writable=get("writable")=="yes",user=get("user").strip(),password=get("password"))
            if action=="delete":
                with db() as con:
                    used=con.execute("SELECT COUNT(*) FROM profiles WHERE input_share=? OR output_share=? OR archive_share=?",(get("name"),get("name"),get("name"))).fetchone()[0]
                if used:return self.page("<h1>Freigabe ist noch einem Profil zugeordnet</h1>",409)
            outcome=samba_call(payload)
            if not outcome.get("ok"):return self.page("<h1>Samba-Fehler</h1><p>"+html.escape(outcome.get("error","Fehler"))+"</p>",400)
            self.send_response(303);self.send_header("Location","/");self.end_headers();return
        with db() as c:
            if self.path=="/qr":
                value=get("qr").strip()
                if not value or len(value)>256:return self.page("Ungültiger QR-Inhalt",400)
                c.execute("UPDATE settings SET value=? WHERE key='qr_text'",(value,))
            elif self.path=="/add":
                name=get("name").strip();inp=get("input");out=get("output")
                if not NAME.fullmatch(name) or inp not in shares() or out not in shares() or inp==out:return self.page("Ungültige Profil- oder Freigabenauswahl",400)
                values=[int(k in data) for k in FIELDS]
                datev=int("datev_mode" in data)
                if datev and "qr_split" not in data:
                    return self.page("DATEV-Modus benötigt QR-Trennung; QR-Trennblätter dürfen erhalten bleiben",400)
                if datev and c.execute("SELECT 1 FROM profiles WHERE output_share=? LIMIT 1",(out,)).fetchone():
                    return self.page("DATEV-Ausgang muss exklusiv sein",409)
                if c.execute("SELECT 1 FROM profiles WHERE archive_share IN (?,?) LIMIT 1",(inp,out)).fetchone():
                    return self.page("Eingang/Ausgang ist als Original-Archiv reserviert",409)
                if not datev and c.execute("SELECT 1 FROM profiles WHERE output_share=? AND datev_mode=1 LIMIT 1",(out,)).fetchone():
                    return self.page("Ausgang bereits für DATEV reserviert",409)
                archive=get("archive_share")
                if archive and (not datev or archive not in shares() or archive in (inp,out)):
                    return self.page("Ungültige Original-Archiv-Freigabe",400)
                if archive and c.execute("SELECT 1 FROM profiles WHERE input_share=? OR output_share=? OR archive_share=? LIMIT 1",(archive,archive,archive)).fetchone():
                    return self.page("Original-Archiv wird bereits durch ein anderes Profil genutzt",409)
                if datev:
                    try:
                        ensure_datev_samba_protection(out)
                        if archive:ensure_datev_samba_protection(archive)
                    except ValueError as exc:return self.page("DATEV-Schutz: "+html.escape(str(exc)),409)
                try:c.execute("INSERT INTO profiles(name,input_share,output_share,qr_split,remove_separators,remove_blank,crop,ocr,datev_mode,archive_share) VALUES (?,?,?,?,?,?,?,?,?,?)",(name,inp,out,*values,datev,archive))
                except sqlite3.IntegrityError:return self.page("Profilname schon vorhanden",409)
            elif self.path=="/profile-update":
                try:
                    ident=int(get("id"))
                    values=check(data,shares())
                    if values[13] and not values[3]:
                        raise ValueError("DATEV-Modus erfordert QR-Trennung; QR-Trennblätter dürfen erhalten bleiben")
                    if c.execute("SELECT 1 FROM profiles WHERE id<>? AND output_share=? AND (datev_mode=1 OR ?=1) LIMIT 1",(ident,values[2],values[13])).fetchone():
                        raise ValueError("DATEV-Ausgang muss exklusiv sein")
                    archive=values[14]
                    if archive and c.execute("SELECT 1 FROM profiles WHERE id<>? AND (input_share=? OR output_share=? OR archive_share=?) LIMIT 1",(ident,archive,archive,archive)).fetchone():
                        raise ValueError("Original-Archiv-Freigabe wird bereits verwendet")
                    if c.execute("SELECT 1 FROM profiles WHERE id<>? AND archive_share IN (?,?) LIMIT 1",(ident,values[1],values[2])).fetchone():
                        raise ValueError("Eingang/Ausgang wird bereits als Archiv genutzt")
                    if values[13]:
                        ensure_datev_samba_protection(values[2])
                        if archive:ensure_datev_samba_protection(archive)
                    c.execute("UPDATE profiles SET name=?,input_share=?,output_share=?,qr_split=?,remove_separators=?,remove_blank=?,crop=?,ocr=?,blank_threshold=?,ocr_languages=?,ocr_output=?,ocr_rotate=?,ocr_deskew=?,datev_mode=?,archive_share=? WHERE id=?",(*values,ident))
                except (ValueError,sqlite3.IntegrityError) as exc:
                    return self.page("Profil ungültig: "+html.escape(str(exc)),400)
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

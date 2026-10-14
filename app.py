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
from urllib.parse import parse_qs,urlsplit,quote
from jobs_ui import dashboard,request_retry,file_flags,save_retention
from profile_settings import migrate,check,controls,SELECT
import company_admin
import company_processing
import review_queue
import review_pdf
import duplicate_review
import notifications
import company_web_access

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
    company_admin.migrate(c)
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
        self.send_header("Content-Security-Policy","default-src 'none'; style-src 'unsafe-inline'; form-action 'self'; script-src 'self'")
        if unauthorized:self.send_header("WWW-Authenticate",'Basic realm="QR Scan Manager"')
        self.end_headers();self.wfile.write(payload)
    def actor(self):
        if valid_auth(self.headers.get("Authorization","")):return ("admin",None)
        with db() as c:return company_web_access.authenticate(c,self.headers.get("Authorization",""))
    def guard(self):
        actor=self.actor()
        route=urlsplit(self.path).path
        if actor and (actor[0]=="admin" or (self.command=="GET" and route in ("/review","/datev-review","/review-pdf"))):
            return True
        self.page("<h1>Keine Berechtigung</h1>" if actor else "<h1>Anmeldung erforderlich</h1>",403 if actor else 401,not bool(actor))
        return False
    def password_needed(self):
        return bool(json.loads(AUTH.read_text()).get("must_change"))
    def password_form(self,msg=""):
        self.page("<h1>Administratorpasswort ändern</h1><p>"+html.escape(msg)+"</p><section><form method='post' action='/password'><label>Neues Passwort (mindestens 12 Zeichen)</label><input type='password' name='password' minlength='12' required><label>Wiederholen</label><input type='password' name='confirm' minlength='12' required><button>Passwort ändern</button></form></section>")
    def do_GET(self):
        if not self.guard():return
        route=urlsplit(self.path)
        if route.path=="/company-ui.js":
            payload=b'document.querySelectorAll("select[data-auto-submit=belegart]").forEach(s=>s.addEventListener("change",()=>s.form.requestSubmit()));'
            self.send_response(200)
            self.send_header("Content-Type","application/javascript; charset=utf-8")
            self.send_header("Content-Length",str(len(payload)))
            self.end_headers()
            self.wfile.write(payload)
            return
        if route.path=="/duplicate-review":
            if self.password_needed():return self.password_form()
            signature=parse_qs(route.query).get("signature",[""])[0]
            if len(signature)!=64 or any(ch not in "0123456789abcdef" for ch in signature):
                return self.page("Ungültige Prüfkennung",400)
            registry=DATA/"datev.sqlite3"
            try:
                with db() as c:
                    job=c.execute("""SELECT j.file FROM jobs j JOIN company_profile_links l ON l.profile_id=j.profile_id
                        WHERE j.signature=?""",(signature,)).fetchone()
                    if not job:raise ValueError("Prüfauftrag nicht vorhanden")
                with sqlite3.connect("file:"+str(registry)+"?mode=ro",uri=True) as con:
                    rows=duplicate_review.cases(con,job[0])
                esc=lambda v:html.escape(str(v),quote=True)
                page="<header><h1>Dublettenprüfung</h1><a href='/review'>Zur Prüfwarteschlange</a></header><section><p>Quelle: "+esc(Path(job[0]).name)+"</p>"
                if not rows:page+="<p>Kein zugeordneter Dublettenverdacht im DATEV-Register gefunden.</p>"
                for digest,matched,path,choice,note,filename in rows:
                    page+="<article><h3>Verdächtiger Einzelbeleg</h3><p>Signatur: "+esc(digest)+"</p><p>Vergleich mit: "+esc(filename or matched)+"</p>"
                    page+="<p>Entscheidung: "+esc(choice or "Noch offen")+"</p><p>Begründung: "+esc(note)+"</p>"
                    page+="<p><a href='/duplicate-pdf?digest="+esc(digest)+"'>Verdächtigen Beleg ansehen</a></p>"
                    page+="<form method='post' action='/duplicate-decision'><input type='hidden' name='signature' value='"+esc(signature)+"'><input type='hidden' name='digest' value='"+esc(digest)+"'>"
                    page+="<label>Entscheidung</label><select name='decision'><option value='confirmed'>Als Dublette bestätigen</option><option value='independent'>Kein Duplikat – weiterer Prüfbedarf vor Übergabe</option></select><label>Begründung</label><textarea name='note' maxlength='1000' required></textarea><button>Entscheidung protokollieren</button></form></article><hr>"
                return self.page(page+"</section>")
            except (ValueError,sqlite3.Error,OSError) as exc:
                return self.page("<h1>Dublettenprüfung nicht verfügbar</h1><p>"+html.escape(str(exc))+"</p>",400)
        if route.path=="/duplicate-pdf":
            if self.password_needed():return self.password_form()
            digest=parse_qs(route.query).get("digest",[""])[0]
            try:
                with sqlite3.connect("file:"+str(DATA/"datev.sqlite3")+"?mode=ro",uri=True) as con:
                    path=duplicate_review.inspected_pdf(con,digest,"suspect",DATA/"datev-review",ROOT)
                size=path.stat().st_size
                if size>100*1024*1024:raise ValueError("Datei zu groß")
                self.send_response(200)
                self.send_header("Content-Type","application/pdf")
                self.send_header("Content-Disposition","inline; filename=duplicate-"+digest[:12]+".pdf")
                self.send_header("X-Content-Type-Options","nosniff")
                self.send_header("Content-Length",str(size))
                self.send_header("Cache-Control","no-store")
                self.end_headers()
                with path.open("rb") as stream:
                    while True:
                        chunk=stream.read(65536)
                        if not chunk:break
                        self.wfile.write(chunk)
                return
            except (ValueError,FileNotFoundError,OSError,sqlite3.Error) as exc:
                return self.page("<h1>Beleg nicht verfügbar</h1><p>"+html.escape(str(exc))+"</p>",404)
        if route.path in ("/review-pdf","/review-draft"):
            if self.password_needed():return self.password_form()
            token=parse_qs(route.query).get("signature",[""])[0]
            try:
                with db() as c:
                    actor=self.actor()
                    if actor[0]!="admin" and not company_web_access.owns_job(c,token,actor[1]):raise ValueError("Keine Berechtigung")
                    if route.path=="/review-pdf":
                        path=review_pdf.source_for_case(c,token,ROOT,DATA/"original-archive")
                    else:
                        review_pdf.source_for_case(c,token,ROOT,DATA/"original-archive")
                        path=DATA/"review-drafts"/(token+".pdf")
                        if not path.is_file() or path.is_symlink():raise FileNotFoundError("Noch kein korrigierter Entwurf")
                size=path.stat().st_size
                if size>100*1024*1024:raise ValueError("PDF größer als Vorschau-Limit")
                self.send_response(200)
                self.send_header("Content-Type","application/pdf")
                self.send_header("Content-Disposition",("inline" if route.path=="/review-pdf" else "attachment")+"; filename=review-"+token[:12]+".pdf")
                self.send_header("X-Content-Type-Options","nosniff")
                self.send_header("Content-Length",str(size))
                self.send_header("Cache-Control","no-store")
                self.end_headers()
                with path.open("rb") as stream:
                    while True:
                        chunk=stream.read(65536)
                        if not chunk:break
                        self.wfile.write(chunk)
                return
            except (ValueError,FileNotFoundError,OSError) as exc:
                return self.page("<h1>PDF nicht verfügbar</h1><p>"+html.escape(str(exc))+"</p><a href='/review'>Zurück</a>",404)
        if route.path not in ("/","/jobs","/datev-review","/companies","/review","/duplicate-review","/duplicate-pdf","/notifications"):return self.page("Nicht gefunden",404)
        if self.password_needed():return self.password_form()
        if route.path=="/notifications":
            if self.password_needed():return self.password_form()
            with db() as c:cfg=notifications.config(c)
            esc=lambda v:html.escape(str(v),quote=True)
            out="<header><h1>E-Mail-Benachrichtigungen</h1><a href='/review'>PDF-Prüfwarteschlange</a></header><section><h2>SMTP-Einstellungen</h2>"
            out+="<p class='small'>Warnungen werden an die zugeordneten Firmenbenutzer mit hinterlegter E-Mail-Adresse versendet. Ohne Aktivierung kein E-Mail-Versand.</p>"
            out+="<form method='post' action='/notifications-save'>"
            for key,title,value in (("host","SMTP-Server",cfg["host"]),("port","Port",cfg["port"]),("username","SMTP-Benutzername",cfg["username"]),("sender","Absenderadresse",cfg["sender"])):
                out+="<label>"+title+"</label><input name='"+key+"' value='"+esc(value)+"' required"+(" type='number' min='1' max='65535'" if key=="port" else "")+">"
            out+="<label>SMTP-Passwort (leer lassen = unverändert)</label><input type='password' name='secret' autocomplete='new-password'>"
            out+="<label>Transportverschlüsselung</label><select name='mode'>"
            for key,label in (("starttls","STARTTLS, typischerweise Port 587"),("ssl","SSL/TLS, typischerweise Port 465")):
                out+="<option value='"+key+"'"+(" selected" if cfg["mode"]==key else "")+">"+label+"</option>"
            out+="</select><label><input type='checkbox' name='enabled'"+(" checked" if cfg["enabled"] else "")+"> Benachrichtigungen aktivieren</label>"
            out+="<button>Einstellungen speichern</button></form></section>"
            return self.page(out)
        if route.path=="/review":
            params=parse_qs(route.query)
            company=params.get("company",[""])[0]
            doctype=params.get("type",[""])[0]
            state=params.get("state",["active"])[0]
            if state not in ("active",*review_queue.STATES):state="active"
            with db() as c:
                actor=self.actor()
                permitted=actor[1] if actor[0]!="admin" else None
                firms=[r for r in c.execute("SELECT id,code FROM companies ORDER BY code") if permitted is None or r[0] in permitted]
                types=company_admin.TYPES
                if permitted is not None and company and (not company.isdigit() or int(company) not in permitted):return self.page("Keine Berechtigung",403)
                try:items=review_queue.records(c,company,doctype,state,allowed_companies=permitted)
                except ValueError:return self.page("Ungültige Filter",400)
            esc=lambda v:html.escape(str(v),quote=True)
            page="<header><h1>PDF-Prüfwarteschlange</h1><a href='/companies'>Firmenverwaltung</a></header>"
            page+="<section><form method='get' action='/review'><label>Firma</label><select name='company'><option value=''>Alle Firmen</option>"
            for cid,code in firms:
                page+="<option value='"+str(cid)+"'"+(" selected" if company==str(cid) else "")+">"+esc(code)+"</option>"
            page+="</select><label>Belegart</label><select name='type'><option value=''>Alle Belegarten</option>"
            for typ in types:
                page+="<option value='"+esc(typ)+"'"+(" selected" if doctype==typ else "")+">"+esc(typ)+"</option>"
            page+="</select><label>Prüfstatus</label><select name='state'>"
            for key,title in (("active","Offen und in Bearbeitung"),("open","Offen"),("in_progress","In Bearbeitung"),("resolved","Als erledigt markiert"),("dismissed","Verworfen")):
                page+="<option value='"+key+"'"+(" selected" if state==key else "")+">"+title+"</option>"
            page+="</select><button>Filtern</button></form></section>"
            page+="<section><h2>Prüffälle ("+str(len(items))+")</h2><p class='small'>Die Einstufung ändert keine PDF-Datei und löst keine DATEV-Übertragung aus. Eine Erledigt-Markierung bestätigt keine erfolgreiche DATEV-Übertragung.</p>"
            for item in items:
                page+="<article><h3>"+esc(item["filename"])+"</h3><p>"+esc(item["company"])+" · "+esc(item["doctype"])+" · "+esc(item["severity"])+" · "+esc(item["category"])+"</p>"
                page+="<p>"+esc(item["message"])+"</p><p class='small'>"+esc(item["updated"])+" · Status: "+esc(item["state"])+"</p>"
                page+="<p><a href='/review-pdf?signature="+esc(item["signature"])+"' target='_blank' rel='noopener'>Original-PDF ansehen</a></p>"
                if self.actor()[0]!="admin":
                    page+="</article><hr>"
                    continue
                page+="<p><a href='/review-draft?signature="+esc(item["signature"])+"'>Korrekturentwurf herunterladen</a></p>"
                if item["category"]=="duplicate":
                    page+="<p><a href='/duplicate-review?signature="+esc(item["signature"])+"'>Dublettenvergleich und Entscheidung</a></p>"
                if self.actor()[0]=="admin":
                    page+="<form method='post' action='/review-draft-create'><input type='hidden' name='signature' value='"+esc(item["signature"])+"'><label>Seiten übernehmen (z. B. 1,3,4; leer = alle)</label><input name='pages' maxlength='512' placeholder='Alle Seiten'><label>Seiten drehen</label><select name='rotation'><option value='0'>Nicht drehen</option><option value='90'>90 Grad</option><option value='180'>180 Grad</option><option value='270'>270 Grad</option></select><button>Korrekturentwurf erstellen</button></form>"

                if self.actor()[0]=="admin":
                    page+="<form method='post' action='/review-update'><input type='hidden' name='signature' value='"+esc(item["signature"])+"'><label>Prüfstatus</label><select name='state'>"
                for key,title in (("open","Offen"),("in_progress","In Bearbeitung"),("resolved","Erledigt"),("dismissed","Verworfen")):
                    page+="<option value='"+key+"'"+(" selected" if item["state"]==key else "")+">"+title+"</option>"
                page+="</select><label>Prüfnotiz</label><textarea name='note' maxlength='1000' rows='3'>"+esc(item["note"])+"</textarea><button>Prüfstatus speichern</button></form></article><hr>"
            page+="</section>"
            return self.page(page)
        if route.path=="/companies":
            params=parse_qs(route.query)
            try:cid=int(params.get("company_id",["0"])[0])
            except ValueError:cid=None
            typ=params.get("doc_type",[""])[0]
            with db() as c:
                content=company_admin.render(c,cid,typ,samba_call({"action":"list"}))
                qr=c.execute("SELECT value FROM settings WHERE key='qr_text'").fetchone()[0]
                content="<section><h2>QR-Trenncode (für alle Firmen)</h2><p class='small'>Gemeinsamer QR-Trenncode für bestehende und neue Verarbeitungsprofile.</p><form method='post' action='/qr'><input name='qr' maxlength='256' value='"+html.escape(qr,quote=True)+"' required><button>QR-Code speichern</button></form></section>"+content
            return self.page("<header><h1>Firmenverwaltung</h1><a href='/'>Zur Konfiguration</a></header>"+content+"<script src='/company-ui.js' defer></script>")
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
            actor=self.actor()
            if actor[0]!="admin":
                with db() as c:
                    marks=",".join("?" for _ in actor[1])
                    allowed={r[0] for r in c.execute("SELECT j.file FROM jobs j JOIN company_profile_links l ON l.profile_id=j.profile_id WHERE l.company_id IN ("+marks+")",tuple(sorted(actor[1])))}
                entries=[entry for entry in entries if entry[1] in allowed]
            lines=[]
            for digest,source,match,path in entries:
                present=bool(path and Path(path).is_file())
                lines.append("<p><b>"+html.escape(digest[:16])+"</b> | Quelle: "+html.escape(source or "")+
                             " | Vergleich: "+("Geschützt" if actor[0]!="admin" else html.escape((match or "")[:16]))+
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
        with db() as c:
            profile_count=c.execute("SELECT COUNT(*) FROM profiles").fetchone()[0]
            legacy=c.execute("""SELECT COUNT(*) FROM profiles p LEFT JOIN company_profile_links l
                ON p.id=l.profile_id WHERE l.profile_id IS NULL""").fetchone()[0]
            firms=c.execute("SELECT COUNT(*) FROM companies").fetchone()[0]
        summary=("<header><h1>QR Scan Manager</h1><nav><a href='/companies'>Firmen & Benutzer</a> · "
                 "<a href='/jobs'>Aufträge & Fehler</a> · <a href='/review'>PDF-Prüffälle</a> · <a href='/notifications'>E-Mail-Warnungen</a> · <a href='/datev-review'>DATEV-Prüfbereich</a></nav></header>"
                 "<section><h2>Übersicht</h2><p>Firmen: "+str(firms)+" · Aktive Profildatensätze: "
                 +str(profile_count)+"</p><p>Die Verarbeitung wird unter "
                 "<a href='/companies'>Firmen & Benutzer</a> konfiguriert.</p></section>")
        if legacy:
            summary+=("<section><h2>Ältere Verarbeitungsprofile</h2><p class='notice'>"
                      +str(legacy)+" manuell angelegte Profile sind weiterhin in der Datenbank und "
                      "können noch von der Überwachung verarbeitet werden. Bitte erst nach Prüfung "
                      "der neuen Firmenprofile gezielt deaktivieren oder entfernen. "
                      "Dieses Update löscht sie nicht automatisch.</p></section>")
        self.page(summary)

    def do_POST(self):
        if not self.guard():return
        if self.path not in ("/password","/qr","/add","/delete","/retry","/smb-create","/smb-update","/smb-password","/smb-delete","/smb-protect-datev","/profile-update","/retention","/company-create","/company-types","/company-user-create","/company-user-register","/company-access","/company-provision","/company-users-save","/company-delete","/company-user-delete","/company-processing","/review-update","/review-draft-create","/duplicate-decision","/notifications-save","/company-user-email","/company-web-password"):return self.page("Nicht gefunden",404)
        origin=self.headers.get("Origin")
        if origin and origin != "http://"+self.headers.get("Host",""):return self.page("Ungültiger Ursprung",403)
        try:
            length=int(self.headers.get("Content-Length","0"))
            if length>8192 or length<1:raise ValueError()
            data=parse_qs(self.rfile.read(length).decode(),keep_blank_values=True)
            get=lambda k:data.get(k,[""])[0]
        except (ValueError,UnicodeDecodeError):return self.page("Ungültige Eingabe",400)
        if self.path=="/review-draft-create":
            if self.password_needed():return self.password_form()
            try:
                with db() as c:
                    draft=review_pdf.prepare_draft(c,get("signature"),DATA/"review-drafts",ROOT,DATA/"original-archive",get("pages"),int(get("rotation")))
                    review_queue.set_case(c,get("signature"),"in_progress","Korrekturentwurf erstellt; noch nicht an DATEV übergeben")
                    c.commit()
            except (ValueError,OSError,sqlite3.Error) as exc:
                return self.page("<h1>Korrektur fehlgeschlagen</h1><p>"+html.escape(str(exc))+"</p><a href='/review'>Zurück</a>",400)
            self.send_response(303)
            self.send_header("Location","/review-draft?signature="+quote(get("signature")))
            self.end_headers()
            return
        if self.path=="/duplicate-decision":
            if self.password_needed():return self.password_form()
            try:
                signature=get("signature")
                with db() as c:
                    source=c.execute("""SELECT j.file FROM jobs j JOIN company_profile_links l ON l.profile_id=j.profile_id
                        WHERE j.signature=?""",(signature,)).fetchone()
                    if not source:raise ValueError("Prüfauftrag nicht vorhanden")
                registry=DATA/"datev.sqlite3"
                with sqlite3.connect(registry,timeout=10) as con:
                    rows=duplicate_review.cases(con,source[0])
                    if get("digest") not in {row[0] for row in rows}:raise ValueError("Dublette nicht diesem Auftrag zugeordnet")
                    duplicate_review.decision(con,get("digest"),get("decision"),get("note"))
                    con.commit()
            except (ValueError,OSError,sqlite3.Error) as exc:
                return self.page("<h1>Entscheidung nicht gespeichert</h1><p>"+html.escape(str(exc))+"</p>",400)
            self.send_response(303)
            self.send_header("Location","/duplicate-review?signature="+quote(signature))
            self.end_headers()
            return
        if self.path in ("/company-user-email","/company-web-password"):
            try:
                with db() as c:
                    if self.path=="/company-user-email":company_admin.save_email(c,get("username"),get("email"))
                    else:company_web_access.set_password(c,get("username"),get("password"))
                    c.commit()
            except (ValueError,sqlite3.Error) as exc:
                return self.page("<h1>Benutzerkonfiguration fehlgeschlagen</h1><p>"+html.escape(str(exc))+"</p>",400)
            self.send_response(303);self.send_header("Location","/companies");self.end_headers();return
        if self.path=="/notifications-save":
            if self.password_needed():return self.password_form()
            try:
                with db() as c:
                    current=notifications.config(c)
                    settings=dict(host=get("host").strip(),port=int(get("port")),username=get("username").strip(),
                        secret=get("secret") or current["secret"],sender=get("sender").strip(),
                        recipient=get("recipient").strip(),mode=get("mode"),enabled=int("enabled" in data))
                    notifications.save(c,settings)
                    c.commit()
            except (ValueError,sqlite3.Error) as exc:
                return self.page("<h1>SMTP-Konfiguration ungültig</h1><p>"+html.escape(str(exc))+"</p>",400)
            self.send_response(303);self.send_header("Location","/notifications");self.end_headers();return
        if self.path=="/review-update":
            if self.password_needed():return self.password_form()
            try:
                with db() as c:
                    review_queue.set_case(c,get("signature"),get("state"),get("note"))
                    c.commit()
            except (ValueError,sqlite3.Error) as exc:
                return self.page("<h1>Prüfwarteschlange: Fehler</h1><p>"+html.escape(str(exc))+"</p><a href='/review'>Zurück</a>",400)
            self.send_response(303);self.send_header("Location","/review");self.end_headers();return
        if self.path=="/password":
            if not self.password_needed():return self.page("Bereits eingerichtet",403)
            value=get("password")
            if value!=get("confirm") or len(value)<12 or len(value)>256:return self.password_form("Passwörter stimmen nicht überein oder sind zu kurz.")
            new=encode_password(value);new["must_change"]=False
            tmp=AUTH.with_suffix(".tmp");tmp.write_text(json.dumps(new));os.chmod(tmp,0o600);os.replace(tmp,AUTH)
            self.page("<h1>Passwort gespeichert</h1><p>Bitte Browseranmeldung neu durchführen.</p>");return
        if self.password_needed():return self.password_form()
        if self.path.startswith("/company-"):
            try:
                with db() as c:
                    if self.path=="/company-create":
                        company_admin.save_company(c,get("code"),get("display_name"),data.get("type",[]))
                    elif self.path=="/company-types":
                        ident=int(get("company_id"))
                        company=c.execute("SELECT code FROM companies WHERE id=?",(ident,)).fetchone()
                        if not company:raise ValueError("Firma existiert nicht")
                        selected=data.get("type",[])
                        if not selected or any(t not in company_admin.TYPES for t in selected):raise ValueError("Mindestens einen gültigen Belegtyp auswählen")
                        for typ in selected:
                            for fn in company_admin.FUNCTIONS:company_admin.share_name(company[0],typ,fn)
                        old={r[0] for r in c.execute("SELECT doc_type FROM company_types WHERE company_id=?",(ident,))}
                        removed=old-set(selected)
                        current={x["name"] for x in samba_call({"action":"list"}).get("shares",[])}
                        if any(company_admin.share_name(company[0],typ,fn) in current for typ in removed for fn in company_admin.FUNCTIONS):
                            raise ValueError("Belegart besitzt Samba-Freigaben; Entfernung blockiert")
                        c.execute("DELETE FROM company_types WHERE company_id=?",(ident,))
                        c.executemany("INSERT INTO company_types(company_id,doc_type) VALUES (?,?)",[(ident,t) for t in selected])
                    elif self.path=="/company-user-create":
                        user=get("username").strip()
                        company_admin.validate_email(get("email"))
                        if not company_admin.USER.fullmatch(user):raise ValueError("Ungültiger SMB-Benutzername")
                        if c.execute("SELECT 1 FROM smb_accounts WHERE username=?",(user,)).fetchone():raise ValueError("SMB-Benutzer existiert bereits")
                        response=samba_call({"action":"company-user-create","username":user,"password":get("password")})
                        if not response.get("ok"):raise ValueError(response.get("error","SMB-Benutzer konnte nicht angelegt werden"))
                        c.execute("INSERT INTO smb_accounts(username) VALUES (?)",(user,))
                        company_admin.save_email(c,user,get("email"))
                    elif self.path=="/company-user-register":
                        user=get("username").strip()
                        company_admin.validate_email(get("email"))
                        if not company_admin.USER.fullmatch(user):raise ValueError("Ungültiger SMB-Benutzername")
                        response=samba_call({"action":"company-user-register","username":user,"password":get("password")})
                        if not response.get("ok"):raise ValueError(response.get("error","SMB-Konto konnte nicht geprüft werden"))
                        c.execute("INSERT OR IGNORE INTO smb_accounts(username) VALUES (?)",(user,))
                        if get("email"):company_admin.save_email(c,user,get("email"))
                    elif self.path=="/company-access":
                        company_admin.change_access(c,int(get("company_id")),get("username"),get("role"))
                    elif self.path=="/company-users-save":
                        ident=int(get("company_id"))
                        chosen=data.get("username",[])
                        company_admin.save_user_selection(c,ident,chosen,get("role"))
                        # Apply revocations immediately on existing generated shares.
                        row=c.execute("SELECT code FROM companies WHERE id=?",(ident,)).fetchone()
                        existing={x["name"] for x in samba_call({"action":"list"}).get("shares",[])}
                        belonging=[company_admin.share_name(row[0],t[0],fn) for t in c.execute("SELECT doc_type FROM company_types WHERE company_id=?",(ident,)) for fn in company_admin.FUNCTIONS]
                        if any(name in existing for name in belonging):
                            if not chosen:raise ValueError("Bei bestehenden Firmenfreigaben muss mindestens ein Benutzer berechtigt bleiben")
                            reply=samba_call({"action":"company-sync-shares","specs":company_admin.share_specs(c,ident)})
                            if not reply.get("ok"):raise ValueError(reply.get("error","Samba-Zugriffsrechte konnten nicht synchronisiert werden"))
                    elif self.path=="/company-delete":
                        if get("confirm")!="yes":raise ValueError("Löschen muss ausdrücklich bestätigt werden")
                        ident=int(get("company_id"))
                        row=c.execute("SELECT code FROM companies WHERE id=?",(ident,)).fetchone()
                        if not row:raise ValueError("Firma existiert nicht")
                        prefix=row[0]+"-"
                        smb=samba_call({"action":"list"})
                        if not smb.get("ok"):raise ValueError("Samba-Freigaben konnten nicht geprüft werden")
                        if any(x["name"].lower().startswith(prefix.lower()) for x in smb.get("shares",[])):
                            raise ValueError("Firma besitzt noch Samba-Freigaben. Aus Sicherheitsgründen zuerst gesondert migrieren; keine Dateien werden gelöscht.")
                        if c.execute("SELECT 1 FROM profiles WHERE input_share LIKE ? OR output_share LIKE ? OR archive_share LIKE ? LIMIT 1",(prefix+"%",prefix+"%",prefix+"%")).fetchone():
                            raise ValueError("Firma wird noch in Verarbeitungsprofilen verwendet")
                        c.execute("DELETE FROM company_access WHERE company_id=?",(ident,))
                        c.execute("DELETE FROM company_types WHERE company_id=?",(ident,))
                        if c.execute("SELECT 1 FROM company_profile_links WHERE company_id=?",(ident,)).fetchone():
                            raise ValueError("Automatisch verwaltete Profile sind noch vorhanden")
                        c.execute("DELETE FROM company_processing WHERE company_id=?",(ident,))
                        c.execute("DELETE FROM companies WHERE id=?",(ident,))
                    elif self.path=="/company-user-delete":
                        if get("confirm")!="yes":raise ValueError("Löschen muss ausdrücklich bestätigt werden")
                        user=get("username")
                        if not company_admin.USER.fullmatch(user):raise ValueError("Ungültiger Benutzer")
                        if c.execute("SELECT 1 FROM company_access WHERE username=?",(user,)).fetchone():
                            raise ValueError("Benutzer ist noch Firmen zugewiesen. Erst alle Häkchen für diesen Benutzer entfernen.")
                        smb=samba_call({"action":"list"})
                        if not smb.get("ok"):raise ValueError("Samba-Freigaben konnten nicht geprüft werden")
                        if any(user in x.get("user","").split() for x in smb.get("shares",[])):
                            raise ValueError("Benutzer wird noch in Samba-Freigaben verwendet; Zugang bleibt zur Sicherheit erhalten")
                        c.execute("DELETE FROM smb_accounts WHERE username=?",(user,))
                    elif self.path=="/company-processing":
                        ident=int(get("company_id"))
                        typ=get("doc_type")
                        selected={k:k in data for k in (*company_processing.FLAGS,"ocr_rotate","ocr_deskew")}
                        try:
                            selected["blank_threshold"]=float(get("blank_threshold").replace(",","."))
                        except ValueError:
                            raise ValueError("Leerseiten-Schwellwert ungültig")
                        selected["ocr_languages"]=get("ocr_languages")
                        selected["ocr_output"]=get("ocr_output")
                        company_processing.save(c,ident,typ,selected)
                        linked=c.execute("SELECT 1 FROM company_profile_links WHERE company_id=?",(ident,)).fetchone()
                        if linked:
                            active=set(shares())
                            company_processing.sync_profiles(c,ident,active)
                    elif self.path=="/company-provision":
                        specs=company_admin.share_specs(c,int(get("company_id")))
                        response=samba_call({"action":"company-sync-shares","specs":specs})
                        if not response.get("ok"):raise ValueError(response.get("error","Samba-Freigaben konnten nicht angelegt werden"))
                        company_processing.sync_profiles(c,int(get("company_id")),set(shares()))
                    c.commit()
            except (ValueError,sqlite3.Error) as exc:
                return self.page("<h1>Firmenverwaltung: Fehler</h1><p>"+html.escape(str(exc))+"</p><a href='/companies'>Zurück</a>",400)
            redirect="/companies"
            if self.path=="/company-users-save":
                redirect+="?company_id="+quote(get("company_id"))+"&saved_users=1#firma-"+quote(get("company_id"))
            if self.path=="/company-processing":
                redirect+="?company_id="+quote(get("company_id"))+"&doc_type="+quote(get("doc_type"))+"#firma-"+quote(get("company_id"))
            self.send_response(303);self.send_header("Location",redirect);self.end_headers()
            return
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
                    if c.execute("SELECT 1 FROM company_profile_links WHERE profile_id=?",(ident,)).fetchone():
                        raise ValueError("Dieses Profil wird in der Firmenverwaltung gepflegt")
                    values=check(data,shares())
                    if "datev_mode" in data and "qr_split" not in data:
                        raise ValueError("DATEV-Modus benötigt QR-Code-Trennung. Übermittelt: qr_split=aus, datev_mode=an. Bitte QR-Trennung im selben Profilformular aktivieren.")
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
                if c.execute("SELECT 1 FROM company_profile_links WHERE profile_id=?",(ident,)).fetchone():
                    return self.page("Firmenprofil kann nur in der Firmenverwaltung geändert werden",409)
                c.execute("DELETE FROM profiles WHERE id=?",(ident,))
        self.send_response(303);self.send_header("Location","/companies" if self.path=="/qr" else "/");self.end_headers()

if __name__=="__main__":
    DATA.mkdir(parents=True,exist_ok=True)
    if not AUTH.exists():raise SystemExit("Auth-Datei fehlt. Installer ausführen.")
    with db():pass
    ThreadingHTTPServer((os.getenv("QRSCAN_BIND","127.0.0.1"),PORT),Handler).serve_forever()

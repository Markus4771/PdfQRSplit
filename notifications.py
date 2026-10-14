"""Opt-in SMTP notifications for firm-scoped PDF failures, no reprocessing."""
import json
import smtplib
import ssl
from email.message import EmailMessage
from pathlib import Path
from company_monitor import classify

def migrate(con):
    con.execute("""CREATE TABLE IF NOT EXISTS notification_settings(
        id INTEGER PRIMARY KEY CHECK(id=1),host TEXT NOT NULL DEFAULT '',
        port INTEGER NOT NULL DEFAULT 587, username TEXT NOT NULL DEFAULT '',
        secret TEXT NOT NULL DEFAULT '', sender TEXT NOT NULL DEFAULT '',
        recipient TEXT NOT NULL DEFAULT '', mode TEXT NOT NULL DEFAULT 'starttls',
        enabled INTEGER NOT NULL DEFAULT 0)""")
    con.execute("""CREATE TABLE IF NOT EXISTS notification_sent(
        signature TEXT NOT NULL, event TEXT NOT NULL,
        sent_at TEXT DEFAULT CURRENT_TIMESTAMP, PRIMARY KEY(signature,event))""")
def config(con):
    migrate(con)
    row=con.execute("SELECT host,port,username,secret,sender,recipient,mode,enabled FROM notification_settings WHERE id=1").fetchone()
    return dict(zip(("host","port","username","secret","sender","recipient","mode","enabled"),row)) if row else dict(host="",port=587,username="",secret="",sender="",recipient="",mode="starttls",enabled=0)
def validate(settings):
    if settings["mode"] not in ("starttls","ssl"):raise ValueError("Nur verschlüsselte SMTP-Verbindungen erlaubt")
    if not 1<=int(settings["port"])<=65535:raise ValueError("Ungültiger SMTP-Port")
    if not settings["host"] or any(x in settings["host"] for x in "\r\n /"):raise ValueError("Ungültiger SMTP-Server")
    for key in ("sender","recipient"):
        val=settings[key]
        if key=="recipient" and not val:continue
        if not val or "\r" in val or "\n" in val or "@" not in val or "," in val:
            raise ValueError("Ungültige E-Mail-Adresse: "+key)
    if settings["username"] and not settings["secret"]:raise ValueError("SMTP-Passwort fehlt")
def save(con,settings):
    validate(settings)
    migrate(con)
    con.execute("""INSERT INTO notification_settings
        (id,host,port,username,secret,sender,recipient,mode,enabled)
        VALUES (1,:host,:port,:username,:secret,:sender,:recipient,:mode,:enabled)
        ON CONFLICT(id) DO UPDATE SET host=excluded.host,port=excluded.port,
        username=excluded.username,secret=excluded.secret,sender=excluded.sender,
        recipient=excluded.recipient,mode=excluded.mode,enabled=excluded.enabled""",settings)
def send(settings,subject,body):
    validate(settings)
    mail=EmailMessage()
    mail["From"]=settings["sender"]
    mail["To"]=settings["recipient"]
    mail["Subject"]=subject
    mail.set_content(body)
    context=ssl.create_default_context()
    if settings["mode"]=="ssl":
        with smtplib.SMTP_SSL(settings["host"],int(settings["port"]),timeout=12,context=context) as smtp:
            if settings["username"]:smtp.login(settings["username"],settings["secret"])
            smtp.send_message(mail)
    else:
        with smtplib.SMTP(settings["host"],int(settings["port"]),timeout=12) as smtp:
            smtp.ehlo()
            smtp.starttls(context=context)
            smtp.ehlo()
            if settings["username"]:smtp.login(settings["username"],settings["secret"])
            smtp.send_message(mail)
def notify(con,signature,profile_id,status,details,filename):
    """Send once per critical event, after job commit; failed send stays retryable."""
    migrate(con)
    settings=config(con)
    if not settings["enabled"]:return False
    row=con.execute("""SELECT c.code,l.doc_type FROM company_profile_links l
          JOIN companies c ON c.id=l.company_id WHERE l.profile_id=?""",(profile_id,)).fetchone()
    if not row:return False
    category,severity,message=classify(status,details)
    if status not in ("error","interrupted") and severity!="Warnung":return False
    event=status if status in ("error","interrupted") else "warning"
    recipients=con.execute("""SELECT DISTINCT a.username,b.email FROM company_access a
        JOIN smb_accounts b ON b.username=a.username
        JOIN company_profile_links l ON l.company_id=a.company_id
        WHERE l.profile_id=? AND b.email<>'' ORDER BY b.email""",(profile_id,)).fetchall()
    if not recipients:return False
    subject="[PdfQRSplit] "+("FEHLER" if event!="warning" else "WARNUNG")+" – "+row[0]+" / "+row[1]
    body=("Firma: "+row[0]+"\\nBelegart: "+row[1]+"\\nPDF: "+Path(filename).name+
        "\\nStatus: "+status+"\\nKategorie: "+category+"\\nFehler: "+message[:1000]+
        "\\nAuftrag: "+signature+"\\nWeitere Informationen in der PDF-Prüfwarteschlange.\\n")
    any_sent=False
    for username,email in recipients:
        personal_event=event+":"+username
        if con.execute("SELECT 1 FROM notification_sent WHERE signature=? AND event=?",(signature,personal_event)).fetchone():
            continue
        recipient_settings=dict(settings,recipient=email)
        send(recipient_settings,subject,body)
        con.execute("INSERT OR IGNORE INTO notification_sent(signature,event) VALUES (?,?)",(signature,personal_event))
        con.commit()
        any_sent=True
    return any_sent

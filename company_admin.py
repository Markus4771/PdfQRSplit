"""Company, DATEV document types and per-company Samba access policy.

Never changes existing shares automatically; new shares must be provisioned explicitly.
"""
import html
import re
import company_processing

TYPES=("Rechnungseingang","Rechnungsausgang","Kasse","Sonstige","OhneBelegtyp")
ROLES=("none","read","input","write","admin")
FUNCTIONS=("Eingang","Archiv","Ausgang","LOG")
COMPANY=re.compile(r"^[A-Za-z0-9][A-Za-z0-9_-]{0,11}$")
USER=re.compile(r"^[A-Za-z][A-Za-z0-9_-]{2,30}$")

def migrate(con):
    con.execute("""CREATE TABLE IF NOT EXISTS companies(
       id INTEGER PRIMARY KEY, code TEXT NOT NULL UNIQUE COLLATE NOCASE,
       display_name TEXT NOT NULL, created_at TEXT DEFAULT CURRENT_TIMESTAMP)""")
    con.execute("""CREATE TABLE IF NOT EXISTS company_types(
       company_id INTEGER NOT NULL, doc_type TEXT NOT NULL,
       PRIMARY KEY(company_id,doc_type),
       FOREIGN KEY(company_id) REFERENCES companies(id))""")
    con.execute("""CREATE TABLE IF NOT EXISTS smb_accounts(
       username TEXT PRIMARY KEY, created_at TEXT DEFAULT CURRENT_TIMESTAMP)""")
    con.execute("""CREATE TABLE IF NOT EXISTS company_access(
       company_id INTEGER NOT NULL, username TEXT NOT NULL, role TEXT NOT NULL,
       PRIMARY KEY(company_id,username),
       FOREIGN KEY(company_id) REFERENCES companies(id))""")
    company_processing.migrate(con)
    con.commit()

def share_name(code,doc_type,function):
    if not COMPANY.fullmatch(code) or doc_type not in TYPES or function not in FUNCTIONS:
        raise ValueError("Ungültiger Name oder Belegtyp")
    name=f"{code}-{doc_type}-{function}"
    if len(name)>40:
        raise ValueError("Freigabename zu lang (max. 40 Zeichen)")
    return name

def save_company(con,code,display_name,selected):
    code=code.strip()
    display_name=display_name.strip()
    if not COMPANY.fullmatch(code) or not 1<=len(display_name)<=100:
        raise ValueError("Firmenkennung (max. 12 Zeichen) oder Firmenname ungültig")
    if not selected or any(x not in TYPES for x in selected):
        raise ValueError("Mindestens einen gültigen Belegtyp auswählen")
    for typ in selected:
        for fn in FUNCTIONS:
            share_name(code,typ,fn)
    con.execute("INSERT INTO companies(code,display_name) VALUES (?,?)",(code,display_name))
    company_id=con.execute("SELECT id FROM companies WHERE code=?",(code,)).fetchone()[0]
    con.executemany("INSERT INTO company_types(company_id,doc_type) VALUES (?,?)",[(company_id,x) for x in TYPES if x in selected])
    return company_id

def change_access(con,company_id,username,role):
    if not USER.fullmatch(username) or role not in ROLES:
        raise ValueError("Ungültiger Benutzer oder Berechtigung")
    if not con.execute("SELECT 1 FROM smb_accounts WHERE username=?",(username,)).fetchone():
        raise ValueError("Benutzer wurde noch nicht über die Firmenverwaltung angelegt")
    if not con.execute("SELECT 1 FROM companies WHERE id=?",(company_id,)).fetchone():
        raise ValueError("Firma existiert nicht")
    if role=="none":
        con.execute("DELETE FROM company_access WHERE company_id=? AND username=?",(company_id,username))
    else:
        con.execute("""INSERT INTO company_access(company_id,username,role) VALUES (?,?,?)
            ON CONFLICT(company_id,username) DO UPDATE SET role=excluded.role""",(company_id,username,role))

def share_specs(con,company_id):
    company=con.execute("SELECT code FROM companies WHERE id=?",(company_id,)).fetchone()
    if not company:raise ValueError("Firma fehlt")
    code=company[0]
    types=[r[0] for r in con.execute("SELECT doc_type FROM company_types WHERE company_id=?",(company_id,))]
    roles=[(u,r) for u,r in con.execute("SELECT username,role FROM company_access WHERE company_id=?",(company_id,))]
    if not roles:raise ValueError("Vor Freigabeanlage mindestens einen berechtigten SMB-Benutzer zuordnen")
    specs=[]
    for typ in types:
        for fn in FUNCTIONS:
            writers=[u for u,r in roles if fn=="Eingang" and r in ("input","write","admin")]
            readers=[u for u,r in roles if r in ("read","write","admin") or (r=="input" and fn=="Eingang")]
            specs.append({"name":share_name(code,typ,fn),"readers":readers,"writers":writers,"protected":fn in ("Archiv","Ausgang","LOG")})
    return specs

def render(con):
    esc=lambda s:html.escape(str(s),quote=True)
    rows=con.execute("SELECT id,code,display_name FROM companies ORDER BY code").fetchall()
    users=[x[0] for x in con.execute("SELECT username FROM smb_accounts ORDER BY username")]
    forms="<section id='firma-neu'><h2>Firmen & DATEV-Belegarten</h2><p class='small'>Neue Firmen werden zunächst ohne Samba-Freigaben angelegt. Nach Benutzerzuordnung können die Freigaben ausdrücklich erstellt werden.</p>"
    forms+="<form method='post' action='/company-create'><label>Firmenkennung / DATEV-Mandantennummer (max. 12 Zeichen)</label><input name='code' maxlength='12' required><label>Firmenname</label><input name='display_name' maxlength='100' required><h3>Belegarten</h3>"
    for i,t in enumerate(TYPES):
        forms+=f"<label><input type='checkbox' name='type' value='{t}'"+(" checked" if i<2 else "")+"> "+t+"</label>"
    forms+="<button>Firma anlegen</button></form></section>"
    forms+="<section><h2>SMB-Benutzer</h2><p class='small'>Konten werden separat von der GUI-Anmeldung verwaltet. Bestehende Konten werden nicht überschrieben.</p><form method='post' action='/company-user-create'><label>Neuer SMB-Benutzer</label><input name='username' required><label>Passwort (mindestens 12 Zeichen)</label><input type='password' name='password' minlength='12' required><button>Benutzer anlegen</button></form>"
    forms+="<form method='post' action='/company-user-register'><h3>Vorhandenen Samba-Benutzer übernehmen</h3><label>SMB-Benutzer</label><input name='username' required><label>Bestehendes SMB-Passwort zur Prüfung</label><input type='password' name='password' required><button>Vorhandenen Benutzer hinzufügen</button></form>"
    if users:
        forms+="<h3>Benutzer aus Verwaltung entfernen</h3><p class='small'>Nur möglich, wenn der Benutzer keiner Firma und keiner verwalteten Freigabe mehr zugeordnet ist. Das Linux-/Samba-Konto bleibt erhalten.</p>"
        for u in users:
            forms+="<form method='post' action='/company-user-delete'><input type='hidden' name='username' value='"+esc(u)+"'><label><input type='checkbox' name='confirm' value='yes' required> "+esc(u)+" aus der Firmenverwaltung entfernen</label><button>Benutzer entfernen</button></form>"
    forms+="<p>Verfügbare Benutzer: "+(esc(", ".join(users)) if users else "Noch keine")+"</p></section>"
    out="<section><h2>Vorhandene Firmen ("+str(len(rows))+")</h2>"
    if rows:
        out+="<p>Diese Firmen sind gespeichert. Firma anklicken, um Benutzerberechtigungen zu bearbeiten.</p>"
        for cid,code,title in rows:
            out+="<p><a href='#firma-"+str(cid)+"'><b>"+esc(code)+"</b> – "+esc(title)+"</a></p>"
    else:
        out+="<p>Noch keine Firmen vorhanden.</p>"
    out+="<p><a href='#firma-neu'>Neue Firma anlegen</a></p></section>"
    for cid,code,title in rows:
        types=[x[0] for x in con.execute("SELECT doc_type FROM company_types WHERE company_id=?",(cid,))]
        acl=con.execute("SELECT username,role FROM company_access WHERE company_id=? ORDER BY username",(cid,)).fetchall()
        out+=f"<section id='firma-{cid}'><h2>{esc(code)} – {esc(title)}</h2><p>Belegarten: {esc(', '.join(types))}</p>"
        out+="<form method='post' action='/company-types'><input type='hidden' name='company_id' value='"+str(cid)+"'><h3>Belegarten bearbeiten</h3>"
        for t in TYPES:
            out+="<label><input type='checkbox' name='type' value='"+t+"'"+(" checked" if t in types else "")+"> "+t+"</label>"
        out+="<button>Belegarten speichern</button></form>"
        out+=company_processing.render(con,cid,types,esc)
        out+="<h3>Benutzer der Firma zuweisen</h3><p class='small'>Mehrere Benutzer per Checkbox auswählen. Eine Berechtigungsstufe gilt für die neu ausgewählten Benutzer; vorhandene Rollen bleiben bei bereits zugewiesenen Benutzern erhalten.</p>"
        out+="<p>Aktuelle Zuordnung: "+(esc(", ".join(f"{u}: {r}" for u,r in acl)) if acl else "Keine Benutzer zugewiesen")+"</p>"
        out+="<form method='post' action='/company-users-save'><input type='hidden' name='company_id' value='"+str(cid)+"'>"
        for u in users:
            out+="<label><input type='checkbox' name='username' value='"+esc(u)+"'"+(" checked" if u in dict(acl) else "")+"> "+esc(u)+(" ("+esc(dict(acl)[u])+")" if u in dict(acl) else "")+"</label>"
        out+="<label>Berechtigung für neu zugewiesene Benutzer</label><select name='role'>"
        for role,caption in (("read","Nur lesen"),("input","Nur Eingang schreiben"),("write","Eingänge lesen/schreiben"),("admin","Administrator")):
            out+="<option value='"+role+"'>"+caption+"</option>"
        out+="</select><button>Benutzerzuordnung speichern</button></form>"
        out+="<form method='post' action='/company-delete'><input type='hidden' name='company_id' value='"+str(cid)+"'><label><input type='checkbox' name='confirm' value='yes' required> Firma endgültig aus der Verwaltung löschen (nur ohne Samba-Freigaben/Profile)</label><button>Firma löschen</button></form>"
        out+="<form method='post' action='/company-provision'><input type='hidden' name='company_id' value='"+str(cid)+"'><button>Fehlende Samba-Freigaben anlegen / Rechte synchronisieren</button></form>"
        out+="<p class='small'>Schema: "+esc(code)+"-Belegart-{Eingang,Archiv,Ausgang,LOG}. DATEV-Belegtransfer nur auf Ausgang konfigurieren. Bereits bestehende fremde Freigaben werden nicht übernommen.</p></section>"
    return out+forms

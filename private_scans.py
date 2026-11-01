"""Private scan profiles: multiple independent input/output mappings per SMB user.

No DATEV registry, no company linkage, and no automatic Samba permission changes.
"""
import html
import re

NAME=re.compile(r"^[A-Za-z][A-Za-z0-9_-]{0,39}$")

def migrate(con):
    con.execute("""CREATE TABLE IF NOT EXISTS private_scan_profiles (
       profile_id INTEGER PRIMARY KEY,
       username TEXT NOT NULL,
       label TEXT NOT NULL,
       FOREIGN KEY(profile_id) REFERENCES profiles(id),
       FOREIGN KEY(username) REFERENCES smb_accounts(username))""")
    con.execute("CREATE INDEX IF NOT EXISTS idx_private_scan_owner ON private_scan_profiles(username)")
    if "photo_mode" not in {row[1] for row in con.execute("PRAGMA table_info(private_scan_profiles)")}:
        con.execute("ALTER TABLE private_scan_profiles ADD COLUMN photo_mode INTEGER NOT NULL DEFAULT 0")

def create(con,username,label,input_share,output_share,available,qr_split=False,ocr=False,photo_mode=False):
    migrate(con)
    if any(type(v) is not bool for v in (qr_split,ocr,photo_mode)):raise ValueError("Ungültige Scanoptionen")
    if not isinstance(username,str) or not con.execute("SELECT 1 FROM smb_accounts WHERE username=?",(username,)).fetchone():
        raise ValueError("Privater SMB-Benutzer unbekannt")
    if not isinstance(label,str) or not 1<=len(label.strip())<=60:
        raise ValueError("Bezeichnung muss 1 bis 60 Zeichen besitzen")
    if not isinstance(input_share,str) or not isinstance(output_share,str) or input_share==output_share:
        raise ValueError("Eingang und Ausgang müssen verschieden sein")
    valid={s["name"]:s for s in available if isinstance(s,dict) and isinstance(s.get("name"),str)}
    if input_share not in valid or output_share not in valid:
        raise ValueError("Unbekannte Samba-Freigabe")
    # Existing ACLs remain authoritative; never provision shares or change Samba credentials here.
    for share in (input_share,output_share):
        members=valid[share].get("user","").split()
        if username not in members:
            raise ValueError("Benutzer hat keinen SMB-Zugriff auf "+share)
        if valid[share].get("datev_protected"):
            raise ValueError("DATEV-geschützte Freigabe nicht für Privatprofile verwenden")
    if not valid[input_share].get("writable"):
        raise ValueError("Eingangsfreigabe ist nicht schreibbar")
    if any(row[0] in (input_share,output_share) for row in con.execute(
        "SELECT archive_share FROM profiles WHERE datev_mode=1")):
        raise ValueError("Freigabe ist einem DATEV-Archiv zugeordnet")
    if con.execute("""SELECT 1 FROM profiles WHERE output_share=? AND datev_mode=1
             OR input_share=? AND datev_mode=1 LIMIT 1""",(output_share,output_share)).fetchone():
        raise ValueError("DATEV-Eingang/-Ausgang darf nicht privat verwendet werden")
    if con.execute("""SELECT 1 FROM profiles WHERE input_share=? AND output_share=? LIMIT 1""",(input_share,output_share)).fetchone():
        raise ValueError("Diese Eingangs-/Ausgangszuordnung existiert bereits")
    if not con.execute("SELECT 1 FROM profiles LIMIT 1").fetchone():
        next_id=1
    else:
        next_id=con.execute("SELECT COALESCE(MAX(id),0)+1 FROM profiles").fetchone()[0]
    name="privat_%d"%next_id
    if not NAME.fullmatch(name):raise ValueError("Zu viele Profile")
    cur=con.execute("""INSERT INTO profiles(name,input_share,output_share,qr_split,remove_separators,
      remove_blank,crop,ocr,blank_threshold,ocr_languages,ocr_output,ocr_rotate,ocr_deskew,datev_mode,archive_share)
      VALUES (?,?,?,?,?,?,?,?,?,?,?,?,?,?,?)""",
      (name,input_share,output_share,int(qr_split),0,int(not photo_mode),0,int(ocr and not photo_mode),0.5,"deu+eng","pdf",0,0,0,""))
    con.execute("INSERT INTO private_scan_profiles(profile_id,username,label,photo_mode) VALUES (?,?,?,?)",
                (cur.lastrowid,username,label.strip(),int(photo_mode)))
    return cur.lastrowid

def render(con,shares):
    migrate(con)
    esc=lambda v:html.escape(str(v),quote=True)
    users=[r[0] for r in con.execute("SELECT username FROM smb_accounts ORDER BY username")]
    profiles=con.execute("""SELECT x.username,x.label,p.input_share,p.output_share,p.id
        FROM private_scan_profiles x JOIN profiles p ON p.id=x.profile_id
        ORDER BY x.username,x.label""").fetchall()
    out="<header><h1>Private Scanaufträge</h1><a href='/private'>Privatübersicht</a></header>"
    out+="<section><h2>Private Benutzer und Scanprofile</h2><p>Mehrere Eingänge und Ausgänge je Benutzer sind möglich. Jeder Scanauftrag hat ein eigenes Eingangs-/Ausgangspaar.</p>"
    if profiles:
        out+="<table><tr><th>Benutzer</th><th>Profil</th><th>Eingang</th><th>Ausgang</th></tr>"
        for user,label,inp,dest,_ in profiles:
            out+="<tr><td>"+esc(user)+"</td><td>"+esc(label)+"</td><td>"+esc(inp)+"</td><td>"+esc(dest)+"</td></tr>"
        out+="</table>"
    out+="<p class='small'>Neue Profile verarbeiten PDFs ohne DATEV-Sicherheitsmodus; QR-Trennung standardmäßig aus, OCR und Leerseitenentfernung an. SMB-Konten und Freigaben zuerst über die bestehende Verwaltung anlegen.</p>"
    if not users or not shares:return out+"<p>Bitte zuerst Benutzer und Samba-Freigaben einrichten.</p></section>"
    out+="<form method='post' action='/private-create'><label>Privater Benutzer</label><select name='username'>"
    for user in users:out+="<option value='"+esc(user)+"'>"+esc(user)+"</option>"
    out+="</select><label>Profilbezeichnung</label><input name='label' maxlength='60' required>"
    for field,caption in (("input","Eingangsfreigabe"),("output","Ausgangsfreigabe")):
        out+="<label>"+caption+"</label><select name='"+field+"'>"
        for share in shares:
            name=share.get("name","")
            if name:out+="<option value='"+esc(name)+"'>"+esc(name)+"</option>"
        out+="</select>"
    out+="<label><input type=\'checkbox\' name=\'qr_split\'> QR-Code-Trennung aktivieren</label>"
    out+="<label><input type=\'checkbox\' name=\'ocr\'> Texterkennung (OCR) aktivieren</label>"
    out+="<label><input type=\'checkbox\' name=\'photo_mode\'> Fotos (JPEG/PNG) als PDF übernehmen; OCR bei Fotos deaktiviert</label>"
    return out+"<button>Privates Scanprofil anlegen</button></form></section>"

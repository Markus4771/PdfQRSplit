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

def update(con,profile_id,label,qr_split,ocr,photo_mode,remove_blank,remove_separators=False,crop=False,ocr_rotate=False,ocr_deskew=False,blank_threshold=0.5,ocr_languages='deu+eng',ocr_output='pdf'):
    migrate(con)
    row=con.execute("""SELECT p.id FROM profiles p JOIN private_scan_profiles x
       ON x.profile_id=p.id WHERE p.id=? AND p.datev_mode=0""",(profile_id,)).fetchone()
    if not row:raise ValueError("Privatprofil existiert nicht")
    if not 1<=len(label.strip())<=60:raise ValueError("Ungültige Bezeichnung")
    if type(blank_threshold) not in (int,float) or not 0<=blank_threshold<=2:raise ValueError("Ungültiger Leerseitenwert")
    if ocr_languages not in ("deu","eng","deu+eng") or ocr_output not in ("pdf","pdfa"):raise ValueError("Ungültige OCR-Einstellung")
    con.execute("UPDATE private_scan_profiles SET label=?,photo_mode=? WHERE profile_id=?",
                (label.strip(),int(photo_mode),profile_id))
    con.execute("""UPDATE profiles SET qr_split=?,ocr=?,remove_blank=?,remove_separators=?,crop=?,
        ocr_rotate=?,ocr_deskew=?,blank_threshold=?,ocr_languages=?,ocr_output=? WHERE id=?""",
        (int(qr_split),int(ocr),int(remove_blank),int(remove_separators),int(crop),int(ocr_rotate),int(ocr_deskew),blank_threshold,ocr_languages,ocr_output,profile_id))

def change_mapping(con,profile_id,username,input_share,output_share,available):
    migrate(con)
    row=con.execute("SELECT x.username FROM private_scan_profiles x JOIN profiles p ON p.id=x.profile_id WHERE p.id=? AND p.datev_mode=0",(profile_id,)).fetchone()
    if not row or username!=row[0]:raise ValueError("Privatprofil unbekannt")
    valid={item["name"]:item for item in available}
    if input_share==output_share or input_share not in valid or output_share not in valid:raise ValueError("Ungültige Freigaben")
    for name in (input_share,output_share):
        entry=valid[name]
        if username not in entry.get("user","").split() or entry.get("datev_protected"):
            raise ValueError("Freigabe nicht für Benutzer freigegeben")
    if not valid[input_share].get("writable"):raise ValueError("Eingang ist schreibgeschützt")
    others=con.execute("SELECT id,input_share,output_share,archive_share,datev_mode FROM profiles WHERE id<>?",(profile_id,)).fetchall()
    for _,src,dst,arc,datev in others:
        if src==input_share and dst==output_share:raise ValueError("Doppeltes Freigabepaar")
        if datev and ({input_share,output_share}&{src,dst,arc}):raise ValueError("Freigabe für DATEV reserviert")
    con.execute("UPDATE profiles SET input_share=?,output_share=? WHERE id=?",(input_share,output_share,profile_id))

def render(con,shares):
    migrate(con)
    esc=lambda v:html.escape(str(v),quote=True)
    users=[r[0] for r in con.execute("SELECT username FROM smb_accounts ORDER BY username")]
    profiles=con.execute("""SELECT x.username,x.label,p.input_share,p.output_share,p.id,p.qr_split,p.ocr,x.photo_mode,p.remove_blank,p.remove_separators,p.crop,p.ocr_rotate,p.ocr_deskew,p.blank_threshold,p.ocr_languages,p.ocr_output
        FROM private_scan_profiles x JOIN profiles p ON p.id=x.profile_id
        ORDER BY x.username,x.label""").fetchall()
    out="<header><h1>Private Scanaufträge</h1><a href='/private'>Privatübersicht</a></header>"
    out+="<section><h2>Private Benutzer und Scanprofile</h2><p>Mehrere Eingänge und Ausgänge je Benutzer sind möglich. Jeder Scanauftrag hat ein eigenes Eingangs-/Ausgangspaar.</p>"
    if profiles:
        out+="<table><tr><th>Benutzer</th><th>Profil</th><th>Eingang</th><th>Ausgang</th></tr>"
        for user,label,inp,dest,pid,qr,ocr,photo,blank,sep,crop,rot,deskew,threshold,lang,output in profiles:
            out+="<tr><td>"+esc(user)+"</td><td>"+esc(label)+"</td><td>"+esc(inp)+"</td><td>"+esc(dest)+"</td></tr>"
        out+="</table>"
        out+="<h3>Bestehende private Profile bearbeiten</h3>"
        for user,label,inp,dest,pid,qr,ocr,photo,blank,sep,crop,rot,deskew,threshold,lang,output in profiles:
            out+="<details><summary>"+esc(user)+" · "+esc(label)+"</summary>"
            out+="<p class='small'>Eingang: "+esc(inp)+" · Ausgang: "+esc(dest)+". Freigaben bleiben bei dieser Bearbeitung unverändert.</p>"
            out+="<form method='post' action='/private-update'><input type='hidden' name='id' value='"+str(pid)+"'>"
            out+="<label>Profilbezeichnung</label><input name='label' maxlength='60' value='"+esc(label)+"' required>"
            for key,title,on in (("qr_split","QR-Code-Trennung",qr),("ocr","OCR-Texterkennung",ocr),("photo_mode","JPEG/PNG unverändert kopieren",photo),("remove_blank","Leerseiten entfernen",blank),("remove_separators","QR-Trennblätter entfernen",sep),("crop","Ränder beschneiden",crop),("ocr_rotate","Seiten automatisch drehen",rot),("ocr_deskew","Schiefe Seiten begradigen",deskew)):
                out+="<label><input type='checkbox' name='"+key+"'"+(" checked" if on else "")+"> "+title+"</label>"
            out+="<label>Leerseiten-Schwelle (%)</label><input type='number' name='blank_threshold' min='0' max='2' step='0.05' value='"+esc(threshold)+"'>"
            for field,title,current,items in (("ocr_languages","OCR-Sprache",lang,(("deu","Deutsch"),("eng","Englisch"),("deu+eng","Deutsch + Englisch"))),("ocr_output","OCR-Ausgabe",output,(("pdf","PDF"),("pdfa","PDF/A")))):
                out+="<label>"+title+"</label><select name='"+field+"'>"
                for value,title2 in items:
                    out+="<option value='"+value+"'"+(" selected" if value==current else "")+">"+title2+"</option>"
                out+="</select>"
            out+="<button>Profil speichern</button></form>"
            out+="<form method='post' action='/private-mapping'><input type='hidden' name='id' value='"+str(pid)+"'>"
            out+="<input type='hidden' name='username' value='"+esc(user)+"'>"
            for field,title,current in (("input","SMB-Eingang",inp),("output","SMB-Ausgang",dest)):
                out+="<label>"+title+"</label><select name='"+field+"'>"
                for item in shares:
                    name=item.get("name","")
                    if user in item.get("user","").split() and not item.get("datev_protected"):
                        out+="<option value='"+esc(name)+"'"+(" selected" if name==current else "")+">"+esc(name)+"</option>"
                out+="</select>"
            out+="<button>Freigaben zuordnen</button></form></details>"
    out+="<p class='small'>Neue Profile verarbeiten PDFs ohne DATEV-Sicherheitsmodus; QR-Trennung standardmäßig aus, OCR und Leerseitenentfernung an. SMB-Konten und Freigaben zuerst über die bestehende Verwaltung anlegen.</p>"
    out+="<section><h3>Private SMB-Freigabe anlegen</h3><form method='post' action='/private-share-create'>"
    out+="<label>Freigabename</label><input name='share_name' required>"
    out+="<label>Benutzer</label><input name='smb_user' required>"
    out+="<label>SMB-Passwort</label><input type='password' name='smb_password' minlength='12' required>"
    out+="<label><input type='checkbox' name='writable' checked> Schreibzugriff</label>"
    out+="<button>Freigabe anlegen</button></form></section>"
    eligible=[item for item in shares if not item.get("company_managed") and not item.get("datev_protected")]
    if eligible:
        out+="<section><h3>Privates SMB-Passwort ändern</h3><form method='post' action='/private-smb-password'>"
        out+="<label>SMB-Freigabe</label><select name='share_name'>"
        for item in eligible:
            out+="<option value='"+esc(item["name"])+"'>"+esc(item["name"])+" ("+esc(item.get("user",""))+")</option>"
        out+="</select><label>Neues SMB-Passwort</label><input type='password' name='password' minlength='12' required>"
        out+="<button>Passwort ändern</button></form></section>"
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
    out+="<label><input type=\'checkbox\' name=\'photo_mode\'> Fotos (JPEG/PNG) im Originalformat übernehmen</label>"
    return out+"<button>Privates Scanprofil anlegen</button></form></section>"

"""Per-company defaults, per-document-type overrides, and explicit managed PDF profiles."""
import json

EXTRAS={"blank_threshold":0.5,"ocr_languages":"deu+eng","ocr_output":"pdf","ocr_rotate":False,"ocr_deskew":False}

FLAGS=("qr_split","remove_separators","remove_blank","crop","ocr","datev_mode")
DEFAULT={"qr_split":True,"remove_separators":False,"remove_blank":True,
         "crop":False,"ocr":True,"datev_mode":True,**EXTRAS}
NAMES={"qr_split":"QR-Code-Trennung","remove_separators":"QR-Trennblätter entfernen",
       "remove_blank":"Leerseiten entfernen","crop":"Ränder beschneiden",
       "ocr":"OCRmyPDF am Schluss","datev_mode":"DATEV-Sicherheitsmodus"}

def migrate(con):
    con.execute("""CREATE TABLE IF NOT EXISTS company_processing (
      company_id INTEGER NOT NULL,
      doc_type TEXT NOT NULL DEFAULT '',
      settings TEXT NOT NULL,
      PRIMARY KEY(company_id,doc_type))""")
    con.execute("""CREATE TABLE IF NOT EXISTS company_profile_links (
      company_id INTEGER NOT NULL,doc_type TEXT NOT NULL,
      profile_id INTEGER NOT NULL UNIQUE,
      PRIMARY KEY(company_id,doc_type))""")

def parse(value):
    settings=json.loads(value)
    if not isinstance(settings,dict):
        raise ValueError("Ungültige Verarbeitungseinstellungen")
    validate(settings,partial=True)
    return settings

def validate(settings,partial=False):
    allowed=set(DEFAULT)
    if not isinstance(settings,dict) or any(k not in allowed for k in settings):
        raise ValueError("Unbekannte Verarbeitungseinstellung")
    if not partial and set(settings)!=allowed:
        raise ValueError("Unvollständige Verarbeitungseinstellungen")
    for key in (*FLAGS,"ocr_rotate","ocr_deskew"):
        if key in settings and type(settings[key]) is not bool:
            raise ValueError("Checkbox-Einstellung ungültig: "+key)
    if "blank_threshold" in settings and (type(settings["blank_threshold"]) not in (int,float) or not 0<=settings["blank_threshold"]<=2):
        raise ValueError("Leerseiten-Schwellwert muss zwischen 0 und 2 Prozent liegen")
    if "ocr_languages" in settings and settings["ocr_languages"] not in ("deu","eng","deu+eng"):
        raise ValueError("Ungültige OCR-Sprache")
    if "ocr_output" in settings and settings["ocr_output"] not in ("pdf","pdfa"):
        raise ValueError("Ungültige OCR-Ausgabe")

def effective(con,cid,typ):
    row=con.execute("SELECT settings FROM company_processing WHERE company_id=? AND doc_type=''",(cid,)).fetchone()
    base=dict(DEFAULT)
    if row:base.update(parse(row[0]))
    if typ:
        row=con.execute("SELECT settings FROM company_processing WHERE company_id=? AND doc_type=?",(cid,typ)).fetchone()
        if row:base.update(parse(row[0]))
    return base

def save(con,cid,typ,settings):
    from company_admin import TYPES
    if typ and (typ not in TYPES or not con.execute("SELECT 1 FROM company_types WHERE company_id=? AND doc_type=?",(cid,typ)).fetchone()):
        raise ValueError("Belegart ist für diese Firma nicht aktiv")
    if not con.execute("SELECT 1 FROM companies WHERE id=?",(cid,)).fetchone():
        raise ValueError("Firma existiert nicht")
    validate(settings)
    if settings["datev_mode"] and not settings["qr_split"]:
        raise ValueError("DATEV-Sicherheitsmodus erfordert QR-Trennung")
    if typ=="": 
        payload=settings
    else:
        # Store only settings that differ from company defaults.
        base=effective(con,cid,"")
        payload={k:v for k,v in settings.items() if base[k]!=v}
    con.execute("""INSERT INTO company_processing(company_id,doc_type,settings)
      VALUES (?,?,?) ON CONFLICT(company_id,doc_type) DO UPDATE SET settings=excluded.settings""",
      (cid,typ,json.dumps(payload,sort_keys=True)))
    return payload

def profile_name(cid,typ):
    from company_admin import TYPES
    return "firma%d_%s"%(cid,("RE","RA","KA","SO","OB")[TYPES.index(typ)])

def sync_profiles(con,cid,existing_shares):
    from company_admin import share_name
    row=con.execute("SELECT code FROM companies WHERE id=?",(cid,)).fetchone()
    if not row:raise ValueError("Firma nicht vorhanden")
    types=[r[0] for r in con.execute("SELECT doc_type FROM company_types WHERE company_id=?",(cid,))]
    specs=[]
    for typ in types:
        inp=share_name(row[0],typ,"Eingang")
        out=share_name(row[0],typ,"Ausgang")
        arc=share_name(row[0],typ,"Archiv")
        if not {inp,out,arc}.issubset(existing_shares):
            raise ValueError("Erst alle Firmenfreigaben anlegen")
        opts=effective(con,cid,typ)
        if opts["datev_mode"] and not opts["qr_split"]:
            raise ValueError("DATEV-Schutz benötigt QR-Trennung")
        link=con.execute("SELECT profile_id FROM company_profile_links WHERE company_id=? AND doc_type=?",(cid,typ)).fetchone()
        values=(int(opts["qr_split"]),int(opts["remove_separators"]),int(opts["remove_blank"]),
                int(opts["crop"]),int(opts["ocr"]),float(opts["blank_threshold"]),opts["ocr_languages"],opts["ocr_output"],int(opts["ocr_rotate"]),int(opts["ocr_deskew"]),int(opts["datev_mode"]),arc if opts["datev_mode"] else "")
        if link:
            pid=link[0]
            if not con.execute("SELECT 1 FROM profiles WHERE id=?",(pid,)).fetchone():
                raise ValueError("Automatisch verwaltetes Profil fehlt; nicht neu anlegen")
            specs.append(("update",pid,inp,out,values))
        else:
            name=profile_name(cid,typ)
            if con.execute("SELECT 1 FROM profiles WHERE name=? OR input_share=? OR output_share=? LIMIT 1",(name,inp,out)).fetchone():
                raise ValueError("Profilkonflikt für "+typ+"; vorhandene Profile werden nicht überschrieben")
            specs.append(("insert",name,inp,out,values,typ))
    # SQLite transaction, no per-profile partial commit.
    for spec in specs:
        if spec[0]=="update":
            _,pid,inp,out,v=spec
            con.execute("""UPDATE profiles SET input_share=?,output_share=?,qr_split=?,remove_separators=?,
               remove_blank=?,crop=?,ocr=?,blank_threshold=?,ocr_languages=?,ocr_output=?,ocr_rotate=?,ocr_deskew=?,datev_mode=?,archive_share=? WHERE id=?""",(inp,out,*v,pid))
        else:
            _,name,inp,out,v,typ=spec
            cur=con.execute("""INSERT INTO profiles
                (name,input_share,output_share,qr_split,remove_separators,remove_blank,crop,ocr,blank_threshold,ocr_languages,ocr_output,ocr_rotate,ocr_deskew,datev_mode,archive_share)
                VALUES (?,?,?,?,?,?,?,?,?,?,?,?,?,?,?)""",(name,inp,out,*v))
            con.execute("INSERT INTO company_profile_links(company_id,doc_type,profile_id) VALUES (?,?,?)",(cid,typ,cur.lastrowid))
    return len(specs)

def render(con,cid,types,esc,selected_company=None,selected_type=""):
    out="<h3>PDF-Verarbeitung</h3><p class='small'>Belegart auswählen: Die Optionen werden automatisch geladen. Änderungen erst mit „Einstellungen speichern“ übernehmen.</p>"
    out+="<form method='get' action='/companies'><input type='hidden' name='company_id' value='"+str(cid)+"'><label>Belegart auswählen</label><select name='doc_type' data-auto-submit='belegart'>"
    for typ in ("",*types):
        title="Firmenstandard (alle Belegarten)" if not typ else typ
        active=selected_company==cid and selected_type==typ
        out+="<option value='"+esc(typ)+"'"+(" selected" if active else "")+">"+esc(title)+"</option>"
    out+="</select><noscript><button>Belegart anzeigen</button></noscript></form>"
    if selected_company!=cid:
        return out
    if selected_type not in ("",*types):
        return out+"<p class='notice'>Die gewählte Belegart ist nicht aktiv.</p>"
    settings=effective(con,cid,selected_type)
    out+="<form method='post' action='/company-processing'><input type='hidden' name='company_id' value='"+str(cid)+"'><input type='hidden' name='doc_type' value='"+esc(selected_type)+"'>"
    out+="<h4>"+esc(selected_type or "Firmenstandard")+"</h4>"
    for flag in FLAGS:
        out+="<label><input type='checkbox' name='"+flag+"'"+(" checked" if settings[flag] else "")+"> "+NAMES[flag]+"</label>"
    out+="<label>Leerseiten: maximaler Schwarzanteil (%)</label><input type='number' name='blank_threshold' min='0' max='2' step='0.05' value='"+esc(settings["blank_threshold"])+"' required>"
    out+="<label>OCR-Sprache</label><select name='ocr_languages'>"
    for code,label in (("deu","Deutsch"),("eng","Englisch"),("deu+eng","Deutsch + Englisch")):
        out+="<option value='"+code+"'"+(" selected" if settings["ocr_languages"]==code else "")+">"+label+"</option>"
    out+="</select><label>OCR-Ausgabe</label><select name='ocr_output'>"
    for code,label in (("pdf","PDF"),("pdfa","PDF/A")):
        out+="<option value='"+code+"'"+(" selected" if settings["ocr_output"]==code else "")+">"+label+"</option>"
    out+="</select>"
    for flag,label in (("ocr_rotate","Seiten automatisch drehen"),("ocr_deskew","Schiefe Seiten begradigen")):
        out+="<label><input type='checkbox' name='"+flag+"'"+(" checked" if settings[flag] else "")+"> "+label+"</label>"
    out+="<p class='small'>Original-Archiv: automatisch die passende Firmenfreigabe je Belegart bei DATEV-Modus.</p>"
    out+="<button>Einstellungen speichern</button></form>"
    return out

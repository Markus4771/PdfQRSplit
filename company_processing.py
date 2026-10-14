"""Per-company defaults, per-document-type overrides, and explicit managed PDF profiles."""
import json

FLAGS=("qr_split","remove_separators","remove_blank","crop","ocr","datev_mode")
DEFAULT={"qr_split":True,"remove_separators":False,"remove_blank":True,
         "crop":False,"ocr":True,"datev_mode":True}
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
    if not isinstance(settings,dict) or any(k not in FLAGS or type(v)!=bool for k,v in settings.items()):
        raise ValueError("Ungültige Verarbeitungseinstellungen")
    return settings

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
    if set(settings)!=set(FLAGS) or any(type(v)!=bool for v in settings.values()):
        raise ValueError("Ungültige Verarbeitungseinstellungen")
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
                int(opts["crop"]),int(opts["ocr"]),int(opts["datev_mode"]),arc if opts["datev_mode"] else "")
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
               remove_blank=?,crop=?,ocr=?,datev_mode=?,archive_share=? WHERE id=?""",(inp,out,*v,pid))
        else:
            _,name,inp,out,v,typ=spec
            cur=con.execute("""INSERT INTO profiles
                (name,input_share,output_share,qr_split,remove_separators,remove_blank,crop,ocr,datev_mode,archive_share)
                VALUES (?,?,?,?,?,?,?,?,?,?)""",(name,inp,out,*v))
            con.execute("INSERT INTO company_profile_links(company_id,doc_type,profile_id) VALUES (?,?,?)",(cid,typ,cur.lastrowid))
    return len(specs)

def render(con,cid,types,esc):
    out="<h3>PDF-Verarbeitung: Firmenstandard</h3><p class='small'>Änderungen je Belegart sind darunter separat möglich. Nach dem Speichern werden vorhandene automatisch verwaltete Profile aktualisiert.</p>"
    for typ in ("",*types):
        settings=effective(con,cid,typ)
        override=bool(typ)
        out+="<form method='post' action='/company-processing'><input type='hidden' name='company_id' value='"+str(cid)+"'><input type='hidden' name='doc_type' value='"+esc(typ)+"'>"
        if override:out+="<h4>"+esc(typ)+" (eigene Einstellungen)</h4>"
        for flag in FLAGS:
            out+="<label><input type='checkbox' name='"+flag+"'"+(" checked" if settings[flag] else "")+"> "+NAMES[flag]+"</label>"
        out+="<p class='small'>Original-Archiv: automatisch die gesonderte Firmenfreigabe für diese Belegart bei aktiviertem DATEV-Modus; sonst keine automatische Archivierung.</p>"
        out+="<button>"+("Belegart-Einstellungen speichern" if override else "Firmenstandard speichern")+"</button></form>"
    return out

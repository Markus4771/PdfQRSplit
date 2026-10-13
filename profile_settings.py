"""Profile schema migration, validation and HTML controls."""
import html
import sqlite3

EXTRA={"blank_threshold":"REAL NOT NULL DEFAULT 0.5","ocr_languages":"TEXT NOT NULL DEFAULT 'deu+eng'","ocr_output":"TEXT NOT NULL DEFAULT 'pdf'","ocr_rotate":"INTEGER NOT NULL DEFAULT 0","ocr_deskew":"INTEGER NOT NULL DEFAULT 0","datev_mode":"INTEGER NOT NULL DEFAULT 0","archive_share":"TEXT NOT NULL DEFAULT ''"}
SELECT="id,name,input_share,output_share,qr_split,remove_separators,remove_blank,crop,ocr,blank_threshold,ocr_languages,ocr_output,ocr_rotate,ocr_deskew,datev_mode,archive_share"
def migrate(db):
    existing={x[1] for x in db.execute("PRAGMA table_info(profiles)")}
    for col,kind in EXTRA.items():
        if col not in existing:db.execute(f"ALTER TABLE profiles ADD COLUMN {col} {kind}")
    db.commit()
def check(data,shares):
    name=data.get("name",[""])[0].strip()
    source=data.get("input",[""])[0]
    dest=data.get("output",[""])[0]
    import re
    if not re.fullmatch(r"[A-Za-z][A-Za-z0-9_-]{0,39}",name):raise ValueError("Ungültiger Profilname")
    if source not in shares or dest not in shares or source==dest:raise ValueError("Ungültige Freigaben")
    try:threshold=float(data.get("blank_threshold",["0.5"])[0])
    except ValueError:raise ValueError("Ungültiger Leerseiten-Schwellwert")
    if not 0<=threshold<=2:raise ValueError("Schwellwert muss zwischen 0 und 2 Prozent liegen")
    lang=data.get("ocr_languages",["deu+eng"])[0]
    output=data.get("ocr_output",["pdf"])[0]
    if lang not in ("deu","eng","deu+eng") or output not in ("pdf","pdfa"):
        raise ValueError("Ungültige OCR-Einstellungen")
    archive=data.get("archive_share",[""])[0]
    if archive and (archive not in shares or archive in (source,dest)):
        raise ValueError("Original-Archiv muss eine dritte Samba-Freigabe sein")
    if archive and "datev_mode" not in data:
        raise ValueError("Archiv-Auswahl nur im DATEV-Modus")
    flags=[int(k in data) for k in ("qr_split","remove_separators","remove_blank","crop","ocr")]
    return (name,source,dest,*flags,threshold,lang,output,int("ocr_rotate" in data),int("ocr_deskew" in data),int("datev_mode" in data),archive)
def controls(profile,shares,action):
    # profile is a tuple matching SELECT; new profiles use the defaults.
    p=profile or (None,"","","",1,0,0,0,0,0.5,"deu+eng","pdf",0,0,0,"")
    esc=lambda v:html.escape(str(v),quote=True)
    def dropdown(name,values,value):
        return "<select name='"+name+"'>"+"".join("<option value='"+esc(k)+"'"+(" selected" if k==value else "")+">"+esc(label)+"</option>" for k,label in values)+"</select>"
    def flag(name,title,enabled):
        return "<label><input type='checkbox' name='"+name+"'"+(" checked" if enabled else "")+"> "+title+"</label>"
    opts=[(v,v) for v in shares]
    fields="<label>Profilname</label><input name='name' maxlength='40' required value='"+esc(p[1])+"'>"
    fields+="<label>Eingang</label>"+dropdown("input",opts,p[2])+"<label>Ausgang</label>"+dropdown("output",opts,p[3])
    for key,title,index in (("qr_split","QR-Code-Trennung",4),("remove_separators","QR-Trennblätter entfernen",5),("remove_blank","Leerseiten entfernen",6),("crop","Ränder beschneiden",7),("ocr","OCR am Ende",8),("ocr_rotate","Seiten automatisch drehen",12),("ocr_deskew","Schiefe Seiten begradigen",13)):
        fields+=flag(key,title,p[index])
    fields+="<label>Original-Archiv (separate Samba-Freigabe)</label>"+dropdown("archive_share",[("","Internes Archiv (bisher)")]+opts,p[15])
    fields+=flag("datev_mode","DATEV-Sicherheitsmodus (exakte Dubletten blockieren; Ausgang exklusiv für DATEV)",p[14])
    fields+="<label>Leerseiten: maximaler Schwarzanteil (%)</label><input type='number' name='blank_threshold' min='0' max='2' step='0.05' value='"+esc(p[9])+"'>"
    fields+="<label>OCR-Sprache</label>"+dropdown("ocr_languages",[("deu","Deutsch"),("eng","Englisch"),("deu+eng","Deutsch + Englisch")],p[10])
    fields+="<label>OCR-Ausgabe</label>"+dropdown("ocr_output",[("pdf","PDF"),("pdfa","PDF/A")],p[11])
    return "<form method='post' action='"+action+"'>"+("<input type='hidden' name='id' value='"+str(p[0])+"'>" if p[0] is not None else "")+fields+"<button>Profil speichern</button></form>"

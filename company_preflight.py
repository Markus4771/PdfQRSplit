"""Read-only operational preflight for company, users and processing profiles.

Never changes a company, Samba share, profile or DATEV handoff.
"""
import html
from company_admin import FUNCTIONS, share_name
from company_processing import effective, profile_name

def inspect(con,share_data):
    rows=con.execute("SELECT id,code,display_name FROM companies ORDER BY code").fetchall()
    available={entry.get("name") for entry in share_data.get("shares",[]) if isinstance(entry,dict)} if share_data.get("ok") else None
    reports=[]
    for cid,code,name in rows:
        users=con.execute("""SELECT a.username,a.role,COALESCE(s.email,'') FROM company_access a
          JOIN smb_accounts s ON s.username=a.username WHERE a.company_id=? ORDER BY a.username""",(cid,)).fetchall()
        types=[x[0] for x in con.execute("SELECT doc_type FROM company_types WHERE company_id=? ORDER BY doc_type",(cid,))]
        findings=[]
        if not users:findings.append("Keine berechtigten Benutzer zugeordnet")
        if not types:findings.append("Keine Belegarten konfiguriert")
        if users and not any(email for _,_,email in users):
            findings.append("Kein Benutzer mit E-Mail-Adresse für Fehlermeldungen")
        summaries=[]
        for typ in types:
            opt=effective(con,cid,typ)
            issues=[]
            if opt["datev_mode"] and not opt["qr_split"]:
                issues.append("QR-Trennung für DATEV fehlt")
            if opt["crop"]:
                issues.append("Ränder-Beschneiden ist aktiviert: Ergebnis prüfen")
            if opt["remove_separators"] is False and opt["datev_mode"]:
                issues.append("QR-Trennblätter bleiben in DATEV-Belegen")
            link=con.execute("""SELECT p.name,p.input_share,p.output_share,p.datev_mode,p.qr_split
              FROM company_profile_links l LEFT JOIN profiles p ON p.id=l.profile_id
              WHERE l.company_id=? AND l.doc_type=?""",(cid,typ)).fetchone()
            if not link or link[0]!=profile_name(cid,typ):
                issues.append("Automatisches Verarbeitungsprofil fehlt oder ist abweichend")
            else:
                expected_in=share_name(code,typ,"Eingang")
                expected_out=share_name(code,typ,"Ausgang")
                if link[1]!=expected_in or link[2]!=expected_out:
                    issues.append("Profil-Eingang oder -Ausgang abweichend")
                if bool(link[3])!=opt["datev_mode"] or bool(link[4])!=opt["qr_split"]:
                    issues.append("Gespeichertes Profil weicht von den Verarbeitungseinstellungen ab")
            if available is None:
                issues.append("Samba-Verfügbarkeit nicht prüfbar")
            else:
                missing=[fn for fn in FUNCTIONS if share_name(code,typ,fn) not in available]
                if missing:issues.append("Fehlende Samba-Freigaben: "+", ".join(missing))
            summaries.append({"type":typ,"settings":opt,"issues":issues})
        reports.append({"id":cid,"code":code,"name":name,"users":users,"types":summaries,"findings":findings})
    return reports

def render(con,share_data):
    esc=lambda x:html.escape(str(x),quote=True)
    reports=inspect(con,share_data)
    firms=len(reports)
    users=con.execute("SELECT COUNT(*) FROM smb_accounts").fetchone()[0]
    issues=sum(len(r["findings"])+sum(len(t["issues"]) for t in r["types"]) for r in reports)
    output=("<section><h2>Systemübersicht und Konfigurationsprüfung</h2>"
            "<p class='small'>Nur lesende Prüfung. Kein Live-Test von Scanner, Samba-Zugriff, OCR oder DATEV-Übertragung.</p>"
            "<div style='display:flex;flex-wrap:wrap;gap:12px'>"
            "<article style='flex:1;min-width:140px'><h3>Firmen</h3><strong>"+str(firms)+"</strong></article>"
            "<article style='flex:1;min-width:140px'><h3>SMB-Benutzer</h3><strong>"+str(users)+"</strong></article>"
            "<article style='flex:1;min-width:140px'><h3>Prüfhinweise</h3><strong>"+str(issues)+"</strong></article></div>")
    for report in reports:
        output+="<details><summary><b>"+esc(report["code"])+" – "+esc(report["name"])+"</b> | "+str(len(report["users"]))+" Benutzer, "+str(len(report["types"]))+" Belegarten</summary>"
        output+="<p><a href='#firma-"+str(report["id"])+"'>Zur Firmenverwaltung</a></p>"
        output+="<h3>Benutzer und Rechte</h3><table><tr><th>Benutzer</th><th>Rolle</th><th>Fehler-E-Mail</th></tr>"
        for username,role,email in report["users"]:
            output+="<tr><td>"+esc(username)+"</td><td>"+esc(role)+"</td><td>"+("Hinterlegt" if email else "Fehlt")+"</td></tr>"
        output+="</table><h3>Verarbeitungsprofile</h3><table><tr><th>Belegart</th><th>QR</th><th>OCR</th><th>DATEV</th><th>Prüfhinweise</th></tr>"
        for item in report["types"]:
            opt=item["settings"]
            flag=lambda k:"An" if opt[k] else "Aus"
            output+="<tr><td>"+esc(item["type"])+"</td><td>"+flag("qr_split")+"</td><td>"+flag("ocr")+"</td><td>"+flag("datev_mode")+"</td><td>"+esc("; ".join(item["issues"]) or "Keine Konfigurationsabweichung erkannt")+"</td></tr>"
        output+="</table>"
        if report["findings"]:
            output+="<p class='notice'>"+esc("; ".join(report["findings"]))+"</p>"
        output+="</details>"
    return output+"</section>"

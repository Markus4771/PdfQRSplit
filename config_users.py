"""Read-only central overview of accounts and their scope."""
import html

def render(con,shares):
    esc=lambda v:html.escape(str(v),quote=True)
    rows=con.execute("""SELECT a.username,COALESCE(a.email,''),
        (SELECT COUNT(*) FROM company_access c WHERE c.username=a.username),
        (SELECT COUNT(*) FROM private_scan_profiles p WHERE p.username=a.username)
        FROM smb_accounts a ORDER BY a.username""").fetchall()
    body="<section><h2>Benutzerverwaltung</h2><p class='small'>Zentrale Übersicht: SMB-Konten, private Profile und Firmenzuordnungen. Firmenrechte werden nur in der Firmenverwaltung geändert.</p>"
    body+="<p>Administratorzugang: <strong>admin</strong> (separates Webpasswort)</p>"
    if rows:
        body+="<table><tr><th>Benutzer</th><th>E-Mail</th><th>Privatprofile</th><th>Firma und Rolle</th><th>SMB-Freigaben</th></tr>"
        for user,email,company,private in rows:
            mapped=", ".join(item.get("name","") for item in shares if user in item.get("user","").split())
            firms=con.execute("""SELECT co.display_name,co.code,ca.role
               FROM company_access ca JOIN companies co ON co.id=ca.company_id
               WHERE ca.username=? ORDER BY co.display_name""",(user,)).fetchall()
            names=", ".join(str(name)+" ("+str(code)+", "+str(role)+")" for name,code,role in firms)
            body+="<tr><td>"+esc(user)+"</td><td>"+esc(email)+"</td><td>"+str(private)+"</td><td>"+esc(names or "Keine Firma")+"</td><td>"+esc(mapped or "Keine Freigaben")+"</td></tr>"
        body+="</table>"
    else:
        body+="<p>Noch keine registrierten SMB-Konten.</p>"
    body+="<p><a href='/private'>Private Scanprofile und SMB-Freigaben verwalten</a> · <a href='/companies'>Firmenbenutzer und Rechte verwalten</a></p>"
    body+="<h3>Privatrollen</h3><p class='small'>Lesen: eigene Profile ansehen. Verwalten: eigene PDF-Optionen bearbeiten, keine SMB-Konten oder DATEV-Funktionen ändern.</p>"
    body+="<form method='post' action='/config-user-role'><label>Benutzer</label><select name='username'>"
    for user,*_ in rows:body+="<option value='"+esc(user)+"'>"+esc(user)+"</option>"
    body+="</select><label>Rolle</label><select name='role'><option value='read'>Lesen</option><option value='manage'>Eigene Profile verwalten</option></select>"
    body+="<button"+(" disabled" if not rows else "")+">Rolle speichern</button></form>"
    body+="<h3>Web-Anmeldedaten vergeben</h3>"
    body+="<p class='small'>Separates Webpasswort für Privat- und Firmenbenutzer, unabhängig vom SMB-Passwort. Mindestens 12 Zeichen.</p>"
    body+="<form method='post' action='/config-user-web-password'><label>Benutzer</label><select name='username'>"
    for user,*_ in rows:body+="<option value='"+esc(user)+"'>"+esc(user)+"</option>"
    body+="</select><label>Neues Webpasswort</label><input type='password' name='password' minlength='12' maxlength='256' required>"
    body+="<button"+(" disabled" if not rows else "")+">Web-Zugang setzen</button></form>"
    body+="<h3>E-Mail-Adresse eines Benutzers ändern</h3><form method='post' action='/config-user-email'>"
    body+="<label>Benutzer</label><select name='username'>"
    for user,*_ in rows:body+="<option value='"+esc(user)+"'>"+esc(user)+"</option>"
    body+="</select><label>E-Mail-Adresse</label><input type='email' name='email' maxlength='254'>"
    body+="<p class='small'>Leeres Feld entfernt die bisherige E-Mail-Adresse.</p>"
    body+="<button"+(" disabled" if not rows else "")+">E-Mail speichern</button></form></section>"
    return body

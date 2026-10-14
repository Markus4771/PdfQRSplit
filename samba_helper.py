#!/usr/bin/env python3
"""Narrow root-only Samba helper. Input JSON on stdin; no shell execution."""
import json, os, re, subprocess, sys, tempfile, pwd
from pathlib import Path
CONF=Path("/etc/samba/qrscan-shares.conf")
ROOT=Path("/srv/samba-shares")
NAME=re.compile(r"^[A-Za-z][A-Za-z0-9_-]{0,39}$")
USER=re.compile(r"^[A-Za-z][A-Za-z0-9_-]{2,30}$")
def fail(message):
    print(json.dumps({"ok":False,"error":message}));sys.exit(1)
def run(cmd,**kwargs):
    r=subprocess.run(cmd,text=True,capture_output=True,timeout=20,**kwargs)
    if r.returncode:fail("Systemaktion fehlgeschlagen: "+cmd[0]+": "+r.stderr[-200:])
    return r
def read():
    entries={};name=None
    for raw in CONF.read_text().splitlines() if CONF.exists() else []:
        s=raw.strip()
        if s.startswith("[") and s.endswith("]"):
            name=s[1:-1]
            if not NAME.fullmatch(name):fail("Ungültige verwaltete Konfiguration")
            entries[name]={}
        elif name and "=" in s:
            k,v=s.split("=",1);entries[name][k.strip()]=v.strip()
    return entries
def write(entries):
    parts=["# Verwaltet durch QR Scan Manager; nicht manuell bearbeiten"]
    for name,values in sorted(entries.items()):
        parts += ["",f"[{name}]"]+[f"    {k} = {v}" for k,v in values.items()]
    old=CONF.read_bytes() if CONF.exists() else None
    fd,tmp=tempfile.mkstemp(prefix=".qrscan-",dir="/etc/samba")
    try:
        with os.fdopen(fd,"w") as f:
            f.write("\n".join(parts)+"\n");f.flush();os.fsync(f.fileno())
        os.chmod(tmp,0o644);os.replace(tmp,CONF)
        r=subprocess.run(["testparm","-s"],capture_output=True,text=True,timeout=20)
        if r.returncode:
            if old is None:CONF.unlink(missing_ok=True)
            else:CONF.write_bytes(old)
            fail("Samba-Konfiguration ungültig: "+r.stderr[-200:])
        run(["systemctl","reload","smbd"])
    finally:
        if os.path.exists(tmp):os.unlink(tmp)
def verify_user(user,password):
    """Check the existing user's SMB password without exposing it in process args."""
    fd,authfile=tempfile.mkstemp(prefix=".qrscan-auth-")
    try:
        with os.fdopen(fd,"w") as cred:
            cred.write("username = "+user+"\npassword = "+password+"\n")
        os.chmod(authfile,0o600)
        result=subprocess.run(["smbclient","-L","localhost","-A",authfile,"-m","SMB3"],capture_output=True,text=True,timeout=20)
    finally:
        os.unlink(authfile)
    if result.returncode:fail("Passwort für vorhandenen SMB-Benutzer stimmt nicht")

def main():
    if os.geteuid()!=0:fail("Root erforderlich")
    try:request=json.loads(sys.stdin.read(16384))
    except (ValueError,TypeError):fail("Ungültiges JSON")
    action=request.get("action")
    entries=read()
    if action=="list":
        print(json.dumps({"ok":True,"shares":[{"name":n,"user":v.get("valid users",""),"writable":v.get("read only")=="no","datev_protected":(v.get("comment")=="QRSCAN-DATEV-READONLY" or (v.get("comment")=="QRSCAN-COMPANY-MANAGED" and v.get("read only")=="yes" and not v.get("write list")))} for n,v in sorted(entries.items())]}));return
    if action=="company-user-create":
        user=request.get("username","");password=request.get("password","")
        if not isinstance(user,str) or not USER.fullmatch(user) or not isinstance(password,str) or not 12<=len(password)<=256:
            fail("Ungültige SMB-Kontodaten")
        try:
            pwd.getpwnam(user)
            fail("Linux-Benutzer existiert bereits; Konto nicht verändert")
        except KeyError:pass
        run(["useradd","--system","--no-create-home","--shell","/usr/sbin/nologin",user])
        result=subprocess.run(["smbpasswd","-s","-a",user],input=password+"\\n"+password+"\\n",capture_output=True,text=True,timeout=20)
        if result.returncode:fail("SMB-Benutzer konnte nicht eingerichtet werden")
        print(json.dumps({"ok":True}));return
    if action=="company-user-register":
        user=request.get("username","");password=request.get("password","")
        if not isinstance(user,str) or not USER.fullmatch(user) or not isinstance(password,str) or not password:
            fail("Ungültige SMB-Benutzerdaten")
        if not any(user in v.get("valid users","").split() for v in entries.values()):
            fail("Benutzer gehört nicht zu einer verwalteten Samba-Freigabe")
        verify_user(user,password)
        print(json.dumps({"ok":True}));return
    if action=="company-sync-shares":
        # Changes only explicitly QR Scan Manager-generated shares with strict markers.
        specs=request.get("specs")
        if not isinstance(specs,list) or not 1<=len(specs)<=20:fail("Ungültige Freigabenliste")
        seen=set()
        for spec in specs:
            name=spec.get("name") if isinstance(spec,dict) else None
            readers=spec.get("readers") if isinstance(spec,dict) else None
            writers=spec.get("writers") if isinstance(spec,dict) else None
            if not isinstance(name,str) or not NAME.fullmatch(name) or name in seen:
                fail("Ungültiger oder doppelter Freigabename")
            seen.add(name)
            if not isinstance(readers,list) or not isinstance(writers,list) or not readers or len(readers)>32 or len(writers)>32:
                fail("Mindestens ein berechtigter Leser benötigt")
            if any(not isinstance(u,str) or not USER.fullmatch(u) for u in readers+writers) or any(u not in readers for u in writers):
                fail("Ungültige Benutzerberechtigungen")
            if bool(spec.get("protected")) and writers:fail("Geschützte Freigabe darf nicht beschreibbar sein")
            for u in readers:
                try:pwd.getpwnam(u)
                except KeyError:fail("Unbekannter SMB-Benutzer: "+u)
            if name in entries and entries[name].get("comment")!="QRSCAN-COMPANY-MANAGED":
                fail("Freigabename bereits vorhanden; wird nicht übernommen: "+name)
            path=ROOT/name
            if path.is_symlink() or (path.exists() and (not path.is_dir() or path.resolve().parent!=ROOT.resolve())):
                fail("Unsicherer Zielpfad: "+name)
            if name not in entries and path.exists():fail("Verzeichnis existiert ohne verwaltete Freigabe: "+name)
        for spec in specs:
            name=spec["name"];path=ROOT/name
            path.mkdir(mode=0o2770,parents=False,exist_ok=True)
            os.chown(path,pwd.getpwnam("qrscan").pw_uid,pwd.getpwnam("qrscan").pw_gid)
            os.chmod(path,0o2770)
            entries[name]={"path":str(path),"browseable":"yes","read only":"yes",
                "valid users":" ".join(sorted(set(spec["readers"]))),
                "force user":"qrscan","create mask":"0660","directory mask":"2770",
                "comment":"QRSCAN-COMPANY-MANAGED"}
            if spec["writers"]:entries[name]["write list"]=" ".join(sorted(set(spec["writers"])))
            if spec["protected"]:entries[name]["hide unreadable"]="yes"
        write(entries)
        print(json.dumps({"ok":True,"count":len(specs)}));return
    name=request.get("name","")
    if not isinstance(name,str) or not NAME.fullmatch(name):fail("Ungültiger Freigabename")
    if action in ("update","delete","password","protect-datev") and name in entries and entries[name].get("comment")=="QRSCAN-COMPANY-MANAGED":
        fail("Firmenfreigaben werden ausschließlich in der Firmenverwaltung verwaltet")
    if action=="create":
        user=request.get("user","");password=request.get("password","")
        if not isinstance(user,str) or not USER.fullmatch(user):fail("Ungültiger SMB-Benutzer")
        if not isinstance(password,str) or not 12<=len(password)<=256:fail("Passwort muss 12-256 Zeichen haben")
        if name in entries:fail("Freigabe bereits vorhanden")
        if any(n.lower()==name.lower() for n in entries):fail("Freigabename doppelt")
        if re.search(r"^\s*\["+re.escape(name)+r"\]\s*$",Path("/etc/samba/smb.conf").read_text(),re.I|re.M):
            fail("Freigabe in Samba bereits vorhanden")
        path=ROOT/name
        if path.exists() or path.is_symlink():fail("Zielordner bereits vorhanden")
        linked=[x for x in entries.values() if x.get("valid users")==user]
        if linked:
            verify_user(user,password)
        else:
            try:pwd.getpwnam(user);fail("Benutzer existiert außerhalb dieses Managers")
            except KeyError:pass
            run(["useradd","--system","--no-create-home","--shell","/usr/sbin/nologin",user])
            result=subprocess.run(["smbpasswd","-s","-a",user],input=password+"\n"+password+"\n",capture_output=True,text=True,timeout=20)
            if result.returncode:fail("SMB-Konto konnte nicht angelegt werden")
        path.mkdir(mode=0o2770,parents=False)
        os.chown(path,pwd.getpwnam("qrscan").pw_uid,pwd.getpwnam("qrscan").pw_gid)
        os.chmod(path,0o2770)
        datev=bool(request.get("datev_protected",False))
        entries[name]={"path":str(path),"browseable":"yes","read only":"yes" if datev else ("no" if request.get("writable",True) else "yes"),
                       "valid users":user,"force user":"qrscan","create mask":"0660","directory mask":"2770"}
        if datev:
            entries[name]["comment"]="QRSCAN-DATEV-READONLY"
            entries[name]["veto files"]="/qrscan-*/"
            entries[name]["hide unreadable"]="yes"
        write(entries)
    elif action=="update":
        if name not in entries:fail("Freigabe fehlt")
        new_user=request.get("user","")
        if new_user:
            password=request.get("password","")
            if not isinstance(new_user,str) or not USER.fullmatch(new_user):fail("Ungültiger SMB-Benutzer")
            if not isinstance(password,str) or not 12<=len(password)<=256:fail("Passwort muss 12-256 Zeichen haben")
            if new_user!=entries[name].get("valid users"):
                if not any(v.get("valid users")==new_user for v in entries.values()):
                    fail("Der neue SMB-Benutzer muss bereits in einer anderen verwalteten Freigabe existieren")
                verify_user(new_user,password)
                entries[name]["valid users"]=new_user
        if entries[name].get("comment")=="QRSCAN-DATEV-READONLY":
            entries[name]["read only"]="yes"
        else:
            entries[name]["read only"]="no" if request.get("writable",True) else "yes"
        write(entries)
    elif action=="protect-datev":
        if name not in entries:fail("Freigabe fehlt")
        values=entries[name]
        path=Path(values.get("path",""))
        if path.is_symlink() or not path.is_dir() or path.resolve().parent!=ROOT.resolve():
            fail("Ungültiger DATEV-Ausgang")
        values["read only"]="yes"
        values["comment"]="QRSCAN-DATEV-READONLY"
        values["veto files"]="/qrscan-*/"
        values["hide unreadable"]="yes"
        write(entries)
    elif action=="password":
        if name not in entries:fail("Freigabe fehlt")
        password=request.get("password","")
        if not isinstance(password,str) or not 12<=len(password)<=256:fail("Passwort muss 12-256 Zeichen haben")
        user=entries[name]["valid users"]
        run(["smbpasswd","-s",user],input=password+"\n"+password+"\n")
    elif action=="delete":
        if name not in entries:fail("Freigabe fehlt")
        entries.pop(name);write(entries)
        # Do not delete files, SMB/Linux users, or credentials.
    else:fail("Unbekannte Aktion")
    print(json.dumps({"ok":True}))
if __name__=="__main__":main()

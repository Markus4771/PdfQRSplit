"""Company-user web credentials and strictly scoped read access."""
import base64
import binascii
import hashlib
import hmac
import os

def migrate(con):
    con.execute("""CREATE TABLE IF NOT EXISTS user_web_credentials(
        username TEXT PRIMARY KEY,salt TEXT NOT NULL,digest TEXT NOT NULL)""")
    con.execute("CREATE TABLE IF NOT EXISTS private_web_roles(username TEXT PRIMARY KEY,role TEXT NOT NULL DEFAULT 'read')")

def set_password(con,username,password):
    migrate(con)
    if len(password)<12 or len(password)>256:raise ValueError("Web-Passwort muss 12 bis 256 Zeichen lang sein")
    if not con.execute("SELECT 1 FROM smb_accounts WHERE username=?",(username,)).fetchone():
        raise ValueError("Benutzer nicht gefunden")
    salt=os.urandom(16)
    digest=hashlib.pbkdf2_hmac("sha256",password.encode(),salt,600000)
    con.execute("""INSERT INTO user_web_credentials(username,salt,digest) VALUES (?,?,?)
         ON CONFLICT(username) DO UPDATE SET salt=excluded.salt,digest=excluded.digest""",
         (username,salt.hex(),digest.hex()))

def authenticate(con,authorization):
    migrate(con)
    try:
        if not authorization.startswith("Basic "):return None
        decoded=base64.b64decode(authorization[6:],validate=True).decode()
        username,password=decoded.split(":",1)
        record=con.execute("SELECT salt,digest FROM user_web_credentials WHERE username=?",(username,)).fetchone()
        if not record:return None
        digest=hashlib.pbkdf2_hmac("sha256",password.encode(),bytes.fromhex(record[0]),600000)
        if not hmac.compare_digest(digest,bytes.fromhex(record[1])):return None
        allowed={r[0] for r in con.execute("SELECT company_id FROM company_access WHERE username=? AND role IN ('read','input','write','admin')",(username,))}
        has_private_table=con.execute("SELECT 1 FROM sqlite_master WHERE type='table' AND name='private_scan_profiles'").fetchone()
        private=con.execute("SELECT 1 FROM private_scan_profiles WHERE username=? LIMIT 1",(username,)).fetchone() if has_private_table else None
        return (username,allowed) if allowed or private else None
    except (ValueError,UnicodeError,OverflowError,binascii.Error):return None

def owns_job(con,signature,companies):
    if not companies:return False
    return bool(con.execute("""SELECT 1 FROM jobs j JOIN company_profile_links l ON l.profile_id=j.profile_id
         WHERE j.signature=? AND l.company_id IN ("""+",".join("?" for _ in companies)+")",(signature,*sorted(companies))).fetchone())

def private_role(con,username):
    migrate(con)
    row=con.execute("SELECT role FROM private_web_roles WHERE username=?",(username,)).fetchone()
    return row[0] if row and row[0] in ("read","manage") else "read"

def set_private_role(con,username,role):
    migrate(con)
    if role not in ("read","manage"):raise ValueError("Ungültige Privatrolle")
    if not con.execute("SELECT 1 FROM smb_accounts WHERE username=?",(username,)).fetchone():
        raise ValueError("Benutzer existiert nicht")
    con.execute("INSERT INTO private_web_roles(username,role) VALUES (?,?) ON CONFLICT(username) DO UPDATE SET role=excluded.role",(username,role))

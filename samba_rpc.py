#!/usr/bin/env python3
"""Local privileged Samba RPC service. Only qrscan may connect."""
import json
import os
import pwd
import socket
import struct
import subprocess
from pathlib import Path

SOCKET=Path("/run/qrscan/samba.sock")
HELPER="/usr/local/lib/qrscan/samba_helper.py"
MAX=16384

def serve():
    SOCKET.parent.mkdir(parents=True,exist_ok=True)
    if SOCKET.exists():SOCKET.unlink()
    sock=socket.socket(socket.AF_UNIX,socket.SOCK_STREAM)
    sock.bind(str(SOCKET))
    uid=pwd.getpwnam("qrscan").pw_uid
    os.chown(SOCKET,0,pwd.getpwnam("qrscan").pw_gid)
    os.chmod(SOCKET,0o660)
    sock.listen(10)
    try:
        while True:
            conn,_=sock.accept()
            with conn:
                try:
                    peer=conn.getsockopt(socket.SOL_SOCKET,socket.SO_PEERCRED,12)
                    pid,client_uid,gid=struct.unpack("3i",peer)
                    if client_uid!=uid:raise PermissionError("Unauthorised user")
                    parts=[]
                    total=0
                    while True:
                        piece=conn.recv(min(4096,MAX+1-total))
                        if not piece:break
                        total+=len(piece)
                        if total>MAX:raise ValueError("Request too large")
                        parts.append(piece)
                    request=json.loads(b"".join(parts))
                    if not isinstance(request,dict) or request.get("action") not in ("list","create","update","password","delete","protect-datev","company-user-create","company-sync-shares"):
                        raise ValueError("Invalid action")
                    result=subprocess.run([HELPER],input=json.dumps(request),text=True,capture_output=True,timeout=45)
                    reply=json.loads(result.stdout)
                except Exception as exc:
                    reply={"ok":False,"error":str(exc)[:300]}
                conn.sendall(json.dumps(reply,ensure_ascii=False).encode())
    finally:
        sock.close()
        SOCKET.unlink(missing_ok=True)

if __name__=="__main__":serve()

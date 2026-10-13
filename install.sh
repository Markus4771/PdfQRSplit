#!/usr/bin/env bash
set -euo pipefail
[[ $EUID -eq 0 ]] || { echo "Als root starten"; exit 1; }
apt-get update
apt-get install -y python3 samba
id -u qrscan >/dev/null 2>&1 || useradd --system --home /var/lib/qrscan --shell /usr/sbin/nologin qrscan
install -d -o qrscan -g qrscan -m 700 /var/lib/qrscan
install -d -o root -g root -m 755 /opt/qrscan
install -m 755 app.py /opt/qrscan/app.py
if [[ ! -f /var/lib/qrscan/auth.json ]]; then
  python3 - <<'PY'
import hashlib,json,secrets
from pathlib import Path
password=secrets.token_urlsafe(18)
salt=secrets.token_bytes(16)
data=dict(salt=salt.hex(),rounds=600000,digest=hashlib.pbkdf2_hmac("sha256",password.encode(),salt,600000).hex(),must_change=True)
p=Path("/var/lib/qrscan/auth.json");p.write_text(json.dumps(data));p.chmod(0o600)
print("Einmaliger QR-Scan-Manager Zugang: admin /",password)
print("Passwort jetzt sicher verwahren; beim ersten Login ändern.")
PY
  chown qrscan:qrscan /var/lib/qrscan/auth.json
fi
# Manager-Datei nur lesbar machen, ohne Samba-Konfiguration zu verändern.
if [[ -e /etc/samba/share-manager.conf ]]; then
  groupadd -f qrscan-share-read
  usermod -aG qrscan-share-read qrscan
  chgrp qrscan-share-read /etc/samba/share-manager.conf
  chmod 640 /etc/samba/share-manager.conf
fi
cat >/etc/systemd/system/qrscan-web.service <<'EOF'
[Unit]
Description=QR Scan Manager Web UI
After=network.target
[Service]
User=qrscan
Group=qrscan
SupplementaryGroups=qrscan-share-read
WorkingDirectory=/opt/qrscan
ExecStart=/usr/bin/python3 /opt/qrscan/app.py
Environment=QRSCAN_BIND=0.0.0.0
Environment=QRSCAN_PORT=8086
Restart=on-failure
NoNewPrivileges=yes
ProtectSystem=strict
ProtectHome=yes
ReadWritePaths=/var/lib/qrscan
PrivateTmp=yes
[Install]
WantedBy=multi-user.target
EOF
systemctl daemon-reload
systemctl enable --now qrscan-web.service
echo "GUI: http://SERVER-IP:8086 (nur im geschützten LAN nutzen)"
echo "HINWEIS: Das ist vorerst die Konfigurations-GUI. PDF-Worker folgt."

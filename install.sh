#!/usr/bin/env bash
set -Eeuo pipefail
trap 'echo "Installation fehlgeschlagen in Zeile $LINENO" >&2' ERR
if [[ ${EUID} -ne 0 ]]; then echo "Bitte mit sudo ausführen: sudo bash install.sh" >&2; exit 1; fi
if [[ ! -f app.py ]]; then echo "Im Projektverzeichnis ausführen (app.py fehlt)" >&2; exit 1; fi
. /etc/os-release
if [[ "${ID:-}" != debian ]]; then echo "Warnung: nur für Debian vorgesehen (gefunden: ${ID:-unbekannt})"; fi
export DEBIAN_FRONTEND=noninteractive
echo "[1/7] Debian Pakete installieren"
apt-get update
apt-get install -y --no-install-recommends \
  ca-certificates python3 python3-venv python3-pip python3-dev \
  build-essential pkg-config libzbar0 libzbar-dev libgl1 libglib2.0-0 \
  poppler-utils ghostscript qpdf imagemagick \
  ocrmypdf tesseract-ocr tesseract-ocr-deu tesseract-ocr-eng \
  samba smbclient acl python3-cryptography
echo "[2/7] Benutzer und Verzeichnisse"
getent group qrscan-share-read >/dev/null || groupadd --system qrscan-share-read
id -u qrscan >/dev/null 2>&1 || useradd --system --home-dir /var/lib/qrscan --shell /usr/sbin/nologin qrscan
usermod -aG qrscan-share-read qrscan
install -d -o qrscan -g qrscan -m 0700 /var/lib/qrscan
install -d -o root -g root -m 0755 /opt/qrscan
install -d -o qrscan -g qrscan -m 0750 /srv/qrscan
install -m 0755 app.py /opt/qrscan/app.py
echo "[3/7] Python-Umgebung und optionale PDF-Bibliotheken"
python3 -m venv /opt/qrscan/venv
/opt/qrscan/venv/bin/python -m pip install --disable-pip-version-check --upgrade pip
# Installiert die Python-Abhängigkeiten für QR- und PDF-Analyse.
/opt/qrscan/venv/bin/pip install --disable-pip-version-check \
  pypdf pymupdf opencv-python-headless pyzbar pillow fastapi uvicorn \
  "scan-pdf-cleaner-cli==1.0.0"
echo "[4/7] QR-Trennwerkzeug bereitstellen"
# Externe QR-Engine getrennt halten, sodass Updates der eigenen App sie nicht überschreiben.
if [[ ! -d /opt/qrscan/vendor/PdfQRSplit/.git ]]; then
  install -d -m 0755 /opt/qrscan/vendor
  git clone https://github.com/adlerweb/PdfQRSplit.git /opt/qrscan/vendor/PdfQRSplit
fi
echo "[5/7] Erstanmeldung einrichten (bestehende Zugangsdaten bleiben erhalten)"
if [[ ! -f /var/lib/qrscan/auth.json ]]; then
  python3 - <<'PY'
import hashlib,json,secrets
from pathlib import Path
password=secrets.token_urlsafe(18)
salt=secrets.token_bytes(16)
data=dict(salt=salt.hex(),rounds=600000,digest=hashlib.pbkdf2_hmac("sha256",password.encode(),salt,600000).hex(),must_change=True)
p=Path("/var/lib/qrscan/auth.json")
with p.open("x") as f: json.dump(data,f)
p.chmod(0o600)
print("Einmaliger GUI-Zugang: admin / "+password)
print("Passwort sicher verwahren. Bei Erstanmeldung muss es geändert werden.")
PY
  chown qrscan:qrscan /var/lib/qrscan/auth.json
fi
echo "[6/7] Samba-Leseanbindung (bestehende Samba-Konfiguration nicht überschreiben)"
# Der bestehende Samba-Manager kann bereits konfiguriert sein. Seine Include-Datei wird
# lediglich für die QR-GUI lesbar gemacht; es werden keine Freigaben angelegt oder geändert.
if [[ -f /etc/samba/share-manager.conf ]]; then
  chgrp qrscan-share-read /etc/samba/share-manager.conf
  chmod 0640 /etc/samba/share-manager.conf
fi
echo "[7/7] systemd-Dienst installieren"
cat >/etc/systemd/system/qrscan-web.service <<'EOF'
[Unit]
Description=QR Scan Manager configuration GUI
Wants=network-online.target
After=network-online.target
[Service]
Type=simple
User=qrscan
Group=qrscan
SupplementaryGroups=qrscan-share-read
WorkingDirectory=/opt/qrscan
Environment=QRSCAN_BIND=0.0.0.0
Environment=QRSCAN_PORT=8086
ExecStart=/opt/qrscan/venv/bin/python /opt/qrscan/app.py
Restart=on-failure
RestartSec=5
NoNewPrivileges=yes
ProtectSystem=strict
ProtectHome=yes
PrivateTmp=yes
ReadWritePaths=/var/lib/qrscan
[Install]
WantedBy=multi-user.target
EOF
systemctl daemon-reload
systemctl enable qrscan-web.service
systemctl restart qrscan-web.service
systemctl is-active --quiet qrscan-web.service || { journalctl -u qrscan-web -n 40 --no-pager; exit 1; }
echo "Installiert: Web-GUI unter http://SERVER-IP:8086 (nur internes LAN)."
echo "WICHTIG: QR-PDF-Worker, automatische Verarbeitung und vollständige Samba-GUI fehlen noch."

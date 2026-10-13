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
  poppler-utils ghostscript qpdf imagemagick default-jre-headless \
  ocrmypdf tesseract-ocr tesseract-ocr-deu tesseract-ocr-eng \
  samba smbclient acl python3-cryptography sudo git curl
echo "[2/7] Benutzer und Verzeichnisse"
getent group qrscan-share-read >/dev/null || groupadd --system qrscan-share-read
id -u qrscan >/dev/null 2>&1 || useradd --system --home-dir /var/lib/qrscan --shell /usr/sbin/nologin qrscan
usermod -aG qrscan-share-read qrscan
install -d -o qrscan -g qrscan -m 0700 /var/lib/qrscan
install -d -o root -g root -m 0755 /opt/qrscan
install -d -o qrscan -g qrscan -m 0750 /srv/qrscan
install -d -o root -g root -m 0755 /srv/samba-shares
install -m 0755 app.py /opt/qrscan/app.py
install -m 0755 worker.py /opt/qrscan/worker.py
install -m 0755 diagnose_qr.py /opt/qrscan/diagnose_qr.py
install -m 0755 watcher.py /opt/qrscan/watcher.py
install -m 0644 jobs_ui.py /opt/qrscan/jobs_ui.py
install -m 0644 profile_settings.py /opt/qrscan/profile_settings.py
install -m 0644 safe_publish.py /opt/qrscan/safe_publish.py
install -m 0644 datev_handoff.py /opt/qrscan/datev_handoff.py
install -m 0644 datev_visual.py /opt/qrscan/datev_visual.py
install -m 0644 test_datev_visual.py /opt/qrscan/test_datev_visual.py
install -m 0644 test_datev_handoff.py /opt/qrscan/test_datev_handoff.py
install -m 0644 retry_policy.py /opt/qrscan/retry_policy.py
install -m 0644 output_naming.py /opt/qrscan/output_naming.py
install -m 0644 test_output_naming.py /opt/qrscan/test_output_naming.py
install -m 0644 test_job_maintenance.py /opt/qrscan/test_job_maintenance.py
install -m 0644 test_retry_policy.py /opt/qrscan/test_retry_policy.py
install -m 0644 test_safe_publish.py /opt/qrscan/test_safe_publish.py
install -m 0755 selftest.py /opt/qrscan/selftest.py
install -d -o root -g root -m 0755 /usr/local/lib/qrscan
install -m 0755 -o root -g root samba_helper.py /usr/local/lib/qrscan/samba_helper.py
install -m 0755 -o root -g root samba_rpc.py /usr/local/lib/qrscan/samba_rpc.py
install -m 0755 sync_permissions.py /opt/qrscan/sync_permissions.py
echo "[3/7] Python-Umgebung und optionale PDF-Bibliotheken"
python3 -m venv /opt/qrscan/venv
/opt/qrscan/venv/bin/python -m pip install --disable-pip-version-check --upgrade pip
# Installiert die Python-Abhängigkeiten für QR- und PDF-Analyse.
/opt/qrscan/venv/bin/pip install --disable-pip-version-check \
  pypdf pypdf4 zxing pymupdf opencv-python-headless pyzbar pillow fastapi uvicorn \
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
if [[ -f /etc/samba/qrscan-shares.conf ]]; then
  chgrp qrscan-share-read /etc/samba/qrscan-shares.conf
  chmod 0640 /etc/samba/qrscan-shares.conf
fi
# Separate Samba include file, independent of the Stirling project.
touch /etc/samba/qrscan-shares.conf
chmod 0644 /etc/samba/qrscan-shares.conf
python3 - <<'PY'
from pathlib import Path
import re
p = Path("/etc/samba/smb.conf")
data = p.read_text()
include = "include = /etc/samba/qrscan-shares.conf"
if include not in data:
    if not re.search(r"(?im)^\s*\[global\]\s*$", data):
        raise SystemExit("Samba [global] fehlt in /etc/samba/smb.conf")
    backup = Path("/etc/samba/smb.conf.bak-qrscan")
    if not backup.exists():
        backup.write_text(data)
    data = re.sub(r"(?im)^(\s*\[global\]\s*)$", lambda m: m.group(1) + "\n   " + include, data, count=1)
    p.write_text(data)
PY
testparm -s >/dev/null
# Legacy sudo rule is no longer necessary; privileges live in a separate daemon.
rm -f /etc/sudoers.d/qrscan-samba
echo "[7/7] systemd-Dienst installieren"
cat >/etc/systemd/system/qrscan-web.service <<'EOF'
[Unit]
Description=QR Scan Manager configuration GUI
Requires=qrscan-samba.service
Wants=network-online.target
After=network-online.target qrscan-samba.service
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
cat >/etc/systemd/system/qrscan-watcher.service <<'EOF'
[Unit]
Description=QR Scan Manager profile-based PDF processing service
After=qrscan-web.service
Wants=qrscan-web.service
[Service]
Type=simple
User=qrscan
Group=qrscan
SupplementaryGroups=qrscan-share-read
WorkingDirectory=/opt/qrscan
ExecStart=/opt/qrscan/venv/bin/python /opt/qrscan/watcher.py
Environment=QRSCAN_POLL_SECONDS=5
Restart=on-failure
RestartSec=5
NoNewPrivileges=yes
ProtectSystem=strict
ProtectHome=yes
PrivateTmp=yes
ReadWritePaths=/var/lib/qrscan /srv/samba-shares
ReadOnlyPaths=/etc/samba
[Install]
WantedBy=multi-user.target
EOF
cat >/etc/systemd/system/qrscan-samba.service <<'EOF'
[Unit]
Description=QR Scan Manager privileged Samba controller
After=smbd.service
Requires=smbd.service
[Service]
Type=simple
User=root
Group=root
RuntimeDirectory=qrscan
RuntimeDirectoryMode=0755
ExecStart=/usr/bin/python3 /usr/local/lib/qrscan/samba_rpc.py
Restart=on-failure
RestartSec=3
NoNewPrivileges=yes
ProtectHome=yes
PrivateTmp=yes
[Install]
WantedBy=multi-user.target
EOF
systemctl daemon-reload
systemctl enable qrscan-samba.service
systemctl restart qrscan-samba.service

systemctl enable qrscan-watcher.service
systemctl restart qrscan-watcher.service
systemctl enable qrscan-web.service
systemctl restart qrscan-web.service
systemctl is-active --quiet qrscan-samba.service || { journalctl -u qrscan-samba -n 40 --no-pager; exit 1; }
systemctl is-active --quiet qrscan-web.service || { journalctl -u qrscan-web -n 40 --no-pager; exit 1; }
systemctl is-active --quiet qrscan-watcher.service || { journalctl -u qrscan-watcher -n 40 --no-pager; exit 1; }
/opt/qrscan/venv/bin/python -m unittest -v test_safe_publish test_retry_policy test_output_naming test_job_maintenance test_datev_handoff test_datev_visual
echo "[8/8] Fluent Bit (nur lokal, ohne DATEV-PC-Anbindung) installieren"
bash ./install_fluent_bit.sh
echo "Installiert: Web-GUI unter http://SERVER-IP:8086 (nur internes LAN)."
echo "Nach dem Anlegen von Profilen einmal: sudo /opt/qrscan/venv/bin/python /opt/qrscan/sync_permissions.py"
echo "Selbsttest: sudo /opt/qrscan/venv/bin/python /opt/qrscan/selftest.py"
echo "Samba-Verwaltung ist in der Web-GUI angebunden. Nur im geschützten Administrationsnetz nutzen."
echo "Produktivbetrieb erst nach vollständigem Debian-13- und Samba-Integrationstest!"

#!/usr/bin/env bash
# Installs an isolated, loopback-only Fluent Bit collector for QR Scan Manager.
set -Eeuo pipefail
[[ ${EUID} -eq 0 ]] || { echo "root required" >&2; exit 1; }
. /etc/os-release
if [[ "${ID:-}" != "debian" ]]; then echo "Fluent Bit setup requires Debian" >&2; exit 1; fi
codename="${VERSION_CODENAME:-}"
[[ "${codename}" =~ ^[a-z]+$ ]] || { echo "Invalid Debian codename" >&2; exit 1; }
apt-get install -y --no-install-recommends gnupg ca-certificates curl
install -d -m 0755 /usr/share/keyrings
keytmp="$(mktemp)"
trap 'rm -f "$keytmp"' EXIT
curl --fail --location --silent --show-error --proto '=https' --tlsv1.2 \
  https://packages.fluentbit.io/fluentbit.key -o "$keytmp"
gpg --batch --yes --dearmor -o /usr/share/keyrings/fluentbit-keyring.gpg "$keytmp"
chmod 0644 /usr/share/keyrings/fluentbit-keyring.gpg
printf 'deb [signed-by=/usr/share/keyrings/fluentbit-keyring.gpg] https://packages.fluentbit.io/debian/%s %s main\n' "$codename" "$codename" \
  > /etc/apt/sources.list.d/fluent-bit.list
apt-get update
apt-get install -y --no-install-recommends fluent-bit
binary="/opt/fluent-bit/bin/fluent-bit"
[[ -x "$binary" ]] || { echo "Fluent Bit binary missing: $binary" >&2; exit 1; }
if ! id -u qrscan-logs >/dev/null 2>&1; then
    useradd --system --no-create-home --shell /usr/sbin/nologin qrscan-logs
fi
install -d -o root -g root -m 0755 /etc/qrscan
install -d -o qrscan-logs -g qrscan-logs -m 0700 /var/lib/qrscan-fluent-bit
# This receiver is intentionally NOT reachable from Windows until TLS and
# per-machine authentication have been configured in a separate step.
cat > /etc/qrscan/fluent-bit.conf <<'EOF'
[SERVICE]
    Flush          5
    Daemon         Off
    Log_Level      info
    storage.path   /var/lib/qrscan-fluent-bit
    storage.sync   normal
    storage.max_chunks_up 16

[INPUT]
    Name              forward
    Tag_Prefix        qrscan.
    Listen            127.0.0.1
    Port              24224
    Buffer_Chunk_Size 256K
    Buffer_Max_Size   1M
    Mem_Buf_Limit     8M

# No log storage/export is configured before log format and retention are reviewed.
[OUTPUT]
    Name   null
    Match  *
EOF
chmod 0644 /etc/qrscan/fluent-bit.conf
cat > /etc/systemd/system/qrscan-fluent-bit.service <<'EOF'
[Unit]
Description=QR Scan Manager local-only Fluent Bit receiver (staging)
After=network.target
[Service]
Type=simple
User=qrscan-logs
Group=qrscan-logs
ExecStart=/opt/fluent-bit/bin/fluent-bit -c /etc/qrscan/fluent-bit.conf
Restart=on-failure
RestartSec=5
NoNewPrivileges=yes
ProtectSystem=strict
ProtectHome=yes
PrivateTmp=yes
ReadWritePaths=/var/lib/qrscan-fluent-bit
[Install]
WantedBy=multi-user.target
EOF
systemctl daemon-reload
systemctl enable --now qrscan-fluent-bit.service
systemctl restart qrscan-fluent-bit.service
systemctl is-active --quiet qrscan-fluent-bit.service
echo "Fluent Bit is listening only on 127.0.0.1:24224; no Windows ingestion configured."

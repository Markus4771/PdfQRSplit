#!/usr/bin/env bash
# Non-destructive Phase 1 validation. Run from a clean checkout on a test VM.
set -Eeuo pipefail
cd "$(dirname "$0")/.."
PYTHON="${PYTHON:-python3}"
echo "[1/3] Python syntax validation"
"$PYTHON" -m compileall -q .
echo "[2/3] Private profiles, access control and user configuration"
"$PYTHON" -m unittest -v test_private_scans test_company_web_access test_config_users
echo "[3/3] Optional SQLite integrity check (read-only)"
if [[ -n "${QRSCAN_TEST_DB:-}" ]]; then
  DB="$QRSCAN_TEST_DB" "$PYTHON" - <<'PY'
import os, sqlite3
from pathlib import Path
p=Path(os.environ["DB"]).resolve(strict=True)
con=sqlite3.connect("file:"+str(p)+"?mode=ro",uri=True)
try:
    status=con.execute("PRAGMA integrity_check").fetchone()[0]
    print("SQLite integrity_check:",status)
    if status!="ok":raise SystemExit(1)
    for table in ("profiles","private_scan_profiles","company_access","jobs"):
        present=con.execute("SELECT 1 FROM sqlite_master WHERE type='table' AND name=?",(table,)).fetchone()
        if present:
            count=con.execute('SELECT COUNT(*) FROM "'+table+'"').fetchone()[0]
            print(table,":",count)
finally:
    con.close()
PY
else
  echo "Skipping DB check (set QRSCAN_TEST_DB=/path/to/backup.sqlite3)"
fi
echo "Phase 1 validation commands completed successfully."

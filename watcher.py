#!/usr/bin/env python3
"""Read-only polling watcher for configured input shares. No PDF processing."""
import json
import logging
import os
import signal
import sqlite3
import time
from pathlib import Path

DATA = Path(os.environ.get("QRSCAN_DATA", "/var/lib/qrscan"))
DB = DATA / "profiles.sqlite3"
SAMBA = Path(os.environ.get("QRSCAN_SAMBA_CONFIG", "/etc/samba/share-manager.conf"))
ROOT = Path(os.environ.get("QRSCAN_SHARE_ROOT", "/srv/samba-shares")).resolve()
INTERVAL = max(2, int(os.environ.get("QRSCAN_POLL_SECONDS", "5")))
STOP = False

def stop(*_):
    global STOP
    STOP = True

def managed_paths():
    """Read only SMB shares managed by the existing share manager."""
    results = {}
    if not SAMBA.is_file():
        logging.warning("Samba manager config unavailable: %s", SAMBA)
        return results
    current = None
    data = {}
    def flush():
        if current is None:
            return
        raw = data.get("path")
        if not raw:
            return
        folder = Path(raw)
        try:
            if (folder.is_dir() and not folder.is_symlink()
                    and folder.resolve().parent == ROOT):
                results[current] = folder
        except OSError:
            pass
    for line in SAMBA.read_text(errors="replace").splitlines():
        line = line.strip()
        if line.startswith("[") and line.endswith("]"):
            flush()
            current = line[1:-1]
            data = {}
        elif "=" in line and current:
            key, value = line.split("=", 1)
            data[key.strip().lower()] = value.strip()
    flush()
    return results

def configured_inputs():
    if not DB.is_file():
        logging.warning("Profile database not yet available")
        return set()
    try:
        with sqlite3.connect(f"file:{DB}?mode=ro", uri=True, timeout=2) as con:
            return {row[0] for row in con.execute(
                "SELECT DISTINCT input_share FROM profiles")}
    except sqlite3.Error as exc:
        logging.error("Cannot read profile database: %s", exc)
        return set()

def monitor():
    # Key: (share name, filename). Values: (size, mtime_ns, stable poll count).
    observed = {}
    announced = set()
    logging.info("QR scan watcher started (read-only; interval=%ss)", INTERVAL)
    while not STOP:
        inputs = configured_inputs()
        folders = managed_paths()
        present = set()
        for name in sorted(inputs):
            folder = folders.get(name)
            if folder is None:
                logging.warning("Input share not accessible/mapped: %s", name)
                continue
            try:
                for path in folder.iterdir():
                    if path.is_symlink() or not path.is_file() or path.suffix.lower() != ".pdf":
                        continue
                    key = (name, path.name)
                    present.add(key)
                    try:
                        stat = path.stat()
                    except OSError:
                        continue
                    signature = (stat.st_size, stat.st_mtime_ns)
                    old = observed.get(key)
                    count = old[2]+1 if old and old[:2] == signature else 0
                    observed[key] = (*signature, count)
                    if key not in announced and count >= 2 and stat.st_size > 0:
                        logging.info("PDF detected: share=%s file=%s bytes=%s (not processed)",
                                     name, path.name, stat.st_size)
                        announced.add(key)
            except OSError as exc:
                logging.error("Cannot list input share %s: %s", name, exc)
        # Forget files that disappeared; a new file of the same name can be observed.
        for key in list(observed):
            if key not in present:
                observed.pop(key, None)
                announced.discard(key)
        time.sleep(INTERVAL)
    logging.info("Watcher stopped")

if __name__ == "__main__":
    logging.basicConfig(level=logging.INFO, format="%(asctime)s %(levelname)s %(message)s")
    signal.signal(signal.SIGTERM, stop)
    signal.signal(signal.SIGINT, stop)
    monitor()

# PdfQRSplit – Repository-Wissen

Webanwendung zum Scannen und Aufteilen von PDF-Scans anhand von QR-Codes.
Debian 13, Python-Standardbibliothek-HTTP-Server, SQLite, Samba-Freigaben.

## Befehle

```bash
# Gesamte Testsuite (16+1 Testmodule, kein pytest noetig)
python3 -m unittest discover -v -s . -p 'test_*.py'

# Einzelnes Modul
python3 -m unittest -v test_review_fixes

# ResourceWarnings als Fehler behandeln (deckt undichte SQLite-Verbindungen auf)
python3 -W error::ResourceWarning -m unittest discover -s . -p 'test_*.py'

# Syntaxpruefung
bash -n install.sh
python3 -m compileall -q .
```

Lokale Testumgebung braucht: `pymupdf`, `pyzbar` + Systembibliothek `libzbar0`,
`scan-pdf-cleaner-cli==1.0.0`, `pypdf`.

## Aufbau

| Modul | Aufgabe |
|---|---|
| `app.py` | HTTP-Server, Routen, GUI. Zentraler Einstieg. |
| `watcher.py` | Beobachtet Samba-Eingangsshares, verarbeitet Dateien, schreibt `jobs`. |
| `worker.py` | PDF-Verarbeitung: QR-Trennung, OCR, Crop, Blank-Removal. |
| `jobs_ui.py` | Auftragsuebersicht und Warteschlange. |
| `company_admin.py` / `company_web_access.py` | Firmenverwaltung und Webzugang. |
| `datev_handoff.py` / `datev_visual.py` | DATEV-Uebergabe, SHA-256-Register, visuelle Dubletten. |
| `duplicate_review.py` | Read-only-Ansicht und Entscheidung bei Dublettenverdacht. |
| `sqlite_util.py` | Gemeinsamer `session()`-Kontextmanager, schliesst SQLite-Verbindungen. |

## Invarianten (nicht verletzen)

- **DATEV-Digest-Sperre:** Der Ausgabename ist `beleg_<sha256>.pdf`. Identische
  PDF-Bytes werden auch nach manueller Wiederholung **nicht erneut** uebergeben.
  `publish_datev` liefert diese Faelle in `duplicates`. Das ist gewollt
  (README, Abschnitt DATEV-Sicherheitsmodus) und kein Fehler.
- **Kein Ueberschreiben:** `safe_publish.publish` und `os.link` mit
  `follow_symlinks=False` verhindern das Ueberschreiben vorhandener Dateien.
- **Fail closed:** Ist Samba nicht erreichbar, werden Zugriffsrechte nicht
  stillschweigend unveraendert gelassen. `samba_shares()` wirft dann.
- **Originale bleiben unangetastet:** Eingangs-PDFs werden nur archiviert, nie
  geloescht. Das Originalarchiv liegt in einem privaten Verzeichnis.
- **Firmen-Isolation:** Zuordnungen laufen ueber `company_profile_links` und
  `jobs.profile_id`. Fremde Firmen sehen keine Daten.
- **`jobs.file` ist die Originalpfad-Referenz:** Das Register `datev_suspects.source`
  muss `jobs.file` entsprechen, nicht dem temporaeren Watcher-Snapshot. Deshalb
  ruft der Watcher `run(..., origin=path)` auf.

## SQLite-Verbindungen

`sqlite3.connect()` als Contextmanager committet, schliesst aber **nicht**.
Deshalb ueberall `sqlite_util.session(...)` statt `with sqlite3.connect(...)`.
Der Default-Isolation-Level ist `""` (sqlite3-Standard). `isolation_level=None`
bedeutet Autocommit und wird nur in `datev_handoff.py` bewusst verwendet,
weil dort manuell mit `BEGIN IMMEDIATE` gearbeitet wird.

## Origin-Schutz

`app.origin_allowed(origin, host)` akzeptiert `http` und `https` mit
identischem Hostnamen **und Port**. Hinter einem TLS-Reverse-Proxy ist daher
keine Zusatzkonfiguration nötig. Abweichende Proxy-Namen werden ueber
`QRSCAN_TRUSTED_ORIGINS` (kommagetrennt) erlaubt.

## Fallen, die schon einmal zugeschlagen haben

- **Einrueckung nach `with` umstellen:** Beim Ersetzen von `with db() as c:` durch
  `with db_session() as c:` muss der gesamte Block auf derselben Ebene bleiben.
  Sonst landen die Zuweisungen ausserhalb des Blocks und die Route endet mit
  `UnboundLocalError`. Deshalb gibt es Routen-Smoke-Tests in
  `test_review_fixes.py` (`RouteSmokeTests`).
- **Isolations-Level:** `sqlite_util.session()` nutzt standardmaessig `""`
  (sqlite3-Standard). `isolation_level=None` heisst Autocommit und schaltet
  Rollback ab. Nur `datev_handoff.py` setzt es bewusst.
- **Ports gehoeren zum Origin:** `origin_allowed()` vergleicht Host **und** Port.
  `https://host:8443` passt nicht zu `Host: host`.
- **CI braucht `scan_pdf_cleaner`:** `worker.py` importiert es direkt. Die
  Debian-13-CI installiert es deshalb ueber pip in ein venv.

## Debian 13 (trixie) heisst anders als Debian 12

Trixie hat die 64-Bit-Bibliotheken umbenannt und liefert kein `pyzbar`:

| alt (Debian 12) | neu (Debian 13) |
| --- | --- |
| `libzbar0` | `libzbar0t64` |
| `libglib2.0-0` | `libglib2.0-0t64` |
| `python3-pyzbar` | gibt es nicht mehr (`python3-zbar` liefert `zbar`, nicht `pyzbar`) |

`pyzbar` kommt daher aus pip. Ein falscher Paketname bricht `apt-get` mit
Exit-Code 100 ab, ohne eine hilfreiche Meldung.

Zusaetzlich: apt-Pakete landen im **System**-Python. Ein venv erbt deren
`sys.path` nicht, also braucht das venv `pymupdf` und `pillow` selbst,
sonst fehlen `fitz` und `PIL`.

Paketnamen immer gegen `deb.debian.org/debian/dists/trixie/main/binary-amd64/Packages.gz`
pruefen, nicht gegen `packages.debian.org` - die Webseite antwortet auch
fuer nicht existierende Pakete mit HTTP 200.

## Konventionen

- Module werden in `install.sh` mit `install -m 0644` nach `/opt/qrscan` kopiert.
  Neue Module und Testdateien dort eintragen, sonst fehlen sie im Deployment.
- Der Installer fuehrt am Ende alle Testmodule aus. Neue Testmodule eintragen.
- Die CI-Datei `.github/workflows/debian13.yml` nutzt `unittest discover`.
- Keine neue Abhaengigkeit ohne Eintrag in `install.sh`.
- Der Code-Stil ist kompakt: kurze Namen, keine Leerzeichen um `=`,
  Einrueckung 4 Leerzeichen ausserhalb von `install.sh`.

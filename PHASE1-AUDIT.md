# Phase 1: Code- und Sicherheitsprüfung (Zwischenstand)

## Durchgeführte Änderungen

- Private Profile dürfen weder DATEV-Eingangs-, DATEV-Ausgangs- noch DATEV-Archivfreigaben erneut verwenden. Die Prüfung umfasst beide private Freigaben.
- Private Fotoverarbeitung deaktiviert nicht länger OCR und Leerseitenprüfung für PDF-Dokumente desselben Profils.
- Administratorprüfungen unterscheiden die echte Administrator-Authentifizierung von regulären Benutzerkonten mit dem Namen `admin`.
- Der private Schreibzugriff setzt eine explizite Verwaltungsrolle und ein zugeordnetes privates Profil voraus. Die konkrete Profil-Eigentümerschaft wird bei `/private-update` vor der Änderung geprüft.
- Regressionstests für DATEV-Freigabenkollisionen, kombinierte Foto-/PDF-Profile und private Rollen ergänzt.
- GitHub Actions führt eine Kompilierungsprüfung aller Python-Dateien sowie die einschlägigen Unittests auf Push aus.

## Offene Prüfungen vor Produktivfreigabe

1. GitHub-Actions-Lauf erfolgreich abschließen; bisher kein bestätigtes Ergebnis.
2. Gesamte Testsuite aus `install.sh` gegen einen frischen Debian-Testhost ausführen.
3. Bestehende Produktionsdatenbank vor und nach Migration vergleichen (Schemas, Zeilenzahlen, DATEV-Dublettensperren).
4. Zugriffe mit mindestens drei Benutzeridentitäten prüfen: Administrator, Privatnutzer mit `read`, Privatnutzer mit `manage` und Firma/DATEV.
5. HTTP Basic Authentication nur mit HTTPS außerhalb eines vertrauenswürdigen internen Netzes verwenden.
6. SMB-Watcher und geteilte SMB-Nutzer sowie fehlgeschlagene zweite Share-Anlage praxisnah testen.

## Änderungsgrenzen

Keine vorhandenen PDF-Dateien, SMB-Shares oder Datenbankzeilen werden durch diese GitHub-Commits unmittelbar verändert. Es erfolgte kein Merge nach `main` und keine Installation auf dem Zielhost. Die Versionsfreigabe bleibt gesperrt, bis die Prüfungen bestanden sind.

## Stand der Testabnahme

Beim GitHub-Commit `a9f36882d657284b3f3762fbd13ba412bc1dfbdc` waren keine bestätigten GitHub-Actions-Ergebnisse abrufbar. Der Entwicklungsbranch ist daher **nicht abgenommen**.

Ein nicht destruktiver Prüfablauf ist unter `scripts/phase1-check.sh` vorhanden. Auf einer separaten Debian-Test-VM mit ausgechecktem Feature-Branch:

```bash
cd /root/PdfQRSplit
git status
git fetch origin
git switch feature/private-users-multi-shares
git pull --ff-only
bash scripts/phase1-check.sh
```

Optional kann ein **vorher angefertigter Datenbank-Sicherungskopiepfad** übergeben werden:

```bash
QRSCAN_TEST_DB=/pfad/zur/testkopie/profiles.sqlite3 bash scripts/phase1-check.sh
```

Der Prüfablauf installiert nichts, ändert keine Samba-Freigaben und verändert die Datenbank nicht. Er führt die Syntaxprüfung und ausgewählte Unit-Tests aus. Die reale Verarbeitung und eine vollständige Installations-/Migrationstestung bleiben zusätzlich erforderlich.

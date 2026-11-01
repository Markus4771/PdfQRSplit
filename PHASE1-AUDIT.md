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

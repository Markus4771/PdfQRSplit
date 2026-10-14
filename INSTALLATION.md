# PdfQRSplit – Installationsanleitung

## Voraussetzungen

- Frische Debian-Installation (Installer ist auf Debian ausgelegt), Zugriff als root/sudo
- Statische IP-Adresse, Netzverbindung und ausreichend Platz für Scans, Datenbank und Archive
- Git-Zugriff zum Repository `Markus4771/PdfQRSplit`
- Zugriff im vertrauenswürdigen LAN; für Web-Zugänge über ungeschützte Netze TLS/HTTPS per Reverse Proxy bereitstellen
- Vor Updates Sicherung des Servers, insbesondere `/var/lib/qrscan`, `/etc/samba` und PDF-Freigaben

## Neu installieren

```bash
apt-get update
apt-get install -y git
cd /root
git clone https://github.com/Markus4771/PdfQRSplit.git
cd PdfQRSplit
bash install.sh
```

Die Installation richtet Webdienst, Watcher und Samba-Verwaltungsdienst ein. Bitte Konsolenausgabe und Tests auf Fehler kontrollieren. Bei einem Abbruch den Fehler beheben und das idempotente Skript erneut aufrufen – keine Datenverzeichnisse manuell löschen.

## Bestehende Installation aktualisieren

```bash
cd /root/PdfQRSplit
git pull --ff-only
bash install.sh
```

Dienste prüfen:

```bash
systemctl status qrscan-web qrscan-watcher qrscan-samba --no-pager
journalctl -u qrscan-web -u qrscan-watcher -u qrscan-samba -n 100 --no-pager
```

Weboberfläche im LAN: `http://SERVER-IP:8086/` (im bisherigen Testaufbau `http://192.168.0.55:8086/`). Das Administratorpasswort beim ersten Login ändern, wenn die Oberfläche dies verlangt.

## Ersteinrichtung

1. Als Administrator anmelden und `/companies` öffnen.
2. Firmenkennung und DATEV-Belegarten anlegen.
3. SMB-Benutzer anlegen oder vorhandene Konten geprüft übernehmen.
4. Je Benutzer E-Mail-Adresse speichern. Zusätzlich **eigenes Web-Passwort** setzen (mindestens 12 Zeichen, nicht das Samba-Passwort). Ohne Web-Passwort gibt es keinen Firmen-Webzugriff.
5. Je Firma Benutzer per Checkbox auswählen, Rolle zuweisen und **Benutzerzuordnung speichern**. Zugehörige Web-Nutzer sehen nur ihre Firmen.
6. Firmenstandard/Belegart auswählen und QR-Trennung, OCR und DATEV-Einstellungen speichern.
7. Mit „Fehlende Samba-Freigaben anlegen / Rechte synchronisieren“ Freigaben und automatisch verwaltete Profile erzeugen.
8. Unter `/notifications` SMTP-Server, Benutzer, verschlüsselten Port, Absender und Passwort eintragen; Warnungen erst nach Prüfung aktivieren. Empfänger werden aus den E-Mail-Adressen der zugeordneten Firmenbenutzer ermittelt.
9. Mit Test-PDF Eingangsverarbeitung, Ausgang, Archiv und LOG prüfen. Der DATEV-Windows-Belegtransfer muss separat getestet werden.

## Sicherheit und Fehlerdiagnose

- Firmen-Webzugänge haben **nur lesenden Zugriff** auf `/review`, `/datev-review` und erlaubte Original-PDFs; Administratoraktionen und DATEV-Freigaben sind ausgeschlossen.
- Basic-Authentifizierung über HTTP ist **nicht ausreichend für Zugriff über das Internet**; unbedingt TLS/HTTPS und Zugangsbeschränkung einsetzen.
- SMTP-Passwort liegt in der zugriffsbeschränkten lokalen Datenbank; Datensicherungen entsprechend schützen.
- Ein PDF im DATEV-Ausgang ist **kein** nachgewiesener DATEV-Upload.
- Bei unklarer Übertragung nicht erneut senden, bis der Belegtransfer-Status geprüft ist.
- Fehler in den Diensten über `journalctl` und `/jobs` untersuchen. Sichere Originale nicht ungeprüft löschen.

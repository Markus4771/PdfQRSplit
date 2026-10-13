# PdfQRSplit – QR Scan Manager

Webbasierter, headless PDF-Scanprozessor für Debian. **Status: Projektgrundlage, noch nicht produktiv einsetzbar.**

## Vereinbarte Funktionen

- Beliebig viele Zuordnungen zwischen Samba-Eingangs- und Ausgangsfreigaben
- Ein global einstellbarer QR-Code-Inhalt als Dokumenttrenner; andere QR-Codes ignorieren
- QR-Trennblätter standardmäßig behalten, optional entfernen (je Profil)
- Optional leere Seiten entfernen mit [Scan PDF Cleaner](https://github.com/The-Free-Converter/scan-pdf-cleaner)
- Optional weiße Seitenränder beschneiden mit Scan PDF Cleaner
- Optional OCR als **letzter Schritt** mit [OCRmyPDF](https://github.com/ocrmypdf/OCRmyPDF)
- Web-GUI zur Konfiguration, zum Testen und zur Einsicht in Protokolle
- Automatische Ordnerüberwachung, Schutz vor unvollständigen Uploads, Fehlerordner
- Installation auf Debian 13 ohne Desktop

## Vorgesehene Verarbeitung

Scanner -> Samba-Eingang -> QR-Code-Trennung -> optional QR-Blatt entfernen -> optional Leerseiten entfernen -> optional Ränder beschneiden -> optional OCR -> Samba-Ausgang.

Die Verarbeitungseinstellungen werden für jedes Eingangs-/Ausgangspaar einzeln gespeichert. Das QR-Trennmerkmal wird einmal zentral definiert.

## Übernahme der Samba-Verwaltung

Quelle: [Markus4771/Stirling/samba-share-manager](https://github.com/Markus4771/Stirling/tree/main/samba-share-manager).

Vorhanden sind u. a. `app.py`, `helper.py` und `install.sh`. Diese sind auf Stirling-Pfade und den Stirling-Dienstbenutzer zugeschnitten. Wir werden die Freigabenverwaltung **anpassen statt unverändert kopieren**. Insbesondere müssen Wiederverwendung von SMB-Benutzern, Passwortwechsel bei Erstanmeldung, sichere Authentifizierung, Pfadvalidierung, ACLs und Rechte getestet werden. Das Altprojekt nutzt ein bekanntes Erstpasswort; dieses darf nicht ungesichert auf einem neuen Server übernommen werden.

## Technische Architektur (vorgesehen)

- Python und FastAPI (GUI/API)
- SQLite für Freigabezuordnungen, Profile, Aufträge, Fehlerprotokolle
- PDF-Worker und Samba-Helper mit getrennten Berechtigungen
- [adlerweb/PdfQRSplit](https://github.com/adlerweb/PdfQRSplit) als möglicher QR-Engine-Baustein, erst nach Prüfung der Schnittstelle und echtem Scantest
- Scan PDF Cleaner und OCRmyPDF als optionale Verarbeitungsschritte
- Atomisches Schreiben der Ausgabedateien; Quelldateien erst nach erfolgreichem Abschluss archivieren oder entfernen
- systemd-Service, Installer, Tests und Upgrade-Anleitung

**Derzeit sind nur Planung und Grundkonfiguration hinterlegt.** Noch kein produktionsfähiger Installer oder laufender Dienst. Die vorhandene Stirling-Installation wird durch dieses Repository nicht verändert.

## Erste Web-GUI (experimentell, Stand 13.10.2026)

Im Repository liegen jetzt `app.py` und `install.sh`. Der Installer richtet den Dienst `qrscan-web.service` mit dem eigenen unprivilegierten Systembenutzer `qrscan` ein. Aufruf nach Installation: `http://SERVER-IP:8086` (nur geschütztes LAN). Ein zufällig generiertes einmaliges Administratorpasswort wird **bei erstmaliger Installation** im Terminal ausgegeben; nach dem ersten Login ist ein Wechsel erforderlich.

Die Web-GUI liest **nur** die vom bisherigen Stirling-Samba-Manager verwalteten Shares unter `/srv/samba-shares/<Name>`; sie verändert weder `smb.conf` noch Samba-Passwörter. Freigaben müssen zunächst im Stirling-Samba-Manager angelegt werden. Die Oberfläche speichert Profilzuordnungen und QR-Text in SQLite.

**Nicht implementiert:** produktiver PDF-Worker, QR-Code-Auswertung, Leerseitenentfernung, OCR, Verwaltung der Samba-Benutzer in derselben GUI, Verarbeitungstests, Profile bearbeiten und QR-Trennblatt-PDF erzeugen. Der Installer installiert diese Verarbeitungstools noch nicht. Dieses erste Stadium darf nicht als fertiger Scanserver eingesetzt werden.

### Testinstallation (isolierter Debian-Testserver)

```bash
sudo apt-get install -y git
 git clone https://github.com/Markus4771/PdfQRSplit.git
cd PdfQRSplit
sudo bash install.sh
sudo systemctl status qrscan-web --no-pager
```

Achtung: Die bisherige Stirling-Freigabenverwaltung verwendet eine eigenständige Konfiguration; die neue GUI ist derzeit nur eine lesende Anbindung. Vor Integration in bestehende Produktivsysteme Samba-Konfiguration sichern und Rechte prüfen.

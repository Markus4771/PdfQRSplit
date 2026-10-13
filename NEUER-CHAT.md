# Entwicklungsstand – PdfQRSplit

Stand: 13.10.2026

## Beschlossene Anforderungen

1. Headless Debian-13-Webanwendung mit eigener GUI (vorläufig Python/FastAPI).
2. Vorhandene Samba-Freigabenverwaltung aus `Markus4771/Stirling/samba-share-manager` als Grundlage übernehmen. Mehrere Eingangsfreigaben werden individuell Ausgangsfreigaben zugeordnet. Dieselben SMB-Zugangsdaten dürfen mehrfach verwendet werden.
3. Ein global definierter QR-Code-Inhalt zum Trennen. QR-Trennseite wird standardmäßig **behalten** und kann je Verarbeitungspaar optional entfernt werden.
4. Optional `scan-pdf-cleaner`: Leerseiten entfernen; optional weiße Ränder beschneiden. Einstellbarer Schwellwert und ein Testmodus ohne Löschung.
5. Optional `ocrmypdf` als **letzter Schritt**: Deutsch/Englisch, PDF/PDF-A, vorhandene Texte überspringen, automatische Rotation, Schräglagenkorrektur.
6. Für jeden Auftrag getrennte Protokolle, Fehlerordner, stabile Dateierkennung und Schutz vor Datenverlust.
7. README.md, NEUER-CHAT.md, Installation auf einem frischen Debian 13; Standardpasswortproblematik des Stirling-Projekts nicht übernehmen.

## Quelle Samba-Modul

`https://github.com/Markus4771/Stirling/tree/main/samba-share-manager`

Die Codeprüfung zeigte spezielle Stirling-Pfade, Stirling-ACLs und eine eigene GUI mit Admin-Authentifizierung. Die Anpassung an PdfQRSplit erfordert unabhängige Pfade und Dienstkonten. Keine produktive Übernahme ohne Authentifizierungs-, Pfad- und Mehrfachbenutzertests.

## Nächste Umsetzungsschritte

- Nutzbare Module aus dem Stirling-Projekt übernehmen und für PdfQRSplit isolieren
- Datenmodell, FastAPI-Oberfläche und Konfigurationsspeicherung realisieren
- PDF-Worker für QR-Trennung und die optionalen Verarbeitungsstufen implementieren
- Jede Stufe mit echten gescannten PDFs, QR-Blättern und schwach bedruckten Seiten testen
- Debian-Installationsskript und systemd-Units erstellen und auf frischer Testinstallation validieren

## Stand GitHub

`Markus4771/PdfQRSplit`: Dokumentation und Beispiel-Profilkonfiguration angelegt; noch keine installierbare Anwendung. Nicht mit fertiger Installation verwechseln.

## Implementierung in dieser Entwicklungsrunde

- `app.py`: erste passwortgeschützte Konfigurations-GUI auf Port 8086; globaler QR-Text, Profilzuordnung, optionale Verarbeitungsschritte, SQLite.
- `install.sh`: Debian-Installer für die Web-GUI, eigener Benutzer, systemd, zufälliges Startpasswort und erzwungener Erstwechsel.
- Lesen bestehender managerverwalteter SMB-Shares aus `/etc/samba/share-manager.conf`; aus Sicherheitsgründen keine Kopie des privilegierten Samba-Helpers.
- **Noch offen:** Echte QR-/Leerseiten-/OCR-Verarbeitung, Tests auf Debian, Bearbeitung vorhandener Profile, Samba-UI-Integration.

## Installer-Update

`install.sh` installiert nun automatisch die Paket- und Python-Abhängigkeiten für alle vereinbarten Komponenten (inkl. Java/ZXing für PdfQRSplit, Scan PDF Cleaner, OCRmyPDF/Tesseract, Samba und Web-GUI). Es bleibt ein **experimenteller** Installer: keine PDF-Worker-Integration, kein vollständiger Samba-Manager, noch kein Debian-13-Livetest. Neue Installationen erstellen zufällige GUI-Zugangsdaten, Updates behalten vorhandene Passwörter.

## PDF-Worker integriert (13.10.2026)
- Neues `worker.py`: verarbeitet Einzel-PDFs via Rendern/pyzbar-QR-Erkennung, PyMuPDF-Aufteilung, `scan_pdf_cleaner` und `ocrmypdf` am Schluss.
- QR-Trennblätter bleiben standardmäßig auf der ersten Seite des Folgedokuments, optionales Entfernen.
- Ausgabe ohne Überschreiben, Eingangsdatei bleibt unberührt.
- Installer kopiert den Worker und installiert notwendige Python-Abhängigkeiten.
- **Noch nicht getestet auf Debian 13 oder mit realen Scans.**
- **Noch offen:** Ausführung je gespeichertes GUI-Profil, automatische Eingangsordner-Überwachung, ACL- und Samba-Schreibrechte, Fehlermanagement, frei einstellbarer Leerseiten-Schwellenwert, vorsichtiger Crop-Test, testgestützte Qualitätssicherung.

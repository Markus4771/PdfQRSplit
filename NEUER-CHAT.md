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

## Umsetzung Schritt 1: Eingang überwachen

Neuer `watcher.py` und `qrscan-watcher.service` im Installer. Liest die Profil-Samba-Eingänge und erkennt stabile PDF-Dateien, loggt aber nur. Kein Löschen/Verschieben/Verarbeiten. Eigene Zugriffsrechte für `qrscan` bleiben noch zu konfigurieren und auf Debian zu testen. Nächster Schritt: echte Job-Verarbeitung nach der Erkennung.

## Schritt 2 implementiert – experimentell

`watcher.py` führt nun Profile automatisch aus, wenn Eingangsdateien mindestens 30 Sekunden stabil erscheinen und als PDF geöffnet werden können. Es verwendet die bestehenden Eingangs-/Ausgangszuordnungen, verarbeitet mittels `worker.run`, belässt die Quelle und speichert Jobstatus in SQLite. Fehler werden protokolliert, vorerst ohne automatischen Retry. Noch keine vollständigen Samba-ACLs, GUI-Jobliste oder Debian-Integrationstests. Alte Read-only-Aussage aus Schritt 1 ist überholt.

## Punkt 3 – 13.10.2026

`sync_permissions.py` ist als root ausführbarer ACL-Helfer für bereits verwaltete Profile hinzugefügt; Installer kopiert ihn, ändert Freigabe-ACLs nicht automatisch. systemd-Watcher erlaubt nun Schreiben unter /srv/samba-shares, sofern Unix-Rechte vorhanden sind. `watcher.py` speichert Wiederholungsversuche, wiederholt vorübergehende IO-Fehler maximal 3-mal und markiert nach Neustarts unterbrochene Jobs zur manuellen Prüfung. Noch nicht auf Debian 13 getestet, noch keine integrierte Samba-Freigabenerstellung.

## Punkt 5: Auftragsübersicht (13.10.2026)

`jobs_ui.py` ergänzt die bestehende Web-GUI um `/jobs`: Status-Übersicht, letzte 100 Aufträge und Fehlermeldungen, manuelles Wiederholen von `error`/`interrupted` mit Bestätigungscheckbox. `install.sh` kopiert das Modul. `watcher.py` markiert liegengebliebene `running`-Aufträge nur noch beim Dienststart als unterbrochen. Noch nicht praktisch getestet.

## Punkt 6 – 13.10.2026

Nichtdestruktiver Installations-Selbsttest `selftest.py` ergänzt; `install.sh` legt ihn im Zielsystem ab und gibt den Testbefehl aus. Der Code ist auf GitHub, aber ein echter Debian-13-Test ist hier mangels Server/DNS nicht durchgeführt worden. Kritische verbleibende Lücke: Der Samba-Helfer aus Punkt 4 ist noch nicht privilegiert angebunden; GUI und Helfer verwenden unterschiedliche Share-Konfigurationsdateien. Vor End-to-End-Freigabe vereinheitlichen und testen.

## Samba GUI verbunden

Die Web-GUI enthält jetzt Samba-Formulare; `samba_helper.py` ist über eine eingeschränkte sudo-Regel aus `install.sh` angebunden. Alle Komponenten referenzieren `/etc/samba/qrscan-shares.conf`, getrennt von Stirling. Gemeinsame SMB-Benutzer sind bei übereinstimmendem Passwort vorgesehen. Noch ohne Debian-13-Live-Test, daher nicht produktiv freigeben.

## Profilbearbeitung und OCR-Optionen

Neue Datei `profile_settings.py` mit Migration älterer SQLite-Profile, Formularen für die Bearbeitung und Eingabevalidierung. `app.py` speichert Änderungen, `watcher.py` überträgt OCR-Sprache, Ausgabeformat, Rotation/Deskew und Leerseiten-Schwellwert an `worker.py`. Installer kopiert die Datei. Noch kein Debian-13-Integrationstest.

## Punkt 3: Verarbeitungsabsicherung

Neues Modul `safe_publish.py` und Test `test_safe_publish.py`. Der Worker veröffentlicht vollständig vorbereitete PDFs ohne Überschreiben. Der Watcher hat nun eine Instanzsperre (`flock`), PDF-Snapshot mit Datenvergleich und eine erweiterte Auftragskennung, die den Quellpfad berücksichtigt. Installer und Selbsttest aktualisiert. Offene Risiken: Stromausfall während Mehrfachpublikation, Scanner-Copy-Race und noch fehlender praktischer Debian-/SMB-Test.

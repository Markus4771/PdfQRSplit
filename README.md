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

## Vollständiger Abhängigkeits-Installer

`install.sh` installiert auf Debian die **benötigten Laufzeitpakete und Python-Bibliotheken** in einer eigenen virtuellen Umgebung: Samba, PDF-Werkzeuge, PdfQRSplit samt Java/ZXing/PyPDF4, Scan PDF Cleaner, OCRmyPDF/Tesseract (Deutsch und Englisch), OpenCV und die Web-GUI. Voraussetzung: `sudo`, `git` und `curl` dürfen schon installiert sein; Git wird nur für den Repository-Checkout genutzt. Debian 13 ist Zielplattform.

```bash
git clone https://github.com/Markus4771/PdfQRSplit.git
cd PdfQRSplit
sudo bash install.sh
```

**Wichtig:** Alle technischen Abhängigkeiten zu installieren bedeutet noch nicht, dass sie in einer fertigen Verarbeitungspipeline verbunden sind. Der aktuelle Installer aktiviert nur `qrscan-web.service`, keinen produktiven PDF-Worker und keine automatische Samba-Freigabenverwaltung. Er ist noch nicht auf einem frischen Debian 13 durchgetestet. Erst auf einer Test-VM ausführen und vor produktiver Nutzung eine Sicherung anlegen.

Die Erstinstallation zeigt ein zufällig erzeugtes Administratorpasswort **einmalig** im Terminal. Bei einer erneuten Installation wird das bestehende Passwort nicht überschrieben.

```bash
sudo systemctl status qrscan-web --no-pager
sudo journalctl -u qrscan-web -n 50 --no-pager
```

## PDF-Einzeldatei-Worker (neu)

`worker.py` verarbeitet **eine einzelne PDF-Datei** in dieser Reihenfolge: QR-Code-Erkennung (exakte Übereinstimmung), Trennung, optionale QR-Blattentfernung, optional Scan PDF Cleaner, optional OCRmyPDF. Quelldatei bleibt immer erhalten. Ausgabedateien werden nicht überschrieben. Die automatische Samba-Ordnerüberwachung und Profilanbindung stehen noch aus.

Nach Installation im Testsystem:
```bash
sudo -u qrscan /opt/qrscan/venv/bin/python /opt/qrscan/worker.py \
  /pfad/scan.pdf /pfad/ausgabe --qr-text 'SCAN-TRENNUNG-001' \
  --remove-blank --ocr
```
Nur Pfade verwenden, auf die `qrscan` zugreifen darf. Eine manuelle Testausführung mit passenden Dateirechten ist erforderlich. Für ein behaltenes Trennblatt wird die QR-Seite **als erste Seite des neuen Dokuments** verwendet. Mit `--remove-separators` entfällt sie. Ohne QR-Marker wird eine einzige Ausgabe erzeugt.

**Wichtige Einschränkung:** Die aktuelle Upstream-Funktion `crop_pdf_margins` von Scan PDF Cleaner kürzt einen *festen* Rand (hier 12 pt) und erkennt die tatsächlichen Seitenränder nicht automatisch. `--crop` deshalb erst nach Sichtprüfung verwenden. Die Leerseitenerkennung verwendet derzeit den festen Upstream-Schwellwert 0,5% und behält aus Sicherheitsgründen mindestens eine Seite. Das angekündigte regelbare GUI-Schwellwertfeld und der Vorschaumodus fehlen noch. Keine Eignung für produktive Dokumente ohne Tests.

QR-Decoder ist `pyzbar` mit gerenderten Seiten; das bisher geklonte upstream-PdfQRSplit liegt als Referenz daneben. Grund: dessen QR-Erkennung setzt eingebettete PDF-Bilder voraus und würde nicht alle gerenderten PDF-Formen zuverlässig erfassen.

## Eingangsordner-Überwachung (Schritt 1)

`watcher.py` ist ein eigenständiger **read-only** systemd-Dienst `qrscan-watcher.service`. Er lädt die konfigurierten Eingangsfreigaben aus SQLite und die Pfadzuordnung aus der vom Stirling-Samba-Manager verwalteten Include-Datei. Im Standardintervall von fünf Sekunden prüft er PDFs (nur direkt im jeweiligen Eingangsordner) und protokolliert eine Datei, wenn Größe und Änderungszeitpunkt in drei aufeinanderfolgenden Durchläufen unverändert blieben. **Er verarbeitet, verschiebt oder löscht noch keine PDFs.**

```bash
sudo systemctl status qrscan-watcher --no-pager
sudo journalctl -u qrscan-watcher -f
```

**Zugriffsrechte:** Der eigene Benutzer `qrscan` muss die Eingangspfad-Verzeichnisse lesen und betreten dürfen. Die Installation verändert deren bestehenden Eigentümer/ACLs bewusst nicht. Werden Fehler `Permission denied` oder `Input share not accessible` protokolliert, müssen die betreffenden Pfade und ACLs zunächst für `qrscan` freigegeben werden. Dies ist kein Freigabenmanager und ersetzt die spätere Rechteintegration nicht.

**Offen:** Profile tatsächlich ausführen, Dateistabilität zusätzlich durch Datei-Öffnungs- und PDF-Lesbarkeitstests verifizieren, Dateijobs persistent speichern, Fehler- und Wiederholungsverarbeitung, Integration des vollständigen Samba-Editors.

## Automatische Profil-Verarbeitung (Schritt 2; experimentell)

`qrscan-watcher.service` startet nach Installation den PDF-Worker für neue, ausreichend lange unveränderte Dateien in den gespeicherten Eingangsfreigaben. Der Dienst lädt SQLite-Profile (Eingang, Ausgang, QR-Trennblätter, Leerseiten, Rand, OCR), liest den globalen QR-Text, prüft PDF-Lesbarkeit und legt Ergebnisse in der zugeordneten Ausgangsfreigabe ab. Mindestwartezeit: 30 Sekunden; Pollingintervall: 5 Sekunden. Eingangsdateien bleiben erhalten. Jobs werden in SQLite (`jobs`) mit Status `running`, `done`, `error` protokolliert. Identische Dateien desselben Profils werden nach einem Neustart nicht nochmals verarbeitet.

**Sicherheit und Einschränkungen:** Noch kein vollständiger Integrationstest auf Debian mit Samba-Rechten. Der `qrscan`-Dienstbenutzer braucht Lesezugriff auf Eingänge und Schreibzugriff auf Ausgänge. Bei Fehlern erfolgt derzeit **kein automatischer Retry**, sondern die Fehlerzeile bleibt für spätere Analyse in der Datenbank. Bei Absturz können Einträge auf `running` verbleiben. Das Verhalten bei gleichzeitigem Dateischreiben muss mit echten Scannerdateien geprüft werden. Original-PDFs werden nicht entfernt. Die GUI zeigt Jobstatus noch nicht an. Vor produktivem Einsatz Backup und Test mit Beispieldokumenten durchführen.

Das alte Read-only-Watcher-Verhalten aus Schritt 1 gilt nach diesem Update nicht mehr. Sobald ein geeignetes Profil eingerichtet ist und der Dienst Zugriff hat, wird die PDF-Verarbeitung automatisch angestoßen.

## Punkt 3: Samba-ACL und Fehlerbehandlung

Neues `sync_permissions.py` erteilt dem Dienstbenutzer `qrscan` für **konfigurierte, vom Samba-Manager verwaltete Ordner** die minimal notwendigen ACLs: Eingang `rx`, Ausgang `rwx`. Auch Default-ACLs werden für neue Dateien gesetzt. Vorhandene Dateien und deren Rechte werden **nicht rekursiv verändert**. Der Installer kopiert den Helfer, führt ihn absichtlich nicht ohne bestätigte Profilzuordnung aus.

**Nach dem Anlegen oder Ändern von Profilen** (auf einem Testsystem):

```bash
sudo /opt/qrscan/venv/bin/python /opt/qrscan/sync_permissions.py
sudo systemctl restart qrscan-watcher
sudo journalctl -u qrscan-watcher -n 80 --no-pager
```

Der systemd-Dienst darf nun in `/srv/samba-shares` schreiben, sofern Dateirechte dies ebenfalls gestatten. Ein bloßes `ReadWritePaths` umgeht niemals Unix-/ACL-Rechte.

Fehlerbehandlung: Laufende Jobs werden nach Dienstabbruch als `interrupted` markiert und **nicht automatisch erneut ausgeführt**. Nur vorübergehende Betriebssystem-/I/O-Fehler werden bis zu 3 Mal mit jeweils längerer Wartezeit wiederholt. PDF- oder Dateinamenskonflikte bleiben als Fehler markiert. Originalscans werden nicht gelöscht.

**Noch offen / Testpflicht:** Der ACL-Helfer setzt voraus, dass die Samba-Freigaben bereits verwaltet werden. Auf einer völlig frischen Debian-Installation ohne Samba-Manager müssen wir zuerst die Share-Erstellung integrieren. Keine Tests mit echten SMB-Dateien durchgeführt. Der Scanner muss nach dem Hochladen die PDF schließen; reine Stabilitätszeit ist noch kein garantiertes Übertragungsende. Die GUI besitzt noch keine Auftrags-/Wiederherstellungsansicht.

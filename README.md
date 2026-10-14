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

## Punkt 5: Auftragsübersicht und Fehlerverwaltung

Die Weboberfläche enthält unter `/jobs` eine neue Auftragsübersicht mit Statuszahlen und den letzten 100 Aufträgen. Angezeigt werden Profil, Quelldatei, Zeitpunkt, Anzahl der Versuche und gekürzte Fehlermeldung. Status: `running`, `done`, `retry`, `error`, `interrupted`.

Für `error` und `interrupted` wird eine **manuelle Wiederholungsfreigabe** angeboten. Der Administrator muss vorher bestätigen, dass bereits erzeugte Ausgabedateien und die Fehlerursache geprüft wurden. Danach setzt die GUI den Auftrag auf `retry`; der Watcher nimmt ihn beim nächsten geeigneten Durchlauf wieder auf. Der Worker überschreibt keine vorhandenen Ausgabedateien. Originaldateien bleiben unverändert. Andere Status können nicht manuell zurückgesetzt werden.

Eine frühere Fehlfunktion wurde behoben: `running`-Jobs werden jetzt ausschließlich beim **Start** des Watchers als möglicherweise unterbrochen gekennzeichnet, nicht bei jedem Polling-Durchlauf.

**Noch offen:** Integrationstest auf Debian/Samba, Live-Aktualisierung der GUI, vollständige Ausgabe-/Seiten-Protokollierung und eine sicher verifizierte Wiederaufnahme von teilweise ausgegebenen Dokumenten. Das aktuelle Replay ist daher bewusst konservativ und kann bei bereits vorhandenen Zieldateien scheitern. Dieses Stadium bleibt experimentell.

## Punkt 6 – Installations-Selbsttest (Debian 13)

`selftest.py` überprüft die Python-Syntax, importierbare PDF-/QR-Bibliotheken, OCRmyPDF und Tesseract, `testparm`, SQLite-Schema, Dienstkonto sowie die aktiven Dienste. Der Test verändert keine Scans, Freigaben oder Benutzer.

```bash
git clone https://github.com/Markus4771/PdfQRSplit.git
cd PdfQRSplit
sudo bash install.sh
sudo /opt/qrscan/venv/bin/python /opt/qrscan/selftest.py
sudo journalctl -u qrscan-web -u qrscan-watcher -n 100 --no-pager
```

**Status:** Der Selbsttest ist implementiert, aber noch **nicht auf einem frischen Debian 13 ausgeführt**. Ein Sandbox-Checkout war mangels DNS/Netzwerk nicht möglich. Es gibt keinen Nachweis einer erfolgreichen Komplettinstallation.

**Bekannter Blocker:** Auf einem frischen Debian ist die eigentliche Samba-Freigabenverwaltung noch nicht produktiv integriert. `samba_helper.py` liegt nur als noch nicht freigeschalteter Code vor; das GUI liest weiterhin `/etc/samba/share-manager.conf`, während der neue Helfer `/etc/samba/qrscan-shares.conf` verwenden würde. Diese Schnittstellen müssen vor dem Produktivtest vereinheitlicht und sicher angebunden werden. `selftest.py` meldet fehlende verwaltete Freigaben ausdrücklich. Auch QR-Trennung, Leerseitenerkennung, OCR und Netzwerk-Rechte müssen mit echten PDFs getestet werden.

## Samba-Verwaltung in einer Oberfläche (Integrationsstand)

In `app.py` sind Formulare zum Erstellen, Einstellen der Schreibberechtigung, Passwortwechsel und Entfernen verwalteter Samba-Freigaben implementiert. Ein SMB-Benutzer kann mehrere Freigaben verwenden, sofern beim Anlegen das bisherige Passwort korrekt angegeben wird. Ein Passwortwechsel wirkt für **alle** Freigaben desselben SMB-Benutzers. SMB-Passwörter werden nicht in SQLite gespeichert. Entfernen einer Freigabe entfernt nur den Samba-Eintrag; Dateien und Benutzer bleiben erhalten. Freigaben, die noch in einem PDF-Profil verwendet werden, können nicht über das GUI entfernt werden.

`install.sh` richtet `/etc/samba/qrscan-shares.conf` als separate Include-Datei ein, erzeugt eine Sicherung der ursprünglichen `smb.conf`, installiert den Root-Helfer unter `/usr/local/lib/qrscan/samba_helper.py` sowie eine eingeschränkte sudoers-Regel für den Dienstbenutzer. GUI, Watcher, ACL-Helfer und Selbsttest verwenden dieselbe Samba-Konfiguration. Bestehende Stirling-Freigaben werden nicht direkt verändert.

**Unbedingt beachten:** Keine vollständige Debian-13-Installation und kein Live-SMB-Test durchgeführt. Das Projekt benötigt einen Testlauf mit zwei Shares und gleichem Benutzer, Passwortwechsel, Windows-Anmeldung, ACL-Prüfung und einem PDF-End-to-End-Test. Die GUI verwendet HTTP Basic Auth: Port 8086 nur in isolierten Administrationsnetzen oder mit vorgeschaltetem TLS verwenden.

## Erweiterte Profilbearbeitung (Punkt 2)

Bestehende Profile sind jetzt direkt in der Weboberfläche bearbeitbar: Name, Samba-Eingang/-Ausgang, QR-Trennung, QR-Trennblatt entfernen, Leerseiten, Randbeschneidung und OCR. Zusätzlich je Profil: Leerseiten-Schwellwert (0–2 %), Sprache Deutsch/Englisch/beide, PDF oder PDF/A, OCR-Rotation und Entzerrung (Deskew). Neue Profile bekommen zunächst Standardwerte und können danach bearbeitet werden. Bestehende SQLite-Datenbanken werden beim Start automatisch um neue Spalten ergänzt. Watcher und Worker lesen die Werte für neue Jobs. Bereits laufende Jobs ändern sich dadurch nicht.

**Noch zu testen:** Live-Installation auf Debian 13; insbesondere das OCRmyPDF-PDF/A-Verhalten und schwach bedruckte Seiten. Auf bestehenden Installationen bei Updates vorher SQLite sichern. Die Einstellung *Ränder beschneiden* verwendet weiterhin einen festen Beschnitt und ist keine automatische Inhaltserkennung.

## Punkt 3 – Absicherung der PDF-Verarbeitung (13.10.2026)

- `watcher.py` sperrt einen zweiten parallelen Überwachungsprozess per Linux-`flock`.
- Neue PDF-Aufträge werden anhand von Profil, **Quellpfad und Dateiinhalt** identifiziert; gleiche Inhalte unter verschiedenen Dateinamen werden nicht mehr versehentlich zusammengefasst.
- Vor der Verarbeitung wird eine private Kopie der Quelldatei erstellt und mit der Quelle verglichen. Ändert der Scanner die Quelldatei dabei, schlägt der Auftrag sicher fehl. Originale bleiben erhalten.
- `safe_publish.py` veröffentlicht fertige Dateien über dateisysteminterne Hardlinks ohne Überschreiben vorhandener Zieldateien. Ausgaben sind erst nach vollständigem Staging sichtbar; bei gewöhnlichen Fehlern werden die in diesem Durchlauf bereits publizierten Dateien zurückgenommen.
- `test_safe_publish.py` enthält Regressionstests für erfolgreiches Veröffentlichen, Nichtüberschreiben und das Abweisen leerer Ausgaben.

Tests (auf dem späteren Debian-System):
```bash
cd /opt/qrscan
/opt/qrscan/venv/bin/python -m unittest -v test_safe_publish
```

**Grenzen:** Bei Stromausfall während der Veröffentlichung kann bereits eine Teilmenge fertiger Dokumente im Ziel liegen. Der Auftrag wird beim Neustart als unterbrochen markiert und muss kontrolliert geprüft werden; die Ausgaben werden nicht automatisch überschrieben. Die Dateistabilitätsprüfung ist keine verbindliche Scanner-Upload-Abschlussmeldung. Hardlinks erfordern einen lokal kompatiblen Ziel-Dateisystemtyp und eine gemeinsame Partition für die temporären und finalen Ausgaben. **Noch kein vollständiger Debian-13-Livetest.**

## Punkt 4 – Debian-13-Testvorbereitung

GitHub Actions Workflow `.github/workflows/debian13.yml` prüft bei Push/Pull Request in einem `debian:13`-Container `bash -n install.sh`, Python-Syntax aller Hauptmodule und die nichtdestruktiven Veröffentlichungs-Regressionstests. Er installiert **nicht** Samba als aktiven Dienst und ist kein vollständiger End-to-End-Test. Den Workflow-Status in GitHub Actions kontrollieren; er wurde nach Erstellung noch nicht als erfolgreich bestätigt.

Auf einem frischen Debian erzeugt `install.sh` jetzt zusätzlich `/srv/samba-shares`, prüft beide systemd-Dienste und startet die PDF-Ausgabetests.

**Vor Freigabe für den Produktivbetrieb auf Test-VM durchführen:** Installer, Startpasswortwechsel, SMB-Share-Anlage, SMB-Zugriff mit zwei Shares/einem Benutzer, Passwortwechsel, Leseschreibrechte, Scanner-Upload, QR-Trennung, Leerseiten, OCR und Überwachung von Fehler-/Neustartzuständen. Der aktuell laufende Entwicklungscontainer ist Debian 13; dort ist GitHub wegen DNS-Auflösung nicht erreichbar. Daher wurde **keine erfolgreiche vollständige Testinstallation** nachgewiesen.

## Samba-Verwaltungsdienst (Oktober 2026)

Die Web-GUI führt den privilegierten Helfer **nicht mehr über sudo** aus. Der separate Dienst `qrscan-samba.service` läuft als root, prüft den lokalen aufrufenden Benutzer über Unix-Socket-Peer-Credentials und akzeptiert nur festgelegte Samba-Verwaltungsaktionen über `/run/qrscan/samba.sock`. `qrscan-web.service` bleibt mit `NoNewPrivileges=yes` und `ProtectSystem=strict` abgesichert. Der Installer entfernt die alte sudoers-Regel und startet den zusätzlichen Dienst. Rechte werden nicht global gelockert. Upgrade:

```bash
cd /root/PdfQRSplit
git pull --ff-only
bash install.sh
systemctl status qrscan-samba qrscan-web --no-pager
```

Noch auf Debian 13 zu prüfen: Samba-Benutzer erstellen, Anmeldung, Dateirechte, Passwortwechsel und Bearbeitung über das Web. Keine bestehenden PDFs werden gelöscht.

## Zwei Samba-Freigaben mit demselben Benutzer

Beim Anlegen einer weiteren Freigabe denselben SMB-Benutzer und dessen vorhandenes Passwort eingeben. Die Passwortprüfung verwendet nun echte Zeilenumbrüche in der geschützten `smbclient`-Anmeldedatei. Bei bereits vorhandenen Freigaben im Abschnitt „Samba-Freigaben“ den gewünschten Freigabeneintrag bearbeiten: im Feld „Auf vorhandenen SMB-Benutzer umstellen“ den Benutzer der ersten Freigabe und im Passwortfeld dessen Passwort eintragen und speichern. Der alte SMB-Benutzer wird nicht gelöscht. **Wichtig:** Ein Samba-Passwort gehört zum Benutzer, nicht zu einer einzelnen Freigabe; ein Passwortwechsel betrifft alle Freigaben dieses Benutzers. Die Formulare übertragen Passwörter derzeit über die Webverbindung; nur im geschützten Testnetz verwenden und TLS vor Produktivbetrieb ergänzen.

## QR-Trennung diagnostizieren (Praxisbefund vom 13.10.2026)

Im Praxisprotokoll wurden 20 PDF-Testdateien vom Profil `Test` in `Eingabe-Test` verarbeitet, aber für jede Datei nur **ein** Ergebnis ausgegeben. In SQLite wurde `qr_split=1` und der QR-Text `SCAN-TRENNUNG-001` nachgewiesen. Noch ist **nicht bewiesen**, ob der QR-Inhalt in den PDFs abweicht oder die QR-Erkennung fehlschlägt.

Das neue Nur-Leseprogramm zeigt QR-Inhalte und Seitenzahlen ohne Dokumente zu verändern:

```bash
/opt/qrscan/venv/bin/python /opt/qrscan/diagnose_qr.py \
  /srv/samba-shares/Eingabe-Test/01_standard_3_teile.pdf \
  --qr-text 'SCAN-TRENNUNG-001'
```

Achtung: QR-Inhalte können vertrauliche Daten enthalten; Ausgabe nicht ungeprüft öffentlich teilen. Für die Diagnose nicht nochmals die bereits verarbeiteten Dateien im Eingang neu anstoßen; vorhandene Ausgabe-Dateinamen würden sonst kollidieren.

## Verarbeitung manuell wiederholen und fremde QR-Codes

In der Web-GUI unter **Aufträge & Fehler** hat jeder abgeschlossene, fehlgeschlagene oder unterbrochene Auftrag den Button **Verarbeitung wiederholen**. Nach Bestätigung legt der Watcher neue Ergebnisse mit dem Namenszusatz `_wiederholung_<hash>_<nummer>` an; vorhandene Ausgabedateien und Eingangsdateien bleiben erhalten. Für dieselbe Quelldatei sind mehrere manuelle Wiederholungen möglich. `jobs.replay_count` wird automatisch bei der Installation bzw. beim ersten Aufruf der Auftragsverwaltung in SQLite ergänzt.

Die QR-Trennung prüft bereits jeden dekodierten QR-Code auf **exakte Übereinstimmung** mit dem konfigurierten Text (aktuell `SCAN-TRENNUNG-001`). Alle anderen QR-Codes lösen keine Dokumenttrennung aus; ihre Seiten werden normal weiterverarbeitet. Falls kein passender QR-Code gefunden wird, erfolgt keine QR-Aufteilung; andere aktivierte Schritte wie OCR laufen weiter. Nur tatsächliche Fehler bei der PDF-Bearbeitung lassen den Auftrag fehlschlagen.

Update: `git pull --ff-only && bash install.sh` im Repositoryverzeichnis. Änderungen an der Datenbank sind automatisch und erhalten bestehende Aufträge. Verhalten auf dem Zielsystem praktisch testen.

Update 13.10.2026: Der Button **Verarbeitung wiederholen** startet mit einem Klick unmittelbar die Wiederholungsanforderung; die zusätzliche Bestätigungs-Checkbox wurde entfernt. Der laufende Watcher verarbeitet den Auftrag im nächsten Durchlauf automatisch. Ausgabedateien bleiben geschützt und bekommen eindeutige Wiederholungsnamen.

## Automatische Wiederholungen bei vorübergehenden Fehlern

Seit Oktober 2026 versucht der Watcher bei bestimmten **vorübergehenden technischen Fehlern** eine Verarbeitung selbstständig erneut, insgesamt höchstens **fünf Verarbeitungsversuche** (einschließlich Erstversuch). Wartezeiten nach Fehlschlägen: **1, 2, 5 und 10 Minuten**. Status `retry` und Zeitpunkt des nächsten Versuchs erscheinen in der Auftragsübersicht; nach Erreichen des Limits wird `error` angezeigt. Fehler wie bestehende Ausgabedateien, Zugriffsverweigerung oder ungültige Dokumentdaten lösen **keine** Endlosschleife aus. Die Wiederholung benötigt eine noch vorhandene, unveränderte Eingangsdatei. Für manuell wiederholte Aufträge bleibt bei späteren automatischen Versuchen der separate Wiederholungsname erhalten.

Ein QR-Code, der **nicht exakt** dem eingestellten Trenntext entspricht, ist **kein Fehler**: Er wird für die Trennung ignoriert, und die übrigen aktivierten Verarbeitungsschritte laufen weiter. Nach erfolgreicher Verarbeitung erfolgt keine automatische Wiederholung.

Update:
```bash
cd /root/PdfQRSplit
git pull --ff-only
bash install.sh
systemctl status qrscan-watcher --no-pager
```

## Korrektur der manuellen Wiederholung bei vorhandenen Ausgaben

Diagnose: Aufträge mit `replay_count=0` scheiterten mit `Ausgabedatei bereits vorhanden: *_0001.pdf`, während manuelle Wiederholungen mit `replay_count>0` erfolgreich waren. Neu: `output_naming.py` verwendet bei der **ersten** Verarbeitung den Originalnamen nur, wenn `<name>_0001.pdf` noch nicht existiert; anderenfalls erstellt der Watcher einen eindeutigen Ausgabestamm `<name>_neu_<12-stelliger-Dateihash>`. Ein manueller Klick nutzt weiterhin `<name>_wiederholung_<hash>_<laufende Nummer>`. Vorhandene Dateien bleiben unangetastet; falls auch der alternative Name existiert, meldet die Verarbeitung weiterhin einen sicheren Konflikt statt zu überschreiben. Bereits als `error` eingetragene Altaufträge können in **Aufträge & Fehler** mit dem vorhandenen Button erneut angestoßen werden. Eine automatische Endlosschleife entsteht nicht. `test_output_naming.py` läuft mit den Installer-Tests.

## Auftragsübersicht und automatische Datenbankpflege

Unter **Aufträge & Fehler** werden bei abgeschlossenen Aufträgen fehlende Ausgabedateien als **Ausgabe fehlt** (mit Anzahl) angezeigt und fehlende Eingangsdateien als **Quelle fehlt**. Ohne Eingangsdatei ist der Wiederholen-Button ausgeblendet. Alte Aufträge behalten ihre Statusdaten; bisherige Ausgabelisten aus Python-Dictionary-Strings sowie neue JSON-Ausgabelisten werden unterstützt. Bei nicht parsebaren älteren Fehlerdetails wird kein Ausgabestatus behauptet.

Die Aufbewahrung der Auftragsdatenbank ist standardmäßig **90 Tage**, über ein Zahlenfeld auf der Auftragsseite zwischen **7 und 3650 Tagen** einstellbar. Der Watcher bereinigt höchstens stündlich nur ältere abgeschlossene, fehlerhafte oder unterbrochene Aufträge. **Keine Original- oder Ausgabedatei wird dabei gelöscht.** Damit unverändert im Eingang verbliebene PDFs durch das Löschen der Jobzeile nicht versehentlich neu verarbeitet werden, wird deren Dateifingerabdruck dauerhaft in der schlanken Tabelle `archived_signatures` bewahrt. Die Statuszeile ist nach dem Bereinigen aus der Übersicht verschwunden; für eine erneute Verarbeitung muss sich die Datei ändern oder erneut als neuer Auftrag eingebracht werden. Die archivierten Fingerabdrücke sind absichtlich von der automatischen Aufbewahrung ausgenommen.

Upgrade im Projektverzeichnis: `git pull --ff-only && bash install.sh`. Die Installation führt auch `test_job_maintenance.py` aus. Die Änderungen müssen noch auf dem Zielserver praktisch geprüft werden.

## DATEV-Sicherheitsmodus ohne Windows-Agent (Vorstufe, Testbetrieb)

Pro Profil kann **DATEV-Sicherheitsmodus** aktiviert werden. Dafür ist eine **eigene exklusive, möglichst leere Samba-Ausgangsfreigabe** erforderlich. QR-Trennung und Entfernung der Trennseiten müssen aktiv sein. Der Worker bildet nach der Trennung **für jede einzelne ausgegebene Rechnung** einen SHA-256 der fertigen PDF-Bytes. Unter `/var/lib/qrscan/datev.sqlite3` wird der Hash in einem **dauerhaften separaten Register** reserviert, bevor die vollständige PDF mit einem nicht überschreibenden Hardlink in den DATEV-Übergabeordner gelangt. Der DATEV-Ausgabename lautet `beleg_<sha256>.pdf`; identische PDF-Bytes können auch nach manueller Wiederholung oder nach Löschung aus der Übergabefreigabe **nicht erneut freigegeben** werden. Das Register wird NICHT durch die normale Auftragsbereinigung gelöscht. Bei unklaren Absturz-/IO-Zuständen bleibt die Reservierung zur manuellen Prüfung erhalten (*fail closed*); automatische Wiederfreigabe ist gesperrt. Mehrseitige PDFs ohne gültigen QR-Trenncode werden im DATEV-Modus zurückgehalten.

**Grenzen:** Erneutes Scannen derselben Papierrechnung kann andere PDF-Bytes erzeugen; dieser Modus erkennt nur byte-identische PDFs sicher. Es gibt noch keine visuelle/OCR-basierte Dublettenprüfung und keine DATEV-Quittung bzw. Zuordnung einer Übertragung. Außerdem verhindern die PDF-Register nicht, dass DATEV Belegtransfer selbst mehrfach aufnimmt oder Menschen Dateien manuell in den Ordner kopieren. DATEV-Ziel daher auf einen zuständigen Übertragungs-PC begrenzen und Samba-Schreibrechte auf das erforderliche Minimum reduzieren. Der Windows-PC darf `datev.sqlite3` keinesfalls ändern. Für zuverlässige Freigabe eines produktiven DATEV-Ordners müssen Wiederanlauf, Rechte, Sicherung und Offline-Dublettentests praktisch geprüft werden. **Vor Abschluss dieser Tests keine produktive DATEV-Überwachung des Zielordners aktivieren.**

Update: `cd /root/PdfQRSplit && git pull --ff-only && bash install.sh`. Der Installer erhält die bestehende Profil- und DATEV-Registerdatenbank. Neue Tests: `test_datev_handoff.py`.

## Fluent Bit auf dem Debian-Scan-Server (Staging)

Der Installer `install.sh` ruft `install_fluent_bit.sh` auf. Es installiert Fluent Bit aus dem offiziellen Debian-Paket-Repository und startet den getrennten Dienst `qrscan-fluent-bit.service` unter `qrscan-logs`. Der Listener ist auf `127.0.0.1:24224` begrenzt, die Konfiguration liegt unter `/etc/qrscan/fluent-bit.conf`. Der vorläufige Null-Ausgang verwirft Testereignisse: Es gibt noch keine persistente DATEV-Protokollsammlung oder Windows-PC-Anbindung. Externe Verbindungen erst nach TLS mit Client-Authentifizierung und Prüfung der tatsächlichen DATEV-Protokolle aktivieren. Betrieb auf Debian noch nicht praktisch getestet.

## Bildbasierte DATEV-Dublettenprüfung (Oktober 2026)

Im aktivierten DATEV-Profil berechnet das neue Modul `datev_visual.py` je PDF-Seite einen visuellen Fingerabdruck (normalisiertes Graustufenbild, 256-Bit-Differenzhash). Der Übergabedienst `datev_handoff.py` vergleicht alle Seiten eines Belegs mit bereits registrierten und zurückgehaltenen Belegen gleicher Seitenzahl. Ähnliche Scans werden als **DATEV-Dublettenverdacht** in der dauerhaften Tabelle `datev_suspects` registriert, **nicht an DATEV freigegeben**, und als Fehler im Auftrag angezeigt. Identische PDF-Bytes bleiben zusätzlich durch SHA-256 gesperrt. Ein erneutes Scannen kann sich auch bei verändertem PDF-Dateihash visuell ähneln.

WICHTIG: Dies ist eine **vorsichtige Verdachtsprüfung, keine zuverlässige Rechnungsidentifikation**. Andere Rechnungen mit ähnlichem Seitenlayout können fälschlich zurückgehalten werden; dieselbe Rechnung kann bei starken Scanänderungen übersehen werden. Ein automatischer Freigabeknopf ist absichtlich noch nicht vorhanden. Die Quelldatei bleibt zur manuellen Klärung erhalten. Vor produktivem DATEV-Betrieb mit verschiedenen echten Belegen kalibrieren und zusätzlich Rechnungsnummer, Aussteller und Rechnungsdatum per OCR in die Prüfung aufnehmen. Dies ist keine Bestätigung eines DATEV-Uploads. Bestehende alte DATEV-Registereinträge ohne Bildhash können nur über SHA-256 geprüft werden; es findet keine automatische rückwirkende Bildanalyse statt.

Update: `git pull --ff-only && bash install.sh`. Neue Regressionstests `test_datev_visual.py` und aktualisierte `test_datev_handoff.py`. Produktivfreigabe steht weiter aus.

## DATEV-Prüfbereich für verdächtige Rechnungen

Bei bildbasiertem Dublettenverdacht wird jetzt die **fertig getrennte einzelne Rechnungs-PDF** dauerhaft und nicht überschreibend unter `/var/lib/qrscan/datev-review/verdacht_<sha256>.pdf` gespeichert. Der Ordner ist nur für `qrscan` zugänglich (0700) und **nicht Bestandteil der DATEV-Übergabe-Samba-Freigabe**. Die Original-Scan-PDF bleibt unverändert im Eingang. Der Verdacht steht im Register `datev_suspects` samt `review_path`, erscheint als Fehler im Auftrag und ist unter **/datev-review** (Link aus Aufträge & Fehler) einsehbar. Die Seite zeigt Metadaten und Speicherort, nicht den PDF-Inhalt und hat absichtlich **keine direkte Freigabe nach DATEV**. Die normale 90-Tage-Bereinigung betrifft das DATEV-Register und die Prüfdateien nicht. Fehlalarme müssen durch eine berechtigte Person außerhalb des Uploadprozesses geprüft werden; diese Version enthält noch keinen revisionssicheren Freigabe-Workflow. Bei Tests keine aktive DATEV-Überwachung des Übergabeordners einschalten.

## DATEV-Samba-Freigabe absichern: Nur-Lese-Zugriff von Windows

Die DATEV-Übergabe-Samba-Freigabe muss explizit als **DATEV geschützt** markiert sein. Entweder beim Anlegen der Freigabe die Checkbox **„DATEV-Übergabe: Windows nur lesen“** aktivieren oder bei einer bestehenden Freigabe in der Web-GUI auf **„Als DATEV-Übergabe schützen (Windows nur lesen)“** klicken. Letzteres schaltet vorhandene Freigaben bewusst nur auf schreibgeschützt um; es löscht keine PDFs. Der Manager schreibt hierfür `read only = yes`, `comment = QRSCAN-DATEV-READONLY`, `veto files = /qrscan-*/`, `hide unreadable = yes` in die verwaltete Samba-Konfiguration und lädt Samba neu. Die gewöhnliche Freigabe-Bearbeitung kann bei DATEV-Freigaben `read only` nicht wieder abschalten. Der Linux-Dienst `qrscan` behält lokalen Schreibzugriff auf den DATEV-Zielordner, sodass nur die Freigabe für die Windows-Clients schreibgeschützt ist.

DATEV-Profile lassen sich nur mit einer entsprechend markierten Freigabe anlegen/aktivieren; der Watcher prüft die Markierung und `read only = yes` bei jedem Verarbeitungsdurchlauf nochmals und blockiert ohne diese Voraussetzungen die DATEV-Übergabe. Bereits vorhandene normale Scan-Freigaben werden beim Update **nicht automatisch umgestellt**. Der DATEV-Ausgang muss exklusiv einem DATEV-Profil zugeordnet sein; andere Profile dürfen nicht dorthin schreiben.

**Wichtige Grenzen:** Die Regel beschränkt SMB-Zugriff; sie schützt nicht gegen berechtigte Linux-Root-Nutzer, lokalen `qrscan`-Code oder Programme, die außerhalb der DATEV-Samba-Freigabe auf denselben Ordner zugreifen. Für Windows-Datev-Belegtransfer muss praktisch getestet werden, ob reiner Lesezugriff mit dessen Ablage-/Löschverhalten kompatibel ist. Vor Produktivbetrieb prüfen: `testparm -s`, `smbclient` Lesetest und expliziter **fehlgeschlagener** Schreib-/Löschtest mit dem DATEV-SMB-Konto. Den DATEV-Ordner nur einem zuständigen DATEV-Belegtransfer-PC zuweisen.

## Samba-Warnungen: globale Parameter in Freigabeabschnitten

Wenn `testparm -s` Meldungen wie `Global parameter workgroup found in service section!` ausgibt, liegt die PdfQRSplit-`include`-Direktive möglicherweise zu früh in `/etc/samba/smb.conf`. Seit dem Fix verschiebt `install.sh` ausschließlich die aktive Direktive `include = /etc/samba/qrscan-shares.conf` hinter sämtliche bereits vorhandenen Samba-Abschnitte. Das erfolgt idempotent mit Zeitstempel-Backup `/etc/samba/smb.conf.bak-qrscan-YYYYMMDD-HHMMSS`, Validierung per `testparm -s <temporäre-Datei>` und atomarer Übernahme. Bei ungültiger Konfiguration wird die originale `smb.conf` nicht verändert. Vorhandene Share-Definitionen, SMB-Zugangsdaten und PDFs werden nicht geändert. Nach `git pull --ff-only && bash install.sh`: `testparm -s` ausführen und kontrollieren, dass die Global-Parameter-Warnungen verschwunden sind.

**Korrektur 14.10.2026:** Der QRSCAN-Samba-`include` muss **als letzte Direktive in `[global]` unmittelbar vor dem ersten Freigabeabschnitt** stehen. Eine Position am Dateiende würde Samba die Direktive fälschlich der letzten Freigabe `[print$]` zuordnen. `install.sh` korrigiert dies mit vorherigem Zeitstempel-Backup und `testparm`-Prüfung. Nach dem Update `testparm -s` erneut ausführen: `include` muss unter `[global]`, nicht unter `[print$]` erscheinen.

## DATEV-Profil: Samba-Schreibschutz beim Speichern automatisch aktivieren (14.10.2026)

Wenn beim Anlegen oder Ändern eines Profils der DATEV-Sicherheitsmodus gewählt ist, prüft `app.py` die ausgewählte Ausgangsfreigabe über den lokalen Samba-Manager. Eine bislang ungeschützte Freigabe wird nun beim Speichern über die Aktion `protect-datev` automatisch auf SMB-Nur-Lesezugriff gesetzt. Bei Fehlern erscheint die konkrete Antwort des Managers; statt der früheren pauschalen Meldung `DATEV-Ausgang muss eine geschützte, schreibgeschützte Samba-Freigabe sein`. **Achtung:** Dies ändert die Rechte der ausdrücklich ausgewählten Ausgangsfreigabe und kann bestehende Windows-Schreibzugriffe unterbrechen. Daher eine **eigene DATEV-Ausgangsfreigabe** auswählen, nicht die allgemeinen Test- oder Scan-Freigaben. Serverprozess `qrscan` darf weiterhin lokal schreiben. Nach Update `git pull --ff-only && bash install.sh` ausführen, DATEV-Profil speichern und `testparm -s` sowie Windows-Lese-/Schreibtests prüfen. Änderung auf Zielserver noch nicht praktisch bestätigt.

## DATEV: QR-Trennblätter optional behalten

Im DATEV-Sicherheitsmodus bleibt **QR-Code-Trennung verpflichtend**, aber das Kontrollkästchen **QR-Trennblätter entfernen** ist nun optional. Bei deaktivierter Entfernung wird das QR-Trennblatt jeweils an den Anfang des nachfolgenden Einzelbelegs übernommen (entsprechend der bestehenden Trennlogik). Es wird nicht als separates Dokument ausgegeben, sofern das Trennblatt vor den Rechnungsseiten liegt. DATEV-Dublettenprüfung und Übergaberegister prüfen weiterhin die fertige Einzel-PDF inklusive eventuell enthaltener QR-Seite. **Achtung:** Das kann die bildbasierte Dublettenerkennung beeinflussen, insbesondere wenn verschiedene Rechnungen identische Trennblätter haben. Vor DATEV-Produktiveinsatz mit echten Belegen testen, ob die Trennblätter für DATEV inhaltlich akzeptabel sind. `app.py` fordert beim Anlegen/Ändern des DATEV-Profils nur noch QR-Trennung.

## Originalscans nach erfolgreicher DATEV-Verarbeitung archivieren

Für **DATEV-Profile mit exklusiver Eingangsfreigabe** wird die ursprüngliche, ungetrennte Scanner-PDF nach vollständig erfolgreicher Verarbeitung aus dem Eingang in ein **privates Originalarchiv** übernommen: `/var/lib/qrscan/original-archive/`. Der Scanner bewahrt das Original nicht im DATEV-Ausgang auf. Der Archivdateiname enthält den originalen Basisnamen und den SHA-256-Hash. Vor dem Bereinigen des Eingangs wird eine neue Archivkopie verifiziert (SHA-256, Dateizustand) und synchronisiert, anschließend der abgeschlossene Auftrag mit Archivpfad in SQLite gespeichert und erst dann das unveränderte Original aus dem Eingang gelöscht. Ein vorhandener identischer Archivbeleg wird nicht überschrieben. Bei Archivierungsfehlern bleibt das Original im Eingang. Bei einem fehlgeschlagenen DATEV-Auftrag oder Dublettenverdacht erfolgt **keine** Originalbereinigung; die bisherige separate `datev-review` bleibt bestehen. Wird dieselbe Eingangfreigabe von mehreren Profilen genutzt, findet sicherheitshalber keine automatische Originalarchivierung statt. Die normalen Nicht-DATEV-Profile behalten ihr altes Verhalten.

ACHTUNG: Die Archivkopie enthält die ursprüngliche Scan-PDF; normale Job-History-Bereinigung entfernt sie nicht. Nur dem lokalen Dienst `qrscan` zugänglich (Ordner 0700, neue Dateien 0600). Archiv muss in PBS-Backup aufgenommen werden. Bei einem plötzlichen Systemabsturz nach Anlage der Archivkopie, aber vor dem Entfernen aus dem Eingang, können **beide Kopien** bestehen bleiben – das ist absichtlich sicherer als Datenverlust. Neue Originale im Eingang werden nicht automatisch rückwirkend archiviert, wenn ihr alter Auftrag bereits als erledigt registriert ist. `test_original_archive.py` enthält Sicherheitsprüfungen. Produktivtests stehen aus.

## Original-Archiv als eigene Samba-Freigabe im Profil auswählen (14.10.2026)

DATEV-Verarbeitungsprofile besitzen jetzt zusätzlich **Original-Archiv (separate Samba-Freigabe)**. Neue und vorhandene Profile können dort eine vorher im Samba-Manager erstellte Freigabe (z. B. `Datev-Archiv`) auswählen. Leer = bisheriges internes `/var/lib/qrscan/original-archive/`. Die Datenbankspalte `profiles.archive_share` wird automatisch nachgerüstet. Ein ausgewähltes Archiv muss von Eingangs- und DATEV-Ausgangsfreigabe verschieden und exklusiv sein; es darf nicht bereits als Eingangs-, Ausgangs- oder Archivfreigabe eines anderen Profils verwendet werden. Die Web-GUI aktiviert für Archivfreigaben automatisch Samba-`read only = yes` (Windows darf lesen, aber nicht schreiben/löschen); der Debian-Dienst `qrscan` kann lokal archivieren. Die Dateiberechtigungen des bestehenden Samba-Archivordners werden beim Archivieren **nicht** verändert. Der Watcher prüft den Freigabenamen und lokale Schreibrechte vor der Verarbeitung. Archive werden SHA-256-geprüft; erst nach erfolgreichem DATEV-Auftrag und nach Speicherung des Archivpfads wird das unveränderte Eingangsoriginal entfernt. Fehler/Dublettenverdacht belassen das Original im Eingang. Existierende historische interne Archivdateien werden nicht automatisch verschoben. Belegtransfer nur auf die DATEV-Ausgangsfreigabe konfigurieren, nicht auf das Archiv. Nach Update `git pull --ff-only && bash install.sh` zuerst separate Freigabe in der GUI anlegen, dann im DATEV-Profil als Archiv auswählen. Prüfung auf Debian/Windows steht noch aus.

## Fehlerbehebung: DATEV-Profil trotz aktivierter QR-Trennung abgelehnt

Nach Hinzufügen der Archivfreigabe verwendete `app.py` bei der Profilaktualisierung irrtümlich falsche Indizes im von `profile_settings.check()` zurückgegebenen Tupel. Das führte zu der Meldung `DATEV-Modus erfordert QR-Trennung`, obwohl QR-Trennung aktiviert war. Die Indizes für `qr_split` (3), `datev_mode` (13) und `archive_share` (14) sind korrigiert. Separates Originalarchiv wählen; `Ausgang-Test` ist keine empfohlene Archivfreigabe. Update: `git pull --ff-only && bash install.sh`.

## DATEV-Profil QR-Prüfung: Diagnose (14.10.2026)

Bei Profiländerungen prüft `app.py` nun unmittelbar die übermittelten Formularfelder `qr_split` und `datev_mode`, statt Tupelindizes zu verwenden. Wenn trotz aktivierter QR-Code-Trennung eine Fehlermeldung erscheint, `/opt/qrscan/app.py` auf dem Zielsystem aktualisieren und `qrscan-web` neu starten (via `git pull --ff-only && bash install.sh`). Die neue Fehlermeldung zeigt explizit `qr_split=aus, datev_mode=an`, wenn der Server die QR-Checkbox nicht erhält. QR-Trennblätter entfernen bleibt optional.

## Fluent-Bit-Paketserver: Debian Trixie Packages.bz2 Prüfsummenfehler (14.10.2026)

Wenn `apt-get update` beim Fluent-Bit-Repository `packages.fluentbit.io/debian/trixie` mit `Datei hat eine unerwartete Größe` abbricht, handelt es sich um einen inkonsistent bereitgestellten Paketindex (APT blockiert die unsichere Quelle). **Nicht** `[trusted=yes]`, unsichere Repositories oder APT-Signatur-/Hash-Prüfungen abschalten. `install.sh` probiert dann bei vorhandenem Fluent-Bit-Repository das Update ohne diese Paketquelle erneut. Scheitert die optionale Fluent-Bit-Installation selbst, wird die Quelle als `fluent-bit.list.disabled` deaktiviert, während die Hauptinstallation fertiglaufen kann. Fluent Bit ist vorerst nur eine optionale lokale Staging-Komponente ohne Windows-Verbindungen oder DATEV-Logauswertung. Sobald der Paketserver wieder gültige Daten liefert, kann die Installation mit `bash install.sh` wiederholt werden.

Nach dem Update kontrollieren: `grep -n 'Übermittelt: qr_split' /opt/qrscan/app.py`, `systemctl is-active qrscan-web qrscan-watcher`, und ob DATEV-Profile gespeichert werden können. Ein älterer Webprozess wird bei Installer-Neustart neu geladen.

## Firmen- und SMB-Benutzerverwaltung (14.10.2026)

Neu: Web-GUI **/companies**, erreichbar über „Firmen & Benutzer“. Firmen mit eigener Kennung (bis 12 Zeichen) und Firmennamen anlegen. Standard-DATEV-Belegarten als Checkboxen: Rechnungseingang, Rechnungsausgang, Kasse, Sonstige, OhneBelegtyp. Eigene Belegarten sind in dieser ersten Version noch nicht implementiert. Jeder gewählte Belegtyp erhält nach **explizitem** Klick auf Freigaben anlegen / Rechte synchronisieren vier getrennte Freigaben `FIRMA-BELEGART-Eingang`, `-Archiv`, `-Ausgang`, `-LOG`. Achtung: Die bisherige 40-Zeichen-Grenze wird vor dem Anlegen geprüft.

Samba-Benutzer in der Firmenverwaltung neu anlegen (mindestens 12 Zeichen Passwort) oder vorhandene verwaltete Samba-Benutzer nach Passwortprüfung registrieren. Danach pro Firma Benutzerrolle wählen: kein Zugriff, nur lesen, nur Eingang schreiben, Eingänge lesen/schreiben, Administrator (Eingänge schreiben; sonst nur lesen). Samba setzt `valid users` plus `write list` bei global `read only = yes` um: Nur Eingangs-Freigaben bekommen Schreibberechtigungen. Archiv/Ausgang/LOG bleiben für Windows schreibgeschützt. Neue Freigaben sind mit `QRSCAN-COMPANY-MANAGED` gekennzeichnet; die alte Freigabenmaske darf diese nicht ändern/löschen. Existierende Freigaben und Profile werden nicht migriert oder gelöscht. Diese erste Ausbaustufe legt **nur** Firmen, Zuordnungen, User und Samba-Freigaben an: Sie generiert **noch keine** PDF-Verarbeitungsprofile, DATEV-Mandantenkonfigurationen, per-Belegart QR-Texte oder DATEV-Belegtransfer-Konfiguration auf Windows. Nach erfolgreichem Einrichten müssen DATEV-Ausgang und Archiv in einem Verarbeitungsprofil zugeordnet werden. Niemals denselben DATEV-Belegtransfer-Eingang als Archiv verwenden.

Installation: `cd /root/PdfQRSplit && git pull --ff-only && bash install.sh`. Das Installationsskript prüft Python-Syntax und führt `test_company_admin` aus. Neue Tabellen in der bestehenden `profiles.sqlite3` werden beim Webstart angelegt, alte Tabellen/Dateien bleiben bestehen. Vor dem Test PBS-Sicherung empfehlen. Keine Live-Integrationstests auf dem Debian-Samba-Zielserver erfolgt.

## 14.10.2026 – Firmenübersicht sichtbar vor Formularen

Nutzer meldete: `companies` SQLite enthält Firmen `Test` und `Juhu`, aber die GUI scheint sie nicht anzuzeigen. `company_admin.render` gibt nun **zuerst** die Übersicht mit Anzahl und Sprunglinks auf jede Firma sowie die einzelnen Firmenkarten mit Belegarten/Berechtigungen aus; Formulare für neue Firmen und SMB-Konten kommen danach. Datenbank wird dabei nicht verändert. Nach `git pull --ff-only && bash install.sh` Seite `/companies` mit Strg+F5 laden. Keine bestehende Firma neu anlegen.

## Mehrfachauswahl der Firmenbenutzer und geschützte Löschvorgänge (14.10.2026)

Auf `/companies` zeigt jede Firma jetzt die registrierten SMB-Benutzer als Checkboxen. Mehrere Konten können gemeinsam ausgewählt werden; die Dropdown-Rolle wird **neu hinzugefügten** Benutzern zugewiesen, die Rollen bereits ausgewählter Konten bleiben bestehen. Häkchen entfernen = Benutzer von dieser Firma entkoppeln. Bei bereits angelegten automatisch verwalteten Freigaben werden die Samba-Rechte direkt nach dem Speichern synchronisiert; bei fehlender SMB-Erreichbarkeit bleibt die DB-Änderung uncommitted. Mindestens ein Berechtigter muss bei bestehenden Firmenfreigaben bleiben.

**Firma löschen** ist erst nach bestätigtem Häkchen möglich und wird abgelehnt, sobald für die Firmenkennung noch Samba-Freigaben oder Verarbeitungsprofile vorhanden sind. Ein solcher Löschversuch entfernt keine Dateien oder Freigaben. Firmen ohne Abhängigkeiten werden mitsamt ihren Belegarten und Benutzerzuordnungen aus der Firmen-Datenbank gelöscht. **Benutzer entfernen** entfernt den Benutzer nur aus der *Firmenverwaltungs-Liste*, nicht aus Linux/Samba, und wird verweigert, solange noch Firmenzuordnungen oder Samba-Freigaben existieren. Dadurch werden bestehende Anmeldungen nicht unerwartet unterbrochen. Ein vollständiger systemseitiger Löschworkflow mit allen Abhängigkeitsprüfungen ist separat zu implementieren. `test_company_admin` erweitert. Deployment: `git pull --ff-only && bash install.sh`; nicht auf bereits eingerichteten Produktivfreigaben ohne Sicherung erproben.

## Verarbeitungseinstellungen je Firma und DATEV-Belegart (14.10.2026)

Unter **Firmen & Benutzer** hat jede Firma jetzt einen Bereich „PDF-Verarbeitung: Firmenstandard“ und eigene Einstellungen für alle aktivierten DATEV-Belegarten. Konfigurierbar als Checkboxen: QR-Code-Trennung, QR-Trennblätter entfernen, Leerseiten entfernen, Ränder beschneiden, OCRmyPDF am Schluss und DATEV-Sicherheitsmodus. Die Verarbeitungseinstellungen sind in `company_processing` (JSON) gespeichert; je Belegart werden nur Abweichungen vom Firmenstandard gehalten. DATEV-Sicherheitsmodus erfordert QR-Trennung; QR-Trennblattentfernung ist optional. Die Archivfreigabe ist automatisch die jeweilige `Firma-Belegart-Archiv`-Freigabe, solange DATEV-Sicherheitsmodus aktiviert ist; wenn DATEV deaktiviert wird, erfolgt derzeit keine automatische Originalarchivierung.

Bei expliziter Einrichtung der Samba-Freigaben über „Fehlende Samba-Freigaben anlegen / Rechte synchronisieren“ wird je Belegart ein eigenes automatisch verwaltetes PDF-Verarbeitungsprofil erstellt, mit dem jeweiligen `-Eingang`, `-Ausgang` und `-Archiv`. Bereits erzeugte Firmenprofile werden bei Änderung der Einstellungen aktualisiert. Bestehende manuelle Profile bleiben unverändert und werden niemals übernommen; Konflikte blockieren die Anlage. Firmenprofile sind gegen manuelle Änderungen oder Löschen in der alten Profilmaske geschützt. Die bestehenden DATEV-Dubletten- und Archivierungsregeln gelten weiterhin. Tabellen `company_processing` und `company_profile_links` werden automatisch migriert. Tests in `test_company_processing.py`, Installer kopiert und führt sie aus. Bereits angelegte Firmen können nachträglich eingerichtet werden; bestehende Freigaben alleine erzeugen noch keine Profile ohne Klick auf den Einrichtungsbutton. Debian-Liveprüfung ausstehend.

## 14.10.2026: Belegart im Auswahlfenster bearbeiten

Die Firmenverwaltung zeigt jetzt je Firma ein Dropdown für „Firmenstandard“ oder einen aktiven DATEV-Belegtyp. Erst nach „Optionen bearbeiten“ erscheint **genau ein** Formular mit QR-Trennung, Trennblattbehandlung, Leerseiten, Rändern, OCR und DATEV-Sicherheitsmodus. Nach „Einstellungen speichern“ kehrt die GUI zur selben Firma/Belegart zurück. Für den nächsten Belegtyp erneut auswählen. Speicherstruktur, individuelle Überschreibungen und automatische Firmenprofile bleiben erhalten. Änderungen in `company_processing.py`, `company_admin.py`, `app.py`, `test_company_processing.py`. Installation mit `git pull --ff-only && bash install.sh`. Noch nicht live auf dem Scan-Server getestet.

## 14.10.2026: Belegart-Auswahl ohne Bearbeiten-Button

Der zusätzliche Button „Optionen bearbeiten“ entfällt. Die Auswahlbox startet bei Änderung automatisch eine GET-Anfrage und lädt die zugehörigen Checkboxen. Der POST-Button „Einstellungen speichern“ bleibt ausdrücklich erforderlich. Die Oberfläche verwendet ein gleichursprüngliches kleines Skript über /company-ui.js und CSP `script-src 'self'`; kein Inline-JavaScript. Bei abgeschaltetem JavaScript wird ein Ersatzbutton angezeigt. Vor dem Wechsel ungespeicherte Änderungen speichern. Update: git pull --ff-only && bash install.sh.

## 14.10.2026 – Erweiterte Belegart-Einstellungen

Der Leerseiten-Schwellwert (maximaler Schwarzanteil, 0–2 %), OCR-Sprache (Deutsch / Englisch / kombiniert), OCR-Ausgabe (PDF / PDF/A), automatische Seitendrehung und Begradigung sind jetzt ebenfalls im auswählbaren Firmenstandard und im Belegart-Editor verfügbar. Bestehende gespeicherte Datensätze bleiben kompatibel und erhalten für neue Felder zunächst die bisherigen Vorgaben: 0,5 %, deu+eng, PDF, automatische Drehung/Begradigung deaktiviert. Die Werte werden bei Firmenprofil-Synchronisation auf die bisherigen `profiles`-Spalten geschrieben. Ein expliziter Speichervorgang ist weiterhin erforderlich. `company_processing.py`, `app.py` und `test_company_processing.py` angepasst. Auf dem Server noch nicht getestet.

## QR-Trenncode in Firmenverwaltung (14.10.2026)

Der bisher global gespeicherte QR-Trenncode wird nur noch unter `/companies` oben angezeigt und bearbeitet. Auf der Hauptseite entfällt die doppelte Einstellung. Es bleibt derselbe Datensatz `settings.qr_text` für sämtliche manuellen und firmenverwalteten Profile; die Verarbeitungslogik ändert sich nicht. Speichern führt wieder zur Firmenverwaltung. Für unterschiedliche QR-Codes pro Firma ist eine spätere getrennte Funktion nötig.

## 14.10.2026 – Startseite bereinigt und Firmen-LOG angebunden

Die bisherige lange Profil- und manuelle Samba-Maske wird auf der QR Scan Manager-Startseite nicht mehr angezeigt. Stattdessen zeigt sie eine kurze Übersicht und verlinkt auf `/companies`, `/jobs` und `/datev-review`. Bestehende Profile, darunter `Test`, werden NICHT gelöscht oder deaktiviert; die Startseite warnt bei älteren, nicht mit einer Firma verknüpften Profilen. Die technische Tabelle `profiles` und die Verarbeitung bleiben erhalten. Neue Aufträge verknüpfter Firmenprofile schreiben nach Abschluss oder Fehler zusätzlich atomar `job_<sha256>.json` mit Status, Zeit, Quelldateiname und Ergebnis in die spezifische `Firma-Belegart-LOG`-Freigabe. Es werden keine PDFs in LOG abgelegt. Fehler bei der LOG-Ausgabe dürfen einen erfolgreichen DATEV-Handoff nicht rückgängig machen. Die LOG-Datei wird bei Wiederholung desselben Auftrags mit demselben Fingerprint überschrieben. Andere manuelle Profile schreiben nicht in Firmen-LOG. Dateien werden als qrscan im lokalen LOG-Verzeichnis angelegt; SMB-Zugriff bleibt nach Freigabenrechten eingeschränkt. Installer ergänzt `profile_logs.py` und `test_profile_logs.py`, führt Tests aus. Vor Installation PBS-Backup; Update `git pull --ff-only && bash install.sh`; Debian-Liveprüfung steht noch aus. Die alten HTTP-Profilendpunkte bestehen vorerst aus Kompatibilitätsgründen, die GUI zeigt sie nicht mehr an.

## Firmen-Statusanzeige (14.10.2026)

Die Firmenverwaltung `/companies` zeigt pro Firma einen schreibgeschuetzten Einrichtungsstatus. Sie liest die aktuell zugeordneten SMB-Benutzer aus `company_access`, die vorhandenen Samba-Freigaben über den Samba-Manager (Soll: vier Freigaben je Belegart) und die automatisch verknuepften Profile aus `company_profile_links`/`profiles`. Pro Belegart werden Anzahl vorhandener Freigaben und Profilstatus angezeigt. Wenn der Samba-Manager nicht erreichbar ist, steht 'Nicht pruefbar' statt einer erfundenen Erfolgsmeldung. 'Konfiguration vollstaendig angelegt' bedeutet NICHT, dass Scans und DATEV getestet wurden. Keine Daten veraendert. Regressionstest in `test_company_admin.py`. Installation mit `git pull --ff-only && bash install.sh`.

## 14.10.2026 – PDF-Problemüberwachung je Firma

Unter `/companies` wird pro Firma unter dem Einrichtungsstatus jetzt eine PDF-Problemübersicht angezeigt: letzte maximal 250 Aufträge, erfolgreiche, fehlgeschlagene, Wiederholungen und Warnungen. Problemzeilen mit Zeitpunkt, Belegart, Dateiname, Fehlerkategorie und dem konkreten Grund. Die Zuordnung erfolgt ausschließlich über `jobs.profile_id` und `company_profile_links`, also keine fremden Firmen. Echte vorhandene Fehltexte werden heuristisch nach Dublette, QR-Trennung, OCR, PDF, Archivierung oder DATEV/Ausgabe kategorisiert; die Daten werden nicht verändert. Warnungen aus dem Ergebnis (z.B. `archive_warning`, `duplicates`) werden berücksichtigt. Eine sichere Rechnungserkennung, OCR-Konfidenzbewertung und inhaltliche Dublettenerkennung sind damit **noch nicht** implementiert und dürfen nicht behauptet werden. Die Anzeige umfasst nur die letzten 250 Aufträge; detaillierte Aufträge weiter unter `/jobs`. Dateien: `company_monitor.py`, `test_company_monitor.py`; Installer kopiert beide und führt Tests aus. Debian-Praxistest ausstehend.

## 14.10.2026 – PDF-Prüfwarteschlange (Schritt 1)

Neue Seite `/review`, über die Navigation `PDF-Prüffälle` erreichbar. Firmenverwaltete PDF-Aufträge mit Fehler, erneutem Versuch, Unterbrechung oder Warnung werden firmen- und belegartbezogen aus den bisherigen `jobs` gelesen. Filter: Firma, Belegart, offen/in Bearbeitung/erledigt/verworfen. Je Prüfauftrag können Bearbeitungsstatus und Notiz (max. 1000 Zeichen) gespeichert werden, in neuer Tabelle `review_cases`, verknüpft über die vorhandene 64-stellige Auftragssignatur. Keine Freigabe, kein Neuversand, keine Änderung von PDF oder DATEV-Status durch diese Funktion. Die Änderung eines Prüfstatus ist ausschließlich organisatorisch. Es werden höchstens 1000 jüngste Aufträge gesichtet; aus ihnen höchstens 150 Fälle angezeigt. Erfolgsmeldungen ohne Warnung sind keine Prüffälle. Vorhandene `company_monitor.classify` liefert Kategorie und Fehlertext. Installer ergänzt `review_queue.py`, `test_review_queue.py`; Datenbank wird automatisch beim Zugriff migriert. Tests auf Debian vor Inbetriebnahme ausführen. Nächste Stufe: sichere PDF-Vorschau und Korrekturen.

## 14.10.2026: Prüfwarteschlange – PDF-Vorschau und Korrekturentwurf (Schritt 2)

`/review` bietet pro Prüffall „Original-PDF ansehen“ (GET `/review-pdf?signature=...`), sowie einen manuellen Korrekturentwurf mit frei gewählter Seitenfolge bzw. Teilmenge (kommagetrennte 1-basierte Seiten) und Drehung um 0/90/180/270 Grad. Der Download folgt nach der Erstellung (`/review-draft?signature=...`). Diese Version bietet **noch keine interaktive Vollbildvorschau, OCR-Neuberechnung, PDF-Upload oder DATEV-Freigabe**. PDF-Quellen werden ausschließlich über die verknüpfte Firmensignatur und erlaubte Pfade im Samba-Root/Originalarchiv freigegeben. Korrekturentwürfe liegen privat unter `/var/lib/qrscan/review-drafts/<signature>.pdf` (0600); Originale bleiben unverändert. Der Vorgang stellt den Prüffall auf „in Bearbeitung“ und lässt sämtliche DATEV-Übertragungen unberührt. Nutzer können den Entwurf herunterladen und getrennt prüfen; ein sicherer neuer Freigabe-/Verarbeitungsvorgang wird erst in einer späteren Entwicklungsstufe implementiert. Installer enthält `review_pdf.py`, `test_review_pdf.py` und dessen Unittests. Produktivtest auf Debian ausstehend.

## 14.10.2026 – Schritt 3 Dublettenprüfung mit Entscheidung

Bei Dublettenfehlern in `/review` gibt es einen Link zu `/duplicate-review?signature=...`. Dort werden zugehörige Einträge aus dem DATEV-Prüfregister für den Original-Job angezeigt, einschließlich SHA256, passender bereits registrierter Belegdatei (falls vorhanden), und der private verdächtige Einzelbeleg kann über `/duplicate-pdf` angezeigt werden. Die Benutzerentscheidung „Als Dublette bestätigen“ oder „Kein Duplikat – weiterer Prüfbedarf“ mit verpflichtender Begründung wird in einer separaten Tabelle `duplicate_decisions` im DATEV-Register gespeichert und kann erneut angezeigt werden. Die Entscheidung **ändert weder `datev_invoices` noch `datev_suspects` und gibt niemals automatisch an DATEV frei**. Eine bestätigte Nicht-Dublette bedarf weiterhin eines separaten sicheren Übergabeworkflows. Die Vorschau gibt ausschließlich PDFs aus dem privaten `datev-review`-Verzeichnis aus, keine beliebigen Pfade. Die Zuordnung zum Job wird vor der Entscheidung kontrolliert. Vergleich erfolgt vorerst anhand der Metadaten und des verdächtigen PDF; eine visuelle Gegenüberstellung des bereits veröffentlichten Originals ist noch nicht umgesetzt. `duplicate_review.py`, `test_duplicate_review.py` und Installer aktualisiert. Live-Test auf Debian ausstehend.

## Geplant: DATEV-Belegtransfer-Überwachung

Punkt 4 ist als **offener Backlog-Eintrag** in [`BACKLOG.md`](BACKLOG.md) dokumentiert: Übertragungsstatus des Windows-DATEV-Belegtransfers prüfen, firmenspezifische Fehler anzeigen, unbekannten Status nicht automatisch erneut übertragen. **Noch nicht implementiert.**

## 14.10.2026 – Punkt 5: E-Mail-Benachrichtigungen

Unter `/notifications` können SMTP-Server, Port, SMTP-Benutzer, Passwort (bleibt beim späteren Bearbeiten verborgen), Absender, Empfänger, TLS-Modus (STARTTLS oder SSL/TLS) und eine ausdrückliche Aktivierung eingetragen werden. Ohne aktive Konfiguration erfolgen **keine** E-Mails. Nach Verarbeitung eines firmenverwalteten Auftrags meldet der Watcher endgültige PDF-Fehler, unterbrochene Aufträge und explizit im Verarbeitungsergebnis gemeldete Warnungen (z. B. Archivierung oder Dublette). Ein Eintrag in `notification_sent` verhindert wiederholte Nachrichten für denselben Auftrag/Status. Vorübergehende `retry`-Status erzeugen bewusst keine sofortige E-Mail, bleiben aber in der Prüfwarteschlange sichtbar. SMTP wird nur verschlüsselt benutzt; E-Mail-Fehler dürfen die PDF-Verarbeitung oder DATEV-Übergabe nicht zurücksetzen. Zugangsdaten werden in der nur für den lokalen Dienst zugänglichen SQLite-Datenbank gespeichert (keine zusätzliche Verschlüsselung innerhalb der DB); Datenbankzugriff und Backups entsprechend schützen. Versand erfolgt synchron nach Auftragsabschluss und enthält Firmenkennung, Belegart, Dateiname und Fehlertext, nicht das PDF selbst. **Kein SMTP-Testversand und keine Benachrichtigung über externe DATEV-Belegtransfer-Fehler**, solange Punkt 4 noch im Backlog liegt. Dateien: `notifications.py`, `test_notifications.py`, Installer/App/Watcher aktualisiert. Debian-Integrationstest ausstehend.

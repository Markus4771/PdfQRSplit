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

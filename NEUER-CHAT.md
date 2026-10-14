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

## Punkt 4 – Debian 13 (Testvorbereitung)

Installer legt jetzt `/srv/samba-shares` an, prüft Web- und Watcher-Dienst und führt die Safe-Publish-Tests aus. `.github/workflows/debian13.yml` führt einen Debian-13-Containercheck mit Syntax- und Publishing-Tests aus. Noch nicht bestätigt, dass CI erfolgreich abgeschlossen wurde, und kein E2E-Samba-/OCR-Test durchgeführt. Entwicklungscontainer Debian 13 vorhanden, GitHub-Download dort durch DNS blockiert.

## Separater Samba-Verwaltungsdienst

`samba_rpc.py` als Root-Dienst `qrscan-samba.service`, Verbindung über Unix-Socket nur für `qrscan` per SO_PEERCRED. Webdienst wieder `NoNewPrivileges=yes`, alte sudoers-Regel wird im Installer entfernt. Kein schreibgeschütztes Dateisystem für Root-Helfer. Installation/SMB-Erstellung noch praktisch verifizieren.

## Samba Mehrfachnutzung – Fehlerkorrektur

Samba-Passwortprüfung enthielt falsche (wörtliche) Zeilenumbrüche in der Credential-Datei. `samba_helper.py` korrigiert; `app.py` erlaubt, bei einer vorhandenen Freigabe auf einen bereits vorhandenen SMB-Benutzer umzustellen und dessen Passwort zu verifizieren. Achtung: vorhandenen Benutzer nicht löschen; noch auf Debian zu testen.

## QR-Praxistest vom 13.10.2026

Das laufende Debian-System meldet alle 20 Test-PDFs als erfolgreich bearbeitet, aber jeweils nur eine Ausgabedatei. Die Profilkonfiguration ist per SQLite bestätigt: `Test|Eingabe-Test|Ausgang-Test|1` und QR-Text `SCAN-TRENNUNG-001`. Die Ursache ist offen. `diagnose_qr.py` neu: listet pro PDF-Seite die dekodierten QR-Codes und Treffer des Solltextes, ohne zu schreiben. Installer kopiert das Programm.

## Verarbeitung wiederholen und QR-Regeln

Neu: Wiederholen-Button für abgeschlossene/fehlerhafte/unterbrochene Aufträge unter `/jobs`. Zusätzliche Spalte `jobs.replay_count`, eindeutiger Ausgabestamm `_wiederholung_<hash>_<nummer>` verhindert Überschreiben. Erfordert noch Praxistest unter Debian 13. QR-Trennlogik in `worker.py` wurde geprüft und war bereits korrekt: Es trennen ausschließlich QR-Inhalte, die exakt dem `qr_text` entsprechen; andere QR-Codes werden ignoriert und die restliche PDF-Verarbeitung läuft weiter.

Update 13.10.2026: Der Button **Verarbeitung wiederholen** startet mit einem Klick unmittelbar die Wiederholungsanforderung; die zusätzliche Bestätigungs-Checkbox wurde entfernt. Der laufende Watcher verarbeitet den Auftrag im nächsten Durchlauf automatisch. Ausgabedateien bleiben geschützt und bekommen eindeutige Wiederholungsnamen.

## Automatische Fehlerwiederholung

`retry_policy.py` und `test_retry_policy.py` ergänzt. Vorübergehende OSError/TimeoutError: maximal 5 Gesamtversuche, mit 1/2/5/10 Minuten Abstand. FileExistsError, PermissionError, ValueError u. ä. gelten als dauerhaft und werden nicht automatisch wiederholt. Watcher loggt den nächsten Versuch in `jobs.details`, `next_retry` bleibt gesetzt; bei ausgeschöpftem Limit `error`. Bei manuell wiederholtem Auftrag wird eigener Ausgabestamm über `replay_count` auch bei nachfolgenden automatischen Versuchen weiterverwendet. Installer kopiert Modul und führt Test aus. Kein unendliches Wiederholen; QR-Inhaltsabweichungen bleiben normale Eingabe und werden ohne Trennung weiterverarbeitet. Auf Zielserver noch zu testen.

## Fehlerbehebung Dateinamenskollision bei Wiederholung

Praxisausgabe: Bei diversen Dateien `replay_count=0`, Status `error`, weil `Ausgang-Test/<dateiname>_0001.pdf` bereits vorhanden war. Neu: `output_naming.py` setzt bei neuen Aufträgen mit belegtem Originalausgabenamen einen stabilen `_neu_<digest>`-Stamm, bei manuell wiederholten Aufträgen weiterhin `_wiederholung_<digest>_<replay_count>`. `watcher.py` ruft die Funktion auf, Installer installiert Modul samt `test_output_naming.py`. Existierende PDFs werden nicht überschrieben. Bereits fehlerhafte Jobs per GUI manuell erneut freigeben. Vor-Ort-Test ausstehend.

## Implementiert: Auftragswartung

`jobs_ui.py`: fehlende Quellen und fehlende Ausgabe-PDFs über gespeicherte Ergebnisliste erkennen (JSON + Legacy-Python-Repr), konfigurierbare `job_retention_days` in SQLite (Default 90, 7–3650 Tage), `cleanup_jobs` löscht nur terminale, alte Auftragszeilen. `app.py`: Anzeige Quelle fehlt / Ausgabe fehlt und GUI-Feld für Aufbewahrung; Wiederholen-Button bei fehlender Quelle deaktiviert. `watcher.py`: JSON-Ausgabemanifest, Bereinigung höchstens stündlich, dauerhafte `archived_signatures`-Fingerabdrücke verhindern erneute Verarbeitung unveränderter Eingangs-PDFs nach DB-Bereinigung. `test_job_maintenance.py` mit Installer verbunden. PDFs niemals löschen. Praxistest noch ausstehend.

## DATEV-Sicherheitsmodus (Entwicklungsstand)

Neues Modul `datev_handoff.py`: pro fertiger Einzel-PDF exakten SHA-256 gegen dauerhaftes separates Register `/var/lib/qrscan/datev.sqlite3` prüfen, zunächst reservieren, dann per Hardlink nur einmal ablegen. Bei unbestätigtem Absturz bleibt `reserved` und blockiert Wiederholung (fail-closed). `worker.py` verwendet es nur im aktivierten DATEV-Profil; mehrseitige PDFs ohne gültige Trenncodes werden im DATEV-Modus zurückgehalten. `profile_settings.py` enthält `datev_mode` als Profilflag, `app.py` stellt Schalter und Ausgangs-Exklusivprüfung bereit, `watcher.py` übergibt das Flag. `install.sh` installiert Modul und Test. Noch keine Belegbild-/OCR-Dublettenprüfung, keine Quittung von DATEV, keine automatische Überwachung Windows-PC. Bis zur Prüfung nicht produktiv verwenden. Ein DATEV-Übergabeverzeichnis darf nicht von mehreren DATEV-PCs gleichzeitig überwacht werden.

## Fluent Bit Vorstufe

`install_fluent_bit.sh` über `install.sh` integriert: lokaler Listener `127.0.0.1:24224`, separater systemd-Dienst, Null-Ausgang. Noch keine DATEV-Protokolle, TLS-Client-Zertifikate oder Windows-Quellen konfiguriert. Nicht produktiv freigeben; Tests auf Zielserver offen.

## DATEV: erneut gescannte Rechnungen

`datev_visual.py` neu mit visuellen 256-bit Seiten-Fingerabdrücken. `datev_handoff.py` speichert diese pro reserviertem Beleg und blockiert ähnliche PDF-Belege gleicher Seitenzahl vor Bereitstellung; Verdachtsfälle landen in `datev_suspects` und Auftrag `error`, Eingangs-PDF bleibt vorhanden. Exakte Byte-Dubletten via SHA-256 unverändert. Installer installiert Modul und Tests. Keine OCR-Rechnungsnummernprüfung, keine visuelle Backfill alter DATEV-Registereinträge, kein automatischer manueller Freigabeworkflow; Fehlalarme und nicht erkannte Dubletten möglich. Nicht produktiv verwenden ohne Tests mit echten Rechnungen.

## DATEV-Quarantäne

`datev_handoff.py` legt bei visuellem Dublettenverdacht die **einzelne fertig verarbeitete Rechnung**, nicht das gesamte Scan-Batch, unter `/var/lib/qrscan/datev-review/verdacht_<digest>.pdf` ab, außerhalb des Samba-DATEV-Zielordners. Registerspalte `datev_suspects.review_path` wird migriert. Kein PDF im DATEV-Ausgang; Originalscan bleibt unangetastet. `app.py` zeigt unter `/datev-review` eine read-only Übersicht; kein unkontrollierter Freigabeknopf. Installer erzeugt geschützten Quarantäneordner (0700) und `test_datev_visual.py` prüft die Dateisicherung. Noch nicht auf Debian praktisch validiert.

## DATEV-Samba-Schutz

`samba_helper.py` bietet `datev_protected` bei `create` und `protect-datev` für bestehende Freigaben. Samba-Konfiguration setzt `read only=yes`, `comment=QRSCAN-DATEV-READONLY`, `veto files=/qrscan-*/`, `hide unreadable=yes`. Spätere `update`-Aufrufe lassen DATEV geschützt schreibgeschützt. `samba_rpc.py` lässt neue Aktion zu. `app.py` zeigt Markierung, Schutzbutton und verlangt markierte DATEV-Samba-Freigabe bei Profilanlage/-änderung. `watcher.py` prüft Markierung plus `read only=yes` vor DATEV-Verarbeitung. Unveränderte gewöhnliche Freigaben. Erfordert Tests mit `testparm` und SMB-Read/Write/Löschprobe; Belegtransfer-Kompatibilität von SMB Nur-Lese noch unbekannt.

## Samba include position fixed

`install.sh` repariert die früh in `[global]` eingesetzte QR Scan Manager `include = /etc/samba/qrscan-shares.conf` durch Verschieben an das Ende der `smb.conf`; Zeitstempelbackup, temporäre `testparm`-Validierung und atomarer Austausch; keine Änderungen an anderen Freigaben. Benutzer `Eingabe-Test`/`Ausgang-Test` bleiben unverändert. Laufzeitkontrolle durch `testparm -s` auf dem Debian-Server steht aus.

**Korrektur 14.10.2026:** Der QRSCAN-Samba-`include` muss **als letzte Direktive in `[global]` unmittelbar vor dem ersten Freigabeabschnitt** stehen. Eine Position am Dateiende würde Samba die Direktive fälschlich der letzten Freigabe `[print$]` zuordnen. `install.sh` korrigiert dies mit vorherigem Zeitstempel-Backup und `testparm`-Prüfung. Nach dem Update `testparm -s` erneut ausführen: `include` muss unter `[global]`, nicht unter `[print$]` erscheinen.

## DATEV-Samba-Profilspeicherung: Fehlerbehebung 14.10.2026

Die frühere Fehlermeldung `Profil ungültig: DATEV-Ausgang muss eine geschützte, schreibgeschützte Samba-Freigabe sein` trat auf, weil `app.py` beim Profilspeichern ausschließlich prüfte, aber keinen Schutz aktivierte. Neu: `ensure_datev_samba_protection()` liest den Status über `samba_call(list)` und ruft für die explizit gewählte DATEV-Ausgangsfreigabe `protect-datev` auf, falls nötig. Konkrete Samba-RPC-Fehler werden in der GUI ausgegeben. In `/add` und `/profile-update` integriert. Achtung: Die ausgewählte Freigabe wird dadurch SMB-schreibgeschützt; unbedingt eigene DATEV-Freigabe verwenden, keine gemeinsam genutzten Testfreigaben. `README.md` ebenfalls aktualisiert. Deployment noch ausstehend; `git pull --ff-only && bash install.sh`.

## DATEV: QR-Trennblätter bleiben auf Wunsch enthalten

`app.py`: DATEV-Profil verlangt nur `qr_split=1`; `remove_separators` darf 0 sein. `worker.sections` übernimmt vorhandene QR-Trennseite bei deaktiviertem Entfernen als erste Seite des nächsten Einzelbelegs. Achtung: identische QR-Trennseiten beeinflussen visuelle Fingerprint-Dublettenprüfung; Sicherheit mit Testbelegen validieren. Keine Änderung des Standardprofils oder der bisherigen getrennten PDF-Verarbeitung.

## Automatisches Originalarchiv – DATEV

Neu `original_archive.py`, `test_original_archive.py`. `watcher.py` archiviert die originale ungetrennte Quell-PDF **nur nach erfolgreicher DATEV-Verarbeitung** und nur wenn kein anderes Profil dieselbe Eingangsfreigabe verwendet. Archiv `/var/lib/qrscan/original-archive/`, 0700; neue Dokumente 0600, SHA-256-verifiziert. Ablauf: Output bereits erfolgreich, Archivkopie dauerhaft ablegen, Job `done` einschließlich `original_archive` persistieren, Eingangsoriginal nur bei unverändertem SHA-256/Dateizustand entfernen. Bei Fehler, Quarantäneverdacht oder gemeinsamer Eingangsfreigabe wird nicht aus dem Eingang entfernt. Keine automatische rückwirkende Archivierung bereits erledigter Jobs. Nach Absturz können beide Kopien existieren, niemals ungeprüft löschen. Installationsroutine erstellt Archivordner und führt Regressionstests aus. Debian-Praxistest und PBS-Backup-Prüfung fehlen.

## Neuer DATEV-Archivshare im Verarbeitungsprofil

Neues Profilfeld `archive_share` in `profile_settings.py`, DB-Migration und Dropdown bei Profilanlage/-bearbeitung. `app.py` validiert drei verschiedene Freigaben, reserviert Archivfreigabe exklusiv und setzt SMB-Zugriff via `ensure_datev_samba_protection` auf Nur-Lesen. `watcher.py` wählt unter `get_shares()` die Archiv-Ziel-Samba-Freigabe statt des internen Pfades, prüft exklusive Verwendung und Schreibrechte. `original_archive.prepare_archive(...,shared=True)` verändert dabei nicht die Verzeichnisrechte der Samba-Freigabe. SHA-256-/Absturzsicherung und Schutz des Quelloriginals bleiben bestehen. Bestehende DATEV-Profile ohne Auswahl behalten das interne Archiv; vorhandene Archivdateien werden nicht automatisch migriert. `test_original_archive.py` erweitert um Test der unveränderten Samba-Ordnerrechte. Installer unverändert ausreichend, weil vorhandene Module kopiert und Tests bereits ausgeführt werden. `git pull --ff-only && bash install.sh` auf Scan-Server ausführen. Noch keine Praxistests.

## 14.10.2026: Fix Profil-Speichern mit Archiv-Auswahl

`app.py` verwendete nach Schema-Erweiterung fälschlich `values[14]` als DATEV-Flag und `values[4]` als QR-Trennung. Tatsächlich gibt `check()` `qr_split` bei Index 3, `datev_mode` bei 13 und `archive_share` bei 14 zurück. Indizes und Exklusivprüfung korrigiert. Screenshot zeigte QR-Trennung aktiv, trotzdem unzutreffende Fehlermeldung. Für Archiv eine neue, eigene Samba-Freigabe nutzen. GitHub geändert, Installation noch offen.

## DATEV-Profil QR-Prüfung: Diagnose (14.10.2026)

Bei Profiländerungen prüft `app.py` nun unmittelbar die übermittelten Formularfelder `qr_split` und `datev_mode`, statt Tupelindizes zu verwenden. Wenn trotz aktivierter QR-Code-Trennung eine Fehlermeldung erscheint, `/opt/qrscan/app.py` auf dem Zielsystem aktualisieren und `qrscan-web` neu starten (via `git pull --ff-only && bash install.sh`). Die neue Fehlermeldung zeigt explizit `qr_split=aus, datev_mode=an`, wenn der Server die QR-Checkbox nicht erhält. QR-Trennblätter entfernen bleibt optional.

## 14.10.2026 – Fluent-Bit-APT-Indexfehler blockierte install.sh

User meldete Debian Trixie `Packages.bz2` unerwartete Größe und Hashabweichung. `install.sh` toleriert jetzt Ausfall des **optionalen** Fluent-Bit-Schritts und deaktiviert bei kaputtem Paketindex ausschließlich `/etc/apt/sources.list.d/fluent-bit.list` in `.list.disabled`; initiales `apt-get update` kann die defekte Fluent-Bit-Quelle ebenfalls gezielt deaktivieren und erneut versuchen. Niemals APT-Hash-/Signaturprüfung abschalten. `qrscan-web` lief, aber `grep -n 'Übermittelt: qr_split' /opt/qrscan/app.py` zeigte noch keinen Treffer; nach `git pull --ff-only && bash install.sh` prüfen. Fluent Bit bleibt ohne Windows-Agent optional und noch ohne DATEV-Logauswertung.

## 14.10.2026 Firmenverwaltung erste Ausbaustufe

Github ergänzt: `company_admin.py` (SQLite-Migration, Firmen, DATEV-Typen, Samba-Benutzerverknüpfung, Zugriffsrollen, HTML-Seite); `test_company_admin.py`; GUI `/companies` plus POST-Routen; `samba_helper.py` rootseitig neue Konto- und Firmenfreigaben-Aktionen, bestehende Konten nur nach Passwortcheck registrieren, ausschließlich mit eigenem Marker verwaltete Freigaben synchronisieren, ansonsten keine Übernahme; `samba_rpc.py` Whitelist; `watcher.py` akzeptiert den neuen geschützten Ausgangsfreigabe-Marker. `install.sh` kopiert die neuen Module und testet. Freigabenamen `<Firma>-<DATEV-Typ>-<Eingang|Archiv|Ausgang|LOG>`; Beschränkung 40 Zeichen. GUI-Seite `http://192.168.0.55:8086/companies` nach Installation. **Nicht** bereits umgesetzt: automatische Profilanlage, DATEV-PC-Konfiguration, individuelle DATEV-Belegtypen, Rollenverwaltung in der Web-GUI (nur admin kann GUI aufrufen), vollständige Samba-Liveprüfung. Alte Daten bleiben unangetastet. Installation/Betrieb auf dem Debian-Server muss Nutzer testen.

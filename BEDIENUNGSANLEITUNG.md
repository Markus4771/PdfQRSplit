# PdfQRSplit – Bedienungsanleitung

## Benutzergruppen

**Administrator:** Richtet Firmen, Belegarten, Verarbeitungsoptionen, Samba-Benutzer, Web-Zugänge, SMTP, Prüfentscheidungen und Korrekturentwürfe ein.

**Firmenbenutzer:** Meldet sich mit seinem Namen und einem **separaten Web-Passwort** an. Sieht unter `/review` die Prüffälle der Firmen, denen er in der Firmenverwaltung zugeordnet wurde, sowie unter `/datev-review` die zu diesen Firmen gehörenden Verdachtsfälle. Für Firmenbenutzer sind diese Ansichten **schreibgeschützt**; Web-Konfiguration und Korrekturaktionen bleiben dem Administrator vorbehalten.

## Benutzer und E-Mail-Adresse pflegen (Administrator)

1. `/companies` öffnen.
2. Unter „SMB-Benutzer“ Benutzer anlegen oder vorhandenen übernehmen.
3. Unter „E-Mail-Adressen der Firmenbenutzer“ seine E-Mail-Adresse eingeben und speichern.
4. Unter „Web-Zugänge für Firmenbenutzer“ eigenes Web-Passwort (mindestens 12 Zeichen) setzen. Das ist **nicht** das Samba-Passwort.
5. Bei der passenden Firma die Checkbox des Benutzers auswählen, Rolle festlegen und „Benutzerzuordnung speichern“ anklicken.
6. Bei mehreren Firmen den Benutzer bei jeder berechtigten Firma zuordnen. Ohne Zuordnung ist kein Firmen-Webzugang möglich.

## Warnungen per E-Mail

Der Administrator stellt SMTP auf `/notifications` ein und aktiviert den Versand ausdrücklich. Bei kritischen Fehlern (z. B. fehlgeschlagene OCR-Verarbeitung) und festgestellten Verarbeitungswarnungen erhält jeder zugeordnete Firmenbenutzer mit hinterlegter E-Mail-Adresse eine Nachricht für **seine Firma**. Die Nachricht enthält Firma, Belegart, Dateinamen und Fehlertext, **nicht die PDF-Anlage**. Temporäre Wiederholungsversuche lösen normalerweise noch keine E-Mail aus. Die Nachricht bedeutet nicht, dass die DATEV-Übertragung bestätigt oder zurückgenommen wurde.

## PDF-Prüffälle ansehen

1. Weboberfläche aufrufen und mit den eigenen Web-Zugangsdaten anmelden.
2. `/review` öffnen (bei der bisherigen Instanz `http://192.168.0.55:8086/review`).
3. Firma, Belegart und Prüfstatus filtern.
4. Die konkrete Fehlermeldung lesen; bei verfügbarem Original auf „Original-PDF ansehen“ klicken.
5. Dem Administrator Fehler bzw. Korrekturwunsch melden. Nur Administratoren können Prüfnotizen, Statusänderungen, PDF-Korrekturentwürfe oder Dublettenentscheidungen bearbeiten.

Mögliche Meldungen: QR-Trennung unklar, OCR fehlgeschlagen, beschädigtes PDF, Dublettenverdacht, DATEV-Handoff-/Ausgabefehler und Archivierungsprobleme. Die Diagnose leitet sich zum Teil aus dem vorhandenen Fehltext ab und ist nicht immer eine sichere automatische Rechnungsklassifikation.

## DATEV-Prüfbereich

Unter `/datev-review` sind passende Dublettenverdachtsfälle der zugeordneten Firmen sichtbar. Ein Verdacht ist **noch keine** belegte doppelte Übertragung. Nur Administratoren dürfen formelle Dublettenentscheidungen treffen. Weder das Öffnen der Seite noch das Markieren eines Prüffalls überträgt Rechnungen an DATEV.

## PDF-Korrektur (Administrator)

In `/review` das Original ansehen und gegebenenfalls Seiten auswählen oder drehen. Daraus entsteht ein **separater Korrekturentwurf**, der heruntergeladen werden kann. Das Original bleibt unangetastet; eine automatische DATEV-Freigabe ist damit nicht verbunden.

## Zustände und Grenzen

- „Erfolgreich verarbeitet“ = lokal verarbeitet/bereitgestellt; **keine** sichere Bestätigung des Windows-DATEV-Belegtransfers.
- „Fehler“ = Bearbeitung fehlgeschlagen; Ursache und Original prüfen.
- „Warnung“ = Verarbeitung möglicherweise erfolgreich, aber besondere Prüfung nötig.
- „Erledigt“ im Prüffall = organisatorischer Status, **keine** DATEV-Upload-Bestätigung.
- Die Überwachung des tatsächlichen Windows-DATEV-Belegtransfers ist noch im `BACKLOG.md`.
- Bei unklarem DATEV-Status keine unkontrollierte Neuübertragung auslösen.

## Unterstützung

Admin prüft `/jobs`, `/companies` sowie die Systemdienste `qrscan-web`, `qrscan-watcher`, `qrscan-samba`. Bei Fehlern die Anzeige und Logdateien sichern, nicht eigenmächtig Archive oder DATEV-Register löschen.

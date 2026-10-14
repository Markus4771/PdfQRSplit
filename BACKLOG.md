# Backlog – PdfQRSplit

## Offen: Punkt 4 – Windows-DATEV-Belegtransfer überwachen

**Status:** Backlog / noch nicht implementiert  
**Priorität:** Nach erfolgreichem Praxistest der PDF-Prüfwarteschlange und Dublettenprüfung

**Ziel:** Zu jedem im DATEV-Ausgang bereitgestellten Beleg erkennen, ob der DATEV-Belegtransfer unter Windows die Übertragung nachweisbar erfolgreich abgeschlossen hat, ob sie fehlgeschlagen ist oder ob der Status ungeklärt bleibt.

### Geplante Aufgaben

1. Installierte DATEV-Belegtransfer-Version und verfügbares Übertragungsprotokoll auf Windows prüfen. Dokumentieren, welche Statusinformationen tatsächlich verfügbar sind; keine nicht belegte API voraussetzen.
2. Windows-seitige Statusermittlung bzw. einen kleinen Überwachungsdienst konzipieren, mit sicherer Übertragung der Ereignisse an PdfQRSplit.
3. Belege anhand eines belastbaren Identifikators der Bereitstellung zuordnen (Dateiname/Hash und Zeit sowie ggf. Mandant/Belegart).
4. Status in PdfQRSplit unterscheiden: **bereitgestellt**, **bestätigt übertragen**, **fehlgeschlagen**, **ungeklärt**. Erst eine echte Bestätigung des Belegtransfers darf als „übertragen“ gelten.
5. Fehlermeldungen in der firmenspezifischen Prüfwarteschlange anzeigen, mit Diagnose und manueller Korrektur-/Wiederaufnahmefunktion.
6. Doppelte DATEV-Übertragungen verhindern: Bei unklarem Status niemals automatisch erneut senden; Freigabe erst nach manueller Klärung. Jede Entscheidung protokollieren.
7. Tests mit erfolgreicher Übertragung, Authentifizierungs-/Netzwerkfehlern, Doppelbelegen, Windows-Neustarts und nicht verfügbarer Protokollquelle erstellen.

**Abgrenzung:** Noch keine Implementierung oder Änderung am Windows-PC bzw. der DATEV-Übertragung. Die bisherige PDF-Ausgangsbereitstellung ist **keine** Upload-Bestätigung.

# Mini-Vorschläge aufs iPhone

Der Mac schreibt jeden Morgen um 07:30 (und bei jedem Lauf über den iPhone-Kurzbefehl) zwei Vorschläge für den Tag nach
**iCloud Drive › Trainingscockpit**:

- `vorschlag-vormittag.txt`
- `vorschlag-nachmittag.txt`

Sie passen zu deiner Erholung laut Uhr und sind dieselben wie in **Heute → Für zwischendurch**. Das iPhone zeigt sie
mit zwei Automationen zu festen Zeiten als Mitteilung an. Einmal einrichten, etwa 5 Minuten.

## Automation 1: 10:00 Uhr

1. Öffne die App **Kurzbefehle** und wähle unten **Automation**.
2. Tippe auf **+** (oder **Neue Automation**) und wähle **Tageszeit**.
3. Stell **10:00** ein, Wiederholen: **Täglich** (oder nur Mo–Fr unter *Wöchentlich*).
4. Wähle **Sofort ausführen** und tippe auf **Weiter**.
5. Tippe auf **Neuer leerer Kurzbefehl** und füge diese drei Aktionen hinzu (oben in die Suche tippen):
   1. **Datei aus Ordner abrufen**: Tippe auf den Ordner und wähle **iCloud Drive › Trainingscockpit**.
      Als Dateipfad gibst du `vorschlag-vormittag.txt` ein. Schalte „Fehler, wenn nicht gefunden“ aus.
   2. **Text aus Eingabe abrufen**: übernimmt automatisch die Datei aus Schritt 1.
   3. **Mitteilung anzeigen**: Tippe ins Textfeld und wähle die Variable **Text**. Als Titel schreibst du „Für zwischendurch“.
6. Tippe auf **Fertig**.

## Automation 2: 14:30 Uhr

Wie oben, nur mit **14:30** und dem Dateipfad `vorschlag-nachmittag.txt`.

## Testen

- Den Ordner gibt es erst nach dem ersten Lauf des Macs: morgen um 07:30 oder sofort, wenn du deinen bisherigen
  Garmin-Kurzbefehl auf dem iPhone startest.
- In der Automation kannst du auf den Kurzbefehl tippen und unten auf **▶** drücken. Dann muss die Mitteilung kommen.
- Erledigt? Im Cockpit unter **Heute → Für zwischendurch** abhaken. Dann zählt es für deine Wochenziele.

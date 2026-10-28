# Trainingscockpit

Florians tägliches Trainings- und Gesundheits-Cockpit: Garmin-Daten vom Mac, ausgewertet zu Recovery, Belastung und Schlafbedarf, plus Tagescoach für Check-in, Training und Gewohnheiten.

| Ordner | Inhalt |
|---|---|
| `mac/` | Läuft auf dem Mac in `~/garmin`: `sync.py` (Garmin Connect), `analyze.py` (Auswertung), `formulas.py` (reine Formeln), `check_fresh.py` (Warnung bei alten Daten), `nudges.py` (Mini-Vorschläge nach iCloud Drive fürs iPhone, Anleitung in `docs/iphone-mini-vorschlaege.md`), `garmin.sh`, launchd-Job |
| `web/cockpit/` | Seite des Trainingscockpits (Claude-Artifact) und `gesamtzustand.txt` (Gewichte der Ampel). Start ist **Heute** mit der Kachel Gesamtzustand oben (Morgen-Ablauf in 4 Schritten, ab 17 Uhr Abend-Reflexion zum Antippen, Check-in, Tagesmodus, Tipp, Training in 3 Stufen, Mini-Vorschläge, Kopf, Gewohnheiten), daneben **Übersicht** (Woche, Trends, Erkenntnisse mit Alltagstipp) |
| `web/tagescoach/` | Alter, eigenständiger Tagescoach; steckt jetzt im Cockpit und kann nach dem Umzug der Daten weg |
| `tests/` | Tests; `make_fixture.py` erzeugt ausgedachte Garmin-Daten |
| `COACH.md` | Leitfaden für den Coach (Plan-Schema, Übungen) |

## So kommt das Dashboard aufs iPhone (Stand 28.10.2026, bleibt so)

Ermittelt aus `mac/garmin.sh`, `mac/de.garmin.dashboard.plist`, dem Ordner `~/garmin` (nur gelesen) und der geplanten Claude-Aufgabe.

1. **Mac, 07:30 (oder beim Aufwachen):** launchd-Job `de.garmin.dashboard` startet `/bin/zsh ~/garmin/garmin.sh --auto`.
   - `sync.py` holt die Rohdaten von Garmin Connect nach `~/garmin/data.json`.
   - `analyze.py` rechnet daraus `~/garmin/dashboard-data.json` (Tageswerte, Verlauf, Plan).
   - `check_fresh.py` warnt bei alten Daten, `nudges.py` legt Mini-Vorschläge in iCloud Drive/Trainingscockpit.
   - Protokoll: `~/garmin/logs/morgenlauf.log`.
2. **Claude-Aufgabe „Trainingscockpit Garmin-Daten“** (stündlich 06:10–11:10, auf dem Mac-Ordner `~/garmin`, nur lesend):
   - liest `dashboard-data.json`,
   - veröffentlicht das Artifact https://claude.ai/artifact/RNbvKqPgmeNJC2JThihJZz neu, die Seite bleibt dabei unverändert, nur die Datei `dashboard-data.json` wird ersetzt,
   - schreibt `sync/garmin` (Datum, letzter Tag mit Daten) in die Artifact-Datenbank.
3. **iPhone:** öffnet die Artifact-Adresse (Lesezeichen, Kurzbefehl `garmin.sh --phone` gibt dieselbe Adresse aus). Die Seite lädt `dashboard-data.json` vom Artifact.
4. **Eingaben vom iPhone** (Check-ins, Häkchen, Abend) speichert die Seite dauerhaft in der privaten Artifact-Datenbank, Sammlung `days/<Datum>`. Nur Florian als Besitzer kann sie lesen und schreiben. Ohne Datenbank (lokale Vorschau) fällt sie auf den Browser-Speicher zurück.

Der Umbau ändert nur Dateien in `web/cockpit/` und fügt die Datei `gesamtzustand.txt` hinzu. `~/garmin`, der launchd-Job, `sync.py` und die Claude-Aufgabe bleiben unverändert. Die Aufgabe ersetzt beim Veröffentlichen nur `dashboard-data.json`, alle anderen Dateien des Artifacts bleiben erhalten.

## Gesundheits-Gesamtübersicht: Aufbau

- **Startkachel (Heute, oben):** Ampel Gesamtzustand, Schlaf, Energie-Akku, Stimmung, darunter der fällige Check-in. Bis 17 Uhr der Morgen-Check-in (wenn offen), ab 17 Uhr der Abend-Check-in.
- **Check-in im Vollbild:** eine Frage pro Bildschirm, zehn große Tasten (1–10) mit Beschriftung für 1, 5 und 10. Nichts ist vorausgewählt, darunter steht klein der letzte Wert. Antippen springt zur nächsten Frage. Morgens 5 Taps bis „Gespeichert“, abends 6. Schmerzen, unterbrochene Nacht, krank bzw. „Was hat Kraft gekostet“ sind danach optional.
- **Übersicht:** Schalter 7 / 30 Tage. Karten für Gesamtzustand (Körper, Kopf, gesamt), Schlaf, Erholung über Nacht (HRV), Stress der Uhr, Energie-Akku (Body Battery), Training in Minuten, Stimmung morgens gegen abends und sechs Check-in-Verläufe. Jede Zahl hat eine Einordnung gegen den eigenen Schnitt der letzten 30 Tage („über deinem Schnitt“), solange zu wenig Werte da sind gegen feste Grenzen („gut“, „niedrig“).
- **Gesamtzustand:** Körper = Schlaf gegen Schlafbedarf, HRV und Stress gegen den eigenen Schnitt, Energie-Akku direkt, jeweils 0–100. Kopf = Check-in-Werte 1–10 auf 0–100 (Stress umgedreht). Fehlende Werte fallen heraus, die übrigen zählen anteilig mehr. Vor dem morgendlichen Abgleich kommen die Körperwerte vom letzten Tag mit Uhrdaten.
- **Gewichte ändern:** `web/cockpit/gesamtzustand.txt`. Nur Zahlen hinter `=` anpassen. Die Datei wird zusammen mit der Seite als Artifact-Datei veröffentlicht; nicht verstandene Zeilen zeigt die Übersicht unter „So rechnet die Ampel“ an. Fehlt die Datei, gelten dieselben Werte eingebaut.
- **Dunkelmodus:** zwischen 4 und 9 Uhr immer dunkel, sonst wie am iPhone eingestellt. Keine externen Schriften oder Anfragen: die Seite lädt nur sich selbst, `dashboard-data.json` und `gesamtzustand.txt`.

## Datenformat der Check-ins

Gespeichert in der privaten Artifact-Datenbank, Dokument `days/<JJJJ-MM-TT>` (im Browser ohne Datenbank: `localStorage["cockpit.days"]`, gleiche Form).

```json
{
  "date": "2026-10-28",
  "am": { "sleep": 7, "energy": 6, "mood": 8, "min": 30, "at": "2026-10-28T05:12:00.000Z" },
  "pm": { "mood": 7, "stress": 4, "focus": 6, "day": 7, "food": 6, "at": "2026-10-28T19:31:00.000Z" },
  "checkin": { "sleep": 4, "energy": 3, "mood": 4, "pain": 5, "night": true, "sick": false },
  "evening": { "drain": ["arbeit"], "screen": true }
}
```

| Feld | Bedeutung | Werte |
|---|---|---|
| `am.sleep` / `am.energy` / `am.mood` | gefühlte Schlafqualität, Energie, Stimmung am Morgen | 1–10 |
| `am.min` | verfügbare Trainingszeit | 0, 10, 20, 30, 45, 60 (= 60 und mehr) Minuten |
| `pm.mood` / `pm.stress` / `pm.focus` / `pm.day` / `pm.food` | Stimmung, Stress, Fokus, Zufriedenheit mit dem Tag, Essen nach Gefühl | 1–10 |
| `am.at` / `pm.at` | Zeitpunkt des Speicherns | ISO-Zeit |
| `checkin.*` | ältere Form (1–5). Neue Morgen-Check-ins schreiben `sleep/energy/mood` umgerechnet mit, damit Tagesmodus und Push-Nachrichten weiterlaufen; `pain/night/sick` kommen aus den optionalen Knöpfen | 1–5 |

Alte Einträge bleiben lesbar: 1–5 wird mit `1 + (x − 1) · 9/4` auf 1–10 umgerechnet (1 → 1, 3 → 5,5, 5 → 10). Alter Abend: `evening.day` wird zu Zufriedenheit, `evening.food` zu Essen („Im Rahmen“ = 8, ein anderes Stichwort = 4, mehrere = 3), der alte Morgen-Stress zählt als Tagesstress.

`dashboard-data.json` (vom Mac, unverändert) liefert pro Tag unter `days[<Datum>]` unter anderem `sleep.asleep` (Sekunden), `parts.sleep.perf` (Schlaf gegen Bedarf, %), `parts.hrv.raw` und `parts.hrv.score`, `stress` (Tagesschnitt 0–100), `bbHigh` (Energie-Akku), `acts[]` (Aktivitäten mit `type`, `min`).

## Was die Tests beweisen

- **Formeln** (`tests/test_formulas.py`): Ampelgrenzen, TRIMP, Strain-Skala, Schlafbedarf, Recovery-Scores und die Auswertung des Morgen-Diktats mit festen Zahlen.
- **Ganzer Durchlauf** (`tests/test_pipeline.py`): `analyze.py` läuft auf 60 ausgedachten Tagen durch, Recovery liegt zwischen 0 und 100 und passt zur Ampel, die Frische-Warnung schlägt bei 7 Tage alten Daten an und schweigt bei frischen.
- **Seiten** (`tests/pages.cjs`): Cockpit und Tagescoach laden ohne JavaScript-Fehler, alle Bereiche öffnen sich, der Hinweis auf fehlende Daten erscheint nur, wenn er soll, und auf Handybreite gibt es keinen seitlichen Bildlauf.
- **Gesamtübersicht** (`tests/pages.cjs`, Tests „Gesamtübersicht …“): Check-in neutral mit Hinweis auf den letzten Wert, höchstens 6 Taps, passender Check-in zur Uhrzeit, alte Einträge lesbar, 30 Tage Beispieldaten füllen alle Diagramme bei 7 und 30 Tagen, Gewichte aus der Datei wirken, Startkachel ohne Scrollen, Touch-Ziele ab 44 px, morgens dunkel, Ladezeit unter 2 Sekunden.
- **Echte Daten** (`tests/echte_daten.cjs`, nur lokal): liest eine Kopie von `~/garmin/dashboard-data.json` und vergleicht Startkachel und Diagramme mit den Werten in der Datei.
- **Screenshots** (`tests/screenshots.cjs`): alle Ansichten bei 390 px Breite.
- **Gleichheit bei Umbauten** (`tests/equivalence.py`, nur lokal mit echten Daten): vergleicht die Ausgabe zweier Stände von `analyze.py` Feld für Feld.

GitHub Actions führt die ersten drei bei jedem Push aus.

```sh
python -m pytest -q
python tests/make_fixture.py /tmp/fx && cp mac/analyze.py mac/formulas.py /tmp/fx/ && (cd /tmp/fx && python analyze.py)
node tests/pages.cjs /tmp/fx/dashboard-data.json      # nutzt /tmp/fx/checkins.json (30 Tage Beispiel-Check-ins)
node tests/screenshots.cjs /tmp/fx/dashboard-data.json /tmp/shots
node tests/echte_daten.cjs KOPIE/dashboard-data.json   # Kopie vom Mac, nie ins Repo
```

## Persönliche Daten

`data.json`, `history.json`, `dashboard-data.json`, Pläne, Logs und die Garmin-Anmeldung (`~/.garminconnect`) gehören nie ins Repo; `.gitignore` schließt sie aus.

## Auf den Mac bringen

Nach einem Merge die Dateien aus `mac/` nach `~/garmin` kopieren (nichts anderes dort überschreiben). Seiten werden als Artifact veröffentlicht.

## Prüfliste Bedienung (28.10.2026, Screenshots bei 390 px)

Geprüft mit `node tests/screenshots.cjs` (29 Bilder: Heute morgens, mittags, abends, jede Check-in-Frage, Gespeichert, Übersicht 7 und 30 Tage, Training, Essen, Mehr und alle Unterbereiche) und den Tests „Gesamtübersicht …“.

| Punkt | Ergebnis |
|---|---|
| Check-in nur mit dem Daumen, ohne Text | erfüllt: nur Tasten, Freitext gibt es im Check-in nicht mehr |
| höchstens 6 Taps bis „Gespeichert“ | erfüllt: morgens 5, abends 6 (Test zählt mit) |
| große Tasten, Touch-Ziele ab 44 px | erfüllt: Skalentasten 60 px hoch, alle Knöpfe im Check-in ≥ 44 × 44 px (Test) |
| Start neutral, letzter Wert klein als Hinweis | erfüllt: nichts vorausgewählt, „Zuletzt: 5 (Di 27.10.)“ |
| Beschriftung für 1, 5 und 10 | erfüllt, unter jeder Skala |
| Startbildschirm ohne Scrollen: Gesamtzustand, 3 Werte, Check-in-Knopf | erfüllt: Startkachel endet über der unteren Leiste (Test misst) |
| ein Gedanke pro Bildschirm | erfüllt im Check-in (eine Frage je Bildschirm) und in der Übersicht (eine Karte je Wert) |
| klare Sprache, Zahlen mit Einordnung | erfüllt: „Energie-Akku“, „Erholung über Nacht“, jede Zahl mit „über/unter deinem Schnitt“, „gut“ usw. (Test) |
| Dunkelmodus morgens | erfüllt: 4–9 Uhr dunkel (Test um 6 und 13 Uhr) |
| Ladezeit unter 2 Sekunden | erfüllt: ca. 120–200 ms bis zur Startkachel in Playwright (Test) |
| kein seitlicher Bildlauf bei 390 px | erfüllt in allen 29 Bildern (`bericht.txt`) |

Beim Durchsehen behoben: Einordnung im „Gespeichert“-Bildschirm war farblos, optionale Knöpfe hatten keinen Rahmen, „Noch etwas?“ war nicht als aufklappbar erkennbar, der Check-in-Knopf stand doppelt auf „Heute“, die Achsen der 1–10-Verläufe zeigten 6 statt 5 als Mitte.

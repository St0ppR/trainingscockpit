# Trainingscockpit

Florians tägliches Trainings- und Gesundheits-Cockpit: Garmin-Daten vom Mac, ausgewertet zu Recovery, Belastung und Schlafbedarf, plus Tagescoach für Check-in, Training und Gewohnheiten.

| Ordner | Inhalt |
|---|---|
| `mac/` | Läuft auf dem Mac in `~/garmin`: `sync.py` (Garmin Connect), `analyze.py` (Auswertung), `formulas.py` (reine Formeln), `check_fresh.py` (Warnung bei alten Daten), `nudges.py` (Mini-Vorschläge nach iCloud Drive fürs iPhone, Anleitung in `docs/iphone-mini-vorschlaege.md`), `garmin.sh`, launchd-Job |
| `web/cockpit/` | Seite des Trainingscockpits (Claude-Artifact). Start ist **Heute** (Morgen-Ablauf in 4 Schritten, ab 17 Uhr Abend-Reflexion zum Antippen, Check-in, Tagesmodus, Tipp, Training in 3 Stufen, Mini-Vorschläge, Kopf, Gewohnheiten), daneben **Übersicht** (Woche, Trends, Erkenntnisse mit Alltagstipp) |
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

## Was die Tests beweisen

- **Formeln** (`tests/test_formulas.py`): Ampelgrenzen, TRIMP, Strain-Skala, Schlafbedarf, Recovery-Scores und die Auswertung des Morgen-Diktats mit festen Zahlen.
- **Ganzer Durchlauf** (`tests/test_pipeline.py`): `analyze.py` läuft auf 60 ausgedachten Tagen durch, Recovery liegt zwischen 0 und 100 und passt zur Ampel, die Frische-Warnung schlägt bei 7 Tage alten Daten an und schweigt bei frischen.
- **Seiten** (`tests/pages.cjs`): Cockpit und Tagescoach laden ohne JavaScript-Fehler, alle Bereiche öffnen sich, der Hinweis auf fehlende Daten erscheint nur, wenn er soll, und auf Handybreite gibt es keinen seitlichen Bildlauf.
- **Gleichheit bei Umbauten** (`tests/equivalence.py`, nur lokal mit echten Daten): vergleicht die Ausgabe zweier Stände von `analyze.py` Feld für Feld.

GitHub Actions führt die ersten drei bei jedem Push aus.

```sh
python -m pytest -q
python tests/make_fixture.py /tmp/fx && cp mac/analyze.py mac/formulas.py /tmp/fx/ && (cd /tmp/fx && python analyze.py)
node tests/pages.cjs /tmp/fx/dashboard-data.json
```

## Persönliche Daten

`data.json`, `history.json`, `dashboard-data.json`, Pläne, Logs und die Garmin-Anmeldung (`~/.garminconnect`) gehören nie ins Repo; `.gitignore` schließt sie aus.

## Auf den Mac bringen

Nach einem Merge die Dateien aus `mac/` nach `~/garmin` kopieren (nichts anderes dort überschreiben). Seiten werden als Artifact veröffentlicht.

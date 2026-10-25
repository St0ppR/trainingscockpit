# Trainingscockpit

Florians tägliches Trainings- und Gesundheits-Cockpit: Garmin-Daten vom Mac, ausgewertet zu Recovery, Belastung und Schlafbedarf, plus Tagescoach für Check-in, Training und Gewohnheiten.

| Ordner | Inhalt |
|---|---|
| `mac/` | Läuft auf dem Mac in `~/garmin`: `sync.py` (Garmin Connect), `analyze.py` (Auswertung), `formulas.py` (reine Formeln), `check_fresh.py` (Warnung bei alten Daten), `garmin.sh`, launchd-Job |
| `web/cockpit/` | Seite des Trainingscockpits (Claude-Artifact). Start ist **Heute** (Morgen-Ablauf in 4 Schritten, ab 17 Uhr Abend-Reflexion zum Antippen, Check-in, Tagesmodus, Tipp, Training in 3 Stufen, Mini-Vorschläge, Kopf, Gewohnheiten), daneben **Übersicht** (Woche, Trends, Erkenntnisse mit Alltagstipp) |
| `web/tagescoach/` | Alter, eigenständiger Tagescoach; steckt jetzt im Cockpit und kann nach dem Umzug der Daten weg |
| `tests/` | Tests; `make_fixture.py` erzeugt ausgedachte Garmin-Daten |
| `COACH.md` | Leitfaden für den Coach (Plan-Schema, Übungen) |

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

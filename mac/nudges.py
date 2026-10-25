#!/usr/bin/env python3
"""
nudges.py – Mini-Vorschläge für zwischendurch aufs iPhone.

Liest dashboard-data.json (von analyze.py) und legt zwei kurze Vorschläge für den Tag in iCloud Drive ab:
  Trainingscockpit/vorschlag-vormittag.txt   (das iPhone zeigt ihn z. B. um 10:00)
  Trainingscockpit/vorschlag-nachmittag.txt  (z. B. um 14:30)
Die Vorschläge passen zur Erholung laut Uhr und sind dieselben wie unter „Heute → Für zwischendurch“ im Cockpit.
Ohne frische Daten gilt „gelb“. Nur Standardbibliothek.
Aufruf:  python nudges.py [ZIELORDNER]   (Standard: iCloud Drive/Trainingscockpit)
"""
import json, sys, datetime as dt
from pathlib import Path

ICLOUD = Path.home() / "Library/Mobile Documents/com~apple~CloudDocs/Trainingscockpit"

# gleiche Liste wie TC_NUDGE_POOL in web/cockpit/index.html; {n} = Wiederholungen je nach Erholung
POOL = {
    "push": ("{n} Liegestütze an der Schreibtischkante", "Körper gerade, Brust zur Kante"),
    "squat": ("{n} Kniebeugen zum Stuhl", "Po tippt kurz an, Knie nach außen"),
    "calf": ("Wadenheben einbeinig, 2 × 12 pro Seite", "3 s runter – macht das Sprunggelenk stabil"),
    "kneewall": ("Knie zur Wand, 10 pro Seite", "Ferse bleibt unten – mehr Beweglichkeit im Sprunggelenk"),
    "hipflex": ("Hüftbeuger dehnen, 45 s pro Seite", "gegen das lange Sitzen und den steifen Rücken"),
    "tspine": ("Oberkörper drehen am Stuhl, 8 pro Seite", "Hände vor der Brust, aus dem oberen Rücken drehen"),
    "sigh": ("3 tiefe Doppel-Einatmer", "zweimal kurz durch die Nase ein, lang durch den Mund aus – runter vom Stress"),
    "box": ("2 Minuten Box-Atmung", "4 s ein · 4 halten · 4 aus · 4 halten"),
    "arrive": ("1 Minute ankommen", "Füße spüren, 5 Dinge sehen, 3 hören – dann erst weiter"),
    "protein": ("Eiweiß-Snack um halb vier", "Skyr, Quark oder Nüsse – dann kippt der Abend seltener"),
    "walk": ("5 Minuten raus, ohne Handy", "nach einer kurzen Nacht besser als jede Übung"),
}
REPS = {"green": {"push": 20, "squat": 25}, "yellow": {"push": 12, "squat": 15}}
SHORT_SLEEP_H = 6.5


def item(nid, band):
    t, d = POOL[nid]
    return nid, t.replace("{n}", str(REPS.get(band, REPS["yellow"]).get(nid, ""))), d


def pick(payload, today):
    """-> (band, [(Zeitfenster, Titel, Detail), ...], Hinweis oder None).
    Vormittags etwas für Kraft und Wochenziele (rot/kurze Nacht: raus an die Luft),
    nachmittags im Wechsel Sprunggelenk, Eiweiß vor dem Heißhunger, Hüfte gegen das Sitzen."""
    day = (payload.get("days") or {}).get(today) or {}
    fresh = payload.get("lastWithData") == today
    band = day.get("band") if fresh and day.get("band") in ("red", "yellow", "green") else "yellow"
    sleep = day.get("sleep") or {}
    hours = sleep["asleep"] / 3600 if fresh and sleep.get("asleep") else None
    short = hours is not None and hours < SHORT_SLEEP_H
    if short and band == "green":
        band = "yellow"   # kurze Nacht: kein Vollgas, auch wenn die Werte gut sind
    note = f"Kurze Nacht ({hours:.1f} h) – heute lieber ruhig." if short else None
    k = dt.date.fromisoformat(today).toordinal()
    am = "walk" if band == "red" or short else ("squat" if k % 2 else "push")
    pm = ("calf", "protein", "hipflex")[k % 3]
    slots = [("vormittag",) + item(am, band)[1:], ("nachmittag",) + item(pm, band)[1:]]
    return band, slots, note


def text(title, detail, note):
    return f"{title} – {detail}" + (f"\n{note}" if note else "") + "\nAbhaken im Cockpit: Heute → Für zwischendurch"


def main(here, out=None, today=None):
    here = Path(here); out = Path(out) if out else ICLOUD
    today = today or dt.date.today().isoformat()
    try:
        payload = json.loads((here / "dashboard-data.json").read_text(encoding="utf-8"))
    except Exception:
        payload = {}
    band, slots, note = pick(payload, today)
    try:
        out.mkdir(parents=True, exist_ok=True)
        for slot, title, detail in slots:
            (out / f"vorschlag-{slot}.txt").write_text(text(title, detail, note), encoding="utf-8")
        (out / "vorschlaege.json").write_text(json.dumps(
            {"date": today, "band": band, "note": note,
             "slots": [{"slot": s, "title": t, "detail": d} for s, t, d in slots]}, ensure_ascii=False, indent=1), encoding="utf-8")
    except OSError as e:
        print(f"Mini-Vorschläge nicht geschrieben ({out}): {e}")
        return 1
    print(f"Mini-Vorschläge ({band}): " + " | ".join(t for _, t, _ in slots))
    return 0


if __name__ == "__main__":
    sys.exit(main(Path(__file__).resolve().parent, sys.argv[1] if len(sys.argv) > 1 else None))

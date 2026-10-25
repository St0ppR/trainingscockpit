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

# gleiche Liste wie TC_NUDGES in web/cockpit/index.html
NUDGES = {
    "red": [("2 Minuten Box-Atmung", "4 s ein · 4 halten · 4 aus · 4 halten"),
            ("5 Minuten gehen", "einmal ums Gebäude oder den Flur entlang"),
            ("Ein großes Glas Wasser", "hilft auch gegen den Nachmittags-Hunger")],
    "yellow": [("10 Kniebeugen am Schreibtisch", "langsam, Stuhl als Ziel"),
               ("Treppe statt Aufzug", "2 Stockwerke, ruhig atmen"),
               ("Hüftbeuger-Dehnung", "45 s pro Seite gegen das Sitzen")],
    "green": [("20 Kniebeugen", "zügig, volle Tiefe"),
              ("15 Liegestütze an der Schreibtischkante", "Körper gerade"),
              ("Treppe hoch, 2× hintereinander", "zügig, oben kurz durchatmen")],
}
SHORT_SLEEP_H = 6.5


def pick(payload, today):
    """-> (band, [(Zeitfenster, Titel, Detail), ...], Hinweis oder None) für den Tag."""
    day = (payload.get("days") or {}).get(today) or {}
    fresh = payload.get("lastWithData") == today
    band = day.get("band") if fresh and day.get("band") in NUDGES else "yellow"
    sleep = day.get("sleep") or {}
    hours = sleep["asleep"] / 3600 if fresh and sleep.get("asleep") else None
    if hours is not None and hours < SHORT_SLEEP_H and band == "green":
        band = "yellow"   # kurze Nacht: kein Vollgas, auch wenn die Werte gut sind
    note = f"Kurze Nacht ({hours:.1f} h) – heute lieber ruhig." if hours is not None and hours < SHORT_SLEEP_H else None
    lst, k = NUDGES[band], dt.date.fromisoformat(today).toordinal()
    slots = [("vormittag",) + lst[k % 3], ("nachmittag",) + lst[(k + 1) % 3]]
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

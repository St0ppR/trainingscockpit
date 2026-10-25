#!/usr/bin/env python3
"""Gibt die Frage fuer den iPhone-Kurzbefehl aus: Tagesempfehlung und drei Varianten aus plan.json fuer heute."""
import json, datetime as dt
from pathlib import Path
HERE = Path(__file__).resolve().parent
today = dt.date.today().isoformat()
pj = None
for f in (HERE / "plan.json", HERE / f"plan-{today}.json"):
    try:
        cand = json.loads(f.read_text(encoding="utf-8"))
        if cand.get("date") == today and cand.get("options"):
            pj = cand; break
    except Exception:
        pass
if pj:
    focus = pj.get("focus")
    print(f"Empfehlung heute: {focus}" if focus else "Drei Varianten für heute:")
    for o in pj["options"][:3]:
        label = o.get("label")
        print(f"{o.get('id')}: " + (f"{label} – " if label else "") + (o.get("short") or o.get("title") or ""))
    print("Welche Variante, und wie viel Zeit hast du?")
else:
    print("Worauf hast du heute Lust (Kraft, Ausdauer oder Beweglichkeit)? Sag dazu, wie viel Zeit du hast.")

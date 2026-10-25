#!/usr/bin/env python3
"""
check_fresh.py – Warnung bei veralteten Daten.

Liest dashboard-data.json (von analyze.py) und prueft:
  - Lief der Garmin-Sync in den letzten 26 Stunden?  (lastSync)
  - Ist der letzte Tag mit Daten hoechstens gestern?  (lastWithData; heute fehlt morgens oft noch)
Bei einem Problem: Warnzeile oben in summary.txt, Eintrag in logs/frische.log und eine
macOS-Mitteilung. Exit-Code 1, damit es im Log auffaellt.  Nur Standardbibliothek.
"""
import json, subprocess, sys, datetime as dt
from pathlib import Path

SYNC_MAX_H = 26
DATA_MAX_DAYS = 1


def warnings(payload, now):
    """Liste deutscher Warntexte; leer, wenn alles frisch ist. now: naive Ortszeit."""
    out = []
    ls = payload.get("lastSync")
    if not ls:
        out.append("Garmin-Sync: kein Zeitstempel – sync.py ist wohl nie durchgelaufen.")
    else:
        age_h = (now - dt.datetime.fromisoformat(ls[:19])).total_seconds() / 3600
        if age_h > SYNC_MAX_H:
            out.append(f"Garmin-Sync lief zuletzt vor {age_h / 24:.0f} Tagen ({ls[:10]}). Anmeldung oder Netz prüfen: ./garmin.sh von Hand starten.")
    lw = payload.get("lastWithData")
    if not lw:
        out.append("Noch keine Tage mit Recovery-Daten.")
    else:
        age_d = (now.date() - dt.date.fromisoformat(lw)).days
        if age_d > DATA_MAX_DAYS:
            out.append(f"Letzte Nacht mit Daten ist {age_d} Tage alt ({lw}). Uhr in der Garmin-App synchronisieren.")
    return out


def notify(text):
    try:
        subprocess.run(["osascript", "-e", f'display notification {json.dumps(text)} with title "Trainingscockpit"'],
                       check=False, timeout=10)
    except Exception:
        pass   # kein macOS (z. B. in CI)


def main(here, now=None):
    here = Path(here); now = now or dt.datetime.now()
    try:
        payload = json.loads((here / "dashboard-data.json").read_text(encoding="utf-8"))
    except Exception as e:
        payload = {}; ws = [f"dashboard-data.json nicht lesbar ({type(e).__name__}) – analyze.py prüfen."]
    else:
        ws = warnings(payload, now)
    if not ws:
        print("Daten frisch."); return 0
    text = "\n".join("⚠ " + w for w in ws)
    print(text)
    sp = here / "summary.txt"
    old = sp.read_text(encoding="utf-8") if sp.exists() else ""
    sp.write_text(text + "\n" + old, encoding="utf-8")
    (here / "logs").mkdir(exist_ok=True)
    with open(here / "logs" / "frische.log", "a", encoding="utf-8") as f:
        f.write(f"{now:%Y-%m-%d %H:%M} | " + " | ".join(ws) + "\n")
    notify(ws[0])
    return 1


if __name__ == "__main__":
    sys.exit(main(Path(__file__).resolve().parent))

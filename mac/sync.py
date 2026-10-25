#!/usr/bin/env python3
"""
Garmin-Sync -> data.json

- Holt pro Tag die KOMPLETTEN Garmin-Antworten (nichts wird weggefiltert).
- Erster Lauf: fragt E-Mail + Passwort (Passwort unsichtbar, wird nicht gespeichert).
- Danach: nutzt nur das Anmelde-Token in ~/.garminconnect (kein Passwort mehr noetig).
- Inkrementell: bereits geladene Tage werden uebersprungen, die letzten 3 Tage
  werden immer neu geholt (Garmin ergaenzt Werte oft noch nachtraeglich).

Aufruf:  .venv/bin/python sync.py            (90 Tage)
         .venv/bin/python sync.py --days 30
         .venv/bin/python sync.py --full     (alles neu laden)
"""
import argparse, datetime as dt, getpass, json, os, sys, time
from pathlib import Path

try:
    from garminconnect import Garmin
except ImportError:
    sys.exit("garminconnect fehlt. Bitte zuerst:  .venv/bin/pip install garminconnect")

HERE = Path(__file__).resolve().parent
OUT = HERE / "data.json"
TOKENS = Path(os.path.expanduser("~/.garminconnect"))

# Alles, was pro Tag geholt wird. Name -> Methode der garminconnect-Bibliothek.
DAILY = {
    "sleep":              "get_sleep_data",          # dailySleepDTO + sleepLevels (Hypnogramm)
    "hrv":                "get_hrv_data",            # Nacht-HRV + Baseline-Band
    "rhr":                "get_rhr_day",
    "stats":              "get_stats",               # Tageszusammenfassung (Schritte, RHR, Stress ...)
    "stress":             "get_stress_data",
    "body_battery":       "get_body_battery",
    "respiration":        "get_respiration_data",
    "spo2":               "get_spo2_data",
    "training_readiness": "get_training_readiness",
    "training_status":    "get_training_status",
    "heart_rates":        "get_heart_rates",
}


def login():
    # 1) Gespeichertes Token versuchen
    if TOKENS.exists():
        try:
            g = Garmin()
            g.login(str(TOKENS))
            print("Angemeldet mit gespeichertem Token.")
            return g
        except Exception as e:
            print(f"Token nicht (mehr) gueltig ({type(e).__name__}) - bitte neu anmelden.")

    # 2) Interaktiver Login - im automatischen Morgenlauf nicht moeglich
    if not sys.stdin.isatty():
        sys.exit("SYNC ABGEBROCHEN: Anmelde-Token fehlt oder ist abgelaufen. "
                 "Bitte einmal im Terminal ausfuehren:  cd ~/garmin && ./garmin.sh")
    email = input("Garmin E-Mail: ").strip()
    pw = getpass.getpass("Garmin Passwort (unsichtbar): ")
    g = Garmin(email=email, password=pw,
               prompt_mfa=lambda: input("Zwei-Faktor-Code: ").strip())
    g.login()
    del pw
    TOKENS.mkdir(mode=0o700, exist_ok=True)
    for attr in ("garth", "client"):
        obj = getattr(g, attr, None)
        if obj is not None and hasattr(obj, "dump"):
            obj.dump(str(TOKENS))
            break
    os.chmod(TOKENS, 0o700)
    print(f"Angemeldet. Token gespeichert in {TOKENS}")
    return g


def call(g, method, *args):
    fn = getattr(g, method, None)
    if fn is None:
        return {"_error": f"Methode {method} gibt es in dieser garminconnect-Version nicht"}
    for attempt in range(3):
        try:
            return fn(*args)
        except Exception as e:
            msg = f"{type(e).__name__}: {e}"
            if "429" in msg or "Too Many" in msg:
                time.sleep(10 * (attempt + 1))
                continue
            return {"_error": msg[:300]}
    return {"_error": "rate limited"}


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("--days", type=int, default=90)
    ap.add_argument("--full", action="store_true")
    a = ap.parse_args()

    data = {"days": {}, "activities": {}, "meta": {}}
    if OUT.exists() and not a.full:
        data = json.loads(OUT.read_text())
        data.setdefault("days", {}); data.setdefault("activities", {}); data.setdefault("meta", {})

    g = login()
    today = dt.date.today()
    dates = [(today - dt.timedelta(days=i)).isoformat() for i in range(a.days)][::-1]
    refresh = {(today - dt.timedelta(days=i)).isoformat() for i in range(3)}

    todo = [d for d in dates if d not in data["days"] or d in refresh]
    print(f"{len(todo)} Tage zu laden ({dates[0]} bis {dates[-1]}) ...")
    for n, d in enumerate(todo, 1):
        day = {k: call(g, m, d) for k, m in DAILY.items()}
        day["_fetched"] = dt.datetime.now().isoformat(timespec="seconds")
        data["days"][d] = day
        print(f"  [{n}/{len(todo)}] {d}", end="\r", flush=True)
        if n % 10 == 0:
            OUT.write_text(json.dumps(data))      # Zwischenstand sichern
    print()

    # Aktivitaeten: Zusammenfassung + Detail (Herzfrequenz-Verlauf fuer TRIMP)
    acts = call(g, "get_activities_by_date", dates[0], dates[-1]) or []
    if isinstance(acts, dict):
        print("Aktivitaeten-Fehler:", acts.get("_error")); acts = []
    new = 0
    for act in acts:
        aid = str(act.get("activityId"))
        entry = data["activities"].get(aid, {})
        entry["summary"] = act
        if "details" not in entry or act.get("startTimeLocal", "")[:10] in refresh:
            entry["details"] = call(g, "get_activity_details", act.get("activityId"), 2000, 4000)
            new += 1
        data["activities"][aid] = entry
    print(f"{len(acts)} Aktivitaeten im Zeitraum, {new} Detail-Abrufe.")

    data["meta"] = {
        "last_sync": dt.datetime.now().isoformat(timespec="seconds"),
        "range": [min(data["days"]), max(data["days"])],
        "garminconnect_version": getattr(sys.modules.get("garminconnect"), "__version__", "?"),
    }
    OUT.write_text(json.dumps(data))
    errs = sum(1 for d in data["days"].values() for v in d.values() if isinstance(v, dict) and "_error" in v)
    print(f"Fertig: {OUT}  ({len(data['days'])} Tage, {len(data['activities'])} Aktivitaeten, {errs} Einzelfehler)")


if __name__ == "__main__":
    main()

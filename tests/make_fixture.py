#!/usr/bin/env python3
"""
Erzeugt ausgedachte Garmin-Rohdaten (data.json) im Format von sync.py.

Keine echten Messwerte: Ruhepuls, HRV, Schlaf und Aktivitaeten werden mit festem Zufallsstartwert
erfunden. So laesst sich analyze.py in CI komplett durchlaufen, ohne persoenliche Daten im Repo.
Aufruf:  python tests/make_fixture.py ZIELORDNER [--days 60] [--end JJJJ-MM-TT]
"""
import argparse, json, random, datetime as dt
from zoneinfo import ZoneInfo
from pathlib import Path


def gmt(d):  return d.strftime("%Y-%m-%dT%H:%M:%S.0")
def ms(d):   return int(d.replace(tzinfo=dt.timezone.utc).timestamp() * 1000)


def make(days=60, end=None, seed=7):
    rnd = random.Random(seed)
    end = end or dt.datetime.now(ZoneInfo("Europe/Berlin")).date()   # wie analyze.py
    out = {"days": {}, "activities": {}, "meta": {"last_sync": f"{end.isoformat()}T07:30:00",
                                                  "range": [(end - dt.timedelta(days=days - 1)).isoformat(), end.isoformat()]}}
    for i in range(days):
        day = end - dt.timedelta(days=days - 1 - i); k = day.isoformat()
        rhr = rnd.randint(52, 62); hrv = rnd.randint(30, 55)
        # Schlaf: Einschlafen ~22:30 Ortszeit (= 20:30 GMT im Sommer, egal fuer den Test)
        start = dt.datetime.combine(day - dt.timedelta(days=1), dt.time(20, 30)) + dt.timedelta(minutes=rnd.randint(-40, 60))
        stages, t = [], start
        sums = {0: 0, 1: 0, 2: 0, 3: 0}
        for _ in range(rnd.randint(14, 20)):
            lvl = rnd.choice([0, 1, 1, 2, 3]); dur = rnd.randint(10, 40) * 60
            stages.append({"startGMT": gmt(t), "endGMT": gmt(t + dt.timedelta(seconds=dur)), "activityLevel": float(lvl)})
            sums[lvl] += dur; t += dt.timedelta(seconds=dur)
        sleep_s = sums[0] + sums[1] + sums[2]
        # Herzfrequenz alle 2 Minuten, eine Trainingsspitze an jedem dritten Tag
        hr, t0 = [], dt.datetime.combine(day, dt.time(6, 0))
        for j in range(0, 16 * 30):
            bpm = rnd.randint(rhr + 5, rhr + 35)
            if i % 3 == 0 and 300 <= j < 330: bpm = rnd.randint(130, 170)
            hr.append([ms(t0 + dt.timedelta(minutes=2 * j)), bpm])
        out["days"][k] = {
            "sleep": {"dailySleepDTO": {"sleepTimeSeconds": sleep_s, "napTimeSeconds": 0,
                                        "deepSleepSeconds": sums[0], "lightSleepSeconds": sums[1],
                                        "remSleepSeconds": sums[2], "awakeSleepSeconds": sums[3],
                                        "sleepStartTimestampGMT": ms(start), "sleepEndTimestampGMT": ms(t)},
                      "sleepLevels": stages},
            "hrv": {"hrvSummary": {"lastNightAvg": hrv}},
            "stats": {"restingHeartRate": rhr, "totalSteps": rnd.randint(3000, 14000),
                      "bodyBatteryHighestValue": rnd.randint(50, 100), "bodyBatteryLowestValue": rnd.randint(5, 40),
                      "averageStressLevel": rnd.randint(20, 45),
                      "moderateIntensityMinutes": rnd.randint(0, 40), "vigorousIntensityMinutes": rnd.randint(0, 20)},
            "heart_rates": {"heartRateValues": hr},
        }
        if i % 3 == 0:
            aid = 1000 + i
            out["activities"][str(aid)] = {"summary": {
                "activityId": aid, "startTimeLocal": f"{k} 16:00:00", "activityType": {"typeKey": "strength_training"},
                "activityName": "Kraft", "duration": 2400.0, "activityTrainingLoad": rnd.uniform(40, 120),
                "averageHR": 120, "maxHR": rnd.choice([178, 180, 181]),
                **{f"hrTimeInZone_{z}": 400.0 for z in range(1, 6)},
                "aerobicTrainingEffect": 2.5, "anaerobicTrainingEffect": 1.0, "trainingEffectLabel": "TEMPO", "calories": 300}}
    return out


if __name__ == "__main__":
    ap = argparse.ArgumentParser()
    ap.add_argument("target"); ap.add_argument("--days", type=int, default=60); ap.add_argument("--end")
    a = ap.parse_args()
    end = dt.date.fromisoformat(a.end) if a.end else None
    Path(a.target).mkdir(parents=True, exist_ok=True)
    (Path(a.target) / "data.json").write_text(json.dumps(make(a.days, end)), encoding="utf-8")

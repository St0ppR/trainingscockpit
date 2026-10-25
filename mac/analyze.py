#!/usr/bin/env python3
"""
analyze.py – die Analyse-Engine.

Liest  data.json     (Garmin-Sync, letzte 90 Tage, komplette Rohantworten)
       history.json  (lange Historie seit 2021 aus dem Export, waechst mit jedem Sync)
Schreibt dashboard-data.json  (alles, was das Dashboard und der Coach brauchen)
         dashboard.html       (lokale Kopie der Seite mit eingebetteten Daten, optional)

Nur Python-Standardbibliothek.  Aufruf:  .venv/bin/python analyze.py
Jede Zahl auf der Seite stammt aus einem Feld der Rohdaten oder aus einer Formel hier.
"""
import json, math, random, sys, statistics as S, datetime as dt
from collections import defaultdict, Counter
from pathlib import Path
from zoneinfo import ZoneInfo
from formulas import clamp, band, trimp, strain_from, f_strain, sleep_debt, hrv_score, rhr_score, sleep_score, parse_said

HERE = Path(__file__).resolve().parent
TZ = ZoneInfo("Europe/Berlin")

# =========================== Parameter ===========================================
SLEEP_BASE_H   = 8.0     # Schlafbedarf-Basis (Garmin nennt fuer dich 7 h 50)
RHR_WINDOW     = 30      # Tage fuer Ruhepuls-Baseline
NAP_CUTOFF_H   = 4.0     # Naechte darunter: nicht in Schlaf-Baseline
W              = {"hrv": 0.50, "rhr": 0.25, "sleep": 0.25}
# Tages-Strain aus Ganztages-Herzfrequenz (TRIMPexp). Kalibriert auf deine Daten:
#   Ruhetag ~2-4 · 20-min-HIIT ~10 · harte Radtour ~14-16 · 11-h-Bergtour ~20
TRIMP_MIN_HRR  = 0.30    # Minuten unter 30 % Herzfrequenzreserve zaehlen nicht (Alltag/Sitzen)
STRAIN_K       = 5.0
STRAIN_TCAP    = 1500.0  # TRIMP, der Strain 21 ergibt
TARGET = {"green": [14.0, 18.0], "yellow": [9.0, 13.5], "red": [0.0, 8.0]}
CATS = {  # Aktivitaetstyp -> Kategorie
    "strength_training": "kraft", "hiit": "intervall", "indoor_cardio": "intervall",
    "cycling": "ausdauer", "road_biking": "ausdauer", "indoor_cycling": "ausdauer", "mountain_biking": "ausdauer",
    "gravel_cycling": "ausdauer", "running": "ausdauer", "trail_running": "ausdauer", "treadmill_running": "ausdauer",
    "hiking": "ausdauer", "walking": "ausdauer", "stair_climbing": "ausdauer", "lap_swimming": "ausdauer",
    "open_water_swimming": "ausdauer", "stand_up_paddleboarding_v2": "ausdauer", "rowing": "ausdauer",
    "indoor_rowing": "ausdauer", "elliptical": "ausdauer", "e_bike_fitness": "ausdauer",
    "breathwork": "erholung", "yoga": "erholung", "pilates": "erholung", "mobility": "erholung", "meditation": "erholung",
}
STAGE = {0: "deep", 1: "light", 2: "rem", 3: "awake"}   # verifiziert gegen dailySleepDTO (Schritt 3)

# =========================== Helfer ===============================================
def g(o, *ks):
    for k in ks:
        if not isinstance(o, dict): return None
        o = o.get(k)
    return o
P = dt.date.fromisoformat
iso = lambda d: d.isoformat()
def prev(day, n=1): return iso(P(day) - dt.timedelta(days=n))
def gmt_ms(s): return dt.datetime.fromisoformat(s.split(".")[0]).replace(tzinfo=dt.timezone.utc).timestamp() * 1000
def hhmm_local(ms):
    return dt.datetime.fromtimestamp(ms / 1000, dt.timezone.utc).astimezone(TZ).strftime("%H:%M")
def clock_min(hhmm):           # Minuten ab Mittag (damit 23:30 < 00:30)
    h, m = map(int, hhmm.split(":")); v = h * 60 + m
    return v + 1440 if v < 720 else v
def min_to_clock(v):
    v = round(v) % 1440; return f"{v // 60:02d}:{v % 60:02d}"
def mean(v): v = [x for x in v if x is not None]; return S.mean(v) if v else None
def sd(v): v = [x for x in v if x is not None]; return S.stdev(v) if len(v) > 1 else None
def r1(x, n=1): return None if x is None else round(x, n)

data = json.loads((HERE / "data.json").read_text())
D = data["days"]
HP = HERE / "history.json"
hist = json.loads(HP.read_text()) if HP.exists() else {"days": {}}
H = hist["days"]

# =========================== 1. Sync-Tage in die Historie =========================
sync_acts = defaultdict(list)
for a in data["activities"].values():
    s = a["summary"]
    k = s["startTimeLocal"][:10]
    sync_acts[k].append({
        "id": s.get("activityId"), "time": s["startTimeLocal"][11:16], "type": g(s, "activityType", "typeKey") or "",
        "name": s.get("activityName") or "", "min": round((s.get("duration") or 0) / 60),
        "load": r1(s.get("activityTrainingLoad") or 0), "avgHR": s.get("averageHR"), "maxHR": s.get("maxHR"),
        "z": [round(s.get(f"hrTimeInZone_{i}") or 0) for i in range(1, 6)],
        "te": s.get("aerobicTrainingEffect"), "ate": s.get("anaerobicTrainingEffect"),
        "label": s.get("trainingEffectLabel"), "kcal": s.get("calories"),
    })

for k, day in D.items():
    h = H.setdefault(k, {})
    dto = g(day, "sleep", "dailySleepDTO") or {}
    st = day.get("stats") or {}
    for key, val in (("hrv", g(day, "hrv", "hrvSummary", "lastNightAvg")), ("rhr", st.get("restingHeartRate")),
                     ("slp", dto.get("sleepTimeSeconds")), ("steps", st.get("totalSteps")),
                     ("bbHigh", st.get("bodyBatteryHighestValue")), ("bbLow", st.get("bodyBatteryLowestValue"))):
        if val: h[key] = val
    if (st.get("averageStressLevel") or -1) >= 0: h["stress"] = st["averageStressLevel"]
    if st.get("vigorousIntensityMinutes") is not None:
        h["im"] = (st.get("moderateIntensityMinutes") or 0) + 2 * (st.get("vigorousIntensityMinutes") or 0)
    if dto.get("napTimeSeconds") is not None: h["nap"] = dto["napTimeSeconds"]
    if dto.get("deepSleepSeconds") is not None:
        for sk, f in (("deep", "deepSleepSeconds"), ("light", "lightSleepSeconds"), ("rem", "remSleepSeconds"), ("awake", "awakeSleepSeconds")):
            h[sk] = dto.get(f) or 0
        h["bed"] = hhmm_local(dto["sleepStartTimestampGMT"]); h["wake"] = hhmm_local(dto["sleepEndTimestampGMT"])
    if k in sync_acts:
        h["acts"] = sync_acts[k]; h["load"] = r1(sum(x["load"] or 0 for x in sync_acts[k]))
    elif "acts" in h and k >= min(D):
        del h["acts"]; h.pop("load", None)
HP.write_text(json.dumps({"source": hist.get("source", ""), "days": dict(sorted(H.items()))}, separators=(",", ":")))

ser = lambda key: {k: v[key] for k, v in H.items() if v.get(key) is not None}
hrv, rhr, slp, stress, steps = ser("hrv"), ser("rhr"), ser("slp"), ser("stress"), ser("steps")
load = {k: v.get("load", 0) for k, v in H.items()}

# =========================== 2. Herzfrequenz-Grenzen ============================
maxes = sorted([a["maxHR"] for v in H.values() for a in v.get("acts", []) if a.get("maxHR")], reverse=True)
HRMAX = next((m for i, m in enumerate(maxes[:-1]) if m - maxes[i + 1] <= 3), maxes[0] if maxes else 185)

# =========================== 3. Tages-Strain (TRIMP) ==============================
def day_trimp(k):
    vals = [(t, v) for t, v in (g(D.get(k, {}), "heart_rates", "heartRateValues") or []) if v]
    if not vals: return None, 0
    rest = rhr.get(k) or mean(list(rhr.values())[-30:]) or 55
    return trimp(vals, rest, HRMAX, TRIMP_MIN_HRR), len(vals)
TR = {k: day_trimp(k) for k in D}
strain = {k: strain_from(t, STRAIN_K, STRAIN_TCAP) for k, (t, _) in TR.items()}

# =========================== 4. Recovery, Schlafbedarf ===========================
def sleep_need(day):
    y = prev(day); short, nights = 0.0, []
    for i in (1, 2, 3):
        k = prev(day, i)
        if k in slp:
            s_ = max(0.0, SLEEP_BASE_H - slp[k] / 3600); short += s_
            nights.append({"date": k, "slept": slp[k] / 3600, "short": s_})
    debt = sleep_debt(short)
    naps = (H.get(y, {}).get("nap") or 0) / 3600
    st = strain.get(y)
    return {"base": SLEEP_BASE_H, "prevStrain": st, "strainAdd": f_strain(st), "debt": debt, "short3": short,
            "debtCapped": 0.35 * short > 1.5, "debtNights": nights, "naps": naps,
            "need": SLEEP_BASE_H + f_strain(st) + debt - naps}
def base_hrv(day):
    v = [x for k, x in hrv.items() if k < day]; return (S.mean(v), S.stdev(v), len(v)) if len(v) > 1 else (None, None, len(v))
def base_rhr(day, n=RHR_WINDOW):
    lo = prev(day, n); v = [x for k, x in rhr.items() if lo <= k < day]
    return (S.mean(v), S.stdev(v), len(v)) if len(v) > 1 else (None, None, len(v))
def base_sleep(day):
    v = sorted(x / 3600 for k, x in slp.items() if k < day and x >= NAP_CUTOFF_H * 3600)
    if len(v) < 4: return None
    return {"median": S.median(v), "p75": S.quantiles(v, n=4)[2], "n": len(v),
            "excluded": sum(1 for k, x in slp.items() if k < day and x < NAP_CUTOFF_H * 3600)}

def recovery(day):
    hm, hs, hn = base_hrv(day); rm, rs, rn = base_rhr(day); sn = sleep_need(day)
    slept = slp.get(day); perf = slept / 3600 / sn["need"] * 100 if slept else None
    parts = {}
    if day in hrv and hm:
        z = (hrv[day] - hm) / hs
        parts["hrv"] = {"raw": hrv[day], "mean": hm, "sd": hs, "n": hn, "z": z, "score": hrv_score(z), "w": W["hrv"]}
    if day in rhr and rm:
        z = (rhr[day] - rm) / rs
        parts["rhr"] = {"raw": rhr[day], "mean": rm, "sd": rs, "n": rn, "z": z, "score": rhr_score(z), "w": W["rhr"]}
    if perf is not None:
        parts["sleep"] = {"raw": slept / 3600, "need": sn["need"], "perf": perf, "score": sleep_score(perf), "w": W["sleep"]}
    ws = sum(p["w"] for p in parts.values())
    for p in parts.values(): p["wUsed"] = p["w"] / ws
    rec = sum(p["score"] * p["wUsed"] for p in parts.values()) if parts else None
    return rec, parts, sn, perf

# =========================== 5. Trainingslast ====================================
all_dates = [iso(P(min(H)) + dt.timedelta(days=i)) for i in range((P(max(H)) - P(min(H))).days + 1)]
def acwr(day):
    a = sum(load.get(prev(day, i), 0) for i in range(7))
    c = sum(load.get(prev(day, i), 0) for i in range(28)) / 4
    return a, c, (a / c if c > 0 else None)

# =========================== 6. Tage fuer die Seite ==============================
sync_days = sorted(D)
out = {}
for day in sync_days:
    dd = D[day]; dto = g(dd, "sleep", "dailySleepDTO") or {}; st = dd.get("stats") or {}
    rec, parts, sn, perf = recovery(day)
    b = band(rec)
    T, nhr = TR[day]
    sleep = None
    if dto.get("sleepTimeSeconds"):
        start = dto["sleepStartTimestampGMT"]
        lv = [[round((gmt_ms(x["startGMT"]) - start) / 60000, 1), round((gmt_ms(x["endGMT"]) - start) / 60000, 1),
               STAGE[int(x["activityLevel"])]] for x in (g(dd, "sleep", "sleepLevels") or [])]
        sleep = {"deep": dto.get("deepSleepSeconds") or 0, "light": dto.get("lightSleepSeconds") or 0,
                 "rem": dto.get("remSleepSeconds") or 0, "awake": dto.get("awakeSleepSeconds") or 0,
                 "asleep": dto["sleepTimeSeconds"], "inBed": (dto["sleepEndTimestampGMT"] - start) / 1000,
                 "bed": hhmm_local(start), "wake": hhmm_local(dto["sleepEndTimestampGMT"]),
                 "startLocalMs": dto.get("sleepStartTimestampLocal"), "levels": lv,
                 "garminNeed": g(dto, "sleepNeed", "actual"), "garminNeedBase": g(dto, "sleepNeed", "baseline"),
                 "garminScore": g(dto, "sleepScores", "overall", "value"), "avgHR": dto.get("avgHeartRate"),
                 "resp": dto.get("averageRespirationValue"), "spo2": dto.get("averageSpO2Value"),
                 "stress": dto.get("avgSleepStress"), "awakeCount": dto.get("awakeCount"),
                 "skinTemp": g(dd, "sleep", "avgSkinTempDeviationC"), "bbGain": g(dd, "sleep", "bodyBatteryChange")}
    tr = (dd.get("training_readiness") or [None])
    tr = tr[0] if isinstance(tr, list) and tr else None
    a7, c28, ratio = acwr(day)
    ts = g(dd, "training_status", "mostRecentTrainingStatus", "latestTrainingStatusData") or {}
    ts = next(iter(ts.values()), {}) if ts else {}
    hr_vals = [v for _, v in (g(dd, "heart_rates", "heartRateValues") or []) if v]
    out[day] = {
        "date": day, "recovery": rec, "band": b, "parts": parts, "target": TARGET.get(b),
        "strain": strain[day], "trimp": T, "hrCoverage": nhr / 720 if nhr else 0,
        "load": load.get(day, 0), "acts": H.get(day, {}).get("acts", []),
        "need": sn, "perf": perf, "sleep": sleep, "sleepBase": base_sleep(day),
        "hrv7": mean([hrv.get(prev(day, i)) for i in range(7)]), "rhr7": mean([rhr.get(prev(day, i)) for i in range(7)]),
        "stress": H.get(day, {}).get("stress"), "highStressMin": (st.get("highStressDuration") or 0) / 60,
        "steps": st.get("totalSteps"), "im": H.get(day, {}).get("im"), "activeKcal": st.get("activeKilocalories"),
        "kcal": st.get("totalKilocalories"),
        "bbHigh": st.get("bodyBatteryHighestValue"), "bbLow": st.get("bodyBatteryLowestValue"),
        "bbWake": st.get("bodyBatteryAtWakeTime"), "hrMaxDay": max(hr_vals) if hr_vals else None,
        "readiness": {"score": tr.get("score"), "level": tr.get("level"), "feedback": tr.get("feedbackShort"),
                      "recoveryTimeH": tr.get("recoveryTime")} if tr else None,
        "garminHrvStatus": g(dd, "hrv", "hrvSummary", "status"), "garminHrvBand": g(dd, "hrv", "hrvSummary", "baseline"),
        "trainingStatus": ts.get("trainingStatusFeedbackPhrase"),
        "acute7": a7, "chronic28": c28, "acwr": ratio,
        "vo2": g(dd, "training_status", "mostRecentVO2Max", "generic", "vo2MaxPreciseValue"),
    }
last = max([d for d in out if out[d]["recovery"] is not None], default=None)

# =========================== 7. Schlafenszeit-Empfehlung =========================
def bedtime_plan(day):
    """Fuer die Nacht nach `day`: wann ins Bett, um den Bedarf zu decken."""
    nights = [k for k in sorted(H) if k <= day and H[k].get("wake") and H[k].get("slp")][-14:]
    if len(nights) < 5: return None
    wake = S.median(clock_min(H[k]["wake"]) for k in nights)
    eff = S.median(H[k]["slp"] / (H[k]["slp"] + (H[k].get("awake") or 0)) for k in nights)
    nxt = iso(P(day) + dt.timedelta(days=1))
    sn = sleep_need(nxt)
    inbed_h = sn["need"] / eff
    bed = wake - inbed_h * 60
    beds = [clock_min(H[k]["bed"]) for k in nights if H[k].get("bed")]
    tiers = [{"pct": pct, "bedtime": min_to_clock(wake - sn["need"] * pct / 100 / eff * 60),
              "sleepH": sn["need"] * pct / 100} for pct in (100, 85, 70)]
    return {"for": nxt, "need": sn["need"], "needParts": sn, "efficiency": eff, "wake": min_to_clock(wake), "tiers": tiers,
            "bedtime": min_to_clock(bed), "inBed": inbed_h, "typicalBed": min_to_clock(S.median(beds)),
            "bedSD": S.stdev(beds) if len(beds) > 1 else None, "n": len(nights)}
plan = bedtime_plan(last) if last else None

# =========================== 8. Training: Wochen, Zonen, Kategorien ==============
def week_of(k): d = P(k); return iso(d - dt.timedelta(days=d.weekday()))
weeks = defaultdict(lambda: {"sessions": 0, "min": 0, "load": 0.0, "cat": Counter(), "catMin": Counter(),
                             "z": [0] * 5, "rec": [], "strain": [], "slp": [], "hrv": [], "rhr": [], "steps": []})
for k in all_dates:
    w = weeks[week_of(k)]; h = H.get(k, {})
    for a in h.get("acts", []):
        c = CATS.get(a["type"], "sonstige"); w["sessions"] += 1; w["min"] += a["min"]; w["load"] += a["load"] or 0
        w["cat"][c] += 1; w["catMin"][c] += a["min"]
        for i in range(5): w["z"][i] += (a.get("z") or [0] * 5)[i] / 60
    if k in out:
        if out[k]["recovery"] is not None: w["rec"].append(out[k]["recovery"])
        if out[k]["strain"] is not None: w["strain"].append(out[k]["strain"])
    for key, src in (("slp", slp), ("hrv", hrv), ("rhr", rhr), ("steps", steps)):
        if k in src: w[key].append(src[k] / 3600 if key == "slp" else src[k])
week_rows = []
for wk in sorted(weeks)[-26:]:
    w = weeks[wk]
    week_rows.append({"week": wk, "sessions": w["sessions"], "min": w["min"], "load": round(w["load"]),
                      "cat": dict(w["cat"]), "catMin": dict(w["catMin"]), "z": [round(x) for x in w["z"]],
                      "rec": mean(w["rec"]), "strain": mean(w["strain"]), "slp": mean(w["slp"]), "hrv": mean(w["hrv"]),
                      "rhr": mean(w["rhr"]), "steps": mean(w["steps"])})
ref = last or max(D)
def since(cat):
    for i in range(0, 400):
        k = prev(ref, i)
        if any(CATS.get(a["type"], "sonstige") == cat for a in H.get(k, {}).get("acts", [])): return i, k
    return None, None
z28 = [0.0] * 5
for i in range(28):
    for a in H.get(prev(ref, i), {}).get("acts", []):
        for j in range(5): z28[j] += (a.get("z") or [0] * 5)[j] / 60
lb = g(D.get(ref, {}), "training_status", "mostRecentTrainingLoadBalance", "metricsTrainingLoadBalanceDTOMap") or {}
lb = next(iter(lb.values()), None) if lb else None
training = {
    "hrMax": HRMAX, "zonesGarmin": None,
    "since": {c: dict(zip(("days", "date"), since(c))) for c in ("kraft", "intervall", "ausdauer", "erholung")},
    "z28": [round(x) for x in z28], "weeks": week_rows,
    "loadBalance": {k: lb.get(k) for k in ("monthlyLoadAerobicLow", "monthlyLoadAerobicHigh", "monthlyLoadAnaerobic",
                    "monthlyLoadAerobicLowTargetMin", "monthlyLoadAerobicLowTargetMax", "monthlyLoadAerobicHighTargetMin",
                    "monthlyLoadAerobicHighTargetMax", "monthlyLoadAnaerobicTargetMin", "monthlyLoadAnaerobicTargetMax",
                    "trainingBalanceFeedbackPhrase")} if lb else None,
    "loadSeries": [{"date": k, "load": load.get(k, 0), "acute": acwr(k)[0], "chronic": acwr(k)[1], "acwr": acwr(k)[2]}
                   for k in all_dates[-120:]],
}

# =========================== 9. Langzeit-Trends ==================================
months = defaultdict(lambda: defaultdict(list))
for k, h in H.items():
    m = k[:7]
    for key in ("hrv", "rhr", "stress", "steps"):
        if h.get(key) is not None: months[m][key].append(h[key])
    if h.get("slp") and h["slp"] >= NAP_CUTOFF_H * 3600: months[m]["slp"].append(h["slp"] / 3600)
    months[m]["load"].append(h.get("load", 0))
    if h.get("bed") and h.get("slp"): months[m]["bed"].append(clock_min(h["bed"]))
month_rows = [{"month": m, **{key: mean(v) for key, v in months[m].items() if key != "load"},
               "loadWeek": sum(months[m]["load"]) / max(1, len(months[m]["load"])) * 7,
               "nHrv": len(months[m]["hrv"])} for m in sorted(months) if m >= "2024-01"]

# =========================== 10. Zusammenhaenge ==================================
# Zielgroesse: HRV der Nacht, relativ zu deinem gleitenden 30-Tage-Mittel davor (Trend herausgerechnet).
def hrv_dev(k):
    if k not in hrv: return None
    prior = [hrv[prev(k, i)] for i in range(1, 31) if prev(k, i) in hrv]
    return hrv[k] - S.mean(prior) if len(prior) >= 10 else None
def rhr_dev(k):
    if k not in rhr: return None
    prior = [rhr[prev(k, i)] for i in range(1, 31) if prev(k, i) in rhr]
    return rhr[k] - S.mean(prior) if len(prior) >= 10 else None
def welch(a, b):
    if len(a) < 2 or len(b) < 2: return 0
    va, vb = S.variance(a) / len(a), S.variance(b) / len(b)
    return (S.mean(a) - S.mean(b)) / math.sqrt(va + vb) if va + vb > 0 else 0
def compare(name, pred, lab_hi, lab_lo, outcome=hrv_dev, unit="ms", what="HRV", min_n=12):
    hi, lo = [], []
    for k in H:
        p = pred(k); o = outcome(k)
        if p is None or o is None: continue
        (hi if p else lo).append(o)
    if len(hi) < min_n or len(lo) < min_n: return None
    diff = S.mean(hi) - S.mean(lo); t = welch(hi, lo)
    return {"name": name, "what": what, "unit": unit, "hi": lab_hi, "lo": lab_lo, "nHi": len(hi), "nLo": len(lo),
            "meanHi": S.mean(hi), "meanLo": S.mean(lo), "diff": diff, "t": t,
            "strength": "deutlich" if abs(t) >= 2.5 else "erkennbar" if abs(t) >= 1.8 else "schwach"}
def q(series, k, cut, above=True):
    v = series.get(k); return None if v is None else (v >= cut if above else v < cut)
def med(series): v = list(series.values()); return S.median(v) if v else 0
bed_med = S.median(clock_min(h["bed"]) for h in H.values() if h.get("bed"))
loads_pos = [v for v in load.values() if v > 0]
hard = S.quantiles(loads_pos, n=4)[2] if len(loads_pos) > 8 else 80
insights = [x for x in [
    compare("Schlafdauer", lambda k: (slp[k] >= 7 * 3600) if k in slp and slp[k] >= NAP_CUTOFF_H * 3600 else None,
            "≥ 7 h geschlafen", "< 7 h geschlafen"),
    compare("Einschlafzeit", lambda k: (clock_min(H[k]["bed"]) <= bed_med) if H.get(k, {}).get("bed") else None,
            f"vor {min_to_clock(bed_med)} eingeschlafen", f"nach {min_to_clock(bed_med)} eingeschlafen"),
    compare("Training am Vortag", lambda k: (load.get(prev(k), 0) >= hard) if prev(k) in H else None,
            f"harter Vortag (Load ≥ {round(hard)})", "leichter Vortag"),
    compare("Training am Vortag (Ruhepuls)", lambda k: (load.get(prev(k), 0) >= hard) if prev(k) in H else None,
            f"harter Vortag (Load ≥ {round(hard)})", "leichter Vortag", outcome=rhr_dev, unit="bpm", what="Ruhepuls"),
    compare("Stress am Vortag", lambda k: q(stress, prev(k), med(stress)),
            f"Stress-Ø ≥ {round(med(stress))} am Vortag", f"Stress-Ø < {round(med(stress))} am Vortag"),
    compare("Bewegung am Vortag", lambda k: q(steps, prev(k), med(steps)),
            f"≥ {round(med(steps)):,} Schritte am Vortag".replace(",", "."), f"< {round(med(steps)):,} Schritte".replace(",", ".")),
    compare("Wochenende", lambda k: P(k).weekday() in (5, 6) if k in hrv else None,
            "Nächte auf Sa/So", "Nächte unter der Woche"),
] if x]

# =========================== 11. Qualitaet (Schritt 7) ============================
F = {"deep": "deepSleepSeconds", "light": "lightSleepSeconds", "rem": "remSleepSeconds", "awake": "awakeSleepSeconds"}
def reconcile(k):
    sums = defaultdict(float)
    for x in D[k]["sleep"]["sleepLevels"]:
        sums[STAGE[int(x["activityLevel"])]] += (gmt_ms(x["endGMT"]) - gmt_ms(x["startGMT"])) / 1000
    dto = D[k]["sleep"]["dailySleepDTO"]
    return {s_: {"levels": sums[s_], "dto": dto.get(F[s_]) or 0, "diff": sums[s_] - (dto.get(F[s_]) or 0)} for s_ in F}
nights = [k for k in D if g(D[k], "sleep", "sleepLevels") and g(D[k], "sleep", "dailySleepDTO", "deepSleepSeconds") is not None]
allrec = [reconcile(k) for k in nights]
full = [(k, h["deep"] / (h["deep"] + h["light"] + h["rem"]) * 100, h["rem"] / (h["deep"] + h["light"] + h["rem"]) * 100)
        for k, h in H.items() if "deep" in h and h["deep"] + h["light"] + h["rem"] >= NAP_CUTOFF_H * 3600]
def rng(i):
    v = sorted(full, key=lambda t: t[i]); qq = S.quantiles([t[i] for t in v], n=20)
    return {"min": v[0][i], "minDate": v[0][0], "max": v[-1][i], "maxDate": v[-1][0], "median": S.median(t[i] for t in v),
            "p5": qq[0], "p95": qq[-1], "zeros": sum(1 for t in v if t[i] == 0)}
nb = iso(P(last) + dt.timedelta(days=1)) if last else iso(dt.date.today())
hb, rb, sb = base_hrv(nb), base_rhr(nb), base_sleep(nb)
quality = {
    "reconcile": [{"date": k, "stages": reconcile(k)} for k in sorted(random.sample(nights, min(3, len(nights))))],
    "reconcileAll": {"n": len(nights), "maxAbs": max((abs(r[s_]["diff"]) for r in allrec for s_ in F), default=None),
                     "over60": sum(1 for r in allrec if max(abs(r[s_]["diff"]) for s_ in F) > 60)},
    "stages": {"n": len(full), "from": min(t[0] for t in full), "to": max(t[0] for t in full), "deep": rng(1), "rem": rng(2)},
    "baselines": {"hrv": {"n": hb[2], "mean": hb[0], "sd": hb[1], "from": min(hrv), "to": max(hrv)},
                  "rhr": {"n": rb[2], "mean": rb[0], "sd": rb[1], "window": RHR_WINDOW},
                  "rhr14": base_rhr(nb, 14)[0], "sleep": sb},
    "noHR": [{"date": k, "type": a["type"], "min": a["min"]} for k in sorted(D) for a in H.get(k, {}).get("acts", []) if not a.get("avgHR")],
    "nActs": sum(len(H.get(k, {}).get("acts", [])) for k in D),
    "hrCoverageLow": [k for k in sorted(D) if out[k]["hrCoverage"] < 0.8 and k != max(D)],
}

# =========================== 12. Kurzfassung fuer den Coach =======================
def brief():
    if not last: return None
    x = out[last]; w = week_rows[-1] if week_rows else {}
    return {
        "date": last, "recovery": r1(x["recovery"]), "band": x["band"], "target": x["target"],
        "hrv": hrv.get(last), "hrvBase": r1(hb[0]), "hrv7": r1(x["hrv7"]), "rhr": rhr.get(last), "rhrBase30": r1(rb[0]),
        "rhrBase14": r1(quality["baselines"]["rhr14"]), "sleepH": r1((slp.get(last) or 0) / 3600, 2),
        "needH": r1(x["need"]["need"], 2), "perf": r1(x["perf"]), "strainYesterday": r1(strain.get(prev(last))),
        "acwr": r1(x["acwr"], 2), "acute7": r1(x["acute7"]), "chronic28": r1(x["chronic28"]),
        "since": training["since"], "z28min": training["z28"], "garminStatus": x["trainingStatus"],
        "garminReadiness": x["readiness"], "garminHrvStatus": x["garminHrvStatus"], "vo2": x["vo2"],
        "stress": x["stress"], "steps": x["steps"], "bedtimePlan": plan,
        "last7": [{"d": k, "rec": r1(out[k]["recovery"]), "strain": r1(out[k]["strain"]),
                   "sleepH": r1((slp.get(k) or 0) / 3600, 1), "acts": [a["type"] for a in out[k]["acts"]]}
                  for k in sorted(out) if k <= last][-7:],
        "thisWeek": w, "insights": [{"name": i["name"], "diff": r1(i["diff"]), "unit": i["unit"], "what": i["what"],
                                     "strength": i["strength"]} for i in insights],
        "loadBalance": training["loadBalance"],
    }

# =========================== 12b. Ernaehrungsziele ================================
PROTEIN_G = 180          # ca. 1,8 g pro kg Zielgewicht (100 kg)
DEFICIT_KCAL = 500
full_days = [k for k in sorted(out) if k < (last or max(D)) and (out[k].get("kcal") or 0) > 1200 and out[k]["hrCoverage"] >= 0.8][-14:]
tdee = S.median(out[k]["kcal"] for k in full_days) if len(full_days) >= 5 else None
nutrition = {"tdee": tdee, "nDays": len(full_days), "deficit": DEFICIT_KCAL, "protein": PROTEIN_G,
             "kcalTarget": max(1800, int(round((tdee - DEFICIT_KCAL) / 50) * 50)) if tdee else 2200}

payload = {
    "version": 2, "generated": dt.datetime.now(TZ).isoformat(timespec="minutes"),
    "lastSync": data.get("meta", {}).get("last_sync"), "today": iso(dt.datetime.now(TZ).date()), "lastWithData": last,
    "params": {"sleepBase": SLEEP_BASE_H, "rhrWindow": RHR_WINDOW, "napCutoff": NAP_CUTOFF_H, "weights": W,
               "trimpMinHrr": TRIMP_MIN_HRR, "strainK": STRAIN_K, "strainTcap": STRAIN_TCAP, "hrMax": HRMAX},
    "days": out, "plan": plan, "training": training, "months": month_rows, "insights": insights,
    "quality": quality, "brief": brief(), "nutrition": nutrition,
}
(HERE / "dashboard-data.json").write_text(json.dumps(payload, separators=(",", ":"), default=lambda o: None), encoding="utf-8")


# =========================== 13. Kurzmeldung fuers iPhone ========================
def summary_text():
    if not last: return "Noch keine Daten."
    x = out[last]; lines = []
    if last != payload["today"]:
        lines.append(f"Die letzte Nacht fehlt noch (Stand {P(last).strftime('%d.%m.')}). Uhr in der Garmin-App synchronisieren.")
    bn = {"green": "grün", "yellow": "gelb", "red": "rot"}.get(x["band"], "–")
    t = x["target"]
    de = lambda v, n=0: f"{v:.{n}f}".replace(".", ",")
    lines.append(f"Recovery {de(x['recovery'])} % ({bn})" + (f" · Ziel-Strain {de(t[0],1)}–{de(t[1],1)}" if t else ""))
    p_ = x["parts"]
    if "hrv" in p_ and "rhr" in p_:
        lines.append(f"HRV {p_['hrv']['raw']} ms (Ø {de(p_['hrv']['mean'],1)}) · Ruhepuls {p_['rhr']['raw']} (Ø {de(p_['rhr']['mean'],1)})")
    if "sleep" in p_:
        h = p_["sleep"]["raw"]; lines.append(f"Schlaf {int(h)}:{round((h-int(h))*60):02d} h = {de(p_['sleep']['perf'])} % vom Bedarf")
    # Morgen-Eingabe (per Diktat im iPhone-Kurzbefehl) + Trainingsplan vom Vorabend (plan.json)
    import re
    said, mins, flag = "", None, None
    inp = HERE / "today_input.txt"
    if inp.exists() and dt.date.fromtimestamp(inp.stat().st_mtime).isoformat() == payload["today"]:
        said = inp.read_text(encoding="utf-8").strip()
    low = said.lower()
    mins, flag = parse_said(said)
    pj = {}
    for pf in (HERE / "plan.json", HERE / f"plan-{payload['today']}.json"):
        if not pf.exists(): continue
        try:
            cand = json.loads(pf.read_text(encoding="utf-8"))
            if cand.get("date") == payload["today"]: pj = cand; break
        except Exception as e: lines.append(f"(Trainingsplan nicht lesbar: {type(e).__name__})")
    if said: lines.append(f"Deine Angabe: {said[:120]}")
    # Wunsch-Option aus der Angabe (A/B/C oder Stichwort)
    pref = None
    opts_ = pj.get("options") or []
    mm = re.search(r"(?:^|[\s,.;:])(?:option\s*|variante\s*|plan\s*)?([abc])(?=$|[\s,.;:!])", low)
    if mm: pref = mm.group(1).upper()
    else:
        kw = {"kraft": r"kraft|kettlebell|gewicht|hantel|muskel", "ausdauer": r"rad|ergo|fahrrad|ausdauer|cardio|zone ?2|laufen",
              "intervall": r"intervall|hiit|power", "mobility": r"mobil|beweg|dehn|locker|yoga|stretch|entspann"}
        rk = {"empfohlen": r"empfohl|wie geplant|normal|standard|plan a", "variante": r"variante|andere|abwechslung|anders",
              "sanft": r"sanft|\bleicht|\bkurz|müde|ruhig|schon|wenig"}
        for o in opts_:
            if o.get("role") and re.search(rk.get(o["role"], r"$^"), low):
                pref = o.get("id"); break
        for o in ([] if pref else opts_):
            if re.search(kw.get(o.get("type",""), r"$^"), low) or (o.get("title","").lower().split()[:1] and o["title"].lower().split()[0] in low):
                pref = o.get("id"); break
    sl = p_.get("sleep", {}).get("raw") if "sleep" in p_ else None
    token = ".".join(["w", {"green": "g", "yellow": "y", "red": "r"}.get(x["band"], "x") if last == payload["today"] else "x",
                      str(mins or pj.get("defaultMin") or 30), (pref or "x").lower(),
                      str(round(x["recovery"])) if last == payload["today"] and x["recovery"] is not None else "x",
                      str(p_["hrv"]["raw"]) if "hrv" in p_ and last == payload["today"] else "x",
                      str(p_["rhr"]["raw"]) if "rhr" in p_ and last == payload["today"] else "x",
                      f"{int(sl)}{round((sl-int(sl))*60):02d}" if sl and last == payload["today"] else "x",
                      payload["today"].replace("-", "")])
    (HERE / "url.txt").write_text("https://claude.ai/artifact/RNbvKqPgmeNJC2JThihJZz#" + token + "\n", encoding="utf-8")
    if opts_:
        o = next((o for o in opts_ if o.get("id") == pref), None)
        lines.append(f"Vorschläge: " + " · ".join(f"{q.get('id')} {q.get('short') or q.get('title')}" for q in opts_) + (f" – Wunsch: {pref}" if pref else ""))
    if flag == "none":
        lines.append("Heute kein Training – gute Erholung. Spaziergang zählt trotzdem.")
    elif pj.get("date") == payload["today"]:
        band_ = flag or (x["band"] if last == payload["today"] else "yellow")
        why = "wegen deiner Angabe" if flag else (bn if last == payload["today"] else "gelb, Nacht fehlt noch")
        v = (pj.get("variants") or {}).get(band_) or {}
        if v and "title" not in v:                      # Varianten nach Dauer
            keys = sorted(int(k) for k in v if str(k).isdigit())
            want = mins or pj.get("defaultMin") or 30
            pick = max([k for k in keys if k <= want] or [keys[0]]) if keys else None
            v = v.get(str(pick), {}) if pick else {}
        if v:
            lines.append("")
            lines.append(f"TRAINING ({why}{', ' + str(mins) + ' min' if mins else ''}): {v.get('title','')} · {v.get('duration','')}")
            if v.get("detail"): lines.append(v["detail"])
    else:
        lines.append("Kein Plan für heute vom Vorabend – Empfehlung folgt im Cockpit.")
    if plan:
        lines.append("")
        lines.append(f"Heute Abend ins Bett: {plan['tiers'][1]['bedtime']} (85 %) bzw. {plan['tiers'][0]['bedtime']} (100 %)")
    return "\n".join(lines)
(HERE / "summary.txt").write_text(summary_text() + "\n", encoding="utf-8")

tpl = HERE / "dashboard_template.html"
if tpl.exists():
    page = tpl.read_text(encoding="utf-8").replace("/*__DATA__*/null", json.dumps(payload, separators=(",", ":")))
    (HERE / "dashboard.html").write_text('<!doctype html><html lang="de"><head><meta charset="utf-8">'
        '<meta name="viewport" content="width=device-width,initial-scale=1"></head><body>' + page + '</body></html>',
        encoding="utf-8")

q_ = quality
print(f"Pruefung: Phasen max {q_['reconcileAll']['maxAbs']:.0f} s ({q_['reconcileAll']['over60']} > 60 s) | "
      f"Baselines HRV {q_['baselines']['hrv']['n']}, RHR {q_['baselines']['rhr']['n']}, Schlaf {q_['baselines']['sleep']['n']} | "
      f"ohne HF {len(q_['noHR'])}/{q_['nActs']}")
print(f"Analyse fertig – letzter Tag mit Daten: {last}, HFmax {HRMAX}, {len(insights)} Zusammenhaenge, "
      f"Schlafenszeit-Empfehlung: {plan['bedtime'] if plan else '–'}")

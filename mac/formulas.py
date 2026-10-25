"""
formulas.py – die reinen Rechenformeln aus analyze.py.

Keine Dateizugriffe, keine globalen Daten: alles hier ist mit festen Zahlen testbar
(siehe tests/test_formulas.py). analyze.py importiert diese Funktionen.
Nur Python-Standardbibliothek.
"""
import math, re

STRAIN_K = 5.0
STRAIN_TCAP = 1500.0     # TRIMP, der Strain 21 ergibt
TRIMP_MIN_HRR = 0.30     # Minuten unter 30 % Herzfrequenzreserve zaehlen nicht (Alltag/Sitzen)


def clamp(x, lo, hi): return max(lo, min(hi, x))


def band(r):
    """Recovery-Ampel: gruen ab 67, gelb ab 34, sonst rot."""
    return None if r is None else ("green" if r >= 67 else "yellow" if r >= 34 else "red")


def trimp(vals, rest, hrmax, min_hrr=TRIMP_MIN_HRR):
    """Banister-TRIMP aus Herzfrequenz-Proben [(t_ms, bpm), ...] (nur Proben mit Wert)."""
    T = 0.0
    for i, (t, v) in enumerate(vals):
        step = min(10.0, (vals[i + 1][0] - t) / 60000) if i + 1 < len(vals) else 2.0
        r = (v - rest) / (hrmax - rest)
        if r >= min_hrr: T += step * r * 0.64 * math.exp(1.92 * r)
    return T


def strain_from(T, k=STRAIN_K, tcap=STRAIN_TCAP):
    """TRIMP -> Strain 0..21 (logarithmisch, bei tcap gedeckelt)."""
    if T is None: return None
    return min(21.0, 21 * math.log(1 + T / k) / math.log(1 + tcap / k))


def f_strain(st):
    """Zusaetzlicher Schlafbedarf in Stunden durch den Strain des Vortags (0 .. 1,7 h)."""
    return 1.7 / (1 + math.exp((17 - (st or 0)) / 3.5))


def sleep_debt(short3):
    """Schlafschuld aus den Fehlstunden der letzten 3 Naechte: 35 %, hoechstens 1,5 h."""
    return min(0.35 * short3, 1.5)


def hrv_score(z): return clamp(50 + 20 * z, 0, 100)
def rhr_score(z): return clamp(50 - 20 * z, 0, 100)
def sleep_score(perf): return min(100.0, perf)


def parse_said(said):
    """Morgen-Diktat -> (Minuten oder None, Flag 'red' | 'none' | None)."""
    low = said.lower(); mins, flag = None, None
    m = re.search(r"(\d{1,3})\s*(min|minuten|m\b)?", low)
    if m: mins = int(m.group(1))
    elif "dreiviertel" in low: mins = 45
    elif "halbe stunde" in low: mins = 30
    elif "eineinhalb" in low or "anderthalb" in low: mins = 90
    elif "stunde" in low: mins = 60
    elif "viertelstunde" in low: mins = 15
    if re.search(r"krank|erk(ä|ae)lt|fieber|schmerz|verletz|grippe|\bweh\b|tut weh|zerrung|hexenschuss|migräne|kopfweh|übel|durchfall", low): flag = "red"
    if re.search(r"kein(e)? (zeit|training)|ausfallen|pause", low): flag = "none"
    return mins, flag

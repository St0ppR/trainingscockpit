import math
import pytest
from formulas import band, trimp, strain_from, f_strain, sleep_debt, hrv_score, rhr_score, sleep_score, parse_said


@pytest.mark.parametrize("r,want", [(None, None), (0, "red"), (33.9, "red"), (34, "yellow"), (66.9, "yellow"), (67, "green"), (100, "green")])
def test_band_grenzen(r, want):
    assert band(r) == want


def test_strain_skala():
    assert strain_from(None) is None
    assert strain_from(0) == 0
    assert strain_from(1500) == pytest.approx(21.0)
    assert strain_from(10_000) == 21.0                      # gedeckelt
    assert strain_from(100) < strain_from(200) < strain_from(400)


def test_trimp_ignoriert_ruhe_und_zaehlt_belastung():
    rest, hrmax = 55, 185
    ruhig = [(i * 60_000, 60) for i in range(30)]            # weit unter 30 % HFR
    assert trimp(ruhig, rest, hrmax) == 0
    hart = [(i * 60_000, 150) for i in range(30)]
    r = (150 - rest) / (hrmax - rest)
    # 29 Abstaende zu 1 min + letzter Punkt mit 2 min
    assert trimp(hart, rest, hrmax) == pytest.approx(31 * r * 0.64 * math.exp(1.92 * r))


def test_trimp_luecken_hoechstens_10_minuten():
    rest, hrmax = 55, 185
    a = trimp([(0, 150), (60 * 60_000, 150)], rest, hrmax)   # 60 min Luecke zaehlt nur 10
    b = trimp([(0, 150), (10 * 60_000, 150)], rest, hrmax)
    assert a == pytest.approx(b)


def test_schlafbedarf_bausteine():
    assert 0 < f_strain(0) < 0.2
    assert f_strain(17) == pytest.approx(0.85)
    assert f_strain(None) == f_strain(0)
    assert sleep_debt(0) == 0
    assert sleep_debt(2) == pytest.approx(0.7)
    assert sleep_debt(10) == 1.5


def test_recovery_scores():
    assert hrv_score(0) == rhr_score(0) == 50
    assert hrv_score(1) == 70 and rhr_score(1) == 30          # hohe HRV gut, hoher Ruhepuls schlecht
    assert hrv_score(5) == 100 and hrv_score(-5) == 0
    assert sleep_score(80) == 80 and sleep_score(120) == 100


@pytest.mark.parametrize("said,mins,flag", [
    ("30 Minuten", 30, None),
    ("45", 45, None),
    ("1 Stunde", 60, None),
    ("1,5 Stunden Zeit", 90, None),
    ("eine Viertelstunde", 15, None),
    ("dreiviertel Stunde", 45, None),
    ("eine halbe Stunde", 30, None),
    ("anderthalb Stunden", 90, None),
    ("eine Stunde", 60, None),
    ("Bin erkältet, 20 min", 20, "red"),
    ("Knie tut weh", None, "red"),
    ("heute keine Zeit", None, "none"),
    ("", None, None),
])
def test_diktat(said, mins, flag):
    assert parse_said(said) == (mins, flag)

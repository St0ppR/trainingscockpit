"""analyze.py und check_fresh.py laufen komplett auf ausgedachten Daten (tests/make_fixture.py)."""
import json, shutil, subprocess, sys, datetime as dt
from pathlib import Path
import pytest
import check_fresh
from make_fixture import make

ROOT = Path(__file__).resolve().parents[1]


@pytest.fixture(scope="module")
def run(tmp_path_factory):
    d = tmp_path_factory.mktemp("garmin")
    (d / "data.json").write_text(json.dumps(make(days=60)), encoding="utf-8")
    for f in ("analyze.py", "formulas.py", "check_fresh.py"):
        shutil.copy(ROOT / "mac" / f, d / f)
    r = subprocess.run([sys.executable, "analyze.py"], cwd=d, capture_output=True, text=True)
    assert r.returncode == 0, r.stderr
    return d


def test_ausgabedateien(run):
    for f in ("dashboard-data.json", "summary.txt", "history.json", "url.txt"):
        assert (run / f).exists(), f


def test_dashboard_daten_plausibel(run):
    p = json.loads((run / "dashboard-data.json").read_text(encoding="utf-8"))
    assert p["lastWithData"] == p["today"]
    b = p["brief"]
    assert b is not None
    days = p["days"]
    seen = 0
    for k, x in (days.items() if isinstance(days, dict) else enumerate(days)):
        if x.get("recovery") is None: continue
        seen += 1
        assert 0 <= x["recovery"] <= 100, k
        assert x["band"] == ("green" if x["recovery"] >= 67 else "yellow" if x["recovery"] >= 34 else "red"), k
    assert seen >= 30


def test_summary_beginnt_mit_recovery(run):
    first = (run / "summary.txt").read_text(encoding="utf-8").splitlines()[0]
    assert first.startswith("Recovery ")


def test_frische_ok(run):
    assert check_fresh.main(run) == 0


def test_frische_warnt(tmp_path):
    (tmp_path / "dashboard-data.json").write_text(json.dumps({"lastSync": "2026-10-17T07:30:00", "lastWithData": "2026-10-17"}))
    (tmp_path / "summary.txt").write_text("Recovery 50 % (gelb)\n", encoding="utf-8")
    assert check_fresh.main(tmp_path, now=dt.datetime(2026, 10, 24, 7, 41)) == 1
    s = (tmp_path / "summary.txt").read_text(encoding="utf-8")
    assert s.startswith("⚠ Garmin-Sync lief zuletzt vor 7 Tagen")
    assert "7 Tage alt" in s and s.rstrip().endswith("Recovery 50 % (gelb)")
    assert (tmp_path / "logs" / "frische.log").exists()


def test_frische_gestern_reicht(tmp_path):
    now = dt.datetime(2026, 10, 25, 7, 40)
    assert check_fresh.warnings({"lastSync": "2026-10-25T07:30:15", "lastWithData": "2026-10-24"}, now) == []


def test_frische_datei_fehlt(tmp_path):
    assert check_fresh.main(tmp_path) == 1

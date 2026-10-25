"""nudges.py: Mini-Vorschläge passend zur Erholung, gleiche Liste wie im Cockpit."""
import json, re
from pathlib import Path
import nudges

ROOT = Path(__file__).resolve().parents[1]
DAY = "2026-10-26"


def payload(band="green", hours=7.5, fresh=True):
    return {"lastWithData": DAY if fresh else "2026-10-20",
            "days": {DAY: {"band": band, "sleep": {"asleep": hours * 3600}}}}


def test_band_bestimmt_die_liste():
    for band in ("red", "yellow", "green"):
        b, slots, _ = nudges.pick(payload(band), DAY)
        assert b == band
        titles = [t for t, _ in nudges.NUDGES[band]]
        assert all(t in titles for _, t, _ in slots)


def test_zwei_verschiedene_vorschlaege():
    _, slots, _ = nudges.pick(payload(), DAY)
    assert [s for s, _, _ in slots] == ["vormittag", "nachmittag"]
    assert slots[0][1] != slots[1][1]


def test_ohne_frische_daten_gelb():
    b, _, note = nudges.pick(payload("green", fresh=False), DAY)
    assert b == "yellow" and note is None
    assert nudges.pick({}, DAY)[0] == "yellow"


def test_kurze_nacht_bremst_gruen():
    b, _, note = nudges.pick(payload("green", hours=5.2), DAY)
    assert b == "yellow" and "5.2 h" in note


def test_dateien_fuers_iphone(tmp_path):
    (tmp_path / "dashboard-data.json").write_text(json.dumps(payload("red")), encoding="utf-8")
    out = tmp_path / "icloud"
    assert nudges.main(tmp_path, out, DAY) == 0
    for s in ("vormittag", "nachmittag"):
        t = (out / f"vorschlag-{s}.txt").read_text(encoding="utf-8")
        assert "Abhaken im Cockpit" in t and len(t) < 200
    j = json.loads((out / "vorschlaege.json").read_text(encoding="utf-8"))
    assert j["band"] == "red" and j["date"] == DAY


def test_gleiche_liste_wie_im_cockpit():
    html = (ROOT / "web/cockpit/index.html").read_text(encoding="utf-8")
    block = html[html.index("const TC_NUDGES"):html.index("};", html.index("const TC_NUDGES"))]
    for band, items in nudges.NUDGES.items():
        line = re.search(rf"\b{band}:\[(.*)\]", block).group(1)
        assert re.findall(r"[{,]t:'([^']+)'", line) == [t for t, _ in items], band


def test_nicht_schreibbar_bricht_nicht_ab(tmp_path):
    blocker = tmp_path / "datei"; blocker.write_text("x")
    assert nudges.main(tmp_path, blocker / "unter", DAY) == 1

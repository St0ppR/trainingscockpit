#!/usr/bin/env python3
"""
Vergleicht zwei Staende von analyze.py auf denselben (echten) Daten.  Nur lokal, nie in CI.

  python tests/equivalence.py ALTER_ORDNER NEUER_ORDNER DATENORDNER

ALTER_/NEUER_ORDNER enthalten analyze.py (+ formulas.py), DATENORDNER data.json, history.json
und ggf. plan.json/today_input.txt. Beide laufen in Kopien mit gleichem Zufallsstartwert;
ausgegeben wird jedes Feld, das sich unterscheidet ("generated" ausgenommen).
"""
import json, shutil, subprocess, sys, tempfile
from pathlib import Path

RUN = "import random, runpy; random.seed(0); runpy.run_path('analyze.py', run_name='__main__')"


def run(code, data, into):
    for f in Path(data).iterdir():
        if f.is_file(): shutil.copy2(f, into / f.name)
    for f in Path(code).glob("*.py"): shutil.copy(f, into / f.name)
    subprocess.run([sys.executable, "-c", RUN], cwd=into, check=True, capture_output=True)
    return into


def diff(x, y, p=""):
    if type(x) != type(y): yield p, x, y; return
    if isinstance(x, dict):
        for k in sorted(set(x) | set(y)):
            if k not in x or k not in y: yield f"{p}/{k}", x.get(k, "<fehlt>"), y.get(k, "<fehlt>")
            else: yield from diff(x[k], y[k], f"{p}/{k}")
    elif isinstance(x, list) and len(x) == len(y):
        for i, (u, v) in enumerate(zip(x, y)): yield from diff(u, v, f"{p}[{i}]")
    elif x != y: yield p, x, y


if __name__ == "__main__":
    old, new, data = sys.argv[1:4]
    with tempfile.TemporaryDirectory() as ta, tempfile.TemporaryDirectory() as tb:
        a, b = run(old, data, Path(ta)), run(new, data, Path(tb))
        ja, jb = (json.loads((d / "dashboard-data.json").read_text()) for d in (a, b))
        ja.pop("generated", None); jb.pop("generated", None)
        n = 0
        for p, x, y in diff(ja, jb):
            n += 1; print(f"{p}: {str(x)[:60]} -> {str(y)[:60]}")
        for f in ("summary.txt", "history.json", "url.txt"):
            if (a / f).read_bytes() != (b / f).read_bytes(): n += 1; print(f"{f} unterscheidet sich")
        print("gleich" if n == 0 else f"{n} Unterschiede"); sys.exit(1 if n else 0)

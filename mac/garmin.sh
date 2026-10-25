#!/bin/zsh
# Sync + Analyse in einem Schritt.
#   ./garmin.sh          -> von Hand: zeigt die Ausgabe und oeffnet danach das lokale Dashboard
#   ./garmin.sh --auto   -> Zeitplan (launchd): schreibt nur ins Log
#   ./garmin.sh --phone [MIN] -> iPhone-Kurzbefehl: schreibt ins Log, gibt nur die Kurzmeldung aus
cd "$(dirname "$0")" || exit 1
mkdir -p logs
MODE="$1"
MINUTES="${2//[^0-9]/}"   # optional: Zeitbudget in Minuten vom iPhone, z. B. ./garmin.sh --phone 30
run() {
  echo "\n=== $(date '+%Y-%m-%d %H:%M:%S') ($MODE) ==="
  .venv/bin/python sync.py || echo "Sync fehlgeschlagen - analysiere mit dem letzten Stand."
  .venv/bin/python analyze.py ${MINUTES:+--minutes $MINUTES}
  .venv/bin/python check_fresh.py || true
  .venv/bin/python nudges.py || true
}
if [[ "$MODE" == "--auto" ]]; then
  run >> logs/morgenlauf.log 2>&1
elif [[ "$MODE" == "--options" ]]; then
  .venv/bin/python options.py
elif [[ "$MODE" == "--phone" ]]; then
  INPUT="$(cat 2>/dev/null)"            # Diktat aus dem iPhone-Kurzbefehl (Feld "Eingabe")
  printf "%s" "$INPUT" > today_input.txt
  echo "$(date '+%Y-%m-%d %H:%M') | $INPUT" >> logs/eingaben.log
  run >> logs/morgenlauf.log 2>&1 < /dev/null
  cat url.txt 2>/dev/null || echo "https://claude.ai/artifact/RNbvKqPgmeNJC2JThihJZz"
else
  run
  open dashboard.html
fi
exit 0

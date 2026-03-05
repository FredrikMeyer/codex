#!/usr/bin/env bash
# Fetch and display production logs from the server.
# Usage: ./fetch-logs.sh [--raw]
#   --raw   Dump the full JSON without formatting

set -euo pipefail

REMOTE_PATH="/var/www/codex/backend/data/storage.json"

if [ "${1:-}" = "--raw" ]; then
  ssh droplet "cat $REMOTE_PATH"
  exit 0
fi

TMPFILE=$(mktemp)
trap 'rm -f "$TMPFILE"' EXIT

ssh droplet "cat $REMOTE_PATH" > "$TMPFILE"

python3 - "$TMPFILE" <<'EOF'
import json
import sys

with open(sys.argv[1]) as f:
    data = json.load(f)

events = data.get("events", [])
ritalin_events = data.get("ritalin_events", [])

def summarise_events(events):
    by_date = {}
    for entry in events:
        ev = entry.get("event", {})
        date = ev.get("date", "unknown")
        by_date.setdefault(date, []).append(ev)
    return by_date

print("=== Asthma events ===")
asthma_by_date = summarise_events(events)
for date in sorted(asthma_by_date, reverse=True):
    day_events = asthma_by_date[date]
    ventoline = sum(e.get("count", 0) for e in day_events if e.get("type") == "ventoline")
    spray = sum(e.get("count", 0) for e in day_events if e.get("type") == "spray")
    parts = []
    if ventoline:
        parts.append(f"ventoline: {ventoline}")
    if spray:
        parts.append(f"spray: {spray}")
    print(f"  {date}  {', '.join(parts)}")

print()
print("=== Ritalin events ===")
ritalin_by_date = summarise_events(ritalin_events)
for date in sorted(ritalin_by_date, reverse=True):
    total = sum(e.get("count", 0) for e in ritalin_by_date[date])
    print(f"  {date}  {total} dose{'s' if total != 1 else ''}")
EOF

#!/usr/bin/env bash
set -euo pipefail

TIMEOUT=300  # 5 minutes
POLL=10      # seconds between checks
elapsed=0

echo "Waiting for latest CI run to complete..."

while true; do
  status=$(gh run list --limit 1 --json status,conclusion,displayTitle \
    --jq '.[0] | "\(.status) \(.conclusion) \(.displayTitle)"')

  run_status=$(echo "$status" | cut -d' ' -f1)
  conclusion=$(echo "$status" | cut -d' ' -f2)
  title=$(echo "$status" | cut -d' ' -f3-)

  if [[ "$run_status" == "completed" ]]; then
    echo "Done: $conclusion — $title"
    [[ "$conclusion" == "success" ]] && exit 0 || exit 1
  fi

  echo "  [${elapsed}s] $run_status — $title"

  if (( elapsed >= TIMEOUT )); then
    echo "Timed out after ${TIMEOUT}s"
    exit 2
  fi

  sleep "$POLL"
  elapsed=$(( elapsed + POLL ))
done

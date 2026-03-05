#!/usr/bin/env bash
# Fetch application logs from the production backend container.
# Usage: ./fetch-app-logs.sh [--lines N] [--follow]
#   --lines N   Number of lines to show (default: 100)
#   --follow    Stream logs in real time

set -euo pipefail

CONTAINER="asthma-backend"
LINES=100
FOLLOW=false

while [[ $# -gt 0 ]]; do
  case "$1" in
    --lines) LINES="$2"; shift 2 ;;
    --follow) FOLLOW=true; shift ;;
    *) echo "Unknown option: $1" >&2; exit 1 ;;
  esac
done

if $FOLLOW; then
  ssh -t droplet "docker logs --follow --tail $LINES $CONTAINER"
else
  ssh droplet "docker logs --tail $LINES $CONTAINER 2>&1"
fi

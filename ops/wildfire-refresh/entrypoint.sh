#!/usr/bin/env bash
# Two modes:
#   once      run one refresh and exit. What the seed and any manual run use.
#   schedule  sleep until RUN_AT, refresh, repeat. The default; pair it with
#             restart: unless-stopped.
#
# The wait is a plain sleep to the next occurrence rather than cron because the
# target time is recomputed from the local clock on every iteration, so the
# March and November clock changes need no special handling and there is no
# second daemon whose log goes somewhere other than `docker compose logs`.
set -euo pipefail

MODE="${1:-schedule}"
RUN_AT="${RUN_AT:-03:17}"

log() { printf '%s  %s\n' "$(date '+%Y-%m-%d %H:%M:%S %Z')" "$*"; }

case "$MODE" in
  once)
    exec /app/refresh.sh
    ;;
  schedule)
    log "scheduled for $RUN_AT $(date '+%Z') daily"
    while true; do
      now=$(date +%s)
      next=$(date -d "today $RUN_AT" +%s)
      [ "$next" -le "$now" ] && next=$(date -d "tomorrow $RUN_AT" +%s)
      log "next run at $(date -d "@$next" '+%Y-%m-%d %H:%M:%S %Z') ($(( (next - now) / 60 )) min)"
      sleep $((next - now))
      # One bad night must not kill the loop; the failure is in the log and
      # tomorrow gets its own attempt.
      /app/refresh.sh || log "refresh failed with exit $?; will try again tomorrow"
    done
    ;;
  *)
    echo "usage: $0 [once|schedule]" >&2
    exit 64
    ;;
esac

#!/usr/bin/env bash
# One refresh: ingest what changed today, score both models, rebuild the page,
# push it. Mirrors what .github/workflows/wildfire-refresh.yml used to do, with
# two corrections that workflow never got: it was written before the ignition
# model existed, so it never refreshed station FWI and never scored the second
# model. A dashboard built without those two steps has a live escalation
# watchlist sitting on top of a frozen ignition wash, which is worse than an
# obviously stale page because nothing about it looks wrong.
#
# The command sequence is the one documented in the model repo's README, not an
# invention of this script. Refits happen only on a full refresh, deliberately:
# the final model changes when a season finishes and becomes labelled, not
# because today's fires moved, and refitting nightly would quietly shift every
# published score for a reason nobody could point at afterwards.
set -euo pipefail

MODEL_DIR=/opt/wildfire
SITE_DIR=/data/site
FULL_REFRESH="${FULL_REFRESH:-0}"
SITE_REPO="${SITE_REPO:-evankoza/evankoza.github.io}"

log() { printf '%s  %s\n' "$(date '+%Y-%m-%d %H:%M:%S %Z')" "$*"; }
die() { log "ERROR: $*"; exit 1; }

[ -n "${GITHUB_TOKEN:-}" ] || die "GITHUB_TOKEN is unset; copy .env.example to .env and fill it in"

# A slow run must never overlap the next night's, or two of them race on the
# same commit and one loses its push.
exec 9>/data/refresh.lock
flock -n 9 || die "another refresh is already running"

YEARS=""
for y in $(seq 2023 "$(date -u +%Y)"); do YEARS="$YEARS -y $y"; done
THIS_YEAR="-y $(date -u +%Y)"

# ---- the model repo ---------------------------------------------------------
log "updating the model"
git -C "$MODEL_DIR" fetch --quiet origin main
git -C "$MODEL_DIR" reset --hard --quiet origin/main
pip install -e "$MODEL_DIR" --no-deps --quiet
log "model at $(git -C "$MODEL_DIR" rev-parse --short HEAD)"

cd "$MODEL_DIR"

# ---- guard ------------------------------------------------------------------
# A cold start is a multi-year download against NRCan. It should be something a
# human asked for, not something an unattended 3am job decides to do because a
# volume went missing.
if [ "$FULL_REFRESH" != "1" ]; then
  missing=0
  for f in "$WILDFIRE_DATA_DIR/curated/hotspots.parquet" \
           "$WILDFIRE_DATA_DIR/curated/reported_fires.parquet" \
           "$WILDFIRE_DATA_DIR/curated/station_fwi.parquet" \
           "$WILDFIRE_DATA_DIR/models/escalation_final.joblib" \
           "$WILDFIRE_DATA_DIR/models/ignition_final.joblib"; do
    [ -f "$f" ] || { log "missing: $f"; missing=1; }
  done
  [ "$missing" = "0" ] || die "no seeded data. Run the one-off seed first:
    docker compose run --rm -e FULL_REFRESH=1 refresh once"
fi

# ---- ingest -----------------------------------------------------------------
# Fires and CIFFC rebuild their curated table from exactly the years given, so
# they always get all of them; both are cheap once raw responses are on disk and
# conditional requests come back 304. Hotspots is the 535 MB one, so a warm run
# merges the current season in place instead of reparsing the closed ones.
log "ingest: reported fires"
python -m wildfire ingest-fires $YEARS
log "ingest: CIFFC preparedness"
python -m wildfire ingest-ciffc $YEARS

if [ "$FULL_REFRESH" = "1" ]; then
  log "ingest: hotspots, every season (full refresh)"
  python -m wildfire ingest-hotspots $YEARS
  # The decadal FWI archive lags by most of a year, so the archive pull gives
  # the training seasons and --daily tops up the season in progress. Scoring
  # today needs both.
  log "ingest: station FWI archive"
  python -m wildfire ingest-fwi $YEARS
else
  log "ingest: hotspots, current season merged in place"
  python -m wildfire ingest-hotspots $THIS_YEAR --merge
fi

log "ingest: station FWI, season in progress"
python -m wildfire ingest-fwi $THIS_YEAR --daily

# ---- features and, only when asked, refits ----------------------------------
log "build: escalation features"
python -m wildfire build

if [ "$FULL_REFRESH" = "1" ]; then
  log "fit: escalation"
  python -m wildfire fit-final
  log "build: ignition panel"
  python -m wildfire build-ignition
  log "fit: ignition"
  python -m wildfire fit-final-ignition
fi

# ---- score ------------------------------------------------------------------
# Scoring the ignition model does not need its training panel rebuilt: a single
# day is one pass over the study area with nothing to sample, so score_ignition
# assembles the day's features itself.
log "score: escalation"
python -m wildfire predict
log "score: ignition"
python -m wildfire predict-ignition
log "render"
python -m wildfire dashboard

# ---- the site ---------------------------------------------------------------
if [ ! -d "$SITE_DIR/.git" ]; then
  log "cloning the site"
  git clone --quiet "https://github.com/${SITE_REPO}.git" "$SITE_DIR"
fi
git -C "$SITE_DIR" fetch --quiet origin main
git -C "$SITE_DIR" reset --hard --quiet origin/main
git -C "$SITE_DIR" config user.name "Evan Koza"
git -C "$SITE_DIR" config user.email "184670498+evankoza@users.noreply.github.com"

log "re-skinning for the web"
WILDFIRE_DASHBOARD="$MODEL_DIR/docs/dashboard.html" \
  python "$SITE_DIR/tools/import_wildfire.py"

# Never commit a page that did not regenerate, and never a truncated one. The
# importer targets ~195 KB; well outside that band means something upstream
# changed shape and a human should look.
PAGE="$SITE_DIR/experiments/wildfire.html"
SIZE=$(stat -c%s "$PAGE")
log "experiments/wildfire.html is $SIZE bytes"
[ "$SIZE" -ge 120000 ] && [ "$SIZE" -le 400000 ] \
  || die "unexpected size ($SIZE bytes); refusing to commit"
STAMP=$(grep -o '"generated":"[^"]*"' "$PAGE" | head -1 | cut -d'"' -f4)
[ -n "$STAMP" ] || die "no generated stamp in the page; refusing to commit"

git -C "$SITE_DIR" add experiments/wildfire.html assets/wildfire
if git -C "$SITE_DIR" diff --cached --quiet; then
  log "dashboard is unchanged; nothing to commit"
  exit 0
fi

git -C "$SITE_DIR" commit --quiet \
  -m "Refresh the wildfire dashboard ($STAMP)" \
  -m "Automated by ops/wildfire-refresh on the home server."

# The token goes into the URL for exactly one command and is scrubbed straight
# after, so it never sits in .git/config where a later `git remote -v` in a log
# would print it.
git -C "$SITE_DIR" push --quiet \
  "https://x-access-token:${GITHUB_TOKEN}@github.com/${SITE_REPO}.git" HEAD:main
log "pushed $STAMP"

# wildfire-refresh

The nightly rebuild of [experiments/wildfire.html](../../experiments/wildfire.html),
packaged to run in Docker on the home server.

## Why it is not in GitHub Actions

It was, in `.github/workflows/wildfire-refresh.yml`, and it never worked. CIFFC's
API answers **403 Forbidden** to GitHub's runner IPs. It is not the User-Agent:
the byte-identical request, and a request with no User-Agent at all, both return
200 from a Canadian residential connection. Almost certainly a geo or datacenter
block, which is CIFFC's decision to make, so the job moves to a machine they
already allow rather than around the block.

This is not only a cold-start problem. Each new day publishes a new sitrep date,
and that is a fresh request, so a cloud-hosted nightly would hit the same 403
every night even with everything else cached.

The workflow file is kept, with its schedule removed, because its comments record
why each step is shaped the way it is.

## What one run does

The sequence is the model repo's documented one, not an invention of this script.

| | warm (nightly) | seed (`FULL_REFRESH=1`) |
|---|---|---|
| `ingest-fires` | every season | every season |
| `ingest-ciffc` | every season | every season |
| `ingest-hotspots` | current season `--merge` | every season |
| `ingest-fwi` | current season `--daily` | archive, then `--daily` |
| `build` | yes | yes |
| `fit-final`, `build-ignition`, `fit-final-ignition` | no | yes |
| `predict`, `predict-ignition`, `dashboard` | yes | yes |

Two of those the old workflow never ran at all: it was written before the
ignition model existed, so it refreshed neither station FWI nor the ignition
scores. A page built without them has a live watchlist sitting on top of a frozen
ignition wash, which is worse than an obviously stale page because nothing about
it looks wrong.

Refits happen only on a seed, deliberately. The final model changes when a season
finishes and becomes labelled, not because today's fires moved.

## Bringing it up

**1. The token.** Create a fine-grained PAT and put it in `.env`; see
[.env.example](.env.example) for the exact scoping. `.env` is gitignored.

```bash
cp .env.example .env && nano .env
```

**2. Seed the data.** Two ways, and the first is better:

*Copy the curated tables and fitted models across* (~210 MB). This preserves the
exact models that produced the published backtest numbers, and skips a multi-hour
cold ingest. From the Windows box:

```bash
tar -C /c/wildfire-forecast/data -czf - curated models | ssh SERVER 'cat > /tmp/wildfire-seed.tgz'
```

then on the server, into the named volume:

```bash
docker compose run --rm -v /tmp/wildfire-seed.tgz:/seed.tgz refresh sh -c 'mkdir -p /data/wildfire && tar -C /data/wildfire -xzf /seed.tgz'
```

*Or re-ingest and refit from scratch.* Slower, downloads the 535 MB hotspot
archives, and produces freshly fitted models rather than the validated ones:

```bash
docker compose run --rm -e FULL_REFRESH=1 refresh once
```

**3. Start it.**

```bash
docker compose up -d --build
```

`docker compose logs -f refresh` shows the schedule and each night's run.

## Operating it

Run one refresh right now, without waiting for 03:17:

```bash
docker compose run --rm refresh once
```

Pick up an upstream model change: nothing to do. Each run pulls
`evankoza/wildfire-forecast` at `main` and reinstalls it. Rebuild the image only
when its *dependencies* change:

```bash
docker compose up -d --build
```

The named volume `wildfire-data` holds the curated tables, the models, the raw
response cache that keeps warm runs on 304s, and the site clone. Losing it means
re-seeding.

## What it refuses to do

- Run cold unattended. If the curated tables or the fitted models are missing it
  stops and tells you to seed, rather than starting a multi-year download against
  NRCan at 3am.
- Commit a page that did not regenerate, or one outside 120-400 KB, or one with
  no `"generated"` stamp in it.
- Overlap itself. A slow run holds a lock; the next night's exits immediately
  rather than racing it for the same commit.

"""Pull the wildfire dashboard into the portfolio as experiments/wildfire.html.

`python -m wildfire dashboard` (in the wildfire-forecast repo) writes one
self-contained 590 KB file with everything inlined, including eight validation
charts as base64 PNGs. That is exactly right for a file you hand someone on a
USB stick and wrong for a page served over the web: 404 KB of those 590 are the
charts, they sit below the fold, and base64 defeats both image caching and any
chance of a useful first paint.

So this does three things and nothing else:

  1. lifts the charts out to assets/wildfire/*.png and points the payload at
     them, lazily loaded -- the page drops to ~180 KB and the charts arrive
     when you scroll to them;
  2. gives it a real document head (doctype, charset, canonical, OG cards),
     which a self-contained artefact does not need and a public URL does;
  3. injects the site's compile-style bar so there is a way back to the
     portfolio.

Everything else on the page is left exactly as the pipeline generated it,
because the point of that generator is that the page cannot drift from the
model it describes. Re-run this after any `wildfire dashboard`:

    python tools/import_wildfire.py

Every class it injects is prefixed `pf-`. The dashboard's own stylesheet is
regenerated upstream and can grow any class name it likes; the prefix is what
keeps a future rename from silently restyling this bar.
"""

from __future__ import annotations

import base64
import json
import os
import re
import shutil
import sys
from pathlib import Path

SITE = Path(__file__).resolve().parent.parent
# Defaults to the local clone; CI (see .github/workflows/wildfire-refresh.yml)
# checks the repo out somewhere else and points this at it.
SRC = Path(os.getenv("WILDFIRE_DASHBOARD", r"C:\wildfire-forecast\docs\dashboard.html"))
OUT = SITE / "experiments" / "wildfire.html"
IMG_DIR = SITE / "assets" / "wildfire"

CANONICAL = "https://evankoza.com/experiments/wildfire.html"
TITLE = "Wildfire Escalation Watch \u2014 forecasting which Canadian fires blow up"
DESC = ("A model that reads a new Canadian wildfire 24 hours after it is reported "
        "and estimates the chance it passes 100 hectares. Live map, ranked "
        "watchlist, and the season- and region-blocked backtests behind it.")

# Chart order matches CHART_META in the generator; these names become filenames.
CHART_NAMES = ["regions", "pr-curve", "calibration", "importance"]

HEAD = f"""<!DOCTYPE html>
<!--
  WILDFIRE ESCALATION WATCH
  Generated, not hand-written. `python -m wildfire dashboard` in
  github.com/evankoza/wildfire-forecast builds the page from the same artefacts
  the CLI writes, and `python tools/import_wildfire.py` in this repo re-skins it
  for the web (charts lifted out of base64, document head, portfolio bar).
  Edit either of those, not this file -- the next import overwrites it.
-->
<html lang="en">
<head>
<meta charset="utf-8">
<meta name="viewport" content="width=device-width, initial-scale=1">
<title>{TITLE}</title>
<meta name="description" content="{DESC}" />
<link rel="canonical" href="{CANONICAL}" />
<meta property="og:type" content="website" />
<meta property="og:site_name" content="Evan Koza" />
<meta property="og:title" content="{TITLE}" />
<meta property="og:description" content="{DESC}" />
<meta property="og:url" content="{CANONICAL}" />
<meta property="og:image" content="https://evankoza.com/assets/thumbnail.png" />
<meta name="twitter:card" content="summary_large_image" />
<link rel="icon" href="/favicon.svg" type="image/svg+xml" />
<link rel="alternate icon" href="/favicon.ico" />
</head>
<body>
"""

# The dashboard is an operations console with its own palette; it keeps it, the
# same way the Discord demo keeps blurple. The bar is the one pumpkin thing on
# the page, which is what makes it read as chrome rather than as content -- and
# the console's teal accent stays clear of the red/amber the risk ramp needs.
BAR_CSS = """
<style id="pf-chrome">
  .pf-bar {
    max-width: 1240px;
    margin: 0 auto;
    padding: 22px 20px 0;
    display: flex;
    align-items: flex-start;
    justify-content: space-between;
    flex-wrap: wrap;
    gap: 14px 24px;
  }
  .pf-eyebrow {
    display: block;
    font-family: var(--mono);
    font-size: 11px;
    letter-spacing: .14em;
    text-transform: uppercase;
    color: #C95000;
  }
  .pf-prompt { opacity: .55; }
  .pf-sub {
    margin: 8px 0 0;
    max-width: 62ch;
    font-size: 13.5px;
    line-height: 1.6;
    color: var(--ink-2);
  }
  .pf-links { display: flex; gap: 10px; flex-wrap: wrap; flex-shrink: 0; }
  .pf-nav {
    font-family: var(--mono);
    font-size: 11px;
    letter-spacing: .08em;
    text-transform: uppercase;
    white-space: nowrap;
    color: var(--ink-2);
    text-decoration: none;
    border: 1px solid var(--rule);
    border-radius: 999px;
    padding: 7px 13px;
    background: var(--panel);
    transition: color .15s, border-color .15s;
  }
  .pf-nav:hover { color: #C95000; border-color: #C95000; }
  @media (max-width: 640px) {
    .pf-bar { padding: 16px 20px 0; }
    .pf-sub { font-size: 13px; }
  }
</style>
"""

BAR_HTML = """
<header class="pf-bar">
  <div>
    <span class="pf-eyebrow"><span class="pf-prompt">~ $</span> ./wildfire dashboard</span>
    <p class="pf-sub">
      A dated snapshot, not a live feed&hellip; the model scores every fire
      Canada reported in the previous three weeks and the page bakes the answer
      in. For what is burning right now, use the CWFIS map linked at the bottom.
    </p>
  </div>
  <div class="pf-links">
    <a class="pf-nav" href="/#return">&larr; Portfolio</a>
    <a class="pf-nav" href="https://github.com/evankoza/wildfire-forecast">Source &#8599;</a>
  </div>
</header>
"""


def main() -> int:
    if not SRC.exists():
        print(f"no dashboard at {SRC} -- run `python -m wildfire dashboard` first")
        return 1

    html = SRC.read_text(encoding="utf-8")

    # ---- 1. charts out of base64 ------------------------------------------
    # The payload is one <script type="application/json"> blob. Rewriting the
    # parsed object and re-serialising is the only edit here that has to survive
    # arbitrary regeneration, so it goes through json rather than a regex over
    # 400 KB of base64.
    m = re.search(
        r'(<script id="payload" type="application/json">)(.*?)(</script>)',
        html, re.S,
    )
    if not m:
        print("payload script not found -- did the dashboard template change?")
        return 1

    payload = json.loads(m.group(2).replace("<\\/", "</"))
    charts = payload["charts"]
    if len(charts) != len(CHART_NAMES):
        print(f"expected {len(CHART_NAMES)} charts, found {len(charts)} -- "
              "update CHART_NAMES to match CHART_META in the generator")
        return 1

    if IMG_DIR.exists():
        shutil.rmtree(IMG_DIR)
    IMG_DIR.mkdir(parents=True)

    saved = 0
    for name, chart in zip(CHART_NAMES, charts):
        for theme in ("light", "dark"):
            data = chart[theme].split(",", 1)[1]
            raw = base64.b64decode(data)
            (IMG_DIR / f"{name}-{theme}.png").write_bytes(raw)
            saved += len(chart[theme])
            # Relative: the page lives at /experiments/, the charts at /assets/.
            chart[theme] = f"../assets/wildfire/{name}-{theme}.png"

    body = json.dumps(payload, separators=(",", ":")).replace("</", "<\\/")
    html = html[:m.start()] + m.group(1) + body + m.group(3) + html[m.end():]

    # ---- 2. the charts are below the fold, so let them arrive late ---------
    # The generator writes both <img> tags from one template line. Both are in
    # the DOM at all times and CSS picks the themed one, so without `lazy` the
    # browser fetches all eight regardless of theme.
    before = html
    html = html.replace(
        "'<img class=\"lt\" src=\"'",
        "'<img class=\"lt\" loading=\"lazy\" decoding=\"async\" src=\"'",
    ).replace(
        "'<img class=\"dk\" src=\"'",
        "'<img class=\"dk\" loading=\"lazy\" decoding=\"async\" src=\"'",
    )
    if html == before:
        print("warning: chart <img> template not found, charts will load eagerly")

    # ---- 3. document head + portfolio bar ----------------------------------
    # The generated file opens with a few bare <meta>s and a <title>, and no
    # doctype or <head>: correct for a self-contained artefact, not enough for a
    # URL that wants a canonical and OG cards. Drop that opening block and
    # supply a real head. The bar goes immediately before the dashboard's own
    # .wrap so it reads as a header above the page.
    head_block = re.match(r"\s*(?:<meta[^>]*>\s*)*<title>.*?</title>\s*", html, re.S)
    if not head_block:
        print("leading <title> block not found -- did the dashboard template change?")
        return 1
    html = html[head_block.end():]
    html = HEAD + BAR_CSS + html.replace(
        '<div class="wrap">', BAR_HTML + '\n<div class="wrap">', 1
    ) + "\n</body>\n</html>\n"

    OUT.write_text(html, encoding="utf-8")

    print(f"wrote {OUT.relative_to(SITE)}  {OUT.stat().st_size / 1024:.0f} KB "
          f"(was {SRC.stat().st_size / 1024:.0f} KB)")
    print(f"wrote {len(CHART_NAMES) * 2} charts to {IMG_DIR.relative_to(SITE)}  "
          f"{sum(f.stat().st_size for f in IMG_DIR.iterdir()) / 1024:.0f} KB "
          f"(was {saved / 1024:.0f} KB of base64)")
    return 0


if __name__ == "__main__":
    sys.exit(main())

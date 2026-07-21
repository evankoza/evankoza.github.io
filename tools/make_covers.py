"""
Generate compile-style ASCII covers (pumpkin glyphs on parchment) that match the
existing coverRaw tiles (lissajous / data-analysis / make-your-own).

Recipe mirrors the in-page renderer in index.html:
  ramp (light->dark): " .'\",:;!i+trxnvczXYUJCLQ0OZmwqpdbkhao#MW&8%B@$"
  glyph #F2622E on parchment #ECEAE3, monospace, advance = 0.6 x height
  lum >= cut -> blank parchment; below -> glyph via ramp.

Two subjects:
  eternal-fm : an infinity (lemniscate) traced by an audio waveform
  invoice    : a stacked invoice page with a magnifier over the fine print
"""
import math, random
from PIL import Image, ImageDraw, ImageFilter, ImageFont, ImageOps, ImageChops

# Two ramps, light->dark. Flip BLOCK_MODE to test the look.
#   glyphs : the original code-ish letter/symbol mosaic
#   blocks : Unicode shade rectangles (light/medium/dark/full) -> reads as solid
#            tiles at four opacities instead of text
BLOCK_MODE = True
RAMP_GLYPHS = " .'\",:;!i+trxnvczXYUJCLQ0OZmwqpdbkhao#MW&8%B@$"
RAMP_BLOCKS = " ░▒▓█"   # (blank) ░ ▒ ▓ █
RAMP = RAMP_BLOCKS if BLOCK_MODE else RAMP_GLYPHS
# Inverted scheme: deep pumpkin field, warm-white glyphs (was the reverse).
# Field matches --pumpkin (#C95000) — keep .tile.raw background in sync.
BG_COLOR = (201, 80, 0)     # #C95000  --pumpkin (the tile fills with this too)
# The cover is baked as the SUBJECT on a TRANSPARENT field. In the page it is used
# purely as a CSS MASK (only its alpha matters, colour is irrelevant): the tile fills
# with solid pumpkin and the subject is SUBTRACTED to punch a real transparent hole,
# so the animated projects-bg code field shows through the subject while the orange
# tile stays solid + connected. `contain` mask sizing means the subject never clips.
# See `.tile.raw::before` in index.html.
FG_COLOR = (255, 255, 255)  # neutral white — only the alpha (subject vs field) is read as a mask
TRANSPARENT_FIELD = True    # subject ink on a transparent field -> used as the knockout mask
TRANSPARENT_FG = False      # (legacy) punch the subject out as see-through holes instead
CROP_MARGIN = 0.06          # after rendering, crop to the glyph content + this margin
                            # (fraction of the larger content dim) so subjects fill the tile
CROP_BOTTOM = 0.20          # EXTRA clear field below the subject (fraction of content height)
                            # reserved for the bottom title so the art never overlaps it
CUT = 150                   # lum >= cut -> blank (bg shows through)
GAMMA = 1.0
CHAR_H = 20                 # glyph height in px (13 -> 15 -> 19 -> 26 -> 32; bigger = lower-res, legible glyphs)
FONT_PATH = r"C:\Windows\Fonts\consola.ttf"

SS = 3  # supersample factor for the source line art (anti-aliased edges -> ramp falloff)


def asciify(src_gray, out_path, char_h=CHAR_H, cut=CUT):
    """src_gray: 'L' image, dark shape on white. Sample -> glyph mosaic -> save webp.
    `cut`: luminance >= cut samples to blank field (raise it for photos, whose
    subject mid-tones sit higher than crisp black line art)."""
    W, H = src_gray.size
    char_w = char_h * 0.6
    cols = max(1, int(W / char_w))
    rows = max(1, int(H / char_h))

    small = src_gray.resize((cols, rows), Image.BILINEAR)
    px = small.load()

    # render the glyphs into an alpha mask (0 = field, 255 = glyph ink). We paint
    # white through this mask (opaque mode) or invert it into the alpha channel to
    # punch transparent holes (TRANSPARENT_FG) — either way the glyph coverage and
    # anti-aliased edges are identical.
    mask = Image.new("L", (W, H), 0)
    md = ImageDraw.Draw(mask)
    font = ImageFont.truetype(FONT_PATH, char_h)
    N = len(RAMP)
    for r in range(rows):
        y = r * char_h
        for c in range(cols):
            lum = px[c, r]              # 0=black shape .. 255=white bg
            if lum >= cut:
                continue
            t = ((cut - lum) / cut) ** GAMMA
            ch = RAMP[min(N - 1, int(t * N))]
            if ch == " ":
                continue
            dy = 0 if BLOCK_MODE else -char_h * 0.12   # letters need a lift; blocks tile as-is
            md.text((c * char_w, y + dy), ch, font=font, fill=255)

    if TRANSPARENT_FIELD:
        out = Image.new("RGBA", (W, H), (0, 0, 0, 0))  # transparent field
        out.paste(FG_COLOR, mask=mask)                 # glyph ink -> cobalt, field see-through
    elif TRANSPARENT_FG:
        out = Image.new("RGBA", (W, H), BG_COLOR + (255,))
        out.putalpha(ImageChops.invert(mask))        # glyph ink -> alpha 0 (see-through)
    else:
        out = Image.new("RGB", (W, H), BG_COLOR)
        out.paste(FG_COLOR, mask=mask)               # glyph ink -> white

    # crop to the glyph content + a uniform margin so the subject fills the tile
    # (covers otherwise carry a lot of empty field; this normalises subject scale).
    # the mask's own bbox is exactly the glyph extent — no diff against the field.
    bbox = mask.getbbox()
    if bbox:
        sub = out.crop(bbox)
        m = int(round(max(sub.size) * CROP_MARGIN))
        mb = int(round(sub.height * CROP_BOTTOM))   # extra clear strip for the bottom title
        fw, fh = sub.width + 2 * m, sub.height + m + mb
        rgba = TRANSPARENT_FIELD or TRANSPARENT_FG
        framed = (Image.new("RGBA", (fw, fh), (0, 0, 0, 0) if TRANSPARENT_FIELD else BG_COLOR + (255,))
                  if rgba else Image.new("RGB", (fw, fh), BG_COLOR))
        framed.paste(sub, (m, m))                   # subject pinned high; clear field below
        out = framed

    out.save(out_path, "WEBP", quality=92, method=6)
    print("wrote", out_path, out.size, f"{cols}x{rows} glyphs")


def reascii(in_path, out_path, char_h=CHAR_H, blur=8, gain=1.7, floor=0.16):
    """Re-render an EXISTING pumpkin-on-parchment cover (no source available) at a
    new glyph size + inverted palette. The old art is sparse (thin glyphs with
    parchment gaps), so measure *ink relative to parchment* (so blank stays blank),
    blur to merge the sparse glyphs into a continuous density field, normalise, and
    apply a hard `floor` so faint background/compression noise clips to blank instead
    of becoming a full-field ASCII texture. `gain` lifts the sparse subject so it
    isn't too faint. Result is fed to asciify as a clean dark-shape-on-white source."""
    PARCH_L = 232
    cov = Image.open(in_path).convert("L")
    ink = cov.point([max(0, PARCH_L - i) for i in range(256)])   # 0 = parchment (blank)
    ink = ink.filter(ImageFilter.GaussianBlur(blur))             # sparse glyphs -> density
    mx = ink.getextrema()[1] or 1
    def f(v):
        n = v / mx
        if n < floor:
            return 255                                           # clean blank field
        n = min(1.0, (n - floor) / (1 - floor) * gain)
        return int(round(255 * (1 - n)))
    src = ink.point([f(v) for v in range(256)])
    asciify(src, out_path, char_h)


# ---------------------------------------------------------------- eternal fm
def src_eternal(size=1000):
    W = H = size * SS
    img = Image.new("L", (W, H), 255)
    d = ImageDraw.Draw(img)
    cx, cy = W / 2, H / 2
    a = W * 0.36                       # lemniscate scale

    # audio-like amplitude envelope along the path parameter s in [0,1).
    # Smooth sinusoids only — the old random grit left the band edge ragged once
    # screened into the coarse block grid.
    def env(s):
        v = (0.62
             + 0.26 * abs(math.sin(s * math.pi * 9))
             + 0.18 * abs(math.sin(s * math.pi * 23 + 1.3)))
        return max(0.18, v)

    NPTS = 1600
    base_amp = W * 0.052               # half-thickness of the waveform band
    stroke = max(2, int(W * 0.0045))
    pts = []
    for i in range(NPTS + 1):
        t = i / NPTS * 2 * math.pi
        den = 1 + math.sin(t) ** 2
        x = a * math.cos(t) / den
        y = a * math.sin(t) * math.cos(t) / den
        pts.append((cx + x, cy + y))

    # draw waveform spikes perpendicular to the path (a wave wrapped on the loop)
    for i in range(NPTS):
        x0, y0 = pts[i]
        x1, y1 = pts[i + 1]
        dx, dy = x1 - x0, y1 - y0
        L = math.hypot(dx, dy) or 1
        nx, ny = -dy / L, dx / L       # unit normal
        s = i / NPTS
        amp = base_amp * env(s)
        d.line([(x0 - nx * amp, y0 - ny * amp),
                (x0 + nx * amp, y0 + ny * amp)], fill=0, width=stroke)
    # solid centerline so the infinity always reads even where spikes are short
    d.line(pts, fill=0, width=max(3, int(W * 0.010)), joint="curve")

    img = img.filter(ImageFilter.GaussianBlur(W * 0.0032))   # extra smoothing -> clean block edges
    return img.resize((size, size), Image.LANCZOS)


# ---------------------------------------------------------------- invoice
# Thin outlines vanish when sampled down to the ~128-col glyph grid, so the
# document is built from BOLD filled bars (a redacted-form silhouette) plus a
# thick magnifier ring -- solid masses that survive the downsample, matching the
# data-analysis bar-chart cover.
def src_invoice(size=1000):
    W = H = size * SS
    img = Image.new("L", (W, H), 255)
    d = ImageDraw.Draw(img)
    rng = random.Random(11)

    def bar(x0, y0, x1, y1, v=0):
        d.rectangle([x0, y0, x1, y1], fill=v)

    pw, ph = W * 0.54, H * 0.76
    px0, py0 = W * 0.18, H * 0.10
    frame = max(3, int(W * 0.016))   # thick page frame survives the grid

    # stack: two sheets peeking up-left as thick L-edges
    for k in (2, 1):
        ox = oy = -k * W * 0.022
        bar(px0 + ox, py0 + oy, px0 + pw + ox, py0 + oy + frame)            # top edge
        bar(px0 + ox, py0 + oy, px0 + ox + frame, py0 + ph + oy)           # left edge
    # top sheet: thick frame
    bar(px0, py0, px0 + pw, py0 + frame)
    bar(px0, py0 + ph - frame, px0 + pw, py0 + ph)
    bar(px0, py0, px0 + frame, py0 + ph)
    bar(px0 + pw - frame, py0, px0 + pw, py0 + ph)

    pad = pw * 0.08
    cl, cr = px0 + pad, px0 + pw - pad
    cw = cr - cl
    y = py0 + ph * 0.07

    # header: logo block + title bar (right)
    bar(cl, y, cl + cw * 0.30, y + ph * 0.06)
    bar(cr - cw * 0.34, y, cr, y + ph * 0.028)
    bar(cr - cw * 0.34, y + ph * 0.040, cr - cw * 0.10, y + ph * 0.058)
    y += ph * 0.11

    # meta block: a couple of fat lines both sides (thicker -> clean in the grid)
    for _ in range(2):
        bar(cl, y, cl + cw * 0.32, y + ph * 0.030)
        bar(cr - cw * 0.32, y, cr - cw * 0.05, y + ph * 0.030)
        y += ph * 0.052
    y += ph * 0.015

    # table header rule (extra thick)
    bar(cl, y, cr, y + frame * 1.3)
    y += ph * 0.045

    # line items: each row = fat bars in 4 columns, widths jittered like text
    # (fewer + thicker than before so the rows read as bold bands, not thin noise)
    row_h = ph * 0.078
    bar_h = ph * 0.044
    ty0 = y - ph * 0.01
    for _ in range(6):
        bar(cl, y, cl + cw * (0.085 + rng.random() * 0.03), y + bar_h)          # UPC
        bar(cl + cw * 0.16, y, cl + cw * (0.34 + rng.random() * 0.16), y + bar_h)  # desc
        bar(cl + cw * 0.58, y, cl + cw * (0.66 + rng.random() * 0.05), y + bar_h)  # DRqty
        bar(cl + cw * 0.78, y, cl + cw * (0.85 + rng.random() * 0.05), y + bar_h)  # scan
        y += row_h
    ty1 = y - row_h + bar_h
    bar(cl, y, cr, y + frame * 1.3)        # table bottom rule

    # column dividers (thick enough to survive)
    for fx in (0.13, 0.55, 0.75):
        x = cl + cw * fx
        bar(x - frame * 0.5, ty0, x + frame * 0.5, ty1)

    # dog-ear page-turn corner, bottom-right
    ear = pw * 0.12
    bx, by = px0 + pw, py0 + ph
    d.polygon([(bx - ear, by), (bx, by), (bx, by - ear)], fill=0)

    # magnifier over the fine print (lower-right rows), bold ring + handle
    lcx, lcy = px0 + pw * 0.72, py0 + ph * 0.66
    lr = pw * 0.235
    ring = max(8, int(W * 0.024))
    d.ellipse([lcx - lr, lcy - lr, lcx + lr, lcy + lr], outline=0, width=ring, fill=255)
    a45 = math.radians(45)
    hx, hy = lcx + lr * math.cos(a45), lcy + lr * math.sin(a45)
    d.line([(hx, hy), (hx + lr * 1.0, hy + lr * 1.0)], fill=0, width=ring + frame)
    # magnified rows inside the lens (fatter than the page rows)
    for i, yy in enumerate([lcy - lr * 0.30, lcy + lr * 0.02, lcy + lr * 0.34]):
        ln = lr * (0.58 - i * 0.08)
        bar(lcx - ln, yy - lr * 0.07, lcx + ln, yy + lr * 0.07)

    img = img.filter(ImageFilter.GaussianBlur(W * 0.0026))   # smooth thin edges for clean blocks
    return img.resize((size, size), Image.LANCZOS)


# ---------------------------------------------------------------- eye (easter egg)
# The vision0 peeking-eye photo, screened into the same block-ASCII knockout as the
# project covers. The wall uses this to (rarely) replace a project's art with a
# staring eye. Photo -> dark-subject-on-white source: composite the transparent PNG
# on white (skin/sclera read light -> blank field), grayscale, then push contrast so
# the iris/pupil/lid-crease/lashes survive as solid dark masses (thin lines vanish in
# the coarse grid). A vignette darkens the outer almond so the eye SHAPE reads, not
# just a floating pupil.
# ---------------------------------------------------------------- eye (easter egg)
# The vision1 eye photo, screened into the SAME pumpkin knockout as every other cover.
# Photo -> dark-subject-on-white source: composite the transparent PNG on white (skin
# /sclera read light -> blank field), grayscale, autocontrast so the iris/pupil/lid
# survive as dark masses, then hand to asciify (cut raised for a photo's higher mids).
def src_eye(size=1000):
    eye = Image.open(r"C:\website\assets\vision1.png").convert("RGBA")
    bg = Image.new("RGBA", eye.size, (255, 255, 255, 255))
    bg.alpha_composite(eye)
    g = ImageOps.autocontrast(bg.convert("L"), cutoff=2)
    return g.resize((size, size), Image.LANCZOS)


# ---------------------------------------------------------------- eye, closed (favicon blink)
# A shut version of the vision1 eye for the tab-blur favicon swap. No closed-eye
# photo exists, so it is drawn: a fat lash-line arc, a lid crease, and tapered
# lashes as solid masses (thin strokes vanish in the coarse grid), with flat greys
# picked to land on the ░▒▓ ramp steps, then screened by the SAME asciify pass as
# the open eye so the two favicons share one texture.
def src_eye_closed(size=1000):
    W = H = size * SS
    img = Image.new("L", (W, H), 255)
    d = ImageDraw.Draw(img)

    def qbez(p0, c, p1, t):
        x = (1 - t) ** 2 * p0[0] + 2 * (1 - t) * t * c[0] + t * t * p1[0]
        y = (1 - t) ** 2 * p0[1] + 2 * (1 - t) * t * c[1] + t * t * p1[1]
        return x, y

    def stroke(p0, c, p1, r_tip, r_mid, fill, n=200):
        """Quadratic-bezier stroke stamped from circles: fat middle, tapered tips."""
        for i in range(n + 1):
            t = i / n
            x, y = qbez(p0, c, p1, t)
            r = r_tip + (r_mid - r_tip) * math.sin(t * math.pi)
            d.ellipse([x - r, y - r, x + r, y + r], fill=fill)

    # the shut lid is a collapsed almond: top curve and lash line share the same
    # corner points, so the silhouette echoes the open eye's almond
    corners = ((0.10 * W, 0.46 * H), (0.90 * W, 0.46 * H))
    top = (corners[0], (0.50 * W, 0.30 * H), corners[1])
    mid = (corners[0], (0.50 * W, 0.47 * H), corners[1])
    lash = (corners[0], (0.50 * W, 0.62 * H), corners[1])

    def lens(a, b, fill):
        pts = [qbez(*a, i / 60) for i in range(61)] + \
              [qbez(*b, i / 60) for i in range(60, -1, -1)]
        d.polygon(pts, fill=fill)

    lens(top, lash, 150)   # whole lid  -> ░ after the screen
    lens(mid, lash, 115)   # darker toward the shut edge -> ▒
    stroke(*lash, W * 0.015, W * 0.033, 0)             # lash line -> █

    # lashes fanning down-outward off the lash line
    for t in (0.18, 0.34, 0.50, 0.66, 0.82):
        x, y = qbez(*lash, t)
        dx = (x - 0.5 * W) * 0.22
        dy = W * 0.075
        m = 40
        for j in range(m + 1):
            s = j / m
            r = W * 0.018 * (1 - s) + W * 0.004 * s
            d.ellipse([x + dx * s - r, y + dy * s - r,
                       x + dx * s + r, y + dy * s + r], fill=0)

    img = img.filter(ImageFilter.GaussianBlur(W * 0.0020))
    return img.resize((size, size), Image.LANCZOS)


# ---------------------------------------------------------------- receipt printer
# The thermal print station: a solid printer body with a receipt rising out of
# the top — thick frame + fat text bars, torn zigzag top edge. All solid masses
# (frame/bars as fat rectangles) so nothing vanishes in the coarse block grid.
def src_printer(size=1000):
    W = H = size * SS
    img = Image.new("L", (W, H), 255)
    d = ImageDraw.Draw(img)
    rng = random.Random(7)

    frame = max(4, int(W * 0.020))

    # receipt strip: rises from the printer mouth to a torn top edge
    rw = W * 0.44
    rx0 = (W - rw) / 2
    ry_top = H * 0.06
    ry_bot = H * 0.62                     # where it disappears into the printer

    # torn top edge: filled zigzag band across the strip
    teeth = 7
    th = H * 0.035
    pts = [(rx0, ry_top + th)]
    for i in range(teeth + 1):
        x = rx0 + rw * i / teeth
        y = ry_top if i % 2 == 0 else ry_top + th
        pts.append((x, y))
    pts += [(rx0 + rw, ry_top + th + frame), (rx0, ry_top + th + frame)]
    d.polygon(pts, fill=0)

    # receipt side edges (thick)
    d.rectangle([rx0, ry_top + th, rx0 + frame, ry_bot], fill=0)
    d.rectangle([rx0 + rw - frame, ry_top + th, rx0 + rw, ry_bot], fill=0)

    # fat "printed text" bars inside the receipt, widths jittered
    pad = rw * 0.14
    y = ry_top + th + H * 0.045
    bar_h = H * 0.030
    while y + bar_h < ry_bot - H * 0.02:
        wfrac = 0.55 + rng.random() * 0.45
        left = rng.random() < 0.75
        x0 = rx0 + pad if left else rx0 + rw - pad - (rw - 2 * pad) * wfrac
        d.rectangle([x0, y, x0 + (rw - 2 * pad) * wfrac, y + bar_h], fill=0)
        y += bar_h * 1.9

    # printer body: solid slab with rounded top corners; the receipt feeds in
    bw = W * 0.78
    bx0 = (W - bw) / 2
    by0 = ry_bot
    by1 = H * 0.92
    d.rounded_rectangle([bx0, by0, bx0 + bw, by1], radius=W * 0.045, fill=0)
    # mouth: a white slot the receipt emerges from (slightly wider than the strip)
    slot_pad = frame * 1.6
    d.rectangle([rx0 - slot_pad, by0 - frame * 0.5, rx0 + rw + slot_pad, by0 + H * 0.028], fill=255)
    # feed button: white dot on the body, lower-right
    br = W * 0.036
    bcx, bcy = bx0 + bw * 0.82, (by0 + by1) / 2 + H * 0.035
    d.ellipse([bcx - br, bcy - br, bcx + br, bcy + br], fill=255)

    img = img.filter(ImageFilter.GaussianBlur(W * 0.0022))
    return img.resize((size, size), Image.LANCZOS)


# ---------------------------------------------------------------- data analysis
def src_data(size=1000):
    """A clean vertical bar chart — solid bars sit crisp in the block grid."""
    W = H = size * SS
    img = Image.new("L", (W, H), 255)
    d = ImageDraw.Draw(img)
    margin = W * 0.09
    base = H * 0.84
    heights = [0.30, 0.52, 0.40, 0.66, 0.55, 0.82, 0.72, 0.95,
               0.80, 0.62, 0.88, 0.70, 0.46, 0.34]
    n = len(heights)
    gap = W * 0.012
    bw = (W - 2 * margin - (n - 1) * gap) / n
    for i, hf in enumerate(heights):
        x0 = margin + i * (bw + gap)
        d.rectangle([x0, base - hf * H * 0.60, x0 + bw, base], fill=0)
    d.rectangle([margin * 0.7, base, W - margin * 0.7, base + max(4, int(W * 0.012))], fill=0)
    img = img.filter(ImageFilter.GaussianBlur(W * 0.0010))
    return img.resize((size, size), Image.LANCZOS)


# ---------------------------------------------------------------- chessbot
# The ChessBot king: the top-left (solid) cell of the chess sprite sheet, saved as a
# clean dark-on-white crop in covers-src. A bold solid mass -> reads great in the
# block grid (no thin linework to vanish). Pairs with the ESP32 ChessBot repo.
def src_chess(size=1000):
    king = Image.open(r"C:\website\tools\covers-src\chessbot-king.png").convert("L")
    return king.resize((size, size), Image.LANCZOS)


# ---------------------------------------------------------------- minesweeper
# The classic minesweeper mine: a solid orb with fat radiating spikes and a
# little square shine. All solid masses (orb + thick spikes) so nothing thins
# out in the coarse block grid — the most iconic read for the infinite-sweeper.
def src_minesweeper(size=1000):
    W = H = size * SS
    img = Image.new("L", (W, H), 255)
    d = ImageDraw.Draw(img)
    cx, cy = W / 2, H / 2
    r = W * 0.24                       # orb radius
    spike_len = W * 0.40               # tip distance from centre
    spike_w = max(6, int(W * 0.060))   # fat spikes survive the downsample
    cap = W * 0.045                     # square nub at each spike tip (blocky classic look)
    for k in range(8):
        ang = k * math.pi / 4
        tx, ty = cx + math.cos(ang) * spike_len, cy + math.sin(ang) * spike_len
        d.line([(cx, cy), (tx, ty)], fill=0, width=spike_w)
        d.rectangle([tx - cap, ty - cap, tx + cap, ty + cap], fill=0)
    d.ellipse([cx - r, cy - r, cx + r, cy + r], fill=0)
    # classic upper-left shine: a white notch punched into the orb (reads as a
    # pumpkin speck inside the knocked-out mine)
    s = r * 0.34
    sx, sy = cx - r * 0.42, cy - r * 0.42
    d.rectangle([sx, sy, sx + s, sy + s], fill=255)
    img = img.filter(ImageFilter.GaussianBlur(W * 0.0024))
    return img.resize((size, size), Image.LANCZOS)


if __name__ == "__main__":
    C = r"C:\website\assets\covers"
    S = r"C:\website\tools\covers-src"   # clean pumpkin-on-parchment originals
    # procedural / clean sources
    asciify(src_eternal(), C + r"\eternal-fm.webp")
    asciify(src_invoice(), C + r"\invoice.webp")
    asciify(src_data(),    C + r"\data-analysis.webp")   # new bar chart (kept)
    asciify(src_chess(),   C + r"\chessbot.webp")         # ESP32 ChessBot king
    asciify(src_printer(), C + r"\printer.webp")          # thermal receipt printer
    asciify(src_minesweeper(), C + r"\minesweeper.webp")  # infinite minesweeper mine
    asciify(src_eye(),     C + r"\eye.webp", cut=205)     # vision1 eye easter egg (1/100 wall tile)
    asciify(src_eye_closed(), C + r"\eye-closed.webp", cut=205)  # favicon blink (tab blur)
    # lissajous / discord / make-your-own: re-screen the original letter-ASCII art
    # (the look that was working — keep these on the reascii path)
    for name in ("lissajous", "discord", "make-your-own"):
        reascii(S + "\\" + name + ".webp", C + "\\" + name + ".webp")

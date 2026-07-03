"""Generate the favicon set from the real eye.webp ASCII-eye motif.

Composites the actual block-shade eye cutout onto a pumpkin-orange tile
(so the icon matches the site's eye, not a redrawn approximation), then
downsamples with LANCZOS for crisp small sizes.
Outputs favicon.ico (multi-size), favicon.svg (embeds the bitmap),
favicon-closed.svg (block-style closed lid, swapped in when the tab
loses focus), and apple-touch-icon.png.
"""
import base64
from io import BytesIO
from pathlib import Path
from PIL import Image, ImageDraw

ROOT = Path(__file__).resolve().parent.parent
EYE = ROOT / "assets" / "covers" / "eye.webp"
ORANGE = (201, 80, 0, 255)   # --pumpkin #C95000

M = 1024                     # master canvas
RADIUS = int(12 / 64 * M)    # rounded-tile corner, matching the 64-grid r=12
EYE_W = int(0.86 * M)        # eye width as a fraction of the tile


def build_master() -> Image.Image:
    tile = Image.new("RGBA", (M, M), (0, 0, 0, 0))
    mask = Image.new("L", (M, M), 0)
    ImageDraw.Draw(mask).rounded_rectangle([0, 0, M - 1, M - 1], radius=RADIUS, fill=255)
    tile.paste(Image.new("RGBA", (M, M), ORANGE), (0, 0), mask)

    eye = Image.open(EYE).convert("RGBA")
    h = round(EYE_W * eye.height / eye.width)
    eye = eye.resize((EYE_W, h), Image.LANCZOS)
    tile.alpha_composite(eye, ((M - EYE_W) // 2, (M - h) // 2))
    # re-clip to the rounded tile in case the eye overflowed the corners
    tile.putalpha(Image.composite(tile.split()[3], Image.new("L", (M, M), 0), mask))
    return tile


EYE_CLOSED = ROOT / "assets" / "covers" / "eye-closed.webp"


def build_closed_master() -> Image.Image:
    """Closed-eye tile: the drawn shut-eye cover (make_covers.src_eye_closed),
    screened by the same asciify pass as the open eye, on the same tile."""
    tile = Image.new("RGBA", (M, M), (0, 0, 0, 0))
    mask = Image.new("L", (M, M), 0)
    ImageDraw.Draw(mask).rounded_rectangle([0, 0, M - 1, M - 1], radius=RADIUS, fill=255)
    tile.paste(Image.new("RGBA", (M, M), ORANGE), (0, 0), mask)

    eye = Image.open(EYE_CLOSED).convert("RGBA")
    eye = eye.crop(eye.getbbox())            # drop the baked title strip; centre the art itself
    h = round(EYE_W * eye.height / eye.width)
    eye = eye.resize((EYE_W, h), Image.LANCZOS)
    tile.alpha_composite(eye, ((M - EYE_W) // 2, (M - h) // 2))
    tile.putalpha(Image.composite(tile.split()[3], Image.new("L", (M, M), 0), mask))
    return tile


def write_svg(img: Image.Image, path: Path) -> None:
    buf = BytesIO()
    img.resize((256, 256), Image.LANCZOS).save(buf, format="PNG")
    b64 = base64.b64encode(buf.getvalue()).decode()
    svg = (
        "<svg xmlns='http://www.w3.org/2000/svg' viewBox='0 0 256 256'>"
        f"<image width='256' height='256' href='data:image/png;base64,{b64}'/></svg>\n"
    )
    path.write_text(svg, encoding="utf-8")


def main() -> None:
    master = build_master()

    sizes = [16, 32, 48, 64, 128, 256]
    frames = [master.resize((s, s), Image.LANCZOS) for s in sizes]
    frames[0].save(ROOT / "favicon.ico", sizes=[(s, s) for s in sizes],
                   append_images=frames[1:])
    master.resize((180, 180), Image.LANCZOS).save(ROOT / "apple-touch-icon.png")

    write_svg(master, ROOT / "favicon.svg")
    write_svg(build_closed_master(), ROOT / "favicon-closed.svg")
    print("wrote favicon.ico, favicon.svg, favicon-closed.svg, apple-touch-icon.png")


if __name__ == "__main__":
    main()

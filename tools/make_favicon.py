"""Generate the favicon set: a pumpkin-orange tile with the ASCII-eye motif.

Draws at 4x (1024px) and downsamples with LANCZOS for crisp small sizes.
Outputs favicon.ico (multi-size), favicon.svg, and apple-touch-icon.png.
"""
from pathlib import Path
from PIL import Image, ImageDraw

ROOT = Path(__file__).resolve().parent.parent
ORANGE = (201, 80, 0, 255)      # --pumpkin #C95000
PAPER = (244, 242, 235, 255)    # --paper  #F4F2EB (the "white" mark)

M = 1024  # master canvas, 16x the 64-unit design grid
S = M / 64  # scale from the approved 64-unit SVG mockup


def draw_master() -> Image.Image:
    img = Image.new("RGBA", (M, M), (0, 0, 0, 0))
    d = ImageDraw.Draw(img)
    # rounded tile (radius 12 on the 64 grid)
    d.rounded_rectangle([0, 0, M - 1, M - 1], radius=int(12 * S), fill=ORANGE)
    # almond eye outline: ellipse rx=22 ry=13, stroke 4
    cx = cy = 32 * S
    rx, ry = 22 * S, 13 * S
    d.ellipse([cx - rx, cy - ry, cx + rx, cy + ry], outline=PAPER, width=round(4 * S))
    # iris: filled circle r=6
    ir = 6 * S
    d.ellipse([cx - ir, cy - ir, cx + ir, cy + ir], fill=PAPER)
    return img


def main() -> None:
    master = draw_master()

    sizes = [16, 32, 48, 64, 128, 256]
    frames = [master.resize((s, s), Image.LANCZOS) for s in sizes]
    frames[0].save(ROOT / "favicon.ico", sizes=[(s, s) for s in sizes],
                   append_images=frames[1:])

    master.resize((180, 180), Image.LANCZOS).save(ROOT / "apple-touch-icon.png")

    svg = (
        "<svg xmlns='http://www.w3.org/2000/svg' viewBox='0 0 64 64'>"
        "<rect width='64' height='64' rx='12' fill='#C95000'/>"
        "<ellipse cx='32' cy='32' rx='22' ry='13' fill='none' "
        "stroke='#F4F2EB' stroke-width='4'/>"
        "<circle cx='32' cy='32' r='6' fill='#F4F2EB'/></svg>\n"
    )
    (ROOT / "favicon.svg").write_text(svg, encoding="utf-8")
    print("wrote favicon.ico, favicon.svg, apple-touch-icon.png")


if __name__ == "__main__":
    main()

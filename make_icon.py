"""
Generates icon.ico (multi-size) and icon.png for JizzAI  (v1.8 design: dark tile, glowing "J" + spark).

    python make_icon.py

Needs Pillow (pip install pillow). build.py runs this automatically when icon.ico is missing.
Change the colours below if you want a different look.
"""
import os, math
from PIL import Image, ImageDraw, ImageFilter

HERE = os.path.dirname(os.path.abspath(__file__))
BG_TOP = (30, 38, 70)         # tile gradient top
BG_BOTTOM = (10, 13, 26)      # tile gradient bottom
J_A = (60, 235, 180)          # "J" gradient start (mint)
J_B = (70, 170, 255)          # "J" gradient end (sky blue)
SPARK = (255, 200, 80)        # amber sparkle
BIG = 1024                    # drawn big, then scaled down (smooth edges)


def _lin(size, a, b, kx=0.25, ky=0.75):
    g = Image.new("RGBA", (size, size))
    px = g.load()
    for y in range(size):
        for x in range(size):
            k = (ky * y + kx * x) / size
            px[x, y] = tuple(int(a[i] + (b[i] - a[i]) * k) for i in range(3)) + (255,)
    return g


def _stroke(d, pts, w, fill=255):
    """Thick round-capped polyline (stamps discs along the path)."""
    r = w / 2
    for (x0, y0), (x1, y1) in zip(pts, pts[1:]):
        n = max(2, int(math.hypot(x1 - x0, y1 - y0) / 3))
        for i in range(n + 1):
            x, y = x0 + (x1 - x0) * i / n, y0 + (y1 - y0) * i / n
            d.ellipse((x - r, y - r, x + r, y + r), fill=fill)


def _j_path(s):
    top_l, top_r, stem_x = (0.30 * s, 0.27 * s), (0.64 * s, 0.27 * s), 0.64 * s
    cx, cy, rad = 0.445 * s, 0.60 * s, 0.195 * s          # hook circle
    pts = [top_l, top_r, (stem_x, cy)]
    for a in range(0, 181, 4):                             # hook: right -> bottom -> left
        t = math.radians(a)
        pts.append((cx + rad * math.cos(t), cy + rad * math.sin(t)))
    return pts


def _star(d, cx, cy, r, fill, k=0.26):
    pts = []
    for i in range(8):
        a = math.pi / 4 * i - math.pi / 2
        rr = r if i % 2 == 0 else r * k
        pts.append((cx + rr * math.cos(a), cy + rr * math.sin(a)))
    d.polygon(pts, fill=fill)


def make_master():
    s = BIG
    mask = Image.new("L", (s, s), 0)
    ImageDraw.Draw(mask).rounded_rectangle((0, 0, s - 1, s - 1), radius=int(s * 0.23), fill=255)
    base = Image.new("RGBA", (s, s), (0, 0, 0, 0))
    base.paste(_lin(s, BG_TOP, BG_BOTTOM, 0.0, 1.0), (0, 0), mask)

    # thin light rim
    rim = Image.new("L", (s, s), 0)
    rd = ImageDraw.Draw(rim)
    rd.rounded_rectangle((0, 0, s - 1, s - 1), radius=int(s * 0.23), outline=255, width=6)
    base.paste(Image.new("RGBA", (s, s), (255, 255, 255, 40)), (0, 0), rim)

    # glow behind the J
    jm = Image.new("L", (s, s), 0)
    _stroke(ImageDraw.Draw(jm), _j_path(s), int(s * 0.145))
    glow = jm.filter(ImageFilter.GaussianBlur(34)).point(lambda v: int(v * 0.55))
    base.paste(_lin(s, J_A, J_B), (0, 0), glow)

    # the J itself (gradient)
    base.paste(_lin(s, J_A, J_B), (0, 0), jm)

    # amber sparkle with glow
    sp = Image.new("L", (s, s), 0)
    _star(ImageDraw.Draw(sp), int(s * .79), int(s * .23), int(s * .115), 255)
    base.paste(Image.new("RGBA", (s, s), SPARK + (255,)), (0, 0), sp.filter(ImageFilter.GaussianBlur(22)).point(lambda v: int(v * .6)))
    base.paste(Image.new("RGBA", (s, s), SPARK + (255,)), (0, 0), sp)
    return base


def main():
    master = make_master()
    sizes = [16, 24, 32, 48, 64, 128, 256]
    master.resize((512, 512), Image.LANCZOS).save(os.path.join(HERE, "icon.png"))
    imgs = [master.resize((n, n), Image.LANCZOS) for n in sizes]
    imgs[-1].save(os.path.join(HERE, "icon.ico"), format="ICO", sizes=[(n, n) for n in sizes],
                  append_images=imgs[:-1])
    print("icon.ico + icon.png written to", HERE)


if __name__ == "__main__":
    main()

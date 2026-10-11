"""
Generates icon.ico (multi-size) and icon.png for 8AI
(v2.9 design: vivid gradient tile, glass highlight, bold white "8" shaped like a chat bubble + spark).

    python make_icon.py

Needs Pillow (pip install pillow). build.py runs this automatically when icon.ico is missing.
Change the colours below if you want a different look.
"""
import os, math
from PIL import Image, ImageDraw, ImageFilter, ImageChops

HERE = os.path.dirname(os.path.abspath(__file__))
BG_A = (96, 52, 255)          # tile gradient start (violet)
BG_B = (20, 130, 255)         # tile gradient end (blue)
GLOW_1 = (0, 230, 255)        # cyan glow (top right)
GLOW_2 = (255, 70, 200)       # magenta glow (bottom left)
EIGHT_A = (255, 255, 255)     # "8" gradient top
EIGHT_B = (212, 226, 255)     # "8" gradient bottom
BIG = 1024                    # drawn big, then scaled down (smooth edges)
R = 0.225                     # tile corner radius


def _grad(size, a, b, diagonal=True):
    """Smooth linear gradient (built small, scaled up -> fast)."""
    n = 64
    g = Image.new("RGB", (n, n))
    px = g.load()
    for y in range(n):
        for x in range(n):
            k = ((x + y) / (2 * n - 2)) if diagonal else (y / (n - 1))
            px[x, y] = tuple(int(a[i] + (b[i] - a[i]) * k) for i in range(3))
    return g.resize((size, size), Image.BICUBIC).convert("RGBA")


def _stroke(d, pts, w, fill=255):
    """Thick round-capped polyline (stamps discs along the path)."""
    r = w / 2
    for (x0, y0), (x1, y1) in zip(pts, pts[1:]):
        n = max(2, int(math.hypot(x1 - x0, y1 - y0) / 3))
        for i in range(n + 1):
            x, y = x0 + (x1 - x0) * i / n, y0 + (y1 - y0) * i / n
            d.ellipse((x - r, y - r, x + r, y + r), fill=fill)


def _ring(cx, cy, r):
    return [(cx + r * math.cos(math.radians(a)), cy + r * math.sin(math.radians(a))) for a in range(0, 365, 3)]


def _eight_mask(s):
    """Digit 8 = small ring on top + big ring below, with a speech-bubble tail at the bottom left."""
    m = Image.new("L", (s, s), 0)
    d = ImageDraw.Draw(m)
    w = int(s * 0.118)
    _stroke(d, _ring(0.50 * s, 0.355 * s, 0.118 * s), w)
    _stroke(d, _ring(0.50 * s, 0.628 * s, 0.150 * s), w)
    # chat-bubble tail (wedge, corners rounded by blur + threshold)
    t = Image.new("L", (s, s), 0)
    ImageDraw.Draw(t).polygon([(0.432 * s, 0.800 * s), (0.255 * s, 0.872 * s), (0.312 * s, 0.672 * s)], fill=255)
    t = t.filter(ImageFilter.GaussianBlur(14)).point(lambda v: 255 if v > 150 else 0).filter(ImageFilter.GaussianBlur(1.5))
    m = ImageChops.lighter(m, t)
    return m


def _star(d, cx, cy, r, fill, k=0.22):
    pts = []
    for i in range(8):
        a = math.pi / 4 * i - math.pi / 2
        rr = r if i % 2 == 0 else r * k
        pts.append((cx + rr * math.cos(a), cy + rr * math.sin(a)))
    d.polygon(pts, fill=fill)


def _blob(s, box, color, blur, alpha):
    m = Image.new("L", (s, s), 0)
    ImageDraw.Draw(m).ellipse(box, fill=255)
    m = m.filter(ImageFilter.GaussianBlur(blur)).point(lambda v: int(v * alpha))
    return Image.new("RGBA", (s, s), color + (255,)), m


def make_master():
    s = BIG
    tile = Image.new("L", (s, s), 0)
    ImageDraw.Draw(tile).rounded_rectangle((0, 0, s - 1, s - 1), radius=int(s * R), fill=255)

    # --- background: gradient + two soft colour glows
    bg = _grad(s, BG_A, BG_B)
    for box, col in (((int(s * .45), -int(s * .25), int(s * 1.25), int(s * .55)), GLOW_1),
                     ((-int(s * .30), int(s * .55), int(s * .55), int(s * 1.30)), GLOW_2)):
        img, m = _blob(s, box, col, 110, 0.75)
        bg.paste(img, (0, 0), m)

    base = Image.new("RGBA", (s, s), (0, 0, 0, 0))
    base.paste(bg, (0, 0), tile)

    # --- glass highlight on the upper half
    hl = Image.new("L", (s, s), 0)
    ImageDraw.Draw(hl).ellipse((-int(s * .25), -int(s * .62), int(s * 1.25), int(s * .52)), fill=255)
    hl = ImageChops.multiply(hl.filter(ImageFilter.GaussianBlur(6)).point(lambda v: int(v * .20)), tile)
    base.paste(Image.new("RGBA", (s, s), (255, 255, 255, 255)), (0, 0), hl)

    # --- inner rim
    rim = Image.new("L", (s, s), 0)
    ImageDraw.Draw(rim).rounded_rectangle((3, 3, s - 4, s - 4), radius=int(s * R), outline=255, width=6)
    base.paste(Image.new("RGBA", (s, s), (255, 255, 255, 70)), (0, 0), rim)

    # --- the 8: soft shadow, glow, then white gradient
    em = _eight_mask(s)
    shadow = ImageChops.offset(em, 0, int(s * .022)).filter(ImageFilter.GaussianBlur(26)).point(lambda v: int(v * .45))
    base.paste(Image.new("RGBA", (s, s), (20, 10, 90, 255)), (0, 0), shadow)
    glow = em.filter(ImageFilter.GaussianBlur(30)).point(lambda v: int(v * .55))
    base.paste(Image.new("RGBA", (s, s), (255, 255, 255, 255)), (0, 0), glow)
    base.paste(_grad(s, EIGHT_A, EIGHT_B, diagonal=False), (0, 0), em)

    # --- spark
    sp = Image.new("L", (s, s), 0)
    _star(ImageDraw.Draw(sp), int(s * .775), int(s * .235), int(s * .105), 255)
    base.paste(Image.new("RGBA", (s, s), (255, 255, 255, 255)), (0, 0), sp.filter(ImageFilter.GaussianBlur(20)).point(lambda v: int(v * .8)))
    base.paste(Image.new("RGBA", (s, s), (255, 255, 255, 255)), (0, 0), sp)
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

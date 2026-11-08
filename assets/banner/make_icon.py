#!/usr/bin/env python3
"""Crispy network icon for server lists (square), in the same neon style as make_network_banner.py.

    python3 make_icon.py <out.gif> <size> [style]      also writes <out>.png (a still frame)

styles:
  ring   a neon ring with a small glitch "C" inside, CRISPY under it
  stack  the banner's CRISPY / NETWORK wordmark, stacked and centred
  block  a dark grass-topped block (seen at an angle) with a neon C on its front face, CRISPY under it
  badge  a small C emblem over a wide CRISPY, with NETWORK under it
"""
import math, random, sys
from PIL import Image, ImageDraw, ImageFont

OUT, N = sys.argv[1], int(sys.argv[2])
STYLE = sys.argv[3] if len(sys.argv) > 3 else "ring"
S = N / 128
BOLD = "/usr/share/fonts/truetype/dejavu/DejaVuSans-Bold.ttf"
f = lambda size: ImageFont.truetype(BOLD, max(6, round(size * S)))
PINK, CYAN, WHITE, YELLOW, GREY = (255, 60, 200), (40, 230, 255), (245, 245, 255), (255, 220, 60), (150, 160, 190)
FRAMES, MS = 30, 80
rnd = random.Random(11)
rain = [[rnd.uniform(0, N), rnd.uniform(-N, N), rnd.uniform(2, 5) * S, rnd.choice([PINK, CYAN])] for _ in range(12)]


def glitch_text(d, xy, text, font, t, amp=1.6, main=WHITE):
    """Text with a magenta/cyan after-image that jumps for a couple of frames each loop."""
    a = (amp * 2.2 if t in (0, 1, 15, 16) else amp) * S
    x, y = xy
    for dx, col in ((-a * 2, (120, 20, 110)), (-a, PINK), (a, CYAN)):
        d.text((x + dx, y), text, font=font, fill=col)
    d.text((x, y), text, font=font, fill=main)


def centred(d, y, text, font, t, **kw):
    w = d.textlength(text, font=font)
    glitch_text(d, ((N - w) / 2, y), text, font, t, **kw)


def background(t):
    img = Image.new("RGB", (N, N), (8, 6, 20))
    d = ImageDraw.Draw(img)
    for y in range(N):
        c = int(22 * y / N)
        d.line([(0, y), (N, y)], fill=(8 + c, 6, 20 + c))
    step = max(4, int(16 * S))
    for x in range(0, N, step): d.line([(x, 0), (x, N)], fill=(30, 20, 60))
    for y in range(0, N, step): d.line([(0, y), (N, y)], fill=(30, 20, 60))
    for r in rain:
        r[1] += r[2]
        if r[1] > N: r[0], r[1] = rnd.uniform(0, N), rnd.uniform(-20 * S, 0)
        d.line([(r[0], r[1]), (r[0], r[1] + 7 * S)], fill=r[3], width=max(1, round(S)))
    return img, d


def ring(img, d, t):
    cx, cy, r = N / 2, 52 * S, 34 * S
    pulse = 0.5 + 0.5 * math.sin(t / FRAMES * 2 * math.pi)
    col = tuple(int(a + (b - a) * pulse) for a, b in zip(PINK, CYAN))
    for k, w in ((3.2, (60, 20, 70)), (1.6, col)):
        d.ellipse([cx - r - k * S, cy - r - k * S, cx + r + k * S, cy + r + k * S], outline=w, width=max(1, round(2.2 * S)))
    big = f(44)
    w = d.textlength("C", font=big)
    glitch_text(d, (cx - w / 2, cy - 30 * S), "C", big, t)
    centred(d, 96 * S, "CRISPY", f(20), t, amp=1.0, main=YELLOW if (t // 10) % 2 else WHITE)


def stack(img, d, t):
    centred(d, 30 * S, "CRISPY", f(27), t)
    centred(d, 62 * S, "NETWORK", f(20.5), t)
    d.line([(24 * S, 94 * S), (104 * S, 94 * S)], fill=PINK if (t // 6) % 2 else CYAN, width=max(1, round(2 * S)))


def block(img, d, t):
    # an isometric block: top (grass), left and right faces (dark stone), a neon C on the right face
    cx, top, s = N / 2, 14 * S, 40 * S
    T = [(cx, top), (cx + s, top + s / 2), (cx, top + s), (cx - s, top + s / 2)]
    L = [(cx - s, top + s / 2), (cx, top + s), (cx, top + 2.1 * s), (cx - s, top + 1.6 * s)]
    R = [(cx, top + s), (cx + s, top + s / 2), (cx + s, top + 1.6 * s), (cx, top + 2.1 * s)]
    d.polygon(T, fill=(70, 150, 60)); d.polygon(L, fill=(40, 34, 60)); d.polygon(R, fill=(28, 24, 46))
    for poly in (T, L, R): d.line(poly + [poly[0]], fill=(10, 8, 20), width=max(1, round(S)))
    d.line([T[3], L[1]], fill=(50, 110, 45), width=max(1, round(3 * S)))   # a grassy lip
    d.line([L[1], T[1]], fill=(50, 110, 45), width=max(1, round(3 * S)))
    face = Image.new("RGBA", (int(s), int(1.1 * s)), (0, 0, 0, 0))
    fd = ImageDraw.Draw(face)
    big = ImageFont.truetype(BOLD, int(0.8 * s))
    w = fd.textlength("C", font=big)
    a = (2.4 if t in (0, 1, 15, 16) else 1.2) * S
    for dx, col in ((-a, PINK + (255,)), (a, CYAN + (255,))): fd.text(((s - w) / 2 + dx, -0.12 * s), "C", font=big, fill=col)
    fd.text(((s - w) / 2, -0.12 * s), "C", font=big, fill=WHITE + (255,))
    # shear the letter onto the right face (it slopes up by half a block per block across)
    face = face.transform((int(s), int(1.6 * s)), Image.AFFINE, (1, 0, 0, 0.5, 1, -0.5 * s), resample=Image.BICUBIC)
    img.paste(face, (int(cx), int(top + 0.62 * s)), face)
    centred(d, 100 * S, "CRISPY", f(19), t, amp=1.0)


def badge(img, d, t):
    cx, cy, r = N / 2, 30 * S, 17 * S
    d.ellipse([cx - r, cy - r, cx + r, cy + r], fill=(30, 12, 50), outline=PINK if (t // 6) % 2 else CYAN, width=max(1, round(2 * S)))
    small = f(24)
    w = d.textlength("C", font=small)
    glitch_text(d, (cx - w / 2, cy - 15.5 * S), "C", small, t, amp=1.0)
    centred(d, 54 * S, "CRISPY", f(29), t)
    d.text(((N - d.textlength("NETWORK", font=f(12))) / 2, 92 * S), "NETWORK", font=f(12), fill=GREY)


def frame(t):
    img, d = background(t)
    {"ring": ring, "stack": stack, "block": block, "badge": badge}[STYLE](img, d, t)
    dd = ImageDraw.Draw(img, "RGBA")
    for y in range(0, N, 2): dd.line([(0, y), (N, y)], fill=(0, 0, 0, 45))
    dd.rectangle([0, 0, N - 1, N - 1], outline=PINK, width=max(1, round(2 * S)))
    return img


frames = [frame(t) for t in range(FRAMES)]
pal = [fr.convert("P", palette=Image.ADAPTIVE, colors=96) for fr in frames]
pal[0].save(OUT, save_all=True, append_images=pal[1:], duration=MS, loop=0, optimize=True, disposal=1)
frames[8].save(OUT.rsplit(".", 1)[0] + ".png")
print(f"wrote {OUT}: {N}x{N} {STYLE}, {FRAMES} frames, {FRAMES * MS / 1000:.1f} s loop, + still .png")

#!/usr/bin/env python3
"""Crispy network icon for server lists (square): a big neon "C" with a cyan/magenta glitch after-image, CRISPY under
it, falling neon rain and scanlines, in the same style as make_network_banner.py.

    python3 make_icon.py <out.gif> <size>      also writes <out>.png (a still frame)
"""
import math, random, sys
from PIL import Image, ImageDraw, ImageFont

OUT, N = sys.argv[1], int(sys.argv[2])
S = N / 128
BOLD = "/usr/share/fonts/truetype/dejavu/DejaVuSans-Bold.ttf"
f = lambda size: ImageFont.truetype(BOLD, max(6, round(size * S)))
PINK, CYAN, WHITE, YELLOW = (255, 60, 200), (40, 230, 255), (245, 245, 255), (255, 220, 60)
FRAMES, MS = 30, 80
rnd = random.Random(11)
rain = [[rnd.uniform(0, N), rnd.uniform(-N, N), rnd.uniform(2, 5) * S, rnd.choice([PINK, CYAN])] for _ in range(14)]


def frame(t):
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
    big = f(92)
    w = d.textlength("C", font=big)
    x0, y0 = (N - w) / 2, -6 * S
    glitch = t in (0, 1, 15, 16)   # a short flicker twice a loop
    amp = (5 if glitch else 2) * S
    for dx, col in ((-amp * 2, (120, 20, 110)), (-amp, PINK), (amp, CYAN)):
        d.text((x0 + dx, y0), "C", font=big, fill=col)
    d.text((x0, y0), "C", font=big, fill=WHITE)
    small = f(19)
    sw = d.textlength("CRISPY", font=small)
    d.text(((N - sw) / 2 + 1.5 * S, 98 * S), "CRISPY", font=small, fill=PINK)
    d.text(((N - sw) / 2, 98 * S), "CRISPY", font=small, fill=YELLOW if (t // 8) % 2 else WHITE)
    dd = ImageDraw.Draw(img, "RGBA")
    for y in range(0, N, 2): dd.line([(0, y), (N, y)], fill=(0, 0, 0, 50))
    dd.rectangle([0, 0, N - 1, N - 1], outline=PINK, width=max(1, round(2 * S)))
    return img


frames = [frame(t) for t in range(FRAMES)]
pal = [fr.convert("P", palette=Image.ADAPTIVE, colors=96) for fr in frames]
pal[0].save(OUT, save_all=True, append_images=pal[1:], duration=MS, loop=0, optimize=True, disposal=1)
frames[8].save(OUT.rsplit(".", 1)[0] + ".png")
print(f"wrote {OUT}: {N}x{N}, {FRAMES} frames, {FRAMES * MS / 1000:.1f} s loop, + still .png")

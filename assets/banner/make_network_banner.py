#!/usr/bin/env python3
"""Crispy network server-list banner: the whole network, not just Anarchy (animated GIF + a still PNG).

    python3 make_network_banner.py <out.gif> <width> <height> <address>

Same look as make_banner.py (the old Anarchy-only banner): the CRISPY / NETWORK logo with a cyan/magenta
after-image, then one slide per gamemode, ending on the address. The still PNG (same name, .png) shows the last
slide, for sites that don't take GIFs. Every claim on a slide is checked against the servers (see marketing/).
"""
import math, random, sys
from PIL import Image, ImageDraw, ImageFont

OUT, W, H, ADDRESS = sys.argv[1], int(sys.argv[2]), int(sys.argv[3]), sys.argv[4]
S = H / 60                                     # scale everything from the 60 px design
BOLD = "/usr/share/fonts/truetype/dejavu/DejaVuSans-Bold.ttf"
MONO = "/usr/share/fonts/truetype/dejavu/DejaVuSansMono-Bold.ttf"
f = lambda path, size: ImageFont.truetype(path, max(8, round(size * S)))

PINK, CYAN, YELLOW, WHITE, GREY = (255, 60, 200), (40, 230, 255), (255, 220, 60), (245, 245, 255), (150, 160, 190)
SLIDES = [  # (headline, sub-line, headline colour)
    ("ANARCHY · SKYBLOCK · FACTIONS · PVP", "one network, Java + Bedrock, no mods needed", WHITE),
    ("ANARCHY SINCE 2020", "no rules · cyberware implants · custom enchants", PINK),
    ("SKYBLOCK, NO PAY-TO-WIN", "skills · pets · bazaar · minions · a boss rift", (120, 255, 120)),
    ("MULTIVERSE: 36 CHARACTERS", "kit PvP · ranked duels · co-op zombie waves", (255, 150, 60)),
    ("OLD-SCHOOL FACTIONS", "1.8 combat · cannons · set raid windows", YELLOW),
    (ADDRESS.upper(), "JAVA + BEDROCK · JOIN NOW", CYAN),
]
FPS_MS, PER_SLIDE = 90, 14                     # 14 frames x 90 ms, plus a held last frame per slide
FRAMES = PER_SLIDE * len(SLIDES)
rnd = random.Random(7)
rain = [[rnd.uniform(0, W), rnd.uniform(-H, H), rnd.uniform(1.5, 4) * S, rnd.choice([PINK, CYAN])] for _ in range(int(12 * W / 468))]


def background(t):
    img = Image.new("RGB", (W, H), (8, 6, 20))
    d = ImageDraw.Draw(img)
    for y in range(H):                         # vertical gradient
        c = int(18 * y / H)
        d.line([(0, y), (W, y)], fill=(8 + c, 6, 20 + c))
    step = int(12 * S)                         # static neon grid (a drifting one triples the file size)
    off = 0
    for x in range(-step, W + step, step):
        d.line([(x - off, 0), (x - off, H)], fill=(30, 20, 60))
    for y in range(0, H, step):
        d.line([(0, y), (W, y)], fill=(30, 20, 60))
    for r in rain:                             # falling neon rain
        r[1] += r[2]
        if r[1] > H: r[0], r[1] = rnd.uniform(0, W), rnd.uniform(-20 * S, 0)
        d.line([(r[0], r[1]), (r[0], r[1] + 5 * S)], fill=r[3], width=1)
    return img


def logo(img, t):
    d = ImageDraw.Draw(img)
    big = f(BOLD, 21)
    x0, y1, y2 = 10 * S, 4 * S, 29 * S
    glitch = (t % 30) in (0, 1, 15) or math.sin(t / 4) > 0.97
    amp = (4 if glitch else 1.5) * S
    for dx, col in ((-amp * 2, (120, 20, 110)), (-amp, PINK), (amp, CYAN)):   # after-images
        d.text((x0 + dx, y1), "CRISPY", font=big, fill=col)
        d.text((x0 - dx, y2), "NETWORK", font=big, fill=col)
    d.text((x0, y1), "CRISPY", font=big, fill=WHITE)
    d.text((x0, y2), "NETWORK", font=big, fill=WHITE)
    sep = x0 + d.textlength("NETWORK", font=big) + 10 * S
    d.line([(sep, 6 * S), (sep, H - 6 * S)], fill=PINK if (t // 6) % 2 else CYAN, width=max(1, round(2 * S)))
    return sep + 10 * S


def slide(img, t, left):
    d = ImageDraw.Draw(img)
    i, k = divmod(t, PER_SLIDE)
    head, sub, col = SLIDES[i]
    hf, sf = f(BOLD, 17 if i < len(SLIDES) - 1 else 18), f(MONO, 10.5)
    room = W - left - 8 * S
    while d.textlength(head, font=hf) > room and hf.size > 9: hf = ImageFont.truetype(BOLD, hf.size - 1)
    while d.textlength(sub, font=sf) > room and sf.size > 8: sf = ImageFont.truetype(MONO, sf.size - 1)
    slide_in = max(0, 4 - k) * 14 * S          # slide in from the right over the first 4 frames
    jitter = (2 * S if k in (0, 1, PER_SLIDE - 1) else 0)
    hx, hy, sy = left + slide_in, 9 * S, 35 * S
    d.text((hx + jitter, hy), head, font=hf, fill=PINK if col != PINK else CYAN)   # glitch shadow
    d.text((hx, hy), head, font=hf, fill=col)
    shown = sub[:max(0, (k - 2) * 6)]          # typewriter sub-line
    d.text((left, sy), shown, font=sf, fill=GREY if i < len(SLIDES) - 1 else YELLOW)
    if i == len(SLIDES) - 1 and (k // 4) % 2:  # blinking cursor on the IP slide
        cx = left + d.textlength(shown, font=sf) + 2 * S
        d.rectangle([cx, sy + 2 * S, cx + 5 * S, sy + 12 * S], fill=YELLOW)


def scanlines(img):
    d = ImageDraw.Draw(img, "RGBA")
    for y in range(0, H, 2):
        d.line([(0, y), (W, y)], fill=(0, 0, 0, 55))
    d.rectangle([0, 0, W - 1, H - 1], outline=PINK)
    return img


frames = []
for t in range(FRAMES):
    img = background(t)
    left = logo(img, t)
    slide(img, t, left)
    frames.append(scanlines(img).convert("P", palette=Image.ADAPTIVE, colors=64))
durations = [FPS_MS] * FRAMES
for n in range(len(SLIDES)):                    # hold each slide's last frame, longest on the IP
    durations[n * PER_SLIDE + PER_SLIDE - 1] = 1800 if n == len(SLIDES) - 1 else 900
frames[0].save(OUT, save_all=True, append_images=frames[1:], duration=durations, loop=0, optimize=True, disposal=1)   # delta frames keep it small
frames[-1].convert("RGB").save(OUT.rsplit(".", 1)[0] + ".png")
print(f"wrote {OUT}: {W}x{H}, {FRAMES} frames, {sum(durations) / 1000:.1f} s loop, + still .png")

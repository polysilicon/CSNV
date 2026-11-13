#!/usr/bin/env python3
"""One gamemode's server-list banner (animated GIF + still PNG/JPG), for listing a mode on its own.

    python3 make_mode_banner.py <mode> <out.gif> <width> <height> <address>      mode: anarchy | skyblock

Same build as make_network_banner.py: the CRISPY / <MODE> logo with an after-image, one slide per feature, ending on
the mode's own address. Anarchy keeps the neon cyber look; Skyblock is green and sky blue with rising sparkles.
Every claim on a slide is on the website's page for the mode, checked against the server (see marketing/).
"""
import math, random, sys
from PIL import Image, ImageDraw, ImageFont

MODE, OUT, W, H, ADDRESS = sys.argv[1], sys.argv[2], int(sys.argv[3]), int(sys.argv[4]), sys.argv[5]
S = H / 60                                     # scale everything from the 60 px design
BOLD = "/usr/share/fonts/truetype/dejavu/DejaVuSans-Bold.ttf"
MONO = "/usr/share/fonts/truetype/dejavu/DejaVuSansMono-Bold.ttf"
f = lambda path, size: ImageFont.truetype(path, max(8, round(size * S)))

WHITE, GREY, YELLOW = (245, 245, 255), (150, 160, 190), (255, 220, 60)
if MODE == "anarchy":
    NAME, A, B, BG, GRID, DEEP = "ANARCHY", (255, 60, 200), (40, 230, 255), ((8, 6, 20), (26, 6, 38)), (30, 20, 60), (120, 20, 110)
    SLIDES = [  # (headline, sub-line, headline colour)
        ("NO RULES · NO CLAIMS · NO RESETS", "one world, untouched since 2020", A),
        ("193 CUSTOM ENCHANTMENTS", "nine rarity tiers · bought with your XP", B),
        ("CYBERPUNK IMPLANTS", "push past capacity, risk cyberpsychosis", (255, 120, 60)),
        ("A MARKET, A BANK AND CRYPTO", "plus a black market you have to find", YELLOW),
        (ADDRESS.upper(), "JAVA + BEDROCK · JOIN NOW", B),
    ]
    STILL = "NO RULES · NO CLAIMS · SINCE 2020"
elif MODE == "skyblock":
    NAME, A, B, BG, GRID, DEEP = "SKYBLOCK", (110, 235, 110), (90, 200, 255), ((6, 18, 34), (10, 42, 56)), (18, 52, 70), (30, 90, 60)
    SLIDES = [
        ("SKYBLOCK, NO PAY-TO-WIN", "7 themed starter islands to grow", A),
        ("5 SKILLS · 68 COLLECTIONS", "every tier pays coins and skill XP", B),
        ("43 MINIONS · PETS · BAZAAR", "minions farm while you play elsewhere", YELLOW),
        ("17 ARMOUR SETS · 19 WEAPONS", "crafted from what you farm", (255, 150, 90)),
        ("MINES, FORESTS, A BOSS RIFT", "levelled mobs · the Sky Lord's Rift", A),
        (ADDRESS.upper(), "JAVA + BEDROCK · JOIN NOW", B),
    ]
    STILL = "SKILLS · MINIONS · PETS · NO PAY-TO-WIN"
else:
    raise SystemExit("mode: anarchy | skyblock")
PINK, CYAN = A, B   # the after-image pair, as in the network banner
FPS_MS, PER_SLIDE = 90, 14                     # 14 frames x 90 ms, plus a held last frame per slide
FRAMES = PER_SLIDE * len(SLIDES)
rnd = random.Random(7)
rain = [[rnd.uniform(0, W), rnd.uniform(-H, H), rnd.uniform(1.5, 4) * S, rnd.choice([PINK, CYAN] + ([YELLOW] if MODE == 'skyblock' else []))] for _ in range(int(12 * W / 468))]


def background(t):
    img = Image.new("RGB", (W, H), BG[0])
    d = ImageDraw.Draw(img)
    for y in range(H):                         # vertical gradient
        u = y / H
        d.line([(0, y), (W, y)], fill=tuple(int(BG[0][i] + (BG[1][i] - BG[0][i]) * u) for i in range(3)))
    step = int(12 * S)                         # static neon grid (a drifting one triples the file size)
    off = 0
    for x in range(-step, W + step, step):
        d.line([(x - off, 0), (x - off, H)], fill=GRID)
    for y in range(0, H, step):
        d.line([(0, y), (W, y)], fill=GRID)
    for r in rain:
        if MODE == "skyblock":                 # sparkles drifting up
            r[1] -= r[2] * 0.5
            if r[1] < 0: r[0], r[1] = rnd.uniform(0, W), H + rnd.uniform(0, 20 * S)
            d.rectangle([r[0], r[1], r[0] + 1.5 * S, r[1] + 1.5 * S], fill=r[3])
        else:                                  # falling neon rain
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
    for dx, col in ((-amp * 2, DEEP), (-amp, PINK), (amp, CYAN)):   # after-images
        d.text((x0 + dx, y1), "CRISPY", font=big, fill=col)
        d.text((x0 - dx, y2), NAME, font=big, fill=col)
    d.text((x0, y1), "CRISPY", font=big, fill=WHITE)
    d.text((x0, y2), NAME, font=big, fill=WHITE)
    sep = x0 + max(d.textlength(NAME, font=big), d.textlength("CRISPY", font=big)) + 10 * S
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
# the still (.png and .jpg, for sites that won't take animation): the gamemodes and the address in one frame
img = background(0)
left = logo(img, 2)
d = ImageDraw.Draw(img)
room = W - left - 8 * S
hf, sf = f(BOLD, 17), f(BOLD, 13)
head, sub = STILL, ADDRESS.upper() + "  ·  JAVA + BEDROCK"
while d.textlength(head, font=hf) > room and hf.size > 9: hf = ImageFont.truetype(BOLD, hf.size - 1)
while d.textlength(sub, font=sf) > room and sf.size > 8: sf = ImageFont.truetype(BOLD, sf.size - 1)
d.text((left + 1.5 * S, 9 * S), head, font=hf, fill=PINK)
d.text((left, 9 * S), head, font=hf, fill=WHITE)
d.text((left, 34 * S), sub, font=sf, fill=CYAN)
still = scanlines(img).convert("RGB")
base = OUT.rsplit(".", 1)[0]
still.save(base + ".png")
still.save(base + ".jpg", quality=95, subsampling=0)
print(f"wrote {OUT}: {W}x{H}, {FRAMES} frames, {sum(durations) / 1000:.1f} s loop, + still .png/.jpg")

#!/usr/bin/env python3
"""TikTok "we're looking for creators" post (1080x1920): a still JPG and a 12 s MP4.

    python3 make_creator_post.py <out dir>

Background: one screenshot per gamemode from the website, dimmed and slowly panning (the video crossfades between
them). Foreground: the network name, the ask, the animated [Creator] tag in its real in-game colours (the pink-to-sage
wave of proxy/tab-animations.yml, animation `creator`), the perks, the Discord and the address. Everything that
matters sits inside TikTok's safe area (clear of the top bar, the right-hand buttons and the caption at the bottom).
Fonts: Lilita One and Silkscreen (SIL Open Font License, in fonts/).
"""
import os, subprocess, sys
from PIL import Image, ImageDraw, ImageFilter, ImageFont

HERE = os.path.dirname(os.path.abspath(__file__))
SHOTS = os.path.join(HERE, "..", "..", "marketing", "site", "images")
OUT = sys.argv[1]
W, H, FPS, SECONDS = 1080, 1920, 30, 12
LILITA = os.path.join(HERE, "fonts", "LilitaOne-Regular.ttf")
PIXEL = os.path.join(HERE, "fonts", "Silkscreen-Bold.ttf")
f = lambda path, size: ImageFont.truetype(path, size)

PINK, PURPLE, WHITE, GOLD, SAGE, GREY = (245, 62, 223), (110, 28, 120), (255, 255, 255), (255, 214, 79), (170, 200, 150), (200, 196, 214)
WAVE = ["#F63EDF", "#FB2BEE", "#F63EDF", "#F152D0", "#EC65C1", "#E878B1", "#E38BA2", "#DE9F93", "#D9B284", "#C7B88A", "#B4BF90", "#A2C596"]
TAG_Y = 620
BACKGROUNDS = ["spawn.webp", "shots/skyblock-hub.webp", "shots/mv-outbreak.webp", "shots/ez-street.webp"]
PERKS = ["The animated [Creator] tag", "Free cosmetics for you", "Private events for your viewers",
         "Early access to new modes", "Your clips on our TikTok"]


def hexc(h): return tuple(int(h[i:i + 2], 16) for i in (1, 3, 5))


def bg_frame(path, t):
    """A screenshot filling the 9:16 frame, slowly zooming in over t (0..1), blurred a little and dimmed."""
    im = Image.open(os.path.join(SHOTS, path)).convert("RGB")
    scale = H / im.height * (1.08 + 0.06 * t)
    im = im.resize((int(im.width * scale), int(im.height * scale)), Image.BILINEAR)
    x = int((im.width - W) * (0.35 + 0.3 * t)); y = (im.height - H) // 2
    im = im.crop((x, y, x + W, y + H)).filter(ImageFilter.GaussianBlur(5))
    return Image.blend(im, Image.new("RGB", (W, H), (14, 8, 22)), 0.72)


def outlined(d, xy, text, font, fill, outline, width, anchor="mm", shadow=None):
    if shadow: d.text((xy[0] + shadow[0], xy[1] + shadow[1]), text, font=font, fill=shadow[2], anchor=anchor, stroke_width=width, stroke_fill=shadow[2])
    d.text(xy, text, font=font, fill=fill, anchor=anchor, stroke_width=width, stroke_fill=outline)


def foreground():
    """Everything but the background and the tag's colours, on a transparent layer."""
    fg = Image.new("RGBA", (W, H), (0, 0, 0, 0)); d = ImageDraw.Draw(fg)
    cx = W // 2
    tf = f(LILITA, 124)
    while d.textlength("CRISPY NETWORK", font=tf) > W - 140: tf = f(LILITA, tf.size - 2)
    outlined(d, (cx, 205), "CRISPY NETWORK", tf, WHITE, PURPLE, 9, shadow=(5, 7, (60, 10, 70)))
    d.rounded_rectangle([cx - 140, 288, cx + 140, 294], radius=3, fill=PINK)
    d.text((cx, 348), "we're looking for", font=f(LILITA, 68), fill=GREY, anchor="mm")
    outlined(d, (cx, 462), "CREATORS", f(LILITA, 178), WHITE, PURPLE, 12, shadow=(7, 9, (60, 10, 70)))
    # the tag plate (its text is drawn per frame, at TAG_Y)
    d.rounded_rectangle([120, TAG_Y - 46, W - 120, TAG_Y + 46], radius=16, fill=(12, 8, 18, 235))
    d.text((cx, TAG_Y + 80), "animated, next to your name on every server", font=f(LILITA, 36), fill=SAGE, anchor="mm")
    # perks (kept clear of TikTok's right-hand buttons)
    top = 735; row = 64
    d.rounded_rectangle([100, top, W - 120, top + 30 + row * len(PERKS)], radius=32, fill=(18, 10, 26, 225), outline=PINK, width=4)
    for i, p in enumerate(PERKS):
        y = top + 15 + row * i + row // 2
        d.text((155, y), "+", font=f(LILITA, 50), fill=PINK, anchor="mm")
        d.text((192, y), p, font=f(LILITA, 50), fill=WHITE, anchor="lm")
    y = top + 30 + row * len(PERKS) + 50
    d.text((cx, y), "any size · YouTube · TikTok · Twitch", font=f(LILITA, 46), fill=GREY, anchor="mm")
    d.text((cx, y + 56), "anarchy · skyblock · pvp · extraction shooter", font=f(LILITA, 40), fill=SAGE, anchor="mm")
    d.text((cx, y + 132), "DM us or join the Discord", font=f(LILITA, 58), fill=WHITE, anchor="mm")
    outlined(d, (cx, y + 200), "discord.gg/hF2bQgU", f(LILITA, 72), GOLD, (40, 20, 0), 4)
    # the address: all of it above TikTok's caption area (roughly the bottom 380 px)
    py = y + 255
    d.rounded_rectangle([170, py, W - 170, py + 96], radius=48, fill=PINK)
    d.text((cx, py + 46), "crispyanarchy.net", font=f(LILITA, 66), fill=WHITE, anchor="mm", stroke_width=3, stroke_fill=(120, 20, 110))
    d.text((cx, py + 134), "java + bedrock · free · no mods", font=f(LILITA, 38), fill=GREY, anchor="mm")
    return fg


def tag(img, step):
    """[CREATOR] YOURNAME in the pixel font: the bracketed tag in the in-game wave (shifted by step), the name white."""
    d = ImageDraw.Draw(img)
    pf = f(PIXEL, 56)
    tag_txt, name = "[CREATOR]", " YOURNAME"
    total = d.textlength(tag_txt, font=pf) + d.textlength(name, font=pf)
    x = (W - total) / 2; y = TAG_Y
    for i, ch in enumerate(tag_txt):
        col = hexc(WAVE[(i - step) % len(WAVE)])
        d.text((x, y), ch, font=pf, fill=col, anchor="lm"); x += d.textlength(ch, font=pf)
    d.text((x, y), name, font=pf, fill=WHITE, anchor="lm")


os.makedirs(OUT, exist_ok=True)
FG = foreground()
# the still: the anarchy background, the wave at rest
still = bg_frame(BACKGROUNDS[0], 0.5).convert("RGBA"); still.alpha_composite(FG); tag(still, 0)
still.convert("RGB").save(os.path.join(OUT, "creators-tiktok.jpg"), quality=93, subsampling=0)
print("wrote creators-tiktok.jpg")

if "--still" not in sys.argv:
    # the video: each background for 3 s with a 0.5 s crossfade, the tag's wave moving like in game (a step per 100 ms)
    per = SECONDS / len(BACKGROUNDS); fade = 0.5
    p = subprocess.Popen(["ffmpeg", "-v", "error", "-y", "-f", "rawvideo", "-pix_fmt", "rgb24", "-s", f"{W}x{H}", "-r", str(FPS), "-i", "-",
                          "-c:v", "libx264", "-pix_fmt", "yuv420p", "-crf", "18", "-preset", "medium", "-movflags", "+faststart",
                          os.path.join(OUT, "creators-tiktok.mp4")], stdin=subprocess.PIPE)
    for n in range(FPS * SECONDS):
        t = n / FPS; k = min(int(t // per), len(BACKGROUNDS) - 1); local = (t - k * per) / per
        frame = bg_frame(BACKGROUNDS[k], local)
        if k + 1 < len(BACKGROUNDS) and t > (k + 1) * per - fade:
            a = (t - ((k + 1) * per - fade)) / fade
            frame = Image.blend(frame, bg_frame(BACKGROUNDS[k + 1], 0), a)
        frame = frame.convert("RGBA"); frame.alpha_composite(FG); tag(frame, int(t * 10))
        p.stdin.write(frame.convert("RGB").tobytes())
    p.stdin.close(); p.wait()
    print("wrote creators-tiktok.mp4")

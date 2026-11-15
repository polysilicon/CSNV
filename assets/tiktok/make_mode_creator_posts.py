#!/usr/bin/env python3
"""One TikTok "we're looking for <mode> creators" post per game mode (1080x1920): a still JPG and a 12 s MP4 each.

    python3 make_mode_creator_posts.py <out dir> [mode ...] [--still]      modes: skyblock anarchy multiverse extraction

Same series look as make_creator_post.py (Lilita One + Silkscreen, the animated [Creator] tag in its in-game colours,
dimmed slowly-zooming screenshots that crossfade), but each post names its mode, uses that mode's own screenshots and
colour, and lists the videos a creator could make there instead of the general perks list. Everything that matters
sits inside TikTok's safe area. Captions to post with: tiktok/captions-modes.md.
"""
import os, subprocess, sys
from PIL import Image, ImageDraw, ImageFilter, ImageFont

HERE = os.path.dirname(os.path.abspath(__file__))
SITE = os.path.join(HERE, "..", "..", "marketing", "site", "images")
W, H, FPS, SECONDS = 1080, 1920, 30, 12
LILITA = os.path.join(HERE, "fonts", "LilitaOne-Regular.ttf")
PIXEL = os.path.join(HERE, "fonts", "Silkscreen-Bold.ttf")
f = lambda path, size: ImageFont.truetype(path, size)
WHITE, GOLD, GREY = (255, 255, 255), (255, 214, 79), (205, 200, 218)
WAVE = ["#F63EDF", "#FB2BEE", "#F63EDF", "#F152D0", "#EC65C1", "#E878B1", "#E38BA2", "#DE9F93", "#D9B284", "#C7B88A", "#B4BF90", "#A2C596"]

MODES = {
    "skyblock": {
        "name": "SKYBLOCK", "accent": (88, 196, 255), "dark": (10, 52, 92), "tint": (6, 16, 30),
        "bg": ["shots/skyblock-hub.webp", "shots/skyblock-minion.webp", "shots/sb-collections.webp", "shots/skyblock-hub.webp"],
        "hook": "one floating island. film the grind.",
        "ideas": ["Island to empire, episode by episode", "Pick 1 of 7 themed starter islands", "Skills, pets, minions and a bazaar",
                  "Levelled mobs in the mines and forests"],
    },
    "anarchy": {
        "name": "ANARCHY", "accent": (255, 92, 70), "dark": (90, 18, 10), "tint": (22, 8, 6),
        "bg": ["spawn.webp", "low.webp", "shots/anarchy-blackmarket.webp", "shots/anarchy-crypto.webp"],
        "hook": "no rules. one world since 2020.",
        "ideas": ["Base hunts, raids and clan wars", "Surviving the wrecked old spawn", "Find the hidden Black Market dealer",
                  "Cyberware implants and custom enchants"],
    },
    "multiverse": {
        "name": "MULTIVERSE", "accent": (196, 110, 255), "dark": (60, 14, 96), "tint": (14, 6, 26),
        "bg": ["shots/mv-outbreak.webp", "shots/mv-tower.webp", "shots/mv-arsenal.webp", "shots/mv-characters.webp"],
        "hook": "36 characters. one arena.",
        "ideas": ["Character vs character showdowns", "Outbreak: how far can your squad get?", "The Tower: a roguelite climb",
                  "1v1 duels with your viewers"],
    },
    "extraction": {
        "name": "EXTRACTION", "accent": (255, 168, 48), "dark": (88, 44, 4), "tint": (20, 13, 4),
        "bg": ["shots/ez-street.webp", "shots/ez-firefight.webp", "shots/ez-city.webp", "shots/ez-bunker.webp"],
        "hook": "loot the city. get out alive.",
        "ideas": ["Raids with last-second extractions", "Team up with strangers, or betray them", "Guns, raiders and revives",
                  "Build up your bunker between runs"],
    },
}


def hexc(h): return tuple(int(h[i:i + 2], 16) for i in (1, 3, 5))


def bg_frame(path, t, tint):
    im = Image.open(os.path.join(SITE, path)).convert("RGB")
    scale = H / im.height * (1.08 + 0.06 * t)
    im = im.resize((int(im.width * scale), int(im.height * scale)), Image.BILINEAR)
    x = int((im.width - W) * (0.35 + 0.3 * t)); y = (im.height - H) // 2
    im = im.crop((x, y, x + W, y + H)).filter(ImageFilter.GaussianBlur(5))
    return Image.blend(im, Image.new("RGB", (W, H), tint), 0.72)


def outlined(d, xy, text, font, fill, outline, width, anchor="mm", shadow=None):
    if shadow: d.text((xy[0] + shadow[0], xy[1] + shadow[1]), text, font=font, fill=shadow[2], anchor=anchor, stroke_width=width, stroke_fill=shadow[2])
    d.text(xy, text, font=font, fill=fill, anchor=anchor, stroke_width=width, stroke_fill=outline)


def fit(d, text, path, size, maxw):
    ft = f(path, size)
    while d.textlength(text, font=ft) > maxw: ft = f(path, ft.size - 2)
    return ft


TAG_Y = 672


def foreground(m):
    fg = Image.new("RGBA", (W, H), (0, 0, 0, 0)); d = ImageDraw.Draw(fg)
    cx, acc, dark = W // 2, m["accent"], m["dark"]
    shadow = (5, 7, tuple(max(0, c - 40) for c in dark))
    outlined(d, (cx, 195), "CRISPY NETWORK", fit(d, "CRISPY NETWORK", LILITA, 84, W - 260), WHITE, dark, 7, shadow=shadow)
    d.text((cx, 285), "we're looking for", font=f(LILITA, 62), fill=GREY, anchor="mm")
    outlined(d, (cx, 400), m["name"], fit(d, m["name"], LILITA, 168, W - 150), acc, dark, 12, shadow=(7, 9, (0, 0, 0)))
    outlined(d, (cx, 530), "CREATORS", f(LILITA, 128), WHITE, dark, 10, shadow=(6, 8, (0, 0, 0)))
    d.rounded_rectangle([cx - 150, 600, cx + 150, 606], radius=3, fill=acc)
    # the tag plate (its text is drawn per frame)
    d.rounded_rectangle([120, TAG_Y - 46, W - 120, TAG_Y + 46], radius=16, fill=(12, 8, 18, 235))
    d.text((cx, TAG_Y + 78), "yours, animated, on every server", font=f(LILITA, 36), fill=(170, 200, 150), anchor="mm")
    # videos you could make (kept clear of TikTok's right-hand buttons)
    top, row = 808, 60
    hook_font = fit(d, m["hook"], LILITA, 50, W - 260)
    d.text((cx, top), m["hook"], font=hook_font, fill=WHITE, anchor="mm")
    box = top + 40
    d.rounded_rectangle([100, box, W - 120, box + 76 + row * len(m["ideas"])], radius=32, fill=(18, 10, 26, 228), outline=acc, width=4)
    d.text((140, box + 40), "VIDEOS YOU COULD MAKE", font=f(PIXEL, 30), fill=acc, anchor="lm")
    for i, idea in enumerate(m["ideas"]):
        y = box + 76 + row * i + row // 2 - 4
        d.rounded_rectangle([141, y - 9, 159, y + 9], radius=5, fill=acc)
        d.text((185, y), idea, font=fit(d, idea, LILITA, 44, W - 330), fill=WHITE, anchor="lm")
    y = box + 76 + row * len(m["ideas"]) + 50
    d.text((cx, y), "any size · YouTube · TikTok · Twitch", font=f(LILITA, 42), fill=GREY, anchor="mm")
    d.text((cx, y + 52), "free cosmetics · private events · early access", font=fit(d, "free cosmetics · private events · early access", LILITA, 38, W - 200), fill=(170, 200, 150), anchor="mm")
    d.text((cx, y + 118), "DM us or join the Discord", font=f(LILITA, 52), fill=WHITE, anchor="mm")
    outlined(d, (cx, y + 176), "discord.gg/hF2bQgU", f(LILITA, 66), GOLD, (40, 20, 0), 4)
    py = y + 222
    d.rounded_rectangle([170, py, W - 170, py + 92], radius=46, fill=acc)
    d.text((cx, py + 44), "crispyanarchy.net", font=f(LILITA, 62), fill=WHITE, anchor="mm", stroke_width=3, stroke_fill=dark)
    assert py + 92 < H - 360, f"{m['name']}: address at {py + 92} runs into TikTok's caption area"
    return fg


def tag(img, step):
    d = ImageDraw.Draw(img); pf = f(PIXEL, 56)
    tag_txt, name = "[CREATOR]", " YOURNAME"
    x = (W - d.textlength(tag_txt, font=pf) - d.textlength(name, font=pf)) / 2
    for i, ch in enumerate(tag_txt):
        d.text((x, TAG_Y), ch, font=pf, fill=hexc(WAVE[(i - step) % len(WAVE)]), anchor="lm"); x += d.textlength(ch, font=pf)
    d.text((x, TAG_Y), name, font=pf, fill=WHITE, anchor="lm")


def make(key, out, video):
    m = MODES[key]; FG = foreground(m)
    still = bg_frame(m["bg"][0], 0.5, m["tint"]).convert("RGBA"); still.alpha_composite(FG); tag(still, 0)
    still.convert("RGB").save(os.path.join(out, f"creators-{key}.jpg"), quality=93, subsampling=0)
    print("wrote", f"creators-{key}.jpg", flush=True)
    if not video: return
    per, fade, bgs = SECONDS / len(m["bg"]), 0.5, m["bg"]
    p = subprocess.Popen(["ffmpeg", "-v", "error", "-y", "-f", "rawvideo", "-pix_fmt", "rgb24", "-s", f"{W}x{H}", "-r", str(FPS), "-i", "-",
                          "-c:v", "libx264", "-pix_fmt", "yuv420p", "-crf", "18", "-preset", "medium", "-movflags", "+faststart",
                          os.path.join(out, f"creators-{key}.mp4")], stdin=subprocess.PIPE)
    for n in range(FPS * SECONDS):
        t = n / FPS; k = min(int(t // per), len(bgs) - 1); local = (t - k * per) / per
        frame = bg_frame(bgs[k], local, m["tint"])
        if k + 1 < len(bgs) and t > (k + 1) * per - fade:
            frame = Image.blend(frame, bg_frame(bgs[k + 1], 0, m["tint"]), (t - ((k + 1) * per - fade)) / fade)
        frame = frame.convert("RGBA"); frame.alpha_composite(FG); tag(frame, int(t * 10))
        p.stdin.write(frame.convert("RGB").tobytes())
    p.stdin.close(); p.wait()
    print("wrote", f"creators-{key}.mp4", flush=True)


if __name__ == "__main__":
    out = sys.argv[1]; os.makedirs(out, exist_ok=True)
    keys = [a for a in sys.argv[2:] if a in MODES] or list(MODES)
    for k in keys: make(k, out, "--still" not in sys.argv)

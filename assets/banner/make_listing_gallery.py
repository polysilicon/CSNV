#!/usr/bin/env python3
"""Server-listing gallery images (Planet Minecraft and other sites with an image gallery), from the website's screenshots.

    python3 make_listing_gallery.py <out dir>

Writes 00-cover.jpg (the four gamemodes in a 2x2 grid with the network name and address) and one 1600x900 JPG per
screenshot with the gamemode tag, a one-line caption and the address. Captions only say what the website says
(marketing/site/build.py); no franchise names, no player counts. Shots that show another franchise's characters
stay out (the Multiverse lobby's statues, the character picker).
"""
import os, sys
from PIL import Image, ImageDraw, ImageFont, ImageFilter

HERE = os.path.dirname(os.path.abspath(__file__))
IMG = os.path.join(HERE, "..", "..", "marketing", "site", "images")
OUT = sys.argv[1]
W, H = 1600, 900
INTER = "/usr/share/fonts/opentype/inter/"
font = lambda name, size: ImageFont.truetype(INTER + name, size)
ADDRESS = "crispyanarchy.net  ·  Java + Bedrock"

MODES = {  # tag, tag colour (pill), text colour on the pill
    "anarchy": ("ANARCHY", (232, 74, 32), (255, 255, 255)),
    "skyblock": ("SKYBLOCK", (70, 200, 95), (8, 30, 12)),
    "multiverse": ("MULTIVERSE", (150, 80, 235), (255, 255, 255)),
    "extraction": ("EXTRACTION ZONE", (240, 176, 40), (30, 20, 0)),
}
SHOTS = [  # file (under images/), mode, caption
    ("spawn.webp", "anarchy", "Never reset since 2020: spawn today"),
    ("shots/anarchy-crypto.webp", "anarchy", "Buy and sell Bitcoin at a live, moving price"),
    ("shots/anarchy-blackmarket.webp", "anarchy", "Find the black market and open doors others can't"),
    ("shots/skyblock-hub.webp", "skyblock", "The hub: market stalls, plots and the island portal"),
    ("shots/skyblock-minion.webp", "skyblock", "43 kinds of minions farm while you play elsewhere"),
    ("shots/sb-collections.webp", "skyblock", "68 collections: every tier pays coins and skill XP"),
    ("shots/mv-outbreak.webp", "multiverse", "Outbreak: co-op zombie waves with guns and upgrades"),
    ("shots/mv-tower.webp", "multiverse", "The Tower: a roguelite climb, floor after floor"),
    ("shots/mv-core.webp", "multiverse", "Core Defense: build a base and keep the core alive"),
    ("shots/ez-street.webp", "extraction", "Loot a ruined city and get out alive"),
    ("shots/ez-commander.webp", "extraction", "The Commander waits in the Core"),
    ("shots/ez-bunker.webp", "extraction", "Your bunker: stations, farms and salvage"),
]


def fit(path, w=W, h=H):
    """Centre-crop to w:h and resize."""
    im = Image.open(os.path.join(IMG, path)).convert("RGB")
    r = w / h
    if im.width / im.height > r:
        cw = int(im.height * r); x = (im.width - cw) // 2; im = im.crop((x, 0, x + cw, im.height))
    else:
        ch = int(im.width / r); y = (im.height - ch) // 2; im = im.crop((0, y, im.width, y + ch))
    return im.resize((w, h), Image.LANCZOS)


def shade_bottom(im, height, strength=215):
    """A dark gradient rising from the bottom edge, so text stays readable on any screenshot."""
    g = Image.new("L", (1, height))
    for y in range(height):
        g.putpixel((0, y), int(strength * (y / height) ** 1.4))
    mask = Image.new("L", im.size, 0); mask.paste(g.resize((im.width, height)), (0, im.height - height))
    return Image.composite(Image.new("RGB", im.size, (6, 6, 10)), im, mask)


def frost(im, height):
    """Blur and darken the bottom band, fading in at its top edge: captions read cleanly over HUDs and menus."""
    y0 = im.height - height
    band = im.crop((0, y0, im.width, im.height)).filter(ImageFilter.GaussianBlur(14))
    band = Image.blend(band, Image.new("RGB", band.size, (6, 6, 10)), 0.58)
    fade = Image.new("L", (1, height))
    for y in range(height): fade.putpixel((0, y), min(255, int(255 * y / 60)))
    out = im.copy(); out.paste(band, (0, y0), fade.resize((im.width, height)))
    return out


def pill(d, x, y, text, bg, fg, f):
    tw = d.textlength(text, font=f); pad_x, pad_y = 18, 9
    asc, desc = f.getmetrics()
    d.rounded_rectangle([x, y, x + tw + 2 * pad_x, y + asc + desc + 2 * pad_y - 6], radius=10, fill=bg)
    d.text((x + pad_x, y + pad_y - 3), text, font=f, fill=fg)


def shot(path, mode, caption, out):
    im = frost(shade_bottom(fit(path), 420, 140), 270)
    d = ImageDraw.Draw(im)
    tag, bg, fg = MODES[mode]
    pill(d, 64, H - 228, tag, bg, fg, font("Inter-ExtraBold.otf", 30))
    cf = font("InterDisplay-Bold.otf", 54)
    while d.textlength(caption, font=cf) > W - 128 and cf.size > 30: cf = font("InterDisplay-Bold.otf", cf.size - 2)
    d.text((64 + 2, H - 158 + 2), caption, font=cf, fill=(0, 0, 0))
    d.text((64, H - 158), caption, font=cf, fill=(255, 255, 255))
    d.text((64, H - 78), ADDRESS, font=font("Inter-SemiBold.otf", 28), fill=(205, 210, 220))
    logo = Image.open(os.path.join(IMG, "icon-512.png")).convert("RGBA").resize((56, 56), Image.LANCZOS)
    im.paste(logo, (W - 64 - 56, H - 64 - 56 + 8), logo)
    im.save(out, quality=92, subsampling=0)


def cover(out):
    tiles = [("spawn.webp", "anarchy"), ("shots/skyblock-hub.webp", "skyblock"),
             ("shots/mv-outbreak.webp", "multiverse"), ("shots/ez-street.webp", "extraction")]
    im = Image.new("RGB", (W, H))
    tw, th = W // 2, H // 2
    for i, (p, mode) in enumerate(tiles):
        t = fit(p, tw, th)
        im.paste(t, ((i % 2) * tw, (i // 2) * th))
    im = Image.blend(im, Image.new("RGB", im.size, (8, 8, 14)), 0.42)
    d = ImageDraw.Draw(im)
    for i, (p, mode) in enumerate(tiles):   # each quarter keeps its mode tag
        tag, bg, fg = MODES[mode]
        f = font("Inter-ExtraBold.otf", 26)
        x = (i % 2) * tw + (28 if i % 2 == 0 else tw - 28 - d.textlength(tag, font=f) - 36)
        y = (i // 2) * th + (28 if i < 2 else th - 28 - 50)
        pill(d, x, y, tag, bg, fg, f)
    # the centre card
    cw, ch = 1020, 360
    cx, cy = (W - cw) // 2, (H - ch) // 2
    card = Image.new("RGBA", (cw, ch), (0, 0, 0, 0)); cd = ImageDraw.Draw(card)
    cd.rounded_rectangle([0, 0, cw - 1, ch - 1], radius=28, fill=(10, 10, 16, 228), outline=(255, 255, 255, 40), width=2)
    im.paste(card, (cx, cy), card)
    d = ImageDraw.Draw(im)
    logo = Image.open(os.path.join(IMG, "icon-512.png")).convert("RGBA").resize((96, 96), Image.LANCZOS)
    tf = font("InterDisplay-Black.otf", 84)
    title = "CRISPY NETWORK"
    total = 96 + 24 + d.textlength(title, font=tf)
    x0 = (W - total) / 2
    im.paste(logo, (int(x0), cy + 52), logo)
    d.text((x0 + 96 + 24, cy + 46), title, font=tf, fill=(255, 255, 255))
    sub = "Anarchy  ·  Skyblock  ·  PvP  ·  Extraction"
    sf = font("InterDisplay-Bold.otf", 44)
    d.text(((W - d.textlength(sub, font=sf)) / 2, cy + 178), sub, font=sf, fill=(255, 196, 92))
    af = font("Inter-SemiBold.otf", 32)
    d.text(((W - d.textlength(ADDRESS, font=af)) / 2, cy + 262), ADDRESS, font=af, fill=(205, 210, 220))
    im.save(out, quality=92, subsampling=0)


os.makedirs(OUT, exist_ok=True)
cover(os.path.join(OUT, "00-cover.jpg"))
for i, (p, mode, cap) in enumerate(SHOTS, 1):
    name = f"{i:02d}-{mode}-{os.path.basename(p).rsplit('.', 1)[0]}.jpg"
    shot(p, mode, cap, os.path.join(OUT, name))
print("wrote", len(SHOTS) + 1, "images to", OUT)

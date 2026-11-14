"""Video links for the Crispy Discord bot: a TikTok, Twitter/X or Instagram link in a message gets a reply with the
video itself, so it plays in Discord.

1. Download it with yt-dlp (one file with sound, no ffmpeg needed) and upload it, if it fits the server's upload
   limit and is under MAX_SECONDS long.
2. Otherwise (too big, too long, private, login wall: Instagram usually) reply with the same post on an
   embed-fixing mirror that Discord plays inline (FIXERS). The original message is left alone.
At most MAX_PER_MESSAGE links per message; a per-user cooldown stops spam. Temporary files are deleted at once.
"""
import asyncio, os, re, tempfile, time

LINK = re.compile(r"https?://(?:www\.|m\.|vm\.|vt\.)?(tiktok\.com|twitter\.com|x\.com|instagram\.com)/[^\s<>|]+", re.I)
FIXERS = {"tiktok.com": "tnktok.com", "twitter.com": "fxtwitter.com", "x.com": "fixupx.com", "instagram.com": "kkinstagram.com"}
VIDEO_HINT = {"twitter.com": "/status/", "x.com": "/status/", "instagram.com": ("/reel", "/p/", "/tv/")}
MAX_PER_MESSAGE, MAX_SECONDS, COOLDOWN = 2, 600, 8
_last = {}


def links(text):
    out = []
    for m in LINK.finditer(text or ""):
        url = m.group(0).rstrip(".,)!?>")
        host = m.group(1).lower()
        hint = VIDEO_HINT.get(host)
        if hint and not any(h in url for h in ((hint,) if isinstance(hint, str) else hint)): continue   # a profile, not a post
        if url not in [u for u, _ in out]: out.append((url, host))
    return out[:MAX_PER_MESSAGE]


def fixed(url, host):
    return re.sub(r"(https?://)(?:www\.|m\.)?" + re.escape(host), r"\g<1>" + FIXERS[host], url, count=1, flags=re.I)


async def expand(url):
    """vm./vt.tiktok.com short links: follow the redirect to the full post address (the mirrors want that)."""
    if not re.search(r"//(vm|vt)\.tiktok\.com", url, re.I): return url
    import aiohttp
    try:
        async with aiohttp.ClientSession() as s:
            async with s.get(url, allow_redirects=True, timeout=aiohttp.ClientTimeout(total=10),
                             headers={"User-Agent": "Mozilla/5.0"}) as r:
                return str(r.url).split("?")[0]
    except Exception:
        return url


def _download(url, folder, limit):
    import yt_dlp
    opts = {"outtmpl": os.path.join(folder, "%(id)s.%(ext)s"), "quiet": True, "no_warnings": True, "noprogress": True, "noplaylist": True,
            # one progressive file with sound under the limit; no ffmpeg merging needed
            "format": f"b[ext=mp4][filesize<{limit}]/b[ext=mp4][filesize_approx<{limit}]/b[ext=mp4]/b",
            "max_filesize": limit, "socket_timeout": 20, "retries": 1}
    with yt_dlp.YoutubeDL(opts) as y:
        info = y.extract_info(url, download=False)
        if info.get("_type") == "playlist": info = (info.get("entries") or [None])[0] or {}
        if not info.get("duration") and not info.get("formats"): return None, info
        if (info.get("duration") or 0) > MAX_SECONDS: return None, info
        y.process_ie_result(info, download=True)
        files = [os.path.join(folder, f) for f in os.listdir(folder)]
        files = [f for f in files if os.path.getsize(f) > 0 and not f.endswith(".part")]
        return (files[0] if files else None), info


async def reply_videos(message, discord):
    found = links(message.content)
    if not found: return
    now = time.monotonic()
    if now - _last.get(message.author.id, 0) < COOLDOWN: return
    _last[message.author.id] = now
    limit = (getattr(message.guild, "filesize_limit", None) or 10 * 1024 * 1024) - 256 * 1024
    for url, host in found:
        sent = False
        with tempfile.TemporaryDirectory(prefix="crispy-media-") as tmp:
            try:
                async with message.channel.typing():
                    path, info = await asyncio.wait_for(asyncio.to_thread(_download, url, tmp, limit), timeout=90)
                if path and os.path.getsize(path) <= limit:
                    who = info.get("uploader") or info.get("channel") or ""
                    caption = f"🎬 {('**' + who + '**: ') if who else ''}<{url}>"
                    await message.reply(content=caption[:1900], file=discord.File(path, filename="video.mp4"), mention_author=False)
                    sent = True
            except Exception as e:
                print(f"[media] {url}: {type(e).__name__}: {str(e)[:160]}")
        if not sent:
            try:
                await message.reply(content=fixed(await expand(url), host), mention_author=False)
            except Exception as e:
                print(f"[media] fallback {url}: {e}")

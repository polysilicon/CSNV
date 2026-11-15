"""Video links for the Crispy Discord bot: a TikTok, Twitter/X or Instagram link in a message gets a reply with the
video itself, so it plays in Discord. An X/Twitter post without a video (text, photos) gets a tweet card instead
(FxTwitter's public API: author, text, first photo, quoted tweet, counts), and any $TICKER in a tweet's text gets the
usual ticker chart card (tickers.post_cards).

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


PLATFORM = {"tiktok.com": "TikTok", "twitter.com": "Twitter", "x.com": "X", "instagram.com": "Instagram"}
STATUS = re.compile(r"/status(?:es)?/(\d+)")


async def fetch_tweet(url):
    """The tweet behind an X/Twitter link from FxTwitter's public API (no key), or None."""
    m = STATUS.search(url)
    if not m: return None
    import aiohttp
    try:
        async with aiohttp.ClientSession() as s:
            async with s.get(f"https://api.fxtwitter.com/status/{m.group(1)}", timeout=aiohttp.ClientTimeout(total=10),
                             headers={"User-Agent": "Mozilla/5.0 (compatible; crispy-bot/1.0)"}) as r:
                if r.status != 200: return None
                return (await r.json()).get("tweet")
    except Exception as e:
        print(f"[media] tweet {url}: {type(e).__name__}: {e}")
        return None


def _n(x):
    try: x = int(x)
    except (TypeError, ValueError): return "0"
    return f"{x / 1e6:.1f}M" if x >= 1e6 else f"{x / 1e3:.1f}K" if x >= 1e4 else f"{x:,}"


def tweet_embed(discord, t, who):
    """A tweet as a Discord embed: author, text, first photo, the tweet it quotes, counts and time."""
    a = t.get("author") or {}
    text = (t.get("text") or "").strip()
    em = discord.Embed(description=text[:4000] or None, url=t.get("url"), color=0x1D9BF0,
                       timestamp=__import__("datetime").datetime.fromtimestamp(t["created_timestamp"], __import__("datetime").timezone.utc)
                       if t.get("created_timestamp") else None)
    em.set_author(name=f"{a.get('name', '?')} (@{a.get('screen_name', '?')})"[:250], url=t.get("url"), icon_url=a.get("avatar_url") or None)
    photos = ((t.get("media") or {}).get("photos") or [])
    if photos: em.set_image(url=photos[0].get("url"))
    q = t.get("quote")
    if q:
        qa = (q.get("author") or {}).get("screen_name", "?")
        em.add_field(name=f"Quoting @{qa}", value=((q.get("text") or "").strip()[:900] or "(media)") + (f"\n[open]({q.get('url')})" if q.get("url") else ""), inline=False)
    em.set_footer(text=f"X · 💬 {_n(t.get('replies'))}  🔁 {_n(t.get('retweets'))}  ❤ {_n(t.get('likes'))}"
                       + (f"  👁 {_n(t.get('views'))}" if t.get("views") else "") + f" · shared by {who}")
    return em


def has_video(t):
    m = (t or {}).get("media") or {}
    return bool(m.get("videos")) or any(x.get("type") in ("video", "gif") for x in (m.get("all") or []))
POST_TEXT_MAX = 700   # characters of the post's caption shown under the video


def post_text(info):
    """The post's own caption (tweet text, TikTok/Instagram description) as a Discord quote, or "".
    A trailing t.co link (X adds one pointing at the media itself) is dropped; long text is cut at POST_TEXT_MAX."""
    text = (info.get("description") or "").strip()
    if not text: return ""
    text = re.sub(r"\s*https?://t\.co/\S+\s*$", "", text).strip()
    lines = [l.rstrip() for l in text.splitlines()]
    while lines and not lines[-1].strip(): lines.pop()
    text = "\n".join(lines).strip()
    if not text: return ""
    if len(text) > POST_TEXT_MAX: text = text[:POST_TEXT_MAX].rsplit(" ", 1)[0] + "…"
    text = re.sub(r"\n{3,}", "\n\n", text)
    return "\n".join("> " + l if l.strip() else ">" for l in text.splitlines())


async def fetch(url, host, limit):
    """(path to an uploadable file or None, info) for one link, in a temp folder the caller removes."""
    tmp = tempfile.mkdtemp(prefix="crispy-media-")
    try:
        path, info = await asyncio.wait_for(asyncio.to_thread(_download, url, tmp, limit), timeout=90)
        if path and os.path.getsize(path) <= limit: return tmp, path, info
    except Exception as e:
        print(f"[media] {url}: {type(e).__name__}: {str(e)[:160]}")
    return tmp, None, {}


async def reply_videos(message, discord):
    """Post each linked video as Yoink's own message, without repeating the link. A message that is only links is
    replaced (deleted once the videos are up); one with other words keeps them and just loses its preview. Both need
    Manage Messages in the channel; without it Yoink replies with the video and leaves the message as it is."""
    found = links(message.content)
    if not found: return
    now = time.monotonic()
    if now - _last.get(message.author.id, 0) < COOLDOWN: return
    _last[message.author.id] = now
    limit = (getattr(message.guild, "filesize_limit", None) or 10 * 1024 * 1024) - 256 * 1024
    leftover = message.content
    for url, _ in found: leftover = leftover.replace(url, "")
    leftover = LINK.sub("", leftover).strip()
    me = message.guild.me if message.guild else None
    can_manage = bool(me and message.channel.permissions_for(me).manage_messages)
    replace = can_manage and not leftover          # nothing but links: Yoink's post stands in for it
    who = message.author.display_name
    posted = 0
    import shutil
    import tickers
    for url, host in found:
        tw = await fetch_tweet(url) if host in ("twitter.com", "x.com") else None
        if tw and not has_video(tw):   # a text/photo tweet: Yoink's own card, then charts for its $tickers
            try:
                kw = {"content": f"🐦 **{who}** shared a post", "embed": tweet_embed(discord, tw, who)}
                if replace: await message.channel.send(**kw)
                else: await message.reply(mention_author=False, **kw)
                posted += 1
                syms = tickers.cashtags(tw.get("text") or "")
                if syms: await tickers.post_cards(message, discord, syms, send=message.channel.send)
            except Exception as e:
                print(f"[media] tweet card {url}: {e}")
            continue
        async with message.channel.typing():
            tmp, path, info = await fetch(url, host, limit)
        try:
            creator = info.get("uploader") or info.get("channel") or ""
            plat = PLATFORM[host]
            caption = f"🎬 **{who}** shared {'an' if plat[0] in 'AEIOUX' else 'a'} {plat} video" + (f" from **{creator}**" if creator else "")
            quote = post_text(info)
            if quote: caption += "\n" + quote
            if path:
                kw = {"content": caption[:1900], "file": discord.File(path, filename="video.mp4")}
            else:   # too big, too long or blocked: the same post on a mirror that plays inline
                kw = {"content": f"{caption}\n{fixed(await expand(url), host)}"[:1900]}
            if replace: await message.channel.send(**kw)
            else: await message.reply(mention_author=False, **kw)
            posted += 1
            if tw:   # a video tweet: charts for its $tickers too
                syms = tickers.cashtags(tw.get("text") or "")
                if syms: await tickers.post_cards(message, discord, syms, send=message.channel.send)
        except Exception as e:
            print(f"[media] posting {url}: {e}")
        finally:
            shutil.rmtree(tmp, ignore_errors=True)
    if not posted or not can_manage: return
    try:
        if replace: await message.delete()          # only once the videos are up
        else: await message.edit(suppress=True)     # keep their words, drop the link preview
    except Exception as e:
        print(f"[media] tidy original: {e}")

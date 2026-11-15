"""$TICKER in Minecraft chat, for the Crispy Discord bot's chat bridge.

When someone types "$BTC" (or $NVDA, $EUR, any symbol tickers.py knows) in game chat on a bridged server, Yoink
answers on that server with one line per symbol (at most 2):
    $BTC Bitcoin · $97,412.30 ▲ 3.21% today · ▲ 12.4% since lbxd's first scan
Hover: the day's range and the source; click: the quote page. The lookup is tickers.lookup (the same as Discord's
cards, cached a minute), and the scan counts in scans.py's shared history (Discord and game share one "first scan"
per symbol), credited to the player's linked Discord account if they have one, else to their Minecraft name.
A per-player cooldown stops spam. Information only, not advice.
"""
import json, time
import aiohttp
import scans, tickers

COOLDOWN, MAX_SYMS = 6, 2
_last = {}


def _line(sym, meta, closes, first):
    price = meta.get("regularMarketPrice"); prev = meta.get("chartPreviousClose") or meta.get("previousClose")
    cur = meta.get("currency") or "USD"
    fx = sym.endswith("USD=X")
    show = sym[:3] if fx else sym.replace("-USD", "")
    name = (tickers.CURRENCY_NAMES.get(show, show) if fx else (meta.get("longName") or meta.get("shortName") or show))[:28]
    pricestr = f"${tickers.fmt_rate(price)}" if fx else tickers.fmt(price, cur)
    pct = (price - prev) / prev * 100 if price is not None and prev else None
    parts = [{"text": f"${show} ", "color": "gold", "bold": True}, {"text": f"{name} · ", "color": "gray", "bold": False},
             {"text": pricestr, "color": "white", "bold": True}]
    if pct is not None:
        parts.append({"text": f" {'▲' if pct >= 0 else '▼'} {abs(pct):.2f}% today", "color": "green" if pct >= 0 else "red", "bold": False})
    if first and first.get("price") and price:
        since = (price - first["price"]) / first["price"] * 100
        parts.append({"text": f" · {'▲' if since >= 0 else '▼'} {abs(since):.1f}% since {first['by'].replace(chr(92), '')}'s first scan",
                      "color": "aqua", "bold": False})
    hi, lo = meta.get("regularMarketDayHigh"), meta.get("regularMarketDayLow")
    if (hi is None or lo is None) and closes: hi, lo = max(closes), min(closes)
    hover = (f"Day range: {tickers.fmt(lo, cur)} - {tickers.fmt(hi, cur)}\n" if hi and lo else "") + \
            f"Data: {meta.get('source', 'Yahoo Finance')}, may be delayed · not financial advice\nClick for the chart"
    url = f"https://www.coingecko.com/en/coins/{meta['geckoId']}" if meta.get("geckoId") else f"https://finance.yahoo.com/quote/{sym}"
    root = {"text": "", "extra": parts,
            # both spellings: older servers read clickEvent/hoverEvent, 1.21.5+ click_event/hover_event
            "clickEvent": {"action": "open_url", "value": url}, "click_event": {"action": "open_url", "url": url},
            "hoverEvent": {"action": "show_text", "contents": hover}, "hover_event": {"action": "show_text", "value": hover}}
    return json.dumps(root, ensure_ascii=False)


async def reply(bot, cfg, rcon, player, text):
    """Called by the bridge for each game chat line (player = plain Minecraft name)."""
    syms = tickers.cashtags(text)[:MAX_SYMS]
    if not syms: return
    now = time.monotonic()
    if now - _last.get(player.lower(), 0) < COOLDOWN: return
    _last[player.lower()] = now
    uid = next((u for u, mc in bot.links.items() if mc.lower() == player.lower()), None) or f"mc:{player.lower()}"
    guild = bot.guilds[0].id if bot.guilds else 0
    async with aiohttp.ClientSession() as session:
        for s in syms:
            try:
                got = await tickers.lookup(session, s)
                if not got: continue
                sym, meta, closes = got
                first = scans.note(guild, "t:" + sym, uid, player, meta.get("regularMarketPrice"))
                await rcon(cfg, "tellraw @a " + _line(sym, meta, closes, first))
            except Exception as e:
                print(f"[gametickers] {s}: {type(e).__name__}: {e}")

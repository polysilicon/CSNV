"""Cashtag cards for the Crispy Discord bot: "$AAPL" or "$BTC" in a message gets a reply with the price, the day's
change and range, and a small chart of the day.

Data: Yahoo Finance's public chart endpoint (no key). A stock is looked up as itself; a coin as <SYMBOL>-USD. The best
known coins are tried as crypto first ($BTC is also a fund's ticker), anything else as a stock first, then as a coin.
Information only, delayed by the source, not advice.
"""
import io, re, time
import aiohttp
from PIL import Image, ImageDraw

CASHTAG = re.compile(r"(?<![\w$])\$([A-Za-z]{1,6}(?:[.-][A-Za-z]{1,2})?)(?![\w])")
CRYPTO_FIRST = {"BTC", "ETH", "SOL", "XRP", "DOGE", "ADA", "BNB", "LTC", "AVAX", "DOT", "LINK", "POL", "MATIC", "SHIB",
                "TRX", "TON", "XMR", "PEPE", "USDT", "USDC", "BCH", "XLM", "ATOM", "NEAR", "SUI", "APT", "ARB", "OP", "HBAR"}
UA = {"User-Agent": "Mozilla/5.0 (compatible; crispy-bot/1.0)"}
MAX_PER_MESSAGE = 3
_cache = {}   # symbol -> (time, result)


async def _chart(session, sym):
    url = f"https://query1.finance.yahoo.com/v8/finance/chart/{sym}"
    async with session.get(url, params={"range": "1d", "interval": "5m"}, headers=UA, timeout=aiohttp.ClientTimeout(total=10)) as r:
        if r.status != 200: return None
        d = await r.json()
    res = (d.get("chart") or {}).get("result")
    if not res: return None
    res = res[0]; meta = res.get("meta", {})
    if meta.get("regularMarketPrice") is None: return None
    closes = [c for c in ((res.get("indicators") or {}).get("quote") or [{}])[0].get("close") or [] if c is not None]
    return meta, closes


async def lookup(session, symbol):
    symbol = symbol.upper()
    hit = _cache.get(symbol)
    if hit and time.monotonic() - hit[0] < 60: return hit[1]
    order = [f"{symbol}-USD", symbol] if symbol in CRYPTO_FIRST else [symbol, f"{symbol}-USD"]
    out = None
    for s in order:
        got = await _chart(session, s)
        if got: out = (s, *got); break
    _cache[symbol] = (time.monotonic(), out)
    return out


def chart_png(closes, up):
    W, H, P = 600, 160, 8
    im = Image.new("RGB", (W, H), (43, 45, 49)); d = ImageDraw.Draw(im)
    if len(closes) >= 2:
        lo, hi = min(closes), max(closes); span = (hi - lo) or 1
        pts = [(P + i * (W - 2 * P) / (len(closes) - 1), H - P - (c - lo) / span * (H - 2 * P)) for i, c in enumerate(closes)]
        col = (35, 165, 90) if up else (218, 55, 60)
        d.polygon(pts + [(pts[-1][0], H - P), (pts[0][0], H - P)], fill=tuple(int(x * 0.35 + 43 * 0.65) for x in col))
        d.line(pts, fill=col, width=3)
    b = io.BytesIO(); im.save(b, "PNG"); b.seek(0); return b


def fmt(x, cur):
    if x is None: return "?"
    sign = "$" if cur == "USD" else ""
    if abs(x) >= 1000: s = f"{x:,.2f}"
    elif abs(x) >= 1: s = f"{x:,.2f}"
    else: s = f"{x:.6f}".rstrip("0")
    return sign + s + ("" if cur in ("USD", None) else f" {cur}")


def card(sym, meta, closes):
    """(embed fields as a dict, chart png) for discord.Embed; kept free of discord imports so it can be tested alone."""
    price = meta.get("regularMarketPrice"); prev = meta.get("chartPreviousClose") or meta.get("previousClose")
    cur = meta.get("currency") or "USD"
    ch = (price - prev) if (price is not None and prev) else None
    pct = (ch / prev * 100) if ch is not None and prev else None
    up = (ch or 0) >= 0
    name = meta.get("longName") or meta.get("shortName") or sym
    is_crypto = sym.endswith("-USD")
    hi, lo = meta.get("regularMarketDayHigh"), meta.get("regularMarketDayLow")
    if (hi is None or lo is None) and closes: hi, lo = max(closes), min(closes)
    title = f"{sym.replace('-USD', '')} · {name}"
    arrow = "▲" if up else "▼"
    desc = f"**{fmt(price, cur)}**  {arrow} {fmt(abs(ch), cur) if ch is not None else '?'} ({pct:+.2f}%)" if pct is not None else f"**{fmt(price, cur)}**"
    fields = [("Day range", f"{fmt(lo, cur)} – {fmt(hi, cur)}")]
    exch = meta.get("fullExchangeName") or meta.get("exchangeName")
    if not is_crypto and exch: fields.append(("Exchange", exch))
    state = meta.get("marketState")
    footer = ("Crypto · 24/7" if is_crypto else f"Market: {state.lower()}" if state else "Stock") + " · data from Yahoo Finance, may be delayed · not financial advice"
    return {"title": title, "description": desc, "color": 0x23A55A if up else 0xDA373C, "fields": fields, "footer": footer,
            "url": f"https://finance.yahoo.com/quote/{sym}"}, chart_png(closes, up)


def cashtags(text):
    seen = []
    for m in CASHTAG.finditer(text or ""):
        s = m.group(1).upper()
        if s not in seen and not s.isdigit(): seen.append(s)
    return seen[:MAX_PER_MESSAGE]


async def reply_cards(message, discord):
    syms = cashtags(message.content)
    if not syms: return
    async with aiohttp.ClientSession() as session:
        for s in syms:
            try:
                got = await lookup(session, s)
            except Exception as e:
                print(f"[tickers] {s}: {e}"); continue
            if not got: continue
            sym, meta, closes = got
            data, png = card(sym, meta, closes)
            e = discord.Embed(title=data["title"], description=data["description"], color=data["color"], url=data["url"])
            for n, v in data["fields"]: e.add_field(name=n, value=v, inline=True)
            e.set_footer(text=data["footer"])
            f = discord.File(png, filename=f"{sym}.png"); e.set_image(url=f"attachment://{sym}.png")
            await message.reply(embed=e, file=f, mention_author=False)

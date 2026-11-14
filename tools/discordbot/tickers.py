"""Cashtag cards for the Crispy Discord bot: "$AAPL" or "$BTC" in a message gets a reply with the price, the day's
change and range, and a small chart of the day.

Data, all public and keyless:
- currencies ($EUR, $JPY, ... ISO codes in FIAT): Yahoo Finance FX (<CODE>USD=X), shown both ways against the dollar;
- the best-known coins (CRYPTO_FIRST): Yahoo <SYMBOL>-USD ($BTC is also a fund's ticker, so coins win there);
- anything else: a stock on Yahoo first, then CoinGecko (thousands of smaller coins: the exact symbol with the largest
  market cap), then Yahoo <SYMBOL>-USD.
Information only, delayed by the source, not advice.
"""
import io, re, time
import aiohttp
import scans
from PIL import Image, ImageDraw

CASHTAG = re.compile(r"(?<![\w$])\$([A-Za-z]{1,6}(?:[.-][A-Za-z]{1,2})?)(?![\w])")
CRYPTO_FIRST = {"BTC", "ETH", "SOL", "XRP", "DOGE", "ADA", "BNB", "LTC", "AVAX", "DOT", "LINK", "POL", "MATIC", "SHIB",
                "TRX", "TON", "XMR", "PEPE", "USDT", "USDC", "BCH", "XLM", "ATOM", "NEAR", "SUI", "APT", "ARB", "OP", "HBAR"}
CURRENCY_NAMES = {'EUR': 'Euro', 'GBP': 'British pound', 'JPY': 'Japanese yen', 'CAD': 'Canadian dollar', 'AUD': 'Australian dollar', 'NZD': 'New Zealand dollar', 'CHF': 'Swiss franc', 'CNY': 'Chinese yuan', 'HKD': 'Hong Kong dollar', 'SGD': 'Singapore dollar', 'INR': 'Indian rupee', 'KRW': 'South Korean won', 'MXN': 'Mexican peso', 'BRL': 'Brazilian real', 'ARS': 'Argentine peso', 'CLP': 'Chilean peso', 'COP': 'Colombian peso', 'PEN': 'Peruvian sol', 'ZAR': 'South African rand', 'TRY': 'Turkish lira', 'RUB': 'Russian ruble', 'PLN': 'Polish zloty', 'CZK': 'Czech koruna', 'HUF': 'Hungarian forint', 'SEK': 'Swedish krona', 'NOK': 'Norwegian krone', 'DKK': 'Danish krone', 'ISK': 'Icelandic krona', 'ILS': 'Israeli shekel', 'AED': 'UAE dirham', 'SAR': 'Saudi riyal', 'QAR': 'Qatari riyal', 'KWD': 'Kuwaiti dinar', 'EGP': 'Egyptian pound', 'NGN': 'Nigerian naira', 'KES': 'Kenyan shilling', 'THB': 'Thai baht', 'VND': 'Vietnamese dong', 'IDR': 'Indonesian rupiah', 'MYR': 'Malaysian ringgit', 'PHP': 'Philippine peso', 'TWD': 'New Taiwan dollar', 'PKR': 'Pakistani rupee', 'BDT': 'Bangladeshi taka', 'UAH': 'Ukrainian hryvnia', 'RON': 'Romanian leu', 'BGN': 'Bulgarian lev'}
FIAT = {"EUR", "GBP", "JPY", "CAD", "AUD", "NZD", "CHF", "CNY", "HKD", "SGD", "INR", "KRW", "MXN", "BRL", "ARS", "CLP",
        "COP", "PEN", "ZAR", "TRY", "RUB", "PLN", "CZK", "HUF", "SEK", "NOK", "DKK", "ISK", "ILS", "AED", "SAR", "QAR",
        "KWD", "EGP", "NGN", "KES", "THB", "VND", "IDR", "MYR", "PHP", "TWD", "PKR", "BDT", "UAH", "RON", "BGN"}
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


async def _gecko(session, symbol):
    """A coin CoinGecko knows by exactly this symbol (the one with the largest market cap): (sym, meta, closes)."""
    base = "https://api.coingecko.com/api/v3/"
    async with session.get(base + "search", params={"query": symbol}, headers=UA, timeout=aiohttp.ClientTimeout(total=10)) as r:
        if r.status != 200: return None
        coins = [c for c in (await r.json()).get("coins", []) if c.get("symbol", "").upper() == symbol]
    if not coins: return None
    coin = min(coins, key=lambda c: c.get("market_cap_rank") or 10 ** 9)
    async with session.get(base + "coins/markets", params={"vs_currency": "usd", "ids": coin["id"], "sparkline": "true",
                           "price_change_percentage": "24h"}, headers=UA, timeout=aiohttp.ClientTimeout(total=10)) as r:
        if r.status != 200: return None
        rows = await r.json()
    if not rows or rows[0].get("current_price") is None: return None
    m = rows[0]
    price, ch = m["current_price"], m.get("price_change_24h")
    meta = {"regularMarketPrice": price, "chartPreviousClose": (price - ch) if ch is not None else None, "currency": "USD",
            "longName": m.get("name"), "regularMarketDayHigh": m.get("high_24h"), "regularMarketDayLow": m.get("low_24h"),
            "source": "CoinGecko", "rank": m.get("market_cap_rank"), "geckoId": coin["id"]}
    closes = ((m.get("sparkline_in_7d") or {}).get("price") or [])[-24:]   # hourly: the last day
    return f"{symbol}-USD", meta, closes


async def lookup(session, symbol):
    symbol = symbol.upper()
    hit = _cache.get(symbol)
    if hit and time.monotonic() - hit[0] < 60: return hit[1]
    out = None
    if symbol in FIAT:
        got = await _chart(session, f"{symbol}USD=X")
        if got: out = (f"{symbol}USD=X", *got)
    if out is None:
        order = [f"{symbol}-USD", symbol, "gecko"] if symbol in CRYPTO_FIRST else [symbol, "gecko", f"{symbol}-USD"]
        for s in order:
            try:
                got = await (_gecko(session, symbol) if s == "gecko" else _chart(session, s))
            except Exception as e:
                print(f"[tickers] {symbol} via {s}: {e}"); got = None
            if got: out = got if s == "gecko" else (s, *got); break
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
    else:   # small coins: three significant digits (PEPE is $0.00000388, not $0.000004)
        import math
        d = max(2, -int(math.floor(math.log10(abs(x)))) + 2) if x else 2
        s = f"{x:.{d}f}"
    return sign + s + ("" if cur in ("USD", None) else f" {cur}")


def fmt_rate(x):
    if x is None: return "?"
    return f"{x:,.4f}" if x < 10 else f"{x:,.2f}"


def card(sym, meta, closes):
    """(embed fields as a dict, chart png) for discord.Embed; kept free of discord imports so it can be tested alone."""
    price = meta.get("regularMarketPrice"); prev = meta.get("chartPreviousClose") or meta.get("previousClose")
    cur = meta.get("currency") or "USD"
    ch = (price - prev) if (price is not None and prev) else None
    pct = (ch / prev * 100) if ch is not None and prev else None
    up = (ch or 0) >= 0
    name = meta.get("longName") or meta.get("shortName") or sym
    is_crypto = sym.endswith("-USD")
    if sym.endswith("USD=X"):   # a currency: 1 unit in dollars, and a dollar in it
        code = sym[:3]
        title = f"{code} · {CURRENCY_NAMES.get(code, code)} vs the US dollar"
        arrow = "▲" if up else "▼"
        inv = (1 / price) if price else None
        desc = (f"**1 {code} = ${fmt_rate(price)}**  ·  $1 = {fmt_rate(inv)} {code}\n"
                + (f"{arrow} {pct:+.2f}% today" if pct is not None else ""))
        hi, lo = meta.get("regularMarketDayHigh"), meta.get("regularMarketDayLow")
        if (hi is None or lo is None) and closes: hi, lo = max(closes), min(closes)
        fields = [("Day range", f"${fmt_rate(lo)} – ${fmt_rate(hi)}")] if hi and lo else []
        return {"title": title, "description": desc, "color": 0x23A55A if up else 0xDA373C, "fields": fields,
                "footer": "Currency · data from Yahoo Finance, may be delayed · not financial advice",
                "url": f"https://finance.yahoo.com/quote/{sym}"}, chart_png(closes, up)
    hi, lo = meta.get("regularMarketDayHigh"), meta.get("regularMarketDayLow")
    if (hi is None or lo is None) and closes: hi, lo = max(closes), min(closes)
    title = f"{sym.replace('-USD', '')} · {name}"
    arrow = "▲" if up else "▼"
    desc = f"**{fmt(price, cur)}**  {arrow} {fmt(abs(ch), cur) if ch is not None else '?'} ({pct:+.2f}%)" if pct is not None else f"**{fmt(price, cur)}**"
    fields = [("Day range", f"{fmt(lo, cur)} – {fmt(hi, cur)}")]
    exch = meta.get("fullExchangeName") or meta.get("exchangeName")
    if not is_crypto and exch: fields.append(("Exchange", exch))
    state = meta.get("marketState")
    src = meta.get("source", "Yahoo Finance")
    if meta.get("rank"): fields.append(("Market cap rank", f"#{meta['rank']}"))
    footer = ("Crypto · 24/7" if is_crypto else f"Market: {state.lower()}" if state else "Stock") + f" · data from {src}, may be delayed · not financial advice"
    url = f"https://www.coingecko.com/en/coins/{meta['geckoId']}" if meta.get("geckoId") else f"https://finance.yahoo.com/quote/{sym}"
    return {"title": title, "description": desc, "color": 0x23A55A if up else 0xDA373C, "fields": fields, "footer": footer,
            "url": url}, chart_png(closes, up)


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
            cur = meta.get("currency") or "USD"
            scans.decorate(e, message, "t:" + sym, meta.get("regularMarketPrice"),
                           (lambda x: f"${fmt_rate(x)}") if sym.endswith("USD=X") else (lambda x: fmt(x, cur)))
            f = discord.File(png, filename=f"{sym}.png"); e.set_image(url=f"attachment://{sym}.png")
            await message.reply(embed=e, file=f, mention_author=False)

"""Token cards from contract addresses for the Crispy Discord bot.

An Ethereum-style address (0x + 40 hex: Ethereum, Base, Arbitrum, BSC and other EVM chains) or a Solana address (32-44
base58 characters) in a message gets a reply card from DexScreener's public API (no key): name, symbol and chain,
price with 1 h and 24 h change, liquidity, 24 h volume, market value, how old the trading pair is, and a chart link.
New or thinly traded tokens get a warning line.

Addresses are read from plain text and from links to token sites (pump.fun, DexScreener, Birdeye, Solscan, Etherscan
...); other links are ignored, so long IDs in video or post URLs aren't mistaken for addresses. A string that looks like
an address but matches no token gets no reply. At most 2 per message; results are kept for a minute.
Information only, not advice.
"""
import re, time
import aiohttp
import scans

EVM = re.compile(r"(?<![0-9A-Za-z])0x[0-9a-fA-F]{40}(?![0-9A-Za-z])")
SOL = re.compile(r"(?<![1-9A-HJ-NP-Za-km-z])[1-9A-HJ-NP-Za-km-z]{32,44}(?![1-9A-HJ-NP-Za-km-z])")
URL = re.compile(r"https?://\S+", re.I)
TOKEN_SITES = ("pump.fun", "dexscreener.com", "birdeye.so", "solscan.io", "etherscan.io", "basescan.org", "arbiscan.io",
               "bscscan.com", "gmgn.ai", "photon-sol", "jup.ag", "raydium.io", "geckoterminal.com", "dextools.io")
CHAINS = {"solana": "Solana", "ethereum": "Ethereum", "base": "Base", "bsc": "BNB Chain", "arbitrum": "Arbitrum",
          "polygon": "Polygon", "avalanche": "Avalanche", "optimism": "Optimism", "blast": "Blast", "sui": "Sui"}
UA = {"User-Agent": "Mozilla/5.0 (compatible; crispy-bot/1.0)"}
MAX_PER_MESSAGE = 2
_cache = {}


def _sol_like(s):   # a real key mixes digits, capitals and lower case; plain words and IDs rarely do
    return any(c.isdigit() for c in s) and any(c.isupper() for c in s) and any(c.islower() for c in s)


def addresses(text):
    text = text or ""
    found = []
    plain = URL.sub(" ", text)
    for u in URL.findall(text):
        if any(site in u.lower() for site in TOKEN_SITES): plain += " " + u.replace("/", " ").replace("?", " ").replace("=", " ")
    for m in EVM.finditer(plain): found.append(m.group(0))
    plain = EVM.sub(" ", plain)   # so the tail of an 0x address isn't read as a Solana one
    for m in SOL.finditer(plain):
        s = m.group(0)
        if _sol_like(s) and not s.startswith("0x"): found.append(s)
    return list(dict.fromkeys(found))[:MAX_PER_MESSAGE]


async def lookup(session, addr):
    hit = _cache.get(addr.lower())
    if hit and time.monotonic() - hit[0] < 60: return hit[1]
    async with session.get(f"https://api.dexscreener.com/latest/dex/tokens/{addr}", headers=UA,
                           timeout=aiohttp.ClientTimeout(total=10)) as r:
        pairs = (await r.json()).get("pairs") or [] if r.status == 200 else []
    same = lambda a: a.lower() == addr.lower() if addr.startswith("0x") else a == addr
    liq = lambda p: (p.get("liquidity") or {}).get("usd") or 0
    as_base = [p for p in pairs if same((p.get("baseToken") or {}).get("address", ""))]
    out = None
    if as_base:
        p = await _main_pair(session, addr, as_base, same)
        out = {"pair": p, "token": p["baseToken"], "price": _f(p.get("priceUsd")), "change": p.get("priceChange") or {}}
    else:   # only ever the other side of a trade (stablecoins, wrapped coins): its price from the pair
        as_quote = [p for p in pairs if same((p.get("quoteToken") or {}).get("address", ""))]
        if as_quote:
            p = max(as_quote, key=liq)
            pu, pn = _f(p.get("priceUsd")), _f(p.get("priceNative"))
            out = {"pair": p, "token": p["quoteToken"], "price": (pu / pn) if pu and pn else None, "change": {}}
    _cache[addr.lower()] = (time.monotonic(), out)
    return out


# Real money to trade against. Spam pairs quote a token against a worthless one of their own and fake huge
# liquidity, so "most liquidity" alone picks them (2026-11-19: a DCTY/MM pair claiming $15M liquidity, $132B cap).
MAJORS = {"SOL", "WSOL", "USDC", "USDT", "ETH", "WETH", "BNB", "WBNB", "USDC.E", "USDT.E", "DAI", "USD1", "PYUSD", "AVAX",
          "WAVAX", "POL", "WPOL", "MATIC", "WMATIC", "CBBTC", "WBTC", "SUI"}


async def _main_pair(session, addr, as_base, same):
    """The pair DexScreener itself shows for the token (its per-chain endpoint lists that first), if it has a price and
    liquidity; otherwise the busiest priced pair against a major currency, ignoring pairs whose market cap is way off."""
    # an EVM address can exist on several chains (forks copy them): use the chain where it actually trades most
    vol = {}
    for p in as_base: vol[p.get("chainId")] = vol.get(p.get("chainId"), 0) + ((p.get("volume") or {}).get("h24") or 0)
    chain = max(vol, key=vol.get)
    as_base = [p for p in as_base if p.get("chainId") == chain]
    try:
        async with session.get(f"https://api.dexscreener.com/tokens/v1/{chain}/{addr}", headers=UA,
                               timeout=aiohttp.ClientTimeout(total=10)) as r:
            main = await r.json() if r.status == 200 else []
        main = [p for p in main if isinstance(p, dict) and same((p.get("baseToken") or {}).get("address", ""))]
        # only if it really trades: a fresh pump.fun coin's "main" pair can be an empty one with no price or liquidity
        if main and _f(main[0].get("priceUsd")) and ((main[0].get("liquidity") or {}).get("usd") or 0) > 0: return main[0]
    except Exception as e:
        print(f"[dex] main pair for {addr}: {type(e).__name__}: {e}")
    live = [p for p in as_base if _f(p.get("priceUsd"))] or as_base   # pairs with a price at all
    good = [p for p in live if ((p.get("quoteToken") or {}).get("symbol") or "").upper() in MAJORS] or live
    caps = sorted(c for c in ((p.get("marketCap") or p.get("fdv")) for p in good) if c)
    if len(caps) >= 3:
        med = caps[len(caps) // 2]
        good = [p for p in good if not (p.get("marketCap") or p.get("fdv")) or (p.get("marketCap") or p.get("fdv")) <= med * 5] or good
    return max(good, key=lambda p: (((p.get("volume") or {}).get("h24") or 0), (p.get("liquidity") or {}).get("usd") or 0))


def _f(x):
    try: return float(x)
    except (TypeError, ValueError): return None


def usd(x, small=False):
    if x is None: return "?"
    if x >= 1e9: return f"${x / 1e9:,.2f}B"
    if x >= 1e6: return f"${x / 1e6:,.2f}M"
    if x >= 1e3 and not small: return f"${x / 1e3:,.1f}K"
    if x >= 1: return f"${x:,.2f}"
    if x == 0: return "$0"
    import math
    d = max(2, -int(math.floor(math.log10(abs(x)))) + 2)
    return f"${x:.{d}f}"


def age(ms):
    if not ms: return "?"
    h = (time.time() * 1000 - ms) / 3_600_000
    return f"{h * 60:.0f} min" if h < 1 else f"{h:.0f} h" if h < 48 else f"{h / 24:.0f} days" if h < 24 * 60 else f"{h / 24 / 30:.0f} months"


def card(addr, got):
    """Embed fields, free of discord imports so it can be tested alone."""
    p, tok = got["pair"], got["token"]
    ch = got["change"]
    h24, h1 = ch.get("h24"), ch.get("h1")
    up = (h24 or 0) >= 0
    chain = CHAINS.get(p.get("chainId"), (p.get("chainId") or "?").title())
    desc = f"**{usd(got['price'], small=True)}**"
    if h24 is not None: desc += f"  {'▲' if up else '▼'} {h24:+.2f}% 24h"
    if h1 is not None: desc += f"  ·  {h1:+.2f}% 1h"
    liquidity = (p.get("liquidity") or {}).get("usd")
    created = p.get("pairCreatedAt")
    young = created and (time.time() * 1000 - created) < 24 * 3_600_000
    if (liquidity is not None and liquidity < 10_000) or young:
        desc += "\n⚠️ " + ("Very low liquidity" if liquidity is not None and liquidity < 10_000 else "Brand-new pair") \
                + ": an unverified token can be a scam or rug pull. Do your own research."
    mcap = p.get("marketCap") or p.get("fdv")
    fields = [("Liquidity", usd(liquidity)), ("24h volume", usd((p.get("volume") or {}).get("h24"))),
              ("Market cap" if p.get("marketCap") else "FDV", usd(mcap)), ("Pair age", age(created)),
              ("Traded on", f"{(p.get('dexId') or '?').title()} · {chain}")]
    short = addr if len(addr) <= 14 else f"{addr[:6]}…{addr[-4:]}"
    return {"title": f"{tok.get('name', '?')} ({tok.get('symbol', '?')}) · {chain}"[:250], "url": p.get("url"),
            "description": desc, "color": 0x23A55A if up else 0xDA373C, "fields": fields,
            "footer": f"{short} · DexScreener · not financial advice", "image": (p.get("info") or {}).get("imageUrl")}


async def reply_cards(message, discord):
    addrs = addresses(message.content)
    if not addrs: return
    async with aiohttp.ClientSession() as session:
        for a in addrs:
            try:
                got = await lookup(session, a)
            except Exception as e:
                print(f"[dex] {a[:10]}: {e}"); continue
            if not got: continue   # looked like an address, isn't a token: stay quiet
            d = card(a, got)
            em = discord.Embed(title=d["title"], url=d["url"], description=d["description"], color=d["color"])
            for n, v in d["fields"]: em.add_field(name=n, value=v, inline=True)
            if d["image"]: em.set_thumbnail(url=d["image"])
            em.set_footer(text=d["footer"])
            chain = got["pair"].get("chainId") or "?"
            scans.decorate(em, message, f"d:{chain}:{a if not a.startswith('0x') else a.lower()}", got["price"],
                           lambda x: usd(x, small=True))
            await message.reply(embed=em, mention_author=False)

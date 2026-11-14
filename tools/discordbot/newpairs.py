"""New coins by topic for the Crispy Discord bot: /newpairs <topic>.

When something happens, new coins named after it appear within minutes. This keeps a rolling 24 h list of every
newly launched coin and searches it by name and symbol:

- pump.fun launches, live, from PumpPortal's public data feed (wss://pumpportal.fun/api/data, subscribeNewToken; free,
  no key). Pump.fun's own site API is behind bot protection and isn't used.
- New trading pools on Solana, Base and Ethereum DEXes, from GeckoTerminal's public new_pools list, polled every minute.

/newpairs shows the newest matches with their current market cap and liquidity (DexScreener, one batched call), age
and a chart link. The list is saved to newpairs.json every few minutes, so a bot restart doesn't empty it.
Information only, not advice: nearly every brand-new coin is a gamble and many are scams, so every reply says so.
"""
import asyncio, json, os, re, time
from collections import deque
import aiohttp

HERE = os.path.dirname(os.path.abspath(__file__))
SAVE = os.path.join(HERE, "newpairs.json")
KEEP_S = 24 * 3600
UA = {"User-Agent": "Mozilla/5.0 (compatible; crispy-bot/1.0)"}
GT_NETWORKS = {"solana": 2, "base": 1, "eth": 1}   # network -> pages of 20 per poll
GT_TO_DS = {"solana": "solana", "base": "base", "eth": "ethereum"}
CHAIN_NAME = {"solana": "Solana", "base": "Base", "ethereum": "Ethereum"}
SHOW = 10

COINS = deque()   # dicts: t (unix s), chain, addr, name, sym, src, mcap (launch, USD or None), sol (launch mcap in SOL)
_seen = set()
stats = {"pump": 0, "gt": 0, "pump_up": False}


def _norm(s): return re.sub(r"[^a-z0-9]", "", (s or "").lower())


def add(c):
    key = (c["chain"], c["addr"])
    if key in _seen or not c["addr"]: return
    _seen.add(key); COINS.append(c)


def prune():
    cut = time.time() - KEEP_S
    while COINS and COINS[0]["t"] < cut:
        old = COINS.popleft(); _seen.discard((old["chain"], old["addr"]))


def search(topic, coins=None):
    """Coins whose name+symbol contain every word of the topic (ignoring spaces and punctuation), newest first."""
    words = [_norm(w) for w in topic.split()]
    words = [w for w in words if w]
    if not words or max(len(w) for w in words) < 3: return None   # too vague to search
    out = []
    for c in reversed(coins if coins is not None else COINS):
        hay = _norm(c["name"]) + " " + _norm(c["sym"])
        if all(w in hay for w in words): out.append(c)
    return out


# ---- feeds
async def pump_feed():
    import websockets
    delay = 5
    while True:
        try:
            async with websockets.connect("wss://pumpportal.fun/api/data", open_timeout=20, ping_interval=30) as ws:
                await ws.send(json.dumps({"method": "subscribeNewToken"}))
                stats["pump_up"] = True; delay = 5
                async for raw in ws:
                    try: m = json.loads(raw)
                    except ValueError: continue
                    if "mint" not in m: continue
                    add({"t": time.time(), "chain": "solana", "addr": m["mint"], "name": (m.get("name") or "")[:60],
                         "sym": (m.get("symbol") or "")[:20], "src": "pump.fun", "mcap": None, "sol": m.get("marketCapSol")})
                    stats["pump"] += 1
        except Exception as e:
            print(f"[newpairs] pump.fun feed: {type(e).__name__}: {e}")
        stats["pump_up"] = False
        await asyncio.sleep(delay); delay = min(delay * 2, 300)


def _ts(s):
    try:
        import datetime
        return datetime.datetime.fromisoformat(s.replace("Z", "+00:00")).timestamp()
    except Exception: return time.time()


async def gt_poll(session):
    for net, pages in GT_NETWORKS.items():
        for page in range(1, pages + 1):
            url = f"https://api.geckoterminal.com/api/v2/networks/{net}/new_pools?include=base_token,dex&page={page}"
            async with session.get(url, headers={**UA, "Accept": "application/json"}, timeout=aiohttp.ClientTimeout(total=15)) as r:
                if r.status == 429: await asyncio.sleep(30); break   # over the free limit: skip this round
                if r.status != 200: print(f"[newpairs] geckoterminal {net}: HTTP {r.status}"); break
                d = await r.json()
            toks = {i["id"]: i["attributes"] for i in d.get("included", []) if i.get("type") == "token"}
            dexes = {i["id"]: i["attributes"].get("name") for i in d.get("included", []) if i.get("type") == "dex"}
            for p in d.get("data", []):
                a, rel = p.get("attributes", {}), p.get("relationships", {})
                tok = toks.get(((rel.get("base_token") or {}).get("data") or {}).get("id"), {})
                dex = dexes.get(((rel.get("dex") or {}).get("data") or {}).get("id")) or "DEX"
                if dex.lower() == "pump.fun": dex = "pump.fun"
                if not tok.get("address"): continue
                mcap = a.get("market_cap_usd") or a.get("fdv_usd")
                add({"t": _ts(a.get("pool_created_at") or ""), "chain": GT_TO_DS[net], "addr": tok["address"],
                     "name": (tok.get("name") or "")[:60], "sym": (tok.get("symbol") or "")[:20], "src": dex,
                     "mcap": float(mcap) if mcap else None, "sol": None})
                stats["gt"] += 1
            await asyncio.sleep(8)   # GeckoTerminal's free limit is low and shared: keep calls well apart


async def poll_loop():
    load()
    n = 0
    async with aiohttp.ClientSession() as session:
        while True:
            try: await gt_poll(session)
            except Exception as e: print(f"[newpairs] geckoterminal: {type(e).__name__}: {e}")
            prune()
            n += 1
            if n % 5 == 0: save()
            await asyncio.sleep(45)


def load():
    try:
        with open(SAVE) as f: data = json.load(f)
        cut = time.time() - KEEP_S
        for c in sorted(data, key=lambda c: c["t"]):
            if c["t"] >= cut: add(c)
    except FileNotFoundError: pass
    except Exception as e: print(f"[newpairs] can't load {SAVE}: {e}")


def save():
    try:
        tmp = SAVE + ".tmp"
        with open(tmp, "w") as f: json.dump(list(COINS), f, separators=(",", ":"))
        os.replace(tmp, SAVE)
    except Exception as e: print(f"[newpairs] can't save: {e}")


# ---- live numbers for the coins shown
async def market(session, coins):
    """(chain, addr) -> {mcap, liq, url, vol} from DexScreener, batched per chain (30 addresses a call)."""
    out = {}
    by_chain = {}
    for c in coins: by_chain.setdefault(c["chain"], []).append(c["addr"])
    for chain, addrs in by_chain.items():
        for i in range(0, len(addrs), 30):
            url = f"https://api.dexscreener.com/tokens/v1/{chain}/{','.join(addrs[i:i + 30])}"
            try:
                async with session.get(url, headers=UA, timeout=aiohttp.ClientTimeout(total=10)) as r:
                    pairs = await r.json() if r.status == 200 else []
            except Exception as e:
                print(f"[newpairs] dexscreener: {e}"); continue
            for p in pairs or []:
                addr = (p.get("baseToken") or {}).get("address")
                if not addr: continue
                liq = (p.get("liquidity") or {}).get("usd") or 0
                key = (chain, addr)
                if key in out and out[key]["liq"] >= liq: continue
                out[key] = {"mcap": p.get("marketCap") or p.get("fdv"), "liq": liq, "url": p.get("url"),
                            "vol": (p.get("volume") or {}).get("h24")}
    return out


def _usd(x):
    if x is None: return "?"
    return f"${x / 1e6:,.2f}M" if x >= 1e6 else f"${x / 1e3:,.1f}K" if x >= 1e3 else f"${x:,.0f}"


def _age(t):
    m = (time.time() - t) / 60
    return f"{m:.0f} min ago" if m < 60 else f"{m / 60:.0f} h ago"


def lines(found, live):
    out = []
    for c in found:
        m = live.get((c["chain"], c["addr"]), {})
        url = m.get("url") or (f"https://pump.fun/coin/{c['addr']}" if c["src"] == "pump.fun" else
                               f"https://dexscreener.com/{c['chain']}/{c['addr']}")
        if m.get("mcap"): val = f"{_usd(m['mcap'])} mcap"
        elif c.get("mcap"): val = f"{_usd(c['mcap'])} mcap at launch"
        elif c.get("sol"): val = f"{c['sol']:,.0f} SOL mcap at launch"
        else: val = "no trades yet"
        if m.get("liq"): val += f" · {_usd(m['liq'])} liq"
        name = re.sub(r"[\[\]*_`~|<>@]", "", c["name"]) or "?"
        sym = re.sub(r"[\[\]*_`~|<>@$]", "", c["sym"]) or "?"
        out.append(f"[**{name[:40]}** (${sym[:12]})]({url}) · {c['src']} · {CHAIN_NAME.get(c['chain'], c['chain'])}\n"
                   f"-# {_age(c['t'])} · {val} · `{c['addr'][:5]}…{c['addr'][-4:]}`")
    return out


def register(bot, discord, app_commands):
    orig = bot.setup_hook

    async def hook():
        await orig()
        asyncio.create_task(pump_feed())
        asyncio.create_task(poll_loop())
    bot.setup_hook = hook

    @bot.tree.command(name="newpairs", description="Find coins launched in the last 24 h whose name matches a topic")
    @app_commands.describe(topic="Words to look for in the coin's name or symbol, e.g. 'moon landing' or 'pepe'")
    async def newpairs_cmd(interaction: discord.Interaction, topic: str):
        topic = topic[:60]
        found = search(topic)
        if found is None:
            return await interaction.response.send_message("Give at least one word of 3+ letters to search for.", ephemeral=True)
        await interaction.response.defer()
        span = (time.time() - COINS[0]["t"]) / 3600 if COINS else 0
        covered = "the last 24 h" if span >= 23 else f"the last {max(span, 0.1):.1f} h (the list is still filling up)"
        if not found:
            return await interaction.followup.send(f"No new coins named like \"{topic}\" in {covered}. "
                                                   f"({len(COINS):,} launches checked.)")
        shown = found[:SHOW]
        async with aiohttp.ClientSession() as session:
            live = await market(session, shown)
        em = discord.Embed(title=f"New coins matching \"{topic}\"",
                           description="\n".join(lines(shown, live))[:4000], color=0xF2A93B)
        more = f" · showing the newest {SHOW}" if len(found) > SHOW else ""
        em.add_field(name="⚠️ Read this", inline=False,
                     value="Brand-new coins are extremely risky: most go to zero and many are scams or rug pulls. "
                           "A matching name doesn't mean it's connected to the event. Not financial advice.")
        em.set_footer(text=f"{len(found)} match{'es' if len(found) != 1 else ''} in {covered}{more} · "
                           f"pump.fun via PumpPortal · DEX pools via GeckoTerminal · prices DexScreener")
        await interaction.followup.send(embed=em)

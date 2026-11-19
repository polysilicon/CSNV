"""Price alerts for things scanned in Discord: when a stock, coin or token someone scanned moves a lot, Yoink says so.

Watched: every $TICKER or contract-address card posted in a channel (scans.decorate calls track()), for WATCH_DAYS
after its latest scan (each new scan starts the clock again and makes that channel the one alerts go to). Every
CHECK_MINUTES the price is looked up again (tickers.lookup / dex.lookup, the same as the cards).

Alert when the price has moved, up or down, by at least:
- BIG (5%) for stocks, the best-known coins (Yahoo's), and currencies;
- SMALL (20%) for smaller coins: CoinGecko coins under SMALL_CAP market cap, and contract-address tokens (DexScreener)
  under SMALL_CAP or with no market cap known.
The move is measured from the price when it was scanned, or at its last alert, so each alert needs a fresh move of the
same size. At most one alert per thing per COOLDOWN. The card says the move, from what to what, since when, and how
it's done since its first scan in the server (scans.json). Polymarket cards aren't watched.

Staff: /pricealerts on|off (per server, on by default) and /pricealerts list. State: pricealerts.json.
Information only, not financial advice.
"""
import asyncio, json, os, time
import aiohttp
import scans, tickers, dex

HERE = os.path.dirname(os.path.abspath(__file__))
FILE = os.path.join(HERE, "pricealerts.json")
BIG, SMALL, SMALL_CAP = 5.0, 20.0, 1_000_000_000
WATCH_DAYS, CHECK_MINUTES, COOLDOWN = 14, 15, 3600
_data = None


def _load():
    global _data
    if _data is None:
        try:
            with open(FILE) as f: _data = json.load(f)
        except (OSError, ValueError): _data = {}
        _data.setdefault("watch", {}); _data.setdefault("off", [])
    return _data


def _save():
    try:
        tmp = FILE + ".tmp"
        with open(tmp, "w") as f: json.dump(_data, f, separators=(",", ":"))
        os.replace(tmp, FILE)
    except Exception as e: print(f"[pricealerts] can't save: {e}")


def track(guild_id, key, channel_id, price):
    """Called for every card posted in a channel: start or refresh watching `key` there."""
    if not key.startswith(("t:", "d:")) or price is None or not channel_id: return
    d = _load()
    k = f"{guild_id}:{key}"
    w = d["watch"].get(k)
    now = int(time.time())
    if w is None:
        d["watch"][k] = {"channel": channel_id, "base": price, "base_t": now, "scanned": now, "last_alert": 0}
    else:
        w["channel"] = channel_id; w["scanned"] = now
    _save()


def _symbol(key):
    """The symbol to look up again from a scans key ('t:NVDA', 't:SOL-USD', 't:EURUSD=X')."""
    s = key[2:]
    if s.endswith("USD=X"): return s[:3]
    if s.endswith("-USD"): return s[:-4]
    return s


async def _price(session, key):
    """(price, threshold %, label, link) now, or None."""
    if key.startswith("t:"):
        got = await tickers.lookup(session, _symbol(key))
        if not got: return None
        sym, meta, _ = got
        price = meta.get("regularMarketPrice")
        if price is None: return None
        fx = sym.endswith("USD=X")
        small = meta.get("source") == "CoinGecko" and (meta.get("marketCap") or 0) < SMALL_CAP
        show = sym[:3] if fx else sym.replace("-USD", "")
        name = tickers.CURRENCY_NAMES.get(show, show) if fx else (meta.get("longName") or meta.get("shortName") or show)
        url = f"https://www.coingecko.com/en/coins/{meta['geckoId']}" if meta.get("geckoId") else f"https://finance.yahoo.com/quote/{sym}"
        fmt = (lambda x: f"${tickers.fmt_rate(x)}") if fx else (lambda x: tickers.fmt(x, meta.get("currency") or "USD"))
        return price, (SMALL if small else BIG), f"${show} · {name}"[:120], url, fmt
    _, chain, addr = key.split(":", 2)
    got = await dex.lookup(session, addr)
    if not got or not got.get("price"): return None
    p = got["pair"]
    mcap = p.get("marketCap") or p.get("fdv")
    tok = got["token"]
    return got["price"], (SMALL if not mcap or mcap < SMALL_CAP else BIG), f"{tok.get('name', '?')} ({tok.get('symbol', '?')})"[:120], \
        p.get("url"), lambda x: dex.usd(x, small=True)


async def check(bot, discord):
    d = _load()
    now = int(time.time())
    expired = [k for k, w in d["watch"].items() if now - w.get("scanned", 0) > WATCH_DAYS * 86400]
    for k in expired: d["watch"].pop(k, None)
    if expired: _save()
    async with aiohttp.ClientSession() as session:
        for k, w in list(d["watch"].items()):
            guild_id, key = k.split(":", 1)
            if guild_id in d["off"] or now - w.get("last_alert", 0) < COOLDOWN: continue
            try:
                got = await _price(session, key)
            except Exception as e:
                print(f"[pricealerts] {key}: {type(e).__name__}: {e}"); continue
            if not got: continue
            price, threshold, label, url, fmt = got
            base = w.get("base")
            if not base: w["base"] = price; continue
            pct = (price - base) / base * 100
            if abs(pct) < threshold: continue
            ch = bot.get_channel(int(w["channel"]))
            if ch is None: continue
            up = pct > 0
            em = discord.Embed(color=0x23A55A if up else 0xDA373C, url=url,
                               title=f"{'📈' if up else '📉'} {label} is {'up' if up else 'down'} {abs(pct):.1f}%",
                               description=f"{fmt(base)} → **{fmt(price)}** since <t:{w['base_t']}:R>"
                                           f"{' (its last alert)' if w.get('last_alert') else ' (when it was scanned here)'}")
            first = scans._load().get(k)
            if first and first.get("price"):
                em.add_field(name="Since first scan", value=scans.since(first, price, fmt), inline=False)
            em.set_footer(text=f"Alerts at ±{threshold:.0f}% · {'smaller coin' if threshold == SMALL else 'stock or major coin'} · "
                               f"watched for {WATCH_DAYS} days after a scan · not financial advice")
            try:
                await ch.send(embed=em, allowed_mentions=discord.AllowedMentions.none())
            except Exception as e:
                print(f"[pricealerts] send {key}: {e}"); continue
            w.update({"base": price, "base_t": now, "last_alert": now})
            _save()
            await asyncio.sleep(1)


async def loop(bot, discord):
    await bot.wait_until_ready()
    await asyncio.sleep(60)
    while True:
        try: await check(bot, discord)
        except Exception as e: print(f"[pricealerts] {type(e).__name__}: {e}")
        await asyncio.sleep(CHECK_MINUTES * 60)


def register(bot, discord, app_commands):
    orig = bot.setup_hook

    async def hook():
        await orig()
        asyncio.create_task(loop(bot, discord))
    bot.setup_hook = hook

    @bot.tree.command(name="pricealerts", description="Staff: price alerts for scanned stocks and coins (on, off, list)")
    @app_commands.default_permissions(manage_guild=True)
    @app_commands.choices(action=[app_commands.Choice(name=n, value=n) for n in ("list", "on", "off")])
    async def pricealerts_cmd(interaction: discord.Interaction, action: app_commands.Choice[str]):
        if not bot.is_staff(interaction.user):
            return await interaction.response.send_message("Staff only.", ephemeral=True)
        d = _load(); g = str(interaction.guild_id)
        if action.value == "on":
            if g in d["off"]: d["off"].remove(g); _save()
            return await interaction.response.send_message("Price alerts are **on** in this server.", ephemeral=True)
        if action.value == "off":
            if g not in d["off"]: d["off"].append(g); _save()
            return await interaction.response.send_message("Price alerts are **off** in this server.", ephemeral=True)
        rows = [(k.split(":", 1)[1], w) for k, w in d["watch"].items() if k.startswith(g + ":")]
        text = "\n".join(f"`{key[2:][:40]}` in <#{w['channel']}> · scanned <t:{w['scanned']}:R>" for key, w in rows) or "Nothing is being watched."
        await interaction.response.send_message(
            f"Price alerts are **{'off' if g in d['off'] else 'on'}**: ±{BIG:.0f}% for stocks and major coins, ±{SMALL:.0f}% for smaller coins "
            f"(under ${SMALL_CAP / 1e9:.0f}B), for {WATCH_DAYS} days after each scan.\n{text}"[:1990], ephemeral=True)

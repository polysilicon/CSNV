"""Paper trading for the Crispy Discord: trade memecoins (and stocks or coins) with fake money at live prices.

Everyone starts with START_USD of paper money. /paper buy <token> <usd> and /paper sell <token> [percent] trade at
the live price: a Solana or 0x contract address (DexScreener, the same main pair as the dex cards) or a $TICKER
(tickers.py). Fills are realistic, not ideal: a FEE on every trade, plus price impact on DEX tokens that grows with the
trade's size against the pool's liquidity (capped at MAX_IMPACT), so buying into a $5K pool costs you. /paper portfolio
shows holdings, value and profit; /paper leaderboard ranks everyone by total value; /paper reset starts over (once a
day). Nothing here is real money or advice. Data: papertrade.json.
"""
import json, os, time
import aiohttp
import dex, tickers

HERE = os.path.dirname(os.path.abspath(__file__))
FILE = os.path.join(HERE, "papertrade.json")
START_USD, FEE, MAX_IMPACT, MAX_POSITIONS, RESET_EVERY = 10_000.0, 0.01, 0.20, 25, 86400
_data = None


def _load():
    global _data
    if _data is None:
        try:
            with open(FILE) as f: _data = json.load(f)
        except (OSError, ValueError): _data = {}
    return _data


def _save():
    tmp = FILE + ".tmp"
    with open(tmp, "w") as f: json.dump(_data, f, separators=(",", ":"))
    os.replace(tmp, FILE)


def account(uid, name):
    d = _load()
    a = d.setdefault(str(uid), {"cash": START_USD, "pos": {}, "trades": 0, "started": int(time.time()), "reset_at": 0})
    a["name"] = name[:40]
    return a


async def quote(session, token):
    """(key, label, price, liquidity or None, url) for a contract address or $TICKER, or None."""
    t = token.strip()
    addrs = dex.addresses(t)
    if addrs:
        got = await dex.lookup(session, addrs[0])
        if not got or not got.get("price"): return None
        p, tok = got["pair"], got["token"]
        a = addrs[0] if not addrs[0].startswith("0x") else addrs[0].lower()
        return f"d:{p.get('chainId')}:{a}", f"{tok.get('symbol', '?')}", got["price"], (p.get("liquidity") or {}).get("usd"), p.get("url")
    sym = t.lstrip("$").upper()
    if not sym.isalnum() or len(sym) > 10: return None
    got = await tickers.lookup(session, sym)
    if not got: return None
    s, meta, _ = got
    price = meta.get("regularMarketPrice")
    if not price: return None
    return f"t:{s}", "$" + s.replace("-USD", ""), price, None, f"https://finance.yahoo.com/quote/{s}"


def impact(usd, liq):
    """Extra cost of a trade's size on a pool (a simple constant-product estimate), as a fraction."""
    if not liq: return 0.0
    return min(MAX_IMPACT, usd / max(liq, 1.0))


def fmt(x):
    return dex.usd(x, small=True) if x < 1 else f"${x:,.2f}"


async def value(session, a):
    """(total value, [(key, pos, price or None, value)])."""
    rows, total = [], a["cash"]
    for k, pos in a["pos"].items():
        price = None
        try:
            q = await quote(session, pos["q"])
            price = q[2] if q else None
        except Exception:
            pass
        v = pos["qty"] * price if price else pos["cost"]
        total += v
        rows.append((k, pos, price, v))
    return total, rows


def register(bot, discord, app_commands):
    group = app_commands.Group(name="paper", description="Paper trading: memecoins and stocks with fake money at live prices")

    async def reply(inter, text, ephemeral=False):
        if inter.response.is_done(): await inter.followup.send(text, ephemeral=ephemeral)
        else: await inter.response.send_message(text, ephemeral=ephemeral)

    @group.command(name="buy", description="Buy with paper money at the live price")
    @app_commands.describe(token="Contract address (Solana or 0x) or a $TICKER", usd="How many paper dollars to spend")
    async def buy(inter: discord.Interaction, token: str, usd: app_commands.Range[float, 1, 1_000_000]):
        await inter.response.defer()
        a = account(inter.user.id, inter.user.display_name)
        if usd > a["cash"]: return await reply(inter, f"You only have **{fmt(a['cash'])}** in paper cash.")
        async with aiohttp.ClientSession() as s:
            q = await quote(s, token)
        if not q: return await reply(inter, "I couldn't find a live price for that. Paste a contract address or a $TICKER.")
        key, label, price, liq, url = q
        if key not in a["pos"] and len(a["pos"]) >= MAX_POSITIONS: return await reply(inter, f"You can hold at most {MAX_POSITIONS} positions. Sell something first.")
        imp = impact(usd, liq)
        fill = price * (1 + imp)
        qty = usd * (1 - FEE) / fill
        pos = a["pos"].setdefault(key, {"q": token.strip(), "label": label, "qty": 0.0, "cost": 0.0, "t": int(time.time())})
        pos["qty"] += qty; pos["cost"] += usd
        a["cash"] -= usd; a["trades"] += 1
        _save()
        warn = f"\n⚠️ Thin pool: your size moved the price {imp * 100:.1f}%." if imp >= 0.02 else ""
        await reply(inter, f"🟢 **{inter.user.display_name}** bought **{label}** with {fmt(usd)} of paper money at {fmt(fill)} "
                           f"(1% fee{f', {imp * 100:.1f}% price impact' if imp >= 0.001 else ''}). [chart](<{url}>)\n"
                           f"Cash left: {fmt(a['cash'])}{warn}\n-# Paper trading: fake money, live prices, not advice.")

    @group.command(name="sell", description="Sell a holding (all of it, or a percent) at the live price")
    @app_commands.describe(token="The contract address or $TICKER you bought", percent="How much to sell (default 100)")
    async def sell(inter: discord.Interaction, token: str, percent: app_commands.Range[float, 1, 100] = 100.0):
        await inter.response.defer()
        a = account(inter.user.id, inter.user.display_name)
        async with aiohttp.ClientSession() as s:
            q = await quote(s, token)
        if not q: return await reply(inter, "I couldn't find a live price for that right now.")
        key, label, price, liq, url = q
        pos = a["pos"].get(key)
        if not pos: return await reply(inter, f"You don't hold **{label}**. `/paper portfolio` shows what you have.")
        part = percent / 100
        qty = pos["qty"] * part
        gross = qty * price
        imp = impact(gross, liq)
        got = gross * (1 - imp) * (1 - FEE)
        cost = pos["cost"] * part
        pnl = got - cost
        pos["qty"] -= qty; pos["cost"] -= cost
        if part >= 0.999 or pos["qty"] <= 0: a["pos"].pop(key)
        a["cash"] += got; a["trades"] += 1
        _save()
        await reply(inter, f"{'🟢' if pnl >= 0 else '🔴'} **{inter.user.display_name}** sold {percent:.0f}% of **{label}** for {fmt(got)}: "
                           f"**{'+' if pnl >= 0 else '-'}{fmt(abs(pnl))}** ({pnl / cost * 100:+.1f}%) [chart](<{url}>)\n"
                           f"Cash: {fmt(a['cash'])}\n-# Paper trading: fake money, live prices, not advice.")

    @group.command(name="portfolio", description="Your paper holdings, value and profit (or someone else's)")
    async def portfolio(inter: discord.Interaction, member: discord.Member = None):
        await inter.response.defer()
        who = member or inter.user
        a = _load().get(str(who.id))
        if not a: return await reply(inter, f"{who.display_name} hasn't paper traded yet. Start with `/paper buy`.")
        async with aiohttp.ClientSession() as s:
            total, rows = await value(s, a)
        lines = []
        for k, pos, price, v in sorted(rows, key=lambda r: -r[3]):
            pnl = v - pos["cost"]
            lines.append(f"**{pos['label']}** {fmt(v)} · {'+' if pnl >= 0 else '-'}{fmt(abs(pnl))} ({(pnl / pos['cost'] * 100) if pos['cost'] else 0:+.1f}%)"
                         + ("" if price else " · *no price now*"))
        em = discord.Embed(color=0x23A55A if total >= START_USD else 0xDA373C, title=f"📊 {who.display_name}'s paper portfolio",
                           description="\n".join(lines) or "No holdings.")
        em.add_field(name="Cash", value=fmt(a["cash"]))
        em.add_field(name="Total value", value=f"{fmt(total)} ({(total - START_USD) / START_USD * 100:+.1f}%)")
        em.add_field(name="Trades", value=str(a["trades"]))
        em.set_footer(text=f"Started with {fmt(START_USD)} of paper money · fake money, live prices, not advice")
        await inter.followup.send(embed=em)

    @group.command(name="leaderboard", description="Who's up the most with paper money")
    async def leaderboard(inter: discord.Interaction):
        await inter.response.defer()
        d = _load()
        rows = []
        async with aiohttp.ClientSession() as s:
            for uid, a in list(d.items())[:50]:
                total, _ = await value(s, a)
                rows.append((total, a.get("name", "?")))
        rows.sort(reverse=True)
        text = "\n".join(f"`{i + 1}.` **{discord.utils.escape_markdown(n)}** {fmt(t)} ({(t - START_USD) / START_USD * 100:+.1f}%)" for i, (t, n) in enumerate(rows[:10]))
        em = discord.Embed(color=0xF1C40F, title="🏆 Paper trading leaderboard", description=text or "Nobody yet. `/paper buy` to start.")
        em.set_footer(text=f"Everyone starts with {fmt(START_USD)} · fake money, live prices, not advice")
        await inter.followup.send(embed=em)

    @group.command(name="reset", description="Start over with fresh paper money (once a day)")
    async def reset(inter: discord.Interaction):
        a = account(inter.user.id, inter.user.display_name)
        if time.time() - a.get("reset_at", 0) < RESET_EVERY:
            return await reply(inter, "You can reset once a day.", ephemeral=True)
        a.update({"cash": START_USD, "pos": {}, "trades": 0, "started": int(time.time()), "reset_at": int(time.time())})
        _save()
        await reply(inter, f"🔄 **{inter.user.display_name}** reset their paper account to {fmt(START_USD)}.")

    bot.tree.add_command(group)

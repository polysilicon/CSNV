"""Crispy Trader's reports in Discord (the trader itself is a separate service: tools/trader, /opt/crispytrader).

Yoink only reads the trader's files (events.jsonl, state.json, config.json); it never sees the wallet key. Every buy,
sell and error is sent as a DM to the owner: the Discord account linked to OWNER_MC in links.json (or OWNER_ID).
/trader (staff) shows the mode, open positions, today's and total profit in SOL, and the win rate.
"""
import asyncio, json, os, time

DIR = "/opt/crispytrader/"
OWNER_MC = "lbxd"
OWNER_ID = 455945793371897877   # GBC, the server owner (their Minecraft account lbxd is not linked)


def _read(name, default):
    try:
        with open(DIR + name) as f: return json.load(f)
    except (OSError, ValueError): return default


async def loop(bot, discord):
    await bot.wait_until_ready()
    path = DIR + "events.jsonl"
    pos = os.path.getsize(path) if os.path.exists(path) else 0   # only new events from here on
    while True:
        await asyncio.sleep(10)
        try:
            if not os.path.exists(path): continue
            size = os.path.getsize(path)
            if size < pos: pos = 0
            if size == pos: continue
            with open(path) as f:
                f.seek(pos); lines = f.readlines(); pos = f.tell()
            uid = OWNER_ID or next((int(u) for u, mc in bot.links.items() if mc.lower() == OWNER_MC), None)
            if not uid: continue
            user = bot.get_user(uid) or await bot.fetch_user(uid)
            for l in lines:
                try: e = json.loads(l)
                except ValueError: continue
                await user.send(embed=card(discord, e))
                await asyncio.sleep(0.5)
        except Exception as ex:
            print(f"[traderfeed] {type(ex).__name__}: {ex}")


def card(discord, e):
    tag = "🧪 PAPER" if e.get("mode") != "live" else "💸 LIVE"
    name = f"{e.get('name', '?')} (${e.get('sym', '?')})"
    if e["kind"] == "buy":
        m = e.get("metrics") or {}
        em = discord.Embed(color=0x5865F2, title=f"{tag} · Bought {name}", url=e.get("url"),
                           description=f"**{e['sol']} SOL** in · mcap ${m.get('mcap', 0):,} · liquidity ${m.get('liq', 0):,}\n"
                                       f"5 min: {m.get('m5')}% · vol ${m.get('vol5', 0):,} · {m.get('buys5')} buys / {m.get('sells5')} sells")
    elif e["kind"] == "sell":
        up = e["pnl_sol"] >= 0
        em = discord.Embed(color=0x23A55A if up else 0xDA373C, title=f"{tag} · Sold {name}: {e['pnl_pct']:+.1f}%", url=e.get("url"),
                           description=f"{e['sol_in']} → **{e['sol_out']} SOL** ({e['pnl_sol']:+.4f}) after {e['held_min']} min\nWhy: {e['reason']}")
    else:
        em = discord.Embed(color=0xE67E22, title=f"{tag} · Problem with {name}", description=str(e.get("error"))[:1000])
    if e.get("sig"): em.add_field(name="Transaction", value=f"[Solscan](https://solscan.io/tx/{e['sig']})")
    em.timestamp = __import__("datetime").datetime.fromtimestamp(e["t"], __import__("datetime").timezone.utc)
    return em


def register(bot, discord, app_commands):
    orig = bot.setup_hook

    async def hook():
        await orig()
        asyncio.create_task(loop(bot, discord))
    bot.setup_hook = hook

    @bot.tree.command(name="trader", description="Staff: Crispy Trader status (mode, positions, profit)")
    @app_commands.default_permissions(manage_guild=True)
    async def trader_cmd(interaction: discord.Interaction):
        if not bot.is_staff(interaction.user):
            return await interaction.response.send_message("Staff only.", ephemeral=True)
        st, cfg = _read("state.json", {}), _read("config.json", {})
        live = cfg.get("mode") == "live"
        n = st.get("wins", 0) + st.get("losses", 0)
        em = discord.Embed(color=0xE67E22 if live else 0x5865F2, title=f"Crispy Trader · {'💸 LIVE' if live else '🧪 PAPER'} mode")
        em.add_field(name="Today", value=f"{st.get('day_pnl', 0):+.4f} SOL")
        em.add_field(name="All time", value=f"{st.get('total_pnl', 0):+.4f} SOL")
        em.add_field(name="Win rate", value=f"{st.get('wins', 0)}/{n} ({st.get('wins', 0) / n * 100:.0f}%)" if n else "no trades yet")
        pos = st.get("positions", {})
        em.add_field(name=f"Open ({len(pos)}/{cfg.get('max_open', '?')})", inline=False,
                     value="\n".join(f"[${p['sym']}]({p.get('url')}) · {p['cost_sol']} SOL · <t:{p['t']}:R> · peak {p.get('peak_pct', 0):+.0f}%" for p in pos.values()) or "none")
        ls = st.get("last_scan")
        if ls:
            fails = ", ".join(f"{k} {v}" for k, v in sorted(ls.get("fails", {}).items(), key=lambda x: -x[1])) or "none"
            em.add_field(name="Last scan", inline=False, value=f"<t:{ls['t']}:R>: {ls['launches']} recent launches, {ls['in_window']} the right age, "
                                                               f"{ls['listed']} on DexScreener.\nFailed on: {fails}")
        recent = st.get("closed", [])[-5:]
        if recent:
            em.add_field(name="Last trades", inline=False,
                         value="\n".join(f"${c['sym']} {c['pnl']:+.4f} SOL ({c['reason']})" for c in reversed(recent)))
        em.set_footer(text=f"{cfg.get('trade_sol')} SOL/trade · max {cfg.get('max_open')} open · stops after -{cfg.get('daily_loss_sol')} SOL a day · "
                           f"TP +{cfg.get('take_profit_pct')}% / SL -{cfg.get('stop_loss_pct')}%")
        await interaction.response.send_message(embed=em, ephemeral=True)

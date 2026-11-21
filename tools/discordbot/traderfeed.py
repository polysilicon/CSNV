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
    if e.get("kind") == "wallets":   # walletfinder.py's report: wallets worth following, for the owner to approve
        rows = "\n".join(f"`{w['wallet']}`\n{w['wins']}/{w['coins']} wins · {w['pnl_sol']:+} SOL · holds ~{w['median_hold_s'] // 60} min · {w['coins_per_day']} coins/day"
                         for w in e.get("passed", [])) or "No wallet passed this time."
        em = discord.Embed(color=0x9B59B6, title="🔎 Wallet finder: wallets worth following",
                           description=f"Checked early buyers of {e.get('runners')} recent runners, vetted {e.get('vetted')} wallets.\n\n{rows}"[:4000])
        em.set_footer(text="Nothing is followed until you approve it · ask Claude to add the ones you want")
        em.timestamp = __import__("datetime").datetime.fromtimestamp(e["t"], __import__("datetime").timezone.utc)
        return em
    tag = "🧪 PAPER" if e.get("mode") != "live" else "💸 LIVE"
    name = f"{e['name']} (${e.get('sym', '?')})" if e.get("name") else f"${e.get('sym', '?')}"
    if e["kind"] == "buy":
        m = e.get("metrics") or {}
        em = discord.Embed(color=0x5865F2, title=f"{tag} · Bought {name}", url=e.get("url"),
                           description=f"**{e['sol']} SOL** in · mcap ${m.get('mcap', 0):,} · liquidity ${m.get('liq', 0):,}\n"
                                       f"5 min: {m.get('m5')}% · vol ${m.get('vol5', 0):,} · {m.get('buys5')} buys / {m.get('sells5')} sells\n"
                                       + (f"Coin age: {m['age_h']:.0f} h · 1 h: {m.get('h1')}% · 24 h: {m.get('h24')}%\n" if m.get("age_h") else "")
                                       + (f"{m['holders']:,} holders · top 10 wallets hold {m['top10']}%\n" if m.get("holders") and m.get("top10") is not None else "")
                                       + f"Signal: **{e.get('signal', 'momentum')}**")
    elif e["kind"] == "partial":
        em = discord.Embed(color=0x2ECC71, title=f"{tag} · Took profit on {name}", url=e.get("url"),
                           description=f"Sold **{e['sold_pct']}%** for {e['sol_out']} SOL ({e['reason']}).\n"
                                       f"Taken so far: **{e['realized']} SOL** of the {e['cost']} SOL stake · the rest is still riding")
    elif e["kind"] == "sell":
        up = e["pnl_sol"] >= 0
        em = discord.Embed(color=0x23A55A if up else 0xDA373C, title=f"{tag} · Sold {name}: {e['pnl_pct']:+.1f}%", url=e.get("url"),
                           description=f"{e['sol_in']} → **{e['sol_out']} SOL** ({e['pnl_sol']:+.4f}) after {e['held_min']} min\nWhy: {e['reason']}")
    else:
        err = str(e.get("error"))
        title = f"{tag} · Buy of {name} didn't go through" if "no SOL spent" in err else f"{tag} · Problem with {name}"
        em = discord.Embed(color=0xE67E22, title=title, description=err[:1000])
    if e.get("sig"): em.add_field(name="Transaction", value=f"[Solscan](https://solscan.io/tx/{e['sig']})")
    em.timestamp = __import__("datetime").datetime.fromtimestamp(e["t"], __import__("datetime").timezone.utc)
    return em


def register(bot, discord, app_commands):
    orig = bot.setup_hook

    async def hook():
        await orig()
        asyncio.create_task(loop(bot, discord))
    bot.setup_hook = hook

    @bot.tree.command(name="tradersetkey", description="Staff: give Crispy Trader an API key (only you see this)")
    @app_commands.default_permissions(administrator=True)
    @app_commands.choices(service=[app_commands.Choice(name="Helius (Solana RPC)", value="helius")])
    async def setkey_cmd(interaction: discord.Interaction, service: app_commands.Choice[str], key: str):
        if not bot.is_staff(interaction.user):
            return await interaction.response.send_message("Staff only.", ephemeral=True)
        key = key.strip()
        if not (8 <= len(key) <= 200) or not all(c.isalnum() or c in "-_" for c in key):
            return await interaction.response.send_message("That doesn't look like an API key.", ephemeral=True)
        # dropped into the trader's inbox (write-only for Yoink); the trader moves it to /etc/crispytrader (600) within seconds
        path = DIR + "inbox/" + service.value + ".key"
        try:
            fd = os.open(path, os.O_WRONLY | os.O_CREAT | os.O_TRUNC, 0o644)
            with os.fdopen(fd, "w") as f: f.write(key)
        except OSError as e:
            return await interaction.response.send_message(f"Couldn't hand the key over: {e}", ephemeral=True)
        await bot.audit(f"🔑 {interaction.user} set the trader's {service.name} key")
        await interaction.response.send_message(f"✅ {service.name} key handed to Crispy Trader. It's stored on the server where only the "
                                                "trader can read it; this message is only visible to you. You can delete it.", ephemeral=True)

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
        lv = [c for c in st.get("closed", []) if c.get("mode") == "live"]
        if lv:
            em.add_field(name="💸 Real trades", value=f"{sum(c['pnl'] for c in lv):+.4f} SOL · {sum(c['pnl'] > 0 for c in lv)}/{len(lv)} wins")
        em.add_field(name="Win rate", value=f"{st.get('wins', 0)}/{n} ({st.get('wins', 0) / n * 100:.0f}%)" if n else "no trades yet")
        pos = st.get("positions", {})
        em.add_field(name=f"Open ({len(pos)}/{cfg.get('max_open', '?')})", inline=False,
                     value="\n".join(f"[${p['sym']}]({p.get('url')}) · {'📈 ' if p.get('signal') == 'breakout' else ''}{p['cost_sol']} SOL · <t:{p['t']}:R> · peak {p.get('peak_pct', 0):+.0f}%"
                                     + (f" · {p.get('steps')} profit step(s), {p.get('realized', 0):.3f} SOL taken" if p.get("steps") else "") for p in pos.values()) or "none")
        ls = st.get("last_scan")
        if ls:
            fails = ", ".join(f"{k} {v}" for k, v in sorted(ls.get("fails", {}).items(), key=lambda x: -x[1])) or "none"
            em.add_field(name="Last scan", inline=False, value=f"<t:{ls['t']}:R>: {ls['launches']} recent launches, {ls['in_window']} the right age, "
                                                               f"{ls['listed']} on DexScreener.\nFailed on: {fails}")
        bs = st.get("last_breakout_scan")
        if bs:
            fails = ", ".join(f"{k} {v}" for k, v in sorted(bs.get("fails", {}).items(), key=lambda x: -x[1])[:5]) or "none"
            em.add_field(name="Breakout scan (older coins)", inline=False,
                         value=f"<t:{bs['t']}:R>: {bs['coins']} trending coins, {bs['checked']} on DexScreener.\nFailed on: {fails}")
        by = {}
        for c in st.get("closed", []):
            g = by.setdefault(c.get("signal") or "momentum", [0, 0, 0.0]); g[0] += 1; g[1] += c["pnl"] > 0; g[2] += c["pnl"]
        if len(by) > 1 or "breakout" in by:
            em.add_field(name="By strategy", inline=False,
                         value="\n".join(f"**{k}**: {v[2]:+.3f} SOL · {v[1]}/{v[0]} wins" for k, v in sorted(by.items())))
        sm = st.get("smart")
        if sm:
            tops = "\n".join(f"`{t['wallet'][:4]}…{t['wallet'][-4:]}` {t['pnl']:+.2f} SOL · {t['wins']}/{t['coins']} wins" for t in sm.get("top", [])[:3])
            em.add_field(name="Smart money", inline=False,
                         value=f"{sm['smart']} smart wallets (of {sm['wallets_tracked']:,} tracked) · {sm['following']} you follow · "
                               f"{sm['trades_per_min']:,} trades/min watched\n" + (tops or "No wallet qualifies yet: it needs 5+ closed coins each."))
        recent = st.get("closed", [])[-5:]
        if recent:
            em.add_field(name="Last trades", inline=False,
                         value="\n".join(f"${c['sym']} {c['pnl']:+.4f} SOL ({c['reason']})" for c in reversed(recent)))
        sz = cfg.get("size_sol")
        size_txt = (f"{sz.get('momentum')}-{max(sz.values())} SOL/trade by signal" if sz else f"{cfg.get('trade_sol')} SOL/trade")
        em.set_footer(text=f"{size_txt} · max {cfg.get('max_open')} open · stops after -{cfg.get('daily_loss_sol')} SOL a day · "
                           "TP " + " then ".join(f"+{a}% sell {b}%" for a, b in cfg.get("take_profit_steps", [])) + " of what's left"
                           + (f" · trails {'/'.join(str(t) for t in cfg['trail_by_step'])} pts by step" if cfg.get("trail_by_step") else f" · runner trails {cfg.get('runner_trail_pct')}%")
                           + f" · SL -{cfg.get('stop_loss_pct')}%")
        await interaction.response.send_message(embed=em, ephemeral=True)

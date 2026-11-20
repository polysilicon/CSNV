"""Crispy Trader: an automated Solana memecoin trader (new-launch momentum), paper first.

Runs as its own service (crispytrader), separate from the Discord bot, so the wallet key never sits in Yoink.

Strategy (config.json, re-read every cycle so it can be tuned without a restart):
- Feed: every new pump.fun launch, live from PumpPortal's public websocket (subscribeNewToken).
- Entry: once a coin is min_age..max_age minutes old, DexScreener's numbers (main pair) must show enough liquidity, a
  market cap in range, 5-minute volume, more buys than sells, a rising but not vertical 5-minute price and a sane 1-hour
  move. Then a Jupiter quote for trade_sol must exist. Max max_open positions; one trade per coin, ever.
- Exit (checked every 15 s with a real Jupiter sell quote for the whole position, so fees and price impact count):
  take profit, stop loss, a trailing stop once up trail_after_pct, max hold time, or the pool draining (rug).
- Safety: after losing daily_loss_sol in a UTC day, no new buys until tomorrow (open positions still exit). A file
  named STOP next to this script pauses buying; "sellall" in it also sells everything.

Modes: "paper" (default) trades on Jupiter quotes without sending anything: the same prices a real trade would get.
"live" signs Jupiter swaps with the wallet in WALLET and sends them; it only starts if the wallet exists and the mode
is "live". Every trade is appended to events.jsonl (Yoink posts them); state.json has positions and totals.
Not financial advice: most new memecoins go to zero.
"""
import asyncio, base64, datetime, json, os, time, traceback
import aiohttp
import smartmoney as sm

HERE = os.path.dirname(os.path.abspath(__file__))
CONFIG, STATE, EVENTS, STOP = (os.path.join(HERE, f) for f in ("config.json", "state.json", "events.jsonl", "STOP"))
WALLET = os.environ.get("TRADER_WALLET", "/etc/crispytrader/wallet.json")
PP_KEY_FILE = "/etc/crispytrader/pumpportal.key"   # PumpPortal API key: per-coin and per-wallet trade feeds need one


def pp_key():
    try:
        with open(PP_KEY_FILE) as f: return f.read().strip() or None
    except OSError: return None
PUBLIC_RPC = "https://api.mainnet-beta.solana.com"
HELIUS_KEY_FILE = "/etc/crispytrader/helius.key"
INBOX = os.path.join(HERE, "inbox")   # Yoink's /trader setkey drops keys here (group-writable); moved into /etc at once


def take_inbox():
    """Move a key Yoink dropped into the inbox into /etc/crispytrader (mode 600), so it never stays readable by Yoink."""
    for name in ("helius.key",):
        src = os.path.join(INBOX, name)
        if os.path.exists(src):
            key = open(src).read().strip()
            os.remove(src)
            if key:
                fd = os.open(os.path.join("/etc/crispytrader", name), os.O_WRONLY | os.O_CREAT | os.O_TRUNC, 0o600)
                with os.fdopen(fd, "w") as f: f.write(key)
                log(f"{name} installed")


def helius_key():
    try:
        with open(HELIUS_KEY_FILE) as f: return f.read().strip() or None
    except OSError: return None


def rpc_url():
    k = helius_key()
    return os.environ.get("TRADER_RPC") or (f"https://mainnet.helius-rpc.com/?api-key={k}" if k else PUBLIC_RPC)
SOL_MINT = "So11111111111111111111111111111111111111112"
JUP = "https://lite-api.jup.ag/swap/v1"
DEX = "https://api.dexscreener.com/tokens/v1/solana/"
UA = {"User-Agent": "Mozilla/5.0 (compatible; crispy-trader/1.0)"}
LAMPORTS = 1_000_000_000

cfg = {}
state = {"positions": {}, "closed": [], "seen": {}, "traded": [], "day": "", "day_pnl": 0.0, "total_pnl": 0.0, "wins": 0, "losses": 0}


def log(*a): print(time.strftime("%H:%M:%S"), *a, flush=True)


def load():
    global cfg, state
    with open(CONFIG) as f: cfg = json.load(f)
    try:
        with open(STATE) as f: state.update(json.load(f))
    except (OSError, ValueError): pass


def save():
    tmp = STATE + ".tmp"
    with open(tmp, "w") as f: json.dump(state, f, separators=(",", ":"))
    os.replace(tmp, STATE)


def event(**e):
    e["t"] = int(time.time()); e["mode"] = cfg.get("mode", "paper")
    with open(EVENTS, "a") as f: f.write(json.dumps(e) + "\n")


def today(): return datetime.datetime.now(datetime.timezone.utc).date().isoformat()


# ------------------------------------------------------------------------------------------------ feed
_ws = None
_kinds = {}   # PumpPortal message types seen (logged every 5 minutes)


_accounts = set()   # wallets we follow on PumpPortal (creators of coins we hold, smart wallets, followed wallets)


async def ws_send(obj):
    if _ws:
        try: await _ws.send(json.dumps(obj))
        except Exception as e: log("ws send:", e)


async def watch_creators(keys):
    """Follow these wallets' trades on PumpPortal (used for the creators of coins we hold)."""
    if not pp_key() or not cfg.get("track_wallets", True): return   # wallet feeds need a funded PumpPortal key
    keys = set(keys) - _accounts
    if keys:
        _accounts.update(keys)
        await ws_send({"method": "subscribeAccountTrade", "keys": list(keys)})


async def sync_wallets():
    """Every few minutes: re-rank wallets, follow the smart ones and the configured ones, drop the rest."""
    want = sm.rescore() | set(cfg.get("follow_wallets", [])) | {p["creator"] for p in state["positions"].values() if p.get("creator")}
    drop = _accounts - want
    if drop and pp_key():
        _accounts.difference_update(drop)
        await ws_send({"method": "unsubscribeAccountTrade", "keys": list(drop)})
    await watch_creators(want)
    sm.save()
    mins = max(1.0, (time.time() - sm.stats["since"]) / 60)
    log("feed messages so far:", dict(_kinds))
    state["smart_needs_key"] = not pp_key()
    state["smart"] = {"wallets_tracked": len(sm.wallets), "smart": len(sm.smart), "following": len(cfg.get("follow_wallets", [])),
                      "trades_per_min": round(sm.stats["trades"] / mins), "coins_followed": len(sm.tracked),
                      "top": [{"wallet": w, "pnl": round(p, 2), "coins": n, "wins": wn} for p, w, n, wn in sm.top()]}


async def feed():
    global _ws
    import websockets
    delay = 10   # grows to 10 min while PumpPortal refuses us, so a block isn't made worse by hammering it
    while True:
        try:
            key = pp_key()
            url = "wss://pumpportal.fun/api/data" + (f"?api-key={key}" if key else "")
            async with websockets.connect(url, open_timeout=20, ping_interval=30) as ws:
                _ws = ws
                await ws.send(json.dumps({"method": "subscribeNewToken"}))
                _accounts.clear()
                await watch_creators({p["creator"] for p in state["positions"].values() if p.get("creator")} | sm.smart | set(cfg.get("follow_wallets", [])))
                if sm.tracked and cfg.get("track_wallets", True) and pp_key(): await ws_send({"method": "subscribeTokenTrade", "keys": list(sm.tracked)})
                log("feed: connected"); delay = 10
                async for raw in ws:
                    try: m = json.loads(raw)
                    except ValueError: continue
                    mint = m.get("mint")
                    k = m.get("txType") or ("message" if "message" in m else "other")
                    _kinds[k] = _kinds.get(k, 0) + 1
                    if k in ("message", "other") and _kinds[k] <= 3: log("feed says:", str(m)[:200])
                    if m.get("txType") in ("buy", "sell"): sm.on_trade(m, set(cfg.get("follow_wallets", [])))
                    if m.get("txType") == "sell" and mint in state["positions"]:
                        pos = state["positions"][mint]
                        if pos.get("creator") and m.get("traderPublicKey") == pos["creator"]:
                            pos["dev_sold"] = True   # the creator is selling: often the start of a rug; manage() sells
                            log("creator sold", pos["sym"])
                        continue
                    if m.get("txType") == "create" and mint and cfg.get("track_wallets", True) and pp_key():
                        sm.on_create(mint, m.get("traderPublicKey"))
                        await ws_send({"method": "subscribeTokenTrade", "keys": [mint]})
                    if m.get("txType") == "create" and mint and mint not in state["seen"]:
                        state["seen"][mint] = {"t": int(time.time()), "sym": (m.get("symbol") or "?")[:20], "name": (m.get("name") or "?")[:40],
                                               "creator": m.get("traderPublicKey")}
                    elif mint and "txType" not in m and mint not in state["seen"]:
                        state["seen"][mint] = {"t": int(time.time()), "sym": (m.get("symbol") or "?")[:20], "name": (m.get("name") or "?")[:40],
                                               "creator": m.get("traderPublicKey")}
        except Exception as e:
            log("feed:", type(e).__name__, e)
        _ws = None
        await asyncio.sleep(delay); delay = min(delay * 2, 600)


# ------------------------------------------------------------------------------------------------ prices
RETRY = "retry"


async def jup_quote(s, inp, out, amount):
    params = {"inputMint": inp, "outputMint": out, "amount": str(int(amount)), "slippageBps": str(cfg["slippage_bps"])}
    async with s.get(JUP + "/quote", params=params, headers=UA, timeout=aiohttp.ClientTimeout(total=10)) as r:
        if r.status == 400: return None            # no route: the token really can't be traded right now
        if r.status != 200: return RETRY           # rate limit or a hiccup: try again next check, decide nothing
        q = await r.json()
    return q if q.get("outAmount") else None


async def dex_pairs(s, mints):
    """{mint: (pair, minutes since it graduated or None)} for up to 30 mints. The pair is the one with real liquidity:
    after a pump.fun coin graduates, DexScreener can still show its dead bonding-curve pair with stale numbers
    (2026-11-19: two rugs bought on "+1,300%" bonding-curve data while the new pool was already dumping)."""
    pairs = {}
    async with s.get("https://api.dexscreener.com/latest/dex/tokens/" + ",".join(mints), headers=UA, timeout=aiohttp.ClientTimeout(total=15)) as r:
        if r.status != 200: return {}
        for p in (await r.json()).get("pairs") or []:
            m = (p.get("baseToken") or {}).get("address")
            if m in mints: pairs.setdefault(m, []).append(p)
    out, now = {}, time.time()
    for m, ps in pairs.items():
        live = [p for p in ps if ((p.get("liquidity") or {}).get("usd") or 0) > 0 and p.get("priceUsd")]
        if not live: continue
        best = max(live, key=lambda p: (p.get("liquidity") or {}).get("usd") or 0)
        pools = [p.get("pairCreatedAt") for p in ps if p.get("dexId") != "pumpfun" and p.get("pairCreatedAt")]
        grad = (now - min(pools) / 1000) / 60 if pools and any(p.get("dexId") == "pumpfun" for p in ps) else None
        out[m] = (best, grad)
    return out


_fails = {}   # why candidates failed in the latest scan (shown by Yoink's /trader)


def passes(p, age_min, grad_min=None):
    c = cfg
    liq = (p.get("liquidity") or {}).get("usd") or 0
    mcap = p.get("marketCap") or p.get("fdv") or 0
    vol5 = (p.get("volume") or {}).get("m5") or 0
    tx5 = (p.get("txns") or {}).get("m5") or {}
    buys, sells = tx5.get("buys") or 0, tx5.get("sells") or 0
    ch = p.get("priceChange") or {}
    m5, h1 = ch.get("m5"), ch.get("h1")
    checks = {"liquidity": liq >= c["min_liquidity_usd"], "market cap": c["min_mcap_usd"] <= mcap <= c["max_mcap_usd"],
              "5m volume": vol5 >= c["min_vol_m5_usd"], "buy/sell": buys >= c["min_buy_sell_ratio_m5"] * max(sells, 1),
              "5m move": m5 is not None and c["min_change_m5_pct"] <= m5 <= c["max_change_m5_pct"],
              "1h move": h1 is None or h1 <= c["max_change_h1_pct"], "age": c["min_age_min"] <= age_min <= c["max_age_min"],
              "just graduated": grad_min is None or grad_min >= c.get("skip_after_graduation_min", 15)}
    for k, ok in checks.items():
        if not ok: _fails[k] = _fails.get(k, 0) + 1
    return all(checks.values()), {"liq": round(liq), "mcap": round(mcap), "vol5": round(vol5), "buys5": buys, "sells5": sells, "m5": m5, "h1": h1}


def passes_smart(p, grad_min=None):
    """The safety half of the filters, for coins smart wallets are buying (no momentum needed)."""
    c = cfg
    liq = (p.get("liquidity") or {}).get("usd") or 0
    mcap = p.get("marketCap") or p.get("fdv") or 0
    tx5 = (p.get("txns") or {}).get("m5") or {}
    m5 = (p.get("priceChange") or {}).get("m5")
    ok = (liq >= c["min_liquidity_usd"] and c["min_mcap_usd"] <= mcap <= c.get("smart_max_mcap_usd", 1_000_000)
          and (tx5.get("buys") or 0) >= (tx5.get("sells") or 0) and (m5 is None or m5 > -10)
          and (grad_min is None or grad_min >= c.get("skip_after_graduation_min", 15)))
    return ok, {"liq": round(liq), "mcap": round(mcap), "vol5": round((p.get("volume") or {}).get("m5") or 0),
                "buys5": tx5.get("buys"), "sells5": tx5.get("sells"), "m5": m5, "h1": (p.get("priceChange") or {}).get("h1")}


# ------------------------------------------------------------------------------------------------ live trading (Jupiter)
_kp = None
def keypair():
    global _kp
    if _kp is None:
        from solders.keypair import Keypair
        with open(WALLET) as f: _kp = Keypair.from_bytes(bytes(json.load(f)))
    return _kp


async def rpc(s, method, params):
    async with s.post(rpc_url(), json={"jsonrpc": "2.0", "id": 1, "method": method, "params": params}, timeout=aiohttp.ClientTimeout(total=20)) as r:
        d = await r.json()
    if "error" in d: raise RuntimeError(f"{method}: {d['error']}")
    return d["result"]


async def swap(s, quote):
    """Sign and send a Jupiter swap for this quote; return the signature once confirmed, else raise."""
    from solders.transaction import VersionedTransaction
    kp = keypair()
    body = {"quoteResponse": quote, "userPublicKey": str(kp.pubkey()), "wrapAndUnwrapSol": True, "dynamicComputeUnitLimit": True,
            "prioritizationFeeLamports": int(cfg["priority_fee_sol"] * LAMPORTS)}
    async with s.post(JUP + "/swap", json=body, headers=UA, timeout=aiohttp.ClientTimeout(total=20)) as r:
        if r.status != 200: raise RuntimeError(f"swap build {r.status}: {(await r.text())[:200]}")
        tx_b64 = (await r.json())["swapTransaction"]
    raw = VersionedTransaction.from_bytes(base64.b64decode(tx_b64))
    signed = VersionedTransaction(raw.message, [kp])
    sig = await rpc(s, "sendTransaction", [base64.b64encode(bytes(signed)).decode(), {"encoding": "base64", "skipPreflight": True, "maxRetries": 3}])
    for _ in range(40):
        await asyncio.sleep(1.5)
        st = (await rpc(s, "getSignatureStatuses", [[sig]]))["value"][0]
        if st and st.get("err"): raise RuntimeError(f"tx failed: {st['err']}")
        if st and st.get("confirmationStatus") in ("confirmed", "finalized"): return sig
    raise RuntimeError(f"tx not confirmed: {sig}")


async def token_balance(s, mint):
    res = await rpc(s, "getTokenAccountsByOwner", [str(keypair().pubkey()), {"mint": mint}, {"encoding": "jsonParsed"}])
    return sum(int(a["account"]["data"]["parsed"]["info"]["tokenAmount"]["amount"]) for a in res["value"])


async def sol_balance(s):
    return (await rpc(s, "getBalance", [str(keypair().pubkey())]))["value"] / LAMPORTS


# ------------------------------------------------------------------------------------------------ trading
def live(): return cfg.get("mode") == "live" and os.path.exists(WALLET)


async def holder_balance(s, owner, mint):
    res = await rpc(s, "getTokenAccountsByOwner", [owner, {"mint": mint}, {"encoding": "jsonParsed"}])
    return sum(int(a["account"]["data"]["parsed"]["info"]["tokenAmount"]["amount"]) for a in res["value"])


async def helius_watch():
    """The creator-sell exit without PumpPortal: logsSubscribe (a standard, free-plan Solana WebSocket method) to the
    creator of each coin we hold. Any of their transactions that logs a sell makes us check their balance of our coin;
    if it dropped, they're selling it, and manage() exits. Only a few low-traffic subscriptions, so it costs little."""
    import websockets
    while True:
        key = helius_key()
        if not key: await asyncio.sleep(30); continue
        try:
            async with websockets.connect(f"wss://mainnet.helius-rpc.com/?api-key={key}", open_timeout=20, ping_interval=30) as ws, aiohttp.ClientSession() as s:
                subs, pending, rid = {}, {}, 0   # creator -> subscription id; request id -> creator
                log("helius: connected")
                while True:
                    want = {p["creator"] for p in state["positions"].values() if p.get("creator")}
                    for c in want - set(subs) - set(pending.values()):
                        rid += 1; pending[rid] = c
                        await ws.send(json.dumps({"jsonrpc": "2.0", "id": rid, "method": "logsSubscribe", "params": [{"mentions": [c]}, {"commitment": "confirmed"}]}))
                    for c in set(subs) - want:
                        rid += 1
                        await ws.send(json.dumps({"jsonrpc": "2.0", "id": rid, "method": "logsUnsubscribe", "params": [subs.pop(c)]}))
                    try: m = json.loads(await asyncio.wait_for(ws.recv(), 10))
                    except asyncio.TimeoutError: continue
                    if "id" in m and m["id"] in pending:
                        c = pending.pop(m["id"])
                        if "result" in m: subs[c] = m["result"]
                        continue
                    if m.get("method") != "logsNotification": continue
                    logs = " ".join((m["params"]["result"]["value"].get("logs") or []))
                    if "Sell" not in logs: continue
                    sub = m["params"]["subscription"]
                    creator = next((c for c, i in subs.items() if i == sub), None)
                    for mint, pos in list(state["positions"].items()):
                        if pos.get("creator") != creator or pos.get("dev_sold"): continue
                        try: bal = await holder_balance(s, creator, mint)
                        except Exception as e: log("helius balance:", e); continue
                        if pos.get("creator_bal") is not None and bal < pos["creator_bal"]:
                            pos["dev_sold"] = True; log("creator sold (helius)", pos["sym"])
                        pos["creator_bal"] = bal
        except Exception as e:
            log("helius:", type(e).__name__, e)
        await asyncio.sleep(30)


async def gecko_launches():
    """Backup launch feed while PumpPortal is down: new Solana pools from GeckoTerminal (free, ~1 min behind).
    These are pools (graduated pump.fun coins and other DEX launches), not coins still on the bonding curve."""
    async with aiohttp.ClientSession() as s:
        while True:
            await asyncio.sleep(60)
            if _ws is not None: continue   # PumpPortal is up: it's faster and has pre-graduation coins
            try:
                async with s.get("https://api.geckoterminal.com/api/v2/networks/solana/new_pools", params={"page": "1"}, headers=UA,
                                 timeout=aiohttp.ClientTimeout(total=15)) as r:
                    if r.status != 200: continue
                    pools = (await r.json()).get("data") or []
                n = 0
                for p in pools:
                    mint = ((p.get("relationships") or {}).get("base_token") or {}).get("data", {}).get("id", "").removeprefix("solana_")
                    a = p.get("attributes") or {}
                    if not mint or mint == SOL_MINT or mint in state["seen"]: continue
                    try: t0 = datetime.datetime.fromisoformat(a["pool_created_at"].replace("Z", "+00:00")).timestamp()
                    except Exception: t0 = time.time()
                    name = (a.get("name") or "?").split(" / ")[0]
                    state["seen"][mint] = {"t": int(t0), "sym": name[:20], "name": name[:40], "creator": None, "src": "geckoterminal"}; n += 1
                if n: log(f"geckoterminal: {n} new pools")
            except Exception as e:
                log("geckoterminal:", type(e).__name__, e)


# "Large Amount of LP Unlocked" is left out on purpose: RugCheck computes it over all of a coin's pools, so an empty
# unlocked side pool flags coins whose real pool is 100% locked (FEAR, GIGAGTA6, MF on 2026-11-20). The lock is checked
# on the pool we actually trade instead (main_pool_lock below).
BAD_RISKS = {"Mint Authority still enabled", "Freeze Authority still enabled", "Single holder ownership",
             "Top 10 holders high ownership", "High ownership", "Copycat token"}


async def rug_ok(s, mint, pool=None):
    """RugCheck's full report, right before a buy. (ok, why). Fails if RugCheck flags a danger from rug_risks, or if the
    pool we'd trade (DexScreener's main pair; else the deepest pool RugCheck knows) has under min_lp_locked_pct of its
    liquidity locked or burned: whoever holds unlocked LP tokens can pull the pool. If RugCheck can't answer, don't buy."""
    try:
        async with s.get(f"https://api.rugcheck.xyz/v1/tokens/{mint}/report", headers={**UA, "Accept": "application/json"},
                         timeout=aiohttp.ClientTimeout(total=20)) as r:
            if r.status != 200: return False, f"rugcheck unavailable ({r.status})"
            d = await r.json()
    except Exception as e:
        return False, f"rugcheck unavailable ({type(e).__name__})"
    bad = [x.get("name") for x in d.get("risks") or [] if x.get("level") == "danger" and x.get("name") in set(cfg.get("rug_risks", BAD_RISKS))]
    if bad: return False, "rugcheck: " + ", ".join(bad)
    markets = d.get("markets") or []
    liq = lambda mk: ((mk.get("lp") or {}).get("quoteUSD") or 0) + ((mk.get("lp") or {}).get("baseUSD") or 0)
    mk = next((x for x in markets if pool and x.get("pubkey") == pool), None) or (max(markets, key=liq) if markets else None)
    if mk is None: return False, "rugcheck: no pool data"
    locked = (mk.get("lp") or {}).get("lpLockedPct") or 0
    if locked < cfg.get("min_lp_locked_pct", 30): return False, f"rugcheck: only {locked:.0f}% of the trading pool's liquidity locked"
    return True, f"pool LP {locked:.0f}% locked"


async def buy(s, mint, info, metrics, pair, signal="momentum"):
    lamports = int(cfg["trade_sol"] * LAMPORTS)
    ok, why = await rug_ok(s, mint, pair.get("pairAddress"))
    if not ok:
        state["traded"] = (state["traded"] + [mint])[-3000:]   # don't keep re-checking it
        key = why.split(":")[0].split("(")[0].strip()
        _fails[key] = _fails.get(key, 0) + 1
        state.setdefault("rug_skips", []).append({"t": int(time.time()), "sym": info["sym"], "why": why})
        state["rug_skips"] = state["rug_skips"][-50:]
        log("skip", info["sym"], why)
        return
    metrics = {**metrics, "rugcheck": why}
    q = await jup_quote(s, SOL_MINT, mint, lamports)
    if not q or q == RETRY: return
    sig, amount = None, int(q["outAmount"])
    if live():
        if await sol_balance(s) < cfg["trade_sol"] + 0.01:
            log("buy skipped: wallet low on SOL"); return
        sig = await swap(s, q)
        await asyncio.sleep(2)
        amount = await token_balance(s, mint) or amount
    if info.get("creator"): asyncio.create_task(watch_creators([info["creator"]]))
    creator_bal = None
    if info.get("creator") and helius_key():
        try: creator_bal = await holder_balance(s, info["creator"], mint)
        except Exception as e: log("creator balance:", e)
    state["positions"][mint] = {"sym": info["sym"], "name": info["name"], "amount": amount, "amount0": amount, "realized": 0.0, "steps": 0, "cost_sol": cfg["trade_sol"], "creator": info.get("creator"), "creator_bal": creator_bal,
                                "t": int(time.time()), "peak_pct": 0.0, "liq0": metrics["liq"], "url": pair.get("url"), "sig": sig}
    state["traded"] = (state["traded"] + [mint])[-3000:]
    save()
    state["positions"][mint]["signal"] = signal
    event(kind="buy", mint=mint, sym=info["sym"], name=info["name"], sol=cfg["trade_sol"], metrics=metrics, url=pair.get("url"), sig=sig, signal=signal)
    log("BUY", info["sym"], mint, metrics)


async def sell(s, mint, reason, fraction=1.0):
    """Sell `fraction` of the position (1 = all of it and close it). Partial sells keep the rest open."""
    pos = state["positions"][mint]
    partial = fraction < 0.999
    amt = int(pos["amount"] * fraction) if partial else pos["amount"]
    if amt <= 0: return False
    q = RETRY
    for _ in range(3):
        try: q = await jup_quote(s, mint, SOL_MINT, amt)
        except Exception: q = RETRY
        if q != RETRY: break
        await asyncio.sleep(1)
    if q == RETRY: log("sell: no quote right now", pos["sym"]); return False
    out_sol = int(q["outAmount"]) / LAMPORTS if q else 0.0
    sig = None
    if live():
        if not q: log("sell: no route for", mint); return False
        sig = await swap(s, q)
    fee = cfg["priority_fee_sol"] if live() else 0.0
    if partial:
        pos["amount"] -= amt; pos["realized"] = pos.get("realized", 0.0) + out_sol - fee; pos["steps"] = pos.get("steps", 0) + 1
        save()
        event(kind="partial", mint=mint, sym=pos["sym"], name=pos["name"], sold_pct=round(fraction * 100), sol_out=round(out_sol, 6),
              realized=round(pos["realized"], 6), cost=pos["cost_sol"], reason=reason, held_min=round((time.time() - pos["t"]) / 60, 1), url=pos.get("url"), sig=sig)
        log("PARTIAL", pos["sym"], reason, f"{out_sol:.4f} SOL")
        return True
    total_out = pos.get("realized", 0.0) + out_sol
    pnl = total_out - pos["cost_sol"] - fee - (cfg["priority_fee_sol"] if live() else 0.0)   # this sell and the buy
    state["positions"].pop(mint)
    if state["day"] != today(): state["day"], state["day_pnl"] = today(), 0.0
    state["day_pnl"] += pnl; state["total_pnl"] += pnl
    state["wins" if pnl > 0 else "losses"] += 1
    state["closed"] = (state["closed"] + [{"mint": mint, "sym": pos["sym"], "cost": pos["cost_sol"], "out": total_out, "pnl": pnl,
                                            "reason": reason, "steps": pos.get("steps", 0), "t0": pos["t"], "t1": int(time.time())}])[-500:]
    save()
    event(kind="sell", mint=mint, sym=pos["sym"], name=pos["name"], sol_in=pos["cost_sol"], sol_out=round(total_out, 6), pnl_sol=round(pnl, 6),
          pnl_pct=round(pnl / pos["cost_sol"] * 100, 1), reason=reason, steps=pos.get("steps", 0),
          held_min=round((time.time() - pos["t"]) / 60, 1), url=pos.get("url"), sig=sig)
    log("SELL", pos["sym"], reason, f"{pnl:+.4f} SOL")
    return True


async def manage(s):
    """Exits for open positions, from a real Jupiter quote for the whole position."""
    stop = open(STOP).read() if os.path.exists(STOP) else ""
    for mint, pos in list(state["positions"].items()):
        if "sellall" in stop:
            await sell(s, mint, "manual sell-all"); continue
        try: q = await jup_quote(s, mint, SOL_MINT, pos["amount"])
        except Exception: q = RETRY
        if q == RETRY and not pos.get("dev_sold") and "sellall" not in stop: continue
        pos["noroute"] = 0 if q and q != RETRY else pos.get("noroute", 0) + 1
        value = int(q["outAmount"]) / LAMPORTS if q and q != RETRY else 0.0
        # the price move since entry, per token (so it still means the same after partial sells)
        pct = (value * pos.get("amount0", pos["amount"]) / (pos["amount"] * pos["cost_sol"]) - 1) * 100 if pos["amount"] else -100.0
        pos["peak_pct"] = max(pos["peak_pct"], pct)
        held = (time.time() - pos["t"]) / 60
        reason = None
        if not q or q == RETRY:
            if pos.get("dev_sold") or "sellall" in stop or pos["noroute"] >= 3: pass
            else: continue   # a missing quote isn't a price: wait for the next check
        if pos.get("dev_sold"): reason = f"creator sold {pct:+.0f}%" if q and q != RETRY else "creator sold"
        elif not q or q == RETRY: reason = "no route (pool gone?)"
        else:
            ladder = cfg.get("take_profit_steps") or [[cfg.get("take_profit_pct", 60), 100]]
            step = pos.get("steps", 0)
            runner = step > 0   # some profit already taken: the rest rides with looser rules
            if step < len(ladder) and pct >= ladder[step][0]:
                part = ladder[step][1] / 100
                label = f"take profit {step + 1}/{len(ladder)} at {pct:+.0f}%"
                try:
                    if part >= 0.999: await sell(s, mint, label)
                    else: await sell(s, mint, label + f": sold {ladder[step][1]}%, the rest rides", part)
                except Exception as e: log("sell failed", mint, e); event(kind="error", mint=mint, sym=pos["sym"], error=str(e)[:200])
                await asyncio.sleep(0.3); continue
            trail = cfg.get("runner_trail_pct", cfg["trail_pct"]) if runner else cfg["trail_pct"]
            if not runner and pct <= -cfg["stop_loss_pct"]: reason = f"stop loss {pct:+.0f}%"
            elif runner and pct <= cfg.get("runner_floor_pct", 0): reason = f"back to entry {pct:+.0f}% (profit already taken)"
            elif pos["peak_pct"] >= cfg["trail_after_pct"] and pct <= pos["peak_pct"] - trail: reason = f"trailing stop {pct:+.0f}% (peak {pos['peak_pct']:+.0f}%)"
            elif held >= (cfg.get("runner_max_hold_min", cfg["max_hold_min"]) if runner else cfg["max_hold_min"]): reason = f"time limit {pct:+.0f}%"
        if reason:
            try: await sell(s, mint, reason)
            except Exception as e: log("sell failed", mint, e); event(kind="error", mint=mint, sym=pos["sym"], error=str(e)[:200])
        await asyncio.sleep(0.3)
    save()


async def scan(s):
    """Entries: coins in the age window that pass the filters."""
    if os.path.exists(STOP): return
    if state["day"] != today(): state["day"], state["day_pnl"] = today(), 0.0
    if state["day_pnl"] <= -cfg["daily_loss_sol"]: return
    now = time.time()
    for m in [m for m, i in state["seen"].items() if now - i["t"] > (cfg["max_age_min"] + 5) * 60]: state["seen"].pop(m)
    window = [m for m, i in state["seen"].items() if cfg["min_age_min"] * 60 <= now - i["t"] <= cfg["max_age_min"] * 60 and m not in state["traded"]]
    _fails.clear()
    listed = 0
    for i in range(0, len(window), 30):
        if len(state["positions"]) >= cfg["max_open"]: return
        try: pairs = await dex_pairs(s, window[i:i + 30])
        except Exception as e: log("dex:", e); continue
        listed += len(pairs)
        for mint, (p, grad) in pairs.items():
            if len(state["positions"]) >= cfg["max_open"] or mint in state["positions"]: continue
            ok, metrics = passes(p, (now - state["seen"][mint]["t"]) / 60, grad)
            if ok:
                try: await buy(s, mint, state["seen"][mint], metrics, p)
                except Exception as e: log("buy failed", mint, e); event(kind="error", mint=mint, sym=state["seen"][mint]["sym"], error=str(e)[:200])
        await asyncio.sleep(1)
    if cfg.get("smart_entries", True) and len(state["positions"]) < cfg["max_open"]:
        follow = set(cfg.get("follow_wallets", []))
        hot = {m: ws for m, ws in sm.hot(cfg.get("smart_min_wallets", 2), cfg.get("smart_window_min", 10), follow).items()
               if m not in state["positions"] and m not in state["traded"]}
        if hot:
            try: pairs = await dex_pairs(s, list(hot)[:30])
            except Exception as e: log("dex:", e); pairs = {}
            for mint, (p, grad) in pairs.items():
                if len(state["positions"]) >= cfg["max_open"]: break
                ok, metrics = passes_smart(p, grad)
                if not ok: continue
                tok = p.get("baseToken") or {}
                info = state["seen"].get(mint) or {"sym": (tok.get("symbol") or "?")[:20], "name": (tok.get("name") or "?")[:40], "creator": sm.creators.get(mint)}
                n = len(hot[mint]); f = any(w in follow for w in hot[mint])
                try: await buy(s, mint, info, metrics, p, signal=f"smart money: {n} wallet{'s' if n > 1 else ''}" + (" (one you follow)" if f else ""))
                except Exception as e: log("buy failed", mint, e); event(kind="error", mint=mint, sym=info["sym"], error=str(e)[:200])
    state["last_scan"] = {"t": int(now), "launches": len(state["seen"]), "in_window": len(window), "listed": listed, "fails": dict(_fails)}


async def main():
    load()
    sm.load()
    log(f"Crispy Trader starting in {cfg['mode']} mode" + (" (no wallet: paper only)" if cfg["mode"] == "live" and not os.path.exists(WALLET) else ""))
    asyncio.create_task(feed())
    asyncio.create_task(helius_watch())
    asyncio.create_task(gecko_launches())
    n = 0
    async with aiohttp.ClientSession() as s:
        while True:
            try:
                with open(CONFIG) as f: cfg.update(json.load(f))
                take_inbox()
                await manage(s)
                per_min = max(1, 60 // cfg.get("exit_check_sec", 5))
                if n % per_min == 0:
                    await scan(s)   # entries once a minute, exits every few seconds
                    old = sm.expired()
                    if old: await ws_send({"method": "unsubscribeTokenTrade", "keys": old})
                if n % (per_min * 5) == 0: await sync_wallets()
            except Exception as e:
                log("loop:", type(e).__name__, e); traceback.print_exc()
            n += 1
            await asyncio.sleep(cfg.get("exit_check_sec", 5))


if __name__ == "__main__":
    asyncio.run(main())

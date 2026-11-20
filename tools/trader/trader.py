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


LAUNCHES = os.path.join(HERE, "launches.jsonl")
LAUNCHES_MAX = 2_000_000


def share_launch(m):
    """Append a new launch to launches.jsonl for Yoink's /newpairs, so the server keeps ONE PumpPortal connection
    (PumpPortal asks for one per IP; two got us refused). Yoink tails the file; it's emptied when it gets big."""
    try:
        if os.path.exists(LAUNCHES) and os.path.getsize(LAUNCHES) > LAUNCHES_MAX: open(LAUNCHES, "w").close()
        with open(LAUNCHES, "a") as f:
            f.write(json.dumps({"t": int(time.time()), "mint": m.get("mint"), "name": (m.get("name") or "")[:60],
                                "symbol": (m.get("symbol") or "")[:20], "marketCapSol": m.get("marketCapSol")}) + "\n")
    except OSError as e:
        log("launches.jsonl:", e)


MIGRATIONS = os.path.join(HERE, "migrations.jsonl")


def log_migration(m):
    """Every pump.fun graduation (time, mint, pool): an unbiased sample of graduates, winners and duds alike, for
    studying what early charts lead to runners. Kept to about 20 MB."""
    try:
        if os.path.exists(MIGRATIONS) and os.path.getsize(MIGRATIONS) > 20_000_000: os.replace(MIGRATIONS, MIGRATIONS + ".old")
        with open(MIGRATIONS, "a") as f:
            f.write(json.dumps({"t": int(time.time()), "mint": m.get("mint"), "pool": m.get("pool")}) + "\n")
    except OSError as e:
        log("migrations.jsonl:", e)


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
                await ws.send(json.dumps({"method": "subscribeMigration"}))   # free: every graduation, logged for research
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
                    if m.get("txType") == "create" and mint: share_launch(m)
                    if m.get("txType") == "migrate" and mint: log_migration(m)
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


async def jup_quote(s, inp, out, amount, slippage_bps=None):
    params = {"inputMint": inp, "outputMint": out, "amount": str(int(amount)), "slippageBps": str(slippage_bps or cfg["slippage_bps"])}
    async with s.get(JUP + "/quote", params=params, headers=UA, timeout=aiohttp.ClientTimeout(total=10)) as r:
        if r.status == 400: return None            # no route: the token really can't be traded right now
        if r.status != 200: return RETRY           # rate limit or a hiccup: try again next check, decide nothing
        q = await r.json()
    return q if q.get("outAmount") else None


async def dex_pairs(s, mints):
    """{mint: pair} for up to 30 mints. The pair is the one with real liquidity:
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
        out[m] = best
    return out


_fails = {}   # why candidates failed in the latest scan (shown by Yoink's /trader)


def pool_sane(liq, mcap, vol5):
    """Rug tells seen on 2026-11-19/20 (every one went -93% to -100% within minutes; no winner had either):
    - market cap under min_mcap_to_liq x liquidity: a real pool holds only part of the supply, so liquidity above the
      market cap means a pool seeded to look deep (WOOF, DOWNCAT, MBBURN, RUDY: 0.5-0.6x);
    - 5-minute volume over max_vol5_to_liq x liquidity: wash-traded by bots before a dump (FIONA 7.6x, RUDY 10.9x)."""
    c = cfg
    return mcap >= c.get("min_mcap_to_liq", 1.5) * liq and vol5 <= c.get("max_vol5_to_liq", 6) * max(liq, 1)


def passes(p, age_min):
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
              "fake pool": pool_sane(liq, mcap, vol5)}
    for k, ok in checks.items():
        if not ok: _fails[k] = _fails.get(k, 0) + 1
    return all(checks.values()), {"liq": round(liq), "mcap": round(mcap), "vol5": round(vol5), "buys5": buys, "sells5": sells, "m5": m5, "h1": h1}


def passes_smart(p):
    """The safety half of the filters, for coins smart wallets are buying (no momentum needed)."""
    c = cfg
    liq = (p.get("liquidity") or {}).get("usd") or 0
    mcap = p.get("marketCap") or p.get("fdv") or 0
    tx5 = (p.get("txns") or {}).get("m5") or {}
    m5 = (p.get("priceChange") or {}).get("m5")
    ok = (liq >= c["min_liquidity_usd"] and c["min_mcap_usd"] <= mcap <= c.get("smart_max_mcap_usd", 1_000_000)
          and (tx5.get("buys") or 0) >= (tx5.get("sells") or 0) and (m5 is None or m5 > -10)
          and pool_sane(liq, mcap, (p.get("volume") or {}).get("m5") or 0))
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


async def close_token_accounts(s, mint):
    """Close our (empty) token accounts for `mint`, returning their rent (about 0.002 SOL each) to the wallet."""
    from solders.instruction import Instruction, AccountMeta
    from solders.pubkey import Pubkey
    from solders.message import MessageV0
    from solders.hash import Hash
    from solders.transaction import VersionedTransaction
    kp = keypair()
    res = await rpc(s, "getTokenAccountsByOwner", [str(kp.pubkey()), {"mint": mint}, {"encoding": "jsonParsed"}])
    ixs = []
    for a in res["value"]:
        if int(a["account"]["data"]["parsed"]["info"]["tokenAmount"]["amount"]) != 0: continue
        ixs.append(Instruction(Pubkey.from_string(a["account"]["owner"]), bytes([9]),   # SPL Token / Token-2022 CloseAccount
                               [AccountMeta(Pubkey.from_string(a["pubkey"]), False, True), AccountMeta(kp.pubkey(), False, True),
                                AccountMeta(kp.pubkey(), True, False)]))
    if not ixs: return None
    bh = (await rpc(s, "getLatestBlockhash", [{"commitment": "confirmed"}]))["value"]["blockhash"]
    tx = VersionedTransaction(MessageV0.try_compile(kp.pubkey(), ixs, [], Hash.from_string(bh)), [kp])
    return await rpc(s, "sendTransaction", [base64.b64encode(bytes(tx)).decode(), {"encoding": "base64", "maxRetries": 3}])


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


async def rug_ok(s, mint, pair, metrics):
    """RugCheck's full report, right before a buy. (ok, why). Fails if RugCheck flags a danger from rug_risks, or if the
    pool we'd trade (DexScreener's main pair; else the deepest pool RugCheck knows) has under min_lp_locked_pct of its
    liquidity locked or burned: whoever holds unlocked LP tokens can pull the pool. If RugCheck can't answer, don't buy.

    Then who holds it (2026-11-20: rugs that dumped -93% to -100% within seconds of our buy):
    - holders: under min_holders, or more than max_buys_per_holder 5-minute buys per holder, means a few wallets are
      faking the activity (the rugs had 3-36 holders behind 300-1,300 buys; winners 54-3,900 holders, under 14 per holder);
    - supply: the 10 biggest wallets other than the pool (Helius, live) holding over max_top10_pct of the supply can
      dump the pool in one go. Both numbers are recorded with every buy so the limits can be tuned on real results."""
    pool = pair.get("pairAddress")
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
    holders = d.get("totalHolders") or 0
    metrics["holders"] = holders
    if holders < cfg.get("min_holders", 30): return False, f"holders: only {holders}"
    if (metrics.get("buys5") or 0) > cfg.get("max_buys_per_holder", 20) * holders:
        return False, f"holders: {metrics.get('buys5')} buys in 5 min from {holders} holders (wash trading)"
    try:
        top = await top10_pct(s, mint, pair)
    except Exception as e:
        top = None; log("top holders:", type(e).__name__, e)
    metrics["top10"] = top
    if top is not None and top > cfg.get("max_top10_pct", 35): return False, f"holders: top 10 wallets hold {top:.0f}% of the supply"
    return True, f"pool LP {locked:.0f}% locked"


async def top10_pct(s, mint, pair):
    """% of the supply in the 10 biggest token accounts, leaving out the pool's own (the one holding about the pool's
    token reserve, pair.liquidity.base). Two RPC calls."""
    sup = await rpc(s, "getTokenSupply", [mint])
    supply = float(sup["value"]["uiAmount"] or 0)
    if supply <= 0: return None
    accts = (await rpc(s, "getTokenLargestAccounts", [mint]))["value"]
    base = float((pair.get("liquidity") or {}).get("base") or 0)
    held = [float(a.get("uiAmount") or 0) for a in accts]
    if base > 0 and held:
        pool_i = min(range(len(held)), key=lambda i: abs(held[i] - base))
        if abs(held[pool_i] - base) <= 0.05 * base: held.pop(pool_i)
    return round(sum(sorted(held, reverse=True)[:10]) / supply * 100, 1)


SIZES = {"momentum": 0.1, "momentum_smart": 0.3, "smart": 0.25, "follow": 0.3, "breakout": 0.2}


def strategy(signal):
    """The strategy a signal label belongs to, for per-strategy stats."""
    sig = signal or "momentum"
    if sig == "breakout": return "breakout"
    if sig.startswith("momentum + smart"): return "momentum + smart money"
    if sig.startswith("smart money"): return "smart money"
    return "momentum"


def size_for(mint, signal):
    """(SOL to spend, signal label): bigger on stronger signals. cfg "size_sol" overrides SIZES; without any of it,
    every trade is trade_sol. A momentum coin that smart wallets are also buying counts as the stronger momentum_smart."""
    sz = {**SIZES, **(cfg.get("size_sol") or {})} if cfg.get("size_sol") is not None else None
    if sz is None: return cfg["trade_sol"], signal
    if signal == "breakout": return sz["breakout"], signal
    if signal.startswith("smart money"): return (sz["follow"] if "follow" in signal else sz["smart"]), signal
    recent = {w: t for w, t in sm.signals.get(mint, {}).items() if time.time() - t <= cfg.get("smart_window_min", 10) * 60}
    if recent: return sz["momentum_smart"], f"momentum + smart money ({len(recent)} wallet{'s' if len(recent) > 1 else ''})"
    return sz["momentum"], signal


async def buy(s, mint, info, metrics, pair, signal="momentum"):
    size, signal = size_for(mint, signal)
    lamports = int(size * LAMPORTS)
    metrics = dict(metrics)
    ok, why = await rug_ok(s, mint, pair, metrics)
    if not ok:
        if signal != "breakout": state["traded"] = (state["traded"] + [mint])[-3000:]   # don't keep re-checking it
        key = why.split(":")[0].split("(")[0].strip()
        _fails[key] = _fails.get(key, 0) + 1
        state.setdefault("rug_skips", []).append({"t": int(time.time()), "sym": info["sym"], "why": why})
        state["rug_skips"] = state["rug_skips"][-50:]
        log("skip", info["sym"], why)
        return
    metrics = {**metrics, "rugcheck": why}
    q = await jup_quote(s, SOL_MINT, mint, lamports)
    if not q or q == RETRY: return
    sig, amount, cost = None, int(q["outAmount"]), size
    if live():
        before = await sol_balance(s)
        if before < size + 0.01:
            log("buy skipped: wallet low on SOL"); return
        try: sig = await swap(s, q)
        except Exception as e:
            # "not confirmed" can still land a few seconds later: if we hold the coin now, track it rather than lose it
            await asyncio.sleep(8)
            if not await token_balance(s, mint): raise
            log("buy landed despite:", e)
        await asyncio.sleep(2)
        amount = await token_balance(s, mint) or amount
        spent = before - await sol_balance(s)   # the swap, fees and the new token account's rent: what really left the wallet
        if 0 < spent < size * 3: cost = spent
    if info.get("creator"): asyncio.create_task(watch_creators([info["creator"]]))
    creator_bal = None
    if info.get("creator") and helius_key():
        try: creator_bal = await holder_balance(s, info["creator"], mint)
        except Exception as e: log("creator balance:", e)
    state["positions"][mint] = {"sym": info["sym"], "name": info["name"], "amount": amount, "amount0": amount, "realized": 0.0, "steps": 0, "cost_sol": cost, "mode": "live" if live() else "paper", "creator": info.get("creator"), "creator_bal": creator_bal,
                                "t": int(time.time()), "peak_pct": 0.0, "liq0": metrics["liq"], "url": pair.get("url"), "sig": sig}
    state["positions"][mint]["signal"] = signal
    if signal != "breakout": state["traded"] = (state["traded"] + [mint])[-3000:]
    save()
    event(kind="buy", mint=mint, sym=info["sym"], name=info["name"], sol=size, metrics=metrics, url=pair.get("url"), sig=sig, signal=signal)
    log("BUY", info["sym"], mint, metrics)


async def sell(s, mint, reason, fraction=1.0):
    """Sell `fraction` of the position (1 = all of it and close it). Partial sells keep the rest open."""
    pos = state["positions"][mint]
    real = live() and pos.get("mode") == "live"   # positions opened on paper stay on paper
    partial = fraction < 0.999
    if real and not partial:
        pos["amount"] = await token_balance(s, mint)   # sell what the wallet really holds
    amt = int(pos["amount"] * fraction) if partial else pos["amount"]
    if amt <= 0 and partial: return False
    q = RETRY
    for _ in range(3):
        try: q = await jup_quote(s, mint, SOL_MINT, amt, cfg.get("sell_slippage_bps", 1000)) if amt > 0 else None
        except Exception: q = RETRY
        if q != RETRY: break
        await asyncio.sleep(1)
    if q == RETRY: log("sell: no quote right now", pos["sym"]); return False
    out_sol = int(q["outAmount"]) / LAMPORTS if q else 0.0
    sig, fee = None, 0.0
    if real and q:
        before = await sol_balance(s)
        sig = await swap(s, q)
        if not partial:
            try:
                await asyncio.sleep(2)
                await close_token_accounts(s, mint)
                await asyncio.sleep(3)
            except Exception as e: log("close token account:", type(e).__name__, e)
        got = await sol_balance(s) - before   # what really came back, after fees (and the account rent, on a full sell)
        if got >= 0: out_sol = got
    elif real and not q and partial: return False
    # (a full sell with no route at all writes the position off at 0: the coin can't be sold, don't hold a slot for it)
    if partial:
        pos["amount"] -= amt; pos["realized"] = pos.get("realized", 0.0) + out_sol - fee; pos["steps"] = pos.get("steps", 0) + 1
        pos["sell_fails"] = 0
        save()
        event(kind="partial", mint=mint, sym=pos["sym"], name=pos["name"], sold_pct=round(fraction * 100), sol_out=round(out_sol, 6),
              realized=round(pos["realized"], 6), cost=pos["cost_sol"], reason=reason, held_min=round((time.time() - pos["t"]) / 60, 1), url=pos.get("url"), sig=sig)
        log("PARTIAL", pos["sym"], reason, f"{out_sol:.4f} SOL")
        return True
    total_out = pos.get("realized", 0.0) + out_sol
    pnl = total_out - pos["cost_sol"] - fee   # live: cost and out are measured wallet changes, fees included
    state["positions"].pop(mint)
    if state["day"] != today(): state["day"], state["day_pnl"] = today(), 0.0
    state["day_pnl"] += pnl; state["total_pnl"] += pnl
    state["wins" if pnl > 0 else "losses"] += 1
    state["closed"] = (state["closed"] + [{"mint": mint, "sym": pos["sym"], "cost": pos["cost_sol"], "out": total_out, "pnl": pnl,
                                            "reason": reason, "steps": pos.get("steps", 0), "t0": pos["t"], "t1": int(time.time()),
                                            "signal": strategy(pos.get("signal")), "mode": pos.get("mode", "paper")}])[-500:]
    save()
    event(kind="sell", mint=mint, sym=pos["sym"], name=pos["name"], sol_in=pos["cost_sol"], sol_out=round(total_out, 6), pnl_sol=round(pnl, 6),
          pnl_pct=round(pnl / pos["cost_sol"] * 100, 1), reason=reason, steps=pos.get("steps", 0),
          held_min=round((time.time() - pos["t"]) / 60, 1), url=pos.get("url"), sig=sig)
    log("SELL", pos["sym"], reason, f"{pnl:+.4f} SOL")
    return True


def sell_failed(mint, pos, e):
    """A sell that raised (a live swap that failed or didn't confirm): retry after a pause, and DM only the first
    failure and every 10th, not one every 5 seconds."""
    pos["sell_fails"] = pos.get("sell_fails", 0) + 1
    pos["sell_retry_t"] = time.time() + min(60, 10 * pos["sell_fails"])
    log("sell failed", pos["sym"], mint, e)
    if pos["sell_fails"] == 1 or pos["sell_fails"] % 10 == 0:
        event(kind="error", mint=mint, sym=pos["sym"], error=f"sell failed ({pos['sell_fails']}x so far, retrying): {str(e)[:180]}")


async def manage(s):
    """Exits for open positions, from a real Jupiter quote for the whole position."""
    stop = open(STOP).read() if os.path.exists(STOP) else ""
    for mint, pos in list(state["positions"].items()):
        if time.time() < pos.get("sell_retry_t", 0): continue   # a sell just failed: wait a moment before trying again
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
        x = exit_cfg(pos)
        reason = None
        if not q or q == RETRY:
            if pos.get("dev_sold") or "sellall" in stop or pos["noroute"] >= 3: pass
            else: continue   # a missing quote isn't a price: wait for the next check
        if pos.get("dev_sold"): reason = f"creator sold {pct:+.0f}%" if q and q != RETRY else "creator sold"
        elif not q or q == RETRY: reason = "no route (pool gone?)"
        else:
            ladder = x.get("take_profit_steps") or [[x.get("take_profit_pct", 60), 100]]
            step = pos.get("steps", 0)
            runner = step > 0   # some profit already taken: the rest rides with looser rules
            if step < len(ladder) and pct >= ladder[step][0]:
                part = ladder[step][1] / 100
                label = f"take profit {step + 1}/{len(ladder)} at {pct:+.0f}%"
                try:
                    if part >= 0.999: await sell(s, mint, label)
                    else: await sell(s, mint, label + f": sold {ladder[step][1]}%, the rest rides", part)
                except Exception as e: sell_failed(mint, pos, e)
                await asyncio.sleep(0.3); continue
            tbs = x.get("trail_by_step")   # trailing stop size by profit steps taken: tight early, loose for the last runner
            trail = tbs[min(step, len(tbs) - 1)] if tbs else (x.get("runner_trail_pct", x["trail_pct"]) if runner else x["trail_pct"])
            if pos.get("moonbag"):   # the part kept after a profitable exit: a free ride with a wide stop
                if pct <= pos["peak_pct"] - x.get("moonbag_trail_pct", 50): reason = f"moonbag trailing stop {pct:+.0f}% (peak {pos['peak_pct']:+.0f}%)"
                elif held >= x.get("moonbag_max_hold_min", 240): reason = f"moonbag time limit {pct:+.0f}%"
            elif not runner and pct <= -x["stop_loss_pct"]: reason = f"stop loss {pct:+.0f}%"
            elif runner and pct <= x.get("runner_floor_pct", 0): reason = f"back to entry {pct:+.0f}% (profit already taken)"
            elif (runner or pos["peak_pct"] >= x["trail_after_pct"]) and pct <= pos["peak_pct"] - trail: reason = f"trailing stop {pct:+.0f}% (peak {pos['peak_pct']:+.0f}%)"
            elif held >= (x.get("runner_max_hold_min", x["max_hold_min"]) if runner else x["max_hold_min"]): reason = f"time limit {pct:+.0f}%"
        bag = x.get("moonbag_pct", 0) / 100
        if reason and bag > 0 and not pos.get("moonbag") and q and q != RETRY and pct > 0 \
                and (reason.startswith("trailing stop") or reason.startswith("time limit")):
            # a profitable exit: sell all but a moonbag, which then rides (H4CK 2026-11-20: sold +3%, went on to +236%)
            try:
                await sell(s, mint, reason + f": sold {100 - bag * 100:.0f}%, {bag * 100:.0f}% kept as a moonbag", 1 - bag)
                if mint in state["positions"]: state["positions"][mint]["moonbag"] = True
            except Exception as e: sell_failed(mint, pos, e)
            await asyncio.sleep(0.3); continue
        if reason:
            try: await sell(s, mint, reason)
            except Exception as e: sell_failed(mint, pos, e)
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
        for mint, p in pairs.items():
            if len(state["positions"]) >= cfg["max_open"] or mint in state["positions"]: continue
            ok, metrics = passes(p, (now - state["seen"][mint]["t"]) / 60)
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
            for mint, p in pairs.items():
                if len(state["positions"]) >= cfg["max_open"]: break
                ok, metrics = passes_smart(p)
                if not ok: continue
                tok = p.get("baseToken") or {}
                info = state["seen"].get(mint) or {"sym": (tok.get("symbol") or "?")[:20], "name": (tok.get("name") or "?")[:40], "creator": sm.creators.get(mint)}
                n = len(hot[mint]); f = any(w in follow for w in hot[mint])
                try: await buy(s, mint, info, metrics, p, signal=f"smart money: {n} wallet{'s' if n > 1 else ''}" + (" (one you follow)" if f else ""))
                except Exception as e: log("buy failed", mint, e); event(kind="error", mint=mint, sym=info["sym"], error=str(e)[:200])
    state["last_scan"] = {"t": int(now), "launches": len(state["seen"]), "in_window": len(window), "listed": listed, "fails": dict(_fails)}


# ------------------------------------------------------------------------------------------------ breakouts (older coins)
BREAKOUT = {"enabled": True, "every_sec": 180, "min_age_h": 1, "max_age_days": 30, "min_mcap_usd": 300_000, "max_mcap_usd": 20_000_000,
            "min_liquidity_usd": 50_000, "min_vol_m5_usd": 15_000, "min_vol_accel": 1.5, "min_change_m5_pct": 3, "max_change_m5_pct": 20,
            "min_change_h1_pct": 5, "max_change_h1_pct": 80, "max_change_h24_pct": 300, "min_buy_sell_ratio_m5": 1.2,
            "max_open": 2, "cooldown_h": 12,
            "exits": {"take_profit_steps": [[20, 50], [50, 50]], "stop_loss_pct": 10, "trail_after_pct": 10, "trail_pct": 8,
                      "runner_trail_pct": 15, "max_hold_min": 120, "runner_max_hold_min": 360, "runner_floor_pct": 0,
                      "trail_by_step": [8, 15, 15]}}
_bo = {"last": 0.0, "fails": {}}


def bcfg():
    return {**BREAKOUT, **(cfg.get("breakout") or {})}


def exit_cfg(pos):
    """The exit settings for a position: breakout buys use their own (tighter: older coins move less), the rest cfg."""
    if pos.get("signal") != "breakout": return cfg
    return {**cfg, **BREAKOUT["exits"], **((cfg.get("breakout") or {}).get("exits") or {})}


async def trending_mints(s):
    """Solana coins in GeckoTerminal's trending pools (5 min and 1 h) and its busiest pools: older coins that are moving."""
    out = []
    for path, params in (("trending_pools", {"duration": "5m"}), ("trending_pools", {"duration": "1h"}),
                         ("pools", {"sort": "h24_tx_count_desc"})):
        for attempt in (1, 2):
            try:
                async with s.get(f"https://api.geckoterminal.com/api/v2/networks/solana/{path}", params={**params, "page": "1"}, headers=UA,
                                 timeout=aiohttp.ClientTimeout(total=15)) as r:
                    if r.status == 429 and attempt == 1: await asyncio.sleep(20); continue   # over the shared limit: one retry
                    if r.status != 200: log(f"trending: GeckoTerminal {path} {r.status}"); break
                    for p in (await r.json()).get("data") or []:
                        mint = ((p.get("relationships") or {}).get("base_token") or {}).get("data", {}).get("id", "").removeprefix("solana_")
                        if mint and mint not in out and mint not in STABLE: out.append(mint)
            except Exception as e:
                log("trending:", type(e).__name__, e)
            break
        await asyncio.sleep(5)   # GeckoTerminal's free limit (about 30 a minute) is shared with Yoink's /newpairs
    return out


STABLE = {SOL_MINT, "EPjFWdd5AufqSSqeM2qN1xzybapC8G4wEGGkZwyTDt1v", "Es9vMFrzaCERmJfrF4H2FYD4KCoNkY11McCe8BenwNYB"}


def passes_breakout(p, b):
    """An older coin breaking out: big enough not to be a fresh rug, moving now on volume that's picking up."""
    liq = (p.get("liquidity") or {}).get("usd") or 0
    mcap = p.get("marketCap") or p.get("fdv") or 0
    vol = p.get("volume") or {}
    vol5, vol1h = vol.get("m5") or 0, vol.get("h1") or 0
    tx5 = (p.get("txns") or {}).get("m5") or {}
    buys, sells = tx5.get("buys") or 0, tx5.get("sells") or 0
    ch = p.get("priceChange") or {}
    m5, h1, h24 = ch.get("m5"), ch.get("h1"), ch.get("h24")
    age_h = (time.time() - p["pairCreatedAt"] / 1000) / 3600 if p.get("pairCreatedAt") else None
    checks = {"age": age_h is not None and b["min_age_h"] <= age_h <= b["max_age_days"] * 24,
              "market cap": b["min_mcap_usd"] <= mcap <= b["max_mcap_usd"], "liquidity": liq >= b["min_liquidity_usd"],
              "5m volume": vol5 >= b["min_vol_m5_usd"], "volume picking up": vol5 >= b["min_vol_accel"] * vol1h / 12,
              "5m move": m5 is not None and b["min_change_m5_pct"] <= m5 <= b["max_change_m5_pct"],
              "1h move": h1 is not None and b["min_change_h1_pct"] <= h1 <= b["max_change_h1_pct"],
              "24h move": h24 is None or h24 <= b["max_change_h24_pct"],
              "buy/sell": buys >= b["min_buy_sell_ratio_m5"] * max(sells, 1), "fake pool": pool_sane(liq, mcap, vol5)}
    for k, ok in checks.items():
        if not ok: _bo["fails"][k] = _bo["fails"].get(k, 0) + 1
    return all(checks.values()), {"liq": round(liq), "mcap": round(mcap), "vol5": round(vol5), "buys5": buys, "sells5": sells,
                                  "m5": m5, "h1": h1, "h24": h24, "age_h": round(age_h, 1) if age_h else None}


async def scan_breakouts(s):
    try: await _scan_breakouts(s)
    except Exception as e: log("breakouts:", type(e).__name__, e)


async def _scan_breakouts(s):
    b = bcfg()
    if not b["enabled"] or time.time() - _bo["last"] < b["every_sec"]: return
    if os.path.exists(STOP) or state["day_pnl"] <= -cfg["daily_loss_sol"]: return
    _bo["last"] = time.time()
    open_b = sum(1 for p in state["positions"].values() if p.get("signal") == "breakout")
    if open_b >= b["max_open"] or len(state["positions"]) >= cfg["max_open"]: return
    recent = state.setdefault("breakout_traded", {})
    for m in [m for m, t in recent.items() if time.time() - t > b["cooldown_h"] * 3600]: recent.pop(m)
    mints = [m for m in await trending_mints(s) if m not in state["positions"] and m not in recent]
    _bo["fails"] = {}
    checked = 0
    for i in range(0, len(mints), 30):
        try: pairs = await dex_pairs(s, mints[i:i + 30])
        except Exception as e: log("dex:", e); continue
        for mint, p in pairs.items():
            checked += 1
            if open_b >= b["max_open"] or len(state["positions"]) >= cfg["max_open"]: break
            ok, metrics = passes_breakout(p, b)
            if not ok: continue
            tok = p.get("baseToken") or {}
            info = {"sym": (tok.get("symbol") or "?")[:20], "name": (tok.get("name") or "?")[:40], "creator": None}
            recent[mint] = int(time.time())   # checked or bought: leave it alone for cooldown_h
            try:
                before = len(state["positions"])
                await buy(s, mint, info, metrics, p, signal="breakout")
                if len(state["positions"]) > before: open_b += 1
            except Exception as e: log("buy failed", mint, e); event(kind="error", mint=mint, sym=info["sym"], error=str(e)[:200])
        await asyncio.sleep(1)
    state["last_breakout_scan"] = {"t": int(time.time()), "coins": len(mints), "checked": checked, "fails": dict(_bo["fails"])}


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
                    t = _bo.get("task")
                    if t is None or t.done(): _bo["task"] = asyncio.create_task(scan_breakouts(s))   # own task: its waits don't hold up exits
                    old = sm.expired()
                    if old: await ws_send({"method": "unsubscribeTokenTrade", "keys": old})
                if n % (per_min * 5) == 0: await sync_wallets()
            except Exception as e:
                log("loop:", type(e).__name__, e); traceback.print_exc()
            n += 1
            await asyncio.sleep(cfg.get("exit_check_sec", 5))


if __name__ == "__main__":
    asyncio.run(main())

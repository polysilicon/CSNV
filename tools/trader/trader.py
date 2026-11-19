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

HERE = os.path.dirname(os.path.abspath(__file__))
CONFIG, STATE, EVENTS, STOP = (os.path.join(HERE, f) for f in ("config.json", "state.json", "events.jsonl", "STOP"))
WALLET = os.environ.get("TRADER_WALLET", "/etc/crispytrader/wallet.json")
RPC = os.environ.get("TRADER_RPC", "https://api.mainnet-beta.solana.com")
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


async def watch_creators(keys):
    """Follow these wallets' trades on PumpPortal (used for the creators of coins we hold)."""
    if _ws and keys:
        try: await _ws.send(json.dumps({"method": "subscribeAccountTrade", "keys": list(keys)}))
        except Exception as e: log("watch:", e)


async def feed():
    global _ws
    import websockets
    while True:
        try:
            async with websockets.connect("wss://pumpportal.fun/api/data", open_timeout=20, ping_interval=30) as ws:
                _ws = ws
                await ws.send(json.dumps({"method": "subscribeNewToken"}))
                await watch_creators({p["creator"] for p in state["positions"].values() if p.get("creator")})
                log("feed: connected")
                async for raw in ws:
                    try: m = json.loads(raw)
                    except ValueError: continue
                    mint = m.get("mint")
                    if m.get("txType") == "sell" and mint in state["positions"]:
                        pos = state["positions"][mint]
                        if pos.get("creator") and m.get("traderPublicKey") == pos["creator"]:
                            pos["dev_sold"] = True   # the creator is selling: often the start of a rug; manage() sells
                            log("creator sold", pos["sym"])
                        continue
                    if m.get("txType") == "create" and mint and mint not in state["seen"]:
                        state["seen"][mint] = {"t": int(time.time()), "sym": (m.get("symbol") or "?")[:20], "name": (m.get("name") or "?")[:40],
                                               "creator": m.get("traderPublicKey")}
                    elif mint and "txType" not in m and mint not in state["seen"]:
                        state["seen"][mint] = {"t": int(time.time()), "sym": (m.get("symbol") or "?")[:20], "name": (m.get("name") or "?")[:40],
                                               "creator": m.get("traderPublicKey")}
        except Exception as e:
            log("feed:", type(e).__name__, e)
        _ws = None
        await asyncio.sleep(10)


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


# ------------------------------------------------------------------------------------------------ live trading (Jupiter)
_kp = None
def keypair():
    global _kp
    if _kp is None:
        from solders.keypair import Keypair
        with open(WALLET) as f: _kp = Keypair.from_bytes(bytes(json.load(f)))
    return _kp


async def rpc(s, method, params):
    async with s.post(RPC, json={"jsonrpc": "2.0", "id": 1, "method": method, "params": params}, timeout=aiohttp.ClientTimeout(total=20)) as r:
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


async def buy(s, mint, info, metrics, pair):
    lamports = int(cfg["trade_sol"] * LAMPORTS)
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
    state["positions"][mint] = {"sym": info["sym"], "name": info["name"], "amount": amount, "cost_sol": cfg["trade_sol"], "creator": info.get("creator"),
                                "t": int(time.time()), "peak_pct": 0.0, "liq0": metrics["liq"], "url": pair.get("url"), "sig": sig}
    state["traded"] = (state["traded"] + [mint])[-3000:]
    save()
    event(kind="buy", mint=mint, sym=info["sym"], name=info["name"], sol=cfg["trade_sol"], metrics=metrics, url=pair.get("url"), sig=sig)
    log("BUY", info["sym"], mint, metrics)


async def sell(s, mint, reason):
    pos = state["positions"][mint]
    q = RETRY
    for _ in range(3):
        try: q = await jup_quote(s, mint, SOL_MINT, pos["amount"])
        except Exception: q = RETRY
        if q != RETRY: break
        await asyncio.sleep(1)
    if q == RETRY: log("sell: no quote right now", pos["sym"]); return False
    out_sol = int(q["outAmount"]) / LAMPORTS if q else 0.0
    sig = None
    if live():
        if not q: log("sell: no route for", mint); return False
        sig = await swap(s, q)
    pnl = out_sol - pos["cost_sol"] - (cfg["priority_fee_sol"] * 2 if live() else 0)
    state["positions"].pop(mint)
    if state["day"] != today(): state["day"], state["day_pnl"] = today(), 0.0
    state["day_pnl"] += pnl; state["total_pnl"] += pnl
    state["wins" if pnl > 0 else "losses"] += 1
    state["closed"] = (state["closed"] + [{"mint": mint, "sym": pos["sym"], "cost": pos["cost_sol"], "out": out_sol, "pnl": pnl,
                                            "reason": reason, "t0": pos["t"], "t1": int(time.time())}])[-500:]
    save()
    event(kind="sell", mint=mint, sym=pos["sym"], name=pos["name"], sol_in=pos["cost_sol"], sol_out=round(out_sol, 6), pnl_sol=round(pnl, 6),
          pnl_pct=round(pnl / pos["cost_sol"] * 100, 1), reason=reason, held_min=round((time.time() - pos["t"]) / 60, 1), url=pos.get("url"), sig=sig)
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
        pct = (value / pos["cost_sol"] - 1) * 100
        pos["peak_pct"] = max(pos["peak_pct"], pct)
        held = (time.time() - pos["t"]) / 60
        reason = None
        if not q or q == RETRY:
            if pos.get("dev_sold") or "sellall" in stop or pos["noroute"] >= 3: pass
            else: continue   # a missing quote isn't a price: wait for the next check
        if pos.get("dev_sold"): reason = f"creator sold {pct:+.0f}%" if q and q != RETRY else "creator sold"
        elif not q or q == RETRY: reason = "no route (pool gone?)"
        elif pct >= cfg["take_profit_pct"]: reason = f"take profit {pct:+.0f}%"
        elif pct <= -cfg["stop_loss_pct"]: reason = f"stop loss {pct:+.0f}%"
        elif pos["peak_pct"] >= cfg["trail_after_pct"] and pct <= pos["peak_pct"] - cfg["trail_pct"]: reason = f"trailing stop {pct:+.0f}% (peak {pos['peak_pct']:+.0f}%)"
        elif held >= cfg["max_hold_min"]: reason = f"time limit {pct:+.0f}%"
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
    state["last_scan"] = {"t": int(now), "launches": len(state["seen"]), "in_window": len(window), "listed": listed, "fails": dict(_fails)}


async def main():
    load()
    log(f"Crispy Trader starting in {cfg['mode']} mode" + (" (no wallet: paper only)" if cfg["mode"] == "live" and not os.path.exists(WALLET) else ""))
    asyncio.create_task(feed())
    n = 0
    async with aiohttp.ClientSession() as s:
        while True:
            try:
                with open(CONFIG) as f: cfg.update(json.load(f))
                await manage(s)
                if n % max(1, 60 // cfg.get("exit_check_sec", 5)) == 0: await scan(s)   # entries once a minute, exits every few seconds
            except Exception as e:
                log("loop:", type(e).__name__, e); traceback.print_exc()
            n += 1
            await asyncio.sleep(cfg.get("exit_check_sec", 5))


if __name__ == "__main__":
    asyncio.run(main())

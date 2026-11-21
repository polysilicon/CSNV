"""Wallet finder for Crispy Trader: find wallets worth copying by working back from coins that already ran, instead of
streaming every trade on every new coin.

1. Runners: pump.fun coins (PumpSwap pools) from GeckoTerminal's trending and busiest Solana pools that graduated
   MIN_AGE_H..MAX_AGE_D ago and are worth MIN_FDV+ with real liquidity (MIN_RESERVE).
2. Early buyers: each runner's pool history is paged back to its start (Helius getSignaturesForAddress), and its first
   EARLY_TX trades are parsed (Helius Enhanced Transactions). A count, not a time window: some runners trade thinly
   for their first hour (2026-11-21 test: 48 trades) and the early part of the run is what matters. A wallet that paid the
   fee and received the coin for at least MIN_BUY_SOL is an early buyer.
3. Candidates: early buyers of 2+ runners first, then the biggest single-runner early buyers, up to MAX_CANDIDATES.
4. Vetting: each candidate's own last VET_PAGES x 100 swaps (any coin). Per coin: SOL in, SOL out, first buy, last
   sell; a coin is closed when it sold at least 90% of what it bought. It passes with VET_* thresholds: enough closed
   coins, win rate, profit, a hold long enough for us to copy, not a high-frequency bot.

Read-only: nothing is traded or changed. Results go to walletfinder.json and, as a summary, to events.jsonl
(kind "wallets") so Yoink DMs them. Wallets are added to config "follow_wallets" only when the owner approves.
Run: sudo -u crispytrader venv/bin/python walletfinder.py [--max-runners N]
"""
import json, os, statistics, sys, time, datetime, urllib.request, urllib.error

HERE = os.path.dirname(os.path.abspath(__file__))
OUT = os.path.join(HERE, "walletfinder.json")
EVENTS = os.path.join(HERE, "events.jsonl")
SOL = "So11111111111111111111111111111111111111112"
UA = {"User-Agent": "Mozilla/5.0 (compatible; crispy-trader/1.0)", "Accept": "application/json"}

MIN_AGE_H, MAX_AGE_D, MIN_FDV, MAX_FDV, MIN_RESERVE = 6, 7, 1_000_000, 50_000_000, 50_000
MAX_RUNNERS, MAX_SIG_PAGES = 15, 150
EARLY_TX, MIN_BUY_SOL = 1500, 0.1
MAX_CANDIDATES, VET_PAGES = 50, 3
VET_MIN_COINS, VET_MIN_WINRATE, VET_MIN_PNL, VET_MIN_HOLD_S, VET_MAX_COINS_DAY, VET_MIN_AVG_BUY = 8, 0.5, 1.0, 120, 100, 0.2

KEY = open("/etc/crispytrader/helius.key").read().strip()
RPC = f"https://mainnet.helius-rpc.com/?api-key={KEY}"
API = "https://api-mainnet.helius-rpc.com/v0"
calls = {"rpc": 0, "enhanced": 0, "gecko": 0}


def http(url, body=None, tries=4):
    for i in range(tries):
        try:
            req = urllib.request.Request(url, json.dumps(body).encode() if body is not None else None,
                                         {**UA, "Content-Type": "application/json"} if body is not None else UA)
            return json.load(urllib.request.urlopen(req, timeout=60))
        except urllib.error.HTTPError as e:
            if e.code == 429: time.sleep(5 * (i + 1)); continue
            if i == tries - 1: raise
            time.sleep(2)
        except Exception:
            if i == tries - 1: raise
            time.sleep(2)


def rpc(method, params):
    calls["rpc"] += 1
    d = http(RPC, {"jsonrpc": "2.0", "id": 1, "method": method, "params": params})
    if "error" in d: raise RuntimeError(f"{method}: {d['error']}")
    time.sleep(0.12)
    return d["result"]


def parse(sigs):
    calls["enhanced"] += 1
    out = http(f"{API}/transactions?api-key={KEY}", {"transactions": sigs}) or []
    time.sleep(0.6)
    return out


def wallet_history(w, pages):
    txs, before = [], None
    for _ in range(pages):
        calls["enhanced"] += 1
        page = http(f"{API}/addresses/{w}/transactions?api-key={KEY}&type=SWAP&limit=100" + (f"&before={before}" if before else "")) or []
        time.sleep(0.6)
        if not page: break
        txs += page; before = page[-1]["signature"]
        if len(page) < 100: break
    return txs


def log(*a): print(time.strftime("%H:%M:%S"), *a, flush=True)


# ------------------------------------------------------------------------------------------------ 1. runners
def runners(limit):
    now, found = time.time(), {}
    for path, params in (("trending_pools", "duration=24h"), ("trending_pools", "duration=6h"), ("trending_pools", "duration=1h"),
                         ("dexes/pumpswap/pools", "sort=h24_volume_usd_desc"), ("dexes/pumpswap/pools", "sort=h24_tx_count_desc")):
        for page in (1, 2, 3):
            calls["gecko"] += 1
            try: d = http(f"https://api.geckoterminal.com/api/v2/networks/solana/{path}?page={page}&{params}")
            except Exception as e: log("gecko:", e); break
            for p in d.get("data") or []:
                a = p["attributes"]
                mint = p["relationships"]["base_token"]["data"]["id"].removeprefix("solana_")
                if p["relationships"]["dex"]["data"]["id"] != "pumpswap" or not mint.endswith("pump"): continue
                t0 = datetime.datetime.fromisoformat(a["pool_created_at"].replace("Z", "+00:00")).timestamp()
                fdv, res = float(a.get("fdv_usd") or 0), float(a.get("reserve_in_usd") or 0)
                if not (MIN_AGE_H * 3600 <= now - t0 <= MAX_AGE_D * 86400 and MIN_FDV <= fdv <= MAX_FDV and res >= MIN_RESERVE): continue
                found.setdefault(mint, {"mint": mint, "pool": a["address"], "name": a["name"].split(" / ")[0][:20], "t0": t0, "fdv": fdv})
            time.sleep(2.5)
    return sorted(found.values(), key=lambda r: -r["fdv"])[:limit]


# ------------------------------------------------------------------------------------------------ 2. early buyers
def early_buyers(r):
    """{wallet: SOL spent} for wallets that bought the coin in the pool's first EARLY_TX trades."""
    sigs, before = [], None
    for _ in range(MAX_SIG_PAGES):
        page = rpc("getSignaturesForAddress", [r["pool"], {"limit": 1000, **({"before": before} if before else {})}])
        if not page: break
        sigs += page; before = page[-1]["signature"]
        if len(page) < 1000: break
    else:
        log(f"  {r['name']}: history longer than {MAX_SIG_PAGES}k trades, skipped"); return None
    sigs = [s for s in reversed(sigs) if not s.get("err") and s.get("blockTime")]
    if not sigs: return {}
    early = [s["signature"] for s in sigs][:EARLY_TX]
    log(f"  {r['name']}: {len(sigs):,} trades in its history, parsing the first {len(early):,}")
    buyers = {}
    for i in range(0, len(early), 100):
        for tx in parse(early[i:i + 100]):
            w = tx.get("feePayer")
            got = any(t.get("mint") == r["mint"] and t.get("toUserAccount") == w for t in tx.get("tokenTransfers") or [])
            if not w or not got: continue
            spent = -sum(a.get("nativeBalanceChange", 0) for a in tx.get("accountData") or [] if a.get("account") == w) / 1e9
            if spent >= MIN_BUY_SOL: buyers[w] = buyers.get(w, 0) + spent
    return buyers


# ------------------------------------------------------------------------------------------------ 4. vetting
def vet(w):
    txs = [t for t in wallet_history(w, VET_PAGES) if t.get("feePayer") == w]
    if len(txs) < 5: return None
    coins = {}
    for t in sorted(txs, key=lambda t: t["timestamp"]):
        sol = sum(a.get("nativeBalanceChange", 0) for a in t.get("accountData") or [] if a.get("account") == w) / 1e9
        for tr in t.get("tokenTransfers") or []:
            m = tr.get("mint")
            if not m or m == SOL: continue
            amt = float(tr.get("tokenAmount") or 0)
            if tr.get("toUserAccount") == w: d = amt
            elif tr.get("fromUserAccount") == w: d = -amt
            else: continue
            c = coins.setdefault(m, {"in": 0.0, "out": 0.0, "bought": 0.0, "sold": 0.0, "t0": t["timestamp"], "t1": t["timestamp"]})
            if d > 0: c["bought"] += d; c["in"] += max(0.0, -sol)
            else: c["sold"] += -d; c["out"] += max(0.0, sol); c["t1"] = t["timestamp"]
            break   # one coin per swap
    closed = [c for c in coins.values() if c["bought"] > 0 and c["sold"] >= 0.9 * c["bought"] and c["in"] > 0]
    span_d = max(1.0, (txs[0]["timestamp"] - txs[-1]["timestamp"]) / 86400)
    if not closed: return {"wallet": w, "coins": 0, "swaps": len(txs)}
    pnl = sum(c["out"] - c["in"] for c in closed)
    wins = sum(1 for c in closed if c["out"] > c["in"])
    return {"wallet": w, "swaps": len(txs), "coins": len(closed), "wins": wins, "winrate": round(wins / len(closed), 2),
            "pnl_sol": round(pnl, 2), "median_hold_s": int(statistics.median(c["t1"] - c["t0"] for c in closed)),
            "coins_per_day": round(len(coins) / span_d, 1), "avg_buy_sol": round(statistics.mean(c["in"] for c in closed), 2),
            "days": round(span_d, 1)}


def passes(v):
    return (v and v.get("coins", 0) >= VET_MIN_COINS and v["winrate"] >= VET_MIN_WINRATE and v["pnl_sol"] >= VET_MIN_PNL
            and v["median_hold_s"] >= VET_MIN_HOLD_S and v["coins_per_day"] <= VET_MAX_COINS_DAY and v["avg_buy_sol"] >= VET_MIN_AVG_BUY)


def main():
    lim = int(sys.argv[sys.argv.index("--max-runners") + 1]) if "--max-runners" in sys.argv else MAX_RUNNERS
    rs = runners(lim)
    log(f"{len(rs)} runners:", ", ".join(f"{r['name']} (${r['fdv'] / 1e6:.1f}M)" for r in rs))
    seen = {}   # wallet -> {coin: sol}
    used = []
    for r in rs:
        try: b = early_buyers(r)
        except Exception as e: log(f"  {r['name']}: {type(e).__name__} {e}"); continue
        if b is None: continue
        used.append(r["name"])
        for w, sol in b.items(): seen.setdefault(w, {})[r["name"]] = round(sol, 2)
    multi = sorted((w for w in seen if len(seen[w]) >= 2), key=lambda w: (-len(seen[w]), -sum(seen[w].values())))
    single = sorted((w for w in seen if len(seen[w]) == 1), key=lambda w: -sum(seen[w].values()))
    cands = (multi + single)[:MAX_CANDIDATES]
    log(f"{len(seen):,} early buyers across {len(used)} runners; {len(multi)} bought 2+ runners early; vetting {len(cands)}")
    results = []
    for i, w in enumerate(cands, 1):
        try: v = vet(w)
        except Exception as e: log(f"  vet {w[:6]}: {e}"); continue
        if not v: continue
        v["early_on"] = seen[w]; v["passes"] = bool(passes(v))
        results.append(v)
        log(f"  {i}/{len(cands)} {w[:6]}: " + (f"{v['wins']}/{v['coins']} wins, {v['pnl_sol']:+} SOL, hold {v['median_hold_s']}s, {v['coins_per_day']}/day" if v.get("coins") else f"no closed coins in {v['swaps']} swaps"))
        if v["passes"]: log(f"  PASS {w}: {v['wins']}/{v['coins']} wins, {v['pnl_sol']:+} SOL, hold {v['median_hold_s'] // 60} min, early on {list(seen[w])}")
    good = sorted((v for v in results if v["passes"]), key=lambda v: -v["pnl_sol"])
    report = {"t": int(time.time()), "runners": used, "early_buyers": len(seen), "multi": len(multi), "vetted": len(results),
              "passed": good, "near": sorted((v for v in results if not v["passes"] and v.get("coins", 0) >= VET_MIN_COINS),
                                            key=lambda v: -v.get("pnl_sol", 0))[:10], "calls": calls}
    with open(OUT, "w") as f: json.dump(report, f, indent=1)
    with open(EVENTS, "a") as f:
        f.write(json.dumps({"kind": "wallets", "t": int(time.time()), "runners": len(used), "vetted": len(results),
                            "passed": [{k: v[k] for k in ("wallet", "coins", "wins", "pnl_sol", "median_hold_s", "coins_per_day")} for v in good[:10]],
                            "mode": "info"}) + "\n")
    log(f"done: {len(good)} wallets pass; API calls {calls}")


if __name__ == "__main__":
    main()

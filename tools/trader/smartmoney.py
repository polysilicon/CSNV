"""Smart-money tracking for Crispy Trader: find wallets that keep making money on new pump.fun coins, and treat their
buys as a signal.

How wallets are scored: the trader subscribes to every trade on each new coin for its first TRACK_MIN minutes
(PumpPortal subscribeTokenTrade, on the trader's one connection). For every wallet and coin it adds up SOL in (buys)
and SOL out (sells); when the wallet's balance of that coin reaches zero, the coin is closed for that wallet: a win if
it took out more than it put in. A wallet is "smart" with at least MIN_COINS closed coins, at least MIN_PNL SOL profit
and a MIN_WINRATE win rate, and it must not look like a sniper bot (more than MAX_COINS_PER_DAY coins a day, or an
average hold under MIN_HOLD_S seconds: those are faster than we can ever copy). Coin creators' own trades don't count.

The signal: smart wallets (and any wallet in config "follow_wallets") are watched live (subscribeAccountTrade). Each
buy of at least MIN_BUY_SOL is recorded; trader.py treats a coin with buys from cfg "smart_min_wallets" smart wallets
(or one followed wallet) in the last cfg "smart_window_min" minutes as a candidate, still subject to its safety checks.

State: wallets.json (wallet stats, kept to the most useful MAX_WALLETS), saved every few minutes.
"""
import json, os, time

HERE = os.path.dirname(os.path.abspath(__file__))
FILE = os.path.join(HERE, "wallets.json")
TRACK_MIN = 30
MIN_COINS, MIN_PNL, MIN_WINRATE = 5, 1.0, 0.55
MAX_COINS_PER_DAY, MIN_HOLD_S = 150, 45
MIN_BUY_SOL = 0.2
MAX_WALLETS, TOP_SMART = 20000, 60

wallets = {}      # wallet -> {"open": {mint: [in, out, first_t]}, "n", "wins", "pnl", "hold", "first", "last"}
creators = {}     # mint -> creator wallet (their trades on their own coin are ignored)
tracked = {}      # mint -> time we started following its trades
signals = {}      # mint -> {wallet: time of their buy}
smart = set()
stats = {"trades": 0, "since": time.time()}


def load():
    global wallets
    try:
        with open(FILE) as f: wallets = json.load(f).get("wallets", {})
    except (OSError, ValueError): wallets = {}
    rescore()


def save():
    prune()
    tmp = FILE + ".tmp"
    with open(tmp, "w") as f: json.dump({"wallets": wallets, "smart": sorted(smart), "at": int(time.time())}, f, separators=(",", ":"))
    os.replace(tmp, FILE)


def prune():
    """Keep the wallets with the most history; drop one-off wallets that haven't traded for a day."""
    now = time.time()
    for w in [w for w, s in wallets.items() if s.get("n", 0) == 0 and not s.get("open") and now - s.get("last", 0) > 86400]: wallets.pop(w)
    if len(wallets) > MAX_WALLETS:
        keep = sorted(wallets, key=lambda w: (w in smart, wallets[w].get("n", 0), wallets[w].get("last", 0)), reverse=True)[:MAX_WALLETS]
        for w in set(wallets) - set(keep): wallets.pop(w)


def score(s):
    n = s.get("n", 0)
    if n < MIN_COINS: return None
    days = max(1.0, (s.get("last", 0) - s.get("first", 0)) / 86400)
    if n / days > MAX_COINS_PER_DAY or s.get("hold", 0) / n < MIN_HOLD_S: return None   # a bot
    if s.get("pnl", 0) < MIN_PNL or s.get("wins", 0) / n < MIN_WINRATE: return None
    return s["pnl"]


def rescore():
    """The TOP_SMART wallets by profit among those that pass. Returns the set (to subscribe to)."""
    ranked = sorted(((score(s), w) for w, s in wallets.items() if score(s) is not None), reverse=True)[:TOP_SMART]
    smart.clear(); smart.update(w for _, w in ranked)
    return set(smart)


def on_create(mint, creator):
    tracked[mint] = time.time()
    if creator: creators[mint] = creator


def expired():
    """Coins we've followed for TRACK_MIN minutes: stop following them (the caller unsubscribes)."""
    now = time.time()
    old = [m for m, t in tracked.items() if now - t > TRACK_MIN * 60]
    for m in old: tracked.pop(m, None); creators.pop(m, None)
    return old


def on_trade(m, follow=()):
    """A PumpPortal trade message. Updates wallet stats, and records smart/followed buys as signals."""
    w, mint, kind = m.get("traderPublicKey"), m.get("mint"), m.get("txType")
    if not w or not mint or kind not in ("buy", "sell"): return
    stats["trades"] += 1
    try: sol = float(m.get("solAmount") or 0)
    except (TypeError, ValueError): sol = 0.0
    now = time.time()
    if kind == "buy" and sol >= MIN_BUY_SOL and (w in smart or w in follow):
        signals.setdefault(mint, {})[w] = now
    if mint not in tracked or creators.get(mint) == w: return
    s = wallets.setdefault(w, {"open": {}, "n": 0, "wins": 0, "pnl": 0.0, "hold": 0.0, "first": now, "last": now})
    s["last"] = now
    pos = s["open"].setdefault(mint, [0.0, 0.0, now])
    if kind == "buy": pos[0] += sol
    else: pos[1] += sol
    bal = m.get("newTokenBalance")
    try: bal = float(bal) if bal is not None else None
    except (TypeError, ValueError): bal = None
    if kind == "sell" and bal is not None and bal <= 1 and pos[0] > 0:   # sold out of this coin: close it
        s["open"].pop(mint)
        pnl = pos[1] - pos[0]
        s["n"] += 1; s["pnl"] += pnl; s["hold"] += now - pos[2]
        if pnl > 0: s["wins"] += 1


def hot(min_wallets, window_min, follow=()):
    """{mint: [wallets]} with enough recent smart buys (or one followed wallet's buy)."""
    now, out = time.time(), {}
    for mint, buys in list(signals.items()):
        recent = {w: t for w, t in buys.items() if now - t <= window_min * 60}
        if not recent: signals.pop(mint); continue
        signals[mint] = recent
        if len(recent) >= min_wallets or any(w in follow for w in recent): out[mint] = sorted(recent)
    return out


def top(n=5):
    return sorted(((wallets[w].get("pnl", 0), w, wallets[w].get("n", 0), wallets[w].get("wins", 0)) for w in smart if w in wallets), reverse=True)[:n]

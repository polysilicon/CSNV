# Crispy Trader

Automated Solana memecoin trader (new-launch momentum). **Paper mode by default.** It runs as its own service, apart
from the Discord bot, so the wallet key never sits in Yoink.

- Host: `/opt/crispytrader` (service `crispytrader`, user `crispytrader`, venv with aiohttp, websockets, solders).
  Wallet: `/etc/crispytrader/wallet.json` (mode 600, readable only by `crispytrader`), made by `wallet.py`.
  Address: `8ThgGCXFsdg8b9GGffFA19hHVzMqvULJ4wcWn9rPmq2Q`. `wallet.py balance` shows its SOL.
- Strategy and limits: `config.json` (re-read every 15 s, no restart needed). Defaults: 0.2 SOL a trade, 5 open
  positions, no new buys after losing 0.5 SOL in a UTC day; entries 3-30 min after launch with liquidity >= $8K, market
  cap $15K-$300K, 5-min volume >= $5K, buys >= 1.3x sells, 5-min move +5..+60%, 1-hour move <= +400%; exits at +60%
  take profit, -25% stop loss, a 20% trailing stop once up 30%, 45 min max hold, or no route left (rug).
- How it trades: see the docstring of `trader.py`. Paper mode prices every buy and sell with a real Jupiter quote (the
  one a live trade would use), so fees and price impact are counted. `"mode": "live"` signs and sends those swaps from
  the wallet; it does nothing live while the wallet is missing.
- Anti-rug (2026-11-19, after two paper trades lost 96-97% to rugs right after graduation): coins are scored on the
  pair with real liquidity (never a dead pump.fun bonding-curve pair), coins that graduated less than
  `skip_after_graduation_min` (15) ago are skipped, the creator's wallet is watched on PumpPortal and any sell by
  them exits at once, and open positions are re-priced every `exit_check_sec` (5) s. A failed quote (rate limit) is
  never read as a price; "no route" only sells after 3 checks in a row. A rug that drains the pool in one transaction
  can still beat any stop loss: position size is the real limit.
- Controls: a file named `STOP` in `/opt/crispytrader` pauses buying; `echo sellall > STOP` also sells everything.
- Reports: `events.jsonl` (every buy, sell, error) and `state.json` (positions, profit, last scan's filter results).
  Yoink (`tools/discordbot/traderfeed.py`) DMs each event to the owner and has `/trader` (staff).

Going live (only when paper results justify it): fund the wallet with a little SOL (trade size x positions + fees),
preferably set `TRADER_RPC` to a private RPC endpoint (the public one rate-limits sending), then set `"mode": "live"`.
Not financial advice: most new memecoins go to zero, and rug pulls are common.

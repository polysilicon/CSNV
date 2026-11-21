# Crispy Trader

Automated Solana memecoin trader (new-launch momentum). **Paper mode by default.** It runs as its own service, apart
from the Discord bot, so the wallet key never sits in Yoink.

- Host: `/opt/crispytrader` (service `crispytrader`, user `crispytrader`, venv with aiohttp, websockets, solders).
  Wallet: `/etc/crispytrader/wallet.json` (mode 600, readable only by `crispytrader`), made by `wallet.py`.
  Address: `8ThgGCXFsdg8b9GGffFA19hHVzMqvULJ4wcWn9rPmq2Q`. `wallet.py balance` shows its SOL.
- Strategy and limits: `config.json` (re-read every 15 s, no restart needed). Defaults: 0.2 SOL a trade, 5 open
  positions, no new buys after losing 0.5 SOL in a UTC day; entries 3-30 min after launch with liquidity >= $8K, market
  cap $15K-$300K, 5-min volume >= $5K, buys >= 1.3x sells, 5-min move +5..+60%, 1-hour move <= +400%; exits: -25% stop loss, a 20% trailing stop once up 30%, 45 min max hold, or no route left (rug). Profits are taken in steps
  (`take_profit_steps`): sell 50% at +60%, half the rest at +200%, and the last part rides with a 35% trailing stop
  (`runner_trail_pct`) for up to 4 hours, sold if it falls back to the entry price (`runner_floor_pct`).
- How it trades: see the docstring of `trader.py`. Paper mode prices every buy and sell with a real Jupiter quote (the
  one a live trade would use), so fees and price impact are counted. `"mode": "live"` signs and sends those swaps from
  the wallet; it does nothing live while the wallet is missing.
- Anti-rug (2026-11-19, after two paper trades lost 96-97% to rugs right after graduation): coins are scored on the
  pair with real liquidity (never a dead pump.fun bonding-curve pair). Fresh pools are allowed (a pool-age skip
  cost as many winners as rugs). Instead, before a buy: fake pools (market cap under `min_mcap_to_liq` x liquidity)
  and wash-traded ones (5 min volume over `max_vol5_to_liq` x liquidity) are skipped; so are coins with under
  `min_holders` holders, over `max_buys_per_holder` 5 min buys per holder, or with the 10 biggest non-pool wallets
  holding over `max_top10_pct` of the supply (Helius; holders and top10 are saved with each buy for tuning). The
  creator's wallet is watched and any sell by them exits at once, and open positions are re-priced every `exit_check_sec` (5) s. A failed quote (rate limit) is
  never read as a price; "no route" only sells after 3 checks in a row. A rug that drains the pool in one transaction
  can still beat any stop loss: position size is the real limit.
- Breakouts (older coins, `"breakout"` in config): every 3 min, GeckoTerminal's trending and busiest Solana pools are
  checked for coins 1 h to `max_age_days` (30) old, $300K-$20M market cap, $50K+ liquidity, up 3-20% in 5 min and 5-80%
  in 1 h on 5-min volume at least 1.5x the hour's average, more buys than sells. Same rug and holder checks. Its own
  exits (`breakout.exits`: take profit +20% then +50%, stop -10%, trail 8%, 2 h limit), at most `max_open` (2) at a
  time, and a coin can be bought again after `cooldown_h` (12). Shown as "breakout" in /trader.
- Live trading safeguards: cost and proceeds are the wallet's real SOL change (fees and rent included); sells allow
  `sell_slippage_bps` (10%); an emptied token account is closed to get its ~0.002 SOL rent back; a coin with no
  route at all is written off so it doesn't hold a slot; a failed sell retries with a pause and DMs only now and then;
  positions opened on paper stay paper after switching to live.
- Entries are confirmed (`confirm_entries`): a momentum coin is bought only if it still passes on the next scan, ~1 min
  later, and hasn't dropped more than `confirm_max_drop_pct` (3%). A 5-min jump over `bounce_max_m5_pct` (25%) while the
  coin is down on the hour is skipped as a dead-cat bounce. Strategies in `paper_strategies` (breakout) trade on paper
  even in live mode and don't count toward the money stats or the daily stop.
- Fast exits (`pool_watch`): a Helius websocket follows the reserve accounts of each held coin's pool (PumpSwap and
  others whose reserves the pool account owns). A move of `pool_wake_pct` (4%) or a drain of `pool_drain_pct` (25%) of
  its SOL wakes the exit check at once instead of at the next 5 s check. Entry scans run in their own task.
- Moonbag: when a trailing stop or time limit would close a trade in profit, `moonbag_pct` (25) of it is kept and rides
  with no stop loss, only a `moonbag_trail_pct` (50) point trailing stop and a `moonbag_max_hold_min` (240) limit.
- Smart money (`smartmoney.py`): follows every trade on new coins for 30 min, keeps a profit-and-loss per wallet, and
  ranks wallets that keep closing coins in profit (5+ coins, +1 SOL, 55%+ wins, not a sniper bot, not the creator).
  When 2+ smart wallets (or one wallet in `follow_wallets`) buy a coin within 10 min, it's a candidate if it passes
  the safety half of the filters. **Needs a PumpPortal API key funded with 0.02 SOL** in
  `/etc/crispytrader/pumpportal.key` (PumpPortal only streams per-coin and per-wallet trades with one); without it
  the trader skips wallet tracking and the creator-sell exit (which uses the same feed).
- Feeds and keys (2026-11-20): launches come from PumpPortal; while it's unreachable, from GeckoTerminal's new Solana
  pools every minute (`gecko_launches`, graduated/DEX pools only). With a Helius key (`/etc/crispytrader/helius.key`)
  the trader uses Helius as its RPC (live trading) and watches the creator of every coin it holds with `logsSubscribe`
  (free-plan WebSocket): a sell in their logs plus a lower balance of our coin triggers the creator-sell exit, without
  PumpPortal. Keys are given in Discord with `/tradersetkey` (staff, ephemeral): Yoink drops them in `inbox/` (mode
  1730, Yoink can write but not list or read) and the trader moves them into `/etc/crispytrader` (600) within seconds.
- RugCheck (2026-11-20): right before any buy, RugCheck's full report must show no "danger" risk from `rug_risks`
  (mint or freeze authority, single holder or top-10 concentration, copycat), and the pool we trade (DexScreener's main
  pair) must have at least `min_lp_locked_pct` (30) of its liquidity locked or burned. RugCheck's own "LP unlocked"
  flag is ignored: it averages all pools, so an empty unlocked side pool flagged coins whose real pool was 100% locked.
  If RugCheck can't be reached the coin is skipped.
  Skips are listed in `state.json` `rug_skips` and counted in `/trader`'s last scan.
- Controls: a file named `STOP` in `/opt/crispytrader` pauses buying; `echo sellall > STOP` also sells everything.
- Reports: `events.jsonl` (every buy, sell, error) and `state.json` (positions, profit, last scan's filter results).
  Yoink (`tools/discordbot/traderfeed.py`) DMs each event to the owner and has `/trader` (staff).

Going live (only when paper results justify it): fund the wallet with a little SOL (trade size x positions + fees),
preferably set `TRADER_RPC` to a private RPC endpoint (the public one rate-limits sending), then set `"mode": "live"`.
Not financial advice: most new memecoins go to zero, and rug pulls are common.

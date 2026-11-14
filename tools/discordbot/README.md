# Discord bot extras

Modules for the Crispy Discord bot (`/opt/crispybot` on the host, service `crispybot`). `bot.py` itself lives only on
the host (it reads tokens from `/etc/crispybot.env`); these two modules are copied next to it, and `bot.py`'s
`on_message` starts `extras()` as its own task, so neither can slow down or break the Minecraft chat bridge.

- `medialinks.py`: a TikTok, Twitter/X or Instagram post link gets a reply with the video (yt-dlp, one MP4 with
  sound under the server's upload limit and 10 minutes), or else the same post on an embed-fixing mirror that plays
  inline (tnktok / fxtwitter / fixupx / kkinstagram). Up to 2 links a message, 8 s cooldown per user.
  Needs `yt-dlp[default,curl-cffi]` in the bot's venv (TikTok needs the browser impersonation).
- `tickers.py`: `$AAPL` / `$BTC` / `$EUR` (up to 3 a message): price card with the day's change, range and chart. Currencies (ISO codes) from Yahoo FX against the dollar both ways; well-known coins and stocks from Yahoo; smaller coins from CoinGecko (exact symbol, largest market cap).
  the day, from Yahoo Finance's public chart data (no key). Well-known coins resolve as crypto first.

- `polymarket.py`: a polymarket.com/event link gets an odds card (each outcome's implied chance as a bar, volume,
  end date); `/polymarket <search>` finds the best open market (Gamma API, no key).

- `dex.py`: a Solana or 0x (EVM) contract address, in text or in a token-site link, gets a DexScreener card: price,
  1 h / 24 h change, liquidity, volume, market cap, pair age, and a warning for thin or brand-new tokens. Non-tokens: no reply.

- `newpairs.py`: `/newpairs <topic>` searches every coin launched in the last 24 h by name/symbol (newest 10, live
  market cap and liquidity from DexScreener, a risk warning). Feeds: pump.fun launches from PumpPortal's websocket
  (needs `websockets` in the venv) and new Solana/Base/Ethereum pools from GeckoTerminal (polled, which includes
  pump.fun's own pools). Each search also asks DexScreener's and GeckoTerminal's (Solana) search for coins under 24 h
  old, so results don't depend on how long the bot has been listening. GeckoTerminal's free rate limit is small: the
  poller takes one page a round to leave room. Pump.fun's site API is behind bot protection and isn't used. The list is kept in
  `newpairs.json` so restarts don't empty it. Wired in bot.py with `newpairs.register(...)`, which starts the feeds
  from `setup_hook`.

- `scans.py`: ticker and contract-address cards say "Scanned by <name>" (with avatar). The first scan of each thing
  in the server is saved (`scans.json`: who, price, time); later cards add "Since first scan": % change (and x-multiple
  past 2x / 0.5x), who called it first and when.

`/console` was removed from bot.py on 2026-11-14 (backup `bot.py.bak-console`); `/mc` with its allowlist remains.

Deploy: copy the modules into `/opt/crispybot`, `systemctl restart crispybot`. Backup of the pre-change bot:
`bot.py.bak-media-tickers`. Keep yt-dlp current (`/opt/crispybot/venv/bin/pip install -U "yt-dlp[default,curl-cffi]"`):
the sites change often and old versions stop working.

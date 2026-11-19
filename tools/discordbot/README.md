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

- `scans.py`: ticker, contract-address and Polymarket cards say "Scanned by <name>" (with avatar). The first scan of each thing
  in the server is saved (`scans.json`: who, price, time); later cards add "Since first scan": % change (and x-multiple
  past 2x / 0.5x; for Polymarket each outcome's odds then -> now in points), who called it first and when.

- `votes_daily.py` (daily post off for now: `DAILY_POST = False`): at 00:03 UTC a vote card in General Chat (yesterday's is deleted): the lobby's vote links
  (featured first), our minecraftservers.org rank and how many votes page 1 of its Anarchy list needs, top voters and
  streaks (read from the lobby's `votes.json`). `/vote` shows it on demand.

- Tweets (`medialinks.py`): an X/Twitter post without a video gets a tweet card from FxTwitter's public API (author,
  text, first photo, quoted tweet, counts, time); video tweets work as before. Any `$TICKER` in a tweet's text gets the
  ticker chart card (`tickers.post_cards`, credited to whoever shared it).

- `gametickers.py`: `$TICKER` in Minecraft chat (any bridged server) gets a one-line price reply on that server (price, day
  change, change since the first scan; hover for the range, click for the chart). Same lookup and scan history as
  Discord; credited to the linked Discord account if there is one. 6 s cooldown per player, 2 symbols a line.

- `faq.py` + `faq_extra.toml`: `/ask <question>`, mentioning @Yoink with a question, or `!ask <question>` (in Discord, or in
  game chat on any bridged server, answered to that player by tellraw) answers questions about the servers, with no
  language model. Answers come from the website: every FAQPage on www.crispyanarchy.net (the /faq/ page and the mode
  pages' question sections, `marketing/site/build.py`) is read every 6 h, so a question added to the site is one Yoink
  answers after the next refresh or `/askadmin reload` (the last good copy is kept in `faq_site.json`).
  `faq_extra.toml` adds bot-only answers, live ones (who's online, your vote points/streak from the lobby's
  `votes.json`, your Discord link) and extra phrasings for site questions; edit it on the host, then `/askadmin reload`.
  Matching blends a small sentence-embedding model (fastembed + BAAI/bge-small-en-v1.5 in the venv, model cached in
  `.fastembed/`; 2 threads, ~5 ms a question, the bot is ~360 MB with it) with keyword scores; without fastembed it
  falls back to keywords. Questions it can't answer confidently go to `faq_misses.jsonl` (`/askadmin misses`).
  Telling people about it: a "type !ask <question>" tip in game chat every 75 min on servers with players on (rotating
  examples, click to start), and when someone asks a question in game or Discord that Yoink can answer well (score >= 0.80)
  it suggests !ask to them, at most once a day per player / once a week per Discord user (`faq_hints.json`).
  `/askadmin status | test <q>` for staff. Tests: `python3 faq_eval.py [faq_tests_holdout.txt] [--words]`
  (2026-11-16: 97% on the tuning set, 88% on the held-out set; 71% held-out with keywords only).

- `dailyword.py`: the lobby's Daily Word (repo `dailyword/`, a five-letter word in six tries). Once a minute it makes sure
  the lobby plugin has today's word (America/Chicago days): on a new day it picks a random unused word and writes
  `plugins/DailyWord/word.json`, `valid.txt` and `answers.txt` on the lobby. Lists (cached in `dailyword_lists.json`,
  refreshed monthly): common no-swears US-English words kept only if they're lowercase dictionary words, minus the censor
  list and `BLOCK`, plus Minecraft words about 1 day in 5; guesses from dwyl/english-words. Used words in
  `dailyword_state.json`. `/dailyword`: today's counts (never the word), yesterday's word and results, streaks.

- `pricealerts.py`: anything scanned in a channel ($TICKER and contract-address cards) is watched for 14 days after its
  latest scan; every 15 min its price is checked again, and a move of ±5% (stocks, major coins, currencies) or ±20%
  (coins under a $1B market cap and DEX tokens) since the scan or the last alert posts a card in that channel (at most
  one an hour per item). Staff: `/pricealerts on|off|list`. State: `pricealerts.json`.

`/console` was removed from bot.py on 2026-11-14 (backup `bot.py.bak-console`); `/mc` with its allowlist remains.

Deploy: copy the modules into `/opt/crispybot`, `systemctl restart crispybot`. Backup of the pre-change bot:
`bot.py.bak-media-tickers` (before /ask: `bot.py.bak-faq`). Keep yt-dlp current (`/opt/crispybot/venv/bin/pip install -U "yt-dlp[default,curl-cffi]"`):
the sites change often and old versions stop working.

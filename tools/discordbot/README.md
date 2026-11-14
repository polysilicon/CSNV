# Discord bot extras

Modules for the Crispy Discord bot (`/opt/crispybot` on the host, service `crispybot`). `bot.py` itself lives only on
the host (it reads tokens from `/etc/crispybot.env`); these two modules are copied next to it, and `bot.py`'s
`on_message` starts `extras()` as its own task, so neither can slow down or break the Minecraft chat bridge.

- `medialinks.py`: a TikTok, Twitter/X or Instagram post link gets a reply with the video (yt-dlp, one MP4 with
  sound under the server's upload limit and 10 minutes), or else the same post on an embed-fixing mirror that plays
  inline (tnktok / fxtwitter / fixupx / kkinstagram). Up to 2 links a message, 8 s cooldown per user.
  Needs `yt-dlp[default,curl-cffi]` in the bot's venv (TikTok needs the browser impersonation).
- `tickers.py`: `$AAPL` / `$BTC` (up to 3 a message) gets a card with price, day change and range, and a chart of
  the day, from Yahoo Finance's public chart data (no key). Well-known coins resolve as crypto first.

Deploy: copy both into `/opt/crispybot`, `systemctl restart crispybot`. Backup of the pre-change bot:
`bot.py.bak-media-tickers`. Keep yt-dlp current (`/opt/crispybot/venv/bin/pip install -U "yt-dlp[default,curl-cffi]"`):
the sites change often and old versions stop working.

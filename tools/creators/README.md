# Creator outreach

Finds small and mid-size Minecraft creators (1,000–150,000 subscribers, uploaded in the last 30 days, mostly
Minecraft), writes a personal pitch for each, and tracks who's been contacted. **It never sends anything.** You read
each draft and send it yourself, one at a time, and mark it sent, so nobody is contacted twice and nobody gets more
than one follow-up.

```
python3 creators.py find                      # YouTube: search, filter, score (needs the API key, below)
python3 creators.py add tiktok @handle --name "Their Name" --video "a recent video title" --contact "TikTok DM"
python3 creators.py draft                     # email + short DM for every new creator
python3 creators.py list                      # the tracker, best first
python3 creators.py mark yt:UC... sent        # then replied / yes / no / ignore
python3 creators.py export                    # data/outreach.md (drafts to copy) and data/creators.csv
```

- **YouTube:** official YouTube Data API v3. Add the key as a network secret for `www.googleapis.com` with
  header `X-Goog-Api-Key` (environment settings), or set `YOUTUBE_API_KEY`. `find` uses about 2,100 of the
  10,000 free daily quota units.
- **TikTok:** no public search API for this (the Research API is academic-only; scraping breaks TikTok's terms), so
  add TikTok creators by hand; their draft is a DM.
- **The pitch:** matches each creator to the gamemode their videos are about (anarchy, skyblock, pvp, extraction),
  mentions a recent video, and offers the animated [Creator] tag (`/vote grant <player> tag:creator` in the lobby),
  free cosmetics, early access to new modes and a private session for their viewers. Wording follows the website.
- **Contact details:** only what creators publish for business (an email in their channel description, links they
  list). Data lives in `data/`, which is gitignored.

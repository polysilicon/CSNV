#!/usr/bin/env python3
"""Creator outreach for the Crispy network: find small and mid-size Minecraft creators, draft a personal pitch for
each, and track who has been contacted. Nothing is ever sent: you read each draft and send it yourself, one at a time.

    python3 creators.py find [--days 45] [--max-searches 20]   YouTube: search, score and store new channels
    python3 creators.py add <platform> <handle> [--name N] [--subs N] [--video "title"] [--modes anarchy,skyblock]
                                                              [--contact "email or where to DM"] [--notes "..."]
    python3 creators.py draft                                  write drafts for creators who don't have one yet
    python3 creators.py list [--status new]                    the tracker, best first
    python3 creators.py mark <id> <status> [--notes "..."]     drafted -> sent -> replied -> yes / no / ignore
    python3 creators.py export                                 data/outreach.md and data/creators.csv

Data stays in tools/creators/data/ (gitignored: it holds creators' public contact details).

YouTube discovery uses the official YouTube Data API v3. The key comes from YOUTUBE_API_KEY, or from the session's
network secret for www.googleapis.com (header X-Goog-Api-Key), which the proxy adds to the request. A search costs 100
of the free 10,000 daily quota units; channel and video lookups cost 1 each, so --max-searches 20 uses about 2,100.
TikTok has no public search API for this (its Research API is for academics, and scraping breaks its terms), so
TikTok creators are added by hand with `add tiktok @handle`; their draft is a short DM.

Contact details: only what a creator publishes for business (an email in their channel description, links they list).
YouTube's own "business email" button sits behind a captcha for a reason: open it yourself when you send.
"""
import argparse, csv, datetime as dt, json, os, re, sys, urllib.parse, urllib.request

HERE = os.path.dirname(os.path.abspath(__file__))
DATA = os.path.join(HERE, "data")
DB = os.path.join(DATA, "creators.json")
API = "https://www.googleapis.com/youtube/v3/"

SENDER = "lbxd"                       # sign-off on every draft
NETWORK = "Crispy Network"
SITE = "https://www.crispyanarchy.net"
DISCORD = "https://discord.gg/hF2bQgU"
SUBS_MIN, SUBS_MAX = 1_000, 150_000   # small to mid-size
ACTIVE_DAYS = 30                      # last upload within this many days
MC_SHARE_MIN = 0.4                    # at least this share of recent uploads is Minecraft
STATUSES = ["new", "drafted", "sent", "replied", "yes", "no", "ignore"]

# what each gamemode is, in the words the website uses (marketing/site/build.py); the address each pitch points to
MODES = {
    "anarchy": {"name": "Crispy Anarchy", "addr": "anarchy.crispyanarchy.net", "page": "/anarchy/",
                "hook": "a no-rules anarchy world that hasn't been reset since 2020, with 193 custom enchantments, cyberpunk implants and a hidden black market",
                "words": ["anarchy", "2b2t", "no rules", "griefing", "base hunt", "spawn"]},
    "skyblock": {"name": "Crispy Skyblock", "addr": "skyblock.crispyanarchy.net", "page": "/skyblock/",
                 "hook": "Skyblock with 5 skills, 68 collections, 43 minions, pets and a player Bazaar, and no pay-to-win",
                 "words": ["skyblock", "one block", "oneblock", "minion", "island", "bazaar"]},
    # pvp and extraction have no DNS records for their own address yet: point to the main one and the lobby
    "pvp": {"name": "Multiverse", "addr": "crispyanarchy.net (pick Multiverse in the lobby)", "page": "/pvp/",
            "hook": "a PvP server with 36 playable characters, kit PvP, ranked duels and co-op zombie waves",
            "words": ["pvp", "duel", "kit", "bedwars", "zombies", "combat", "practice"]},
    "extraction": {"name": "Extraction Zone", "addr": "crispyanarchy.net (pick Extraction Zone in the lobby)", "page": "/extraction-zone/",
                   "hook": "an extraction shooter in a ruined city: loot, fight armed raiders and other players, and get out alive before the timer ends",
                   "words": ["extraction", "guns", "gun", "shooter", "raid", "loot", "survival games", "dayz", "zombie apocalypse"]},
}
GENERAL_WORDS = ["server", "servers", "smp", "minecraft"]
SEARCHES = {  # what to search on YouTube for each mode, plus general server-hopping content
    "anarchy": ["minecraft anarchy server", "minecraft anarchy base", "anarchy server griefing"],
    "skyblock": ["minecraft skyblock server", "minecraft skyblock series", "skyblock minions"],
    "pvp": ["minecraft pvp server", "minecraft kit pvp", "minecraft duels"],
    "extraction": ["minecraft extraction", "minecraft guns server", "minecraft zombie apocalypse server"],
    "general": ["trying minecraft servers", "minecraft server review", "best minecraft servers to play"],
}
PERKS = ["the animated [Creator] tag, shown next to your name on every server and in our Discord",
         "free cosmetics (tags and name colours) for you",
         "early access to new modes and updates before they go public",
         "a private session or event for you and your viewers, whenever you'd like one"]
EMAIL_RE = re.compile(r"[A-Za-z0-9._%+-]+@[A-Za-z0-9.-]+\.[A-Za-z]{2,}")


# ---------------------------------------------------------------- storage
def load():
    if not os.path.exists(DB): return {}
    with open(DB, encoding="utf-8") as f: return json.load(f)


def save(db):
    os.makedirs(DATA, exist_ok=True)
    tmp = DB + ".tmp"
    with open(tmp, "w", encoding="utf-8") as f: json.dump(db, f, indent=1, ensure_ascii=False)
    os.replace(tmp, DB)


def now(): return dt.datetime.now(dt.timezone.utc).isoformat(timespec="seconds")


# ---------------------------------------------------------------- YouTube
def yt(path, **params):
    q = urllib.parse.urlencode({k: v for k, v in params.items() if v is not None})
    req = urllib.request.Request(API + path + "?" + q)
    key = os.environ.get("YOUTUBE_API_KEY")
    req.add_header("X-Goog-Api-Key", key or "proxy-injects-the-key")   # the session proxy replaces a placeholder
    try:
        with urllib.request.urlopen(req, timeout=30) as r: return json.load(r)
    except urllib.error.HTTPError as e:
        body = e.read().decode("utf-8", "replace")[:300]
        if e.code in (400, 401, 403):
            sys.exit(f"YouTube API refused the request ({e.code}): {body}\n"
                     "Is a key set? YOUTUBE_API_KEY, or a network secret for www.googleapis.com (header X-Goog-Api-Key).")
        raise


def chunks(xs, n):
    for i in range(0, len(xs), n): yield xs[i:i + n]


def mode_scores(text):
    t = text.lower()
    return {m: sum(t.count(w) for w in d["words"]) for m, d in MODES.items()}


def find(args):
    db = load()
    since = (dt.datetime.now(dt.timezone.utc) - dt.timedelta(days=args.days)).isoformat(timespec="seconds").replace("+00:00", "Z")
    seen, searches = set(), 0
    for group, queries in SEARCHES.items():
        for q in queries:
            if searches >= args.max_searches: break
            r = yt("search", part="snippet", type="video", q=q, publishedAfter=since, maxResults=50,
                   relevanceLanguage="en", order="relevance", videoDuration="medium")
            searches += 1
            for it in r.get("items", []): seen.add(it["snippet"]["channelId"])
    new_ids = [c for c in seen if f"yt:{c}" not in db]
    print(f"{searches} searches, {len(seen)} channels, {len(new_ids)} not in the tracker yet")
    added = 0
    for batch in chunks(new_ids, 50):
        chans = yt("channels", part="snippet,statistics,contentDetails", id=",".join(batch), maxResults=50).get("items", [])
        for ch in chans:
            st, sn = ch["statistics"], ch["snippet"]
            if st.get("hiddenSubscriberCount"): continue
            subs = int(st.get("subscriberCount", 0))
            if not SUBS_MIN <= subs <= SUBS_MAX: continue
            uploads = ch["contentDetails"]["relatedPlaylists"]["uploads"]
            items = yt("playlistItems", part="contentDetails,snippet", playlistId=uploads, maxResults=15).get("items", [])
            if not items: continue
            vids = [i["contentDetails"]["videoId"] for i in items]
            vinfo = yt("videos", part="statistics,snippet", id=",".join(vids)).get("items", [])
            if not vinfo: continue
            last = max(dt.datetime.fromisoformat(v["snippet"]["publishedAt"].replace("Z", "+00:00")) for v in vinfo)
            if (dt.datetime.now(dt.timezone.utc) - last).days > ACTIVE_DAYS: continue
            mc = [v for v in vinfo if "minecraft" in (v["snippet"]["title"] + " " + " ".join(v["snippet"].get("tags", []))).lower()]
            share = len(mc) / len(vinfo)
            if share < MC_SHARE_MIN: continue
            views = sorted(int(v["statistics"].get("viewCount", 0)) for v in vinfo)
            median = views[len(views) // 2]
            text = " ".join(v["snippet"]["title"] for v in vinfo) + " " + sn.get("description", "")
            ms = mode_scores(text)
            desc = sn.get("description", "")
            emails = sorted(set(EMAIL_RE.findall(desc)))
            links = sorted(set(re.findall(r"https?://[^\s)]+", desc)))[:8]
            top_mc = max(mc, key=lambda v: v["snippet"]["publishedAt"]) if mc else None
            db[f"yt:{ch['id']}"] = {
                "id": f"yt:{ch['id']}", "platform": "youtube", "name": sn["title"],
                "handle": sn.get("customUrl", ""), "url": f"https://www.youtube.com/channel/{ch['id']}",
                "subs": subs, "median_views": median, "engagement": round(median / max(subs, 1), 3),
                "mc_share": round(share, 2), "last_upload": last.date().isoformat(), "country": sn.get("country", ""),
                "modes": [m for m, s in sorted(ms.items(), key=lambda x: -x[1]) if s > 0][:2] or ["general"],
                "recent_video": top_mc["snippet"]["title"] if top_mc else "",
                "recent_video_url": f"https://www.youtube.com/watch?v={top_mc['id']}" if top_mc else "",
                "contact": emails[0] if emails else "YouTube About page (business email button) or a link they list",
                "emails": emails, "links": links, "status": "new", "found": now(), "notes": "",
            }
            added += 1
    save(db)
    print(f"added {added} creators ({SUBS_MIN:,}-{SUBS_MAX:,} subscribers, uploaded in the last {ACTIVE_DAYS} days, "
          f"{int(MC_SHARE_MIN * 100)}%+ Minecraft). Next: creators.py draft")


# ---------------------------------------------------------------- manual entries (TikTok and anything else)
def add(args):
    db = load()
    handle = args.handle.lstrip("@")
    cid = f"{args.platform[:2]}:{handle.lower()}"
    if cid in db: sys.exit(f"{cid} is already in the tracker ({db[cid]['status']})")
    urls = {"tiktok": f"https://www.tiktok.com/@{handle}", "youtube": f"https://www.youtube.com/@{handle}",
            "twitch": f"https://www.twitch.tv/{handle}", "instagram": f"https://www.instagram.com/{handle}"}
    modes = [m.strip() for m in (args.modes or "").split(",") if m.strip() in MODES] or \
            ([m for m, s in sorted(mode_scores(args.video or "").items(), key=lambda x: -x[1]) if s > 0][:2] or ["general"])
    db[cid] = {"id": cid, "platform": args.platform, "name": args.name or handle, "handle": "@" + handle,
               "url": urls.get(args.platform, ""), "subs": args.subs, "median_views": None, "engagement": None,
               "mc_share": None, "last_upload": "", "country": "", "modes": modes,
               "recent_video": args.video or "", "recent_video_url": "", "contact": args.contact or f"{args.platform} DM",
               "emails": EMAIL_RE.findall(args.contact or ""), "links": [], "status": "new", "found": now(),
               "notes": args.notes or ""}
    save(db)
    print(f"added {cid} ({', '.join(modes)}). Next: creators.py draft")


# ---------------------------------------------------------------- drafts
def pick_mode(c):
    return next((m for m in c["modes"] if m in MODES), "anarchy" if "general" in c["modes"] else c["modes"][0])


def draft_for(c):
    m = MODES[pick_mode(c)]
    first = c["name"] or "there"   # channel names aren't always personal names: greet by the whole name
    video = c.get("recent_video", "").strip()
    seen = (f"I watched \"{video}\" and " if video else "I've been watching your Minecraft videos and ") + \
           "think your viewers would get a lot out of what we've built."
    perks = "\n".join(f"- {p}" for p in PERKS)
    subject = f"{m['name']}: a server for your next video?"
    email = f"""Hi {first},

{seen}

I run the {NETWORK}. One of its servers is {m['name']}: {m['hook']}. Java and Bedrock, no mods needed.

If you'd like to play it on your channel, there's no script and no obligation: play it however you want. As a thank you, you'd get:
{perks}

Java: {m['addr']}
Bedrock: crispyanarchy.net, port 19100, then pick {m['name'].replace('Crispy ', '')} in the lobby
More: {SITE}{m['page']}
Discord: {DISCORD}

If it's not for you, no worries at all, and I won't follow up more than once.

Thanks,
{SENDER}
{NETWORK}"""
    dm = (f"Hi {first}! I run the {NETWORK}. {m['name']} is {m['hook']}. "
          f"If you ever want to play it for a video, you'd get a [Creator] tag, free cosmetics and early access to new modes. "
          f"Join: {m['addr']} · {SITE}{m['page']} · No pressure either way!")
    return {"mode": pick_mode(c), "subject": subject, "email": email, "dm": dm, "written": now()}


def draft(args):
    db = load(); n = 0
    for c in db.values():
        if c["status"] == "new" or (args.redo and c["status"] == "drafted"):
            c["draft"] = draft_for(c); c["status"] = "drafted"; n += 1
    save(db); export(args, quiet=True)
    print(f"drafted {n}. Read them in {os.path.relpath(os.path.join(DATA, 'outreach.md'))}, send the ones you like yourself, "
          "then: creators.py mark <id> sent")


# ---------------------------------------------------------------- tracker
def score(c):
    if c.get("engagement") is None: return 0.0
    fit = 1.0 if any(m in MODES for m in c["modes"]) else 0.6
    return round(min(c["engagement"], 1.0) * 100 * (c.get("mc_share") or 0) * fit, 1)


def ordered(db, status=None):
    rows = [c for c in db.values() if status in (None, c["status"])]
    return sorted(rows, key=lambda c: (STATUSES.index(c["status"]) if c["status"] in STATUSES else 9, -score(c)))


def lst(args):
    for c in ordered(load(), args.status):
        subs = f"{c['subs']:,}" if c.get("subs") else "?"
        print(f"{c['id']:<34} {c['status']:<8} {score(c):>5}  {subs:>8} subs  {','.join(c['modes']):<20} {c['name']}")


def mark(args):
    db = load()
    if args.id not in db: sys.exit(f"no creator {args.id}")
    if args.status not in STATUSES: sys.exit("status: " + ", ".join(STATUSES))
    c = db[args.id]; c["status"] = args.status; c.setdefault("history", []).append([now(), args.status])
    if args.notes: c["notes"] = (c["notes"] + " | " if c["notes"] else "") + args.notes
    save(db); export(args, quiet=True); print(f"{args.id}: {args.status}")


def export(args, quiet=False):
    db = load(); os.makedirs(DATA, exist_ok=True)
    rows = ordered(db)
    with open(os.path.join(DATA, "creators.csv"), "w", newline="", encoding="utf-8") as f:
        w = csv.writer(f)
        w.writerow(["id", "status", "score", "platform", "name", "url", "subs", "median_views", "engagement", "modes",
                    "last_upload", "contact", "recent_video", "notes"])
        for c in rows:
            w.writerow([c["id"], c["status"], score(c), c["platform"], c["name"], c["url"], c.get("subs"), c.get("median_views"),
                        c.get("engagement"), " ".join(c["modes"]), c.get("last_upload"), c.get("contact"), c.get("recent_video"), c.get("notes")])
    out = ["# Creator outreach", "", f"Updated {now()}. Send each one yourself, then `creators.py mark <id> sent`. "
           "Never more than one follow-up.", ""]
    for c in rows:
        if c["status"] in ("no", "ignore"): continue
        subs = f"{c['subs']:,} subscribers" if c.get("subs") else "subscribers unknown"
        out += [f"## {c['name']} ({c['platform']}) — {c['status']}", "",
                f"- `{c['id']}` · {subs} · score {score(c)} · fits: {', '.join(c['modes'])}",
                f"- {c['url']}" + (f" · recent: [{c['recent_video']}]({c['recent_video_url']})" if c.get("recent_video_url") else ""),
                f"- Contact: {c.get('contact')}" + (f" · links: {' '.join(c['links'])}" if c.get("links") else "")]
        if c.get("notes"): out.append(f"- Notes: {c['notes']}")
        d = c.get("draft")
        if d:
            if c["platform"] in ("tiktok", "instagram", "twitch"):
                out += ["", "**DM:**", "", "```", d["dm"], "```"]
            else:
                out += ["", f"**Email subject:** {d['subject']}", "", "```", d["email"], "```", "", "**Short DM version:**", "", "```", d["dm"], "```"]
        out.append("")
    with open(os.path.join(DATA, "outreach.md"), "w", encoding="utf-8") as f: f.write("\n".join(out))
    if not quiet: print(f"wrote data/outreach.md and data/creators.csv ({len(rows)} creators)")


def main():
    p = argparse.ArgumentParser(description=__doc__.split("\n")[0])
    s = p.add_subparsers(dest="cmd", required=True)
    f = s.add_parser("find"); f.add_argument("--days", type=int, default=45); f.add_argument("--max-searches", type=int, default=20)
    a = s.add_parser("add"); a.add_argument("platform", choices=["tiktok", "youtube", "twitch", "instagram"]); a.add_argument("handle")
    a.add_argument("--name"); a.add_argument("--subs", type=int); a.add_argument("--video"); a.add_argument("--modes")
    a.add_argument("--contact"); a.add_argument("--notes")
    d = s.add_parser("draft"); d.add_argument("--redo", action="store_true", help="rewrite drafts not yet sent")
    l = s.add_parser("list"); l.add_argument("--status", choices=STATUSES)
    m = s.add_parser("mark"); m.add_argument("id"); m.add_argument("status"); m.add_argument("--notes")
    s.add_parser("export")
    args = p.parse_args()
    {"find": find, "add": add, "draft": draft, "list": lst, "mark": mark, "export": export}[args.cmd](args)


if __name__ == "__main__":
    main()

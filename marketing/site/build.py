#!/usr/bin/env python3
"""Static website for Crispy Anarchy (www.crispyanarchy.net), written for search engines and AI answer engines.

    python3 build.py <outdir>

Writes plain HTML pages (real text, one topic per page), JSON-LD structured data, sitemap.xml, robots.txt and
llms.txt. Images come from images/ next to this file. The BlueMap 3D map is deployed alongside under /map/.
Every claim here was checked against the live servers (see marketing/listings.md for the rules: no player counts,
no "biggest/best", no franchise names).
"""
import re, json, os, shutil, sys, html
sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
from news import NEWS
from datetime import date

SITE = "https://www.crispyanarchy.net"
JAVA = "crispyanarchy.net"
BEDROCK_PORT = "19100"
DISCORD = "https://discord.gg/hF2bQgU"
UPDATED = date.today().isoformat()
HERE = os.path.dirname(os.path.abspath(__file__))

VOTE = [
    ("MinecraftServers.org", "https://minecraftservers.org/vote/587166"),   # first: the featured site (+1 bonus vote point)
    ("TopG", "https://topg.org/minecraft-servers/server-687311"),
    ("Planet Minecraft", "https://www.planetminecraft.com/server/crispy-anarchy-1-16-no-rules-survival/vote/"),
    ("Minecraft-Server-List", "https://minecraft-server-list.com/server/503605/vote/"),
    ("MMTop200", "https://mmtop200.com/vote/5176"),
    ("Minecraft-MP", "https://minecraft-mp.com/server/365762/vote/"),
    ("ServerTilt", "https://www.servertilt.com/minecraft-servers/crispy-anarchy/vote"),
]

NAV = [("/", "Home"), ("/anarchy/", "Anarchy"), ("/skyblock/", "Skyblock"), ("/pvp/", "Multiverse"),
       ("/extraction-zone/", "Extraction Zone"), ("/crispymon/", "Crispymon"), ("/join/", "How to join"), ("/news/", "News"),
       ("/vote/", "Vote"), ("/faq/", "FAQ")]

e = html.escape


def join_box(compact=False):
    return f"""<div class="join{' compact' if compact else ''}">
  <div class="addr-row"><span class="lbl">Java</span><code class="addr">{JAVA}</code><button type="button" class="copy" data-copy="{JAVA}">Copy</button></div>
  <div class="addr-row"><span class="lbl">Bedrock</span><code class="addr">{JAVA}</code><span class="port">port <b>{BEDROCK_PORT}</b></span><button type="button" class="copy" data-copy="{JAVA}">Copy</button></div>
  <p class="status" data-status><span class="dot"></span><span class="txt">Checking server status…</span></p>
</div>"""


def ld(obj):
    return '<script type="application/ld+json">' + json.dumps(obj, ensure_ascii=False, separators=(",", ":")) + "</script>"


ORG = {"@type": "Organization", "@id": SITE + "/#org", "name": "Crispy Anarchy", "alternateName": ["Crispy Network", "Crispy"],
       "url": SITE + "/", "logo": SITE + "/img/icon-512.png", "foundingDate": "2020", "sameAs": [DISCORD] + [u for _, u in VOTE]}
WEBSITE = {"@type": "WebSite", "@id": SITE + "/#website", "name": "Crispy Anarchy", "url": SITE + "/", "publisher": {"@id": SITE + "/#org"},
           "inLanguage": "en"}


DATES_FILE = os.path.join(HERE, "page_dates.json")   # path -> [content hash, date it last changed]
try:
    DATES = json.load(open(DATES_FILE))
except (OSError, ValueError):
    DATES = {}
SHOW_UPDATED = ("/crispymon/", "/anarchy/", "/skyblock/", "/pvp/", "/extraction-zone/", "/vanilla-anarchy/", "/bedrock-skyblock/",
                "/bedrock-anarchy/", "/2b2t-alternative/", "/guides/anarchy-survival/", "/guides/skyblock-beginners/", "/faq/", "/join/", "/rules/")


def changed(path, title, desc, body):
    """The date this page's content last changed (kept in page_dates.json, which is committed), not the build date."""
    import hashlib
    h = hashlib.sha1((title + "\0" + desc + "\0" + body).encode()).hexdigest()[:16]
    old = DATES.get(path)
    if not old or old[0] != h:
        DATES[path] = [h, UPDATED]
    return DATES[path][1]


def page(path, title, desc, body, crumbs=None, extra_ld=(), image="/img/og.jpg", h1_hero=None):
    url = SITE + path
    modified = changed(path, title, desc, body)
    if path in SHOW_UPDATED:
        body += f'<p class="wrap fine page-updated">Last updated <time datetime="{modified}">{fmt_date(modified)}</time>.</p>\n'
    graph = [ORG, WEBSITE, {"@type": "WebPage", "@id": url + "#page", "url": url, "name": title, "description": desc,
                            "isPartOf": {"@id": SITE + "/#website"}, "about": {"@id": SITE + "/#org"},
                            "dateModified": modified, "primaryImageOfPage": SITE + image, "inLanguage": "en"}]
    if crumbs:
        graph.append({"@type": "BreadcrumbList", "itemListElement": [
            {"@type": "ListItem", "position": i + 1, "name": n, "item": SITE + p} for i, (p, n) in enumerate([("/", "Home")] + crumbs)]})
    graph += list(extra_ld)
    nav = "".join(f'<a href="{p}"{" aria-current=\"page\"" if p == path else ""}>{n}</a>' for p, n in NAV)
    nav += f'<a class="nav-discord" href="{DISCORD}" rel="noopener">Discord</a>'
    return f"""<!doctype html>
<html lang="en">
<head>
<meta charset="utf-8">
<meta name="viewport" content="width=device-width, initial-scale=1, viewport-fit=cover">
<title>{e(title)}</title>
<meta name="description" content="{e(desc)}">
<link rel="canonical" href="{url}">
<meta name="robots" content="index, follow, max-image-preview:large, max-snippet:-1">
<meta name="theme-color" content="#0d1016">
<meta property="og:type" content="website">
<meta property="og:site_name" content="Crispy Anarchy">
<meta property="og:title" content="{e(title)}">
<meta property="og:description" content="{e(desc)}">
<meta property="og:url" content="{url}">
<meta property="og:image" content="{SITE}{image}">
<meta name="twitter:card" content="summary_large_image">
<link rel="icon" type="image/png" href="/img/icon-64.png">
<link rel="apple-touch-icon" href="/img/icon-512.png">
<link rel="preconnect" href="https://fonts.googleapis.com">
<link rel="preconnect" href="https://fonts.gstatic.com" crossorigin>
<link rel="stylesheet" href="https://fonts.googleapis.com/css2?family=Chakra+Petch:wght@600;700&family=JetBrains+Mono:wght@500;700&display=swap">
<link rel="stylesheet" href="/style.css">
{ld({"@context": "https://schema.org", "@graph": graph})}
</head>
<body>
<a class="skip" href="#main">Skip to content</a>
<header class="site">
  <div class="wrap hdr">
    <a class="logo" href="/"><img src="/img/mark.svg" alt="" width="28" height="28"><span>Crispy <b>Anarchy</b></span></a>
    <button type="button" class="menu-btn" aria-expanded="false" aria-controls="nav">Menu</button>
    <nav id="nav" aria-label="Main">{nav}</nav>
  </div>
</header>
<main id="main">
{body}
</main>
<footer class="site">
  <div class="wrap foot">
    <div>
      <p class="foot-name">Crispy Anarchy</p>
      <p>A Minecraft anarchy server since 2020, plus Skyblock, PvP and the new Extraction Zone on one network. Java and Bedrock.</p>
      <p>Java: <code>{JAVA}</code> · Bedrock: <code>{JAVA}</code> port <code>{BEDROCK_PORT}</code></p>
    </div>
    <div class="foot-links">
      {''.join(f'<a href="{p}">{n}</a>' for p, n in NAV[1:])}
      <a href="/spawn-map/">3D spawn map</a>
      <a href="/vanilla-anarchy/">Vanilla anarchy</a>
      <a href="/bedrock-anarchy/">Bedrock anarchy</a>
      <a href="/bedrock-skyblock/">Bedrock Skyblock</a>
      <a href="/guides/anarchy-survival/">Anarchy guide</a>
      <a href="/guides/skyblock-beginners/">Skyblock guide</a>
      <a href="/2b2t-alternative/">Servers like 2b2t</a>
      <a href="/rules/">Rules</a>
      <a href="{DISCORD}" rel="noopener">Discord</a>
    </div>
  </div>
  <div class="wrap fine">Not an official Minecraft product. Not approved by or associated with Mojang or Microsoft. Updated {UPDATED}.</div>
</footer>
<script src="/site.js" defer></script>
</body>
</html>
"""


def fig(name, alt, cap):
    """A screenshot from images/shots/ (1600x900 webp) with a caption."""
    return (f'<figure class="pic"><img src="/img/shots/{name}.webp" alt="{e(alt)}" width="1600" height="900" loading="lazy">'
            f'<figcaption>{cap}</figcaption></figure>')


def figs(*items):
    """Two or more screenshots side by side (stacked on phones)."""
    return '<div class="pics">' + "".join(fig(*i) for i in items) + '</div>'


def faq_ld(qas):
    return {"@type": "FAQPage", "mainEntity": [{"@type": "Question", "name": q, "acceptedAnswer": {"@type": "Answer", "text": a}} for q, a in qas]}


def faq_html(qas):
    return "".join(f'<details><summary><h3>{e(q)}</h3></summary><p>{e(a)}</p></details>' for q, a in qas)


GAMESERVER = {"@type": "GameServer", "@id": SITE + "/#server", "name": "Crispy Anarchy Minecraft server", "url": SITE + "/",
              "game": {"@type": "VideoGame", "name": "Minecraft", "gamePlatform": ["PC (Java Edition)", "Bedrock Edition"]},
              "serverStatus": "OnlineServerStatus", "provider": {"@id": SITE + "/#org"},
              "description": "Minecraft anarchy server since 2020, never reset. Java address crispyanarchy.net; Bedrock crispyanarchy.net port 19100."}

# ---------------------------------------------------------------- FAQ (shared by /faq/ and snippets elsewhere)
FAQ = [
    ("What is the Crispy Anarchy server IP?",
     f"Java Edition: {JAVA} (no port needed). Bedrock Edition: {JAVA}, port {BEDROCK_PORT}."),
    ("What is a Minecraft anarchy server?",
     "An anarchy server is a Minecraft survival server with no gameplay rules: no land claims, no protected bases and no staff stepping in to stop griefing or PvP. "
     "Griefing, raiding and PvP are all part of the game, and the world is never reset, so it keeps years of history."),
    ("Does Crispy Anarchy have rules?",
     "Crispy Anarchy has no gameplay rules and no land claims: anything you build can be found, raided or griefed by other players. The only rules are community rules that apply everywhere: no hate speech or hateful builds, no real-life harassment, threats or doxxing, and no spam. See www.crispyanarchy.net/rules/."),
    ("Has the Crispy Anarchy map ever been reset?",
     "No. The anarchy world has been running since 2020 and has never been reset."),
    ("Can Bedrock players join Crispy Anarchy?",
     f"Yes. Bedrock Edition players (Windows, phone, tablet and console) join with {JAVA} on port {BEDROCK_PORT} and play with Java players on the same servers."),
    ("Which Minecraft versions can join?",
     "Java Edition 1.13 up to 26.3 can join; the server itself runs 26.2. Bedrock players need the current Bedrock version."),
    ("Do I need mods or a special client?",
     "No. Everything, including custom enchantments, implants and the market, works on the normal game. No mods or resource packs are required."),
    ("Is Crispy Anarchy cracked?",
     "No. Java players need a paid Java Edition account. Bedrock players sign in with their Microsoft account."),
    ("Is Crispy Anarchy free?",
     "Yes, it is free to join and play."),
    ("Are chat reports turned off?",
     "Yes. The anarchy server runs No Chat Reports, so chat messages cannot be reported to Mojang through the game's chat reporting."),
    ("How is Crispy Anarchy different from 2b2t?",
     "Same idea: no gameplay rules and a world that is never reset. Different: Bedrock players can join too, the server adds 193 custom enchantments, "
     "cyberpunk implants and a market economy with a crypto exchange, and the community is smaller, so you meet people quickly."),
    ("What other game modes does the network have?",
     "Besides Anarchy there is Vanilla Anarchy (plain survival), Skyblock with skills, pets and minions, a PvP server called Multiverse "
     "with 36 characters, duels and co-op zombie waves, and Extraction Zone, a PvPvE looting mode in a ruined city, open now. All share one chat and one Discord."),
    ("Where is spawn on Crispy Anarchy?",
     "World spawn is at X 287, Z -207 in the overworld. You can explore the area around it on the 3D map at www.crispyanarchy.net/spawn-map/."),
]

# The rest of the network: /faq/ shows these under their own headings. Yoink (the Discord bot) reads every FAQPage on
# the site for /ask, so a question added here is one the bot can answer after its next refresh (tools/discordbot/faq.py).
FAQ_MORE = [
    ("Getting around", [
        ("How do I switch between game modes?",
         "Every mode is on the same address. You arrive in the lobby: use the Pick a Server item in your hotbar and choose a mode. "
         "Type /lobby (or /hub) on any server to go back and pick another one."),
        ("Does my inventory carry over between game modes?",
         "No. Each mode has its own world, inventory and progress. What you keep everywhere is your vote points, your cosmetics "
         "(tags, name colours and chat colours) and your Discord link."),
        ("Are there games in the lobby?",
         "Yes. UNO for 2 to 8 players (bots fill empty seats; type /uno) and a solo poker card game with a daily run on the same seed for everyone. Both are in the lobby's Pick a Server menu."),
        ("Can I teleport away in the middle of a fight?",
         "No. Hitting or being hit by another player puts you in combat for 15 seconds. Until it runs out you can't leave with /lobby or /hub, "
         "and on Anarchy and Skyblock commands like /home, /spawn, /back, /tpa, /warp and /island are blocked too."),
        ("How do I report a player or a bug?",
         f"Open a ticket in the Crispy Discord ({DISCORD}); the ticket channel is linked in the welcome channel. Anarchy has no gameplay rules, "
         "so griefing and PvP there are not reportable, but the community rules (no hate speech, harassment, doxxing or spam) apply everywhere."),
        ("Where can I suggest an idea for the server?",
         f"In the suggestions channel on the Crispy Discord ({DISCORD})."),
    ]),
    ("Voting and rewards", [
        ("How do I vote for the server?",
         "Open www.crispyanarchy.net/vote/ (or type /vote in game for the links) and vote on each site with your exact Minecraft username. "
         "You can vote on every site once a day."),
        ("What do I get for voting?",
         "Each vote gives you one reward, which you send to Anarchy, Skyblock, Multiverse or Extraction Zone from the /vote menu, plus vote points for cosmetics. "
         "A vote on MinecraftServers.org gives one extra point, and voting every day builds a streak: your first vote each day earns an extra point from day 3, two from day 7 and three from day 14."),
        ("I voted but didn't get my reward. What do I do?",
         "Rewards aren't handed out on their own: type /vote and click a server to send a reward there (shift-click sends them all), and it arrives when you're online on that server. "
         "Some vote sites take a few minutes to report a vote. Check that you typed your exact username. If it still hasn't shown up after an hour, open a ticket on Discord."),
        ("When does the vote day reset?",
         "At midnight UTC, the same time the vote sites reset. If you haven't voted today you get a reminder in chat every 90 minutes; switch it off with the bell in /vote."),
        ("What are vote points for?",
         "Cosmetics: tags next to your name, name colours and chat colours, which work on every server. Type /cosmetics to buy and wear them. Some tags can't be bought and are earned instead, for example by topping a leaderboard."),
        ("Do I get anything for inviting a friend?",
         "Yes. Your friend types /invitedby <your name> within their first 48 hours on the network. Once they've played 60 minutes, they get 5 vote points and a vote reward and you get 10 vote points. "
         "Bring three friends and you also earn the [Recruiter] tag. Type /invite in game for the details."),
    ]),
    ("Discord", [
        ("Is there a Discord server?",
         f"Yes: {DISCORD}. Game chat from every server is relayed there, and you can pick roles in the welcome channel to see the channels you want."),
        ("How do I link my Minecraft account to Discord?",
         "Join any Crispy server, then in Discord type /link with your exact Minecraft name (Bedrock players include the leading dot). "
         "Yoink sends a 6-digit code to you in game chat; type /verify with that code in Discord within 5 minutes. /unlink removes the link."),
        ("What does linking my Discord account do?",
         "Players can ping you from game chat by your Minecraft name, you can run a few commands such as /msg, /tpa, /home and /spawn from Discord with /mc, "
         "and price checks you make in game are credited to your Discord name."),
    ]),
    ("Anarchy", [
        ("Can I lose my items if I'm killed in the Anarchy market?",
         "No. PvP stays on in the market, but if you die there you keep your inventory and respawn with it. A totem in your hand still saves you as usual. "
         "Items on the market's armor stands and in its item frames can't be taken either."),
        ("What is Vanilla Anarchy?",
         "The same idea as Anarchy, with no gameplay rules and no claims, but plain survival: no custom enchantments, implants or market. Pick it in the lobby."),
    ]),
    ("Skyblock", [
        ("How do I start on Skyblock?",
         "Pick Skyblock in the lobby. The first time you go to your island you choose one of seven themed starter islands. "
         "Every player also gets a Skyblock Guide book with how-to pages and recipes (lost it? /guide book). Walk through the portal on your island to reach the hub, where the merchants and the Bazaar are."),
        ("Can I play Skyblock with friends?",
         "Yes. Type /invite <player> while they're online to add them to your island. An island holds 4 members at first, and up to 8 with the co-op upgrades in /island upgrades. /visit <player> lets you look around someone else's island."),
        ("What are the main Skyblock commands?",
         "/island for the island menu, /challenges, /skills, /collections, /pets, /bazaar (or /bz), /shop, /island level and /island top for the island rankings, "
         "and /warp hub, /warp mines or /warp woods for the resource zones."),
    ]),
]
FAQ_ALL = FAQ + [qa for _, qas in FAQ_MORE for qa in qas]


def home():
    modes = [
        ("/anarchy/", "Anarchy", "No gameplay rules, no claims, one world since 2020. Custom enchantments, implants, a market and a hidden black market."),
        ("/vanilla-anarchy/", "Vanilla Anarchy", "Plain survival anarchy with no custom items, for people who like it pure."),
        ("/skyblock/", "Skyblock", "Grow your island with skills, collections, pets, 43 minions, a Bazaar and gear crafted from what you farm."),
        ("/pvp/", "Multiverse", "36 playable characters: arena PvP, ranked duels, zombie waves, Core Defense and a roguelite tower."),
        ("/extraction-zone/", "Extraction Zone", "New: loot a ruined city, fight armed raiders and other players, and get out alive. Open now."),
        ("/spawn-map/", "3D spawn map", "Fly over two square kilometres of spawn, wrecked by six years of anarchy."),
        ("/bedrock-anarchy/", "Bedrock anarchy", "Play anarchy from Windows, phone, tablet or console, in the same world as Java players."),
        ("/crispymon/", "Crispymon", "Our Cobblemon server: catch and battle creatures, gym badges, trainers, breeding and trading. Modded Java 1.21.1."),
        ("/bedrock-skyblock/", "Bedrock Skyblock", "Skyblock on Windows, phone, tablet or console, on the same islands and Bazaar as Java players."),
    ]
    cards = "".join(f'<a class="card" href="{u}"><h3>{n}</h3><p>{d}</p></a>' for u, n, d in modes)
    latest = "".join(f'''<article class="post-card"><p class="date"><time datetime="{n['date']}">{fmt_date(n['date'])}</time></p><h3><a href="/news/{n['slug']}/">{e(n['title'])}</a></h3><p>{e(n['summary'])}</p></article>''' for n in NEWS[:3])
    body = f"""
<section class="hero">
  <div class="wrap hero-in">
    <p class="kicker">Minecraft anarchy server · since 2020 · never reset</p>
    <h1>Crispy Anarchy: a Minecraft anarchy server for Java and Bedrock, since 2020</h1>
    <p class="lede">One world, running since 2020 and never reset. No gameplay rules, no claims, no protected bases. Custom enchantments, cyberpunk implants and a player market on top, and no mods needed.</p>
    {join_box()}
  </div>
</section>
<img class="banner" src="/img/wide.webp" alt="Wide 3D view of Crispy Anarchy spawn: a griefed tower and ruined walls rising out of lava-scarred stone and ocean" width="2400" height="675" fetchpriority="high">
<section class="wrap block">
  <h2>What is Crispy Anarchy?</h2>
  <p class="measure">Crispy Anarchy is a free Minecraft anarchy server that has been running since 2020 without a map reset. There are no gameplay rules and no land claims: players grief, raid, fight and build wherever they like, and everything that happens stays in the world. Java Edition players join at <code>{JAVA}</code>; Bedrock Edition players join at <code>{JAVA}</code> on port <code>{BEDROCK_PORT}</code>.</p>
  <p class="measure">Crispy Anarchy is also the name of the wider Crispy network: our <a href="/anarchy/">Minecraft anarchy server</a> plus a <a href="/vanilla-anarchy/">vanilla anarchy server</a>, a <a href="/skyblock/">Minecraft Skyblock server</a>, a <a href="/pvp/">PvP server</a> and <a href="/extraction-zone/">Extraction Zone</a>, linked by one chat and one Discord.</p>
  <ul class="facts">
    <li><b>2020</b><span>world started, never reset</span></li>
    <li><b>0</b><span>rules or land claims</span></li>
    <li><b>193</b><span>custom enchantments</span></li>
    <li><b>1.13–26.3</b><span>Java versions that can join</span></li>
  </ul>
</section>
<section class="wrap block">
  <h2>Game modes on the network</h2>
  <div class="cards">{cards}</div>
</section>
<section class="wrap block split">
  <div>
    <h2>See six years of anarchy in 3D</h2>
    <p>The spawn area has been fought over since 2020. We rendered two square kilometres around spawn as a 3D map you can fly through in your browser: lava casts, pillars, wither holes and what is left of the old builds.</p>
    <p><a class="btn" href="/spawn-map/">Open the 3D map</a></p>
  </div>
  <img src="/img/low.webp" alt="Ground-level 3D view of Crispy Anarchy spawn: ruined stone walls, water and lava flows" width="1600" height="900" loading="lazy">
</section>
<section class="wrap block">
  <h2>Latest news</h2>
  <div class="posts">{latest}</div>
  <p><a href="/news/">All news</a></p>
</section>
<section class="wrap block">
  <h2>Guides for new players</h2>
  <ul class="more">
    <li><a href="/guides/anarchy-survival/">How to survive on a Minecraft anarchy server</a></li>
    <li><a href="/guides/skyblock-beginners/">Crispy Skyblock beginner's guide: your first hours</a></li>
    <li><a href="/2b2t-alternative/">Looking for a server like 2b2t?</a></li>
  </ul>
</section>
<section class="wrap block">
  <h2>Quick answers</h2>
  <div class="faq">{faq_html(FAQ[:5])}</div>
  <p><a href="/faq/">All questions</a></p>
</section>
"""
    return page("/", "Crispy Anarchy – Minecraft Anarchy Server & Network (Java & Bedrock)",
                "Crispy Anarchy is a Minecraft anarchy server with no gameplay rules, running since 2020 and never reset, and a network with Skyblock, PvP and Extraction Zone. Java and Bedrock crossplay. IP: crispyanarchy.net",
                body, extra_ld=[GAMESERVER, faq_ld(FAQ[:5])])


def anarchy():
    body = f"""
<section class="wrap block head">
  <p class="kicker">Anarchy · Java + Bedrock</p>
  <h1>Minecraft anarchy server with no gameplay rules, running since 2020</h1>
  <p class="lede measure">Crispy Anarchy is our main server: a survival world with no gameplay rules and no land claims that has never been reset since it started in 2020. On top of plain anarchy it adds custom enchantments, cyberpunk implants and a player market, all without mods.</p>
  {join_box(True)}
</section>
<figure class="wrap shot"><img src="/img/low.webp" alt="Ground-level 3D view of Crispy Anarchy spawn: ruined stone walls, water and lava flows" width="1600" height="900" loading="lazy"><figcaption>Spawn today, from the <a href="/spawn-map/">3D map</a>.</figcaption></figure>
<section class="wrap block prose">
  <h2>No gameplay rules, no claims, no resets</h2>
  <p>There are no gameplay rules on Crispy Anarchy. Nothing is protected: bases can be found and raided, builds can be griefed, and anyone can kill anyone. Chat reports are off (the server runs No Chat Reports).</p>
  <p>The few <a href="/rules/">community rules</a> are about people, not gameplay: no hate speech or hateful builds, no real-life harassment, threats or doxxing, and no spam.</p>
  <p>The world started in 2020 and has never been wiped, so the land around spawn carries six years of history. Spawn itself is at X 287, Z -207, and the closer you get the less is left standing. Most players head out along the axis highways to find space to build.</p>

  <h2>193 custom enchantments</h2>
  <p>Crispy Anarchy has 193 custom enchantments in nine rarity tiers: Simple, Unique, Elite, Ultimate, Legendary, Soul, Heroic, Mastery and Rare. Heroic enchantments are upgrades that need the base enchantment at its maximum level. You buy random enchantment books from the Enchanter in the market with your XP.</p>

  <h2>Cyberpunk implants</h2>
  <p>The Ripperdoc in the market sells implants, bought with diamonds or netherite. Each implant takes one body slot and uses up some of your capacity. You can go over the limit of 20, but every point over raises the chance of a cyberpsychosis episode.</p>

  <h2>The market, the bank and crypto</h2>
  <p>The market is a separate area full of villager shops that trade in Gold Coins and Coin Bags. The Banker exchanges 36 emeralds or 36 diamonds for one Gold Coin, 16 coins for a block of netherite, and 64 coins for a Coin Bag. Next to the bank, a crypto trader buys and sells Bitcoin at a price that moves up and down like a real cryptocurrency, with its own price chart.</p>
  <p>PvP is on in the market too, but if you're killed there you keep your items, XP and implants. Everywhere else, you drop everything. And there's a combat tag: for 15 seconds after a fight you can't teleport away with <code>/home</code>, <code>/spawn</code>, <code>/tpa</code> and the like.</p>
  {fig("anarchy-crypto", "The Crypto Exchange trader at his desk in the Crispy Anarchy market, with a Bitcoin on the counter", "The Crypto Exchange: buy and sell Bitcoin at a live, moving price.")}
  <p>Somewhere in the world there is also a black market. Its location is not published: you have to find it. Find it once and you earn the [Black Market] tag, which opens doors that stay shut for everyone else.</p>
  {fig("anarchy-blackmarket", "A market merchant on Crispy Anarchy who only trades with players wearing the Black Market tag", "Some merchants only deal with players who have found the black market.")}

  <h2 id="vanilla">Vanilla Anarchy</h2>
  <p>Prefer anarchy without custom items? <a href="/vanilla-anarchy/">Vanilla Anarchy</a> is a separate server with plain survival anarchy: no custom enchantments, no implants, no shops. Pick it from the lobby.</p>

  <h2>New to anarchy?</h2>
  <p>Read <a href="/guides/anarchy-survival/">how to survive on a Minecraft anarchy server</a> before you jump in. Coming from 2b2t? See <a href="/2b2t-alternative/">what's the same and what's different</a>.</p>

  <h2>Play from Java or Bedrock</h2>
  <p>Java Edition 1.13 to 26.3 can join at <code>{JAVA}</code>. Bedrock Edition players on Windows, phones, tablets and consoles join at <code>{JAVA}</code> on port <code>{BEDROCK_PORT}</code> and share the same world. Step-by-step instructions are on the <a href="/join/">how to join</a> page.</p>
</section>
"""
    qas = [FAQ[2], FAQ[3], FAQ[10]]
    body += f'<section class="wrap block"><h2>Anarchy questions</h2><div class="faq">{faq_html(qas)}</div></section>'
    return page("/anarchy/", "Minecraft Anarchy Server – No Gameplay Rules, Never Reset Since 2020 | Crispy Anarchy",
                "A Minecraft anarchy server with no gameplay rules and no claims, running since 2020 and never reset. 193 custom enchantments, implants, a market and crypto. Java & Bedrock: crispyanarchy.net",
                body, crumbs=[("/anarchy/", "Anarchy")], extra_ld=[GAMESERVER, faq_ld(qas)], image="/img/low.webp")


SKYBLOCK_FAQ = [
    ("What is the Crispy Skyblock server IP?",
     f"Java Edition: skyblock.crispyanarchy.net, or {JAVA} and pick Skyblock in the lobby. Bedrock Edition: {JAVA}, port {BEDROCK_PORT}, then pick Skyblock in the lobby."),
    ("Is Crispy Skyblock pay-to-win?",
     "No. Coins, gear, minions and pets all come from playing: farming, mining, fighting and trading on the Bazaar. Nothing that makes you stronger is sold for real money."),
    ("Can I play Crispy Skyblock on Bedrock?",
     f"Yes. Bedrock Edition players on Windows, phones, tablets and consoles join {JAVA} on port {BEDROCK_PORT}, pick Skyblock in the lobby, and play on the same islands as Java players."),
    ("Is there PvP on Crispy Skyblock?",
     "No. PvP is off on islands (visitors included), in the hub and in the resource zones, so nobody can kill you while you farm or visit a friend."),
    ("Do minions keep working when I'm offline?",
     "Yes. Minions run on real time and keep collecting while you're offline until their storage is full. Collect from them when you're back."),
    ("Can I play Skyblock with friends?",
     "Yes. Type /invite <player> to add a friend to your island. An island holds 4 members at first and up to 8 with co-op upgrades. /visit <player> lets you look around someone else's island; visitors can't build, break or open anything."),
]


def skyblock():
    islands = [("Classic", "Plains", "The classic L of dirt with an oak tree, and a chest with lava, ice, cactus, sugar cane, melon and pumpkin seeds."),
               ("Desert Oasis", "Desert", "Sand, sandstone, cactus and a tiny oasis. It never rains, and dirt only comes from the chest."),
               ("Jungle", "Jungle", "A tall jungle tree with cocoa, plus bamboo and a melon."),
               ("Frozen Peak", "Snowy taiga", "Spruce, snow, a frozen pond and sweet berries."),
               ("Mushroom Isle", "Mushroom fields", "A giant mushroom and a mooshroom. No hostile mobs spawn here."),
               ("Swamp island", "Swamp", "Mud, a lily-pad pond and vines. Slimes come out at night."),
               ("Farm island", "Plains", "Ripe wheat, carrot and potato rows, a barn and a scarecrow.")]
    island_rows = "".join(f"<tr><td>{n}</td><td>{b}</td><td>{d}</td></tr>" for n, b, d in islands)
    skills = [("Farming", "Fully grown crops", "+2% chance of double crop drops per level"),
              ("Mining", "Ores, stone, obsidian", "+2% chance of double ore drops per level"),
              ("Foraging", "Logs", "+2% chance of double logs per level"),
              ("Combat", "Hostile mobs and bosses", "+1% damage per level"),
              ("Fishing", "Every catch", "More luck, so better catches")]
    skill_rows = "".join(f"<tr><td>{n}</td><td>{x}</td><td>{p}</td></tr>" for n, x, p in skills)
    body = f"""
<section class="wrap block head">
  <p class="kicker">Skyblock · Java + Bedrock · no pay-to-win</p>
  <h1>Minecraft Skyblock server with skills, minions, pets and a player Bazaar</h1>
  <p class="lede measure">Crispy Skyblock starts you on one of seven themed islands in the void and gives you years of things to grow into: five skills, 68 collections, 43 kinds of minions, pets, a player-run Bazaar, island bosses and gear you craft from what you farm. It's free, there's no pay-to-win, PvP is off, and Java and Bedrock players share the same islands.</p>
  {join_box(True)}
  <p class="note">Java players can also connect straight to <code>skyblock.crispyanarchy.net</code>. Everyone else picks Skyblock in the lobby.</p>
</section>
<figure class="wrap shot"><img src="/img/shots/skyblock-hub.webp" alt="Aerial view of the Crispy Skyblock hub island: cherry trees, market stalls, a central plaza and a lookout tower" width="1600" height="900"><figcaption>The Skyblock hub: market stalls, merchants, player plots and portals to your island and the resource zones.</figcaption></figure>
<section class="wrap block prose">
  <h2>What is Crispy Skyblock?</h2>
  <p>Skyblock is Minecraft survival on a small island floating over the void: everything you build starts from a few blocks of dirt, one tree and a chest. Crispy Skyblock keeps that start and adds a long road of progression on top, all without mods or a resource pack. You can play it alone, or bring friends onto your island and grow it together.</p>
  <p>It's part of the Crispy network, which has run an anarchy server since 2020. Skyblock has its own world and economy, but shares one chat and one <a href="{DISCORD}" rel="noopener">Discord</a> with the rest of the network.</p>

  <h2>Seven themed starter islands</h2>
  <p>The first time you go to your island you pick where to start. Each island has its own biome across your whole plot and its own starter chest:</p>
</section>
<section class="wrap block"><div class="tablewrap"><table class="modes"><thead><tr><th>Island</th><th>Biome</th><th>What you start with</th></tr></thead><tbody>{island_rows}</tbody></table></div></section>
<section class="wrap block prose">
  <p>While you play, the sky helps out: an animal drops onto your island every 15 minutes of island play time, a supply crate every 25, an ore meteor every 45, and dungeons to clear at 30, 90 and 180 minutes. After 150 minutes an End portal arrives. Any of these drops can be switched off per island.</p>

  <h2>Five skills that level as you play</h2>
  <p>There's no grinding a menu for XP: you level a skill by doing it. Every skill goes up to level 25, every level-up pays coins, and every level makes you better at that job.</p>
</section>
<section class="wrap block"><div class="tablewrap"><table class="modes"><thead><tr><th>Skill</th><th>XP from</th><th>Perk</th></tr></thead><tbody>{skill_rows}</tbody></table></div></section>
<section class="wrap block prose">
  <p>Blocks you placed yourself give no XP and no double drops, so placing and breaking the same block won't level you. A cobblestone generator still counts.</p>

  <h2>68 collections and 26 challenges</h2>
  <p>Everything you gather counts toward its collection: 23 farming, 20 mining, 8 foraging, 10 combat and 7 fishing resources, plus your minions' haul at half rate. Each collection has nine tiers, and every tier pays coins and skill XP. Only what you gather yourself counts, so buying from the Bazaar won't get you there. Open them with <code>/collections</code>.</p>
  {fig("sb-collections", "The Crispy Skyblock Collections menu showing Farming, Mining and Foraging categories and tier progress", "The Collections menu: 68 resources, nine tiers each, coins and skill XP for every tier.")}
  <p>On top of that, 26 one-time challenges (Easy, Medium, Hard and three that need an island level) pay out resources, spawn eggs and XP. Find them in <code>/challenges</code>.</p>

  <h2>Island level and the Top Islands board</h2>
  <p>Every block on your island adds to its level, and valuable blocks such as diamond, emerald and netherite blocks or beacons add more. The best islands appear on the Top Islands board in the hub, and <code>/island top</code> lists the top ten.</p>

  <h2>43 kinds of minions</h2>
  <p>Minions are small helpers you craft and place on your island. Each one keeps collecting its resource, from crops and logs to ores and mob drops, and they run on real time, so they keep working while you're offline until their storage is full. Upgrade a minion to make it faster and give it more room. You start with five minion slots and get more as your island level rises and through island upgrades.</p>
  {fig("skyblock-minion", "Minions working on a player's Skyblock island next to storage chests, with an Oak Minion label", "Minions at work on an island, filling up while you play elsewhere.")}

  <h2>The Bazaar: a market run by players</h2>
  <p>The Bazaar is where players trade. Place a sell offer or a buy order at your own price; new orders match the best price on the other side straight away. Sales go through even if you're offline, and you collect your coins later. Open it with <code>/bazaar</code> (or <code>/bz</code>), or visit the Bazaar merchant in the hub.</p>

  <h2>Pets</h2>
  <p>Pets float beside you and boost one skill's XP, by 10% plus 1% for every pet level, up to level 30. Pick a Pig for Farming, a Silverfish for Mining, a Fox for Foraging, a Wolf for Combat or a Squid for Fishing. The rare Phoenix can't be bought at all: it can drop for anyone on an island that beats an End boss, and it boosts every skill.</p>

  <h2>Crafted gear with abilities</h2>
  <p>Turn stacks of what you farm into enchanted versions, then craft 17 armour sets and 19 weapons. Armour sets give a bonus when you wear all four pieces, from Speed and Haste for farmers to extra hearts and void protection, and weapons have right-click abilities such as short-range teleports, ground slams and healing. Better gear needs more farming, not real money. <code>/gear</code> shows every item and its recipe.</p>

  <h2>Your own Nether and End, and island bosses</h2>
  <p>Every island has a Nether plot of its own, where fortress wrecks with blaze spawners and pieces of bastion land over time, and its own End island once your End portal arrives. Both have a boss altar: summon the island's next boss when you're ready, from the Blaze King and the Magma Titan in the Nether to the Ender Colossus and the Void Ravager in the End. Every member gets coins and loot for each kill.</p>

  <h2>Resource zones off your island</h2>
  <p>Portals in the hub lead to two shared resource zones with levelled mobs:</p>
  <ul>
    <li><b>The Deep Mines</b>: caves through a rock island, lined with ores that grow back after 45 seconds. The deeper you go, the richer the ores and the tougher the mobs.</li>
    <li><b>Whispering Woods</b>: a dense forest of big trees whose logs grow back after 30 seconds.</li>
  </ul>
  <p>If you die in a zone you only drop what you gathered there; the rest of your inventory and your XP come back when you respawn.</p>

  <h2>Island upgrades and co-op</h2>
  <p>Spend coins in <code>/island upgrades</code> to grow your island from 128 to 256 blocks across, add minion slots, raise the member limit from 4 to 8, and upgrade your cobblestone generator so it sometimes makes ore (at the top tier, diamond and emerald too). Invite friends with <code>/invite &lt;player&gt;</code>, and let anyone look around with <code>/visit &lt;player&gt;</code>: visitors can't build, break or open anything.</p>

  <h2>No PvP, no pay-to-win</h2>
  <p>PvP is off across Skyblock: on islands (visitors included), in the hub and in the resource zones. And nothing that makes you stronger is sold for real money. Coins, gear, minions and pets all come from playing.</p>

  <h2>The hub</h2>
  <p>The hub is a floating island with a plaza, a fountain and merchants in market stalls. Buy a plot there for a shop or a house, and use its portals to reach your island and the resource zones.</p>

  <h2>How to join Crispy Skyblock</h2>
  <ol class="steps">
    <li>Java Edition (1.13 to 26.3): add the server <code>skyblock.crispyanarchy.net</code>, or <code>{JAVA}</code> and pick Skyblock in the lobby.</li>
    <li>Bedrock Edition: add <code>{JAVA}</code> with port <code>{BEDROCK_PORT}</code>, join, and pick Skyblock in the lobby. See <a href="/bedrock-skyblock/">Skyblock on Bedrock</a> for console steps.</li>
    <li>Choose your starter island, read the Skyblock Guide book you get on joining, and start farming.</li>
  </ol>
  <p>New to it? The <a href="/guides/skyblock-beginners/">Crispy Skyblock beginner's guide</a> walks through your first hours.</p>
</section>
<section class="wrap block"><h2>Skyblock questions</h2><div class="faq">{faq_html(SKYBLOCK_FAQ)}</div></section>
"""
    return page("/skyblock/", "Minecraft Skyblock Server (Java & Bedrock) – No P2W | Crispy Skyblock",
                "A free Minecraft Skyblock server for Java and Bedrock: 7 themed starter islands, 5 skills, 68 collections, 43 minions, pets, a player Bazaar, island bosses and craftable gear. No pay-to-win, no PvP.",
                body, crumbs=[("/skyblock/", "Skyblock")], extra_ld=[GAMESERVER, faq_ld(SKYBLOCK_FAQ)], image="/img/shots/skyblock-hub.webp")


CRISPYMON = "crispymon.org:12673"
MODPACK_URL = "https://www.curseforge.com/minecraft/modpacks/crispymon-cobblemon-1-8-1-modpack"   # the Crispymon modpack download; empty = "get it in the Discord"


def crispymon():
    get_pack = (f'<a href="{MODPACK_URL}" rel="noopener">Download the Crispymon modpack</a>' if MODPACK_URL
                else f'Get the Crispymon modpack from the Crispymon channel in our <a href="{DISCORD}" rel="noopener">Discord</a>')
    qas = [
        ("What is the Crispymon server IP?",
         f"{CRISPYMON} (Java Edition 1.21.1, with the Crispymon modpack installed). It's a separate server from the rest of the Crispy network, so it has its own address."),
        ("Is Crispymon a Cobblemon server?",
         "Yes. Crispymon runs Cobblemon 1.8 on Minecraft 1.21.1, with gyms and badges, trainers to battle, breeding, a global trade station, an economy and player shops added on top."),
        ("Do I need a modpack to join Crispymon?",
         "Yes. Crispymon is a modded server, so you need the Crispymon modpack, which has the same mods as the server. " +
         (f"Download it at {MODPACK_URL}." if MODPACK_URL else "The download link is in the Crispymon channel of our Discord.")),
        ("Can Bedrock players join Crispymon?",
         "No. Crispymon is a modded Java Edition server, and mods don't run on Bedrock. Bedrock players can join the rest of the Crispy network: Anarchy, Skyblock, Multiverse and Extraction Zone."),
        ("Will Crispymon run on a low-end PC?",
         "It's a pack of about 150 mods, so give Minecraft at least 4 GB of memory, ideally 6 GB, and keep render distance around 6 to 8 on weaker machines. Shaders and Distant Horizons are optional: leave them off on low-end PCs and laptops."),
    ]
    body = f"""
<section class="wrap block head">
  <p class="kicker">Crispymon · Cobblemon · Java 1.21.1 · modded</p>
  <h1>Crispymon: a Cobblemon server with gyms, trainers, breeding and trading</h1>
  <p class="lede measure">Crispymon is the Crispy community's Cobblemon server: catch, train and battle creatures across a big modded world, earn gym badges, take on trainers, breed for the perfect team and trade with other players. It runs Cobblemon 1.8 on Minecraft 1.21.1 with about 150 mods.</p>
  <div class="join compact"><div class="addr-row"><span class="lbl">Java</span><code class="addr">{CRISPYMON}</code><button type="button" class="copy" data-copy="{CRISPYMON}">Copy</button></div></div>
  <p class="note">Modded server: you need the Crispymon modpack (Java Edition 1.21.1). {get_pack}.</p>
</section>
<section class="wrap block prose">
  <h2>Catch, train and battle</h2>
  <p>Cobblemon brings catchable creatures into Minecraft: find them in the wild, battle and catch them, level them up and build a team. On Crispymon wild creatures can fight back too, and catching them earns you XP. Healing centers patch your team up between fights, and you can ride many of your creatures around the world.</p>

  <h2>Gyms, badges and trainers</h2>
  <p>Take on gyms, each with its own trainers and a leader to beat for its badge, and collect the set. On the road you'll meet trainers ready to battle, and legendary monuments and myth-and-legend structures hide some of the rarest encounters in the game.</p>

  <h2>Breeding</h2>
  <p>Breed your creatures to pass on moves and stats, and work toward the team you actually want instead of whatever you caught first.</p>

  <h2>Trading and the economy</h2>
  <ul>
    <li><b>Global trade station:</b> list creatures and items for other players to buy, and browse what everyone else is selling, even when they're offline.</li>
    <li><b>Money and shops:</b> earn coins as you play, buy supplies at the server shop, and set up chest shops of your own to sell to other players.</li>
    <li><b>Gacha machines and a trading card game:</b> extra ways to spend your coins and collect.</li>
  </ul>

  <h2>A big world to explore</h2>
  <p>Crispymon's world uses Terralith and Oh The Biomes We've Gone for far more varied terrain than vanilla, with new towns, temples, dungeons, towers and ocean ruins from YUNG's mods, Tidal Towns, Towns and Towers and more, plus extra Cobblemon structures to find. Waystones let you travel back to places you've found, and JourneyMap draws your map as you go.</p>

  <h2>Build, farm and settle in</h2>
  <p>Claim your land so it stays yours, then fill it with furniture, Macaw's doors, windows and bridges, Farmer's Delight cooking, Supplementaries decorations and Sophisticated Backpacks and Storage for everything you collect. Your creatures can even help out around your base.</p>

  <h2>How to join Crispymon</h2>
  <ol class="steps">
    <li>{get_pack}, and install it with the CurseForge app (or any launcher that imports CurseForge modpacks, such as Prism Launcher).</li>
    <li>Give Minecraft at least 4 GB of memory in the launcher, ideally 6 GB.</li>
    <li>Add the server <code>{CRISPYMON}</code> and join.</li>
  </ol>
  <p>On a lower-end PC or laptop, keep render distance around 6 to 8 and leave shaders and Distant Horizons off.</p>

  <h2>Part of the Crispy community</h2>
  <p>Crispymon has its own address and world, but shares the Crispy <a href="{DISCORD}" rel="noopener">Discord</a> with our <a href="/anarchy/">anarchy server</a>, <a href="/skyblock/">Skyblock</a>, <a href="/pvp/">Multiverse PvP</a> and <a href="/extraction-zone/">Extraction Zone</a>. Pick the Modded Minecraft role in the Discord's welcome channel to see the Crispymon channels.</p>
</section>
<section class="wrap block"><h2>Crispymon questions</h2><div class="faq">{faq_html(qas)}</div></section>
"""
    server = {"@type": "GameServer", "@id": SITE + "/crispymon/#server", "name": "Crispymon Cobblemon server", "url": SITE + "/crispymon/",
              "game": {"@type": "VideoGame", "name": "Minecraft", "gamePlatform": ["PC (Java Edition)"]}, "serverStatus": "OnlineServerStatus",
              "provider": {"@id": SITE + "/#org"}, "description": f"Cobblemon 1.8 server on Minecraft 1.21.1 (modded). Address {CRISPYMON}."}
    return page("/crispymon/", "Cobblemon Server – Crispymon: Gyms, Trainers, Breeding & Trading (1.21.1)",
                f"Crispymon is a Cobblemon server for Minecraft 1.21.1: catch and battle creatures, earn gym badges, battle trainers, breed and trade on a global trade station. Modded Java, join at {CRISPYMON}.",
                body, crumbs=[("/crispymon/", "Crispymon")], extra_ld=[server, faq_ld(qas)])


def bedrock_skyblock():
    blocks = "".join(f"<div><h2>{e(k)}</h2><ol class='steps'>{''.join(f'<li>{e(x.replace(chr(10), ' '))}</li>' for x in v[:-1])}<li>Save, then join. You arrive in the lobby: pick <b>Skyblock</b>.</li></ol></div>"
                     for k, v in BEDROCK_STEPS.items())
    qas = [
        ("Is there a Minecraft Bedrock Skyblock server?",
         f"Yes. Crispy Skyblock accepts Bedrock Edition players on Windows, phones, tablets and consoles at {JAVA}, port {BEDROCK_PORT}. Pick Skyblock in the lobby."),
        ("Can Bedrock and Java players play Skyblock together?",
         "Yes. Bedrock and Java players share the same Skyblock world, the same Bazaar and the same chat, and can be members of the same island."),
        ("What port does Crispy Skyblock use on Bedrock?",
         f"Port {BEDROCK_PORT}, not the default 19132. The address is {JAVA}."),
        ("Is Crispy Skyblock free on Bedrock?",
         "Yes. You sign in with the Microsoft account you already use for Minecraft Bedrock, and there's nothing to buy to play."),
    ]
    howtos = [{"@type": "HowTo", "name": f"Join Crispy Skyblock on Minecraft Bedrock ({k})",
               "step": [{"@type": "HowToStep", "position": i + 1, "text": x} for i, x in enumerate(v[:-1] + ["Save, then join. You arrive in the lobby: pick Skyblock."])]}
              for k, v in BEDROCK_STEPS.items()]
    body = f"""
<section class="wrap block head">
  <p class="kicker">Bedrock Skyblock · crossplay with Java</p>
  <h1>A Minecraft Bedrock Skyblock server, shared with Java players</h1>
  <p class="lede measure">Crispy Skyblock isn't Java-only. Bedrock Edition players on Windows, phones, tablets, Xbox, PlayStation and Switch join the same Skyblock world as Java players, with the same skills, minions, pets and player Bazaar, and no pay-to-win.</p>
  {join_box(True)}
</section>
<section class="wrap block two">{blocks}</section>
<section class="wrap block prose">
  <h2>What Bedrock players get on Skyblock</h2>
  <ul>
    <li>Your own island: seven themed starter islands to choose from, island upgrades and co-op with up to 8 members.</li>
    <li>Five skills, 68 collections, 26 challenges and an island level on the Top Islands board.</li>
    <li>43 kinds of minions that keep working while you're offline, and pets that boost your skills.</li>
    <li>The same player-run Bazaar as Java players, so you trade with everyone.</li>
    <li>Your island's own Nether and End with bosses, and the shared resource zones.</li>
    <li>No PvP anywhere on Skyblock, and nothing that makes you stronger is sold for real money.</li>
  </ul>
  <p>Everything is described on the main <a href="/skyblock/">Crispy Skyblock page</a>, and the <a href="/guides/skyblock-beginners/">beginner's guide</a> covers your first hours.</p>
  <h2>Playing on Bedrock</h2>
  <p>Bedrock players connect through a translation layer, so a few custom menus and item textures look slightly different from Java. Everything still works the same way. If something doesn't, tell us in the <a href="{DISCORD}" rel="noopener">Discord</a>.</p>
  <h2>Can't connect?</h2>
  <ul>
    <li>Check the port is <b>{BEDROCK_PORT}</b>. The default 19132 won't work.</li>
    <li>Update Minecraft: the server supports the current Bedrock version.</li>
    <li>On a console, make sure the DNS change saved and that you joined a featured server to open the list.</li>
  </ul>
</section>
<section class="wrap block"><h2>Bedrock Skyblock questions</h2><div class="faq">{faq_html(qas)}</div></section>
"""
    return page("/bedrock-skyblock/", "Bedrock Skyblock Server – Crossplay with Java, No P2W | Crispy Skyblock",
                f"Crispy Skyblock is a Minecraft Bedrock Skyblock server shared with Java players: skills, 43 minions, pets and a player Bazaar, no pay-to-win. Join at {JAVA} port {BEDROCK_PORT} on Windows, mobile and console.",
                body, crumbs=[("/skyblock/", "Skyblock"), ("/bedrock-skyblock/", "Bedrock Skyblock")], extra_ld=howtos + [faq_ld(qas)],
                image="/img/shots/skyblock-hub.webp")


def vanilla_anarchy():
    qas = [
        ("What is a vanilla anarchy server?",
         "An anarchy server with no gameplay rules that also keeps the game itself close to vanilla: no custom items, enchantments or shops. Survival the way Minecraft ships it, with nobody protecting anything."),
        ("How do I join Crispy's Vanilla Anarchy?",
         f"Join {JAVA} (Bedrock: port {BEDROCK_PORT}) and pick Vanilla Anarchy in the lobby's Pick a Server menu."),
        ("Is Vanilla Anarchy the same world as Crispy Anarchy?",
         "No. Vanilla Anarchy is a separate world on its own server. Crispy Anarchy is the main world, with custom enchantments, implants and a market on top of anarchy."),
        ("Does Vanilla Anarchy have rules?",
         "No gameplay rules: griefing, raiding and PvP are all allowed. Only the network's community rules apply: no hate speech or hateful builds, no real-life harassment, threats or doxxing, and no spam."),
    ]
    body = f"""
<section class="wrap block head">
  <p class="kicker">Vanilla Anarchy · Java + Bedrock</p>
  <h1>Vanilla anarchy server: plain survival, no rules, no custom items</h1>
  <p class="lede measure">Vanilla Anarchy is the Crispy network's pure anarchy server: survival with no gameplay rules and no land claims, and none of the custom enchantments, implants or shops of our main anarchy world. Just Minecraft, other players, and whatever you can hold on to.</p>
  {join_box(True)}
</section>
<section class="wrap block prose">
  <h2>Anarchy without the extras</h2>
  <p>Some players want anarchy exactly as the game ships it: no custom gear to chase, no economy, no shops, nothing you can buy an edge with. That's what Vanilla Anarchy is for. Your gear comes from mining, enchanting tables, villagers and whatever you can take from other players.</p>
  <ul>
    <li><b>No gameplay rules.</b> Griefing, raiding, stealing and PvP are all part of the game.</li>
    <li><b>No claims and no protection.</b> Anything you build can be found and taken apart.</li>
    <li><b>No custom items.</b> No custom enchantments, no implants, no market. Survival as Mojang made it.</li>
    <li><b>Random spawns.</b> New players land somewhere random, so nobody can camp the spawn point.</li>
    <li><b>Chat reports off.</b> The server runs No Chat Reports, so messages can't be reported to Mojang through the game.</li>
    <li><b>Java and Bedrock.</b> Java Edition 1.13 to 26.3 and Bedrock players on Windows, phones, tablets and consoles share the same world.</li>
  </ul>

  <h2>Vanilla Anarchy or Crispy Anarchy?</h2>
  <p>Both have no gameplay rules. The difference is what sits on top:</p>
</section>
<section class="wrap block"><div class="tablewrap"><table class="modes"><thead><tr><th></th><th>Vanilla Anarchy</th><th>Crispy Anarchy</th></tr></thead><tbody>
<tr><td>Gameplay rules</td><td>None</td><td>None</td></tr>
<tr><td>Custom enchantments</td><td>No</td><td>193, in nine tiers</td></tr>
<tr><td>Implants</td><td>No</td><td>Cyberpunk implants from the Ripperdoc</td></tr>
<tr><td>Market and economy</td><td>No</td><td>Villager market, Gold Coins, a bank and a crypto exchange</td></tr>
<tr><td>World</td><td>Its own world</td><td>One world since 2020, never reset</td></tr>
</tbody></table></div></section>
<section class="wrap block prose">
  <p>Both are on the same network, so you can switch between them from the lobby any time, and the chat is shared. Read more about the main world on the <a href="/anarchy/">Crispy Anarchy page</a>, or see the <a href="/guides/anarchy-survival/">anarchy survival guide</a> before you jump in. The tips there work on both servers.</p>

  <h2>How to join Vanilla Anarchy</h2>
  <ol class="steps">
    <li>Java Edition: add the server <code>{JAVA}</code>. Bedrock Edition: add <code>{JAVA}</code> with port <code>{BEDROCK_PORT}</code>.</li>
    <li>Join: you arrive in the lobby.</li>
    <li>Use the Pick a Server item in your hotbar and choose <b>Vanilla Anarchy</b>.</li>
  </ol>
  <p>The only rules are the <a href="/rules/">community rules</a> that apply on every server.</p>
</section>
<section class="wrap block"><h2>Vanilla Anarchy questions</h2><div class="faq">{faq_html(qas)}</div></section>
"""
    return page("/vanilla-anarchy/", "Vanilla Anarchy Server – No Rules, No Custom Items (Java & Bedrock) | Crispy Anarchy",
                f"A Minecraft vanilla anarchy server: plain survival with no gameplay rules, no claims and no custom items. Random spawns, chat reports off, Java & Bedrock. Join at {JAVA} and pick Vanilla Anarchy.",
                body, crumbs=[("/anarchy/", "Anarchy"), ("/vanilla-anarchy/", "Vanilla Anarchy")], extra_ld=[faq_ld(qas)])


def alt_2b2t():
    qas = [
        ("Is there a Minecraft server like 2b2t?",
         f"Yes. Crispy Anarchy works the same way: no gameplay rules, no claims, and a world that is never reset (it has run since 2020). Unlike 2b2t, Bedrock players can join too, at {JAVA} port {BEDROCK_PORT}."),
        ("Can Bedrock players play on an anarchy server like 2b2t?",
         f"2b2t is a Java Edition server. Crispy Anarchy lets Bedrock Edition players on Windows, phones, tablets and consoles join the same anarchy world as Java players, at {JAVA} port {BEDROCK_PORT}."),
        ("Is Crispy Anarchy a 2b2t clone?",
         "No. It shares the anarchy idea, but it's its own server and world, with extras 2b2t doesn't have: 193 custom enchantments, cyberpunk implants, a market with a crypto exchange and a hidden black market. There's also a Vanilla Anarchy server for anyone who wants plain survival anarchy."),
    ]
    body = f"""
<section class="wrap block head">
  <p class="kicker">Anarchy servers like 2b2t</p>
  <h1>Looking for a Minecraft server like 2b2t?</h1>
  <p class="lede measure">2b2t is the best-known Minecraft anarchy server: a Java Edition world with no rules that has run since 2010. If that's the kind of game you want, Crispy Anarchy runs on the same idea: no gameplay rules, no claims and a world that's never reset, running since 2020. Here's what's the same and what's different.</p>
  {join_box(True)}
</section>
<section class="wrap block prose">
  <h2>What's the same</h2>
  <ul>
    <li><b>No gameplay rules.</b> Griefing, raiding, stealing and PvP are all allowed, and staff don't step in.</li>
    <li><b>No land claims.</b> Nothing is protected. Hiding your base well is the only defence.</li>
    <li><b>A world that's never reset.</b> Crispy Anarchy's world started in 2020 and has never been wiped, so the land around spawn carries years of history. You can fly over it on the <a href="/spawn-map/">3D spawn map</a>.</li>
    <li><b>Chat reports off.</b> The server runs No Chat Reports.</li>
  </ul>

  <h2>What's different</h2>
  <ul>
    <li><b>Bedrock players can join.</b> 2b2t is Java Edition only. On Crispy Anarchy, Bedrock players on Windows, phones, tablets and consoles play in the same world as Java players. See <a href="/bedrock-anarchy/">Bedrock anarchy</a>.</li>
    <li><b>Custom content on top of anarchy.</b> 193 custom enchantments in nine tiers, cyberpunk implants from a Ripperdoc, a villager market with Gold Coins, a bank, a crypto exchange with a moving price, and a black market you have to find yourself. All without mods.</li>
    <li><b>A pure option too.</b> If you'd rather have anarchy exactly as the game ships it, <a href="/vanilla-anarchy/">Vanilla Anarchy</a> is a separate world with no custom items at all.</li>
    <li><b>A smaller community.</b> You meet the same faces quickly and can join a clan (<code>/clan list</code>), and there's a shared chat and Discord with the rest of the network.</li>
    <li><b>More to play on the same network.</b> When you need a break from anarchy: <a href="/skyblock/">Skyblock</a>, <a href="/pvp/">Multiverse PvP</a> and <a href="/extraction-zone/">Extraction Zone</a>.</li>
  </ul>

  <h2>Rules, honestly</h2>
  <p>There are no gameplay rules, but there are a few <a href="/rules/">community rules</a> about people, on every server: no hate speech or hateful builds, no real-life harassment, threats or doxxing, and no spam.</p>

  <h2>Before you join</h2>
  <p>New players land somewhere random near the old spawn, the most wrecked part of the map. Read the <a href="/guides/anarchy-survival/">anarchy survival guide</a> first: it covers getting out of spawn alive, keeping your base hidden and what the market is for.</p>
</section>
<section class="wrap block"><h2>Questions</h2><div class="faq">{faq_html(qas)}</div></section>
"""
    return page("/2b2t-alternative/", "Minecraft Servers Like 2b2t – An Anarchy Server for Java & Bedrock | Crispy Anarchy",
                "Looking for a Minecraft server like 2b2t? Crispy Anarchy has no gameplay rules, no claims and a world never reset since 2020, and Bedrock players can join too. What's the same and what's different.",
                body, crumbs=[("/anarchy/", "Anarchy"), ("/2b2t-alternative/", "Servers like 2b2t")], extra_ld=[faq_ld(qas)], image="/img/low.webp")


def guide(path, title, desc, h1, kicker, intro, steps, outro, crumb, image="/img/og.jpg"):
    """A how-to guide: numbered sections (each a heading and paragraphs), HowTo structured data."""
    secs = "".join(f'<h2 id="s{i + 1}">{i + 1}. {e(h)}</h2>' + "".join(f"<p>{p}</p>" for p in ps) for i, (h, ps) in enumerate(steps))
    toc = "".join(f'<li><a href="#s{i + 1}">{e(h)}</a></li>' for i, (h, _) in enumerate(steps))
    howto = {"@type": "HowTo", "name": h1, "description": desc,
             "step": [{"@type": "HowToStep", "position": i + 1, "name": h, "text": re.sub(r"<[^>]+>", "", " ".join(ps)), "url": SITE + path + f"#s{i + 1}"}
                      for i, (h, ps) in enumerate(steps)]}
    body = f"""
<article class="wrap block head prose">
  <p class="kicker">{kicker}</p>
  <h1>{e(h1)}</h1>
  <p class="lede">{intro}</p>
  <p><b>In this guide:</b></p><ol class="steps">{toc}</ol>
  {secs}
  {outro}
</article>
<section class="wrap block"><h2>Ready?</h2>{join_box(True)}</section>
"""
    return page(path, title, desc, body, crumbs=[crumb, (path, h1)], extra_ld=[howto], image=image)


def guide_anarchy():
    steps = [
        ("Get away from spawn", [
            "New players land somewhere random near the old spawn, the most griefed part of the map: lava casts, holes and players who come back to hunt newcomers. Don't settle there. Gather wood, food and a few tools, and head out.",
            "The further you go, the more untouched land you find. A couple of thousand blocks is a start; many players go much further. Travelling in the Nether covers eight blocks of overworld for every block you walk."]),
        ("Set your respawn point", [
            "Sleep in a bed as soon as you can. Without one, you respawn somewhere random when you die. A bed in a hidden spot far from spawn means a death doesn't throw you back to the start."]),
        ("Use your ender chest", [
            "An ender chest is the only storage nobody else can open: its contents belong to you, whichever ender chest you open. Keep your best gear and anything you can't afford to lose in it, and carry a spare ender chest so you can reach it anywhere."]),
        ("Hide your base", [
            "There are no claims, so nothing protects your base except nobody finding it. Build away from highways, portals and other players' paths, don't leave trails such as torches or bridges leading to it, and think twice before sharing coordinates. Yoink, our Discord bot, hides coordinates when it relays game chat to Discord, but anyone on the server can still read them in game."]),
        ("Know what you can lose", [
            "When you die you drop everything you carry, and anyone can pick it up. Don't carry your best things on a trip you might not survive. The one exception is the market: PvP is on there, but if you're killed in the market you keep your items, XP and implants."]),
        ("Use the market", [
            "Type <code>/trigger market</code> to reach the market. The Enchanter sells random custom enchantment books for XP (there are 193 enchantments in nine tiers), the Ripperdoc fits cyberpunk implants for diamonds or netherite, and the Banker turns emeralds or diamonds into Gold Coins for the villager shops. There's also a crypto trader whose Bitcoin price moves like the real thing."]),
        ("Expect the combat tag", [
            "Hitting or being hit by another player puts you in combat for 15 seconds. Until it runs out you can't escape with <code>/home</code>, <code>/spawn</code>, <code>/back</code>, <code>/tpa</code>, <code>/lobby</code> and similar commands. Win the fight or run on foot."]),
        ("Find people, or don't", [
            "You can play alone, but a group is safer and builds faster. <code>/clan list</code> shows the clans, and you can ask in chat to join one or make your own with <code>/clan create</code>. Chat is shared with every Crispy server and the Discord. Just remember anyone can turn on you: it's anarchy."]),
        ("Look for the black market", [
            "Somewhere in the world there's a black market. Its location isn't published. Find it once and you earn the [Black Market] tag, which some merchants ask for before they'll deal with you."]),
    ]
    outro = """<h2>Still stuck?</h2><p>Type <code>/trigger cw_help</code> in game for the survival tips any time, or ask in chat with <code>!ask &lt;question&gt;</code> and Yoink answers. More answers are in the <a href="/faq/">FAQ</a>, and the server itself is described on the <a href="/anarchy/">Crispy Anarchy page</a>. Prefer it with no custom items? Try <a href="/vanilla-anarchy/">Vanilla Anarchy</a>.</p>"""
    return guide("/guides/anarchy-survival/", "How to Survive on a Minecraft Anarchy Server – Beginner's Guide | Crispy Anarchy",
                 "A beginner's guide to surviving on a Minecraft anarchy server: getting away from spawn, respawn points, ender chests, hiding your base, the market, the combat tag and clans.",
                 "How to survive on a Minecraft anarchy server", "Guide · Anarchy",
                 "Anarchy servers have no rules and no protection, so your first hour decides a lot. These are the habits that keep new players alive on Crispy Anarchy, and most of them work on any anarchy server.",
                 steps, outro, ("/anarchy/", "Anarchy"), image="/img/low.webp")


def guide_skyblock():
    steps = [
        ("Pick your starter island", [
            "The first time you go to your island you choose one of seven. Classic is the safest start: plenty of dirt and a chest with lava and ice for a cobblestone generator. Mushroom Isle has no hostile mobs. Desert Oasis is the hardest: no rain, and dirt only from the chest."]),
        ("Don't fall, and read the Guide", [
            "The void is below every island. Build carefully and keep a few blocks spare. You get a Skyblock Guide book on joining: right-click it (or type <code>/guide</code>) for how-to pages and a recipe viewer. Lost it? <code>/guide book</code>."]),
        ("Build a cobblestone generator", [
            "Lava next to flowing water makes cobblestone, and that's your supply of stone for building and tools. Mining generator cobblestone also counts for the Mining skill. Later, the ore generator upgrade makes it sometimes produce ore."]),
        ("Grow a farm and plant trees", [
            "Plant the saplings and seeds from your chest straight away. Farming and Foraging level up as you harvest, and every level gives a chance of double drops. Only fully grown crops give XP, and blocks you placed yourself don't count, so you can't level by placing and breaking."]),
        ("Work through the challenges", [
            "<code>/challenges</code> has 26 one-time hand-ins, from easy ones you can do on day one to hard ones that need an island level. They pay resources, spawn eggs and XP, and they're the quickest way to get things the island can't make yet."]),
        ("Craft your first minion", [
            "Minions collect a resource for you and keep going while you're offline until their storage is full. Your island starts with five minion slots. Every minion recipe is in your recipe book: craft one, place it, and collect from it when you come back."]),
        ("Watch the sky", [
            "While you play, things drop onto your island: an animal every 15 minutes, a supply crate every 25, an ore meteor every 45, and dungeons at 30, 90 and 180 minutes of island play time. Clear the dungeons for loot. At 150 minutes an End portal arrives."]),
        ("Visit the hub and trade", [
            "Walk through the portal on your island to reach the hub. Merchants there sell supplies (also from anywhere with <code>/shop</code>), and the Bazaar (<code>/bazaar</code>) is where players trade with buy and sell orders at their own prices. Collections and skills keep paying coins as you go, too."]),
        ("Go to the resource zones", [
            "The hub's portals lead to the Deep Mines (ores that grow back) and the Whispering Woods (logs that grow back), both with levelled mobs. If you die there you only drop what you gathered there; your own gear and XP come back when you respawn."]),
        ("Upgrade, invite friends and take on bosses", [
            "Spend coins in <code>/island upgrades</code> on size, minion slots, co-op slots and the ore generator. <code>/invite &lt;player&gt;</code> adds friends to your island. When you're well geared, your island's own Nether and End each have a boss altar: every member gets coins and loot for each kill, and End bosses can drop the rare Phoenix pet."]),
    ]
    outro = """<h2>Keep going</h2><p>Everything on Skyblock is on the <a href="/skyblock/">Crispy Skyblock page</a>. Playing on a phone or console? See <a href="/bedrock-skyblock/">Skyblock on Bedrock</a>. And if you get stuck, ask in game chat with <code>!ask &lt;question&gt;</code> and Yoink answers.</p>"""
    return guide("/guides/skyblock-beginners/", "Minecraft Skyblock Beginner's Guide: Your First Hours | Crispy Skyblock",
                 "A beginner's guide to Crispy Skyblock: picking a starter island, a cobblestone generator, farms, challenges, your first minion, sky drops, the Bazaar, resource zones, upgrades and bosses.",
                 "Crispy Skyblock beginner's guide: your first hours", "Guide · Skyblock",
                 "Starting on a few blocks over the void can feel slow. This guide covers what to do first on Crispy Skyblock and what to aim for next, so you're not stuck wondering where to go.",
                 steps, outro, ("/skyblock/", "Skyblock"), image="/img/shots/skyblock-hub.webp")


def pvp():
    modes = [
        ("#arena", "PvP Arena", "Any number", "Drop in as any character and fight on a map that changes every 10 minutes."),
        ("#duels", "Duels", "1 v 1", "Challenge a player, both get a random character, and the result counts toward your rating."),
        ("#outbreak", "Outbreak", "Solo or co-op", "Survive endless zombie waves, earn points, buy guns and upgrades, and fight a boss every 5 waves."),
        ("#core", "Core Defense", "Solo or co-op", "Build walls and traps on real terrain to keep a core alive while mobs dig toward it."),
        ("#tower", "The Tower", "1 to 4", "A roguelite climb: fight floor after floor, beat challenges and bosses, and stack upgrades."),
        ("#micro", "Micro Outbreak", "Solo or co-op", "Zombie waves at 1/16 scale, as toy soldiers in a giant room under the lobby."),
    ]
    rows = "".join(f'<tr><td><a href="{a}">{n}</a></td><td>{p}</td><td>{d}</td></tr>' for a, n, p, d in modes)
    qas = [
        ("Can I play Multiverse alone?",
         "Yes. Outbreak, Core Defense, The Tower and Micro Outbreak all work solo, and get harder with more players. The PvP Arena and Duels need other players."),
        ("How many characters are there?",
         "36. Each has its own weapon, armour and two right-click abilities with cooldowns, and some carry guns. A Random character button picks one for you."),
        ("Does gear carry over between games?",
         "No. Every game starts from your character's kit, so nobody can grind an unfair advantage in PvP. Progress you keep is your mastery level for each character, your ratings and records, and the tags you earn."),
        ("Do I need mods to play?",
         f"No. Everything works on the normal game, on Java Edition 1.13 to 26.3 and on Bedrock ({JAVA}, port {BEDROCK_PORT})."),
        ("Is it free?", "Yes. Every character is free to play, and everyone in a game starts from the same kit."),
    ]
    body = f"""
<section class="wrap block head">
  <p class="kicker">Multiverse · PvP and PvE · Java + Bedrock</p>
  <h1>Multiverse: a Minecraft PvP and zombies server with 36 playable characters</h1>
  <p class="lede measure">Multiverse is the Crispy network's action server. Pick one of 36 characters from famous shows and games, each with its own weapons and abilities, then fight other players in the arena or a ranked duel, or team up against zombie waves, defend a core, or climb a roguelite tower. Most modes work solo, so there is always something to play.</p>
  {join_box(True)}
</section>
<figure class="wrap shot"><img src="/img/shots/mv-lobby.webp" alt="The Multiverse lobby on the Crispy network: character statues on pedestals under a purple MULTIVERSE sign" width="1600" height="900"><figcaption>The Multiverse lobby, where every mode starts.</figcaption></figure>
<section class="wrap block">
  <h2>The modes at a glance</h2>
  <div class="tablewrap"><table class="modes"><thead><tr><th>Mode</th><th>Players</th><th>What it is</th></tr></thead><tbody>{rows}</tbody></table></div>
</section>
<section class="wrap block prose">
  <h2 id="characters">36 characters, each with abilities</h2>
  <p>Every kit is a character: heroes, villains, cartoon favourites, game mascots and more. Each has its own weapon and armour plus <b>two abilities</b> in the hotbar: right-click to use one, and a cooldown sweep shows when it's ready again. Abilities include force pushes, fireballs, dashes, shields, grenades, lightning and hookshots. Some characters carry <b>guns</b>: they fire instantly where you aim, with no arrows to carry, and shotguns hit everything in a short cone.</p>
  <p>Can't decide? The <b>Random character</b> button picks one for you.</p>
  {fig("mv-characters", "The Multiverse character menu: a chest menu of 36 character heads to pick from", "Pick a character: 36 to choose from, or a random one.")}
  <h3>Character mastery</h3>
  <p>Every character levels up separately. You earn mastery XP for that character with PvP kills (+10), Outbreak kills (+1) and Tower floors (+5). Levels I to V unlock at 50, 150, 400, 800 and 1,500 XP. Level V is <b>Master</b>: it's announced to the whole server, gives you a sparkle aura while you play that character, and earns the network-wide <b>[Kit Master]</b> chat tag.</p>

  <h2 id="arena">PvP Arena</h2>
  <p>Talk to the PvP Arena NPC, pick a character, and you drop into the current arena with three seconds of spawn protection. The arena <b>rotates every 10 minutes</b> through eleven maps: a Roman colosseum and ten themed worlds, including a lava mining outpost, a swamp, a farm, a suburban street, an underwater town, a mushroom castle, a nuclear-plant town, a desert town, a checkered hill zone with a loop-de-loop and a back alley. A boss bar counts down to the next map, and everyone fighting moves across together.</p>
  <ul>
    <li>A kill heals you and gives you ten seconds of extra hearts and a golden apple.</li>
    <li>Kill streaks are announced at 3, 5, 10 and up.</li>
    <li>Watch from the stands: spectators can walk around the rim but can't be hurt.</li>
    <li>The lobby leaderboard shows the top kills and best streaks.</li>
  </ul>

  <h2 id="duels">Duels</h2>
  <p>Everyone in the lobby has a <b>Duel Challenge</b> item. Look at a player and right-click to challenge them; they get Accept and Decline buttons. You both fight in a private duel pit as a <b>random character</b>, rolled separately for each of you, so it comes down to skill, not a favourite pick. Duels are ranked with an Elo rating that starts at 1,000. The player with the top rating wears the <b>[Champion]</b> tag.</p>

  <h2 id="outbreak">Outbreak: zombie wave survival</h2>
  <p>Survive as many waves as you can, alone or with friends. One player opens a lobby and picks a map, others join with a click, and the leader starts the run. Friends can also drop in to a run that's already going at the next wave break.</p>
  {fig("mv-outbreak", "Zombies and vindicators closing in during an Outbreak wave on the Ruins map", "A wave closing in on the Ruins map.")}
  <ul>
    <li><b>Waves</b> get bigger and tougher every round, with new mob types unlocking as you go. Every fifth wave brings a giant boss.</li>
    <li><b>Points</b>: 100 per kill plus a bonus for everyone still standing when a wave is cleared.</li>
    <li><b>The Arsenal</b> in the middle of the map sells healing, food, perk drinks (extra hearts, speed, strength and more), armour upgrades, and a <b>weapon upgrade</b> in four tiers for whatever you're holding, including guns.</li>
    <li><b>Wall guns</b>: four guns per map are mounted on the walls to buy, from a pistol to an assault rifle. Hold a handgun in each hand to dual-wield them: one click fires both.</li>
    <li><b>The Mystery Box</b> rolls one of 19 prizes: powerful wonder weapons, character gear and abilities, guns, or a teddy bear and half your points back.</li>
    <li><b>Power-ups</b> drop from kills: revive the whole team, one-hit kills, double points, or a nuke that wipes the wave.</li>
    <li><b>Revive</b> a downed teammate by crouching next to them for three seconds.</li>
    <li><b>A secret weapon</b>: collect power cells from boss waves and assemble something much bigger at the Arsenal.</li>
  </ul>
  {figs(("mv-wallgun", "A rifle mounted on a pillar to buy for 1,250 points in Outbreak", "Wall guns: right-click to buy."), ("mv-arsenal", "The Outbreak Arsenal menu showing the Mystery Box for 950 points", "The Arsenal, with the Mystery Box."))}
  <p>There are five maps, each with its own layout: <b>Ruins</b> (an overgrown courtyard), <b>Toxic Mine</b> (a cave with mine-cart tracks and sludge), <b>Neon City</b> (a night-time crossroads), <b>Hellfort</b> (a keep surrounded by lava) and <b>Orbital Station</b> (a wheel-shaped space station). Your best wave goes on the lobby leaderboard, and a new server record is announced to everyone.</p>

  <h2 id="core">Core Defense</h2>
  <p>An Outbreak map with a twist: instead of surviving, you protect a <b>core</b> in the middle of real Minecraft terrain. You get 90 seconds to build before the first wave, in survival mode with tools and blocks, and the Arsenal sells planks, stone, obsidian, iron bars, cobwebs, magma, water and lava to build defences.</p>
  {figs(("mv-core", "The glowing core on a mossy stone pad in a forest clearing in Core Defense", "The core you have to protect."), ("mv-core-arsenal", "The Core Defense Arsenal menu with weapons, perks, building blocks and traps", "Core Defense's Arsenal: weapons, blocks and traps."))}
  <ul>
    <li>The core has 100 health and heals a little after every wave. If it reaches zero, the run is over.</li>
    <li>Mobs head straight for the core and <b>dig through your walls</b>, slower through stone and obsidian. Builders bridge gaps and cover lava, Breakers chew through walls faster, and from wave 6 Firewalkers ignore lava moats.</li>
    <li>Every fifth wave the <b>Warlord</b> arrives: he digs four times as fast and calls in Builders.</li>
    <li>While the core stands, dying just sends you back after five seconds with your inventory.</li>
  </ul>

  <h2 id="tower">The Tower: a roguelite climb</h2>
  <p>Climb as high as you can, solo or with up to three friends, starting as a random character.</p>
  {fig("mv-tower", "Zombies coming at the player across a stone-brick floor in The Tower", "Fighting through a mob floor.")}
  <ul>
    <li><b>Mob floors</b> get harder as you go, with new mob types every five floors.</li>
    <li><b>Challenge floors</b> every third floor: a parkour run over magma, a glass bridge where one pane in every row is fake, a hedge maze against the clock, or a crafting challenge with materials hidden in barrels. Three strikes on a floor and you're out.</li>
    <li><b>Bosses</b> every fifth floor: the Brute, the Bone King, the Warlord and the Beast, each tougher than the last.</li>
    <li><b>Upgrades</b>: after each floor, pick 1 of 3. They stack for the whole climb and come in four rarities, from common boosts like extra health and speed to rare lifesteal and critical hits, epic extra lives and lightning, and legendary attack drones and black holes.</li>
  </ul>
  <p>Your best floor goes on the lobby leaderboard.</p>

  <h2 id="micro">Micro Outbreak</h2>
  <p>Outbreak at <b>1/16 scale</b>. You play a tiny toy soldier in a toy room built under the lobby's glass floor, so everyone in the lobby can watch from above. Bookshelves are pillars and toy blocks are platforms. You fight shrunken mobs with a bayonet and a toy rifle, earn points, and upgrade your gear at a miniature Arsenal between waves.</p>
  {figs(("mv-micro-above", "The Micro Outbreak toy room seen from the lobby through its glass floor", "From the lobby, looking down through the glass."), ("mv-micro-inside", "Inside Micro Outbreak: a tiny toy soldier among giant bookshelves and toy blocks, with mobs in the distance", "Down at toy-soldier size."))}

  <h2>Leaderboards and tags</h2>
  <p>The lobby leaderboard shows the top three for kills, best kill streak, duel rating, best Outbreak wave and best Tower floor. Earned tags like <b>[Champion]</b> and <b>[Kit Master]</b> show in chat on every server on the network.</p>

  <h2>How to get there</h2>
  <p>Join <code>{JAVA}</code> on Java Edition, or <code>{JAVA}</code> port <code>{BEDROCK_PORT}</code> on Bedrock, and choose <b>Multiverse</b> in the lobby. See <a href="/join/">how to join</a> for step-by-step instructions.</p>
</section>
<section class="wrap block"><h2>Multiverse questions</h2><div class="faq">{faq_html(qas)}</div></section>
"""
    return page("/pvp/", "Multiverse – Minecraft PvP & Zombies Server with 36 Characters | Crispy Network",
                "Play as 36 characters with their own abilities: arena PvP, ranked duels, zombie wave survival, Core Defense and a roguelite tower. Solo or co-op, Java & Bedrock at crispyanarchy.net",
                body, crumbs=[("/pvp/", "Multiverse")], extra_ld=[GAMESERVER, faq_ld(qas)], image="/img/shots/mv-outbreak.webp")


def extraction():
    qas = [
        ("Is Extraction Zone open?", "Yes, since Friday 13 November 2026. It replaced the old Factions server on the Crispy network."),
        ("What happens if I log out in the middle of a raid?", "Your raid timer keeps running and a stand-in of you stays where you stood, carrying your gear. Raiders leave it alone, but other players can kill it and take everything. Log back in before your time runs out."),
        ("What happens if I die in the zone?", "You lose everything you carried in. What you left in your bunker is safe, and if you lose everything the Quartermaster sends a basic relief kit."),
        ("Can I team up with other players?", "Yes. Anyone you meet in the zone can become a teammate for the raid, and any teammate can turn on you."),
        ("Do I need mods?", "No. It runs on the normal Minecraft client, Java or Bedrock, through the Crispy lobby."),
    ]
    faq_html = "".join(f"<h3>{e(q)}</h3><p>{e(a)}</p>" for q, a in qas)
    body = f"""
<section class="wrap block head">
  <p class="kicker">Extraction Zone · new · open now · Java + Bedrock</p>
  <h1>Extraction Zone: a Minecraft extraction shooter in a ruined city</h1>
  <p class="lede measure">Drop into a ruined city with the gear you chose to risk, loot what you can, fight armed raiders and other players, and reach an extraction point before the timer runs out. Get out and the loot is yours. Die and you lose everything you brought in.</p>
  {join_box(True)}
</section>
<figure class="wrap shot"><img src="/img/shots/ez-street.webp" alt="A masked raider on a foggy street in the ruined city of Extraction Zone, with overgrown concrete buildings and cobwebs" width="1600" height="900" fetchpriority="high"><figcaption>A raider in the outskirts, out of the haze.</figcaption></figure>
<section class="wrap block prose">
  <h2>How a raid works</h2>
  <ol>
    <li><b>Gear up in camp.</b> Buy guns, ammo, armour and medkits from the Quartermaster with Gold Coins, and take a contract from the Fixer.</li>
    <li><b>Deploy.</b> Board at the helipad and you are dropped on a street at the edge of the zone.</li>
    <li><b>Loot.</b> Search crates in buildings. The closer to the city centre, the better the loot and the tougher the enemies. Crates restock every 10 minutes, and an opened crate shows a countdown above it.</li>
    <li><b>Extract.</b> Reach one of the extraction points and hold it for 30 seconds before the 25-minute timer ends. The flare draws a wave of raiders, so expect a fight.</li>
  </ol>
  {figs(("ez-camp", "The Extraction Zone camp from above: a helipad marked with an H, lamp posts, sandbags and watchtowers", "The camp: gear up, then deploy from the helipad."),
        ("ez-fixer", "The Fixer, a masked trader in a wooden booth, who hands out contracts", "The Fixer hands out contracts before each raid."))}
  <h2>One shared zone with PvP</h2>
  <p>Everyone raids the same city at the same time. Players you meet can team up with you for the raid, and any of them can betray you for what you carry. Trust is part of the loot.</p>
  {figs(("ez-city", "Aerial view of the ruined city in grey fog: cracked streets, tilted buildings and rubble", "The city from above, fading into the haze."),
        ("ez-map", "The Extraction Zone map held in hand, with yellow, orange and magenta rings closing in on the centre", "Your zone map: the rings close in on the Core."))}
  <h2>Downed, not dead</h2>
  <p>A fatal hit puts you on the ground for 45 seconds. Another player can crouch beside you to get you back up, or finish you off and take your gear. A Self-Revive Injector, rare in the inner city or made in your bunker, gets you up on your own.</p>
  <h2>Guns and enemies</h2>
  <p>Pistols, SMGs, shotguns, rifles and a machine gun, each with a magazine you have to reload. Hold a handgun in each hand to dual-wield: one click fires both, at the cost of a little accuracy. The city is held by Infected, Bandit Gunners, Raiders and Riflemen, and the armed ones shoot back. When the shooting has to stop, there are blades: a combat knife, a machete, a fire axe and a sledgehammer.</p>
  {figs(("ez-firefight", "First-person gunfire down a city street at armed raiders by a concrete building", "Trading shots with raiders in the street."),
        ("ez-commander", "The Commander, a heavily armed boss with a red health bar, on a dark street at night", "The Commander, waiting in the Core."))}
  <h2>Contracts, the Commander and zone events</h2>
  <p>The Fixer offers jobs before each raid: recover an intel cache from a district, take out a number of Riflemen, or extract from a particular point. Finish the job and get out alive for bonus coins.</p>
  <p>The Commander, a heavily armed boss with an escort, lands in the city centre and carries the best loot in the zone. Every few minutes something else happens somewhere in the city: a supply drop under a red flare, a helicopter crash guarded by raiders, or a hot extract that pays double for 3 minutes.</p>
  <h2>Money you can lose</h2>
  <p>The Zone runs on Gold Coins, and 64 of them condense into a Coin Bag. Coins are items, so you can only spend what you carry. Traders inside the zone, the Smuggler and the Arms Dealer, sell gear you can't get in camp, so bringing cash in is worth the risk. Sell what you extract to the Broker in camp.</p>
  <h2>Your bunker</h2>
  <p>Every player gets a protected bunker under the camp to store loot, build and decorate. Fill it with stations: sew armour and bandages, brew medkits, reload your own ammo, distil moonshine to sell, make tools like a grappling hook and smoke grenades, and break spare armour and guns down into parts at a Salvage Bench. Upgrades change how you play: a gun workbench for extended magazines and faster reloads, a medical station for cheaper heals, and a field radio that pins down the next zone event. Nobody can raid it.</p>
  {fig("ez-bunker", "A player's underground bunker: stone-tiled floor, a wheat farm, stations along the wall and stairs up to camp", "A bunker with a farm going and stations along the wall.")}
  <h2>A new city every week</h2>
  <p>The city is rebuilt every Monday, so the streets stay clear and there is always fresh ground to search. After every raid you get a recap of your loot, kills and distance, and the best runs are announced to everyone.</p>
  <h2>Questions</h2>
  {faq_html}
  <h2>How to get there</h2>
  <p>Join <code>{JAVA}</code> (Bedrock: port <code>{BEDROCK_PORT}</code>) and choose Extraction Zone in the lobby's server selector.</p>
</section>
"""
    return page("/extraction-zone/", "Extraction Zone – Minecraft Extraction Shooter, PvPvE Looting | Crispy Network",
                "Loot a ruined city with guns, fight armed raiders and players, team up or betray, and extract alive. Now open on the Crispy network. Java & Bedrock, no mods.",
                body, crumbs=[("/extraction-zone/", "Extraction Zone")], extra_ld=[GAMESERVER, faq_ld(qas)], image="/img/shots/ez-street.webp")


def spawn_map():
    body = f"""
<section class="wrap block head">
  <p class="kicker">3D map · 2 × 2 km around spawn</p>
  <h1>Crispy Anarchy spawn in 3D: six years of anarchy you can fly through</h1>
  <p class="lede measure">This is a full 3D render of about two square kilometres around Crispy Anarchy's world spawn (X 287, Z -207), made with BlueMap. Drag to look around, scroll to zoom, and switch to free-flight from the menu.</p>
  <p class="row"><a class="btn" href="/map/">Open the map full screen</a></p>
</section>
<div class="wrap"><div class="mapframe"><iframe src="/map/" title="Interactive 3D map of Crispy Anarchy spawn" loading="lazy" allow="fullscreen"></iframe></div></div>
<section class="wrap block prose">
  <h2>What you are looking at</h2>
  <p>The anarchy world has never been reset since 2020, so spawn shows everything players have done to it: lava casts poured over the land, towering pillars, flattened terrain and ruined walls. Roughly one kilometre in each direction is rendered; further out the land turns back into islands and ocean.</p>
  <p>The two long lines running away from spawn are the axis highways at X = 0 and Z = 0, which players use to get far enough out to build.</p>
  <h2>Want to see it in person?</h2>
  <p>Join <code>{JAVA}</code> on Java Edition, or <code>{JAVA}</code> port <code>{BEDROCK_PORT}</code> on Bedrock, and pick Anarchy in the lobby.</p>
</section>
<figure class="wrap shot"><img src="/img/spawn.webp" alt="3D render of Crispy Anarchy spawn: a towering griefed pillar, lava casts and ruined walls surrounded by ocean" width="1600" height="825" loading="lazy"></figure>
"""
    return page("/spawn-map/", "Crispy Anarchy Spawn 3D Map – Minecraft Anarchy Server Map",
                "Fly through a 3D render of Crispy Anarchy spawn: two square kilometres of a Minecraft anarchy world that has never been reset since 2020.",
                body, crumbs=[("/spawn-map/", "3D Map")], image="/img/og.jpg")


def join():
    steps_java = ["Open Minecraft: Java Edition (any version from 1.13 to 26.3).", "Click Multiplayer, then Add Server.",
                  f"Type {JAVA} as the Server Address. You don't need a port.", "Click Done, then join. You arrive in the lobby: pick a game mode."]
    steps_bedrock = ["Open Minecraft (Bedrock Edition) and go to Play, then Servers.", "Scroll down and choose Add Server.",
                     f"Server Address: {JAVA}. Port: {BEDROCK_PORT}.", "Save and join. You arrive in the lobby: pick a game mode."]
    howto = lambda name, steps: {"@type": "HowTo", "name": name, "step": [{"@type": "HowToStep", "position": i + 1, "text": s} for i, s in enumerate(steps)]}
    ol = lambda steps: "<ol class='steps'>" + "".join(f"<li>{e(s)}</li>" for s in steps) + "</ol>"
    body = f"""
<section class="wrap block head">
  <p class="kicker">How to join</p>
  <h1>How to join Crispy Anarchy on Java and Bedrock</h1>
  <p class="lede measure">The server address is <code>{JAVA}</code> for both editions. Bedrock also needs the port <code>{BEDROCK_PORT}</code>.</p>
  {join_box(True)}
</section>
<section class="wrap block two">
  <div><h2>Java Edition</h2>{ol(steps_java)}</div>
  <div><h2>Bedrock Edition</h2>{ol(steps_bedrock)}<p class="note">Works on Windows, phones and tablets. Consoles need a workaround: see the <a href="/bedrock-anarchy/">Bedrock guide</a>.</p></div>
</section>
<section class="wrap block prose">
  <p>Before you join, read the <a href="/rules/">rules</a>: no gameplay rules and no bans on Anarchy, but no hate speech, harassment, sexual content or spam anywhere.</p>
  <h2>Trouble connecting?</h2>
  <ul>
    <li><b>Java says "outdated client" or "outdated server":</b> use a version between 1.13 and 26.3.</li>
    <li><b>Java says "failed to verify username":</b> you need a paid Java Edition account; the server is not cracked.</li>
    <li><b>Bedrock can't connect:</b> check that the port is {BEDROCK_PORT} (not 19132) and that your game is up to date.</li>
    <li>Still stuck? Ask in our <a href="{DISCORD}" rel="noopener">Discord</a>.</li>
  </ul>
</section>
"""
    return page("/join/", "How to Join Crispy Anarchy – Server IP for Java & Bedrock",
                f"Crispy Anarchy server IP: {JAVA} for Java Edition 1.13–26.3, and {JAVA} port {BEDROCK_PORT} for Bedrock. Step-by-step instructions and fixes for common errors.",
                body, crumbs=[("/join/", "How to join")], extra_ld=[howto("Join Crispy Anarchy on Minecraft Java Edition", steps_java),
                                                                  howto("Join Crispy Anarchy on Minecraft Bedrock Edition", steps_bedrock)])


def vote():
    rows = "".join(f'<li><a href="{u}" rel="noopener">{n}</a>' + (' <span class="note">+1 bonus vote point</span>' if i == 0 else '') + '</li>'
                   for i, (n, u) in enumerate(VOTE))
    body = f"""
<section class="wrap block head">
  <p class="kicker">Vote</p>
  <h1>Vote for Crispy Anarchy</h1>
  <p class="lede measure">Voting every day helps new players find the server, and you get rewards for it on the server of your choice. Enter your exact Minecraft username on each site.</p>
</section>
<section class="wrap block"><ol class="votes">{rows}</ol>
<p class="note">Type <code>/vote</code> in game to see your vote points and claim rewards.</p></section>
<section class="wrap block">
  <h2>Streaks and reminders</h2>
  <ul>
    <li>Each vote is one reward, which you send to Anarchy, Skyblock, Multiverse or Extraction Zone in <code>/vote</code>, plus vote points for cosmetic tags and colours.</li>
    <li>Vote every day for a streak: your first vote each day earns an extra point from day 3, two from day 7 and three from day 14.</li>
    <li>A vote on MinecraftServers.org earns one extra point.</li>
    <li>If you haven't voted today you get a reminder in chat every 90 minutes; switch it off with the bell in <code>/vote</code>. <code>/vote links</code> ticks off the sites you've done today. A new vote day starts at midnight UTC.</li>
  </ul>
</section>
"""
    return page("/vote/", "Vote for Crispy Anarchy – Daily Vote Rewards",
                "Vote for the Crispy Anarchy Minecraft server on 7 server lists and earn in-game rewards on Anarchy, Skyblock, Multiverse or Extraction Zone, with daily streak bonuses.",
                body, crumbs=[("/vote/", "Vote")])


def faq():
    body = f"""
<section class="wrap block head">
  <p class="kicker">FAQ</p>
  <h1>Crispy Anarchy questions and answers</h1>
  {join_box(True)}
</section>
<section class="wrap block"><h2>The server</h2><div class="faq open">{faq_html(FAQ)}</div></section>
""" + "".join(f'<section class="wrap block"><h2>{e(h)}</h2><div class="faq open">{faq_html(qas)}</div></section>\n' for h, qas in FAQ_MORE)
    return page("/faq/", "Crispy Anarchy FAQ – IP, Rules, Versions, Bedrock, Voting",
                "Answers about the Crispy Anarchy Minecraft server: the IP, rules, resets, Bedrock support, versions, game modes, voting, Discord and Skyblock.",
                body, crumbs=[("/faq/", "FAQ")], extra_ld=[faq_ld(FAQ_ALL)])


def notfound():
    body = f"""<section class="wrap block head"><h1>Page not found</h1><p class="lede">This page doesn't exist (anarchy got to it). Try the <a href="/">home page</a> or join the server:</p>{join_box(True)}</section>"""
    return page("/404.html", "Page not found | Crispy Anarchy", "This page does not exist.", body).replace(
        '<meta name="robots" content="index, follow, max-image-preview:large, max-snippet:-1">', '<meta name="robots" content="noindex">')


LLMS = f"""# Crispy Anarchy

> Crispy Anarchy is a free Minecraft anarchy server that has run since 2020 without a map reset. No gameplay rules and no land claims (community rules against hate speech, harassment and spam apply). Java Edition address: {JAVA} (versions 1.13 to 26.3). Bedrock Edition address: {JAVA}, port {BEDROCK_PORT}. Java and Bedrock players share the same worlds. No mods needed.

Key facts:
- Server address (Java): {JAVA}
- Server address (Bedrock): {JAVA} port {BEDROCK_PORT}
- Running since 2020, never reset. World spawn: X 287, Z -207.
- Rules: no gameplay rules and no bans on Anarchy (griefing, raiding and PvP allowed). Community rules on every server: follow the Minecraft Usage Guidelines and Minecraft/Xbox Community Standards; no hate speech or hateful builds, no real-life harassment, threats or doxxing, no spam. Slurs are automatically starred in chat, signs, books and item names. Chat reports are disabled.
- Requires a paid Java account (not cracked); Bedrock uses Microsoft accounts.
- Anarchy extras: 193 custom enchantments in 9 tiers, cyberpunk implants from a Ripperdoc, a villager market with Gold Coins, a bank, a crypto (Bitcoin) trader with a fluctuating price, and a hidden black market.
- Other modes on the same network: Vanilla Anarchy (plain survival anarchy), Skyblock (5 skills, 68 collections with tier rewards, 43 minions, pets, Bazaar, craftable gear), Multiverse PvP (36 characters, kit PvP, Elo duels, co-op zombie waves, Core Defense), Extraction Zone (open since 13 November 2026: a shared PvPvE zone in a ruined city with guns, armed raiders, loot crates, extraction points, traders and a protected stash plot in camp; whatever you carry is lost if you die).
- Discord: {DISCORD}

## Pages
- [Anarchy server]({SITE}/anarchy/): rules, enchantments, implants, market, Vanilla Anarchy
- [How to join]({SITE}/join/): Java and Bedrock steps and troubleshooting
- [Bedrock anarchy]({SITE}/bedrock-anarchy/): joining from Windows, mobile and console
- [News]({SITE}/news/): updates and new features
- [Rules]({SITE}/rules/): community rules (Minecraft Usage Guidelines, no hate, no harassment)
- [FAQ]({SITE}/faq/)
- [3D spawn map]({SITE}/spawn-map/)
- [Skyblock]({SITE}/skyblock/)
- [PvP]({SITE}/pvp/)
- [Extraction Zone]({SITE}/extraction-zone/)
- [Vote]({SITE}/vote/)
"""

ROBOTS = f"""User-agent: *
Allow: /

# AI search and assistants are welcome to read and cite this site.
User-agent: GPTBot
Allow: /
User-agent: OAI-SearchBot
Allow: /
User-agent: ChatGPT-User
Allow: /
User-agent: ClaudeBot
Allow: /
User-agent: Claude-SearchBot
Allow: /
User-agent: PerplexityBot
Allow: /
User-agent: Google-Extended
Allow: /
User-agent: Applebot-Extended
Allow: /

Sitemap: {SITE}/sitemap.xml
"""


def fmt_date(d):
    y, m, dd = d.split("-")
    return f"{int(dd)} {['January','February','March','April','May','June','July','August','September','October','November','December'][int(m)-1]} {y}"


def news_index():
    items = "".join(f"""<article class="post-card"><p class="date"><time datetime="{n['date']}">{fmt_date(n['date'])}</time></p>
<h2><a href="/news/{n['slug']}/">{e(n['title'])}</a></h2><p>{e(n['summary'])}</p></article>""" for n in NEWS)
    body = f"""
<section class="wrap block head">
  <p class="kicker">News</p>
  <h1>Crispy Anarchy news and updates</h1>
  <p class="lede measure">What's new on Anarchy, Skyblock, Multiverse PvP and Extraction Zone.</p>
</section>
<section class="wrap block"><div class="posts">{items}</div></section>
"""
    blog = {"@type": "Blog", "name": "Crispy Anarchy news", "url": SITE + "/news/", "publisher": {"@id": SITE + "/#org"},
            "blogPost": [{"@type": "BlogPosting", "headline": n["title"], "url": f"{SITE}/news/{n['slug']}/", "datePublished": n["date"]} for n in NEWS]}
    return page("/news/", "Crispy Anarchy News & Updates – Minecraft Anarchy Server",
                "Updates from the Crispy Anarchy Minecraft network: new features, fixes and events on Anarchy, Skyblock, PvP and Extraction Zone.",
                body, crumbs=[("/news/", "News")], extra_ld=[blog])


MODE_PAGES = [("Skyblock", "/skyblock/", "Crispy Skyblock"), ("Extraction", "/extraction-zone/", "Extraction Zone"),
              ("Multiverse", "/pvp/", "Multiverse"), ("Outbreak", "/pvp/", "Multiverse"), ("Anarchy", "/anarchy/", "Crispy Anarchy"),
              ("Soulbound", "/anarchy/", "Crispy Anarchy"), ("Black Market", "/anarchy/", "Crispy Anarchy"), ("Crypto", "/anarchy/", "Crispy Anarchy")]


def mode_link(n):
    """'More about <mode>' links under a news post, for every mode its title names."""
    seen, out = set(), []
    for word, url, name in MODE_PAGES:
        if word.lower() in n["title"].lower() and url not in seen:
            seen.add(url); out.append(f'<a href="{url}">{name}</a>')
    return f'<p class="note">More about {" and ".join(out)}.</p>' if out else ""


def news_post(n):
    path = f"/news/{n['slug']}/"
    i = NEWS.index(n)
    others = [m for m in NEWS if m is not n][:3]
    more = "".join(f'<li><a href="/news/{m["slug"]}/">{e(m["title"])}</a> <span class="date">{fmt_date(m["date"])}</span></li>' for m in others)
    body = f"""
<article class="wrap block head prose">
  <p class="kicker"><a href="/news/">News</a> · <time datetime="{n['date']}">{fmt_date(n['date'])}</time></p>
  <h1>{e(n['title'])}</h1>
  <p class="lede">{e(n['summary'])}</p>
  {n['body']}
  {mode_link(n)}
</article>
<section class="wrap block">
  <h2>Come and see</h2>
  {join_box(True)}
  <h2>More news</h2><ul class="more">{more}</ul>
</section>
"""
    post = {"@type": "BlogPosting", "headline": n["title"], "description": n["summary"], "datePublished": n["date"], "dateModified": n["date"],
            "url": SITE + path, "mainEntityOfPage": SITE + path, "author": {"@id": SITE + "/#org"}, "publisher": {"@id": SITE + "/#org"},
            "image": SITE + n.get("image", "/img/og.jpg")}
    return page(path, f"{n['title']} | Crispy Anarchy", n["summary"], body,
                crumbs=[("/news/", "News"), (path, n["title"])], extra_ld=[post], image=n.get("image", "/img/og.jpg"))


BEDROCK_STEPS = {
    "Windows, Android, iPhone and iPad": [
        "Open Minecraft and go to Play, then the Servers tab.",
        "Scroll to the bottom and choose Add Server.",
        f"Server Name: Crispy Anarchy. Server Address: {JAVA}. Port: {BEDROCK_PORT}.",
        "Save, then tap the server to join. You arrive in the lobby: pick Anarchy."],
    "Xbox, PlayStation and Nintendo Switch": [
        "Consoles only show Mojang's featured servers, so you need a server-list helper to reach any other server.",
        "The usual way is a BedrockConnect DNS server: in your console's network settings, set the primary DNS to a public BedrockConnect address (search for the current list).",
        "Open Minecraft, go to Servers and join any featured server: a server list opens instead.",
        f"Choose to connect to a server, enter {JAVA} and port {BEDROCK_PORT}, and join."],
}


def bedrock():
    blocks = "".join(f"<div><h2>{e(k)}</h2><ol class='steps'>{''.join(f'<li>{e(x)}</li>' for x in v)}</ol></div>" for k, v in BEDROCK_STEPS.items())
    qas = [
        ("Is there a Minecraft Bedrock anarchy server?",
         f"Yes. Crispy Anarchy is an anarchy server that Bedrock Edition players can join at {JAVA}, port {BEDROCK_PORT}. It has been running since 2020 without a reset."),
        ("Can Bedrock and Java players play together on Crispy Anarchy?",
         "Yes. Bedrock and Java players share the same anarchy world, the same market and the same chat."),
        ("What port does Crispy Anarchy use on Bedrock?",
         f"Port {BEDROCK_PORT}, not the default 19132. The address is {JAVA}."),
        ("Do I need Xbox Live or a paid account on Bedrock?",
         "You sign in with the Microsoft account you already use for Minecraft Bedrock. Nothing else is needed."),
    ]
    howtos = [{"@type": "HowTo", "name": f"Join Crispy Anarchy on Minecraft Bedrock ({k})",
               "step": [{"@type": "HowToStep", "position": i + 1, "text": x} for i, x in enumerate(v)]} for k, v in BEDROCK_STEPS.items()]
    body = f"""
<section class="wrap block head">
  <p class="kicker">Bedrock anarchy · crossplay with Java</p>
  <h1>A Minecraft Bedrock anarchy server, shared with Java players</h1>
  <p class="lede measure">Most anarchy servers are Java only. Crispy Anarchy lets Bedrock Edition players on Windows, phones, tablets and consoles join the same anarchy world as Java players, a world that has been running since 2020 without a reset.</p>
  {join_box(True)}
</section>
<section class="wrap block two">{blocks}</section>
<section class="wrap block prose">
  <h2>What Bedrock players get</h2>
  <ul>
    <li>The same anarchy world as Java players: no gameplay rules, no claims, never reset.</li>
    <li>The market, the Banker and the Crypto Exchange, the Enchanter's 193 custom enchantments and the Ripperdoc's implants.</li>
    <li>Every other mode on the network too: Vanilla Anarchy, Skyblock, Multiverse PvP and Extraction Zone.</li>
    <li>One chat with Java players and our Discord.</li>
  </ul>
  <p>Bedrock players connect through a translation layer, so a few things look slightly different from Java, such as some custom menus and item textures. If something doesn't work on Bedrock, tell us in the <a href="{DISCORD}" rel="noopener">Discord</a>.</p>
  <h2>Can't connect?</h2>
  <ul>
    <li>Check the port is <b>{BEDROCK_PORT}</b>. The default 19132 won't work.</li>
    <li>Update Minecraft: the server supports the current Bedrock version.</li>
    <li>On a console, make sure the DNS change saved and that you joined a featured server to open the list.</li>
  </ul>
</section>
<section class="wrap block"><h2>Bedrock questions</h2><div class="faq">{faq_html(qas)}</div></section>
"""
    return page("/bedrock-anarchy/", "Bedrock Anarchy Server – Crossplay with Java Since 2020 | Crispy Anarchy",
                f"Crispy Anarchy is a Minecraft Bedrock anarchy server shared with Java players. No gameplay rules, never reset since 2020. Join at {JAVA} port {BEDROCK_PORT} on Windows, mobile and console.",
                body, crumbs=[("/bedrock-anarchy/", "Bedrock anarchy")], extra_ld=howtos + [faq_ld(qas)])


MUG = "https://www.minecraft.net/en-us/usage-guidelines"
MCS = "https://www.minecraft.net/en-us/community-standards"
XCS = "https://www.xbox.com/en-US/legal/community-standards"


def rules():
    body = f"""
<section class="wrap block head">
  <p class="kicker">Rules</p>
  <h1>Crispy Anarchy rules</h1>
  <p class="lede measure">Gameplay on Crispy Anarchy is anarchy: no claims, no protected bases, no bans, and nobody will step in if your base gets griefed. The rules below are about people, not gameplay. They apply everywhere on the network: Anarchy, Vanilla Anarchy, Skyblock, Multiverse, Extraction Zone and the lobby. Our Discord has its own moderation.</p>
</section>
<section class="wrap block prose">
  <h2>1. Follow Microsoft's rules</h2>
  <p>All players must follow the <a href="{MUG}" rel="noopener">Minecraft Usage Guidelines</a>, the <a href="{MCS}" rel="noopener">Minecraft Community Standards</a> and the <a href="{XCS}" rel="noopener">Xbox Community Standards</a>, which you agreed to when you created your Minecraft account.</p>

  <h2>2. No hate</h2>
  <p>No slurs, hate speech or attacks on people for their race, ethnicity, nationality, religion, gender, gender identity, sexual orientation or disability. That covers chat, private messages, signs, books, item names, usernames, skins, builds, banners and map art. Hate symbols, such as swastikas, count as hate speech wherever they are built, however far from spawn.</p>

  <h2>3. No real-life harm</h2>
  <p>No harassment, bullying or threats against real people, on the server or in any other community. No doxxing: never share anyone's real name, address, photos, school or other personal information. Don't tell people to kill themselves.</p>

  <h2>4. No sexual content</h2>
  <p>No sexually explicit chat, builds, map art or skins, and nothing sexual involving minors, ever.</p>

  <h2>5. No spam, ads or scams</h2>
  <p>Don't flood chat with repeated messages, don't advertise other servers or third-party shops, and don't scam anyone for real money, accounts or personal information.</p>

  <h2>What's still fine on Anarchy</h2>
  <p>Griefing, raiding, stealing, killing, traps, lying and betrayal are all part of the game. Other modes have their own gameplay rules where they need them, like the protected stash plots in Extraction Zone's camp.</p>

  <h2>How this works</h2>
  <p>There are no bans, mutes or player reports on our Minecraft servers. These rules are here so everyone knows what is expected, not so we can punish people. Instead, we keep the worst content out with roadblocks rather than staff: slurs and hate slogans are automatically replaced with stars in chat, private messages, signs, books and item names on every server, and hateful builds and map art are cleared away when we come across them.</p>
</section>
"""
    return page("/rules/", "Crispy Anarchy Rules – Community Rules for an Anarchy Server",
                "Crispy Anarchy has no gameplay rules and no bans, but everyone is expected to follow the Minecraft Usage Guidelines and Community Standards: no hate speech or hateful builds, no real-life harassment, no sexual content, no spam.",
                body, crumbs=[("/rules/", "Rules")])


def main(out):
    if os.path.exists(out):
        shutil.rmtree(out)
    os.makedirs(out)
    pages = {"/": home, "/anarchy/": anarchy, "/skyblock/": skyblock, "/pvp/": pvp, "/extraction-zone/": extraction,
             "/spawn-map/": spawn_map, "/join/": join, "/vote/": vote, "/faq/": faq,
             "/bedrock-anarchy/": bedrock, "/news/": news_index, "/rules/": rules,
             "/vanilla-anarchy/": vanilla_anarchy, "/bedrock-skyblock/": bedrock_skyblock, "/2b2t-alternative/": alt_2b2t,
             "/guides/anarchy-survival/": guide_anarchy, "/guides/skyblock-beginners/": guide_skyblock, "/crispymon/": crispymon}
    for n in NEWS:
        pages[f"/news/{n['slug']}/"] = (lambda n=n: news_post(n))
    for path, fn in pages.items():
        d = os.path.join(out, path.strip("/"))
        os.makedirs(d, exist_ok=True)
        open(os.path.join(d, "index.html"), "w").write(fn())
    open(os.path.join(out, "404.html"), "w").write(notfound())
    prio = {"/": "1.0", "/anarchy/": "0.9", "/skyblock/": "0.9", "/join/": "0.9", "/bedrock-anarchy/": "0.8", "/bedrock-skyblock/": "0.8",
            "/vanilla-anarchy/": "0.8"}
    mod = {f"/news/{n['slug']}/": n["date"] for n in NEWS}
    with open(DATES_FILE, "w") as f: json.dump(DATES, f, indent=1, sort_keys=True)
    sm = "".join(f"<url><loc>{SITE}{p}</loc><lastmod>{mod.get(p) or DATES.get(p, [0, UPDATED])[1]}</lastmod><priority>{prio.get(p, '0.6' if p in mod else '0.7')}</priority></url>" for p in pages)
    open(os.path.join(out, "sitemap.xml"), "w").write(
        f'<?xml version="1.0" encoding="UTF-8"?>\n<urlset xmlns="http://www.sitemaps.org/schemas/sitemap/0.9">{sm}</urlset>\n')
    open(os.path.join(out, "robots.txt"), "w").write(ROBOTS)
    open(os.path.join(out, "llms.txt"), "w").write(LLMS)
    key = open(os.path.join(HERE, "indexnow_key.txt")).read().strip()   # IndexNow (Bing, Yandex, ...): public by design
    open(os.path.join(out, key + ".txt"), "w").write(key)
    open(os.path.join(out, "_headers"), "w").write(
        "/img/*\n  Cache-Control: public, max-age=2592000\n/*.css\n  Cache-Control: public, max-age=86400\n/*.js\n  Cache-Control: public, max-age=86400\n"
        "/map/*\n  X-Robots-Tag: noindex\n"
        "https://:project.pages.dev/*\n  X-Robots-Tag: noindex\n")
    open(os.path.join(out, "_redirects"), "w").write("/factions/ /extraction-zone/ 301\n/factions /extraction-zone/ 301\n")
    for f in ("style.css", "site.js"):
        shutil.copy(os.path.join(HERE, f), out)
    shutil.copytree(os.path.join(HERE, "images"), os.path.join(out, "img"))


if __name__ == "__main__":
    main(sys.argv[1])

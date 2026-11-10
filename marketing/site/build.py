#!/usr/bin/env python3
"""Static website for Crispy Anarchy (www.crispyanarchy.net), written for search engines and AI answer engines.

    python3 build.py <outdir>

Writes plain HTML pages (real text, one topic per page), JSON-LD structured data, sitemap.xml, robots.txt and
llms.txt. Images come from images/ next to this file. The BlueMap 3D map is deployed alongside under /map/.
Every claim here was checked against the live servers (see marketing/listings.md for the rules: no player counts,
no "biggest/best", no franchise names).
"""
import json, os, shutil, sys, html
from datetime import date

SITE = "https://www.crispyanarchy.net"
JAVA = "crispyanarchy.net"
BEDROCK_PORT = "19100"
DISCORD = "https://discord.gg/hF2bQgU"
UPDATED = date.today().isoformat()
HERE = os.path.dirname(os.path.abspath(__file__))

VOTE = [
    ("TopG", "https://topg.org/minecraft-servers/server-687311"),
    ("Planet Minecraft", "https://www.planetminecraft.com/server/crispy-anarchy-1-16-no-rules-survival/vote/"),
    ("MinecraftServers.org", "https://minecraftservers.org/vote/587166"),
    ("Minecraft-Server-List", "https://minecraft-server-list.com/server/503605/vote/"),
    ("MMTop200", "https://mmtop200.com/vote/5176"),
    ("Minecraft-MP", "https://minecraft-mp.com/server/365762/vote/"),
    ("ServerTilt", "https://www.servertilt.com/minecraft-servers/crispy-anarchy/vote"),
]

NAV = [("/", "Home"), ("/anarchy/", "Anarchy"), ("/skyblock/", "Skyblock"), ("/pvp/", "PvP"),
       ("/factions/", "Factions"), ("/spawn-map/", "3D Map"), ("/join/", "How to join"), ("/vote/", "Vote"),
       ("/faq/", "FAQ")]

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


def page(path, title, desc, body, crumbs=None, extra_ld=(), image="/img/og.jpg", h1_hero=None):
    url = SITE + path
    graph = [ORG, WEBSITE, {"@type": "WebPage", "@id": url + "#page", "url": url, "name": title, "description": desc,
                            "isPartOf": {"@id": SITE + "/#website"}, "about": {"@id": SITE + "/#org"},
                            "dateModified": UPDATED, "primaryImageOfPage": SITE + image, "inLanguage": "en"}]
    if crumbs:
        graph.append({"@type": "BreadcrumbList", "itemListElement": [
            {"@type": "ListItem", "position": i + 1, "name": n, "item": SITE + p} for i, (p, n) in enumerate([("/", "Home")] + crumbs)]})
    graph += list(extra_ld)
    nav = "".join(f'<a href="{p}"{" aria-current=\"page\"" if p == path else ""}>{n}</a>' for p, n in NAV)
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
    <a class="logo" href="/"><img src="/img/icon-64.png" alt="" width="32" height="32"><span>Crispy <b>Anarchy</b></span></a>
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
      <p>A Minecraft anarchy server since 2020, plus Skyblock, PvP and Factions on one network. Java and Bedrock.</p>
      <p>Java: <code>{JAVA}</code> · Bedrock: <code>{JAVA}</code> port <code>{BEDROCK_PORT}</code></p>
    </div>
    <div class="foot-links">
      {''.join(f'<a href="{p}">{n}</a>' for p, n in NAV[1:])}
      <a href="{DISCORD}" rel="noopener">Discord</a>
    </div>
  </div>
  <div class="wrap fine">Not an official Minecraft product. Not approved by or associated with Mojang or Microsoft. Updated {UPDATED}.</div>
</footer>
<script src="/site.js" defer></script>
</body>
</html>
"""


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
     "An anarchy server is a Minecraft survival server with no rules: no land claims, no protected bases and no staff stepping in. "
     "Griefing, raiding, PvP and hacked clients are all part of the game, and the world is never reset, so it keeps years of history."),
    ("Does Crispy Anarchy have rules?",
     "No. Crispy Anarchy has no gameplay rules and no land claims. Anything you build can be found, raided or griefed by other players."),
    ("Are hacked clients allowed on Crispy Anarchy?",
     "Yes. It is an anarchy server: there are no rules against hacked clients and the anarchy server runs no anticheat."),
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
     "Same idea: no rules and a world that is never reset. Different: Bedrock players can join too, the server adds 193 custom enchantments, "
     "cyberpunk implants and a market economy with a crypto exchange, and the community is smaller, so you meet people quickly."),
    ("What other game modes does the network have?",
     "Besides Anarchy there is Vanilla Anarchy (plain survival), Skyblock with skills, pets and minions, a PvP server called Multiverse "
     "with 36 characters, duels and co-op zombie waves, and old-school Factions. All share one chat and one Discord."),
    ("Where is spawn on Crispy Anarchy?",
     "World spawn is at X 287, Z -207 in the overworld. You can explore the area around it on the 3D map at www.crispyanarchy.net/spawn-map/."),
]


def home():
    modes = [
        ("/anarchy/", "Anarchy", "No rules, no claims, one world since 2020. Custom enchantments, implants, a market and a hidden black market."),
        ("/anarchy/#vanilla", "Vanilla Anarchy", "Plain survival anarchy with no custom items, for people who like it pure."),
        ("/skyblock/", "Skyblock", "Grow your island with skills, pets, 43 minions, a Bazaar and gear crafted from what you farm."),
        ("/pvp/", "Multiverse PvP", "36 playable characters, kit PvP, ranked duels and co-op zombie waves."),
        ("/factions/", "Factions", "1.8-style combat, cannons and obsidian walls, with set raid windows."),
        ("/spawn-map/", "3D spawn map", "Fly over two square kilometres of spawn, wrecked by six years of anarchy."),
    ]
    cards = "".join(f'<a class="card" href="{u}"><h3>{n}</h3><p>{d}</p></a>' for u, n, d in modes)
    body = f"""
<section class="hero">
  <img class="hero-img" src="/img/spawn.webp" alt="3D render of Crispy Anarchy spawn: lava-scarred stone, giant pillars and ruined walls around spawn" width="1600" height="825" fetchpriority="high">
  <div class="wrap hero-in">
    <p class="kicker">Minecraft anarchy server · since 2020 · never reset</p>
    <h1>Crispy Anarchy: a no-rules Minecraft anarchy server for Java and Bedrock</h1>
    <p class="lede">One world, running since 2020 and never reset. No rules, no claims, no protected bases. Custom enchantments, cyberpunk implants and a player market on top, and no mods needed.</p>
    {join_box()}
  </div>
</section>
<section class="wrap block">
  <h2>What is Crispy Anarchy?</h2>
  <p class="measure">Crispy Anarchy is a free Minecraft anarchy server that has been running since 2020 without a map reset. There are no rules and no land claims: players grief, raid, fight and build wherever they like, and everything that happens stays in the world. Java Edition players join at <code>{JAVA}</code>; Bedrock Edition players join at <code>{JAVA}</code> on port <code>{BEDROCK_PORT}</code>.</p>
  <p class="measure">Crispy Anarchy is also the name of the wider Crispy network, which adds Vanilla Anarchy, Skyblock, a PvP server and Factions, linked by one chat and one Discord.</p>
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
  <img src="/img/overview.webp" alt="Aerial 3D view of the Crispy Anarchy spawn region with oceans and islands around the griefed spawn" width="1600" height="740" loading="lazy">
</section>
<section class="wrap block">
  <h2>Quick answers</h2>
  <div class="faq">{faq_html(FAQ[:5])}</div>
  <p><a href="/faq/">All questions</a></p>
</section>
"""
    return page("/", "Crispy Anarchy – Minecraft Anarchy Server (Java & Bedrock) | crispyanarchy.net",
                "Crispy Anarchy is a no-rules Minecraft anarchy server since 2020, never reset. Java and Bedrock crossplay, 193 custom enchantments, implants and a market. IP: crispyanarchy.net",
                body, extra_ld=[GAMESERVER, faq_ld(FAQ[:5])])


def anarchy():
    body = f"""
<section class="wrap block head">
  <p class="kicker">Anarchy · Java + Bedrock</p>
  <h1>Minecraft anarchy server with no rules, running since 2020</h1>
  <p class="lede measure">Crispy Anarchy is our main server: a survival world with no rules and no land claims that has never been reset since it started in 2020. On top of plain anarchy it adds custom enchantments, cyberpunk implants and a player market, all without mods.</p>
  {join_box(True)}
</section>
<figure class="wrap shot"><img src="/img/low.webp" alt="Ground-level 3D view of Crispy Anarchy spawn: ruined stone walls, water and lava flows" width="1600" height="900" loading="lazy"><figcaption>Spawn today, from the <a href="/spawn-map/">3D map</a>.</figcaption></figure>
<section class="wrap block prose">
  <h2>No rules, no claims, no resets</h2>
  <p>There are no gameplay rules on Crispy Anarchy. Nothing is protected: bases can be found and raided, builds can be griefed, and anyone can kill anyone. Hacked clients are not against any rule and the anarchy server runs no anticheat. Chat reports are off (the server runs No Chat Reports).</p>
  <p>The world started in 2020 and has never been wiped, so the land around spawn carries six years of history. Spawn itself is at X 287, Z -207, and the closer you get the less is left standing. Most players head out along the axis highways to find space to build.</p>

  <h2>193 custom enchantments</h2>
  <p>Crispy Anarchy has 193 custom enchantments in nine rarity tiers: Simple, Unique, Elite, Ultimate, Legendary, Soul, Heroic, Mastery and Rare. Heroic enchantments are upgrades that need the base enchantment at its maximum level. You buy random enchantment books from the Enchanter in the market with your XP.</p>

  <h2>Cyberpunk implants</h2>
  <p>The Ripperdoc in the market sells implants, bought with diamonds or netherite. Each implant takes one body slot and uses up some of your capacity. You can go over the limit of 20, but every point over raises the chance of a cyberpsychosis episode.</p>

  <h2>The market, the bank and crypto</h2>
  <p>The market is a separate area full of villager shops that trade in Gold Coins and Coin Bags. The Banker exchanges 36 emeralds or 36 diamonds for one Gold Coin, 16 coins for a block of netherite, and 64 coins for a Coin Bag. Next to the bank, a crypto trader buys and sells Bitcoin at a price that moves up and down like a real cryptocurrency, with its own price chart.</p>
  <p>Somewhere in the world there is also a black market. Its location is not published: you have to find it.</p>

  <h2 id="vanilla">Vanilla Anarchy</h2>
  <p>Prefer anarchy without custom items? Vanilla Anarchy is a separate server with plain survival anarchy: no custom enchantments, no implants, no shops. Pick it from the lobby.</p>

  <h2>Play from Java or Bedrock</h2>
  <p>Java Edition 1.13 to 26.3 can join at <code>{JAVA}</code>. Bedrock Edition players on Windows, phones, tablets and consoles join at <code>{JAVA}</code> on port <code>{BEDROCK_PORT}</code> and share the same world. Step-by-step instructions are on the <a href="/join/">how to join</a> page.</p>
</section>
"""
    qas = [FAQ[2], FAQ[3], FAQ[4], FAQ[11]]
    body += f'<section class="wrap block"><h2>Anarchy questions</h2><div class="faq">{faq_html(qas)}</div></section>'
    return page("/anarchy/", "Minecraft Anarchy Server – No Rules, Never Reset Since 2020 | Crispy Anarchy",
                "A Minecraft anarchy server with no rules and no claims, running since 2020 and never reset. 193 custom enchantments, implants, a market and crypto. Java & Bedrock: crispyanarchy.net",
                body, crumbs=[("/anarchy/", "Anarchy")], extra_ld=[GAMESERVER, faq_ld(qas)], image="/img/low.webp")


def skyblock():
    body = f"""
<section class="wrap block head">
  <p class="kicker">Skyblock · Java + Bedrock</p>
  <h1>Minecraft Skyblock server with skills, pets and minions</h1>
  <p class="lede measure">Crispy Skyblock starts you on one of seven themed islands and gives you plenty to grow into: five skills, 43 kinds of minions, pets, a player-run Bazaar and gear you craft from what you farm. No pay-to-win.</p>
  {join_box(True)}
</section>
<section class="wrap block prose">
  <h2>Islands and upgrades</h2>
  <p>Choose one of seven themed starter islands. Upgrade its size, minion slots, co-op slots and ore generator as you go, and invite friends to build with you. Island level grows with what you place.</p>
  <h2>Five skills</h2>
  <p>Level Farming, Mining, Combat, Foraging and Fishing by doing them. Each level gives rewards.</p>
  <h2>43 minions</h2>
  <p>Minions collect resources for you while you play elsewhere. There are 43 kinds, from crops and ores to mob drops.</p>
  <h2>Enchanted resources and crafted gear</h2>
  <p>Turn stacks of farmed resources into enchanted versions at the Compactor, then craft 17 armour sets and 19 weapons with their own abilities. Better gear needs more farming, not real money.</p>
  <h2>Bazaar, pets and the hub</h2>
  <p>Trade with other players on the Bazaar with buy and sell orders. Level up pets that follow you around. Buy a plot in the hub for a shop or a house.</p>
  <h2>Mines, forests and a boss rift</h2>
  <p>Regenerating mines and forests are full of levelled mobs, and the Sky Lord's Rift holds a boss. Loot and dungeons fall from the sky onto your island.</p>
  <h2>How to get there</h2>
  <p>Join <code>{JAVA}</code> (Bedrock: port <code>{BEDROCK_PORT}</code>) and choose Skyblock in the lobby.</p>
</section>
"""
    return page("/skyblock/", "Minecraft Skyblock Server with Skills, Pets & Minions | Crispy Network",
                "Skyblock on the Crispy network: 7 starter islands, 5 skills, 43 minions, pets, a player Bazaar and craftable gear. No pay-to-win. Java & Bedrock at crispyanarchy.net",
                body, crumbs=[("/skyblock/", "Skyblock")], extra_ld=[GAMESERVER])


def pvp():
    body = f"""
<section class="wrap block head">
  <p class="kicker">Multiverse PvP · Java + Bedrock</p>
  <h1>Minecraft PvP server: 36 characters, kit PvP, duels and zombie waves</h1>
  <p class="lede measure">Multiverse is the Crispy network's PvP server. Pick one of 36 characters, each with its own abilities and gear, and fight in the arena, in ranked duels or together against waves of zombies.</p>
  {join_box(True)}
</section>
<section class="wrap block prose">
  <h2>Kit PvP with 36 characters</h2>
  <p>Every kit is a character with its own weapons, armour and right-click abilities with cooldowns. Pick one from the menu and drop into one of eight arena maps. Playing a character earns mastery levels and rewards for that character.</p>
  <h2>Ranked duels</h2>
  <p>Challenge another player to a duel in the duel pits. Duels are ranked with an Elo rating.</p>
  <h2>Outbreak: co-op zombie waves</h2>
  <p>Team up against waves of zombies with guns, upgrades and bosses, across five maps, with revives and a hidden weapon quest.</p>
  <h2>Core Defense</h2>
  <p>Build a base and keep its core alive.</p>
  <h2>How to get there</h2>
  <p>Join <code>{JAVA}</code> (Bedrock: port <code>{BEDROCK_PORT}</code>) and choose Multiverse in the lobby.</p>
</section>
"""
    return page("/pvp/", "Minecraft PvP Server – Kit PvP, Ranked Duels & Zombie Waves | Crispy Network",
                "Multiverse PvP on the Crispy network: 36 playable characters with abilities, kit PvP, Elo-ranked duels, co-op zombie waves and Core Defense. Java & Bedrock at crispyanarchy.net",
                body, crumbs=[("/pvp/", "PvP")], extra_ld=[GAMESERVER])


def factions():
    body = f"""
<section class="wrap block head">
  <p class="kicker">Factions · Java + Bedrock</p>
  <h1>Old-school Minecraft Factions server with cannons and raid windows</h1>
  <p class="lede measure">Crispy Factions plays like classic factions: 1.8-style combat, TNT cannons and obsidian walls. Raids are only allowed in set windows, so you can build in peace the rest of the time. No pay-to-win.</p>
  {join_box(True)}
</section>
<section class="wrap block prose">
  <h2>Classic factions gameplay</h2>
  <p>Found a faction, claim land, build a base and wall it in with obsidian. Combat uses 1.8-style hit timing. Skills from mcMMO level up as you play.</p>
  <h2>Raid windows</h2>
  <p>Raiding is open on weeknights from 6 to 11 pm and on weekends from noon to midnight, Eastern Time. Outside those windows bases are safe.</p>
  <h2>How to get there</h2>
  <p>Join <code>{JAVA}</code> (Bedrock: port <code>{BEDROCK_PORT}</code>) and choose Factions in the lobby.</p>
</section>
"""
    return page("/factions/", "Minecraft Factions Server – 1.8 Combat, Cannons & Raid Windows | Crispy Network",
                "Old-school Minecraft Factions on the Crispy network: 1.8-style combat, cannons, obsidian walls, mcMMO and set raid windows. No pay-to-win. Java & Bedrock at crispyanarchy.net",
                body, crumbs=[("/factions/", "Factions")], extra_ld=[GAMESERVER])


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
<figure class="wrap shot"><img src="/img/overview.webp" alt="Bird's-eye 3D render of Crispy Anarchy spawn and the surrounding islands" width="1600" height="740" loading="lazy"></figure>
"""
    return page("/spawn-map/", "Crispy Anarchy Spawn 3D Map – Minecraft Anarchy Server Map",
                "Fly through a 3D render of Crispy Anarchy spawn: two square kilometres of a Minecraft anarchy world that has never been reset since 2020.",
                body, crumbs=[("/spawn-map/", "3D Map")], image="/img/overview.webp")


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
  <div><h2>Bedrock Edition</h2>{ol(steps_bedrock)}<p class="note">Works on Windows, phones and tablets. On consoles, Bedrock only lets you add servers through a workaround such as a DNS or LAN-proxy app.</p></div>
</section>
<section class="wrap block prose">
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
    rows = "".join(f'<li><a href="{u}" rel="noopener">{n}</a></li>' for n, u in VOTE)
    body = f"""
<section class="wrap block head">
  <p class="kicker">Vote</p>
  <h1>Vote for Crispy Anarchy</h1>
  <p class="lede measure">Voting every day helps new players find the server, and you get rewards for it on the server of your choice. Enter your exact Minecraft username on each site.</p>
</section>
<section class="wrap block"><ol class="votes">{rows}</ol>
<p class="note">Type <code>/vote</code> in game to see your vote points and claim rewards.</p></section>
"""
    return page("/vote/", "Vote for Crispy Anarchy – Daily Vote Rewards",
                "Vote for the Crispy Anarchy Minecraft server on 7 server lists and earn in-game rewards on Anarchy, Skyblock, PvP or Factions.",
                body, crumbs=[("/vote/", "Vote")])


def faq():
    body = f"""
<section class="wrap block head">
  <p class="kicker">FAQ</p>
  <h1>Crispy Anarchy questions and answers</h1>
  {join_box(True)}
</section>
<section class="wrap block"><div class="faq open">{faq_html(FAQ)}</div></section>
"""
    return page("/faq/", "Crispy Anarchy FAQ – IP, Rules, Versions, Bedrock",
                "Answers about the Crispy Anarchy Minecraft server: the IP, rules, hacked clients, resets, Bedrock support, versions and game modes.",
                body, crumbs=[("/faq/", "FAQ")], extra_ld=[faq_ld(FAQ)])


def notfound():
    body = f"""<section class="wrap block head"><h1>Page not found</h1><p class="lede">This page doesn't exist (anarchy got to it). Try the <a href="/">home page</a> or join the server:</p>{join_box(True)}</section>"""
    return page("/404.html", "Page not found | Crispy Anarchy", "This page does not exist.", body).replace(
        '<meta name="robots" content="index, follow, max-image-preview:large, max-snippet:-1">', '<meta name="robots" content="noindex">')


LLMS = f"""# Crispy Anarchy

> Crispy Anarchy is a free Minecraft anarchy server that has run since 2020 without a map reset. No rules, no land claims, no anticheat on the anarchy server. Java Edition address: {JAVA} (versions 1.13 to 26.3). Bedrock Edition address: {JAVA}, port {BEDROCK_PORT}. Java and Bedrock players share the same worlds. No mods needed.

Key facts:
- Server address (Java): {JAVA}
- Server address (Bedrock): {JAVA} port {BEDROCK_PORT}
- Running since 2020, never reset. World spawn: X 287, Z -207.
- Rules: none on Anarchy (griefing, raiding, PvP and hacked clients allowed). Chat reports are disabled.
- Requires a paid Java account (not cracked); Bedrock uses Microsoft accounts.
- Anarchy extras: 193 custom enchantments in 9 tiers, cyberpunk implants from a Ripperdoc, a villager market with Gold Coins, a bank, a crypto (Bitcoin) trader with a fluctuating price, and a hidden black market.
- Other modes on the same network: Vanilla Anarchy (plain survival anarchy), Skyblock (5 skills, 43 minions, pets, Bazaar, craftable gear), Multiverse PvP (36 characters, kit PvP, Elo duels, co-op zombie waves, Core Defense), Factions (1.8 combat, cannons, set raid windows).
- Discord: {DISCORD}

## Pages
- [Anarchy server]({SITE}/anarchy/): rules, enchantments, implants, market, Vanilla Anarchy
- [How to join]({SITE}/join/): Java and Bedrock steps and troubleshooting
- [FAQ]({SITE}/faq/)
- [3D spawn map]({SITE}/spawn-map/)
- [Skyblock]({SITE}/skyblock/)
- [PvP]({SITE}/pvp/)
- [Factions]({SITE}/factions/)
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


def main(out):
    if os.path.exists(out):
        shutil.rmtree(out)
    os.makedirs(out)
    pages = {"/": home, "/anarchy/": anarchy, "/skyblock/": skyblock, "/pvp/": pvp, "/factions/": factions,
             "/spawn-map/": spawn_map, "/join/": join, "/vote/": vote, "/faq/": faq}
    for path, fn in pages.items():
        d = os.path.join(out, path.strip("/"))
        os.makedirs(d, exist_ok=True)
        open(os.path.join(d, "index.html"), "w").write(fn())
    open(os.path.join(out, "404.html"), "w").write(notfound())
    prio = {"/": "1.0", "/anarchy/": "0.9", "/join/": "0.9"}
    sm = "".join(f"<url><loc>{SITE}{p}</loc><lastmod>{UPDATED}</lastmod><priority>{prio.get(p, '0.7')}</priority></url>" for p in pages)
    open(os.path.join(out, "sitemap.xml"), "w").write(
        f'<?xml version="1.0" encoding="UTF-8"?>\n<urlset xmlns="http://www.sitemaps.org/schemas/sitemap/0.9">{sm}</urlset>\n')
    open(os.path.join(out, "robots.txt"), "w").write(ROBOTS)
    open(os.path.join(out, "llms.txt"), "w").write(LLMS)
    open(os.path.join(out, "_headers"), "w").write(
        "/img/*\n  Cache-Control: public, max-age=2592000\n/*.css\n  Cache-Control: public, max-age=86400\n/*.js\n  Cache-Control: public, max-age=86400\n"
        "/map/*\n  X-Robots-Tag: noindex\n"
        "https://:project.pages.dev/*\n  X-Robots-Tag: noindex\n")
    for f in ("style.css", "site.js"):
        shutil.copy(os.path.join(HERE, f), out)
    shutil.copytree(os.path.join(HERE, "images"), os.path.join(out, "img"))


if __name__ == "__main__":
    main(sys.argv[1])

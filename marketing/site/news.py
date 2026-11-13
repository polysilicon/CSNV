"""News posts for www.crispyanarchy.net/news/. Newest first. Each post gets its own page at /news/<slug>/.

Body is HTML (paragraphs and lists). Keep it factual: only what is live on the servers. Never publish Black Market
spots or anything else players are meant to find.
"""

NEWS = [
    {
        "slug": "extraction-zone-open",
        "date": "2026-11-13",
        "title": "Extraction Zone is open",
        "summary": "Extraction Zone is live: loot a ruined city, fight raiders and players, revive your squad or finish off a rival, and get out alive.",
        "image": "/img/shots/ez-street.webp",
        "body": """
<p><a href="/extraction-zone/">Extraction Zone</a> is open. Pick it in the lobby's server selector.</p>
<ul>
<li><b>Raid a ruined city.</b> Four rings from the outskirts to the Core: the deeper you go, the tougher the raiders and the better the loot.</li>
<li><b>Extract under fire.</b> Hold an extraction point for 30 seconds while the flare draws raiders in.</li>
<li><b>Downed, not dead.</b> Another player can revive you or finish you off and take your gear. Carry a Self-Revive Injector to get up on your own.</li>
<li><b>Guns and blades.</b> Pistols to a machine gun, plus a combat knife, machete, fire axe and sledgehammer.</li>
<li><b>Your bunker.</b> Store loot and build stations to craft armour, meds, ammo and tools, or salvage spare gear into parts.</li>
<li><b>No safe logout.</b> Leave mid-raid and a stand-in of you stays behind with your gear while your timer runs.</li>
</ul>
<p>New players get a Field Guide on their first visit, and <code>/guide</code> gives a fresh copy any time.</p>
<figure class="pic"><img src="/img/shots/ez-city.webp" alt="Aerial view of the ruined Extraction Zone city in grey fog" width="1600" height="900" loading="lazy"><figcaption>The city from above.</figcaption></figure>
""",
    },
    {
        "slug": "skyblock-collections",
        "date": "2026-11-12",
        "title": "Skyblock: 68 collections with coins and skill XP for every tier",
        "summary": "Everything you gather on Skyblock now counts toward a collection. 68 resources, nine tiers each, and every tier pays coins and skill XP.",
        "image": "/img/shots/sb-collections.webp",
        "body": """
<p>Skyblock has <b>collections</b>. Every resource you gather counts toward its own collection, and each one has nine tiers (I to IX). Every new tier pays coins and XP in that resource's skill.</p>
<ul>
<li><b>68 collections:</b> 23 farming, 20 mining, 8 foraging, 10 combat and 7 fishing.</li>
<li><b>What counts:</b> what you pick up from mining, chopping, farming, mob drops and fishing, what a resource zone hands you, and half of what you collect from your minions (gathering yourself is twice as fast).</li>
<li><b>What doesn't:</b> anything bought, crafted or dropped by another player, and drops from blocks you placed yourself.</li>
<li><b>A head start:</b> collections started from what you had already picked up before the update, and any tiers that reached paid their coins straight away.</li>
</ul>
<p>Open them with <code>/collections</code>, from the Island Menu, or from the Skyblock Guide.</p>
<figure class="pic"><img src="/img/shots/sb-collections.webp" alt="The Crispy Skyblock Collections menu showing 15 of 612 tiers unlocked" width="1600" height="900" loading="lazy"><figcaption>The Collections menu in game.</figcaption></figure>
""",
    },
    {
        "slug": "extraction-zone-replaces-factions",
        "date": "2026-11-12",
        "title": "Factions closes, Extraction Zone opens Friday 13 November",
        "summary": "Factions has closed. Its replacement is Extraction Zone: loot a ruined city with guns, fight raiders and players, and get out alive.",
        "body": """
<p>Factions has closed to make room for something new. Thanks to everyone who raided and built there.</p>
<p>Its replacement, <a href="/extraction-zone/">Extraction Zone</a>, opens on <b>Friday 13 November</b>. It is a looting mode in a ruined city that everyone shares:</p>
<ul>
<li>Deploy with the gear you choose to risk, loot crates and reach an extraction point before the 25-minute timer runs out.</li>
<li>Guns with magazines and reloads, and armed enemies that shoot back.</li>
<li>Team up with players you meet, or betray them for their loot.</li>
<li>Traders in camp and inside the zone, Credits you carry as items, and a protected stash plot in camp you can build on and upgrade.</li>
</ul>
<p>Pick Extraction Zone in the lobby's server selector from Friday.</p>
""",
    },
    {
        "slug": "website-and-3d-spawn-map",
        "date": "2026-11-10",
        "title": "New website and a 3D map of six years of anarchy",
        "summary": "Crispy Anarchy has a website, with a 3D map of two square kilometres around spawn you can fly through in your browser.",
        "body": """
<p>Crispy Anarchy now has a proper home on the web at <a href="/">www.crispyanarchy.net</a>, with how to join on Java and Bedrock, every game mode on the network and answers to the usual questions.</p>
<p>The centrepiece is the <a href="/spawn-map/">3D spawn map</a>: about two square kilometres around world spawn (X 287, Z -207), rendered block for block. The world has never been reset since 2020, so it shows everything players have done to spawn: lava casts, towers, wither holes and the ruins of old builds. Drag to look around, scroll to zoom, or switch to free-flight from the map's menu.</p>
""",
    },
    {
        "slug": "soulbound-buffed-and-kit-shulkers-fixed",
        "date": "2026-11-10",
        "title": "Soulbound fixed and buffed, market kit shulkers restocked",
        "summary": "Soulbound now really returns your item, with a much better chance per level, and the market's kit shulkers contain full stacks again.",
        "body": """
<p><b>Soulbound.</b> Soulbound items were being saved when you died but not handed back properly, so they could vanish. That is fixed: the item now drops at your feet when you respawn. The chance to keep the item has also gone up a lot:</p>
<ul><li>Soulbound I: 25%</li><li>Soulbound II: 50%</li><li>Soulbound III: 75%</li><li>Soulbound IV: 100%</li></ul>
<p>Enchantment books come from the Enchanter in the market, bought with XP.</p>
<p><b>Kit shulkers.</b> The Building Kits and Shulker Kits villagers in the market were selling shulkers with one item per slot after the move to the new Minecraft version. Every kit has its full stacks back, and the letter-block heads in the letter kits have their textures and names again.</p>
""",
    },
    {
        "slug": "crypto-exchange-and-banker",
        "date": "2026-11-09",
        "title": "Anarchy: a Crypto Exchange with live prices, and a new Banker menu",
        "summary": "Trade Bitcoin at a price that moves like a real cryptocurrency, and exchange diamonds, emeralds and coins at the Banker's new menu.",
        "body": """
<p>A <b>Crypto Exchange</b> trader has opened next to the bank in the market. It buys and sells Bitcoin at a price that rises and falls on its own, like a real cryptocurrency, and its menu shows a price chart so you can time your trades. Buy low, sell high, or lose your shirt.</p>
<p>The <b>Banker</b> now has a chest menu too. Exchange rates:</p>
<ul><li>36 diamonds or 36 emeralds = 1 Gold Coin</li><li>16 Gold Coins = 1 block of netherite</li><li>64 Gold Coins = 1 Coin Bag</li></ul>
<p>Old Gold Coins, Coin Bags and Bitcoins saved by earlier Minecraft versions are converted automatically when they are in your inventory or ender chest, so the market accepts them again.</p>
""",
    },
    {
        "slug": "skyblock-minions-compactor-gear",
        "date": "2026-11-09",
        "title": "Skyblock: 20 new minions, the Compactor and gear crafted from your farms",
        "summary": "Skyblock now has 43 minions, a Compactor that turns stacks into enchanted resources, and new armour and weapons crafted from them.",
        "body": """
<p><b>20 new minions</b> bring Skyblock to 43: six kinds of logs, eight farming minions, copper, gravel, ice, creeper, slime and fishing. Several of them wear mob-head skins.</p>
<p><b>The Compactor</b> stands in the hub between the Farming and Mining stalls. Use <code>/compact</code> to turn big stacks of farmed resources into enchanted versions. Some special armour, weapons and tools need these to craft.</p>
<p><b>New gear:</b> armour sets, weapons and tools crafted from what your minions collect, all on one cost rule so better gear means more farming, not real money. The <code>/guide</code> recipe pages are now sorted by kind.</p>
""",
    },
    {
        "slug": "skyblock-homes-visits-portals",
        "date": "2026-11-08",
        "title": "Skyblock: island homes, visits and movable portals",
        "summary": "Set homes on your island, visit any island (unless it's private), move your island's portals, and play with a gentler island-level curve.",
        "body": """
<ul>
<li><code>/island home</code> and <code>/island sethome</code> set where you arrive on your island, plus up to three personal homes with <code>/sethome</code> and <code>/home</code>.</li>
<li><code>/island visit</code> takes you to any island, even when its owner is offline, unless they made it private with <code>/island public off</code>. Visitors can't use an island's Nether or End portals.</li>
<li>Island portals and the sky-drop landing pad can be moved.</li>
<li>Island level now climbs on a gentler curve, and <code>/shop</code> opens the merchants' shop from anywhere.</li>
</ul>
""",
    },
    {
        "slug": "anarchy-clans",
        "date": "2026-11-08",
        "title": "Anarchy: clans are back",
        "summary": "Clans return on Anarchy with a clan tag in chat, private clan chat, ranks and a friendly-fire toggle. No claims: it's still anarchy.",
        "body": """
<p>Clans are back on Crispy Anarchy, with the 24 clans from the old clans plugin carried over.</p>
<ul><li>Your clan tag shows in chat.</li><li>Private clan chat.</li><li>Ranks inside the clan.</li><li>A friendly-fire toggle, so you can stop hitting your own clanmates.</li><li>Clan kill counts and a top list.</li></ul>
<p>Clans don't come with land claims. Your base is only as safe as you keep it hidden.</p>
""",
    },
    {
        "slug": "the-black-market",
        "date": "2026-11-07",
        "title": "Anarchy: the Black Market opens",
        "summary": "A dealer hides somewhere in the market. Find the spot and you get a random piece of contraband and the [Black Market] tag. Then it moves.",
        "body": """
<p>Somewhere in the market there is a hidden spot. Find it and crouch there, and the Black Market Dealer appears for a moment, hands you a random piece of contraband and gives you the <b>[Black Market]</b> chat tag. Then the spot moves somewhere else, so the next person has to find it all over again.</p>
<p>Contraband includes ability items like the Phase Shard, Jump Jet, Smoke Bomb, Tesla Coil, Gravity Bomb, Swap Orb, Chrono Clock and Frost Nova, plus Growth and Shrink potions and their splash versions.</p>
<p>We're not saying where it is.</p>
""",
    },
]

"""News posts for www.crispyanarchy.net/news/. Newest first. Each post gets its own page at /news/<slug>/.

Body is HTML (paragraphs and lists). Keep it factual: only what is live on the servers. Never publish Black Market
spots or anything else players are meant to find.
"""

NEWS = [
    {
        "slug": "lobby-minigames-daily-word",
        "date": "2026-11-19",
        "title": "Lobby Minigames and a new game: Daily Word",
        "summary": "The lobby's games now have their own menu, with a new daily word game alongside UNO and Balatro Craft. Plus: ask Yoink questions, and safer Skyblock.",
        "body": """
<h2>Lobby Minigames</h2>
<p>The games you can play right in the lobby, without switching servers, now have their own menu. Open the server selector (the Nether Star) and click <b>Lobby Minigames</b>, or type <code>/minigames</code> (or <code>/games</code>) anywhere in the lobby. There's room for more games, so if you have an idea for one, post it in the suggestions channel on our <a href="https://discord.gg/hF2bQgU" rel="noopener">Discord</a>.</p>

<h2>New: Daily Word</h2>
<p>Guess the day's five-letter word in six tries. After each guess, every letter turns <b>green</b> (right letter, right spot), <b>yellow</b> (in the word, wrong spot) or <b>grey</b> (not in it). Everyone gets the same word, and a new one arrives every night at midnight (US Central time).</p>
<ul>
<li><b>Play:</b> <code>/word</code>, or Daily Word in Lobby Minigames. On Java 1.21.6 or newer you type your guesses in a pop-up with your board in coloured letters. On Bedrock you use the chest menu and type your guess in chat, where only you see it. On any version, <code>/word &lt;guess&gt;</code> works too.</li>
<li><b>Streaks and stats:</b> solve it on consecutive days to build a streak. <code>/word stats</code> shows your win rate and how many guesses you usually need, and <code>/word top</code> lists today's solvers and the longest streaks.</li>
<li><b>No spoilers:</b> when someone solves it, the lobby sees how many guesses they took and their colour grid, never the word. Once you've finished, you can't post the answer in chat either.</li>
<li><b>On Discord:</b> <code>/dailyword</code> shows how many people have played and solved today's word, yesterday's answer and the longest streaks. Every few days the word is a Minecraft one.</li>
</ul>

<h2>UNO and Balatro Craft</h2>
<p>Both games got a round of fixes. Their buttons respond more reliably, UNO offers <b>Play again</b> when a game ends, and both have a button back to the other minigames.</p>

<h2>Ask Yoink</h2>
<p>Our Discord bot Yoink now answers questions about the servers: the IP, versions, Bedrock, voting, Discord linking, Skyblock, the Anarchy market and more. Use <code>/ask</code> on Discord, mention @Yoink, or type <code>!ask</code> followed by your question in game chat on any server, and the answer comes back to you. It can also tell you who's online and, once your account is linked, your vote points and streak. Answers come from our <a href="/faq/">FAQ</a>, which is bigger now too.</p>

<h2>Skyblock: safer falls, no PvP on islands</h2>
<ul>
<li><b>PvP is off on islands.</b> Nobody can hurt you on your island or someone else's, visitors included. PvP was already off in the hub and the resource zones.</li>
<li><b>Falling off the hub no longer kills you.</b> Players who walked off the edge of the hub were caught and sent back to spawn, then died from the fall when they landed. Now you land safely. Falling off your own island into the void still kills you, as it should in Skyblock.</li>
</ul>
""",
    },
    {
        "slug": "extraction-death-boxes-dual-wield-crate-timers",
        "date": "2026-11-16",
        "title": "Extraction Zone: death boxes, dual wielding and crate timers",
        "summary": "Your gear now waits in a barrel where you died, you can fire two handguns at once, and opened crates show when they restock.",
        "image": "/img/shots/ez-firefight.webp",
        "body": """
<p>Three changes to <a href="/extraction-zone/">Extraction Zone</a> since launch:</p>
<ul>
<li><b>Death boxes.</b> When you die in the zone, what you were carrying goes into a barrel where you fell, labelled with your name, instead of scattering on the ground. It stays for 15 minutes. You can run back for it, and so can anyone else.</li>
<li><b>Dual wielding.</b> Hold a handgun in each hand and one click fires both, a moment apart, at the cost of a little accuracy.</li>
<li><b>Crate timers.</b> A crate you've opened shows a small countdown above it until it restocks. Crates restock every 10 minutes whether or not anyone is nearby, so camping one doesn't block it.</li>
</ul>
<p>All three are in the Field Guide (<code>/guide</code>).</p>
<figure class="pic"><img src="/img/shots/ez-firefight.webp" alt="A firefight in the streets of the Extraction Zone city" width="1600" height="900" loading="lazy"><figcaption>A firefight in the city.</figcaption></figure>
""",
    },
    {
        "slug": "vote-streaks-invite-friends-prices-in-chat",
        "date": "2026-11-16",
        "title": "Vote streaks, rewards for inviting friends, and prices in chat",
        "summary": "Daily vote streaks earn bonus points, inviting a friend pays you both, and typing a ticker like $BTC in chat shows its price.",
        "body": """
<h2>Vote streaks</h2>
<ul>
<li><b>Streak bonus.</b> Vote at least once a day and your streak grows. Your first vote each day earns an extra point from day 3, two from day 7 and three from day 14.</li>
<li><b>MinecraftServers.org bonus.</b> A vote on <a href="https://minecraftservers.org/vote/587166" rel="noopener">MinecraftServers.org</a> earns one extra vote point.</li>
<li><b>Reminders.</b> If you haven't voted today, you get a clickable reminder in chat every 90 minutes. Turn it off with the bell in <code>/vote</code>.</li>
<li><code>/vote links</code> now ticks off the sites you've already voted on today. A new vote day starts at midnight UTC.</li>
</ul>
<h2>Invite a friend</h2>
<p>Type <code>/invite</code> on any server to see how it works. A new player types <code>/invitedby &lt;your name&gt;</code> in their first two days. Once they've played for an hour, you get 10 vote points and they get 5 points and a free vote reward. Bring three friends and you earn the <b>[Recruiter]</b> tag.</p>
<h2>Prices in chat</h2>
<p>Type a ticker such as <code>$BTC</code>, <code>$NVDA</code> or <code>$EUR</code> in chat on any server and the price shows up in chat, with the day's change. Hover for the day's range, click for the chart. It's the same lookup our Discord bot uses.</p>
<h2>A clearer server selector</h2>
<p>The lobby's server selector has been rewritten so each mode says what it is, whether PvP is on and what you keep. Everything is in the same place as before, and a new <b>Not sure? Start here</b> book in the corner suggests a mode for what you feel like playing.</p>
""",
    },
    {
        "slug": "anarchy-welcome-market-combat-tag-outbreak-pack-a-punch",
        "date": "2026-11-16",
        "title": "Anarchy: a new-player welcome, safer market deaths and a combat tag; Outbreak: Pack-a-Punch per gun",
        "summary": "New players on Anarchy get a welcome and survival tips, you keep your items if you die in the market, and you can't teleport out of a fight. Outbreak's Pack-a-Punch now upgrades one gun at a time.",
        "image": "/img/low.webp",
        "body": """
<h2>Anarchy</h2>
<ul>
<li><b>A welcome for new players.</b> Brand-new players now get a short welcome after they land, with buttons for the market, clans, survival tips and the other modes. The tips are there for anyone with <code>/trigger cw_help</code>. Nothing else about spawn has changed: it's still anarchy.</li>
<li><b>Safer market deaths.</b> PvP is still on in the market, but if you're killed there you keep your items, XP and implants. Everywhere else you drop everything as before.</li>
<li><b>Combat tag.</b> For 15 seconds after you hit or are hit by a player, you can't use <code>/home</code>, <code>/spawn</code>, <code>/back</code>, <code>/rtp</code>, <code>/warp</code>, <code>/tpa</code> (or accept one), the market teleport, or leave for another server. No more teleporting out of a fight.</li>
</ul>
<h2>Multiverse: Outbreak</h2>
<ul>
<li><b>Pack-a-Punch per gun.</b> The Arsenal's weapon upgrade now upgrades only the gun you're holding. Each gun has its own tier, I to IV, shown in its description, so you choose which guns to invest in. Tiers still reset when you go down.</li>
<li><b>Dual wielding.</b> Hold a handgun in each hand to fire both with one click.</li>
</ul>
""",
    },
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

# Per-mode listings: Anarchy and Skyblock

The network listing (`listings.md`) stays as it is. These are **extra** listings, one per gamemode, so a player
searching for "anarchy" or "skyblock" finds a listing that is only about that mode and an address that drops them
straight into it. Every claim below is on the website's page for the mode (`/anarchy/`, `/skyblock/`), checked
against the live servers; the same rules apply as in `listings.md` (no player counts, no "biggest/best", no
franchise names, no vote bots or paid votes).

## Before listing: the per-mode addresses

A listing site pings the address you give it, and players type it in, so the address must work first.

1. **DNS** (Squarespace Domains, which took over Google Domains; `crispyanarchy.net` → DNS settings). Add, for each
   of `anarchy` and `skyblock`:

   | Type | Host | Data |
   |---|---|---|
   | CNAME | `anarchy` | `crispyanarchy.net.` |
   | SRV | `_minecraft._tcp.anarchy` | priority 0, weight 5, port 13134, target `anarchy.crispyanarchy.net.` |
   | CNAME | `skyblock` | `crispyanarchy.net.` |
   | SRV | `_minecraft._tcp.skyblock` | priority 0, weight 5, port 13134, target `skyblock.crispyanarchy.net.` |

   The SRV target must be the subdomain itself: the game sends the SRV *target* to the server as the address it
   joined, so a target of `crispyanarchy.net` lands everyone in the lobby (that was the first try, 2026-11-13).
2. **Proxy:** the forced hosts that send `anarchy.crispyanarchy.net` to Anarchy and `skyblock.crispyanarchy.net` to
   Skyblock (falling back to the lobby if that server is down). Staged in `velocity.toml.tonight` since 2026-11-09;
   applied with `velocity reload`, no restart.
3. Check: join `anarchy.crispyanarchy.net` and `skyblock.crispyanarchy.net` from Java and land in the right mode.

Bedrock ignores SRV records and Geyser always lands in the lobby, so Bedrock players still use
`crispyanarchy.net`, port **19100**, and pick the mode in the lobby.

## Anarchy

**Java address:** `anarchy.crispyanarchy.net` (sites with IP and port fields: `anarchy.crispyanarchy.net`, port `13134`)
**Bedrock:** `crispyanarchy.net`, port `19100`, then pick Anarchy in the lobby
**Website:** https://www.crispyanarchy.net/anarchy/

### Title
- 57 chars: `Crispy Anarchy | No Rules, No Resets Since 2020, Implants`
- 49 chars: `Crispy Anarchy | No Rules, Never Reset Since 2020`
- 27 chars: `Crispy Anarchy | Since 2020`

### Short description
> Anarchy with no gameplay rules, no claims and no resets since 2020. 193 custom enchants, cyberpunk implants, a player market and crypto. Java + Bedrock.

### Long description
```
CRISPY ANARCHY: no gameplay rules, no claims, never reset since 2020.

NO RULES, NO CLAIMS, NO RESETS
- Nothing is protected: find bases, raid them, grief them, or build your own legacy
- One world, never wiped since 2020: six years of history around spawn
- Chat reports are off (No Chat Reports)
- The only rules are about people: no hate speech, no real-life threats or doxxing, no spam

193 CUSTOM ENCHANTMENTS
- Nine rarity tiers, from Simple to Mastery and Heroic upgrades
- Buy random enchantment books from the Enchanter with your XP

CYBERPUNK IMPLANTS
- The Ripperdoc sells implants for diamonds or netherite
- Push past your capacity of 20 and risk a cyberpsychosis episode

A MARKET, A BANK AND CRYPTO
- Villager shops trading in Gold Coins and Coin Bags
- A crypto trader with a moving price and its own chart
- A black market whose location is never published: find it for a tag that opens doors

PREFER IT PURE?
- Vanilla Anarchy is a separate plain-survival anarchy server, a click away in the lobby

Also on the same network: Skyblock, a 36-character PvP server and an extraction shooter.

Java: anarchy.crispyanarchy.net (any version 1.13 to 26.3)
Bedrock: crispyanarchy.net, port 19100
Discord: discord.gg/hF2bQgU
```

### Tags
Anarchy, Survival, PvP, Economy, Custom Enchants, Crossplay (Java + Bedrock), Vanilla. Not Factions or Skyblock
here: a mode listing should match its tags.

### Banners
`assets/banner/anarchy/`: `crispy_anarchy_468x60.gif` (standard), `_728x90`, `_1092x140`, each with a still
`.png`/`.jpg` and an `.mp4`. Regenerate with `python3 assets/banner/make_mode_banner.py anarchy <out.gif> <w> <h> anarchy.crispyanarchy.net`.

### Screenshots (for sites with a gallery)
`marketing/site/images/shots/anarchy-crypto.webp`, `anarchy-blackmarket.webp`, and the spawn renders
`marketing/site/images/low.webp`, `wide.webp`.

## Skyblock

**Java address:** `skyblock.crispyanarchy.net` (IP and port fields: `skyblock.crispyanarchy.net`, port `13134`)
**Bedrock:** `crispyanarchy.net`, port `19100`, then pick Skyblock in the lobby
**Website:** https://www.crispyanarchy.net/skyblock/

### Title
- 55 chars: `Crispy Skyblock | Skills, Minions, Pets, Bazaar, No P2W`
- 47 chars: `Crispy Skyblock | Skills, Minions, Pets, No P2W`
- 24 chars: `Crispy Skyblock | No P2W`

### Short description
> Skyblock with 5 skills, 68 collections, 43 minions, pets, a player Bazaar and 36 craftable gear pieces. 7 starter islands. No pay-to-win. Java + Bedrock.

### Long description
```
CRISPY SKYBLOCK: grow an island, level your skills, no pay-to-win.

YOUR ISLAND
- Pick one of 7 themed starter islands
- Upgrade its size, minion slots, co-op slots and ore generator
- Invite friends to build with you; island level grows with what you place

SKILLS AND COLLECTIONS
- 5 skills: Farming, Mining, Combat, Foraging and Fishing, each with level rewards
- 68 collections with nine tiers each: every tier pays coins and skill XP
- Only what you gather counts, so you earn it

MINIONS, PETS AND THE BAZAAR
- 43 kinds of minions that collect while you play elsewhere
- Pets that level up and follow you
- A player-run Bazaar with buy and sell orders

GEAR YOU CRAFT
- Compact farmed resources into enchanted versions
- Craft 17 armour sets and 19 weapons with their own abilities
- Better gear needs more farming, not real money

BEYOND YOUR ISLAND
- Regenerating mines and forests full of levelled mobs
- The Sky Lord's Rift, with a boss
- Loot and dungeons fall from the sky onto your island
- Buy a hub plot for your shop or house

Also on the same network: a no-rules anarchy server, a 36-character PvP server and an extraction shooter.

Java: skyblock.crispyanarchy.net (any version 1.13 to 26.3)
Bedrock: crispyanarchy.net, port 19100
Discord: discord.gg/hF2bQgU
```

### Tags
Skyblock, Economy, Survival, RPG, PvE, Crossplay (Java + Bedrock).

### Banners
`assets/banner/skyblock/`: same sizes and formats as Anarchy. Regenerate with
`python3 assets/banner/make_mode_banner.py skyblock <out.gif> <w> <h> skyblock.crispyanarchy.net`.

### Screenshots
`marketing/site/images/shots/skyblock-hub.webp`, `skyblock-minion.webp`, `sb-collections.webp`.

## Where to list (checked 2026-11-13)

**The 7 sites we're already on: no extra listings.** TopG ("One server = one listing per game"), MinecraftServers.org
("only create one listing for the same server") and Minecraft-MP (same MOTD, player count and IP = duplicate; network
sub-servers can't take votes) forbid it; Planet Minecraft very likely does (one listing per server, nothing leading to
the same hub). ServerTilt (blocks only the same hostname + port, 4 listings per account) and MMTop200 (no rule, but
removes anything "duplicated") are unclear: ask their support before adding a mode there. Keep the network listing.

**New sites: one listing each, led by one mode.** We aren't listed on these yet, so a single listing per site is
within every rule, and it can be the Anarchy or Skyblock listing (its own address, copy and banner):

| Site | List | Its rule on more than one listing | Notes |
|---|---|---|---|
| minecraft-serverlist.com | **Anarchy** | one listing per server (plus one Bedrock listing) | free; Anarchy and Skyblock categories; voting |
| minelist.net | **Anarchy** | same IP = duplicate | Anarchy and Skyblock categories; voting |
| minecraft.menu | **Anarchy** | none stated | free; Anarchy page, Skyblock category; monthly votes |
| mcserv.org | **Anarchy** | none stated | free; Skyblock filter, Anarchy tag; voting |
| mclike.com | **Skyblock** | one listing per server | Anarchy and Skyblock filters; voting |
| serverlist.net | **Skyblock** | may hide or merge duplicates | free; Anarchy and Skyblock categories; voting |
| craftlist.org | **Skyblock** | none stated | Skyblock category (no Anarchy one); NuVotifier |
| blockatlas.net | **Skyblock** | none stated | Anarchy and Skyblock categories; monthly votes |
| minecraftiplist.com | **Skyblock** | none stated | Anarchy and Skyblock tags; Votifier |

Not checked (their pages refused automated reads): topminecraftservers.org, findmcserver.com, Minecraft-Server-List.
"None stated" isn't permission: list one mode there, and add the other only if their support says yes.

Votes: give each listing the same Votifier settings as the network listing (address, port and public key from the
lobby's NuVotifier); votes reach the lobby the same way, and players pick which server gets the reward in `/vote`.
To show a new site in the lobby's `/vote` menu, add it to `votes.links` in the lobby's CrispyLobby config.

**Outside server lists** (no one-listing rule; each post can be about one mode): Reddit's server-advertising
communities (read each one's posting rules and limits first), Discord server-advertising servers, and the website's
own `/anarchy/` and `/skyblock/` pages.

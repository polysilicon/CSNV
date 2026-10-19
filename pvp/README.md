# Crispy PvP

Kit/arena PvP server (AMP instance `CrispyPvP01`, Fabric 26.2, Velocity name `pvp`). It replaces Bending, whose
instance was deleted after a backup to `/AMPStorage/backups/Bending01-20261019.tgz`.

## Instance
| | |
|---|---|
| Game / AMP port | 25569 / 8085 (127.0.0.1, behind Velocity) |
| RCON | 25582. Password in `server.properties`, copied to `RCON_PVP` in `/etc/crispybot.env` |
| Memory | 4 GB max, same idle-shrink flags as the other servers |
| World | superflat; AMP settings: `Minecraft.WorldType=FLAT`, `Game.GameMode=adventure`, `StandaloneServer=False` |
| Mods | fabric-api, fabric-permissions-api, FabricProxy-Lite (config copied from Anarchy), ferritecore, lithium, Moonrise, NoChatReports, spark |
| Datapacks | `crispy_enchants` (copied from Anarchy), `crispy_cyberware` (built with `anarchy/cyberware/build.py --pvp`), `crispy_pvp` (this folder) |

AMP rewrites `server.properties` on start, so change game settings through AMP, not the file.

## How it plays
- Players spawn in a safe neon lobby at 0 101 0, where they're immune to damage and can't deal any.
- **Kit Dealer** (left NPC) opens a chest menu of 10 kits. Click one and you're dropped at one of 8 random PvP arena
  spawns with 3 s of spawn protection. The kit's custom enchants and cyberware are already on.
- **Outbreak** (right NPC, or the zombie head in the kit menu) opens the PvE loadout menu. Pick a kit to queue.
- PvP kills:
  - heal the killer and give 10 s of Absorption and a golden apple;
  - streaks are announced at 3, 5, 10 and so on;
  - the sidebar shows total kills.
- Death, logout, `/spawn`, `/lobby` or `/trigger pvp.spawn` sends you back to the lobby, clearing your inventory and
  implants. `/spawn` and `/lobby` are blocked for 10 s after you take damage.
- The PvP arena is a 61×61 neon city at night (centre 0, -60, 100).
- **Leaderboards** on the south side of the lobby show the top 5 for Kills (`pvp.kills`), Best Kill Streak (`pvp.best`) and
  Best Outbreak Wave (`pve.best`). The mod rewrites them every 5 s. `pvp:admin/place_leaderboard` re-places them.

| Kit | Gear | Cyberware |
|---|---|---|
| Edgerunner | Katana: Sharpness V, Lifesteal III, Double Strike II | Sandevistan, Mantis Blades, Reflex Tuner, Kiroshi |
| Juggernaut | Sword + shield, netherite Prot IV with Armored III / Tank II | Subdermal Armor, Titanium Bones, Second Heart, Lynx Paws |
| Sniper | Bow: Power V, Infinity, Lethal Sniper III, Lightning Arrows II | Kiroshi, Reinforced Tendons, Biomonitor, Reflex Tuner |
| Berserker | Axe: Sharpness V, Cleave III, Bleed III, Rage II | Gorilla Arms, Berserk, Titanium Bones |
| Netrunner | Sword: Sharpness IV, Assassin III, Poison II, plus Invisibility | Sandevistan, Lynx Paws, Reflex Tuner, Kiroshi |
| Medic | Lifesteal sword, Angelic III chest, 4 Healing II + 2 Regen | Biomonitor, Bionic Lungs, Kiroshi, Reflex Tuner |
| Pyro | Fire Aspect II + Execute sword, Flame bow, Fire Prot IV | Gorilla Arms, Berserk, Biomonitor, Lynx Paws |
| Ranger | Crossbow: Quick Charge III, Multishot, Longbow II, Venom II | Kiroshi, Reinforced Tendons, Reflex Tuner, Subdermal Armor |
| Shinobi | Shadow Assassin + Featherweight sword, 8 pearls, Dodge/Trickster, Springs/Gears | Sandevistan, Lynx Paws, Kiroshi, Subdermal Armor |
| Skyhammer | Mace: Density IV, Wind Burst II, 16 wind charges | Reinforced Tendons, Titanium Bones, Second Heart, Subdermal Armor |

All kit gear is unbreakable, and every kit also gets 16 steak and 2 golden apples.

## Outbreak (PvE waves)
- **Queue**: the first player to queue starts a 10 s countdown, and anyone who queues meanwhile joins the same run.
  If you queue during a run, you drop in at the next wave break.
- **Arena**: ruins at 0, -60, 300, with 12 barred mob windows around the walls and the **Arsenal** shop in the middle.
  Team members are on team `pve`, so there's no friendly fire, and they see their points on the team sidebar.
- **Waves**: there are 6 + 4·(wave−1) mobs, plus 3 + 2·(wave−1) for each extra player, capped at 150. At most 30 are alive at once.
  - New types unlock as you go: husks at wave 2, skeletons at 3, spiders at 4, vindicators at 6, wither skeletons at 7, creepers at 8.
  - Mobs get +15% health and +8% damage per wave.
  - Every 5th wave adds an **Abomination** boss (a giant zombie, 150 base health, with a boss bar).
  - The last 4 mobs, and every mob in a wave that runs over 3 minutes, glow.
- **Points**:
  - start with 500;
  - 100 per kill;
  - a 100 × wave bonus for everyone still standing when a wave is cleared.
- **Arsenal**: Golden Apple 500, Med Kit 750, Ammo 250, Strength 1,000, Juggernog (+3 hearts) 2,500,
  Speed Cola 2,000, Mystery Box 950 (one of four wonder weapons), Ray Bow 5,000, Rations (16 steak) 100.
  Juggernog and Speed Cola are one per life, and you aren't charged if you already have one.
- **Food**: Rations in the Arsenal, plus 4 steak for every survivor whenever a wave is cleared.
- **Down**: if you die you spectate above the arena and come back with your kit at the next wave. The run ends when
  everyone is down. Your best wave is saved in `pve.best`, and a new server record (`#record pve`) is announced to everyone.

Kits, shop, mob pool, spawns and arena layouts are tables at the top of `build.py`.

## Building
```
python3 build.py <outdir>                 # -> <outdir>/crispy_pvp, copy into world/datapacks
```
The dialog only loads on a server restart. To (re)build the lobby and arena:
```
forceload add -16 -16 16 16
forceload add -32 64 32 136
forceload add -24 276 24 324
function pvp:admin/build                  # build_lobby (+ place_npc), build_arena, build_pve
forceload remove -32 64 32 136
forceload remove -24 276 24 324
```
`pvp:admin/place_npc` re-places just the lobby NPCs and signs. The lobby chunks stay force-loaded.

## Admin room
A sealed room under the lobby (floor y 90) holds:
- a max-level book of every custom enchant (193 of them), in chests labelled by gear type: melee, ranged, tools, armor;
- one of every cyberware implant, plus a Neuroblocker.

```
/function pvp:admin/room       go in (tags you pvp.admin, creative mode, implants cleared)
/function pvp:admin/leave      back to the lobby
/function pvp:admin/fill_room  refill the chests
/function pvp:admin/unbreakable  make everything you're carrying unbreakable (handy before /pvpkit create)
```
The stray check leaves `pvp.admin` players alone in the room. `enchants.json` (id, max level, group) was exported from
`crispy_enchants`; regenerate it if enchants are added.

**Heads**: the Head Index mod (`headindex-1.2.1.jar`, MIT, server-side) gives ops a `/head` menu of minecraft-heads.com
heads, for kit icons and gear. It needs a free minecraft-heads.com API key in its config.

## Admin-made kits
Set up your own inventory (hotbar, inventory, armor, offhand). If you want implants too, install them with the items
from `/function cyber:admin/give`. Then run:
```
/pvpkit create <name>     save it, or replace the kit with that name (the held item becomes the menu icon)
/pvpkit list              ids, authors, item and implant counts
/pvpkit delete <id>
```
- Up to 10 custom kits.
- They show up in the bottom two rows of both the Kit Dealer and the Outbreak menus.
- They're given exactly as saved, with gear in the same slots and implants installed.
- Ids start at 101.
- They're stored in the world (`pvp:customkits`), so `/reload` and datapack updates keep them.
- The commands need op (permission level 2).

## Server mod (spawnmod/)
`spawnmod/` is a small server-side Fabric mod with two parts:
- `/spawn` and `/lobby`, which run `/trigger pvp.spawn`, so the 10 s combat lock still applies.
- `/pvpmenu <name>`, which opens a chest menu defined in storage `pvp:menus` (written by `pvp:load`). Clicking an item
  closes the menu and runs its `cmd` as the player, always a `/trigger`. Every other click is cancelled. A menu's
  `custom_kits` field adds the admin-made kits.
- `/pvpkit`, which manages admin-made kits (see above). The datapack uses `pvpkit give <id>` to hand one out. Minecraft 26.x is unobfuscated, so it compiles straight against the server jar with
Java 25:
```
spawnmod/build.sh <lib-dir> <path-to-javac-25>   # lib-dir: server-26.2.jar (from the official bundler), brigadier,
                                                  # fabric-loader 0.19.5, fabric-api 0.161.0 with its nested jars unpacked
```
Copy `crispy-pvp-spawn-1.3.1.jar` into `mods/` and restart the server.

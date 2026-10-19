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
- Right-click the **Kit Dealer**, pick a kit, and you're dropped at one of 8 random arena spawns with 3 s of spawn
  protection. Your kit's custom enchants and cyberware are already on.
- **Kills**:
  - the killer is healed, gets 10 s of Absorption and a golden apple;
  - streaks are announced at 3, 5, 10, 15 and so on, and when a streak of 3+ ends;
  - the sidebar shows total kills.
- **Death**, logging out, or `/trigger pvp.spawn` (blocked for 10 s after taking damage) sends you back to the lobby.
  Your inventory and implants are cleared. Gamerules: keep inventory and immediate respawn on, so nothing drops.
- The arena is a 61×61 neon city at night (centre 0, -60, 100), with walls, a barrier ceiling and cover buildings.

| Kit | Weapon | Cyberware |
|---|---|---|
| Edgerunner | Netherite katana: Sharpness V, Lifesteal III, Double Strike II | Sandevistan, Mantis Blades, Reflex Tuner, Kiroshi |
| Juggernaut | Netherite sword + shield; netherite Prot IV with Armored III and Tank II | Subdermal Armor, Titanium Bones, Second Heart, Lynx Paws |
| Sniper | Bow: Power V, Infinity, Lethal Sniper III, Lightning Arrows II | Kiroshi, Reinforced Tendons, Biomonitor, Reflex Tuner |
| Berserker | Netherite axe: Sharpness V, Cleave III, Bleed III, Rage II | Gorilla Arms, Berserk, Titanium Bones |
| Netrunner | Diamond sword: Sharpness IV, Assassin III, Poison II, plus Invisibility | Sandevistan, Lynx Paws, Reflex Tuner, Reinforced Tendons |

All kit gear is unbreakable, and every kit also gets 16 steak and 2 golden apples.

Kits, spawns, cover buildings and positions are all tables at the top of `build.py`.

## Building
```
python3 build.py <outdir>                 # -> <outdir>/crispy_pvp, copy into world/datapacks
```
The dialog only loads on a server restart. To (re)build the lobby and arena:
```
forceload add -16 -16 16 16
forceload add -32 64 32 136
function pvp:admin/build                  # build_lobby (+ place_npc) and build_arena
forceload remove -32 64 32 136
```
`pvp:admin/place_npc` re-places just the Kit Dealer and the lobby signs. The lobby chunks stay force-loaded.

## /spawn and /lobby
`spawnmod/` is a tiny server-side Fabric mod that adds `/spawn` and `/lobby`. Both run `/trigger pvp.spawn`, so
the 10 s combat lock still applies. Minecraft 26.x is unobfuscated, so it compiles straight against the server jar with
Java 25:
```
spawnmod/build.sh <lib-dir> <path-to-javac-25>   # lib-dir: server-26.2.jar (from the official bundler), brigadier,
                                                  # fabric-loader 0.19.5, fabric-api 0.161.0 with its nested jars unpacked
```
Copy `crispy-pvp-spawn-1.0.0.jar` into `mods/` and restart the server.

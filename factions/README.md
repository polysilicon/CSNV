# Crispy Factions — "Working Man's 2013 Factions"

Sub-server on the Crispy network (Velocity). 1.8-era combat, classic cannon/obsidian raiding,
prime-time raid windows, no pay-to-win.

| | |
|---|---|
| AMP instance | `Factions01` (start on boot), panel port 8089 |
| Engine | Paper **1.21.11** (build 132), Java 21, 6 GB heap |
| Game port | `127.0.0.1:25572` — reachable only through Velocity (`factions` server) |
| RCON | `127.0.0.1:25581`, password in `/root/factions_rcon_password.txt` on the VM |
| Lobby | DeluxeHub server selector, slot 13 (TNT icon) → `[PROXY] factions` |

> FactionsUUID 4.7.x is a paid Spigot resource, so the server runs **SaberFactions 4.1.9**, a free
> FactionsUUID fork with the same `/f` commands, power system and roles. SaberFactions is tested up
> to MC 1.21, which is why the engine is Paper 1.21.11 (newer clients join via ViaVersion).

## Plugin stack

| Plugin | Version | Role |
|---|---|---|
| OldCombatMechanics | 2.7.0 | 1.7/1.8 combat |
| SaberFactions | 4.1.9 | factions, claims, power |
| EssentialsX (+Chat, +Spawn) | 2.22.0 | economy, kits, homes, `/craft`, `/echest` |
| Vault | 1.7.3 | economy bridge |
| LuckPerms | 5.5.87 | ranks |
| EconomyShopGUI | 7.3.2 | `/shop` |
| Chunky | 1.4.40 | pre-generation |
| ViaVersion / ViaBackwards | 5.12.x | newer clients |
| **CrispyFactions** (custom) | 1.0.0 | raid window, obsidian durability, Aegis Star, collector hopper, item bans, `/nv`, AFK |
| HMCWraps | — | *not installed*: download from SpigotMC/Polymart and drop into `plugins/` |

`install_plugins.sh` downloads everything except HMCWraps; `configure.py` applies every setting below.

## 1. Combat (OldCombatMechanics)
- All worlds locked to the `old` modeset: no attack cooldown, sword blocking (Paper consumable animation),
  old potion values + 1.8 splash throwing, old armour strength, no sweep, old tool damage/crits/regen.
- `disable-offhand` always on (no shields/totems in the offhand); shield, mace and end-crystal crafting denied.
- CrispyFactions additionally blocks: elytra gliding (and wearing), tridents (throwing + melee), mace and
  netherite weapons in PvP, netherite smithing upgrades, wearing netherite armour, totem resurrection,
  end-crystal placement outside the End, and end-crystal damage to players.

## 2. Factions & raiding
- SaberFactions: 15 members max, no alts, power 10 / -10, -2 per death, +0.2/min, no offline regen.
- Disabled: `/f fly`, `/f tnt` bank + tntfill, `/f upgrades`, `/f chest`, `/f vault`, `/f missions`, `/f alts`, grace.
  `factions.fly` / `factions.tnt` are also denied in LuckPerms.
- Obsidian durability (CrispyFactions): **5 TNT hits or 3 creeper hits** (charged creepers count double),
  radius 3. Obsidian touching water/lava is immune and TNT that explodes in water does nothing, so watered
  walls need sand+TNT hybrid cannons. Damage is forgotten after 30 min without a hit. No regen walls, no genbuckets.
- Cannon physics: falling-block / TNT height nerfs off, TNT moves in water, `max-tnt-per-tick: 500`,
  `optimize-explosions: true`.
- World borders: overworld 5000×5000 (±2500), nether 2500×2500. Both pre-generated with Chunky.

## 3. Prime-time raid window (America/New_York)
| Days | Raid window |
|---|---|
| Mon–Fri | 18:00 – 23:00 |
| Sat–Sun | 12:00 – 24:00 |

Outside the window, explosions deal **0 damage to blocks inside faction claims** (obsidian included).
Wilderness/warzone PvP and farming are unaffected. Warnings at 60/15/5/1 min, title + broadcast on open/close.
`/raidwindow` (`/rw`) shows status. Admin override: `/raidwindow force open|closed|auto`.

## 4. Aegis Vacation Star
- Item: glinting nether star `✦ Aegis Vacation Star (25 Raid-Hours) ✦`.
- `/kit aegis`: free once per 14-day cycle; cycles start every other Friday from **2026-10-16**
  (`aegis.kit.first-friday`). Requires **10 h playtime**.
- `/shop` → Specials: **$2,500,000**.
- Right-click inside your own claim as Leader/Co-Leader during peacetime → banks **25 raid-window hours**
  (ticks only while the window is open = 5 weeknights).
- Guardrails: not during a window or within **6 h** of one opening; one active per faction;
  **14-day** faction cooldown after it expires.
- Pacifism lock while active: members can't ignite TNT or place creepers in enemy territory, and
  dispensers in the faction's own land won't fire TNT/creeper eggs.
- `/aegis` shows status; admin `/aegis give <player> [n]`, `/aegis collector <player> [n]`, `/aegis reset <faction>`.

## 5. Economy (`/shop`)
Only the farm table pays out; all other sale prices were removed from the default shop.

**Phase 1 — sell**
| Item | Sell |
|---|---|
| Cactus | $10 |
| Sugar Cane | $15 |
| Blaze Rod | $35 |
| Gunpowder | $20 |

**Phase 1 — buy**
| Item | Price |
|---|---|
| Obsidian | $200 |
| TNT | $150 |
| Creeper Spawn Egg | $15,000 |
| Blaze Spawner | $200,000 |
| Skeleton / Zombie Spawner | $75,000 |
| Splash Healing II | $150 |
| Speed II | $250 |
| Fire Resistance | $250 |
| Sand / Red Sand / Gravel | $5 |
| Water Bucket | $50 |
| Cactus / Sugar Cane (to start farms) | $100 / $150 |
| Aegis Vacation Star | $2,500,000 |
| Cactus Collector Hopper | $50,000 |

Building sections (Blocks, Decoration, Dyes, Redstone, Workstations, Food) are buy-only.
Starting balance $500.

**Phase 2 — day 11** (`phase2.launch-date` + 10 days; automatic, or `/crispyfactions phase2`)
| Item | Price |
|---|---|
| Iron Golem Spawner | buy $650,000 |
| Iron Ingot | sell $40 |

**Cactus Collector Hopper**: one per chunk; every cactus that drops in that chunk goes straight into it
(no water streams, no item entities). Break it to get the collector back.

## 6. Ranks (LuckPerms, no P2W)
| Group | Inherits | Perks |
|---|---|---|
| default | — | Essentials basics, `/kit starter`, `/shop`, `/f` |
| VIP `&a[VIP]` | default | `/craft`, `/echest`, `/nv`, 2 h AFK limit, `/kit vip` |
| Venom `&5[Venom]` | VIP | `/kit venom` |
| Immortal `&6[Immortal]` | Venom | `/kit immortal` |

Rank kits (daily) are base-builder supplies (sand, glass, redstone, pistons, hoppers, repeaters, dispensers)
plus starter diamond gear at Protection II / Sharpness II only. AFK kick: 30 min, 2 h for ranks,
exempt with `crispy.afk.exempt`. Give a rank: `lp user <name> parent add vip`.

**Wraps**: gear drops normally on death, so wrapped Prot IV / Sharp V gear becomes a physical trophy.
Install HMCWraps for the visual skins.

## Still to do in-game (needs a player)
1. `/setspawn` at the spawn build, then claim it: `/f claim safezone` (and `/f claim warzone` around it).
2. Optional: create `/warp`s, adjust `/kit starter`.
3. Set `phase2.launch-date` and `aegis.kit.first-friday` in `plugins/CrispyFactions/config.yml` to the
   real launch date, then `/crispyfactions reload`.

## Building CrispyFactions
```
CP=$(find <server>/libraries -name '*.jar' | tr '\n' ':')<path>/SaberFactions.jar
javac --release 21 -proc:none -cp "$CP" -d out $(find crispyfactions/src -name '*.java')
cp crispyfactions/res/* out/ && (cd out && jar cf ../CrispyFactions-1.0.0.jar .)
```

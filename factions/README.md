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
| mcMMO | 2.3.002 | RPG skills (built from the GPL source, commit 25474dc) |
| ViaVersion / ViaBackwards | 5.12.x | newer clients |
| **CrispyFactions** (custom) | 1.1.0 | raid window, obsidian durability, Aegis Star, collector hopper, item bans, `/nv`, AFK, combat tag |
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
- Locator bar (player dots in the XP bar) off: `gamerule minecraft:locator_bar false` in all three worlds.
- World borders: overworld 5000×5000 (±2500), nether 2500×2500. Both pre-generated with Chunky.

## 3. Prime-time raid window (America/New_York) — currently OFF

> The schedule is switched off (`raid-window.enabled: false` in `plugins/CrispyFactions/config.yml`):
> claims can be raided at any time, and an Aegis Star simply protects for 25 real hours (it can be
> activated any time; the 14-day cooldown and pacifism lock still apply). Set it to `true` and run
> `/crispyfactions reload` to bring back the schedule below.

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

## PvP combat tag (CrispyFactions 1.1.0)
- Hitting or being hit by a player (melee, bow, snowball, rod) tags **both** players for **15 s**; the action bar counts down.
- While tagged you can't:
  - run escape commands: `/spawn`, `/home`, `/back`, `/warp`, `/tpa…`, `/f home`, `/f stuck`, `/echest`, `/kit`, `/fly` and more (`combat-tag.blocked-commands`);
  - teleport by command;
  - walk or ender-pearl into the spawn safezone.
- **Logging out, timing out or switching server while tagged kills you**, and your items drop where you stood.
  Kicks (restarts, AFK kick, staff) aren't punished.
- `/combat` (`/ct`) shows your timer. `crispy.combat.bypass` exempts a player (off for everyone by default, ops included).
- Settings are in `plugins/CrispyFactions/config.yml` → `combat-tag`; apply changes with `/crispyfactions reload`.

## mcMMO (classic setup)
- Built from source (`git checkout 25474dc && mvn package`), because the SpigotMC download is paid. Configs are in `mcmmo/`.
- Retro 1–1000 scale, every skill capped at **1000**, scoreboard sidebar on, stats tracking and April Fools off.
  Spawner mobs give no XP (default).
- PvP toned down: Archery Daze max 25% (was 50), Axes Armor Impact 10% (was 25), Unarmed Disarm max 15% (was 33).
- Blacksmith corner beside the spawn point: iron block at 7 73 13 = **Repair**, gold block at 7 73 16 = **Salvage**.

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

## Spawn & PvP arena
![spawn map](spawn_map.png)

Built by `gen_spawn.py` (writes the `crispyspawn` datapack; run each `cspawn:<part>` function with the area force-loaded).
The area x -80..79, z -176..79 was changed to the plains biome so snow doesn't settle on the build.

- **Spawn hub** (centre 0,0): walled stone-brick plaza, floor y72, walls at ±40 with corner towers, beacon fountain,
  four planters with benches, info signs. The spawn point is 0.5 73 14.5, facing north. It is set as the world spawn
  and in Essentials `spawn.yml` (default + newbies; the newbie kit is now `starter`). There are gates on all four sides,
  with stairs down to y65 and roads out.
- **PvP colosseum** (centre 0,-112): sand floor y64 with r=25, eight lit pillars, a 7×7 king-of-the-hill dais with a gold
  centre, eight tiers of seating and four tunnel entrances. A flat walled road at y64 runs from the spawn north gate to
  the south entrance.
- **Zones** (`apply_zones.py`, run only while the server is stopped): chunks -3..2 are the **safezone** (x/z -48..47);
  chunks -12..11 around it are the **warzone** (x/z -192..191; PvP on, no building, TNT/creeper/fireball damage blocked).
  The script only touches unclaimed or zone chunks.

## Still to do
1. Optional: create `/warp`s, adjust `/kit starter`.
2. Set `phase2.launch-date` and `aegis.kit.first-friday` in `plugins/CrispyFactions/config.yml` to the
   real launch date, then `/crispyfactions reload`.

## Building CrispyFactions
```
CP=$(find <server>/libraries -name '*.jar' | tr '\n' ':')<path>/SaberFactions.jar
javac --release 21 -proc:none -cp "$CP" -d out $(find crispyfactions/src -name '*.java')
cp crispyfactions/res/* out/ && (cd out && jar cf ../CrispyFactions-1.1.0.jar .)
```

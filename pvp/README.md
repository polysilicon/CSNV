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
| Datapacks | `crispy_enchants` (copied from Anarchy), `crispy_cyberware` (built with `anarchy/cyberware/build.py --pvp`; used by the cyberpunk kits and the admin room), `crispy_pvp` (this folder) |

AMP rewrites `server.properties` on start, so change game settings through AMP, not the file.

## How it plays
- Players spawn in a safe stone hub at 0 101 0, where they're immune to damage and can't deal any.
- **Kit Dealer** (left NPC) opens a chest menu of 20 kits. Click one and you're dropped at one of 8 random arena
  spawns with 3 s of spawn protection.
- **Outbreak** (right NPC, or the zombie head in the kit menu) opens the map menu: pick one of the four maps (or Random),
  then pick a kit to queue.
- PvP kills:
  - heal the killer and give 10 s of Absorption and a golden apple;
  - streaks are announced at 3, 5, 10 and so on;
  - the sidebar shows total kills.
- Death, logout, `/spawn`, `/lobby` or `/trigger pvp.spawn` sends you back to the lobby, clearing your inventory and
  implants. `/spawn` and `/lobby` are blocked for 10 s after you take damage.
- The PvP arena is a 61×61 sandstone colosseum (centre 0, -60, 100).
- **Leaderboards** on the south side of the lobby show the top 5 for Kills (`pvp.kills`), Best Kill Streak (`pvp.best`) and
  Best Outbreak Wave (`pve.best`). The mod rewrites them every 5 s. `pvp:admin/place_leaderboard` re-places them.

### Kits
The menu shows all 20 kits mixed together in three rows; custom kits go on the row below.

**Franchise kits** have two **ability items** each (`abilities.py`):
- They're in the hotbar (clay balls with their own look, so they never clash with cyberware). Right-click to use one;
  it comes back to the same slot right after.
- The item shows its cooldown sweep, like an ender pearl.
- Abilities hit mobs and enemy players, never Outbreak teammates.

| Kit | Gear | Abilities |
|---|---|---|
| Jedi Knight | Lightsaber (Sharpness V), robes, Jump Boost II | **Force Push** (cone knockback, 7 s), **Mind Trick** (blind + slow, 15 s) |
| Sith Lord | Red lightsaber (Sharpness V, Fire Aspect) | **Force Lightning** (cone, 6 dmg + slow, 9 s), **Force Choke** (lift + Wither, 14 s) |
| Hero of Hyrule | Master Sword, Hylian Shield, bow | **Spin Attack** (7 dmg around you, 6 s), **Hookshot** (reel a target in, 8 s) |
| Spartan | Assault rifle (crossbow), energy sword, trimmed netherite | **Frag Grenade** (10 dmg where it lands, 10 s); passive **energy shield**: 4 absorption hearts that come back after 4 s without damage |
| Doom Slayer | Super Shotgun (multishot), Crucible | **Chainsaw** (14 dmg up close, 12 s), **Berserk Rune** (Strength II/Speed II/Resistance, 25 s); passive **glory kills** (every kill heals) |
| Witcher | Steel sword, silver sword (Smite V), 2 Swallow potions | **Igni** (3 fireballs, 8 s), **Quen** (shield, 16 s) |
| Mario | Hammer (mace), overalls, Resistance I | **Fireball** (3 s), **Super Jump Punch** (leap + 6 dmg uppercut, 8 s) |
| Pikachu | Iron Tail sword, Speed I, Resistance I | **Thunder Jolt** (zap 6 dmg, 4 s), **Quick Attack** (dash, 6 s) |
| Kirby | Star sword, Jump Boost II, Resistance I | **Inhale** (suck in + 5 dmg + 2 hearts, 10 s), **Stone** (immune 3 s + slam, 12 s) |
| Samus | Arm Cannon (bow), Varia Suit (gold) | **Charge Shot** (explosive, 6 s), **Screw Attack** (spin up + 6 dmg, 8 s) |

**Character heads, enchants and sizes**:
- Each character kit wears its character's head as the helmet. The head has diamond-helmet armor and Protection IV,
  so it costs no defence.
- The heads are also the kit icons in both menus.
- The textures come from the Head Index (`/head`) minecraft-heads.com cache, picked into `heads.json`. Edgerunner
  wears David Martinez.
- Custom enchants:

  | Kit | Custom enchants |
  |---|---|
  | Jedi | Double Strike II, Dodge II |
  | Sith | Demonic Lifesteal III, Paralyze II |
  | Link | Blessed III, Eagle Eye III, Springs II |
  | Spartan | Eagle Eye III, Armored III |
  | Doom Slayer | Bleed IV, Rage III, Tank II |
  | Witcher | Cleave III, Bleed III, Dodge II |
  | Mario | Pummel II, Springs III |
  | Pikachu | Paralyze III |
  | Kirby | Devour III, Antigravity II |
  | Samus | Explosive II, Eagle Eye III, Reinforced III |

- Sizes (`scale` modifier `pvp:size`, removed on `to_lobby`, going down and Outbreak entry): Pikachu and Kirby 0.6×,
  Mario 0.85×, Spartan 1.1×, Samus 1.08×, Adam Smasher 1.3×.

**Other kits**:

| Kit | Gear | Abilities |
|---|---|---|
| Randy Marsh (South Park) | No weapon: fists +7 damage at sword attack speed; light blue shirt, jeans and brown shoes (leather); **Sandevistan** cyberware (double-tap sneak) | **Tegridy** (Regeneration II + Speed I 6 s, 20 s) |
| Courier Six (Fallout: New Vegas) | Lucky (revolver crossbow, Eagle Eye III), Machete (Bleed II), Ranger armor + Desert Ranger head | **V.A.T.S.** (enemies within 12 blocks: Slowness III + glowing 5 s; you: Strength I, 18 s), **Stimpak** (Instant Health II + Regeneration II, 15 s) |

Randy's head came from a skin uploaded to MineSkin (no Randy in the head database). The same works for any character:
upload the skin at mineskin.org and put its texture value in `heads.json`.

**Cyberpunk kits** (Edgerunner, Netrunner, Adam Smasher) keep their cyberware:

| Kit | Gear | Cyberware |
|---|---|---|
| Edgerunner | Katana: Sharpness V, Lifesteal III, Double Strike II | Sandevistan, Mantis Blades, Reflex Tuner, Kiroshi |
| Netrunner | Sword: Sharpness IV, Assassin III, Poison II, plus Invisibility | Sandevistan, Lynx Paws, Reflex Tuner, Kiroshi |
| Adam Smasher | Militech Heavy Cannon (crossbow: Quick Charge III, Multishot, Piercing II), Arasaka Breaker (axe: Sharpness IV, Cleave III), netherite Prot III with a redstone rib trim (chest: Armored III, Explosive Immunity III), gunmetal cyborg head, 1.3× size | Projectile Launch System (sneak + jump), Berserk (double-tap sneak), Subdermal Armor, Titanium Bones |

**Classic kits** have no cyberware, just custom enchants and one passive effect:

| Kit | Gear | Passive |
|---|---|---|
| Juggernaut | Sword + shield, netherite Prot IV with Armored III / Tank II | Health Boost II |
| Sniper | Bow: Power V, Infinity, Lethal Sniper III, Lightning Arrows II | Night Vision |
| Berserker | Axe: Sharpness V, Cleave III, Bleed III, Rage II | Speed I |
| Medic | Lifesteal sword, Angelic III chest, 4 Healing II + 2 Regen | Regeneration I |
| Pyro | Fire Aspect II + Execute sword, Flame bow, Fire Prot IV | Fire Resistance |
| Ranger | Crossbow: Quick Charge III, Multishot, Longbow II, Venom II | Speed I |
| Shinobi | Shadow Assassin + Featherweight sword, 8 pearls, Dodge/Trickster, Springs/Gears | Speed II |
| Skyhammer | Mace: Density IV, Wind Burst II, 16 wind charges | Jump Boost II |

All kit gear is unbreakable, and every kit also gets 16 steak and 2 golden apples.

## Outbreak (PvE waves)
- **Progression** (Arsenal):
  - **Pack-a-Punch** upgrades the weapon in your hand, tier I / II / III for 2,000 / 4,000 / 7,500 points. Each tier adds
    Sharpness +2 (swords and axes), Power +2 (bows), Piercing and Quick Charge +1 (crossbows), Impaling +2 (tridents) or
    Density and Breach +1 (maces). Tier III also adds Fire Aspect II, Flame + Punch, Multishot, Channeling or Wind Burst.
    The tier is stored on the item (`custom_data.pvp_tier`) and shown as gold lore stars.
  - **Armor Upgrade**, for 1,500 / 3,000 / 6,000 points: I gives +1 Protection and Unbreaking on everything you wear,
    II gives Resistance I, and III gives +2 hearts.
  - Perks: **Double Tap** (Strength I, 3,000) and **PhD Flopper** (Fire Resistance + Jump Boost, 1,500), alongside
    Juggernog and Speed Cola.
  - Upgrades and perks last until you go down; you come back with your kit as it was.
  - **Veteran bonus**: you start each run with 500 points + 25 per wave of your best run (`pve.best`), capped at +1,000.
- **Queue**: the first player to queue starts a 10 s countdown, and anyone who queues meanwhile joins the same run.
  If you queue during a run, you drop in at the next wave break.
- **Maps**: four arenas of the same size, each with 12 barred mob windows, the player spawns and the **Arsenal** in
  the middle, but with their own layout. Each player's pick is kept in `pve.map`.
  - The first player to queue decides the run's map, and the lobby is told which map is starting.
  - Anyone who queues after that joins the run already under way, whatever they picked, and is told so.
  - **Back to maps** (slot 45) in the kit menu goes back to the map menu.

  | Map | Centre | Layout | Extra mobs |
  |---|---|---|---|
  | Ruins | 0, -60, 300 | overgrown courtyard: a broken colonnade with lintels around a raised dais, fallen columns, crumbling wall corners | none |
  | Toxic Mine | 0, -60, 400 | cave: rock outcrops, stalagmites, an overhang with stalactites, a mine-cart loop under timber frames, toxic barrels, slime sludge puddles (they slow you) | cave spiders (wave 2+), silverfish (wave 4+) |
  | Neon City | 0, -60, 500 | crossroads with crosswalks, kerbs and street lamps; a tower with a glowing sign, a noodle bar, a car park, an arcade with a rooftop billboard | pillagers (wave 3+), vindicators (wave 5+) |
  | Hellfort | 0, -60, 600 | you start inside a walled keep with four arched gates and corner towers; outside are fenced lava pools, basalt columns, a giant ribcage and a ruined portal | wither skeletons (wave 3+), blazes (wave 4+) |

  Behind each window is a smoke vent: a campfire (soul campfire in Hellfort) outside the bars, with solid wall behind it,
  so you can't see out to the other maps. During a run, smoke puffs also drift across the bars.

  The layouts are in `outbreak_maps.py`. Building checks that every mob window can still walk to the Arsenal and the
  spawns are clear, and fails if not.
  Team members are on team `pve`, so there's no friendly fire, and they see their points on the team sidebar.
- **Waves**: there are 6 + 4·(wave−1) mobs, plus 3 + 2·(wave−1) for each extra player, capped at 150. At most 30 are alive at once.
  - New types unlock as you go: husks at wave 2, skeletons at 3, spiders at 4, vindicators at 6, wither skeletons at 7, creepers at 8.
  - Mobs get +15% health and +8% damage per wave.
  - Every 5th wave adds an **Abomination** boss (a giant zombie, 150 base health, with a boss bar).
  - The last 4 mobs, and every mob in a wave that runs over 3 minutes, glow.
- **Break**: 20 s between waves. Downed players come back at the start of the break, so they can re-buy at the Arsenal.
- **Power-ups**: 4% of kills drop a glowing power-up in front of the killer. It lasts 30 s and any survivor can pick it up.
  - **Max Ammo**: 64 arrows each.
  - **Insta-Kill**: 30 s of Strength XX.
  - **Double Points**: 30 s of double kill points.
  - **Nuke**: kills every mob except the boss, +400 points each.
- **Dropped items**: items players throw stay on the ground (normal 5-minute despawn); other loose items in the arenas are cleared.
- **Points**:
  - start with 500;
  - 100 per kill;
  - a 100 × wave bonus for everyone still standing when a wave is cleared.
- **Arsenal**: Golden Apple 500, Med Kit 750, Ammo 250, Strength 1,000, Juggernog (+3 hearts) 2,500,
  Speed Cola 2,000, Mystery Box 950 (one of four wonder weapons), Ray Bow 5,000, Rations (16 steak) 100.
  Juggernog and Speed Cola are one per life, and you aren't charged if you already have one.
- **Food**: Rations in the Arsenal, plus 4 steak for every survivor whenever a wave is cleared.
- **Cleanup**: the map is force-loaded for the length of a run, so when the last player leaves or goes down every mob is
  killed. Any `pve.mob` found while no wave is running (for example, one saved in a chunk that loads later) is
  removed too.
- **Down**: if you die you spectate above the arena and come back with your kit when the wave is cleared. The run ends when
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
forceload add -24 276 24 324              # and -24 376 24 424, -24 476 24 524, -24 576 24 624 for the other maps
function pvp:admin/build                  # build_lobby (+ place_npc), build_arena, build_pve (all four maps)
forceload remove -32 64 32 136
forceload remove -24 276 24 324
```
`pvp:admin/build_pve_<ruins|mine|neon|hellfort>` rebuilds one Outbreak map. `pvp:admin/place_npc` re-places just the lobby NPCs and signs. The lobby chunks stay force-loaded.

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

**Militech Cyberskeleton** (test-only, Cyberware chest): David's full-body frame from the last episode of Edgerunners.
- Skeleton slot, capacity 14, so expect cyberpsychosis.
- +10 hearts, +8 armor, +4 toughness, +6 attack damage, +1.5 knockback, 80% knockback resistance.
- Much higher jumps, +15% speed, a slightly bigger frame and less fall damage.
- **Ground slam**: landing from 3+ blocks deals 8 damage within 4.5 blocks and knocks targets up (5 s cooldown; spares
  your Outbreak team).
- **Dual-wield**:
  - A sword, axe, mace or trident in the offhand adds its damage (Sharpness included) to every main-hand hit. Its other
    enchants don't apply.
  - With a bow or crossbow in each hand, the offhand one fires a second arrow 0.5 s after your shot, with the same
    damage. The delay gets it past the target's hit cooldown. That arrow can't be picked up.
- **Look**: every armor piece the wearer has on gets the **Rib** trim in **Redstone** (red ribs), checked every second,
  so armor put on later gets it too.
  - Pieces that already have a trim are left alone.
  - Taking the implant out removes only the trim it added (marked `custom_data.cy_trim`).
  - Electric sparks come off the back.
- **Show extras** (episode 10):
  - **Sandevistan + Cyberskeleton**: with both installed, the Sandy lasts 9 s instead of 6, recharges in 30 s instead
    of 60, and leaves a longer after-image trail.
  - **Psychosis meter** (0–100%), shown with heat on the action bar. It replaces the random over-capacity episodes.
    - Gains: slam +8, Sandy +15, each kill +5, leap +4, throw +3, last stand +30. It falls 1 every 2 s.
    - 40%+: nausea flashes. 70%+: heartbeat, darkness flashes and short body-flicker bursts.
    - 100%: **cyberpsycho**. The server is told, you flicker in and out of view, and you get Strength III and
      Glowing, but lose 1 health per second
      until you take Neuroblocker pills or die.
  - **Neuroblocker Pills** (PvP only; quick swallow, Anarchy keeps the drink): besides the normal 20-minute
    immunity, they halve a Cyberskeleton's meter and end a full episode.
  - **Last stand**, once per life: dropping to 3 hearts or less gives Resistance III and Strength II for 8 s. Then
    the frame gives out and you're left on half a heart.
  - **Grab and throw**: a sneaking hit flings the target up and away. Mobs are thrown along your look direction;
    players get a burst of Levitation. 2 s cooldown.
  - **Charged leap**: hold sneak on the ground for 1 s ("LEAP CHARGED"), then jump. A wind blast behind your feet
    throws you forward, and landing from it is a ground slam. It takes priority over the Projectile Launcher's
    sneak + jump when charged.
  - **Heat** (0–100%): slam +15, Sandy +25, leap +10, throw +5. It cools 4% a second, and steam vents off your back
    from 50%. At 100% the frame overheats: Slowness II, and slam/leap/throw are offline for 4 s.
  - **Sounds**: piston servos on jumps and landings, heavy iron-golem footsteps while sprinting.
- It's only built into PvP's `crispy_cyberware` (`build.py --pvp`). It isn't sold at Anarchy's Ripperdoc and isn't in
  any kit. Implant id 17 isn't in the kit mod's list, so `/pvpkit create` leaves it out of saved kits.

**David test kit** (admin-only, never in a menu): `/function pvp:admin/test_david` in the lobby queues you for
Outbreak with it, on the map you last picked in the Outbreak menu.
- It tags you `pvp.tester`. `/trigger pve.join set 60` only works for testers.
- Gear:
  - a Sharpness V netherite sword, plus a netherite axe in the offhand (dual-wield);
  - two Quick Charge III crossbows (put one in each hand to dual-fire) and a Power V Infinity bow, with arrows;
  - netherite armor (Prot IV, which gets the Rib trim);
  - 3 Neuroblocker Pills and food.
- Implants: Cyberskeleton, Sandevistan, Kiroshi and Reflex Tuner.
- You get it back each time you're revived.

**Velocity** (`pvp:velocity`, bows and crossbows, I-V, in the Ranged chest): arrows leave 20% faster per level, so they
drop less and hit harder. Levels above V from `/fe` work up to XX (5x speed).

**Any enchant, any item, any level** (ops, from the server mod):
```
/forceenchant <enchantment> [level]   e.g. /fe minecraft:sharpness 50, /fe crispy_enchants:<id> 10
/forceenchant <enchantment> 0         remove that enchant
/forceenchant clear                   remove every enchant from the held item
```
It works on the held item, and on a book it sets the book's stored enchants. It ignores which items an enchant
normally goes on, its max level (up to 255) and conflicts. It sets the exact level, so it can also lower one. With no
level it uses the enchant's normal max. An enchant only takes effect in its own slots (a sword enchant works while
held, an armor enchant while worn). Vanilla clients have names only up to X, so higher levels show as
`enchantment.level.N` in the tooltip.

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
- Up to 9 custom kits show (bottom row of the kit menus).
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

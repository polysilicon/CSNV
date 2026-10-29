# Crispy PvP

**Shown to players as "Multiverse"** (36 characters from your favourite shows and games · PvP · Duels · Outbreak; Haunted Night for Halloween 2026):
the hub selector (DeluxeHub `menus/serverselector.yml` on the lobby), the welcome menu and stats (CrispyLobby
`config.yml`), the tab list (`proxy/tab-config.yml`) and the spawn hologram here. Its Velocity server name is `multiverse`
(was `pvp` until CrispyLobby 1.12.1). Internally it's still `pvp`: the `CrispyPvP01` instance, this folder, the `pvp:`
datapack namespace and its vote-server key in the lobby (`proxy: multiverse`).

Kit/arena PvP server (AMP instance `CrispyPvP01`, Fabric 26.2, Velocity name `multiverse`). It replaces Bending, whose
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

## Arena
The PvP arena is a round Roman colosseum (`arena_map.py`, drawn with the Outbreak map engine and built by
`admin/build_arena`; force-load about ±54 blocks around 0 100 first):
- a round fighting floor 81 blocks across (radius 40): a red-sandstone mosaic in the middle, eight spoke paths and a ring
  path, sand-swept stone, and a raked-sand track along the wall;
- a round wall with pilasters, torches and red banners, a barred gladiator gate (with a tunnel) at each compass
  point, invisible barrier above the wall and a barrier lid at 31 above the floor;
- cover: a columned emperor's pavilion (9x9) with a brazier, four gladiator barracks (9x9: arched doors, barred
  windows, weathered tops, awnings, supplies, practice targets), spina walls on the axes, fallen columns and crates,
  eight obelisks, four date palms, lamp posts and four lion cages;
- eight spawns at radius 32 (`arena_map.SPAWNS`);
- **stands**: nine rows of stepped seating all the way round, aisles every 30 degrees, a parapet with braziers and
  flag poles on the rim, and the emperor's box (dais, quartz columns, canopy, throne) above the north gate.

**Lobby** (`admin/build_lobby`): a deepslate-tile plaza with an amethyst ring, a purpur cross and a crying-obsidian
centre over a beacon (beam through purple glass at spawn), froglight corners, chiseled podiums under the NPCs, a purple
glass rim with deepslate-brick pillars and end rods, and a **Hall of Heroes** on the west side: seven character heads
on pedestals with names (`item_display`/`text_display` tagged `pvp.lobbydeco`, replaced on every rebuild).

**Spectating**: the deepslate and amethyst gate on the east side of the lobby (`admin/build_portal`) takes you to the stands
(`function spectate`, tag `pvp.spec`) at one of three spots. Spectators can walk the stands but can't be hurt or hurt
anyone (Resistance V + Weakness), and barrier keeps them out of the fight. `/spawn`, or leaving the stands, takes
them back to the lobby.

`arena_map.check()` makes sure every spawn is clear and can walk to the centre, and the spectator spots are on the stands.

### Map rotation
The arena rotates through eleven maps, ten minutes each (`ROT_SECS`), in this order: the Colosseum, then the
themed maps in `arena_maps.py`, each built once at its own spot (x -700, z -400..400 in steps of 100):

| # | Map | From | What's there |
|---|-----|------|--------------|
| 2 | Mustafar | Star Wars | two lava rivers with railed bridges, a mining facility (ladder to the roof, a catwalk over the lava to a lookout), collector towers holding lava out over the rivers, the high ground, obsidian shards, basalt spires, pipes, a landing pad |
| 3 | Shrek's Swamp | Shrek | mud and lily-pad pools with boardwalks, a pond with a fishing dock, Shrek's tree-stump house (mossy roof, chimney, table and stools), the outhouse, "Beware Ogre" signs and Farquaad's wanted poster, vine trees, mossy mounds, firefly bushes, a camp fire |
| 4 | Tegridy Farms | South Park | the farmhouse (upstairs, porch, Randy's grill), a red barn with a hay loft, a silo, fenced fields of "crops", the Tegridy Weed stand, a windmill pump and trough, a chicken coop, a pasture hill, the grow tent, the TEGRIDY FARMS gate, Randy's tractor |
| 5 | Quahog | Family Guy | Spooner Street with raised sidewalks: the Griffin house (couch and TV, kitchen, upstairs), Quagmire's (and his car), Joe's (with ramp), the Drunken Clam (bar, stools, pool table, darts), a bus stop, mailboxes, parked cars, lamp posts |
| 6 | Bikini Bottom | SpongeBob | SpongeBob's pineapple, Squidward's head, Patrick's rock, the Krusty Krab (with seating), the Chum Bucket, Sandy's treedome, Mrs. Puff's Boating School, sand dunes, coral, jellyfish and bubbles |
| 7 | Mushroom Kingdom | Super Mario | Peach's castle behind a moat, warp pipes, floating brick and ? blocks, coins, giant mushrooms you climb by ladder, climbable hills, Bowser's bridge over lava, the end-of-level staircase and flagpole, a brick castle, clouds |
| 8 | Springfield | The Simpsons | the nuclear plant (two walk-in cooling towers, waste barrels), Kwik-E-Mart, Moe's Tavern, 742 Evergreen Terrace (couch and TV) with Bart's treehouse, the Lard Lad donut, the Duff blimp overhead |
| 9 | Albuquerque | Breaking Bad | the RV cook lab and camp, Walt's house (pizza on the roof) and pool with the pink bear, Los Pollos Hermanos, the A1A Car Wash, Saul's office, power poles, red rocks, mesas |
| 10 | Green Hill Zone | Sonic | a loop-de-loop, checkered plateaus, a checkered hill with a tunnel, a lake with a log bridge, palm trees, totem poles, sunflowers, springs (slime), gold rings, Eggman's capsule, the GOAL sign |
| 11 | Rainey Street | King of the Hill | the alley behind Hank's house: privacy fences, power lines, bins; Hank, Dale, Bill and Boomhauer at the fence with a beer (armor stands, no hitbox); eight houses with yards (Hank's striped lawn, grill and propane tank, Dale's bunker and van, Bill's car on blocks, Kahn's hedges), Hank's pickup out front |

Every themed map has the same frame: a 73x73 floor, a themed outer wall with barrier above it and a barrier lid,
and a rampart behind the wall whose top is the spectators' walkway. Signs (`text_display`) and figures (armor stands) are tagged
`pvp.mapdeco_<key>`. `arena_maps.check()` makes sure every spawn is clear and they can all reach each other.

- `#amap pvp` is the current map, `#anext pvp` the next and `#arot pvp` the seconds left. A purple boss bar shows
  the map and the time to the next one to everyone in an arena or the stands; there's a chat warning at 60 s and 10 s.
- When the time is up, everyone fighting is moved to a spawn on the new map ("NEW MAP" title), spectators go to the
  new map's walkway, and the server is told the new map. Joining the arena or the stands always uses the current map.
- `function pvp:admin/next_map` skips to the next map.
- Buildings get windows away from their doorways, a ceiling with hanging lanterns, and furniture (`arena_maps.furnish`:
  things against the walls, a bed, a rug with a table and chairs); every map has themed lamp posts (`arena_maps.lamps`).
- Fire from fire abilities is cleared within 12 blocks of every player each second, so it can't burn the wooden maps.

## How it plays
- Players spawn in a safe stone hub at 0 101 0, where they're immune to damage and can't deal any.
- **PvP Arena** (left NPC, was the Kit Dealer) opens a chest menu of 36 character kits. Click one and you're dropped at one of 8 random arena
  spawns with 3 s of spawn protection.
- **Outbreak** (right NPC) opens the map menu: pick one of the four maps (or Random),
  then pick a kit to queue.
- PvP kills:
  - heal the killer and give 10 s of Absorption and a golden apple;
  - streaks are announced at 3, 5, 10 and so on;
  - the sidebar shows total kills.
- Death, logout, `/spawn`, `/lobby` or `/trigger pvp.spawn` sends you back to the lobby, clearing your inventory and
  implants. `/spawn` and `/lobby` are blocked for 10 s after you take damage.
- The PvP arena is a 61×61 sandstone colosseum (centre 0, -60, 100).
- **Leaderboards**: one big board on the south side of the lobby (`pvp.lb.all`, mod 1.4.4) shows the top 3 for Kills
  (`pvp.kills`), Best Kill Streak (`pvp.best`), Duel Rating (`pvp.elo`), Best Outbreak Wave (`pve.best`) and Best Tower
  Floor (`tw.best`). The mod rewrites it every 5 s. `pvp:admin/place_leaderboard` re-places it.

### Kits
Every kit is a character. The menu shows all 36 in four full rows of 9, with the top and bottom rows left empty, roughly grouped by franchise. The
classic kits with no character (Juggernaut, Berserker, Medic, Pyro, Ranger, Shinobi, Skyhammer) were removed.

**Franchise kits** have two **ability items** each (`abilities.py`):
- They're in the hotbar (clay balls with their own look, so they never clash with cyberware). Right-click to use one;
  it comes back to the same slot right after.
- The item shows its cooldown sweep, like an ender pearl.
- Abilities hit mobs and enemy players, never Outbreak teammates.

| Kit | Gear | Abilities |
|---|---|---|
| Jedi Knight | Lightsaber (diamond, Sharpness III), robes, Jump Boost II | **Force Push** (cone knockback, 7 s), **Mind Trick** (blind + slow, 15 s) |
| Sith Lord | Red lightsaber (diamond, Sharpness III, Fire Aspect) | **Force Lightning** (cone, 6 dmg + slow, 9 s), **Force Choke** (lift + Wither, 14 s) |
| Hero of Hyrule | Master Sword (Sharpness III), Hylian Shield, bow, Prot III | **Spin Attack** (7 dmg around you, 6 s), **Hookshot** (reel a target in, 8 s) |
| Spartan | MA5 Assault Rifle (gun ability), energy sword, trimmed netherite chest with iron legs and boots (Prot I) | **Frag Grenade** (10 dmg where it lands, 10 s); passive **energy shield**: 4 absorption hearts that come back after 5 s without being hit (hits the shield soaks up count too) |
| Doom Slayer | Super Shotgun (gun ability), Crucible (diamond, Sharpness II), netherite chest with iron legs and boots (Prot I) | **Chainsaw** (10 dmg up close, 14 s), **Berserk Rune** (Strength I/Speed II/Resistance, 25 s); passive **glory kills** (every kill heals) |
| Witcher | Steel sword (Sharpness III), silver sword (Smite V), 2 Swallow potions, chainmail Prot II | **Igni** (3 fireballs, 8 s), **Quen** (shield, 16 s) |
| Mario | Hammer (mace), overalls, Resistance I | **Fireball** (3 s), **Super Jump Punch** (leap + 6 dmg uppercut, 8 s) |
| Pikachu | Iron Tail sword, Speed I, Resistance I | **Thunder Jolt** (zap 6 dmg, 4 s), **Quick Attack** (dash, 6 s) |
| Kirby | Star sword, Jump Boost II, Resistance I | **Inhale** (suck in + 5 dmg + 2 hearts, 10 s), **Stone** (immune 3 s + slam, 12 s) |
| Samus | Arm Cannon (gun ability: Power Beam), Varia Suit (gold) | **Charge Shot** (explosive, 6 s), **Screw Attack** (spin up + 6 dmg, 8 s) |

**Guns** are abilities, not bows or crossbows: right-click fires a hitscan shot (with a tracer) at the first enemy
along your aim, so there are no arrows to carry. Shotguns hit everything in a short cone in front of you instead.

| Gun | Kit | Range | Damage | Cooldown | Extra |
|---|---|---|---|---|---|
| MA5 Assault Rifle | Spartan | 32 | 3 | 0.4 s | |
| Super Shotgun | Doom Slayer | 7 (cone) | 7 | 1.2 s | knockback |
| Lucky | Courier Six | 40 | 7 | 1 s | |
| Militech Heavy Cannon | Adam Smasher | 32 | 6 | 1 s | Slowness I 1 s |
| Guts | Rebecca | 6 (cone) | 12 | 0.8 s | knockback |
| Pistol | Rebecca | 28 | 4 | 0.35 s | |
| Trunk M60 | Walter White | 32 | 4 | 0.25 s | |
| Arm Cannon (Power Beam) | Samus | 36 | 5 | 0.5 s | |
| Militech Handgun | David Martinez | 30 | 6 | 0.6 s | |
| Amban Rifle | Mandalorian | 60 | 12 | 2.5 s | glowing 3 s |
| Laser Pistol | Leela | 28 | 4 | 0.6 s | glowing 1 s |

Bows stay bows: Link's Hero Bow, Red's Slingshot and the Sniper's Sniper Rifle.

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
  | Spartan | Eagle Eye III |
  | Doom Slayer | Bleed IV, Rage III |
  | Witcher | Cleave III, Bleed III, Dodge II |
  | Mario | Pummel II, Springs III |
  | Pikachu | Paralyze III |
  | Kirby | Devour III, Antigravity II |
  | Samus | Explosive II, Eagle Eye III, Reinforced III |

- Sizes (`scale` modifier `pvp:size`, all removed on `to_lobby`, going down and Outbreak entry). Size changes stats
  too (`size_stats()` in `build.py`, modifiers `pvp:size_dmg/_hp/_kb/_spd`): big characters hit harder, have more
  health and knockback resistance but are slower; small ones are faster but hit softer with less health.

  | Kit | Size | Damage | Health | Knockback res. | Speed |
  |---|---|---|---|---|---|
  | Pikachu, Kirby | 0.6× | −20 % | −2 hearts | | +12 % |
  | Red | 0.7× | −15 % | −1.5 hearts | | +9 % |
  | Rebecca | 0.75× | −12 % | −1 heart | | +7.5 % |
  | Sonic, SpongeBob | 0.8× | −10 % | −1 heart | | +6 % |
  | Mario | 0.85× | −8 % | −1 heart | | +4.5 % |
  | Mr. Krabs | 0.9× | −5 % | −½ heart | | +3 % |
  | Samus | 1.08× | +4 % | +1 heart | +8 % | −2.4 % |
  | Spartan, Peter Griffin, Homer, Tony Soprano | 1.1× | +5 % | +1 heart | +10 % | −3 % |
  | Donkey Kong | 1.25× | +12 % | +2.5 hearts | +25 % | −7.5 % |
  | Shrek, Adam Smasher | 1.3× | +15 % | +3 hearts | +30 % | −9 % |

**Other kits**:

| Kit | Gear | Abilities |
|---|---|---|
| Randy Marsh (South Park) | No weapon: fists +7 damage at sword attack speed; light blue shirt, jeans and brown shoes (leather, Prot IV); **Sandevistan** cyberware (double-tap sneak) | **Tegridy** (Regeneration II + Speed I 6 s, 20 s), **Wassup Bruh** (Strength II 8 s, 22 s) |
| Courier Six (Fallout: New Vegas) | Lucky (revolver, gun ability), Machete (Bleed II), Ranger armor (Prot II) + Desert Ranger head | **V.A.T.S.** (enemies within 12 blocks: Slowness III + glowing 5 s; you: Strength I, 18 s), **Stimpak** (Instant Health II + Regeneration II, 15 s) |
| Sonic | Chaos Emerald (iron sword, Sharpness V), blue leather with red shoes (Springs II, Gears II), Speed II, 0.8× | **Spin Dash** (dash + Speed III 2 s, 5 dmg up close, 6 s), **Homing Attack** (12 blocks: zip to the target, 7 dmg, bounce off, 8 s) |
| Walter White (Breaking Bad) | Trunk M60 (machine gun ability), 3 splash Poison II, yellow hazmat suit (Explosive Immunity III), Heisenberg head | **Say My Name** (10 blocks: Weakness II + Slowness I + glowing 6 s; you: Resistance I, 22 s), **Fulminated Mercury** (explosive throw, 10 s) |
| Herobrine (Minecraft) | Diamond sword (Sharpness V, Fire Aspect), Steve-coloured leather, Night Vision | **Smite** (24 blocks: 7 lightning dmg + Blindness 2 s, 10 s), **Haunt** (teleport behind the nearest enemy within 16 blocks, blinds them, you go invisible 2 s, 12 s) |
| Donkey Kong | No weapon: fists +9 damage at axe speed; brown leather (Prot IV) with a red tie, Tank II, 1.25× | **Giant Punch** (4 blocks: 12 dmg, launches, 9 s), **Ground Pound** (5 blocks: 6 dmg, Slowness III 2 s, pops them up, 10 s) |
| Mandalorian | Amban Rifle (gun ability), Darksaber (Sharpness III), Beskar (iron Prot III, quartz trim), Din Djarin head | **Jetpack** (launch + Slow Falling 6 s, 9 s), **Flamethrower** (4 blocks: 5 fire dmg + 3 fireballs, 9 s) |
| Red (Angry Birds) | Slingshot (bow: Power IV, Punch II, Infinity), beak: fists +8 at sword speed, red leather with a cream belly, Jump Boost I, 0.7× | **Fling** (slingshots you forward; crashing into an enemy or landing deals 9 dmg + knockback within 3 blocks, 8 s), **Battle Cry** (6 blocks: 4 dmg + knockback + Slowness I; you: Strength I + Speed I 6 s, 18 s) |
| Spider-Man | No weapon: fists +7 at sword speed; red and blue suit (Dodge III, Springs II), Jump Boost II | **Web Shot** (20 blocks: 3 dmg, stuck in place 2 s, 9 s), **Web Swing** (swing forward + Slow Falling 3 s + Speed II, 7 s) |
| Shrek | No weapon: fists +8 at axe speed; vest (Tank II), Health Boost I, 1.3× | **Swamp Roar** (6 blocks: 4 dmg, knockback, Nausea 4 s, Slowness I 3 s, 14 s), **Onion Layers** (8 absorption hearts 12 s + Resistance I 6 s, 20 s) |
| Peter Griffin (Family Guy) | No weapon: fists +6 at sword speed; 2 Strength potions ("Pawtucket Patriot"), Health Boost I, 1.1× | **Chicken Fight** (Strength II + Resistance I + Speed I 10 s, 30 s), **Surfin' Bird** (8 blocks: Nausea 6 s, Slowness II + Weakness I 4 s, 20 s) |
| Homer Simpson | Plutonium Rod (iron sword: Sharpness IV, Poison II), Health Boost I, 1.1× | **Donut** (Instant Health I, Regeneration II 4 s, full hunger, 14 s), **Belly Bump** (6 blocks in front: 5 dmg + big knockback, 8 s) |
| Darth Maul (Star Wars) | Double-Bladed Lightsaber (diamond: Sharpness III, Sweeping Edge III, Double Strike II), black robes (Dodge II, Springs I), Speed I | **Saber Throw** (16 blocks: 6 dmg + Slowness I 2 s, 10 s), **Saber Spin** (3.5 blocks: 5 dmg + knockback, 9 s) |
| Mr. Krabs (SpongeBob) | No weapon: claws +6 at sword speed; red shell, blue shirt (Armored II), 0.9× | **Claw Pinch** (4 blocks: 8 dmg + Slowness II 2 s, 7 s), **Money Grab** (6 blocks: pulls enemies 2 blocks in, Weakness I 4 s; you: Strength I 5 s, 14 s) |
| Saul Goodman (Better Call Saul) | Gavel (mace: Density III, Breach I), loud yellow suit (Prot IV, Dodge II, Springs II shoes), Speed I | **You've Been Served** (16 blocks: 6 dmg, Weakness II + glowing 5 s, you heal 4; 16 s), **Loophole** (untouchable 1.5 s, clears Slowness/Weakness/Poison/Wither/Blindness/Nausea, Speed II 3 s, 20 s), **Fingertip Lightning** ("lightning bolts shoot from my fingertips": 16 blocks, 6 lightning dmg, arcs for 3 dmg to enemies within 3 blocks of the target, 10 s) |
| Sniper (Team Fortress 2, was the classic Sniper) | Sniper Rifle (bow: Power III, Infinity, Lethal Sniper II), Kukri (Sharpness III, Bleed I), red shirt and brown vest, RED Sniper head, Night Vision | **Jarate** (thrown splash: Weakness II + glowing 8 s, Slowness I 3 s, 16 s), **Focus** (every enemy within 40 blocks glows 6 s, 20 s) |
| Hank Hill (King of the Hill) | Grill Spatula (swings like an iron sword: Sharpness IV, Fire Aspect), white tee and jeans (Explosive Immunity III), Fire Resistance | **Propane Tank** (explosive throw, 10 s), **I'm Gonna Kick Your Ass** (Strength II + Speed I 6 s, knocks back enemies within 3 blocks, 22 s) |
| Leela (Futurama) | No weapon: martial arts, fists +7 at sword speed; white top, black pants (Dodge II, Springs I), Speed I | **Martial Arts Kick** (dash, 7 dmg + knockback up close, 7 s), **Laser Pistol** (gun: hitscan, 28 blocks, 4 dmg every 0.6 s, glowing 1 s; Pack-a-Punch works on it) |
| Elliot (Mr. Robot) | Pocketknife (Sharpness III, Poison I), black hoodie (Dodge II), Night Vision; Elliot head (MineSkin upload) | **Blackout** (12 blocks: Darkness 6 s, Blindness 2 s, Slowness I 3 s, 22 s), **Mr. Robot** (Strength II + Resistance I + Speed I 6 s, 25 s) |
| Tony Soprano (The Sopranos) | Baseball Bat (Sharpness IV, Knockback I), white bathrobe, 1.1×; Tony head (MineSkin upload) | **Gabagool** (Instant Health I, Regeneration II 4 s, full hunger, 15 s), **Whack** (16 blocks: 6 dmg, Wither I + Slowness II + glowing 4 s, 14 s) |
| SpongeBob | Golden Spatula (swings like an iron sword: Sharpness IV, Knockback II), white shirt and brown shorts (Dodge II, Springs II), Jump Boost I, 0.8× | **Krabby Patty** (Instant Health I, Regeneration II 5 s, full hunger, 15 s), **Bubble Blower** (3 wind-charge bubbles that pop with knockback, 8 s) |
| Bender (Futurama) | Bent Girder (iron axe: Sharpness IV, Cleave II), metal body (iron Prot III, Armored II), Fire Resistance | **Bite My Shiny Metal Ass** (8 blocks: Weakness I + glowing 6 s; you: Resistance I 6 s, 18 s), **Olde Fortran** (Strength I + Speed I + Regeneration I 8 s, 20 s) |

Randy's head came from a skin uploaded to MineSkin (no Randy in the head database). The same works for any character:
upload the skin at mineskin.org and put its texture value in `heads.json`.

**Cyberpunk kits** (David Martinez, Lucy, Adam Smasher, Rebecca) keep their cyberware:

| Kit | Gear | Cyberware |
|---|---|---|
| David Martinez (was Edgerunner) | Cyber-arms: fists +6 at sword speed; yellow EMT jacket and black pants (Dodge II), David head; abilities **Militech Handgun** (gun: 30 blocks, 6 dmg, 0.6 s) and **Overclock** (Strength II + Speed II 6 s, costs some health: 4 magic damage before armor, 20 s) | Sandevistan, Kiroshi, Reflex Tuner, Reinforced Tendons |
| Lucy (was Netrunner) | Monowire (diamond sword: Sharpness IV, Assassin III, Poison II), white bodysuit (Dodge II), Lucyna head; abilities **Short Circuit** (quickhack: 20 blocks, 5 dmg, Slowness II 2 s, glowing 3 s, 8 s) and **Optical Camo** (Invisibility + Speed I 6 s, 25 s) | Lynx Paws, Reflex Tuner, Kiroshi |
| Adam Smasher | Militech Heavy Cannon (gun ability), **Borg Slam** (leap, then a landing slam: 10 dmg within 5 blocks, knockback, Slowness II 2 s; 14 s), Arasaka Breaker (axe: Sharpness I, Cleave III), netherite (iron boots) Prot I with a redstone rib trim (chest: Explosive Immunity III), Adam Smasher head (MineSkin upload), 1.3× size | Projectile Launch System (sneak + jump), Sandevistan (double-tap sneak) |
| Rebecca | Guts (shotgun ability) and Pistol (gun ability), black leather with pink boots (Dodge II), 0.75× | Gorilla Arms, Reinforced Tendons, Reflex Tuner, Kiroshi |

All kit gear is unbreakable, and every kit also gets 16 steak and 2 golden apples.

## Kit mastery
Every character has its own mastery XP (`pvp.mx<kit id>`): +10 per PvP kill and +1 per Outbreak kill while playing it
(`pvp.cur` is the character you last picked).
- Levels I / II / III / IV / V at 50 / 150 / 400 / 800 / 1,500 XP. V is **Master**.
- Level-ups show a title and a chat line; reaching Master is announced to everyone and counts in `pvp.mastered`.
- Picking a kit shows your stars and progress for that character, with a link to `/trigger pvp.mastery`, which lists
  every character you've played.
- Masters get a sparkle aura while playing that character and a gold star in kill streak announcements.

## The Tower (`tower.py`)
A roguelite climb, solo or up to 4 players. The **🗼 The Tower** NPC sits between the PvP Arena and Outbreak NPCs:
clicking it opens the Tower menu. Climbs are organised like the UNO tables in the lobby:
- **Create a lobby**: the first player opens a lobby and leads it (tag `tw.lead`); the lobby gets a clickable
  *[Click to join]* invite.
- Others **join** from the Tower NPC (or the invite), up to 4 (tag `tw.q`). The menu shows the leader and who's in.
- The **leader starts** the climb (**▶ Start** in the menu or the chat button), solo or with whoever joined.
- **Leave the lobby** at any time. If the leader leaves, walks out of the lobby or logs off, the next player leads;
  the lobby closes when it's empty, or after 5 minutes without starting (`LOBBY_IDLE`, a 1-minute warning first).
- `tower/open_menu` picks the menu: `tower` (create), `tower_join`, `tower_member`, `tower_lead`, or `tower_busy`
  during a climb (floor and who's climbing). Buttons use `/trigger tw.join set 1` (create/join), `2` (leave), `3` (start).

Everyone starts as a **random character**.
- One room (x 388..412, z -12..12 at y -61, kept force-loaded: `admin/build_tower` builds it), rebuilt every floor:
  - **mob floors**: cover pillars and low walls (6 layouts), 3 + floor/2 mobs (+2 per extra player, max 16) from a pool
    that changes every 5 floors (zombies/skeletons/spiders, then husks/strays, vindicators/wither skeletons,
    blazes/piglin brutes; no spiders, they climb to the ceiling out of melee reach), +12% health and +5% damage per floor;
  - **challenge floors** every 3rd floor (3, 6, 9...; a boss wins on 15, 30...), one of four picked at random and
    never the same twice in a row (`tower/pick_challenge`):
    - **Parkour**: a snake of platforms over magma (2x2, or 1x1 in the harder half of 10 layouts);
    - **Glass Bridge**: 6 rows of two glass panes over magma; one pane in every row is fake (rolled each time, `#g0..5`)
      and shatters when you step on it;
    - **Maze**: one of 10 hedge mazes (azalea leaves, barrier roof so nobody jumps over), gold block in the cell furthest
      from the start, 60 s + 1 per floor (max 2 min);
    - **Crafting**: craft a random item (Iron Pickaxe, Compass, Clock, Lantern, Fishing Rod, Jukebox) from materials
      split over 12 barrels (a random barrel per stack, plus junk), 90 s + 1 per floor, a mob every 15 s; the materials
      are taken back afterwards.
    Magma and the gold block work as before; falling, a wrong pane and running out of time are all **strikes**
    (`tw.falls`), and the 3rd strike on a floor kills you;
  - **boss** every 5th floor: The Brute, Bone King, The Warlord, The Beast in turn, with a boss bar
    (health 80 + 40 per boss beaten + 30 per extra player) and two adds.
- After each floor everyone picks **1 of 3 random upgrades** (clickable chat lines, `/trigger tw.pick`, 20 s or one is
  picked for you). They stack for the whole climb (attribute modifiers `pvp:tw_u<n>_<i>`, re-applied from the counts in
  `tw.u<n>`). Like Crab Champions, each has a **rarity**: an offer rolls Common 60% / Rare 28% / Epic 10% /
  Legendary 2% first (Lucky shifts it), then an upgrade of that rarity (`tower/roll_one`).
  | Rarity | Upgrades |
  |---|---|
  | Common | Vitality, Sharpened, Swift, Plated, Frenzy, Spring Step, Juggernaut, Second Wind, Firestarter, Toxic, Thorns |
  | Rare | Vampire, Crit Chance, Frostbite, Shield, Bloodlust, Lucky |
  | Epic | Extra Life, Glass Cannon, Lightning, Explosive |
  | Legendary | Attack Drone, Black Hole |
  On-hit upgrades (Crit Chance, Firestarter, Frostbite, Toxic, Lightning, Explosive) work with any damage you deal:
  melee, guns, abilities and the drone (advancement `towerhit` on `player_hurt_entity`; the mobs hurt that tick have
  `HurtTime` 10). Thorns uses `entity_hurt_player`. Toxic is Wither, since most Tower mobs are undead.
- Dying ends your climb unless you have an Extra Life; the climb is over when nobody is left. Best floor per player in
  `tw.best`, the server record in `#trecord tw`; +5 mastery XP per floor for the character you're playing.
- Tower players are on team `tower` (no friendly fire; abilities skip them like Outbreak teammates).
- Anyone climbing who ends up outside the room (through the ceiling or a wall) is put back at the floor's start
  (`tower/escaped`).
- **Parkour risk**: the 3rd fall into the magma on a floor (`MAX_FALLS`, counted in `tw.falls`) kills you, so it ends
  your climb unless an Extra Life saves you.
- **Your build**: the sidebar (objective `tw.side`, shown to team `tower`) has the floor, and in a solo climb your Extra
  Lives, falls left and every upgrade with its level and total bonus ("Sharpened II  +30% damage"). A sidebar is shared
  by the whole team, so in co-op it shows the floor and climbers only. Everyone also gets a **Climb Log** (book):
  right-click it for your character, upgrades and stats in chat; the same summary shows after every pick.
- **Leaderboard**: "🗼 Best Tower Floor" (`tw.best`) is a row on the lobby leaderboard.

## Duels
- In the lobby everyone gets a **⚔ Duel Challenge** item (hotbar slot 9). Look at a player within 8 blocks and
  right-click to challenge them. They get clickable **[Accept] / [Decline]** (`/trigger pvp.duela` / `pvp.dueld`), and
  the challenge expires after 30 s.
- Accepting takes both players to a free duel pit (three small round pits at x -300, z 0 / 60 / 120;
  `admin/build_duels`). Each fights as a random character (rolled separately for each player, so
  it's down to skill, not a favourite pick), with 3 s of grace. Everyone is told who fights as what
  ("⚔ lbxd fights as Darth Maul"), and each dueler's title shows their character.
- The first to die loses. Ratings are ELO (`pvp.elo`, start 1000, K 32), with wins and losses in `pvp.dwin` /
  `pvp.dloss`, and the result is announced.
- Leaving mid-duel (`/spawn`, disconnecting) is a forfeit. If your opponent logs out, you win by walkover with no
  rating change.
- `/trigger pvp.duelstats` shows your rating and record.
- The lobby has a **⚔ Duel Rating** row (`pvp.elo`) on the lobby leaderboard, and the network
  lobby's earned tags include **[Champion]** (#1 duel rating) and **[Kit Master]** (mastered a character).

## Outbreak (PvE waves)
- **Progression** (Arsenal):
  - **Pack-a-Punch** upgrades the weapon in your hand, tier I / II / III / IV for 2,000 / 4,000 / 7,500 / 12,000 points. Each tier adds
    Sharpness +2 (swords and axes), Power +2 (bows), Piercing and Quick Charge +1 (crossbows), Impaling +2 (tridents) or
    Density and Breach +1 (maces). Tier III also adds Fire Aspect II, Flame + Punch, Multishot, Channeling or Wind Burst; tier IV adds Lifesteal II
    (swords), another Sharpness +2 (axes), Explosive I (bows, crossbows), Impaling +2 or Density +2.
    The tier is stored on the item as `custom_model_data` strings (`pvp_tier1`..`4`) and shown as gold lore stars. It
    used to be `custom_data.pvp_tier`, but crispy_enchants' migration wipes small `custom_data` every 2 s, so the tier
    vanished and tier I could be bought again and again.
  - **Guns** (gun abilities) can be Pack-a-Punched too, for the same prices: hold any gun and it upgrades **all** your
    guns (score `pve.gun`, since a gun item is swapped for a fresh one after every shot). Tier I +40 % damage, II +80 %,
    III +120 % and hits slow the target, IV +180 % and also sets mobs on fire. Like the armor upgrade, it resets when you
    go down. Gun lore shows your tier and the damage it does: the gun loot tables run item modifier
    `pvp:gunlore/<gun>`, which adds the line for the holder's `pve.gun`, and buying a tier rewrites every gun you carry
    (`pve/up/gun_lore`).
  - **Wall-buys**: Outbreak-only guns (no character has them), 4 per map, right-click to buy (`WALL_BUYS`, per map in
    `WALL_MAPS`): M1911 500 (every map), Olympia 750, MP40 1,000, Kar98k 1,250, Stakeout 1,500, STG-44 1,750.
    | Gun | Type | Damage | Fire rate | Range |
    |---|---|---|---|---|
    | M1911 | pistol | 5 | 0.45 s | 28 |
    | Olympia | shotgun (cone) | 12 | 1.4 s | 6 |
    | MP40 | SMG | 3 | 0.2 s | 26 |
    | Kar98k | rifle | 16 | 1.6 s | 50 |
    | Stakeout | shotgun (cone) | 9 | 0.9 s | 7 |
    | STG-44 | assault rifle | 5 | 0.3 s | 34 |
    Ruins: M1911, Olympia, MP40, Kar98k · Toxic Mine: M1911, Stakeout, MP40, STG-44 · Neon City: M1911, Olympia,
    STG-44, Kar98k · Hellfort: M1911, Stakeout, Kar98k, MP40 · Orbital: M1911, Olympia, STG-44, Stakeout.
    Spots come from the layout (`outbreak_maps.wallbuy_spots`: a reachable floor cell next to a solid wall, one per
    quarter, away from mob windows and spawns). Each is a gun item display, a name and price text display and an
    interaction carrying the gun's number in `pve.wb`. You can only carry one of each; re-run `admin/build_pve` after changing them.
  - **Armor Upgrade**, for 1,500 / 3,000 / 6,000 points: I gives +1 Protection and Unbreaking on everything you wear,
    II gives Resistance I, and III gives +2 hearts.
  - Perks: **Double Tap** (Strength I, 3,000) and **PhD Flopper** (Fire Resistance + Jump Boost, 1,500), alongside
    Juggernog and Speed Cola.
  - Upgrades and perks last until you go down; you come back with your kit as it was.
  - **Sidebar** (players in the run only, `pve.side`): each survivor's points and kills this run, e.g.
    `lbxd  1250 pts · 34 kills`, sorted by points. It's rebuilt every second, so players who leave or log off drop off.
  - **Veteran bonus**: you start each run with 500 points + 25 per wave of your best run (`pve.best`), capped at +1,000.
- **Lobbies** (like the UNO tables in the lobby): the first player picks a map and a kit, which opens an Outbreak
  lobby they lead (`pve.lead`), with a clickable *[Click to join]* invite in the lobby. Others join from the Outbreak
  NPC (or the invite) and pick their kit (`pve.q`). The **leader starts** the run (**▶ Start** in the menu or the chat
  button); there's no countdown any more.
  - The NPC shows the menu that fits (`pve/open_menu`): the map menu (open a lobby), `pve_join`, `pve_member`
    (change kit, leave), `pve_lead` (start, change map, change kit, leave) or `pve_running` (drop in) during a run.
  - If the leader leaves, walks out of the lobby or logs off, the next player leads; the lobby closes when it's
    empty, or after 5 minutes without starting (`PVE_LOBBY_IDLE`, a 1-minute warning first).
  - `pve.join` values: a kit id joins with that kit, 81..85 / 91 pick a map, 92 opens the kit menu, 93 starts (leader),
    99 leaves.
  - During a run you can still **drop in**: pick a kit and you join at the next wave break.
- **Maps**: five arenas in the same 65 × 65 footprint (walls at ±33 from the centre), each with 12 barred mob
  windows in its outer wall, the player spawns and the **Arsenal** in the middle, but with their own layout. They were
  45 × 45 until the character kits' jumps and dashes needed more room: each map's original design fills the middle
  and an outer ring of themed cover (ruined pillars, rock outcrops, kiosks and parked cars, lava pools and basalt)
  surrounds it. Each player's pick is kept in `pve.map`.
  - The lobby leader decides the run's map (and can change it until the run starts; the current map's name is kept
    in `pvp:pve mapname` for the menus and messages). Players joining a lobby or a run play its map.
  - **Back to maps** (slot 45) in the kit menu goes back to the map menu.

  | Map | Centre | Layout | Extra mobs |
  |---|---|---|---|
  | Ruins | 0, -60, 300 | overgrown courtyard: a broken colonnade with lintels around a raised dais, fallen columns, crumbling wall corners | none |
  | Toxic Mine | 0, -60, 400 | cave: rock outcrops, stalagmites, an overhang with stalactites, a mine-cart loop under timber frames, toxic barrels, slime sludge puddles (they slow you) | cave spiders (wave 2+), silverfish (wave 4+) |
  | Neon City | 0, -60, 500 | crossroads with crosswalks, kerbs and street lamps; a tower with a glowing sign, a noodle bar, a car park, an arcade with a rooftop billboard | pillagers (wave 3+), vindicators (wave 5+) |
  | Hellfort | 0, -60, 600 | you start inside a walled keep with four arched gates and corner towers; outside are fenced lava pools, basalt columns, a giant ribcage and a ruined portal | wither skeletons (wave 3+), blazes (wave 4+) |
  | Orbital Station | 0, -60, 700 | **not a square**: a roofed, wheel-shaped space station (ceiling at 7, hull 6 high). A round hub (Arsenal, spawns, reactor columns, a ring of consoles, a tinted skylight), four 9-wide spoke corridors (lit strip, glowing side grates, wall pipes, warning stripes and arches at each end), and a 12-wide outer ring with four glass lab pods, cryo pods, server racks, hydroponic planters, benches, copper bulbs and a lit seam; viewports look out on a black starfield that is never reachable. Its 12 mob windows are in the outer hull (`outbreak_maps.ORBITAL_POINTS`, via `build.MAP_POINTS`); downed players float inside the hub (`DOWNED_Y`) | endermites (wave 2+), strays with bows (wave 4+) |

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
  Speed Cola 2,000, Mystery Box 950 (see below), Ray Bow 5,000, Rations (16 steak) 100.
  Juggernog and Speed Cola are one per life, and you aren't charged if you already have one.
- **Mystery Box** (950): 19 rolls with equal odds (about 5.3 % each), announced to the whole run.
  - Wonder weapons: much stronger than kit gear, but not unbreakable: they wear out and break.
    - Excalibur: netherite sword, Sharpness X, Sweeping Edge III, Fire Aspect II, Lifesteal III; 300 uses.
    - Thunderfang: trident, Sharpness VIII, Impaling V, Loyalty III, Channeling, Paralyze II; 200 uses.
    - Wunderwaffe: crossbow, Quick Charge III, Multishot, Piercing V, Power VI, Flame, Explosive II, + 64 arrows;
      250 uses (a multishot volley uses 3).
    - Thundergun: mace, Density VIII, Breach IV, Wind Burst III, + 16 wind charges; 150 uses.
  - Character gear: Lightsaber (Sharpness VI, Double Strike II), Darksaber (Sharpness VII, Fire Aspect), Arasaka
    Breaker (Sharpness VI axe, Cleave III).
  - Character abilities: Propane Tank, Jarate, Fingertip Lightning, Charge Shot, Krabby Patty. They
    work like the kits' ability items, and like all gear they're lost when you go down.
  - Guns (the kits' gun abilities, see Guns above): MA5 Assault Rifle, Super Shotgun, Lucky, Trunk M60, Amban Rifle, Laser Pistol.
  - Teddy Bear: nothing, and half the points (475) back.
- **Co-op revive**: going down leaves a glowing marker where you fell. A teammate crouching next to it for 3 s revives you
  there (with your kit) and gets +250 points. Otherwise you're back at the start of the next wave as before.
- **The Annihilator quest**: every boss wave cleared gives each survivor a **Power Cell**. Three Power Cells at the
  Arsenal (**Assemble: Annihilator**) build the Annihilator, a gun ability (50 blocks, 24 damage, 8 more to everything
  within 3 blocks of the hit, 0.8 s) that can be Pack-a-Punched like the other guns.
- **Food**: Rations in the Arsenal, plus 4 steak for every survivor whenever a wave is cleared.
- **Strays**: any wave mob outside the map's area (Ghosts are vexes and fly through blocks, under the floor or into the
  next map) is put back at a mob window once a second, so a wave can't stall on a mob nobody can reach.
- **Cleanup**: the map is force-loaded for the length of a run, so when the last player leaves or goes down every mob is
  killed. Any `pve.mob` found while no wave is running (for example, one saved in a chunk that loads later) is
  removed too.
- **Down**: if you die you spectate above the arena and come back with your kit when the wave is cleared. The run ends when
  everyone is down. Your best wave is saved in `pve.best`, and a new server record (`#record pve`) is announced to everyone.

Both the PvP kit menu (slot 49) and the Outbreak loadout menu (slot 51) have a **🎲 Random character** button
(`RANDOM_KIT` = 98 on `pvp.kit` / `pve.join`; `kit/roll` picks one and tells the player which).

**No stashing gear:** every decorative container in the arena, duel pits and Outbreak maps (barrels, chests, brewing
stands, `outbreak_maps.CONTAINERS`) is placed with a lock no real item matches, so it can't be opened; and items
dropped in the arena or a duel pit are removed every second. Otherwise you could hide items and switch character to
collect them. Maps built before this: `function pvp:admin/lock_containers` (with those areas force-loaded) locks and
empties them in place.

Kits, shop, mob pool, spawns and arena layouts are tables at the top of `build.py`.

## Haunted Night (Halloween 2026)
A limited-time Outbreak variant, open until **2026-11-07** (UTC). The **🎃 Haunted Night** NPC (a mannequin dressed as
Michael Myers, with jack o'lanterns, at 6.5 101 5.5 in the lobby; `admin/place_hw` / `admin/remove_hw`) opens it.
- **Gate**: the mod (`Events.java`) sets `#halloween pvp` to 1 every 5 s until 2026-11-07, then 0. While it's 0 the NPC
  is removed (`hw/gate`, every second) and the map can't be picked. `scoreboard players set #hwforce pvp 1` opens it
  anyway (for testing).
- It's Outbreak map 6 (`haunted`, centre 0, -60, 800; `admin/build_pve_haunted`): a moonlit graveyard around a
  ruined chapel, gravel paths, rows of tombstones, dead trees with cobwebs, a fenced crypt, a pumpkin patch with
  scarecrows and a witch's camp. It isn't in the Outbreak map menu or Random. Lobbies, drop-in, the Arsenal, wall-buys
  (M1911, Olympia, Kar98k, Stakeout), revive and power-ups all work as in Outbreak, but only one Outbreak lobby/run
  exists at a time, so the NPC says so if a normal Outbreak is on.
- **Horror characters only** (`HALLOWEEN_KITS`, ids 44-48; their own menu `pve_hw` with a random
  pick). They're never in the arena, duels, the Tower or random rolls elsewhere. Kits that don't fit the lobby's map
  are swapped for a random fitting one when the run starts (`hw/fix_kit`, `hw/unfix_kit`). They have mastery like
  every character.

  | Character | Gear | Abilities |
  |---|---|---|
| Michael Myers | Kitchen Knife: Sharpness IV, Bleed II · coveralls · a bit big | The Shape · Relentless |
  | Jason Voorhees | Machete (axe): Sharpness III, Cleave II · big and tough | Machete Throw · Shift |
  | Slender Man | Tendril (sword): Sharpness III, Blind II · black suit · very tall | Static · Tendrils |
  | Ghostface | Buck 120 Knife: Sharpness III, Assassin II · black robe (Dodge II) | Stalk · Ambush |
  | Freddy Fazbear | Microphone (mace): Density II, Stun II · animatronic suit · big | Jumpscare · Power Outage |

  All five heads come from the Head Index (minecraft-heads.com) cache.
- **Mobs** (its own roster, rolled instead of the normal pool): Pumpkinheads (zombies in carved pumpkins), Restless Bones
  (skeletons with jack o'lanterns, wave 2+), Graveyard Spiders (2+), Witches (3+), Ghosts (vexes, 4+), Ghouls (zombie
  villagers, 5+), Reapers (wither skeletons, 6+), Jack-o-Creepers (7+).
- **Bosses**: wave 5 **The Scarecrow** (a big zombie in a pumpkin and hay coat; every 8 s a cloud of crows slows and
  blinds nearby players and two Pumpkinheads join), wave 10 **the Headless Horseman** (a wither skeleton on a
  skeleton horse, holding a jack o'lantern; every 4 s graves burst under two players (evoker fangs), every 12 s two
  Ghosts, faster below half health). Boss abilities run from `hw/second`.
- **Winning**: clearing wave 10 ends the run (`hw/victory`): everyone in it counts a win (`pvp.hwwins`) and gets
  one random Halloween cosmetic they don't own yet (`hw/reward`, `pvp.hw<n>` = 1). With all of them, they're told so.
- **Cosmetics** (15, `HW_COSMETICS`): worn network-wide from the lobby's `/cosmetics` > Halloween page
  (CrispyLobby 1.13.0 reads the `pvp.hw<n>` scores; `halloween_cosmetics.py <config.yml>` writes their config).

  | # | Kind | Name | Code |
  |---|---|---|---|
  | 1 | tag | Lost My Head | `&8[&4☠ &cL&4o&cs&4t &cM&4y &cH&4e&ca&4d&8]` |
  | 2 | tag | Pumpkin King | `&8[&6☾ &6&lP&e&lu&6&lm&e&lp&6&lk&e&li&6&ln &8&lKing&8]` |
  | 3 | tag | Graveborn | `&8[&7✝ &7G&8r&fa&7v&8e&fb&7o&8r&fn&8]` |
  | 4 | tag | Crispy Halloween '26 | `&8[&6☾ &6&lC&e&lr&6&li&e&ls&6&lp&e&ly &6H&5a&6l&5l&6o&5w&6e&5e&6n &d'26&8]` |
  | 5 | tag | Trick or Treat | `&6[&eT&6r&fi&ec&6k &fo&er &6T&fr&ee&6a&ft&6]` |
  | 6 | tag | Slasher | `&4[&c⚔ &4&lS&c&ll&4&la&c&ls&4&lh&c&le&4&lr&4]` |
  | 7 | name colour | Pumpkin | `&#ff7518>&#ffb347` |
  | 8 | name colour | Candy Corn | `&#ffd23f/&#ff8c1a/&#ffffff` |
  | 9 | name colour | Witch's Brew | `&#7fff00>&#8a2be2` |
  | 10 | name colour | Blood Moon | `&#8b0000>&#ff3b3b` |
  | 11 | name colour | Ghostly | `&#ffffff>&#8a8f99` |
  | 12 | chat colour | Pumpkin Spice | `&#e8823a` |
  | 13 | chat colour | Candy Corn | `&#ffd23f/&#ff8c1a/&#ffffff` |
  | 14 | chat colour | Witch's Brew | `&#7fff00>&#8a2be2` |
  | 15 | chat colour | Spectral | `&#7df9ff>&#ffffff` |

## Balance (2026-10-25)
Kits were tuned so no character wins on stats alone. Each kit was scored as effective HP (health, armor, toughness,
Protection, Dodge, hitbox size, heals and shields, and debuffs it puts on the enemy) times damage per second (melee,
guns at a 75 % hit rate, abilities averaged over their cooldowns). Before: 0.2x to 4.8x the median. After: 0.8x to
1.25x, most within ±15 %. The main levers were armor (netherite only on chests), Sharpness, gun damage and fist bonuses.
- Nerfed: Adam Smasher, Doom Slayer, Spartan, Witcher, Courier Six, Mandalorian, Jedi, Sith, Darth Maul, Hero of
  Hyrule, Bender, Tony Soprano, Elliot.
- Buffed: SpongeBob and Hank Hill (spatulas swing like swords), Saul, Red, Rebecca, Walter White, Donkey Kong, Leela,
  Spider-Man, Sonic, Randy.
It is a model, not match data: watch kill counts per kit and adjust from there.

Second pass (from 53 kills in the logs after the first): Darth Maul got 17 and the Sniper 16 (three different players
on streaks with it); everything else had 0-3. Sniper Rifle Power V -> III, Lethal Sniper III -> II, no Lightning Arrows
(a full-draw Power V shot was ~22 damage before armor); Red's Slingshot back to Power IV; Darth Maul Double Strike III -> II,
Saber Throw 8 -> 6 damage (10 s), Saber Spin 7 -> 5 damage (9 s).

**Per-character stats** are now kept on the scoreboard: PvP kills in `pvp.kk` and deaths in `pvp.kd`, under fake players
`#<kit key>` (e.g. `scoreboard players get #maul pvp.kk`), counted from `pvp.cur` in `killed` and `respawned`.

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
Each rotation map is built on its own (force-load it first, e.g. Mustafar at -700 -400:
`forceload add -741 -441 -659 -359`, `function pvp:admin/build_map_mustafar`, then remove the forceload);
keys: mustafar, swamp, tegridy, quahog, bikini, mushroom, springfield, albuquerque, greenhill, rainey.
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
- Custom kits are not shown in the kit menus for now . Give one with
  `pvpkit give <id>`, or add `custom_kits` back to the menus in `build.py`.
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
  Since 1.4.5, item names, lore and the title are resolved for the viewer when the menu opens, so they can hold
  live parts (`selector`, `score`, `nbt` from storage): the lobby menus show the leader, the players and the map.
- `/pvpkit`, which manages admin-made kits (see above). The datapack uses `pvpkit give <id>` to hand one out. Minecraft 26.x is unobfuscated, so it compiles straight against the server jar with
Java 25:
```
spawnmod/build.sh <lib-dir> <path-to-javac-25>   # lib-dir: server-26.2.jar (from the official bundler), brigadier,
                                                  # fabric-loader 0.19.5, fabric-api 0.161.0 with its nested jars unpacked
```
Copy `crispy-pvp-spawn-1.3.1.jar` into `mods/` and restart the server.

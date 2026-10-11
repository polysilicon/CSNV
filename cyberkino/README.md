# Cyberpunk Kino

Black Ops Zombies in Cyberpunk 2077's Megabuilding H10: round-based waves, door buys, wall-buys, a Mystery Box,
Cyberpunk's guns and cyberware, and Black Ops' real Ray Gun.

- **Press F7** anywhere: V is teleported into V's apartment in Megabuilding H10 and the match starts there.
  V's equipped weapons and all of V's cyberware come off, leaving only a **Unity** pistol and the cyberware the
  chips give; it all goes back on when the match ends (F7 again, or when V goes down).
- **Zones and door buys.** Barricades close the corridors in rings around where you started. Buy one (F) to open
  the next ring: 750 points, each next ring 250 more.
- **Wall-buys** on the walls: Tactician, SOR-22, Pulsar, Shingen, Saratoga, Carnage, Copperhead. Buying again
  gives ammo for half the price.
- **The Mystery Box** (950): Lexington, Overture, Ajax, Masamune, Sidewinder, Kyubi, Crusher, Zhuo, Grad, Defender,
  Dian, and rarely the Achilles or **Black Ops' Ray Gun**, its model read from your own copy of Black Ops.
- **Zombies:** Scavengers and Maelstrom, melee only, more each round; every 5th round a **cyberpsycho**.
- **Cyberware chips:** one zombie per round drops a chip. Pick it up (F) for the next piece you don't have:
  Sandevistan (Z slows time), Reinforced Tendons (double jump), Subdermal Armor, Mantis Blades.
- 500 points to start, 60 per kill, 100 extra for the chip carrier, 500 for a cyberpsycho. Solo.

Keys: F7 start/stop, F buy/pick up, Z Sandevistan (change them in CET's Bindings tab).

You need both games: Cyberpunk 2077 and Call of Duty: Black Ops (Steam). Nothing from either game is included;
the Ray Gun is read from your Black Ops each time it changes.

## Playing
Install it from Melty and press Play. The first time, the launcher spends about a minute building the Ray Gun,
then Cyberpunk starts. Load a save and press F7.

While the mod is installed, the Militech Omaha pistol looks like the Ray Gun everywhere in the game.

If something goes wrong: `cyberkino-launch.log` next to the launcher (the Ray Gun build) and `cyberkino.log`
in `bin\x64\plugins\cyber_engine_tweaks\mods\cyberkino` (each match) say what happened.

## How it works
- `cet/cyberkino/init.lua` (Cyber Engine Tweaks, which Melty installs): the match. When F7 is pressed it casts
  rays around V to find the walls, places barricades (Cyberpunk's road barrier prop) where each ring crosses an
  opening, weapon cases on the walls for the wall-buys and a weapon crate as the Mystery Box, and spawns the
  zombies from Cyberpunk's own character records. Guns and cyberware are Cyberpunk's own items and stats.
- `cyberkino-launch.exe` (each Play): reads `ray_gun_zm` and its world model from Black Ops'
  `zone\Common\common_zombie.ff` with OpenAssetTools' Unlinker, exports the Omaha's meshes from your Cyberpunk
  with WolvenKit, fits the Ray Gun onto the Omaha's body mesh (same length, muzzle forward, on the Omaha's rig),
  empties the Omaha's other parts, imports and packs them into `archive\pc\mod\zz_cyberkino_raygun.archive`,
  presets the CET keys and starts Cyberpunk.

## Building
The design lives in JSON sheets in `sheets/` (weapons, cyberware, zombies, rules, props, keys, arena, Ray Gun, tools).
- `python3 tools/preflight.py`: every unfilled cell and broken reference (set `CYBERKINO_TDB` and `CYBERKINO_PATHS`
  to WolvenKit's TweakDB name list and path list to check every record and depot path against the game).
- `python3 tools/build.py [--release]`: generates `cet/cyberkino/data.lua` and `launcher/sheets_gen.go`, builds the
  launcher, and with `--release` downloads the bundled tools and writes `build/CyberKino-<version>.zip`.
- `luajit tools/cetsim/sim.lua`: plays a whole match of the CET mod against stand-ins for the game's API.
- `cd launcher && go test ./...`.

`melty.json` is the install recipe Melty uses.

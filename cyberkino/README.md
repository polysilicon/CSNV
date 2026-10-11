# Cyberpunk Kino

Black Ops Zombies in Cyberpunk 2077's Megabuilding H10: round-based waves, door buys, wall-buys, a Mystery Box,
Cyberpunk's guns and cyberware, and Black Ops' real Ray Gun.

- **Press F7** anywhere: V is teleported into V's apartment in Megabuilding H10 and the match starts there.
  V's weapons go into V's own stash in the apartment and all of V's cyberware comes off, leaving only a **Unity**
  pistol and the cyberware the chips give; it all comes back when the match ends (F7 again, or when V goes down).
- **A fixed map, like Kino.** The barricades, wall-buys, Mystery Box spots and zombie windows sit in fixed places
  on H10, placed with the in-game layout editor (CET overlay > "Cyberpunk Kino layout"). Each barricade is bought on its
  own (F), like Kino's doors: 750 points, each next one 250 more, and it wakes the zombie spawns behind it. Closed
  barricades hold along their whole width: you can't walk past them.
- **Wall-buys** on the walls: Tactician, SOR-22, Pulsar, Shingen, Saratoga, Carnage, Copperhead. Buying again
  gives ammo for half the price.
- **The Mystery Box** (950, moves to another spot every 4 uses): Lexington, Overture, Ajax, Masamune, Sidewinder, Kyubi, Crusher, Zhuo, Grad, Defender,
  Dian, and rarely the Achilles or **Black Ops' Ray Gun**, its model read from your own copy of Black Ops.
- **Zombies:** Scavengers and Maelstrom, melee only, more each round; every 5th round a **cyberpsycho**.
- **Cyberware chips:** one zombie per round drops a chip. Pick it up (F) for the next piece you don't have:
  Sandevistan (Z slows time), Reinforced Tendons (double jump), Subdermal Armor, Mantis Blades.
- 500 points to start, 60 per kill, 100 extra for the chip carrier, 500 for a cyberpsycho. Solo.

Keys: F7 start/stop, F buy/pick up, Z Sandevistan (change them in CET's Bindings tab). On a controller, hold
Reload (X on Xbox, Square on PlayStation) at a barricade, wall-buy, Mystery Box or chip to use it, like Black Ops.

You need both games: Cyberpunk 2077 and Call of Duty: Black Ops (Steam). Nothing from either game is included;
the Ray Gun is read from your Black Ops each time it changes.

## Playing
Install it from Melty and press Play. The first time, the launcher spends about a minute building the Ray Gun,
then Cyberpunk starts. Load a save and press F7.

While the mod is installed, the Militech Omaha pistol looks like the Ray Gun everywhere in the game.

If something goes wrong: `cyberkino-launch.log` next to the launcher (the Ray Gun build) and `cyberkino.log`
in `bin\x64\plugins\cyber_engine_tweaks\mods\cyberkino` (each match) say what happened.

## How it works
- `cet/cyberkino/init.lua` (Cyber Engine Tweaks, which Melty installs): the match. F7 teleports V into V's
  apartment, moves V's weapons into V's stash, takes off V's cyberware, and places the layout (`sheets/layout.json`,
  or a player's own `layout.json` from the editor): Cyberpunk's road barrier props as barricades, weapon cases as
  wall-buys and Mystery Box, and zombies from Cyberpunk's own character records at the spawn points of open zones.
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

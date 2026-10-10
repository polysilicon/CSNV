# Cyberpunk Kino

Black Ops Zombies on the real Kino der Toten, with Cyberpunk 2077's guns and cyberware.

- **You're in Black Ops.** Kino der Toten is loaded from your own copy of Call of Duty: Black Ops: the
  map, the zombies, the rounds, the perks, Pack-a-Punch and the Mystery Box all run as they do in Black Ops.
- **Every gun is a Cyberpunk gun.** You start with a Unity. The wall-buys become the SOR-22, Copperhead,
  Saratoga, Pulsar, Shingen, Dian, Carnage and Tactician. The Mystery Box only rolls Cyberpunk guns:
  Lexington, Overture, Ajax, Masamune, Sidewinder, Kyubi, Crusher, Zhuo, Grad and Defender, plus the rare
  Achilles and Malorian Arms 3516. Pack-a-Punch makes the Iconic version of each one.
  Their 3D models and colours come from your own copy of Cyberpunk 2077. They fire with Black Ops' sounds
  and animations.
- **Cyberware from special zombies.** One glowing zombie each round drops a cyberware chip. Hold Use on it
  to install the next piece you don't have yet:
  - **Sandevistan:** aim and press Melee to slow time for a few seconds (20 s cooldown).
  - **Reinforced Tendons:** press Jump again in the air to double jump.
  - **Subdermal Armor:** you take more hits (stacks with Juggernog).
  - **Mantis Blades:** they replace your knife and cut zombies down.
  Like perks, you lose your cyberware when you go down.
- **Solo.** Black Ops only loads mods in solo play.

You need both games installed: Call of Duty: Black Ops (Steam) and Cyberpunk 2077. Nothing from either
game is included in the mod; it reads both from your PC.

## Playing
Install it from Melty and press Play. The first time, the launcher spends a minute or two building the mod
from your games (later Plays are instant unless a game updates). Then Black Ops starts with the mod loaded:
choose **Zombies > Solo > Kino der Toten**.

If something goes wrong, `cyberkino-launch.log` next to the launcher says what, line by line (lines that
start with `CyberKino error:` or `CyberKino warning:`).

## How it works
Each Play, `cyberkino-launch.exe`:
1. reads Kino from your Black Ops `zone\Common\zombie_theater.ff` with OpenAssetTools' Unlinker (weapon
   files, gun models and skeletons, materials, Kino's scripts);
2. exports the Cyberpunk meshes listed in `sheets/weapons.json` and `sheets/models.json` from your
   Cyberpunk archives with WolvenKit, with their materials;
3. fits each Cyberpunk gun into the Black Ops gun it replaces (same length, muzzle at its `tag_flash`,
   bound to its skeleton, so Black Ops' animations move it) and rebuilds its colours;
4. writes the weapon files (the Black Ops gun's own file with the Cyberpunk name, model and numbers),
   adds two lines to Kino's `zombie_theater.gsc` that run `maps/cyberkino.gsc`, and links everything into
   `<Black Ops>\mods\cyberkino\mod.ff` and `cyberkino.iwd` with OpenAssetTools' Linker;
5. asks Steam to start Black Ops with the mod (`steam.exe -applaunch 42700 +set fs_game mods/cyberkino`;
   Steam's copy of Black Ops drops its launch options when started directly).

The work files are in `%LOCALAPPDATA%\CyberKino`.

## Building
The design lives in JSON sheets in `sheets/`, one row per gun, chip, model, script hook, zone and tool.
- `python3 tools/preflight.py`: lists every unfilled cell and broken cross-reference (set `CYBERKINO_PATHS`
  to WolvenKit's path list to also check every Cyberpunk mesh path).
- `python3 tools/build.py`: generates `gsc/maps/cyberkino.gsc`, `gsc/clientscripts/cyberkino.csc`,
  `gsc/english/localizedstrings/cyberkino.str` and `launcher/sheets_gen.go` from the sheets and builds
  the launcher (Go). `--release` also downloads the bundled tools and writes `build/CyberKino-<version>.zip`.
- `cd launcher && go test ./...` (set `OAT_LINKER` to OpenAssetTools' Linker to also run a model and
  weapon through the real Linker and back).

`melty.json` is the install recipe Melty uses.

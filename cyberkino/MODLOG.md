# Cyberpunk Kino: mod log

## Design (interview, 2026-10-10)
- Black Ops Zombies on the real Kino der Toten (Black Ops is the host), with Cyberpunk 2077's guns and cyberware.
- Cyberware comes from special zombies: one per round drops a chip (Sandevistan, Reinforced Tendons,
  Subdermal Armor, Mantis Blades).
- Cyberpunk guns everywhere: start pistol, wall-buys and Mystery Box.
- Solo (Black Ops loads mods offline only).
- Limit agreed in the interview: the guns fire with Black Ops sounds (OpenAssetTools can't build T5 sound banks).

## Melty read-up
- cyberpunk-2077: redengine, CET/RED4ext/redscript/ArchiveXL/TweakXL auto-installed (not needed here: Cyberpunk
  isn't started, its archives are read with WolvenKit). 12 live mashups, none with Black Ops.
- custom-call-of-duty-black-ops (Steam 42700): outside the catalog, host supported, no loader.
- Closest: Nacht der Blocks (Minecraft + BO1, BO1 only "secondary"), Mirror's Edge: Night City (recipe example).

## Route
- Black Ops (T5, IW-engine derivative): mods/<name>/mod.ff loaded with `+set fs_game mods/<name>`; mod.ff assets
  override the stock level's (how BO1 Reimagined edits stock maps' scripts).
- OpenAssetTools v0.33.0 (Linux build tested here, Windows build bundled): T5 Unlinker dumps weapon/xmodel/material/
  rawfile; Linker loads XModel (glTF), Material (JSON), Weapon (raw infostring), RawFile, Localize; images are
  external .iwi (ImageConverter) packed in an .iwd. Sound banks can't be built.
- WolvenKit 9.1.0 console (needs .NET 10, bundled) `uncook` exports Cyberpunk .mesh to glTF + material JSON + PNG.
- Cyberpunk mesh paths verified against WolvenKit's path list (usedhashes.kark, decompressed with its libkraken).
- Fitting: Cyberpunk gun turned so its muzzle (thin end) points at the Black Ops gun's tag_flash, scaled to its
  length, centred, every vertex on the Black Ops model's dominant joint, Black Ops skeleton + inverse binds kept.
- Scripts: two lines added at run time to the player's own maps/zombie_theater.gsc around maps\_zombiemode::main()
  (pre_main / post_main); one to clientscripts/zombie_theater.csc include_weapons().

## Checked here (Linux, no games)
- preflight clean: 9 sheets, 0 unfilled, 0 broken; all 46 Cyberpunk mesh paths exist in the game's path list.
- go vet + go test: weapon file edits, hooks, fitting, DDS, zone file, material clone; a fitted model and an edited
  weapon file go through the real OAT T5 Linker and back through the Unlinker unchanged (skeleton, length, muzzle).
- Not checkable here: the real Kino dump, WolvenKit's export layout, BO1 loading the mod, the GSC compiling.

## Melty
- modId 20b26959-2fb3-472b-b388-e2138a5c5873 (slug cyberpunk-kino), draft.
- Release 0.1.0: CyberKino-0.1.0.zip, 85115712 bytes, sha256 c1fd6ff7863b9481ed648f1f72ac3298f3796b26f61e252caa81f17c04a1ca47,
  uploadId 75315a42-5ab2-49bd-ba43-7cf3e887573e, releaseId 5b5401b7-1f42-43f0-b82e-5f5f78b4ff23.
  validate_recipe valid; one_click_check yes, publishable; findings: review (executable code, unverified layout).
- Test d6e7f31b-4de1-44bb-95cc-01f965357d0e (3 runs x 8 min): waiting for the creator to open it on their PC.

## Test 1 (0.1.0, creator's PC, pressed Play)
- Error box: "none of the Cyberpunk guns could be built". Unlinker and WolvenKit both exited 0, so every gun failed
  a later step. No log received yet. Likely cause: the zombie weapon files, view models and materials live in
  common_zombie.ff, and only zombie_theater.ff was dumped. (WolvenKit also exits 0 when it exports nothing.)
- Fix (0.1.1): zones use load | unlink | both; common_zombie.ff and zombie_theater.ff are both dumped (Kino's own
  wins) and referenced while linking; dumps logged with counts; Cyberpunk .glb found anywhere in WolvenKit's output;
  WolvenKit exporting nothing is its own error; material falls back to any dumped weapon material; the error box
  lists the first three reasons.
- Release 0.1.1: CyberKino-0.1.1.zip, 85118954 bytes, sha256 9c8724d2..2087, releaseId 707cea70-7f62-4bb9-9b5c-31f3a259db03.
  Test e7d35709-adc7-4d31-a4eb-931f2ba0f543. (Test d6e7f31b was never picked up by Melty on the PC.)

## Test 2 (0.1.1, creator's PC, log received)
- Both zones dumped (common_zombie: 79 weapons, 316 models, 624 materials; zombie_theater: 13 weapons, 925 models,
  1244 materials). WolvenKit exported 46/46 meshes in 27 s. All 21 guns built. Hooks applied. Cloned materials load.
- Linker failed: "Lod exceeds limit of 65535 vertices" (cpk_copperhead_view). Cyberpunk meshes are much denser.
- Every glTF material was "Default": WolvenKit names them so; the real material per submesh is in .Material.json's
  Appearances. So every gun was gun-metal grey.
- Muzzle guess split -Z / +Z across guns; Cyberpunk's convention (+Y forward, Z up) is -Z in WolvenKit's glTF.
- Fix (0.1.2): vertex-clustering simplify to 20000 vertices per model (per material and normal direction);
  submesh materials from Appearances; Cyberpunk forward fixed at -Z. Release 0.1.2: sha256 cebf4272..0410.

## Test 3 (0.1.2, creator's PC, log received)
- All 21 guns built under 20000 vertices each; real Cyberpunk materials found (multilayer, BaseColor, Albedo,
  DiffuseTexture; a few fall back to grey). All guns face -Z -> +X. Chip and Mantis built. Models and materials link.
- Linker failed on the first weapon: missing sub asset "aivsai/pistol.accu" (accuracygraph). OAT reads accuracy graphs
  from accuracy/aivsai|aivsplayer/<name> and flame tables from weapons/<name>.
- Fix (0.1.3): writeWeapon copies those from the dump, or writes a flat accuracy graph (AI aim only); flame tables
  not dumped are blanked. Release 0.1.3 sha256 5ec31560..e549, releaseId 3fbe4948-f2ed-4c98-8d14-15bca734c40c,
  test 086193db-08f8-4138-8bac-d7e7572ca2ce.

## Test 4 (0.1.3, creator's PC)
- mod.ff built and Black Ops booted, but guns were the stock Black Ops ones. A loaded mod with broken scripts would
  stop Kino with a script error, so the mod most likely wasn't loaded: a Steam game started directly restarts
  through Steam and loses its command line (+set fs_game mods/cyberkino).
- Fix (0.1.4): write steam_appid.txt (42700) next to BlackOps.exe so it keeps its command line; if the process
  still exits within 15 s, start it via steam://run/42700//+set fs_game mods/cyberkino/. Release 0.1.4 sha256
  81ecd344..dfbd, test 97debbaa-91a6-49ec-b59d-0ff9a40a3fd8.
- Fallback check for the creator: Black Ops main menu > Mods > cyberkino loads the same mod by hand.

## Test 5 (0.1.4, log received)
- Built in 1m50s, mod written. BlackOps.exe exited at once despite steam_appid.txt (Steam's DRM hands over).
  The fallback steam://run link had raw spaces, so Windows' URL handler most likely cut the options off.
- Fix (0.1.5): start through steam.exe -applaunch 42700 +set fs_game mods/cyberkino (steam.exe found via the
  registry: HKCU SteamExe, HKLM InstallPath); fallback steam://run link URL-encoded. No more steam_appid.txt
  (the one 0.1.4 wrote stays; it is harmless). Release 0.1.5 sha256 49c1cfc5..4e6f, test 05394932-6d9f-472e-9f7e-abd893977759.

## Test 6 (0.1.5)
- Still stock guns; no log sent. Unknown whether fs_game reaches the game or the mod loads but its scripts don't run.
- 0.1.6 adds proof: "Cyberpunk Kino loaded" on screen 8 s into Kino (post_main ran), PrintLn markers, and
  +set logfile 2 so Black Ops writes mods/cyberkino/console.log; the next Play copies its telling lines into
  cyberkino-launch.log. Release 0.1.6 sha256 5c8e9659..ad30, test 44fafbe4-15f5-4b08-b776-6351c3963ad1.

## Test 7 (0.1.6)
- No "Cyberpunk Kino loaded" message; creator's Black Ops shows no Mods menu. Log (first run of 0.1.6): mod built,
  steam.exe -applaunch asked with +set fs_game mods/cyberkino +set logfile 2; no console.log from before.
- 0.1.7: the launcher stays after handing over to Steam, logs BlackOps.exe's real command line (Win32_Process via
  PowerShell), says whether fs_game arrived, waits for the game to close and copies console.log's telling lines.

## Test 8 (0.1.7, log received)
- Black Ops' real command line: "BlackOps.exe" +set fs_game mods/cyberkino +set logfile 2. The options arrive;
  Steam was not the problem. No console.log in mods/cyberkino or main afterwards.
- Remaining causes: Black Ops doesn't load mod.ff, or loads it before Kino's zone so Kino's own scripts win.
- 0.1.8: every gun is also written under its stock weapon names (bo_base, bo_base_upgraded, replaces), so mod.ff
  alone swaps the guns, no script needed; the launcher lists mods/cyberkino and scans the Black Ops folder,
  LocalAppData\Activision, VirtualStore and Documents for any .log written while the game ran.

## Test 9 (0.1.8, log received) - root cause found
- mods/cyberkino holds mod.ff (22.8 MB) and cyberkino.iwd (70 MB); BlackOps.exe ran 4 min with
  +set fs_game mods/cyberkino +set logfile 2; starting pistol and the Olympia wall-buy stayed stock; no log written.
- Cause: retail Black Ops 1 on Steam has no mod loading (no Mods menu, fs_game ignored). The community route is
  Game_Mod from Nukem9/LinkerMod: a DLL started by bin/launcher_ldr.exe via BO_Mods.bat that patches BlackOps.exe,
  including turning off Steam DRM (CEG) checks (components/game_mod/CEG.cpp). The repository has no licence.
- So the Black Ops-host design can't ship one-click: Game_Mod can't be bundled (no licence), players would install
  it by hand (Melty blocks that), and writing an equivalent means bypassing the game's DRM, which this project won't do.
- Waiting on the creator's decision (see reply).

## Redesign (0.2.0): Cyberpunk host
- Creator chose: Kino-style Zombies inside Cyberpunk (Kino map can't be exported/collided), arena inside Megabuilding H10,
  Scavengers + Maelstrom with a cyberpsycho every 5th round, Cyberpunk guns/cyberware, Black Ops' Ray Gun, F7 hotkey,
  V starts with a Unity only.
- CET mod (cet/cyberkino): arena from raycasts around V (barricade rings = door buys, wall-buy cases on walls, box),
  rounds, points, chips, cyberware (stat modifiers, time dilation, Mantis Blades item), loadout stashed and restored.
  All records checked against WolvenKit's TweakDB name list; tools/cetsim/sim.lua plays a full match with 0 errors.
- Launcher: Ray Gun from common_zombie.ff (OAT) fitted onto the Omaha body mesh, other Omaha parts emptied, WolvenKit
  import + pack -> archive/pc/mod/zz_cyberkino_raygun.archive; presets CET bindings (F7/F/Z); starts Cyberpunk.
- Release 0.2.0: sha256 eb4fde3a..e87a, releaseId 13878e00-f09b-4240-82a2-eba82ae805f9, one click yes,
  test 50dcc14a-6787-4be2-8bc1-84e7ee696a95. Untested in game.

## Test 10 (0.2.0, creator's report)
- V's inventory and cyberware stayed during the match. Cause: the mod used EquipRequest, which doesn't exist in
  Cyberpunk (WolvenKit's RTTI classes: GameplayEquipRequest{owner,itemID,slotIndex,addToInventory,forceEquipWeapon},
  UnequipRequest{owner,areaType,slotIndex,force}), so equipping the Unity and restoring failed.
- Creator asked F7 to teleport to V's apartment first.
- 0.2.1: F7 teleports to V's Apartment (-1391.87, 1271.69, 123.08, yaw -99.25 from Appearance Menu Mod's locations
  db), waits teleport_settle_s, then builds the arena. Weapons (3 slots) and all 12 cyberware areas (4 slots each)
  are force-unequipped and recorded; equip/restore use GameplayEquipRequest. Unequipped items stay in the backpack.
  Release 0.2.1 sha256 9be85189..130f, test 7d7037f4-f064-46f6-99b1-4e6ea7796c95.

## Open
1. Play 0.3.2 on the creator's layout (TESTING.md part 2) and send cyberkino.log.
2. Real screenshot from that test.
3. Licence and remix choice from the creator.

## Test 11 (0.2.1, creator's report)
- Teleport works and cyberware is removed. Weapons stayed in the backpack (unequipped only).
- Wall-buys and the box landed in random spots, zombies spawned in one place, and invisible barriers sent V back
  to the start. Cause: the arena was built from raycasts around V, which don't understand the apartment's walls.
- 0.3.0: fixed layout instead of raycasts. CET overlay -> "Cyberpunk Kino layout" editor records the match start,
  V's stash, wall-buys (face the wall), Mystery Box spots, zombie spawns and barricades per zone into layout.json
  (sheets/layout.json ships it once recorded). Weapons are moved into V's stash during a match and back after.
  A closed barricade pushes V back where they stand, not to the start. The box moves after 4 uses.
  Simulation: 77 log lines, 0 errors. Release 0.3.0 sha256 8489d518..cf4b, test eb1b0a05-f207-4d46-a631-3edb85d506e4.

## Layout from the creator (0.3.1)
- Creator placed the arena with the editor: start, 6 barricades (all zone 1), 4 zone-1 and 3 zone-2 spawns, 6 wall-buys
  (Tactician, SOR-22, Pulsar, Shingen, Saratoga, Carnage), 2 Mystery Box spots, V's stash (entity 16570246047455160070ULL,
  class Stash). Two floors: z 123 and z 119. Copied into sheets/layout.json; no match played on it yet.
- With all six barricades in zone 1, buying one would have cleared all six. 0.3.1: each barricade is bought on its own
  (price door_cost_first + bought * door_cost_step) and wakes the spawns of the zone behind it.
- Hold is now a rectangle along the barricade (barricade_half_width_m 1.5) that also catches walking past the line,
  and it keeps V's place along it. Buys, chips and holds only count on V's floor (floor_height_m 2.0), since the two
  floors stack wall-buys within 2.5 m of each other.
- A gun missing from the inventory the frame it's given (0.2.1 log: Ajax) is looked for again for 30 frames and equipped.
- Simulator: new edge, past-the-line, beside, other-floor, through-the-floor and one-door-only checks (90 lines, 0
  errors); CYBERKINO_SIM_SHIPPED=1 plays the built-in layout (6 barricades, 6 wall-buys, 2 box spots, 7 spawns, 0 errors).
- Release 0.3.1 sha256 2c7b861e..b1c2, releaseId 8dd01ae6-677e-4e8d-b1d0-0b82ef6e218c, one click yes,
  test 825ed2a3-19ce-44ba-bbae-303aed99dd06.

## Test 12 (0.3.1, creator's report)
- Layout works. Zombies don't target or attack V. Creator asked for a controller button for doors, chips, wall-buys and box.
- Cause (likely): spawned NPCs come up passive; setting the attitude alone doesn't start combat. V's apartment also puts
  GameplayRestriction.NoCombat on V.
- 0.3.2: zombies get Appearance Menu Mod's hostile recipe (plain AIRole, hostile attitude both ways,
  ReactionPresets.Ganger_Aggressive, reactionComponent:TriggerCombat(V)) hostile_delay_s after spawning, again 2 s
  later, then TriggerCombat every combat_refresh_s. GameplayRestriction.NoCombat is lifted from V during a match.
  Controller: Observe PlayerPuppet.OnAction, hold "Reload" (X / Square) for hold_buy_s at a buy uses it; F and the
  hold share a 0.3 s guard so one press never buys twice. Both records checked in the TweakDB name list.
- Simulator: zombies set hostile and kept in combat, restriction lifted, Reload tap doesn't buy and hold does (0 errors);
  shipped layout 0 errors.
- Release 0.3.2 sha256 27479950..4cb4, releaseId 63083e88-0241-4487-a987-da009fe06e59, one click yes,
  test 376002d8-6c8b-4fac-91aa-693559767b01.

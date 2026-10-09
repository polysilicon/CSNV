# Crab Run: Night City: mod log

Solo Cyberpunk 2077 mod (host) with Crab Champions as a required companion: every load is a Crab
Champions-style run in Night City.

## Decisions (with the user)
- User first wanted to play inside Crab Champions; Melty can't host a non-catalog game yet, so the idea was
  flipped: Cyberpunk is the host and Crab Champions brings its run structure, perks, icons and sounds.
- First minute: loading a save starts a run (fresh start, starter weapon, countdown, waves).
- Between waves: a crystal shop with Crab perks, Cyberpunk cyberware and Cyberpunk weapons.
- Solo, with shareable run seeds. v1 must have: scaling waves, Crab sounds & icons, island hops, Crab-style HUD.
- License MIT, remixes allowed.

## Melty read-up (2026-10-09)
- cyberpunk-2077: Melty installs CET 1.37.1, RED4ext, redscript, ArchiveXL, TweakXL. No account risk flagged.
- custom-crab-champions: not in catalog; usable as companion via {game:custom-crab-champions}.
- Nothing joins these two yet. Closest: Risk of Crab (RoR2 + Crab), Mirror's Edge: Night City (CET + bridge exe).

## Route
- CET Lua mod (`mod/`) for the run; `CrabRunBridge.exe` (`bridge/`, .NET 10 single file) launched by Melty:
  reads Crab Champions' UE 4.27 paks with CUE4Parse 1.2.2.202609 (managed Zlib/Oodle, no native DLLs
  besides SkiaSharp), writes crab/crab_data.json + icons/sounds into the CET mod folder, starts Cyberpunk,
  plays sounds (NAudio/NVorbis), relays keys (GetAsyncKeyState while Cyberpunk is foreground).
- CET facts checked in CET source: ImGui.LoadTexture (stb_image, only in onDraw), sandbox has json, bit32,
  loadstring, no setfenv/bit; io paths relative to the mod folder.
- Game API signatures checked in the decompiled 2.31 scripts (codeberg adamsmasher/cyberpunk): EquipRequest,
  UnequipRequest, StatusEffectSystem.ApplyStatusEffect, RPGManager.CreateStatModifier, NavigationSystem,
  GodModeSystem, TimeSystem. Spawning/hostility patterns from Entity Spawner and AMM. Enemy records and
  island coordinates from AMM's database; shop item records all appear in the 2.31 game scripts.

## Status
- preflight CLEAN (12 sheets, 173 rows). Lua tests 265 + 173 pass (simulated game). Bridge tests 18 pass
  (pak mount incl. zlib, matching, ogg/wav decode, file channel). Windows exe smoke-tested under Wine:
  extraction, launch of a stand-in Cyberpunk2077.exe, heartbeat, exit on game close.
- Property walker checked on real UE4 cooked assets (UAssetAPI test files, not shipped). Real Crab Champions
  perk/texture/sound extraction NOT yet run: needs a PC with Crab Champions.
- **Untested in game.** All rows in_game=false.

## Melty listing
- modId 8ba45d6b-9a94-414d-908c-38a050347a51 (slug crab-run-night-city), draft, MIT, remixes allowed.
- Release 0.1.0 (releaseId c5312cfb-1522-40fe-a7c1-28c26f488df5): CrabRun-0.1.0.zip, 44050723 bytes,
  sha256 6d635a08...c3ac. One click: yes, publishable. Finding: executable-code (review).
- No screenshot yet: needs the game running on the user's PC.

## In-game test 1 (0.1.0, user's PC)
- Save loaded, no countdown, no waves. Cause: game.session_ok called Game.GetSystemRequestsHandler(), which
  is an inkMenuScenario method, not a Game function; the error made every frame read as "main menu", so the
  run never started. The hooks sheet had marked it "community idiom" instead of checking it.
- Fix (0.1.1): GetSingleton('inkMenuScenario'):GetSystemRequestsHandler():IsPreGame(), and a failing
  pre-game check no longer blocks (player present + attached is enough). tests/test_game.lua loads the real
  game.lua with CET-like globals; it fails on 0.1.0 with the same error and passes on 0.1.1. All other
  Game.* calls re-checked against the 2.31 scripts (GetDynamicEntitySystem is native-only, used by Entity Spawner).
- Release 0.1.1 submitted (CrabRun-0.1.1.zip, sha256 ab124248...628d), one click yes.

## Next
1. In-game test on the user's PC (Melty Test): check crabrun.log, bridge.log, crab/crab_data.json.
2. Fix what it shows (perk keys vs DA_Perk names, sound keywords, spawn hostility).
3. Real gameplay screenshot/clip -> add_screenshot -> publish on the user's say-so.

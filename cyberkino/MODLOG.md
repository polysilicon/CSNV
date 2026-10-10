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

## Open
1. In-game test on the creator's PC (TESTING.md), then fixes.
2. Real screenshot from that test.
3. Licence and remix choice from the creator.

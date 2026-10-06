# CS2 in the Mojave: mod log

Solo Fallout: New Vegas mod with a Counter-Strike 2 layer. The player's CS2 buy key and crosshair come along
(read from CS2's settings files on disk; CS2 is never started, so no VAC risk). CS-style HUD, CS2-styled buy
menu, 3 weapons bought with caps.

## Decisions (with the user)
- Continue this design; CS2 brings the player's setup (binds + crosshair) by reading files only.
- First minute: the HUD switches as soon as a save loads; the buy key works anywhere.
- v1 scope: core loop + CS2-styled buy menu (option 2). Solo.

## Melty read-up (2026-10-06)
- fallout-new-vegas: Melty installs xNVSE 6.4.9 itself; launch `{game}/nvse_loader.exe`. 0 live mashups.
- counter-strike-2: no loader; VAC risk for anything loading into the game. Closest mashup: Spike Rush
  (CS2 + Geometry Dash, standalone, reads the player's CS2 binds/crosshair). Nothing like this exists.
- Recipe checked with validate_recipe + one_click_check (with every entry): **one click: yes, publishable**.
  `entries` must be `{path, size}` objects; plain strings crash Melty's checker server-side.

## Route
- Loader: xNVSE (Melty installs it) + **JIP LN NVSE bundled** (GPL-3.0; needed for the script runner,
  InjectUIXML, key/menu events, MessageBoxExAlt, GetINIFloat, aux vars, GetFormFromMod).
- No GECK, no hand-made .esp: logic is an xNVSE UDF file in `Data/NVSE/user_defined_functions/csnv/`
  (xNVSE precompiles that folder at startup; `CompileScript "csnv\csnv_main.txt"` returns it), started by a
  one-line JIP runner script `Data/NVSE/Plugins/scripts/ln_csnv.txt` (`ln_` = load or new game).
- Weapons: **not** xNVSE CloneForm. Its own help text says clones are not saved, and the persist flag is
  ignored in `TESForm::CloneForm`, so bought guns would vanish on reload. Instead `csnv-launch.exe` copies
  the base WEAP records out of the player's own FalloutNV.esm into `Data/CSNV.esp` before every Play
  (DATA damage/clip, DNAM flags/fire rate per xEdit's wbDefinitionsFNV.pas) and adds it to plugins.txt.
- Launch: Melty runs `{managed}/csnv-launch.exe --fnv {game} --cs2 {game:counter-strike-2}`; it writes
  `Data/config/csnv_cs2.ini` + `xhair.dds`, builds CSNV.esp, then runs `nvse_loader.exe`. Log: `{managed}/csnv-launch.log`.
- HUD/buy screen: XML layers injected into HUDMainMenu (once per session) and MessageMenu (each open).

## Source facts checked (xNVSE 6.4.9 tag, JIP LN main)
- JIP runner prefixes: gr_ restart, lg_/gl_ load, ln_/nl_ load-or-new, ng_ new, sg_ save, xg_ exit, mx_ main menu.
- JIP temp aux vars (`*` prefix) survive loading a save; names starting `_` are global (not tied to a mod).
- JIP event handlers are not cleared on load; xNVSE delayed calls (CallWhilePerSeconds) are -> restart each load.
- JIP GetINIFloat reads `Data\config\<file>`, key syntax `Section:Key`.
- InjectUIXML path is relative to the game folder (JIP itself reads `jip_temp.xml` from the cwd).
- MessageBoxExAlt calls its callback with the 0-based button index.

## GitHub / Melty setup
- melty.json at the repo root (validated, one click: yes; fileName CSNV-*.zip).
- CI: .github/workflows/ci.yml (preflight, go vet/test, build). Release: tag v* -> release.yml builds with --release and attaches the zip.
- Default branch claude/cs2-mojave-mod-rmm4pm now carries everything (PRs #1, #2 merged).
- Release v0.1.0 published by the workflow (manual run; this session cannot push tags): CSNV-0.1.0.zip, 1247674 bytes, sha256 cf22a238f7333da1fcc249a35287bc7c6b6abf40c6e4870778630cc69d2f3362. Still untested in game.
- vendor/jip_nvse.dll (JIP 57.30) is committed; build --release works.

## Melty listing
- modId 25c95984-1204-494b-ac6f-71ecdd3e99ca (slug cs2-in-the-mojave), draft made by the user (text, games, pictures).
- Set: license "MIT (bundled JIP LN NVSE: GPL-3.0)", remixes allowed.
- Release 0.1.0 submitted (releaseId e51073e3-4334-426b-ab63-bc3ded61408c): upload CSNV-0.1.0.zip = the GitHub v0.1.0 asset,
  sha256 cf22a238...3362. submit_release + one_click_check on the stored files: one click yes, publishable, nothing to finish.
  Only finding: 'executable-code' (csnv-launch.exe, jip_nvse.dll), severity review.
- Release 0.1.1 submitted (GitHub v0.1.1 asset, 1249813 bytes, sha256 9df53ca2...a32f, 22 files): one click yes. Supersedes 0.1.0 (broken script).
- Next: user presses Test on 0.1.1 in the Melty app; then publish on their say-so.

## In-game test 1 (0.1.0, user's PC, via Melty Test)
- Console: xNVSE 6.3.5 (not 6.4.9) and JIP LN 57.30 loaded. Then: "Max script expression length inside
  parenthesis (512 characters) exceeded", "Failed to precompile ... csnv_main.txt", "Error on line 80",
  "Could not extract function script". Line 80 = the inline buy-key lambda (1662 chars in one paren pair).
  Main script never compiled -> no HUD, no buy key.
- Fix (0.1.1): no inline lambdas; each handler is its own UDF file (csnv_onkey, csnv_buy, csnv_onmenu,
  csnv_hudtick, csnv_always) fetched with CompileScript. build.py now fails on >512 chars in parentheses or
  inline lambdas (it reproduces the line-80 error on the 0.1.0 script). All commands checked present in xNVSE 6.3.5.

## In-game test 2 (0.1.1)
- 512-char error gone. New: "Unquoted argument 'PlayerRef' will be treated as string by default",
  "Invalid operands for operator ." -> csnv_hudtick, csnv_main, csnv_onkey, csnv_onmenu failed to precompile.
  xNVSE precompiles user_defined_functions at startup, when editor IDs (PlayerRef) do not resolve.
- Fix (0.1.2): every function sets `ref rP` = GetFormFromMod "FalloutNV.esm" "000014" (the player ref) after its
  declarations and calls through rP; build.py fails if PlayerRef/player. appears in a script.

## Status
- Build: `python3 tools/preflight.py` clean (0 unfilled, 0 broken). `python3 tools/build.py` -> build/CSNV-0.1.0.zip.
- Launcher: `go vet` + `go test` pass (synthetic ESM, CS2 vcfg parsing, plugins.txt, DDS); Linux smoke run OK.
- **Untested in game** (all 49 sheet rows verified=false). Needs a session on the Windows PC.

## Open items
1. Done: JIP LN NVSE 57.30 committed in vendor/ (user supplied the Nexus file).
2. In-game test: user is testing by hand with TESTING.md (checks A-J); waiting on their results.
3. Confirm the vanilla HUD tile names in `sheets/hud_hide.json` (dump the HUD tile tree in game).
4. Confirm the base form IDs (the launcher logs any that aren't WEAP records).
5. Listing: title/tagline/description still to choose. License: MIT (own code/sheets/art; JIP stays GPL-3.0). Remix: allowed. (User asked for a default option.)
6. Real gameplay screenshot from this build.

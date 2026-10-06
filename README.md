# CS2 in the Mojave

A solo Fallout: New Vegas mod that brings your Counter-Strike 2 setup into the Mojave.

- **CS-style HUD.** Health, armor, ammo (clip / reserve) and caps in the corners, the way CS2 shows them.
- **Your CS2 buy key opens a buy menu** anywhere in the world, styled like CS2, paid in caps.
- **3 weapons:** P-18 Sidearm (200 caps), K-47 Rifle (900, full auto), Magnum Longshot (1500).
  They are copies of New Vegas's own 9mm pistol, service rifle and sniper rifle with CS-flavoured stats.
- **Your CS2 crosshair:** colour, size, gap, thickness and dot are read from your CS2 settings.
- **Single player.**

CS2 is never started or touched while it runs: the launcher only reads the settings files CS2 keeps on disk.
Nothing from Valve's or Bethesda's files is shipped.

## Playing
Install it from Melty and press Play. Melty installs xNVSE, and the launcher then:
1. reads your CS2 binds and crosshair (or uses CS2's defaults if CS2 isn't installed),
2. builds `Data/CSNV.esp` from your own `FalloutNV.esm` (the three weapons) and enables it,
3. starts New Vegas through xNVSE.

Load a save or start a new game; the HUD switches over and the buy key works right away.
If something is missing, the game console (`~`) shows lines starting with `CSNV error:`, and the launcher
writes `csnv-launch.log` next to itself.

## How it is made
The design lives in JSON sheets in `sheets/` (weapons, buy menu, buy screen, HUD, CS2 settings, game hooks).
`tools/preflight.py` checks every cell and cross-reference; `tools/build.py` generates everything from them:
- `Data/NVSE/user_defined_functions/csnv/csnv_main.txt`: the main xNVSE script,
- `Data/NVSE/Plugins/scripts/ln_csnv.txt`: JIP LN's script runner runs it on every load,
- `Data/menus/csnv/*.xml`: the HUD and buy-screen layers (JIP `InjectUIXML`),
- `Data/textures/interface/csnv/*.dds`: original art drawn by `tools/make_art.py`,
- `launcher/` (Go): `csnv-launch.exe`.

Build: `python3 tools/preflight.py && python3 tools/build.py` (needs Python 3 and Go; put `jip_nvse.dll` in `vendor/`).
Launcher tests: `cd launcher && go test ./...`.

## Publishing on Melty
- `melty.json` (repository root) is the install recipe Melty reads from this repository: it installs `Data/` into
  the New Vegas folder and `CSNV/` into Melty's own folder, asks Melty for xNVSE, and starts `csnv-launch.exe`.
  It is checked with Melty's `validate_recipe` and `one_click_check` (one click: yes).
- Releases: push a tag like `v0.1.0`. `.github/workflows/release.yml` runs preflight and tests, builds
  `CSNV-0.1.0.zip` with `tools/build.py --release` (which needs `vendor/jip_nvse.dll`), and attaches it to a GitHub release.

## License and remixing
CS2 in the Mojave's own code, sheets and art are MIT-licensed (see `LICENSE`), and remixes are welcome,
on Melty too. The bundled JIP LN NVSE stays under its own GPL-3.0 license.

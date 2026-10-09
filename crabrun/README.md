# Crab Run: Night City

A solo Cyberpunk 2077 mod that turns every load into a **Crab Champions run in Night City**.

- **Fresh start as a run.** Load a save and V drops into a run: weapons stashed, a starter pistol in hand,
  a countdown, then waves of real Night City gangs (Maelstrom, Tyger Claws, Valentinos, Wraiths, Scavengers…).
- **Waves that scale**, with a boss every 5th wave (elite gangers, then MaxTac).
- **Crystals and a crystal shop.** Kills drop Crab Champions crystals. Between waves the world slows and a
  6-card shop opens: **Crab Champions perks** (their real names, descriptions and icons, read from your own
  Crab Champions install), **Cyberpunk cyberware** (Gorilla Arms, Mantis Blades, Sandevistans…) and
  **Cyberpunk weapons**, iconics from wave 5.
- **Island hops.** Every 3 waves V is teleported to the next "island": a different Night City district.
- **Crab Champions sounds and music** from your own install play on pickups, purchases, wave starts, portals.
- **Crab-style HUD**: island, wave, timer, crystals with the Crab crystal icon, and your perks with stacks.
- **Run seeds.** Every run has a 6-character seed. Share it: the same seed gives the same islands, waves and
  shop rolls. Press F7 to type a friend's seed.
- **Death ends the run, not your save**: V is healed, sent back to where the run started, and your own gear is
  re-equipped. F9 ends a run early, F8 starts a new one.

You need **Cyberpunk 2077** and **Crab Champions** installed. Nothing from either game ships with Crab Run.

## Keys
| Key | When | Does |
|---|---|---|
| 1–6 | shop | buy that card |
| R | shop | reroll the cards (costs crystals) |
| Enter | shop | continue to the next wave (the shop also closes by itself) |
| F7 | countdown / after a run | type a seed (A–Z, 2–9, Backspace, Enter) |
| F8 | after a run | new run with a random seed |
| F9 | during a run | end the run |

## How it works
- `mod/` is a Cyber Engine Tweaks Lua mod (Melty installs CET). It runs the waves, shop, perks and HUD.
- `bridge/` is `CrabRunBridge.exe`, which Melty starts instead of the game. It reads Crab Champions' `.pak`
  files (Unreal Engine 4.27) from the player's install with CUE4Parse: each perk's `DA_Perk_*` data asset
  (name, description, icon), the crystal icon and the run sounds. It writes them beside the CET mod
  (`crab/`), starts Cyberpunk 2077, then plays the Crab sounds the mod asks for and relays the keys above
  (CET's Lua may only touch files inside its own folder, so the two meet in `io/`).
- The design lives in JSON sheets in `sheets/`: enemies, waves, islands, shop weapons and cyberware,
  Crab perks, Crab sounds and art, shop layout, keys, rules, and every game hook. `tools/preflight.py`
  checks every cell and cross-reference; `tools/build.py` generates `mod/data.lua` and
  `bridge/SheetData.g.cs` from them and, with `--release`, the release zip.

## Building and testing
```
python3 tools/preflight.py && python3 tools/build.py --release   # needs Python 3 and the .NET 10 SDK
cd tests && luajit test_run.lua && luajit test_cet.lua            # run logic + CET wiring with a simulated game
cd tests/bridge && dotnet run -c Release -- fixtures              # pak reading, sounds, file channel
```
Logs on the player's PC: `.../cyber_engine_tweaks/mods/CrabRun/crabrun.log` and `bridge.log`; what was
found in Crab Champions is in `crab/crab_data.json` and `crab/assets.txt`.

## License
Crab Run's own code, sheets and docs are MIT-licensed (`LICENSE`); remixes are welcome. Bundled libraries
keep their own licenses (`THIRD-PARTY-NOTICES.md`).

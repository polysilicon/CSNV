# CS2 in the Mojave: mod log

Solo Fallout: New Vegas mod with a Counter-Strike 2-style layer. CS2 is inspiration only: nothing loads
into CS2, and no Valve files are used.

## Status
- Design sheets in `sheets/` are the source of truth. Run `python3 tools/preflight.py` before every build.
- Nothing is built or tested in game yet. Melty read-up (game_info, search_mashups) is still pending:
  this cloud session cannot reach melty.gg.
- In-game testing and capture will run from a session on the player's Windows PC.

## Route (proposed, not yet built)
- Loader: xNVSE only (Melty installs it). Anything else must be bundled and shareable.
- Plugin (.esp) with a quest script: hotkey poll, buy menu, caps checks, AddItem.
- Weapons: new records reusing vanilla New Vegas models, with CS-style names and stats.
- HUD: route still open (see `hooks.hud_overlay`).

## Open items (from preflight)
- `hooks.weapon_ammo`: an in-clip ammo call that works with xNVSE alone.
- `hooks.hud_overlay`: how to draw the HUD without a hand-installed dependency.
- Weapon stats: take them from the vanilla base weapons, then tune.
- `hud.hud_armor.art`: an original armor icon.

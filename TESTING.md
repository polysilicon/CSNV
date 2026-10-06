# Testing CS2 in the Mojave by hand

This is a hand install for testing only. Once it is on Melty, players just press Play.
Use a test save: the buy test adds caps with the console.

## Set up (about 10 minutes)
1. **Back up your saves.** Copy `Documents\My Games\FalloutNV\Saves` somewhere safe.
2. **xNVSE 6.4.9.** If your New Vegas folder has no `nvse_loader.exe`, download `xNVSE 6.4.9` from
   https://github.com/xNVSE/NVSE/releases/tag/6.4.9 (the .7z or .zip under "Assets") and extract everything
   into the New Vegas folder (the one with `FalloutNV.exe`; in Steam: right-click Fallout: New Vegas >
   Manage > Browse local files).
3. **This mod.** Extract the `CSNV-<version>.zip` you were given into the New Vegas folder. It merges into `Data\` (JIP LN NVSE 57.30 is included) and adds a `CSNV\` folder.
4. **Start it.** Double-click `<New Vegas>\CSNV\csnv-launch.exe`. If Windows shows "Windows protected your PC",
   click **More info > Run anyway** (the launcher isn't code-signed yet). New Vegas starts through xNVSE.

## Checks (reply with each letter: OK, or what you saw)
- **A. Launcher log.** Open `<New Vegas>\CSNV\csnv-launch.log` and paste its contents to me.
- **B. Console.** Load your test save, press `~`, and look for `CS2 in the Mojave: ready.` or any line starting
  `CSNV error:`. Paste those lines.
- **C. HUD.** Bottom-left: `+ <health>`, a shield icon with your armor (DT) number and `$ <caps>`. Bottom-right: `clip / reserve`.
  Are the vanilla health bar and ammo counter hidden, or still showing?
- **D. Crosshair.** Does it look like your CS2 crosshair (colour, size, gap, dot)?
- **E. Buy menu.** Press your CS2 buy key (B unless you changed it in CS2). A dark CS2-style panel with BUY MENU
  and the price list should appear, with the game's buttons for the three weapons and Cancel.
- **F. Caps.** In the console, type `player.additem f 3000` and press Enter, then close the console.
- **G. Buying.** Buy each weapon. It should go into your hands with starter ammo, under its name
  (P-18 Sidearm, K-47 Rifle, Magnum Longshot). Does the K-47 fire full auto?
- **H. Too poor.** With fewer caps than the price (drop them, or buy until you run out), buying should say "Not enough caps".
- **I. Save and reload.** Save, quit to the main menu, and load that save. Are the weapons still there? Do the HUD and buy key still work?
- **J. Screenshots.** Take two (Steam's F12 key): one in the world showing the HUD, the crosshair and a bought weapon,
  and one with the buy menu open. Send them to me. One may become the Melty cover image.

If the game crashes or won't start, tell me the step, and send `csnv-launch.log` and
`<New Vegas>\nvse.log` / `<New Vegas>\Data\NVSE\nvse.log` if they exist.

## Undo
Delete `<New Vegas>\CSNV\`, `Data\CSNV.esp`, `Data\NVSE\user_defined_functions\csnv\`,
`Data\NVSE\Plugins\scripts\ln_csnv.txt`, `Data\menus\csnv\`, `Data\textures\interface\csnv\`,
`Data\config\csnv_cs2.ini`, and remove the `CSNV.esp` line from `%LOCALAPPDATA%\FalloutNV\plugins.txt`.

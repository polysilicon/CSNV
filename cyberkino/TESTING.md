# Testing Cyberpunk Kino

## 1. Place the arena once (about 10 minutes)
The arena needs a fixed layout on V's floor of Megabuilding H10. Load a save, go to V's apartment and open the CET
overlay (its key, usually ~ or Insert): a window "Cyberpunk Kino layout" appears. Every click is saved at once,
and a preview prop appears where each thing goes.

1. Stand where a match should start (inside V's apartment) and click **Match start**.
2. **V's stash**: look straight at the stash and click the stash button.
3. **Zone 1** (zone counter at 1): place 2 wall-buys (face a wall, pick the gun with < >, click), one or two
   Mystery Box spots, and 2-3 zombie spawns at the far ends of zone 1 (doorways, windows, where zombies should come from).
4. **Barricades** for zone 1: stand on the zone 1 side of each doorway or corridor that leads further, facing out,
   and click **Barricade** (it goes 1.5 m in front of you). Every opening out of zone 1 needs one.
5. Press **+** for zone 2: its wall-buys, box spots and spawns, then its barricades into zone 3. And so on.
6. **Undo last** removes the last thing placed. Close the overlay when done.

The creator's layout from 2026-10-11 is built into 0.3.1, so this part is already done; it's here for changing it.
Then send me `bin\\x64\\plugins\\cyber_engine_tweaks\\mods\\cyberkino\\layout.json`: I build it into the mod so
every player gets your map.

## 2. Play
Press **F7**. Check, and tell me what you saw:
- **A.** V is teleported into the apartment; "ROUND 1" and points top-left; you hold only a Unity; your weapons are
  in V's stash and your cyberware is off.
- **B.** You can't walk past a closed barricade; "[F] Clear the barricade" clears only that one, and the others stay.
- **C.** The wall-buys and box are where you placed them; the box moves after 4 uses.
- **D.** Zombies come from your spawn points (only from open zones); a cyberpsycho on round 5.
- **E.** Chips drop each round; [F] installs cyberware (Z for Sandevistan).
- **F.** F7 again: your weapons come back from the stash and your cyberware goes back on.

Press F12 for screenshots in a match (one with the Ray Gun if you get it), and send `cyberkino.log` from the same folder.

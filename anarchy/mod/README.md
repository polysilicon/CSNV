# Crispy Anarchy mod

A small server-side Fabric mod (26.2) for CrispyAnarchy: chest-menu shops for the market's Ripperdoc (`crispy_cyberware`)
and Enchanter (`crispy_enchants`). Players need no mods.

```
bash build.sh <lib-dir> <javac-25>     # -> crispy-anarchy-1.0.0.jar, goes in the server's mods/
```

- Right-clicking a vendor's interaction box (tags `cy.doc` / `ce.enchanter`) opens its chest menu instead of the
  datapack's dialog (`AnarchyMod`, `UseEntityCallback`).
- **Ripperdoc** (`Shops.ripperdoc`): every implant and the Neuroblocker with its icon, slot, capacity, effect, price and how many
  diamonds / netherite you have; installed ones glow, a taken slot or going over the capacity limit is flagged.
  "Remove an implant…" lists your body slots; the capacity button prints your full status.
- **Enchanter** (`Shops.enchanter`): each book tier with its price and how much XP you have, and the Heroic upgrade.
- What's for sale comes from the datapacks (storage `cyber:shop` and `crispy_enchants:shop`, written on load). A click
  sets the datapack's buy score and runs its buy function as the player, so the datapack still checks you're within
  8 blocks of the vendor, takes the price and gives the item; the menu then redraws.
- The datapacks keep their dialogs and `/trigger` buy scores for servers without this mod (PvP, Skyblock).

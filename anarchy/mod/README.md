# Crispy Anarchy mod

A small server-side Fabric mod (26.2) for CrispyAnarchy: clans (below), and chest-menu shops for the market's Ripperdoc (`crispy_cyberware`)
and Enchanter (`crispy_enchants`). Players need no mods.

```
bash build.sh <lib-dir> <javac-25> <placeholder-api.jar>   # -> crispy-anarchy-1.1.0.jar, goes in the server's mods/
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

## Clans (1.1.0, `Clans.java`)

The old Bukkit "Clans" plugin's idea, rebuilt: a clan name shown as a tag in chat, a private clan chat, kills and a top
list. **No land claiming and no bases.**

- `/clan create <name>` (2-10 letters/numbers), `invite`, `accept`/`deny` (clickable), `leave`, `kick`, `promote`/`demote`
  (officers), `transfer`, `disband` (confirm), `info [clan]`, `list`, `top` (kills), `color <colour>`, `pvp on|off`
  (friendly fire, off by default), `/clan chat` (toggle) and `/cc <message>`. Ops: `/clan spy`.
- **Clan chat never reaches public chat, the log or Discord**: toggled chat is stopped in Fabric's `ALLOW_CHAT_MESSAGE`
  (before the server logs or broadcasts it); `/cc` sends straight to the members.
- **The tag in chat**: placeholder `%crispy:clan%` (`[Name] ` in the clan colour, hover for info, click for `/clan info`),
  in `config/styled-chat.json`: `"chat": "<%crispy:clan%%crispy:tag%%crispy:name%> ${message}"` (backup of the old
  format: `styled-chat.json.bak-clans`). Only Anarchy has the clan tag; cross-chat and Discord show the cosmetic tag.
- **Kills**: killing a player outside your clan adds one to your clan's kills.
- **Data**: `config/crispy_clans.json`. On 2026-11-08 it was seeded from the old plugin's `plugins/Clans/*.yml` (24 clans,
  52 members, names from `usercache.json`, kills kept; owners kept, no officers). The old base locations were not
  carried over (no bases).

# Black Market (Anarchy)

**The Black Market Dealer**: a shop villager in the market (`crispy:market`, -102.5 95 -68.5, on the street outside
the bank's east door) that only trades with players **wearing** the rare **[Black Market]** tag (lobby tag
`blackmarket`). The gate is the chat-tags mod's (`needtag.blackmarket`): anyone not wearing it gets the one-line
"needs [Black Market] equipped" message, with a click to equip it once they've earned it.

**Earning the tag**: find the hidden dealer. Crouching for 4 seconds in the current hidden spot somewhere in the market
(one of eight covered corners in or beside shop buildings, listed in `gen_bm.py`; it moves to a different one after every find) makes a hooded "???" appear for 5 seconds, whisper,
hand over one random item (`loot_table/black_market`) and grant the hidden advancement `anarchy:black_market`,
which the lobby turns into the tag. Once per player.

Built so cheats can't find it: no block, sign, chest or entity marks the spot (nothing for x-ray or entity ESP),
the dealer only exists for the 5 seconds after someone triggers it, and the advancement is hidden with a vague
description. The location is only in the server's datapack files, so keep this repository private.

Dealer trades (Gold Coins, the market currency), all written by `gen_items.py` (`python3 gen_items.py`, then upload
and `/function og:place`):

| Contraband | Gets you | Price |
|---|---|---|
| Phase Shard ×8 | right-click: blink up to 10 blocks where you look (stops at walls), 4 s | 6 |
| Jump Jet ×8 | right-click: launched high into the air, Slow Falling 5 s, 6 s | 4 |
| Smoke Bomb ×4 | right-click: Blindness + Slowness 4 s on everyone within 6; you get Invisibility + Speed II 6 s, 20 s | 6 |
| Tesla Coil ×4 | right-click: 6 damage + Slowness II 3 s to everything within 5, 15 s | 8 |
| Gravity Bomb ×4 | right-click: everything within 6 levitates 3 s, then falls, 20 s | 8 |
| Snare Dart ×8 | right-click: dart at the first target in 24 blocks: 3 damage, Slowness IV 3 s, Glowing 8 s, 8 s | 6 |
| Stim Shot ×4 | right-click: Instant Health II, Regeneration II 6 s, Absorption 30 s, 30 s | 6 |
| Growth Potion ×2 | drink: 2x size, +4 hearts, +1.5 reach, 3 min | 6 |
| Shrink Potion ×2 | drink: 0.35x size (fits through 1-block gaps, hard to hit), 3 min | 6 |
| Contraband Blade / Pickaxe | netherite, Sharpness V Looting III / Efficiency V Fortune III | 48 |
| Contraband Wings, Stash, Mending book, enchanted golden apple, totem | | 32, 10, 16, 12, 8 |

Ability items work like Multiverse's (right-click, the client shows the cooldown), but each use spends one charge
from the stack. They're clay balls with an item model, a near-instant `consumable` and a `use_cooldown`; using one
fires its `consume_item` advancement (`og:item/<key>`, matched on `custom_data {bm:"<key>"}`) whose reward runs
`og:item/use_<key>` as the player. They hit every living thing except the user and shopkeepers (`#og:not_target`).
The size potions add attribute modifier `og:size` (one replaces the other); `og:item/second` (once a second) ends it
after 3 minutes or on death. The hidden dealer's random item can now also be Phase Shards, Stim Shots, Gravity Bombs or
a size potion. Ops: `/function og:give_all` gives one of each (needs 9 free slots).

- Install: `datapack/` as `world/datapacks/crispy_og`, `/reload` (og:load starts the once-a-second check), then
  `/function og:place` for the dealer.
- The market's own `spawn_shops`/reinstall kills every `crispy_shop` villager, so run `/function og:place` again after.
- `/function og:remove` takes the dealer away. To test: `/advancement revoke <player> only anarchy:black_market`.

**Smuggler's Map** (`mapart/`): a locked map (id 90001, `world/data/minecraft/maps/90001.dat`, dimension
`crispy:market`) showing the whole market from above (4 blocks a pixel, centred on 0, -15) with a red dot at each
of the eight spots. `render.py` reads the market's top blocks from its region files, `compose.py` turns them into map
colours (the palette is MapColor's, taken from the server jar) and draws the dots. Hand it out with
`give <player> minecraft:filled_map[minecraft:map_id=90001,...]` (see the item name and lore used in chat history).
If the spots change, re-run compose.py with the new list and upload 90001.dat again.

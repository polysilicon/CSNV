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
| Swap Orb ×4 | right-click: trade places with the player or mob you aim at (24 blocks), 12 s | 8 |
| Chrono Clock ×4 | right-click: rewind to where you stood 5 s ago (same dimension), 25 s | 8 |
| Frost Nova ×4 | right-click: 3 freeze damage, Slowness V + Mining Fatigue III 4 s within 6, 18 s | 6 |
| Blood Siphon ×4 | right-click: 4 damage to everything within 5; heals you, more if 3+ hit, 20 s | 8 |
| Growth Potion ×2 | drink: 2x size, +4 hearts, +1.5 reach | 6 |
| Shrink Potion ×2 | drink: 0.35x size (fits through 1-block gaps, hard to hit) | 6 |
| Moon Juice ×2 | drink: low gravity, huge floaty jumps, no fall damage | 6 |
| Swiftfoot Tonic ×2 | drink: +40% speed, walk straight up 1-block steps | 6 |

Brews last 3 minutes, one at a time (a new one replaces the old). No generic items: everything sold, and the hidden
dealer's once-per-player gift (`loot_table/black_market`, one random stack), is Black Market contraband.
An ability with nothing to do (Swap Orb with no target, Chrono Clock before 5 s of history) gives its charge back.

Ability items work like Multiverse's (right-click, the client shows the cooldown), but each use spends one charge
from the stack. They're clay balls with an item model, a near-instant `consumable` and a `use_cooldown`; using one
fires its `consume_item` advancement (`og:item/<key>`, matched on `custom_data {bm:"<key>"}`) whose reward runs
`og:item/use_<key>` as the player. They hit every living thing except the user and shopkeepers (`#og:not_target`).
The brews add attribute modifier `og:size`; `og:item/second` (once a second) ends it after 3 minutes or on death, and
keeps each player's last 5 positions for the Chrono Clock (reset on death or changing dimension). Ops: `/function og:give_all` gives one of each (needs 9 free slots).

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

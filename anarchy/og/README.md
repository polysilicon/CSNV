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

Dealer trades (Gold Coins, the market currency): Contraband Blade (netherite sword, Sharpness V, Looting III) 48,
Contraband Pickaxe (Efficiency V, Fortune III) 48, Contraband Wings (elytra) 32, Mending book 16, enchanted golden
apple 12, totem 8, Contraband Stash (shulker box) 10, 64 rockets 4.

- Install: `datapack/` as `world/datapacks/crispy_og`, `/reload` (og:load starts the once-a-second check), then
  `/function og:place` for the dealer.
- The market's own `spawn_shops`/reinstall kills every `crispy_shop` villager, so run `/function og:place` again after.
- `/function og:remove` takes the dealer away. To test: `/advancement revoke <player> only anarchy:black_market`.

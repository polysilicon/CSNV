# Market decorations locked (2026-11-14)

A player reported that items could be taken from the market's item frames and armor stands (adventure mode doesn't
stop that). Added to the live `crispy_market` datapack (not otherwise in this repo):

- `data/crispy/tags/entity_type/market_props.json`: item_frame, glow_item_frame, armor_stand
- `function/market/lock_props.mcfunction`, called at the end of `function/second.mcfunction` (backup
  `second.mcfunction.bak-lock`): every second, each prop in loaded market chunks without the `crispy_locked` tag goes
  through `market/lock_one`:
  - armor stands: `{Invulnerable:1b,DisabledSlots:4144959}` (no taking, adding or swapping gear)
  - frames: `{Fixed:1b,Invulnerable:1b}` (no taking or rotating the item, can't be broken)
  then get the tag. New props placed later are locked within a second of being loaded.

At the time: 26 frames (all still holding their items) and 5 stands (all with head, netherite boots and leggings and
an elytra) were locked.

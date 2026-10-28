# Crispy Skyblock

Skyblock on `Falling01` (Fabric 26.2, Velocity name `skyblock`, was `falling`). It replaced Crispy Falling on
2026-10-28 with a fresh world. The old world is kept on the instance as `world_falling_backup`; `gen.py` is its retired
`crispy_falling` datapack.

- `skyblock.py <outdir>` builds the `crispy_skyblock` datapack (install as `world/datapacks/crispy_skyblock`, or upload
  it zipped). Its dimension files make the overworld and the Nether void, so a new world must be created with the pack
  already in `world/datapacks`.
- `mod/` is the `crispy_skyblock` server mod (`crispy-skyblock-2.0.0.jar`, build with
  `mod/build.sh <lib-dir> <javac>`, same lib dir as `pvp/spawnmod` plus Fabric API's `fabric-events-interaction-v0`
  unpacked into `fa/META-INF/jars/`). Now `crispy-skyblock-2.2.2.jar`.

## How it plays

- **Starter islands.** The first time a player goes to their island they pick one of seven from a chest menu. Each has
  its own chest, and the whole 128x128 plot gets the island's biome:

  | Island | Biome | Notes |
  |---|---|---|
  | Classic | plains | the original L of dirt, one oak, chest with lava, ice, cactus, sugar cane, melon, pumpkin seeds |
  | Desert Oasis | desert | sand and sandstone, cactus, a two-block oasis; no rain, dirt only from the chest |
  | Jungle | jungle | tall jungle tree with cocoa, bamboo, a melon |
  | Frozen Peak | snowy taiga | spruce, snow, a frozen pond, sweet berries |
  | Mushroom Isle | mushroom fields | giant mushroom, a penned mooshroom; no hostile spawns |
  | Shrek's Swamp | swamp | mud, lily-pad pond, vines, an outhouse; slimes at night |
  | Tegridy Farms | plains | ripe wheat, carrot and potato rows, a barn and a scarecrow |

- **Hub** (rebuilt in hub v2, `crispy_skyblock:hub`, run once when `#hubv cs_cfg` is below 2): a natural floating island
  about 80 blocks across: grassy hills, trees (oak, birch, cherry), flowers, a pond, a deep rocky underside, and a
  stone plaza with a fountain. Merchants stand in five market stalls around the plaza; spawn is just south of the
  fountain facing the portal home. Light blocks keep monsters away and any that appear are removed. The hub area is
  |x|,|z| <= 50 (adventure mode).
- **Hub portals.** Every island has a portal frame (crying obsidian on a reinforced deepslate and obsidian platform)
  14 blocks north of its centre, out over the void, so players bridge to it; walking through takes you to the hub. The
  hub's portal (north of the plaza) takes you to your island. The blocks are blast-proof and immovable, and the mod
  (`Portals`) stops players breaking them. Islands made before portals get theirs the next time a member is there.
- **Sky events** while a member is online (by island play time): an animal every 15 min, a supply crate (barrel with
  the `chests/supply` loot table) every 25 min, a meteor of ores every 45 min, dungeons at 30, 90 and 180 min, and an
  End portal at 150 min. They all land within 6 blocks of the island centre.
- **Nether.** Each island has its own 64x64 void Nether plot under island/8 with a small netherrack starter island.
  A fortress wreck with a blaze spawner lands after 2 min there (another at 20, a wither skeleton one at 60), and
  bastion chunks at 10 and 40 min.
- **Challenges** (`/island challenges` or `/challenges`): 26 one-time hand-ins (Easy, Medium, Hard, and three that need
  an island level) for resources, spawn eggs and XP. Finished ones show crossed out.
- **Island level** (`/island level`): the mod counts every block in the plot (1 point each; iron, gold, diamond,
  emerald, netherite blocks, beacons and the like more; fluids, plants, bedrock, spawners and portal frames nothing);
  100 points = 1 level. Once a minute per island on demand, and every 5 minutes for islands with someone online. It
  sets `cs_lvl` for the island and its members, keeps results in storage `crispy_skyblock:levels`, and rewrites the
  Top Islands board in the hub (the text display tagged `cs_top`). `/island top` lists the top 10. Islands nobody belongs to any more are left off, and the board refreshes when someone starts a new island.
- **Menu.** Esc → Island Menu (a dialog): go home, challenges, level, top, invite, accept, info, hub, how to play, start
  a new island (wipes inventory, ender chest and XP; then the island picker opens; once per 10 min).

## Economy and minions (2.1.0)

Hypixel-style, vanilla only. Prices, shop categories, minion types and tiers are defined in `skyblock.py` (`SHOP`,
`MINIONS`, `TIERS`) and loaded into storage `crispy_skyblock:eco cfg`, which the mod reads.

- **Coins** are the `cs_coins` score. `/coins` (`/bal`, `/purse`), `/coins top`, `/pay <player> <amount>`;
  staff: `/coins give <player> <amount>` (negative takes).
- **Merchants**: five villagers in the hub (tagged `cs_npc` + `cs_shop_<category>`, respawned by `crispy_skyblock:npcs`
  5 s after every load, once the hub's entities are in): Farm Merchant, Mine Merchant, Lumber Merchant, Monster Hunter, Builder. Clicking one opens that
  category of the shop (tabs switch categories). Left-click buys 1, shift-left a stack; right-click sells 1,
  shift-right sells all of that item; **Sell everything** sells every sellable item. Only plain items are traded.
- **Minions**: 23 types (ores, crops, logs, mob drops). Craft Tier I with 8 of the resource around a wooden pickaxe
  (datapack recipes; the result is an armor stand item with `custom_data {cs_minion:{type,tier}}` and the resource's
  model). Place it on your own island: a small dyed armor stand with the resource as its head and a tool in hand.
  It does one action per tier interval (30/25/20/15/10 s), storing up to 64/128/192/256/384 items, on real time, so it
  keeps going while you're offline until it's full. Right-click (island members or staff): collect all, upgrade
  (coins + the recipe item: 500+64, 2,000+160, 8,000+320, 25,000+640), or pick it up. Each island gets 5 minions,
  +1 per 20 island levels, up to 15. Records: storage `crispy_skyblock:minions`.
- **Sidebar**: every player gets a SKYBLOCK sidebar (sent as packets only to them): location, purse, island level and
  minions.

## Mod commands

`/island` (alias `/is`) opens the Island Menu; `/island choose|challenges|level|top`; `/invite <player>` (also
`/island invite <player>`). Menus are chest GUIs defined by the datapack in storage `crispy_skyblock:menus` (set on
every load); an entry with `done:"<objective>"` shows its `item_done` once the viewer's score there is 1 or more.

# Crispy Skyblock

Skyblock on `Falling01` (Fabric 26.2, Velocity name `falling`, shown as **Skyblock**). It replaced Crispy Falling on
2026-10-28 with a fresh world. The old world is kept on the instance as `world_falling_backup`; `gen.py` is its retired
`crispy_falling` datapack.

- `skyblock.py <outdir>` builds the `crispy_skyblock` datapack (install as `world/datapacks/crispy_skyblock`, or upload
  it zipped). Its dimension files make the overworld and the Nether void, so a new world must be created with the pack
  already in `world/datapacks`.
- `mod/` is the `crispy_skyblock` server mod (`crispy-skyblock-2.0.0.jar`, build with
  `mod/build.sh <lib-dir> <javac>`, same lib dir as `pvp/spawnmod`).

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
  Top Islands board in the hub (the text display tagged `cs_top`). `/island top` lists the top 10.
- **Menu.** Esc → Island Menu (a dialog): go home, challenges, level, top, invite, accept, info, hub, how to play, start
  a new island (wipes inventory, ender chest and XP; then the island picker opens; once per 10 min).

## Mod commands

`/island` (alias `/is`) opens the Island Menu; `/island choose|challenges|level|top`; `/invite <player>` (also
`/island invite <player>`). Menus are chest GUIs defined by the datapack in storage `crispy_skyblock:menus` (set on
every load); an entry with `done:"<objective>"` shows its `item_done` once the viewer's score there is 1 or more.

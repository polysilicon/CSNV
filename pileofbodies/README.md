# Pile of Bodies (CrispyAnarchy remake), Minecraft 26.2

A remake of SethBling's 2013 survival map: survive on a heap of giant player statues in the void. This version has 16
bodies: 8 well-known skins (SethBling as a tribute, Notch, jeb_, Dinnerbone, CaptainSparklez, Grian, MumboJumbo, Dream)
and 8 from CrispyAnarchy (lbxd, 3951, wumpty73, alexrmc, samonthebus, Petrex82, M_cosine, aionimas).

## What's in the world
- **Statues:** each is the player model at 2 blocks per skin pixel, about 64 blocks tall, with the outer layers (hats,
  jackets, sleeves) as a one-block shell.
- **Surfaces:** every pixel becomes the closest *survival* block. That gives wood (logs, planks), stone, dirt, gravel,
  sand, clay, terracotta, wool, pumpkins and melons (seeds), mushroom blocks, hay, ice (water) and persistent leaves
  (saplings). Strong colours use wool.
- **Insides:** stone, andesite, tuff and gravel, with ore clusters (coal, iron, copper, redstone, lapis, gold, diamond,
  emerald) and the odd lava pocket.
- **The heap:** bodies drop one at a time onto the growing pile in random lying poses. It's about 118×126 blocks across,
  from y 64 to 171. The world is void (flat, one air layer, plains biome), so mobs spawn on the pile; the Nether and
  End generate normally.
- **End portal:** void worlds have no strongholds, so SethBling's torso hides a room with 12 empty End portal frames.
- **Extras:** a name sign on every head; spawn on the summit with a starter chest (2 saplings, 4 seeds, 2 sugar cane,
  4 bone meal, a water bucket, 8 torches and a book with goals).

## Rebuild
1. Get the skins: PNGs plus `index.json` (`{name: {"slim": bool}}`) from the Mojang API.
2. Generate the builder datapack: `python3 build.py <skins dir> <out>/pob` (seeded, so it's reproducible).
3. Start a vanilla 26.2 server with:
   - `level-type=minecraft:flat`
   - `generator-settings={"layers":[{"block":"minecraft:air","height":1}],"biome":"minecraft:plains","features":false,"lakes":false}`
   - `generate-structures=false`

   Put the pack in `world/datapacks/`, then run each line of `pob:build` over RCON or the console. The whole function
   at once goes over the 65,536-command limit.
4. Stop the server and remove `datapacks/pob`. The world in `world/` is the map.

Change the pile shape with `SPREAD0`, `SPREAD_PER`, `SETTLE` and `CENTRE_PULL` at the top of `build.py`.

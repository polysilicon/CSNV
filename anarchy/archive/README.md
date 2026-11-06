# Archived worlds on Anarchy

`datapack/` (installed as `world/datapacks/crispy_archive`) adds old worlds as dimensions you can visit:

- `crispy:themarket`: a copy of the `themarket` world folder (region, entities, poi copied into
  `world/dimensions/crispy/themarket`; the original folder is untouched). Same empty-void generator as
  `crispy:market`, so nothing new generates past the old map. Ops: `/function crispy:themarket` (to its old spawn,
  -32 128 144) and `/function crispy:themarket_back`. Not an Essential Commands warp, since those are open to every
  player on Anarchy.

The dimension loads on server start (datapack dimensions can't be added with /reload).

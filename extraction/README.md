# Extraction Zone (instance Extraction01)

Extraction-shooter mode replacing Factions. Fabric 26.2, AMP instance `Extraction01` (AMP port 8087, game 127.0.0.1:25574,
SFTP 2230, 4 GB, sleep mode off), Velocity server `extraction`. **Private until launch:** whitelist on (lbxd only),
not in the lobby selector, the proxy's `try` list or TAB. Factions01 keeps running until launch; its backup is
`/AMPStorage/backups/Factions01-20261112.tgz` (world, nether, end, all plugins and their data).

`python3 build.py <out>` writes the `crispy_extraction` datapack (zip it into `world/datapacks/`). One-time setup by
an op or the console: `/function ez:admin/build_camp`, then `/function ez:admin/setup` (places extraction and
insertion markers, crates and raider spawners; waits 20 s for the terrain to generate).

## How it plays
- **Camp** (dimension `ez:camp`, a void world; world spawn is here): nobody can deal or take damage. Stash = vanilla
  ender chests (27 slots, per player). Quartermaster sells ammo, bandages, medkits, guns (20–128 credits) and iron
  armour; the Fence buys valuables for credits. The deploy pad (interaction `ez.deploy`) sends you into the zone.
- **Zone** (overworld box x -1050..-250, z 30..830): POIs Old Town (village, tier 2), Raider Outpost (pillager
  outpost, tier 3), Portal Ruins (2), Crash Site, Lumber Camp, Radio Hill (1). Barrel crates (`ez.crate`) refill every
  10 min while loaded and nobody is within 20 blocks. Raider spawners top their POI up to a cap every 20 s while a
  raider is within 80 blocks (Infected zombies, Bandit pillagers, Raider vindicators, each with its own drops).
- **Raid**: 25 min timer on the action bar with the nearest extraction point. Outside the zone: radiation damage. Hold
  an extraction point (flare column, radius 4) for 30 s; everyone in the zone is told someone's extracting there.
  Death (or the timer) = you drop everything (keep_inventory off) and respawn in camp.
- **Guns**: Multiverse's gun abilities (`pvp/abilities.py`, namespace `pvp`), renamed to neutral names; every shot
  needs one Ammo (`ez.ammo` in custom_data) from your inventory.
- **Squads**: `/trigger truce` next to a raider offers a truce; they `/trigger truce` within 30 s to squad up (team
  `ez_sq<N>`, green names, friendly fire stays on). Hitting a squadmate is a betrayal: announced, attacker leaves.
- **First join**: pistol, 24 ammo, 2 bandages, 10 credits.
- **Relief kit** (mod `Relief`, 1.0.8): after a death the datapack runs `/ezkit`; a player with no gun and under 20
  credits, counting their inventory and every container on their stash plot, gets `ez:kit/give` (pistol, 24 ammo,
  3 bandages, 8 cooked beef; no credits). At most once every 10 minutes per player. Players can ask with `/kit` in camp.
- **Enemies look like soldiers**: Bandit Gunner, Raider and Raider Rifleman are skeletons in a modern-soldier player
  head (minecraft-heads.com textures) and dyed leather with an armour trim (desert/dune, camo/wild, black/silence),
  Silent, nothing drops. Infected stay zombies.

## 1.1.0 (2026-11-12)

Mod `crispy-extraction-1.1.0`, datapack and `shops.json` together.

- **Gold Coins** (`Coins.java`): the money is Anarchy's Gold Coin item; 64 condense into a Coin Bag. `count/take/give` handle
  bags (change is automatic, payouts come as bags + coins). Trader menus: "Condense coins into bags" (slot 47) and
  "Break a Coin Bag" (51). Old Credits (gold nuggets) in inventories become coins.
- **Contracts** (`Contracts.java`): The Fixer (`ez:admin/contracts_npc`, by the helipad) or `/contracts`. Three offers
  per player: RECOVER an Intel Cache (barrel on a street in a district, Contract Tracker compass), ELIMINATE N of a type,
  EXFIL from a named point, BOSS (within 48 blocks of the Commander's death). Pays on extraction; dying fails it.
- **The Commander** (`Boss.java`, `ez:boss/spawn`): 260 HP, armour, M60 hitscan (`GUNNERS["boss"]`), three Riflemen; at
  the city centre 4 min after start then 20 min after each death, while raiders are in. Boss bar within 64 blocks. Loot
  table `ez:mob/boss`.
- **Events** (`Events.java`): every 6-9 min with raiders in: supply drop (`ez:event/supply`, red flare, 8 min), helicopter
  crash (wreck + 2 `ez:event/heli` crates + 3 Riflemen, 12 min), hot extract (marker `ez.exfil ez.hot`, 3 min, valuables
  pay double). Placed blocks only replace air and are restored after.
- **Stash upgrades** (`Plots.PERKS`, Plot Manager): Gun Workbench 300 (`Workbench.java`: Extended Magazine +50% and
  Quick Reload -35%, 40 coins each, written as `custom_data {ezmod:{mag:1b,rl:1b}}` and read by the datapack's magazine
  code via `ez.cap`), Medical Station 200 (bandages/medkits 40% off), Field Radio 250 (exact spot of the first event each
  raid).
- **Raid recap** (`Raid.java`, `/ezhook deploy|extract|died` from the datapack): time, distance, kills by type, loot
  value (valuables at Fence prices + coins carried), hot-extract bonus, contract result. Standout runs (250+ coins, 8+
  kills, the Commander, or a big hot extract) are broadcast and logged as `<name> has completed the challenge [...]`,
  which the Discord bot posts once Extraction is in its bridge list.
- **Weekly reset** (`Reset.java`): on the first start of a new ISO week (UTC) the Lost Cities dimension is moved to
  `old_city/last` before the worlds load; setup and the map redraw run 10 s after start. AMP restarts the instance every
  Monday 07:00 UTC (schedule trigger "Weekly city reset"). `/ezadmin reset` forces it on the next start.
- **Radiation edge**: green haze wall along the border within 28 blocks, Geiger clicks within 12, a one-time warning;
  the zone map draws the border in red.

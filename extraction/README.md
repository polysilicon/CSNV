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

# Crispy Skyblock

Skyblock on `Falling01` (Fabric 26.2, Velocity name `skyblock`, was `falling`). It replaced Crispy Falling on
2026-10-28 with a fresh world. The old world is kept on the instance as `world_falling_backup`; `gen.py` is its retired
`crispy_falling` datapack.

- `skyblock.py <outdir>` builds the `crispy_skyblock` datapack (install as `world/datapacks/crispy_skyblock`, or upload
  it zipped). Its dimension files make the overworld and the Nether void, so a new world must be created with the pack
  already in `world/datapacks`.
- `mod/` is the `crispy_skyblock` server mod (`crispy-skyblock-2.0.0.jar`, build with
  `mod/build.sh <lib-dir> <javac>`, same lib dir as `pvp/spawnmod` plus Fabric API's `fabric-events-interaction-v0`
  unpacked into `fa/META-INF/jars/`). Now `crispy-skyblock-2.5.0.jar`. Since 2.3.0 it has a Mixin
  (`EndPortalBlock.getPortalDestination`), so `build.sh` takes Sponge Mixin's jar as a third argument.

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
  End portal at 150 min. They land within 6 blocks of the island centre, except the End portal (below).
- **Nether.** Each island has its own 64x64 void Nether plot under island/8 with a small netherrack starter island.
  A fortress wreck with a blaze spawner lands after 2 min there (another at 20, a wither skeleton one at 60), and
  bastion chunks at 10 and 40 min.
- **End portal and the island's own End** (2.3.0). The End portal event builds the portal on its own platform 14 blocks
  east of the island centre, out over the void, so it can never overwrite anything built on the island; players bridge
  to it and can't break it. It doesn't go to the vanilla End: each island has its own End island in the void dimension
  `crispy_skyblock:end` (End sky and fog, no dragon fight; type `the_end_type.json` from the server jar with
  `has_ender_dragon_fight` false), at the island's x/z, y 64. It's built the first time anyone goes (`end/island`):
  end stone with a purpur ring, obsidian pillars, chorus, the summoning altar in the middle and a purpur gateway home on
  its north edge (walk through it to go home). Players are kept within the same 128x128 square as their island
  (`p/ebounds`, once a second), so nobody can fly over to another island's End.
- **Nether boss arena.** Every island's Nether plot has a blackstone arena 16 blocks south of its starter island with
  its own altar (built with new Nether islands; older ones get it the next time a member is in their Nether).
- **Bosses.** Right-clicking the lodestone on an altar asks "Are you sure you want to summon a boss right now?"; a
  second right-click within 10 s summons that realm's next boss for the island, with a boss bar.
  Each island climbs its own ladder (starting at a different boss per island, then in turn after each kill):

  | Realm | Bosses (HP) | Reward to every member |
  |---|---|---|
  | End | Ender Colossus (400), Void Ravager (500), Shulker Matriarch (450), The Archmage (350) | 3,000 coins + loot |
  | Nether | Blaze King (400), Magma Titan (500), Brute Warlord (450), Wither Knight (500) | 1,500 coins + loot |

  Each has a periodic ability (scream and levitate, endermite or blaze adds, phantoms, blink and blindness, ground
  slam, ...). Loot is `loot_table/entities/boss_<key>` (End: pearls, shells, dragon's breath, diamonds, a 20-25% elytra
  chance, a totem from the Archmage; Nether: blaze rods, ancient debris, netherite scrap, an upgrade template chance,
  a wither skull chance from the Wither Knight). After a kill the realm is on cooldown for 20 min of island play time; only
  members can summon; a boss nobody fights for 2 min despawns. Storage: `plots[id].endp/endb/narena`; scores
  `cs_ba*`/`cs_bc*`/`cs_bi*`/`cs_bk*` (alive, cooldown, index, kills per realm).
- **Challenges** (`/island challenges` or `/challenges`): 26 one-time hand-ins (Easy, Medium, Hard, and three that need
  an island level) for resources, spawn eggs and XP. Finished ones show crossed out.
- **Island level** (`/island level`): the mod counts every block in the plot (1 point each; iron, gold, diamond,
  emerald, netherite blocks, beacons and the like more; fluids, plants, bedrock, spawners and portal frames nothing);
  100 points = 1 level. Once a minute per island on demand, and every 5 minutes for islands with someone online. It
  sets `cs_lvl` for the island and its members, keeps results in storage `crispy_skyblock:levels`, and rewrites the
  Top Islands board in the hub (the text display tagged `cs_top`). `/island top` lists the top 10. Islands nobody belongs to any more are left off, and the board refreshes when someone starts a new island.
- **Menu.** Esc → Island Menu (a dialog): go home, challenges, level, top, invite, accept, info, hub, how to play, start
  a new island (wipes inventory, ender chest and XP; then the island picker opens; once per 10 min).

## Skills (2.5.0)

`Skills.java`. Five skills earn XP into scoreboard objectives (`sk_farm`, `sk_mine`, `sk_forage`, `sk_combat`,
`sk_fish`); level L needs 100 x L^2 XP in total, up to 25. Each level-up pays 100 x L coins.

| Skill | XP from | Perk per level |
|---|---|---|
| Farming | fully grown crops 2, nether wart / cocoa 3, melon / pumpkin 4, sugar cane / cactus 1 | +2% chance of double drops |
| Mining | ores 4-30 (diamond 25, emerald 30, ancient debris 50), stone / cobble / netherrack 1, end stone 2, obsidian 5 | +2% chance of double ore drops |
| Foraging | logs 5 | +2% chance of double logs |
| Combat | hostile mobs: half their max health; bosses (`cs_boss`) 300 | +1% damage (attribute modifier `crispy_skyblock:skill_combat`) |
| Fishing | 30 per catch (the `fish_caught` stat, checked every second) | +0.2 Luck (`crispy_skyblock:skill_fishing`), better catches |

- Blocks a player placed give no XP and no double drops (`BlockItemMixin` remembers placed positions in memory, up to
  200,000 per dimension), so placing and breaking can't farm it; cobblestone from a generator still counts. Crops and
  minions don't count as placed blocks; only fully grown crops give XP.
- Kills are caught by `LivingEntityMixin` (on `LivingEntity.die`), crediting the killer or whoever last hurt the mob.
- `/skills` (`/island skills`, or Island Menu > Skills) shows each skill's level, progress bar and perk. The sidebar
  shows the skill average. XP shows on the action bar as you earn it.

## Bazaar, island upgrades, pets and resource zones (2.6.0)

Menus are built by `Ui.java` (chest GUIs that refill after each click).

**Bazaar** (`Bazaar.java`; `/bazaar`, `/bz`, the Bazaar NPC in the hub, Island Menu > Bazaar). A player market for
the merchant goods, stored in `<world>/crispy_bazaar.json`. Place a sell offer (items held in escrow) or a buy order
(coins held in escrow) at your own price; new orders match the best price on the other side straight away. Sellers
pay 1% tax. Sales to offline players are paid into their `cs_coins` by name. Up to 20 open orders each; claim or
cancel them under "My orders". Amount and price are entered in a dialog.

**Island upgrades** (`Upgrades.java`; `/island upgrades`). Any member can buy them; tiers live on `plots[id]`
(`us`, `um`, `uc`, `ug`).

| Upgrade | Tiers | Cost |
|---|---|---|
| Size | 128 > 160 > 192 > 256 square | 25k / 75k / 200k |
| Minion slots | +2 per tier | 10k / 30k / 90k |
| Co-op slots | 4 > 6 > 8 members | 15k / 50k |
| Ore generator | lava + water cobblestone sometimes comes out as ore (`LiquidBlockMixin`); tier 3 adds diamond and emerald | 5k / 25k / 75k |

Size moves the plot's corners and `sd` (size - 1, used by the datapack's bounds checks in place of the old fixed
size), forceloads the new ground and paints it with the island's biome.

**Pets** (`Pets.java`; `/pets`, `/island pets`). Bought in the pets menu, stored in `crispy_skyblock:pets` by UUID.
The active pet floats beside you as an `item_display` head. Each pet boosts one skill's XP by 10% + 1% per pet level
(level = sqrt(xp / 40), max 30; it levels from the XP it boosts) and gives a small stat (`crispy_skyblock:pet`).
Pig (Farming, 2.5k), Silverfish (Mining, 5k), Fox (Foraging, 5k), Wolf (Combat, 8k), Squid (Fishing, 5k). The Phoenix
can't be bought: each island member has a 3% chance of one per End boss kill; it boosts every skill at half rate
and gives +2 hearts. Staff: `/pets grant <player> <pet>`.

**Resource zones** (`expansion.py` builds them, `Zones.java` runs them; `/warp hub|home|mines|woods`, the Warps NPC).
- The Deep Mines (-260, 90, -360): a terraced quarry, richer ores further down. Ores and stone regrow after 45 s.
- Whispering Woods (260, 100, -360): a forest island. Logs regrow after 30 s.
- Only the zone's resource blocks can be broken; a mined block is bedrock until it grows back (all are restored when
  the server stops). Nothing can be placed. Hostile mobs spawn while players are there (8 + 2 per player).
- Build or rebuild them with `function crispy_skyblock:zones/build_all`.
- Portals (2.8.0): the hub has a portal to each zone either side of the island portal (Mines at -13 -14, Woods at
  13 -14), and each zone has a portal back to the hub behind its arrival platform. Every portal (hub, zones and each
  island's hub portal) now has a themed frame (`portal/style_island|mines|woods`) around a swirling portal surface
  (a `block_display`, tag `cs_portalfx`: nether_portal on island portals, which doesn't lead to the Nether; a thin pane of orange or lime stained glass on the Mines and Woods portals) and themed particles
  (`portal/fx_*`). Walking through is handled by `Portals.FIXED` in the mod. Existing island portals are restyled
  the next time a member is on the island (`plots[id].portal` 1b -> 2b); the hub rebuilds once (`hub_v4`).

**Zone RPG rules** (2.7.0, `ZoneRules.java`):
- Zone mobs get a level when they spawn: in the Deep Mines 2 + one per block below the rim (about Lv 2 at the top,
  Lv 25 on the floor, +/-2); in the Whispering Woods Lv 3-8. Each level adds 15% health and 6% damage. The name tag
  shows `[Lv N] Mob ||||||||-- hp/max`, coloured by level and remaining health. Kills pay 2 coins per level (and
  Combat XP, which already scales with max health).
- Zone mobs don't burn in daylight (`MobMixin` on `Mob.isSunBurnTick`).
- Items that drop in a zone (mined blocks, mob loot; not items a player threw) are marked gathered (custom_data
  `cs_gathered` and a lore line). The mark comes off when you leave the zone.
- Dying in a zone drops only gathered items. The rest of the inventory and your XP are put aside in storage
  `crispy_skyblock:stash` (`ServerPlayerMixin` on `ServerPlayer.die`) and given back on respawn (or on join, after a
  restart). Nothing changes if keep_inventory is on.

## Market District (2.9.0)

`district.py` builds a floating island south of the hub (x -45..45, z 50..146), joined to the hub's south path by a
bridge, with 16 plots (16x16) along a lit avenue; `HubPlots.java` runs them. The Realtor NPC at the district's
entrance, a plot's sign, or `/plots` opens the plots menu: buy a free plot (20,000 coins, click twice to confirm,
one plot each), visit any plot, abandon yours (clears it, 50% back). `/plots trust|untrust <player>`, `/plots home`,
`/warp plots`; staff: `/plots evict <n>` (for sale again, builds kept).

- Ownership is in storage `crispy_skyblock:hubplots` (`p<n>`: owner UUID, name, trust, tnames).
- The owner, trusted players and the owner's island co-op can build from 4 below the floor to 32 above. Standing in
  the plot they're tagged `cs_hpbuild` and the datapack puts them in survival; the rest of the district is adventure
  like the hub (and skips the island bounds check). Nothing outside a plot can be broken or placed; chests, item
  frames and armor stands in a plot can only be used by its builders. TNT, fire and lava aren't allowed.
- Labels over each plot's sign (`cs_hpl_<n>`) show "For sale" or the owner, refreshed every 30 s.
- Built once by `district/build` (scheduled from load while `#districtv cs_cfg` is unset).

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

## Armor and weapons (2.4.0)

`gear.py` (imported by `skyblock.py`) defines craftable Hypixel-style gear. Everything is made at a crafting table from
farmable blocks; the top tier needs boss loot. The recipes (and all minion recipes) are unlocked in every player's recipe book, and `/gear`
(`/island gear`, or Island Menu > Armor & Weapons) shows each item with its recipe. Items are unbreakable and carry
vanilla enchantments plus ones from `crispy_enchants` (the Anarchy/PvP custom enchant pack, also installed on Skyblock
as `world/datapacks/crispy_enchants.zip`; build it with `anarchy/enchants/gen.py`).

Armor pieces use the main block and core item in the piece's shape (helmet `#C#/# #`, chestplate `# #/#C#/###`,
leggings `#C#/# #/# #`, boots `# #/C C`). Wearing all four gives the set bonus (checked once a second, `gear/bonus`).

| Set | Rarity | Crafted from | Full set bonus |
|---|---|---|---|
| Farm Suit | Uncommon | Hay Block + Wheat | Bountiful Harvest: Speed I and Haste I. |
| Mushroom Armor | Uncommon | Red Mushroom Block + Brown Mushroom | Night Stalker: At night: Strength I and Regeneration I. |
| Cactus Armor | Uncommon | Cactus + Green Dye | Desert Bloom: Regeneration I while standing on sand. Attackers get pricked. |
| Pumpkin Armor | Uncommon | Pumpkin + Jack O Lantern | Squash Buckler: Resistance I: you take 20% less damage. |
| Angler Armor | Uncommon | Dried Kelp Block + Cod | Deep Sea Diver: Water Breathing, Dolphin's Grace and Luck II (better fishing loot). |
| Lapis Armor | Rare | Lapis Block + Diamond | Deep Core: +4 hearts and Luck II. Each piece gives +1 heart too. |
| Miner's Outfit | Rare | Coal Block + Iron Pickaxe | Pickaxe Prodigy: Haste II. Each piece mines a bit faster. |
| Golem Armor | Rare | Iron Block + Carved Pumpkin | Iron Skin: Resistance I. Every 30s you get Absorption II. |
| Blaze Armor | Epic | Magma Block + Blaze Rod | Hellfire: Fire Resistance. In the Nether: Strength I and Speed I too. |
| Ender Armor | Epic | Purpur Block + Ender Eye | End Born: Speed I. In your island's End: Strength II and Regeneration I. |
| Voidwalker Armor | Legendary | Shulker Shell + Netherite Ingot | Void Touched: Strength I, Speed I, Resistance I and +4 hearts. Fall into the void and you drift down slowly. |

Weapons and tools. Right-click abilities are handled by the mod (`Gear`): an item with `custom_data`
`{cs_ability, cs_cd}` runs `gear/ab/<key>` and goes on its own cooldown (`use_cooldown` group). Abilities only hit mobs
in `#crispy_skyblock:gear_targets` (never players, villagers or pets) and never set fire to or break blocks.

| Item | Rarity | Crafted from | Ability / notes |
|---|---|---|---|
| Undead Sword | Uncommon | 2 Bone Block, 1 Stick | Deals extra damage to zombies, skeletons and other undead. |
| Rogue Sword | Uncommon | 1 Gold Block, 1 Sugar, 1 Stick | Speed Boost (right-click, 15s): Gain Speed III for 6 seconds. |
| Zombie Sword | Rare | 4 Rotten Flesh, 2 Iron Block, 1 Stick | Instant Heal (right-click, 20s): Heal yourself and players within 7 blocks for 4 hearts. |
| Golem Sword | Rare | 2 Iron Block, 2 Carved Pumpkin, 1 Stick | Iron Punch (right-click, 8s): Slam the ground: 10 damage to every enemy within 5 blocks and knocks them into the air. |
| Leaping Sword | Rare | 2 Feather, 1 Slime Block, 1 Stick | Leap (right-click, 4s): Launch yourself forward and fall slowly for a moment. |
| Aspect of the End | Rare | 2 Ender Eye, 1 Diamond Sword | Instant Transmission (right-click, 2s): Teleport 8 blocks ahead of you and gain Speed II for 3 seconds. |
| Ember Rod | Epic | 1 Magma Block, 2 Blaze Rod | Fire Blast (right-click, 3s): Shoot a blast of flame at the first enemy in your sight (12 damage, up to 16 blocks). |
| Pigman Sword | Epic | 2 Cooked Porkchop, 2 Gold Block, 1 Blaze Rod | Burning Souls (right-click, 20s): 8 damage to enemies within 6 blocks, then Absorption II for 15 seconds. |
| Voidedge | Legendary | 4 Dragon Breath, 2 Shulker Shell, 1 Netherite Sword | Shadow Step (right-click, 8s): Teleport behind the nearest enemy within 12 blocks and strike it for 16 damage. |
| Runaan's Crossbow | Rare | 4 Bone Block, 2 String, 1 Crossbow | Fires three arrows at once and reloads in a flash. |
| Stonk | Rare | 3 Gold Block, 2 Stick | Mines faster than any vanilla pickaxe, smelts ores and puts the drops straight in your bag. |
| Treecapitator | Epic | 3 Obsidian, 2 Stick | A good chance to fell a whole tree with one swing. |
| Angler's Rod | Uncommon | 3 Dried Kelp Block, 2 String | Better catches, and they bite much sooner. |

## Mod commands

`/island` (alias `/is`) opens the Island Menu; `/island choose|challenges|gear|level|top`; `/gear`; `/skills`; `/bazaar` (`/bz`); `/pets`; `/warp`; `/plots`; `/island upgrades|pets|skills`; `/invite <player>` (also
`/island invite <player>`). Menus are chest GUIs defined by the datapack in storage `crispy_skyblock:menus` (set on
every load); an entry with `done:"<objective>"` shows its `item_done` once the viewer's score there is 1 or more.

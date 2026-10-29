# Crispy Skyblock

Skyblock on `Falling01` (Fabric 26.2, Velocity name `skyblock`, was `falling`). It replaced Crispy Falling on
2026-10-28 with a fresh world. The old world is kept on the instance as `world_falling_backup`; `gen.py` is its retired
`crispy_falling` datapack.

- `skyblock.py <outdir>` builds the `crispy_skyblock` datapack (install as `world/datapacks/crispy_skyblock`, or upload
  it zipped). Its dimension files make the overworld and the Nether void, so a new world must be created with the pack
  already in `world/datapacks`.
- `mod/` is the `crispy_skyblock` server mod (`crispy-skyblock-2.0.0.jar`, build with
  `mod/build.sh <lib-dir> <javac>`, same lib dir as `pvp/spawnmod` plus Fabric API's `fabric-events-interaction-v0`
  unpacked into `fa/META-INF/jars/`). Now `crispy-skyblock-2.4.0.jar`. Since 2.3.0 it has a Mixin
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
  its north edge (walk through it to go home).
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
farmable blocks; the top tier needs boss loot. The recipes are unlocked in every player's recipe book, and `/gear`
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

`/island` (alias `/is`) opens the Island Menu; `/island choose|challenges|gear|level|top`; `/gear`; `/invite <player>` (also
`/island invite <player>`). Menus are chest GUIs defined by the datapack in storage `crispy_skyblock:menus` (set on
every load); an entry with `done:"<objective>"` shows its `item_done` once the viewer's score there is 1 or more.

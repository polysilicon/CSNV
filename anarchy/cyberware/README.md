# Crispy Cyberware (Anarchy)

Cyberpunk-style implants for Crispy Anarchy (Fabric 26.2). Datapack only, so players need no mods.

```
python3 build.py <outdir>     # writes <outdir>/crispy_cyberware
```
Install it to `world/datapacks/crispy_cyberware`. Dialogs are only read at startup, so the first install needs a
**server restart** (a `/reload` loads everything else). Then place the Ripperdoc once:
```
execute in crispy:market run forceload add -48 56 -32 72
execute in crispy:market positioned -46.5 172 65.5 run function cyber:admin/place_doc
execute in crispy:market run forceload remove -48 56 -32 72
```
It stands four blocks north of the Enchanter. Like the Enchanter it is tagged `crispy_shop`, because the market moves
every other villager out of the world each second. That also means `crispy:market/reinstall` removes it, so
re-run the place commands after a reinstall.

## How it works
- On Anarchy the `crispy-anarchy` mod (`anarchy/mod`) shows the Ripperdoc as a chest menu; without it, the dialog
  opens. Either way buying runs `cyber:doc/buy`, which checks you're near the Ripperdoc and takes the price (a failed
  payment returns 0: before the fix, `return run tellraw` returned 1, so people could buy without paying).
- **Ripperdoc** (right-click): buy implants with diamonds or netherite, buy Neuroblockers, or remove an implant
  (free; the item goes back to your inventory). You can only buy within 8 blocks of the Ripperdoc.
- **Installing**: hold right-click with an implant for 2.5 s. Implants are recognised by their icon, because creative-mode
  clients can strip custom data from items they move. One implant per body slot; if the slot is taken
  you get the item back.
- **Capacity**: every implant costs capacity. Going over **20** is allowed, but each second over the limit there is
  an `excess / 600` chance of a cyberpsychosis episode, at most one every 30 s. With 10 over, that's about one a
  minute. An episode is one of:
  - nausea and darkness;
  - rage (strength, but you glow);
  - blindness;
  - 4 damage;
  - hunger and weakness.

  Nearby players see "X is showing signs of cyberpsychosis!". A **Neuroblocker** (2 diamonds) suppresses it for 20 minutes.
- **Flicker**: during an episode the player's body glitches in and out of view for about 6 s, with red sparks, like
  cyberpsychos in the anime. A Cyberskeleton wearer gets short bursts from 70% psychosis and flickers constantly while
  fully cyberpsycho. Only the invisibility the flicker added itself is ever removed (tag `cy.flk_on`), so real
  invisibility potions are kept.
- **Death**: all installed implants drop as items where you died, so anyone can pick them up and install them.
- `/trigger cyber` shows your installed implants, capacity, Neuroblocker time and cooldowns.

| Implant | Slot | Cap | Price | Effect |
|---|---|---|---|---|
| Kiroshi Optics | Ocular | 2 | 8 diamonds | permanent night vision |
| Subdermal Armor | Integumentary | 4 | 24 diamonds | +4 armor, +1 toughness |
| Titanium Bones | Skeleton | 4 | 24 diamonds | +2 hearts, +10% knockback resistance |
| Bionic Lungs | Skeleton | 2 | 8 diamonds | +4 oxygen bonus, swim 30% faster |
| Gorilla Arms | Arms | 5 | 32 diamonds | +2 attack damage, +0.5 knockback |
| Mantis Blades | Arms | 6 | 32 diamonds | +1.5 damage, +0.4 attack speed, +0.5 reach |
| Power Grip | Hands | 2 | 12 diamonds | +30% mining speed, +0.5 underwater mining |
| Reinforced Tendons | Legs | 4 | 16 diamonds | higher jump, +3 safe fall, −40% fall damage |
| Lynx Paws | Legs | 2 | 8 diamonds | fast sneaking, step up full blocks |
| Reflex Tuner | Nervous System | 4 | 24 diamonds | +10% movement speed |
| Biomonitor | Circulatory | 3 | 16 diamonds | ≤4 hearts: Regen II 6 s + Absorption; 90 s cooldown |
| Second Heart | Circulatory | 8 | 2 netherite | ≤2 hearts: Instant Health III, Absorption II, Fire Res; 10 min cooldown |
| Sandevistan | Operating System | 8 | 3 netherite | double-tap sneak: Speed IV, Haste II for 6 s; Slowness III on everything within 12 blocks; leaves an Edgerunners-style after-image trail; 60 s cooldown |
| Berserk | Operating System | 7 | 2 netherite | double-tap sneak: Strength II + Resistance for 8 s (you glow); 75 s cooldown |
| Projectile Launch System | Arms | 6 | 2 netherite | sneak + jump: fires an explosive round (fireball, power 1) where you look; 8 s reload. On Anarchy it can break blocks if mob griefing is on |
| Militech Cyberskeleton (PvP test-only) | Skeleton | 14 | not sold | +10 hearts, +8 armor, +4 toughness, +6 damage, big jumps, 80% knockback resistance; landing from 3+ blocks ground-slams nearby enemies (8 damage, 5 s cooldown); dual-wield: offhand melee weapon adds its damage, offhand bow/crossbow fires a second arrow; worn armor gets a red Rib trim; Sandevistan synergy, psychosis meter, last stand, grab & throw, charged leap, heat/overheat (see pvp/README.md). Only built with `--pvp`, admin room / `cyber:admin/give` only |

Everything is set in the tables at the top of `build.py`:
- implants, prices and capacity costs: `IMPLANTS`;
- the capacity limit: `CAP_LIMIT`;
- the Neuroblocker: `NEURO`;
- Operating System cooldowns: `OS_CD`.

**Sandevistan after-images**: every 2 ticks while it runs, a hologram copy of the player is left where they stand,
like the anime's trail.
- The copy is an invisible, glowing mannequin, so only a coloured silhouette of their body shows. It copies their
  facing, crouch and model (slim or wide arms), with a few cyan-green specks.
- Each copy lasts 10 ticks and fades aqua → green → dark aqua (teams `cy.g1`–`cy.g3`), so a short blue-green trail
  follows them.
- The model comes from a hidden item_display (`cy.ganchor`) holding the player's head, which follows the player.
- Copies are removed below the world, so there's no death animation.
- Leftover copies are cleaned up on load.
- Tune it with `GHOST_TICKS`, `GHOST_LIFE` and `GHOST_COLORS`.

Admins can get one of everything with `function cyber:admin/give`.

## Testing notes
- On the live server, after a `/reload`, every function, loot table and advancement loaded, except the two
  dialogs; those need a restart.
- On an armor stand, each implant's stat changes applied and then removed back to the base value.
- Installing by right-click, double-tap sneak and the death drop need a real player, so test those in game.

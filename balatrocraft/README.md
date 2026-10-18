# Balatro Craft

A poker roguelike played in a chest menu on the Lobby server (`CrispyLobby01`, Paper 26.2).
Open it with `/balatro` (aliases `/bc`, `/cards`) or the emerald in slot 4 of the DeluxeHub server selector.

## How a run works
- 8 cards in hand. Click cards to select up to 5 (selected cards rise a row), then **Play** or **Discard**.
- Score = **Chips × Mult**. The hand type gives base chips and mult; each scoring card adds its chips (2–10, faces 10, ace 11).
- 4 hands and 3 discards per blind. Each ante has a Small, Big and Boss blind; beat the Ante 8 boss (Ender Dragon) to win,
  then the run continues in endless mode.
- Targets per ante: 300, 700, 1,600, 3,500, 7,000, 12,000, 20,000, 30,000 (×1 small, ×1.5 big, ×2 boss, ×4 dragon).
- Cash out after each blind: $3/$4/$5, plus $1 per unused hand, plus $1 interest per $5 held (max $5).

## Minecraft twist
- **Suits:** Diamonds ◆, Redstone ❤, Emeralds ♣, Coal ♠. Stack size shows the rank.
- **Mobs = jokers** (5 slots): Zombie, Skeleton, Creeper (blows cards out of your deck), Spider, Slime, Blaze, Fox, Bee, Axolotl,
  Wither Skeleton (×3), Piglin, Villager, Cow, Phantom, Ghast (×2), Iron Golem (+1 hand), Enderman (+1 discard),
  Allay (copies the mob to its right).
- **Bosses:** Warden (face cards face down), Elder Guardian (max 3 cards), Wither (first hand halved), Ravager (no discards),
  Evoker / Witch / Pillager / Drowned (debuff a suit), Ender Dragon (Ante 8, 4× target).
- **Shop:** 2 mobs and 2 items per visit, reroll from $5. Enchanted books level up a hand type; tools change cards
  (Sharpening Stone +30 chips, Rabbit's Foot +4 mult, Blast Furnace → Diamonds, Blaze Powder +1 rank, Silk Touch copy,
  Lava Bucket destroy, Emerald Bundle doubles money up to +$20).

- **Card packs:** every shop has one pack: Standard ($4, pick 1 of 3) or Jumbo ($6, pick 2 of 5). Picked cards join
  your deck; 30% come enchanted. The Creeper never blows the deck below 30 cards.
- **Chat:** the 💬 book (table, shop and pack screens) shows the last 7 lobby chat lines live. Click it to type; the game
  reopens as soon as you send your message.

## Daily run and leaderboard
`/balatro daily`: one attempt per day (America/Chicago), same seed for everyone. `/balatro top [daily]` shows the top 10
by blinds cleared, then best hand. Rewards are cosmetic only; nothing is paid with real money.

## Files
- Runs are saved after every action in `plugins/BalatroCraft/runs/<uuid>.yml` (resume any time); scores in `scores.yml`.
- Admin: `/balatro reset <player>` deletes a player's current run.

## Build and test
```
CP=$(find <lobby>/libraries -name '*.jar' | grep -v paper-api/1.21 | tr '\n' ':')
javac --release 21 -proc:none -cp "$CP" -d out $(find src -name '*.java') && cp res/* out/ && (cd out && jar cf ../BalatroCraft-1.0.0.jar .)
javac --release 21 -cp "out:$CP" -d tout test/crispy/balatro/SimTest.java && java -cp "tout:out:$CP" crispy.balatro.SimTest
```
`SimTest` checks hand detection and invariants, round-trips saves, and plays 2,000 bot runs (balance check).

# UnoCraft

UNO played in a chest menu on the Lobby server (`CrispyLobby01`, Paper 26.2).

To open it:
- type `/uno`;
- or click the red concrete **UNO** item in slot 6 of the DeluxeHub server selector, next to Balatro Craft.

## Playing
- `/uno` opens the table list.
- **Create a table**:
  - The lobby gets a clickable *[Click to join]* invite.
  - Others can also join with `/uno join <id>`.
  - The host can **add bots** to fill seats.
  - 2-8 players. The host clicks **Start**.
- The game screen:
  - **Top row**: every player, with their card count. The current player glows. The last slot is the direction of play.
  - **Second row**: **UNO!** (bell), **Draw / Pass**, the **top card**, the **colour to match** and **Leave**
    (shift-click).
  - **Your hand** is below. Cards you can play glow. Arrows page through more than 27 cards.
- Rules (standard 108-card deck):
  - Match the colour, number or symbol.
  - **Skip**, **Reverse** (acts as a Skip with 2 players), **Draw Two**, **Wild** (pick a colour from the wool row)
    and **Wild Draw Four**.
  - Can't play? Draw one card. If it fits you may play it, or **Pass**; otherwise your turn ends.
  - Click **UNO!** before playing your second-to-last card, or draw 2 as a penalty.
  - No stacking and no Draw Four challenges.
  - If the deck runs out and nobody can play, the player with the fewest cards wins.
- **Turns**:
  - 30 s each. Running out of time draws and passes for you.
  - 3 missed turns in a row removes you from the table.
  - Your turn opens the game for you, unless you're in another menu.
  - Bots wait 1.5 s, then play.
- Card looks:

  | Card | Item | Stack size |
  |---|---|---|
  | Number | coloured concrete (0 is concrete powder) | the number |
  | Skip | coloured stained glass | 1 |
  | Reverse | coloured glazed terracotta | 1 |
  | Draw Two | coloured shulker box | 2 |
  | Wild | nether star | 1 |
  | Wild Draw Four | end crystal | 4 |

- Wins are broadcast in the lobby. `/uno top` shows the most wins, saved in `plugins/UnoCraft/stats.yml`.
- `/uno leave` leaves a table. Leaving the lobby (switching server or logging out) leaves too, and your cards go back
  into the deck.

## Build and test
```
CP=$(ls <paper-api and its libraries>/*.jar | tr '\n' ':')
javac --release 21 -proc:none -cp "$CP" -d out $(find src -name '*.java') && cp res/* out/ && (cd out && jar cf ../UnoCraft-1.0.0.jar .)
javac --release 21 -cp out -d tout test/crispy/uno/SimTest.java && java -cp tout:out crispy.uno.SimTest
```
`Game.java` has no Minecraft code. `SimTest` covers:
- 3,000 bot games (2-8 players), checking that the 108 cards are never lost or duplicated and every play is legal;
- players leaving mid-game;
- 200 games against a player who always times out;
- the UNO penalty.

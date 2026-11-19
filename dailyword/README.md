# Daily Word

Guess the day's five-letter word in six tries, in a chest menu on the Lobby server (`CrispyLobby01`, Paper 26.2).
Open it with `/word` (alias `/dailyword`) or from **Lobby Minigames** in the server selector (`/minigames`).

## Playing
- Click **Type a guess** and send a five-letter word in chat. That message is hidden: nobody else sees it.
  `/word <guess>` works too.
- Each guess shows as a row of glass named by its letter: **green** = right letter, right spot; **yellow** = in the
  word, wrong spot; **grey** = not in it. The same colours are repeated in chat, and the sign in the corner shows
  every letter you've tried. Repeated letters follow the standard rules (see `Score.java`).
- Six tries. Everyone gets the same word; a new one at midnight, America/Chicago (like Balatro Craft's daily run).
- Solving it announces "X solved Daily Word #N in 3/6" in the lobby, with the colour grid on hover (no letters).
- Stats: played, win %, current and best streak, guesses-to-solve (`/word stats`). `/word top`: today's solvers and the
  longest streaks.
- **No spoilers:** a player who has finished today's word can't post it in chat.

## Where the word comes from
The Discord bot picks it (`tools/discordbot/dailyword.py`): every day it chooses a random word nobody has had yet and
writes `plugins/DailyWord/word.json` (`{day, number, word}`), plus `valid.txt` (every allowed guess) and
`answers.txt`. The lists come from open sources: common US-English words with swears removed
(first20hours/google-10000-english), kept only if they are lowercase dictionary words (wooorm/dictionaries, so no
names or abbreviations), plus a short list of Minecraft words; guesses may be any of ~16k five-letter English words
(dwyl/english-words). If the bot's word is missing or not today's, the plugin picks one itself from `answers.txt`,
seeded by the date. `/word refresh` (console) reloads.

## Files
`plugins/DailyWord/stats.yml` (players, per-day history with the word), `summary.json` (for the bot's `/dailyword`:
today's counts, never today's word; yesterday's word and results; current streaks).

## Build and test
```
CP=$(find <lobby>/libraries -name '*.jar' | grep -v paper-api/1.21 | tr '\n' ':')
javac --release 21 -proc:none -cp "$CP" -d out $(find src -name '*.java') && cp res/* out/ && (cd out && jar cf ../DailyWord-1.0.0.jar .)
javac --release 21 -cp out -d tout test/crispy/word/ScoreTest.java && java -cp tout:out crispy.word.ScoreTest
```

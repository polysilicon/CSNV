# CrispyLobby

Paper 26.2 plugin for the Lobby (`CrispyLobby01`). It provides:

- the sidebar;
- the spawn handling;
- the network stats board and `/stats`;
- network vote rewards and cosmetics (1.4.0).

Build with JDK 25 against `paper-api-26.2` and `nuvotifier-2.7.3.jar`. The source is in `src/`; `plugin.yml` and `config.yml` are in `res/`.

## Vote rewards

Server-list votes arrive at **NuVotifier on the lobby, port 8193**. That is the port to tunnel and give to TopG and Planet Minecraft, together with the lobby's `plugins/Votifier/rsa/public.key` or the v2 token in `plugins/Votifier/config.yml`.

Factions' own NuVotifier is disabled (`plugins/NuVotifier-2.7.3.jar.disabled`). Its vote broadcast is off, since the lobby announces votes network-wide. Its `/vote` lists the same sites.

The sites are TopG, Planet Minecraft, MinecraftServers.org, Minecraft-Server-List and MMTop200. A site's test vote (username in `votes.test-usernames`) is only logged.

Each vote gives the player:

- **1 unclaimed reward**;
- `points-per-vote` **vote points**, used for cosmetics.

### Claiming

In the lobby, `/vote` (or `/rewards`) opens a menu.

- Click a server to send 1 reward there.
- Shift-click to send all of them.

A claimed reward waits in `plugins/CrispyLobby/votes.json`. Every 5 s the lobby checks each backend's `list` over RCON, using the port and password from that instance's own `server.properties`. When the player is online there, the server's `commands` run with `%player%` replaced.

Defaults:

| Server | Reward |
|---|---|
| Factions | `vote test %player% CrispyAnarchy`: CrispyFactions' normal vote reward ($5,000, a Crispy Case, a bonus key every 5th vote). It also counts toward Factions' vote party. |
| Anarchy (`og`) | 3 diamonds, 2 golden apples, 5 levels |
| Vanilla | no reward (trails only) |
| Falling | 4 iron, 16 bone meal, 2 saplings |
| PvP | no item reward; it only gets trails |

Edit `votes.servers` in the live config, then run `/vote reload`.

### Admin commands

- `/vote give <player> [n]`: hand out votes (also good for testing).
- `/vote points <player> <+/-n>`
- `/vote reset <player>`: delete a player's vote data.
- `/vote reload`

## Cosmetics (`/cosmetics`)

Cosmetics are bought once with vote points. `/cosmetics` (or Cosmetics in `/vote`) opens a hub with two buttons, **Tags** and **Name colours**. Each has its own menu, where you buy, wear or take off (or use the barrier button). A player can wear one tag and one name colour at a
time, and both show on every server.

- **Tags** (`cosmetics.tags`) appear before the name in chat, after it in the tab list, and on name tags.
  - The lobby writes `plugins/CrispyLobby/tags.json`.
  - In chat they're added by `chattags/` (the Fabric mod and the Paper plugin), so they also reach cross-chat and Discord.
  - The tab list and name tags come from the **CrispyTags** Velocity plugin (`proxy/crispytags`, needs TAB).
- **Name colours** (`cosmetics.name-colors`, a colour code like `&b`, `&6&l`, or `rainbow`) colour the name in chat.
  - The lobby writes `plugins/CrispyLobby/namecolors.json`, which the same `chattags/` readers use.

**Earned tags** (1.7.0) cost nothing. They're on their own page of the Tags menu.
- **Advancements** (permanent once claimed): Dragonslayer, Withered, Beaconator, Netherite, Monster Hunter, Wanderer,
  Hero, Wings and UNO. Completed on any server listed in `cosmetics.earned-sources.advancements`; the files are read
  directly.
- **Milestones** (permanent): Veteran (100 h played), Slayer (10,000 mob kills), Excavator (100,000 blocks mined),
  Nomad (5,000 km travelled), Deathwish (300 deaths) and Kit Master (1.7.1: mastered a PvP character). All are
  network totals from the stats board.
- **Rankings** (worn only while held): Warlord (#1 player kills), No-Lifer (top 3 playtime), Tycoon (#1 Factions
  money), Patient Zero (#1 Outbreak wave), Unstoppable (#1 PvP kill streak), High Roller (#1 Balatro), Card Shark
  (#1 UNO wins), Champion (1.7.1: #1 duel rating) and Top Voter (#1 voter this month). After every stats refresh (5 min), anyone who lost the spot has
  the tag taken off and is told.
- Config: a tag with `advancement`, or `stat` + `min`, or `stat` + `top`, is an earned tag. `stat` is a stats-board
  category or `VOTES`. The stats board also gained Outbreak Best Wave and PvP Best Kill Streak (read from the PvP
  server's `scoreboard.dat`) and UNO Wins.

Walking trails were retired in 1.5.0. Their points were refunded on the first load, and the `crispy_cosmetics`
datapack was removed from every server.

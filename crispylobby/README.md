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

The sites are TopG, Planet Minecraft, MinecraftServers.org and Minecraft-Server-List. A site's test vote (username in `votes.test-usernames`) is only logged.

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

Cosmetics are bought once with vote points and toggled on and off in the menu. They show on every server.

- **Tags** (`cosmetics.tags`) appear after the name in the tab list and above the head.
  - The lobby writes `plugins/CrispyLobby/tags.json`.
  - The **CrispyTags** Velocity plugin (`proxy/crispytags`, needs TAB) reads it every 3 s and sets TAB's custom suffix.
- **Trails** (`cosmetics.trails`) are particles while walking or sprinting. They are hidden for spectators and invisible players.
  - The lobby draws its own trails.
  - On the backends, the `crispy_cosmetics` datapack (`cosmetics/build.py`, installed as `world/datapacks/crispy_cosmetics.zip`) draws them from the `crispy.trail` score. The lobby sets that score over RCON when it sees the player on the server.
  - After adding or renumbering trails, rebuild the datapack and re-upload it.

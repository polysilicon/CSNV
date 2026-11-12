# New-player analytics

`new_player_funnel.py` measures where new players drop off, from our own logs. It runs **on the AMP host** (the player
data never leaves it) with the standard library only:

    python3 new_player_funnel.py --days 60            # anonymised report on stdout
    python3 new_player_funnel.py --days 60 --names    # with real names

The full report (real names) is always written to `/root/crispy_analytics/funnel-<date>.md` (mode 600). Copy the
script there first (`/root/crispy_analytics/new_player_funnel.py`); rerun weekly and compare the weekly table.

## Sources it reads

| Data | Where | Used for |
|---|---|---|
| Velocity log (`test01/Minecraft/logs`, since 2025-06-11) | logins, server switches, disconnects with reasons, kicks, refused logins | sessions, visits, funnel, errors |
| `[source] NAME host=… new=…` lines (CrispyTags 1.11.0+) | same log | which address each player joined with |
| Anarchy and Vanilla logs from before the proxy | backend logs | a "new" name that played there before 2025-06 is a returning veteran |
| Backend logs of the first server a player picked | `<instance>/Minecraft/logs` | deaths, chat, commands (Paper/Factions only; Fabric servers don't log commands) |
| Lobby log | `CrispyLobby01/Minecraft/logs` | what new players typed in the lobby (example timelines) |

No IPs are used (every connection comes through the relay, so the proxy sees one internal address).

## Definitions

- **Visit**: sessions less than 30 minutes apart are one visit (a crash, reconnect or restart is not a "return").
- **New player**: first visit in the window, never seen by the proxy before, not a pre-proxy Anarchy/Vanilla player.
  Staff are excluded (`--exclude`, default `lbxd`).
- **Chose a mode**: reached any server other than the lobby in the first visit.
- **Bounced**: chose a mode but the whole first visit was under 2 minutes.
- **Error in first visit**: any kick or failed connection (unable to connect, internal error, invalid payload...).
- **D1**: a new visit within 48 h of first joining (counted once 48 h have passed).
- **D7**: played on any day 7-13 after first joining (counted once 14 days have passed).
- **D30**: played on any day 30-59 (counted once 60 days have passed).

Numbers are small (10-30 new players a week): read counts, not just percentages, and judge changes over 2-3 weeks.

## Source tracking: one address per channel

Each channel gets its own name. All of them reach the same server; CrispyTags logs which one a player typed, and the
report's "By source" table splits the funnel by it. No proxy config is needed (unknown hosts go to the lobby).

DNS (Google Domains / Squarespace, zone `crispyanarchy.net`), two records per source:

| Type | Host | Value |
|---|---|---|
| A | `<src>` | `167.71.109.106` (same as `crispyanarchy.net`) |
| SRV | `_minecraft._tcp.<src>` | priority `0`, weight `5`, port `13134`, target `crispyanarchy.net` |

| `<src>` | Channel | Put it in |
|---|---|---|
| `topg` | TopG | listing's Server IP field |
| `pmc` | Planet Minecraft | Server IP |
| `mcso` | MinecraftServers.org | Server IP (port field: 13134) |
| `mcsl` | Minecraft-Server-List | Server IP (port field: 13134) |
| `mmtop` | MMTop200 | Server IP |
| `mcmp` | Minecraft-MP | Server IP (port field: 13134) |
| `tilt` | ServerTilt | Server IP |
| `cf` | CurseForge server listing | Server address |
| `play` | the website (join box and copy button) | `marketing/site/build.py` `JAVA` |
| `dc` | Discord (#info, welcome, FAQ) | bot info posts and welcome.toml |
| `yt`, `tt` | YouTube, TikTok video descriptions | when we start posting |

Order matters: add the DNS records, check that `<src>.crispyanarchy.net` joins in the game, then change the listing.
Bedrock players keep using `crispyanarchy.net` port 19100 (Bedrock ignores SRV, and Geyser may not pass the name on).
Votes are unaffected (Votifier doesn't use the server address).

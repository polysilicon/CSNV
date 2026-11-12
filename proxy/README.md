# Velocity proxy (AMP instance `test01`, Velocity 3.4.0)

## Network tab list: TAB 6.2.0 (NEZNAMY)
- `plugins/TAB-6.2.0.jar` (Modrinth, sha512 checked). Live config: `plugins/tab/config.yml` and `groups.yml`
  (copies here as `tab-config.yml` / `tab-groups.yml`; the generated originals are kept as `*.orig` next to them).
- Velocity server names (`/server <name>`): `lobby`, `anarchy` (was `og`), `Vanilla`, `factions`, `skyblock` (was `falling`), `multiverse`
  (was `pvp`). Renamed on 2026-10-28; DeluxeHub's selector, CrispyLobby (`proxy:`), TAB's `%server%` names and
  CrispyTags' combat-tag lookup were updated with them.
- Global player list: everyone on Lobby, Factions, Anarchy, Vanilla, Skyblock and Multiverse shows in one tab list,
  sorted by server then name, tagged `[Server] name`, with live ping. Crispymon is not on the proxy.
- Header "CrispyAnarchy / N players online"; footer with your server, ping and the Discord link.
- Server names are prettified with `placeholder-output-replacements` for `%server%`.
- DeluxeHub's own tablist on the Lobby is switched off (`tablist.enabled: false`) so it doesn't overwrite TAB.
- Apply edits with `btab reload` in the proxy console (no restart).

## CrispyTags (`proxy/crispytags`, 1.4.2)
- Shows the lobby's cosmetic tags after names in the tab list and on name tags (through TAB), from the lobby's `tags.json`.
  - Name tags need **VelocityScoreboardAPI** (2.1.1) next to TAB; without it TAB can't send scoreboard teams on Velocity.
  - TAB's teams are off on Multiverse (`disable-condition: '%server%=Multiverse'`; TAB's `%server%` is the display
    name): the PvP datapack shows its Outbreak and Tower sidebars by team colour (`sidebar.team.*`), and a TAB team
    coloured by someone's name colour made the Tower sidebar stick. The ping objective is off too (`playerlist-objective`).
- (Before 1.7.0) owned `/vote` and `/cosmetics` on every server. Since 1.7.0 each server draws the lobby's menus
  itself (CrispyLobby `RemoteMenus`, crispy_chattags 1.7.0, CrispyChatTags 1.6.0), so they're no longer registered here.
  The old behaviour, for reference: off the lobby it connects the player to `lobby`
  (`-Dcrispytags.lobby` to change), then hands the command line to CrispyLobby on the `crispy:vote` plugin channel,
  which opens the menu. On the lobby it hands it over straight away.
- Not in combat (1.2.0): before sending anyone to the lobby it reads `Minecraft/crispy_combat.json` of the server
  they're on (written by `crispy_chattags` on the Fabric servers and CrispyFactions on Factions) and refuses with
  "You can't use /vote in combat (Ns left)". No file (or a server not in its list) means no check.
- `/lobby` (alias `/hub`, 1.4.2) on every server (1.4.0): sends you to `lobby`, like `/server lobby`, but refuses while you're combat-tagged
  (same check as `/vote`). On the lobby it just says you're already there.
- `/server <name>` is refused while combat-tagged too (1.4.1, a `CommandExecuteEvent` listener). A bare `/server`
  still lists the servers, and moves that aren't a command (like being sent to the lobby when a server goes down)
  aren't affected.
- Name colors in the tab list (1.3.0): reads the lobby's `namecolors.json` (set from the cosmetics menu) and sets each
  player's tab-list name to the same colors the lobby uses (`rainbow` and `|` sequences cycle per letter). Players
  without a color keep TAB's default name. The file is re-read when it changes.

## Bedrock (Geyser 2.12.1+, NetherNet) — 2026-11-09

Bedrock 26.60+ dropped RakNet; clients now join with NetherNet: a TCP "signaling" request, then WebRTC gameplay over
UDP. LocalXpose can't run a TCP and a UDP tunnel on the same public port, so the two are split:

| LocalXpose tunnel | Public | Local (proxy host) | Geyser config.yml |
|---|---|---|---|
| bedrocktcp (TCP) | us.loclx.io:19100 | :19100 | `bedrock.port: 19100` (built-in signaling) |
| bedrockudp (UDP) | us.loclx.io:19101 | :19101 | `bedrock.webrtc-port: 19101` |

`bedrock.signaling.advertise-addresses: ["crispyanarchy.net:19101"]` tells clients where the UDP side is
(crispyanarchy.net and us.loclx.io are the same IP). Players still use **crispyanarchy.net, port 19100**; a one-time
"trust this server" prompt on first join is normal. Backup of the pre-change config: `config.yml.bak-nethernet`;
the old jar is `Geyser-Velocity-2.11.3.jar.bak`. If Bedrock shows "Terracotta", Geyser is too old for the client.

## Per-mode addresses + first-join welcome (CrispyTags 1.10.0) — staged 2026-11-09, deploy at night

**Addresses:** `anarchy|skyblock|multiverse|factions|vanilla.crispyanarchy.net` go straight to that server
(velocity.toml `[forced-hosts]`, falling back to the lobby if the server is down). Plain `crispyanarchy.net` still goes
to the lobby. Each needs a DNS SRV record like the main one: `_minecraft._tcp.<mode>` → priority 0, weight 5,
port 13134, target `us.loclx.io` (Java only).

**Welcome:** `Newcomers.java` marks a player new at login when no server has a saved file for their UUID
(`<instance>/Minecraft/world/players/data` or `world/playerdata`). If they land anywhere but the lobby they get a
welcome with [Other modes] (/lobby), [Discord] and [Vote rewards], and everyone else online sees "<name> just joined
Crispy for the first time, on <mode>. Say hi!". Lobby arrivals keep CrispyLobby's own welcome. The lobby's
`cosmetics.joined-sources.player-data` now also lists Skyblock, Multiverse and Factions, so a player who started
on one of those isn't treated as new when they first visit the lobby.

Deploy (files are staged under inactive names):
1. Proxy (test01): `plugins/CrispyTags-1.9.0.jar` → `.bak`, `CrispyTags-1.10.0.jar.pending` → `.jar`;
   `velocity.toml` → `velocity.toml.bak-forcedhosts`, `velocity.toml.tonight` → `velocity.toml`; restart the proxy.
2. Lobby: `plugins/CrispyLobby/config.yml` → `config.yml.bak-joined`, `config.yml.tonight` → `config.yml`; `vote reload`.

## CrispyTags 1.11.0 (staged as CrispyTags-1.11.0.jar.pending; goes live with a proxy restart)

- `[source] NAME host=... new=...` on every login: the address the player typed, for `tools/analytics`.
- `ChannelCap`: big mod packs register more than Paper's 128 plugin channels, and the lobby kicked them with
  "Invalid custom payload payload!" (17 kicks, 6 players, Sep-Nov 2026). The proxy now passes on at most 100 channel
  registrations per connection (vanilla, proxy and our own namespaces first) and drops the rest, logged as `[channels]`.
- Factions replaced by Extraction Zone in the first-join welcome and the combat-tag server list.

velocity.toml (2026-11-12, live after `velocity reload`): `kick-existing-players = true` (a reconnect replaces a stale
session instead of "You are already connected to this proxy!") and `try = ["lobby", "multiverse"]` (if the lobby is
down, players land on Multiverse instead of "Unable to connect you to lobby"). Lobby `allow-flight=true` (no flying
kicks in the hub), from its next restart.

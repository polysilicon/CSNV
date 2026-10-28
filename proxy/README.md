# Velocity proxy (AMP instance `test01`, Velocity 3.4.0)

## Network tab list: TAB 6.2.0 (NEZNAMY)
- `plugins/TAB-6.2.0.jar` (Modrinth, sha512 checked). Live config: `plugins/tab/config.yml` and `groups.yml`
  (copies here as `tab-config.yml` / `tab-groups.yml`; the generated originals are kept as `*.orig` next to them).
- Velocity server names (`/server <name>`): `lobby`, `anarchy` (was `og`), `Vanilla`, `factions`, `falling`, `multiverse`
  (was `pvp`). Renamed on 2026-10-28; DeluxeHub's selector, CrispyLobby (`proxy:`), TAB's `%server%` names and
  CrispyTags' combat-tag lookup were updated with them.
- Global player list: everyone on Lobby, Factions, Anarchy, Vanilla, Falling and Multiverse shows in one tab list,
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
- Owns `/vote` and `/cosmetics` on every server: off the lobby it connects the player to `lobby`
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

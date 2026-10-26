# Velocity proxy (AMP instance `test01`, Velocity 3.4.0)

## Network tab list: TAB 6.2.0 (NEZNAMY)
- `plugins/TAB-6.2.0.jar` (Modrinth, sha512 checked). Live config: `plugins/tab/config.yml` and `groups.yml`
  (copies here as `tab-config.yml` / `tab-groups.yml`; the generated originals are kept as `*.orig` next to them).
- Global player list: everyone on Lobby, Factions, Anarchy (`og`), Vanilla, Falling and PvP shows in one tab list,
  sorted by server then name, tagged `[Server] name`, with live ping. Crispymon is not on the proxy.
- Header "CrispyAnarchy / N players online"; footer with your server, ping and the Discord link.
- Server names are prettified with `placeholder-output-replacements` for `%server%`.
- DeluxeHub's own tablist on the Lobby is switched off (`tablist.enabled: false`) so it doesn't overwrite TAB.
- Apply edits with `btab reload` in the proxy console (no restart).

## CrispyTags (`proxy/crispytags`, 1.4.0)
- Shows the lobby's cosmetic tags after names in the tab list and on name tags (through TAB), from the lobby's `tags.json`.
- Owns `/vote` and `/cosmetics` on every server: off the lobby it connects the player to `lobby`
  (`-Dcrispytags.lobby` to change), then hands the command line to CrispyLobby on the `crispy:vote` plugin channel,
  which opens the menu. On the lobby it hands it over straight away.
- Not in combat (1.2.0): before sending anyone to the lobby it reads `Minecraft/crispy_combat.json` of the server
  they're on (written by `crispy_chattags` on the Fabric servers and CrispyFactions on Factions) and refuses with
  "You can't use /vote in combat (Ns left)". No file (or a server not in its list) means no check.
- `/lobby` on every server (1.4.0): sends you to `lobby`, like `/server lobby`, but refuses while you're combat-tagged
  (same check as `/vote`). On the lobby it just says you're already there.
- Name colors in the tab list (1.3.0): reads the lobby's `namecolors.json` (set from the cosmetics menu) and sets each
  player's tab-list name to the same colors the lobby uses (`rainbow` and `|` sequences cycle per letter). Players
  without a color keep TAB's default name. The file is re-read when it changes.

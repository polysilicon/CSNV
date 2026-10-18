# Velocity proxy (AMP instance `test01`, Velocity 3.4.0)

## Network tab list: TAB 6.2.0 (NEZNAMY)
- `plugins/TAB-6.2.0.jar` (Modrinth, sha512 checked). Live config: `plugins/tab/config.yml` and `groups.yml`
  (copies here as `tab-config.yml` / `tab-groups.yml`; the generated originals are kept as `*.orig` next to them).
- Global player list: everyone on Lobby, Factions, Anarchy (`og`), Vanilla, Falling and Bending shows in one tab list,
  sorted by server then name, tagged `[Server] name`, with live ping. Crispymon is not on the proxy.
- Header "Crispy Network / N players online"; footer with your server, ping and the Discord link.
- Server names are prettified with `placeholder-output-replacements` for `%server%`.
- DeluxeHub's own tablist on the Lobby is switched off (`tablist.enabled: false`) so it doesn't overwrite TAB.
- Apply edits with `btab reload` in the proxy console (no restart).

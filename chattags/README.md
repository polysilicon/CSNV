# Chat tags

These show the vote-cosmetic tags bought in the lobby (`/cosmetics`) before the sender's name in chat, e.g.
`<[Voter] lbxd> hi`. The tag is also in the server log, so the Discord bot's cross-chat and Discord relay carry it
with no bot change. Both versions read the lobby's `plugins/CrispyLobby/tags.json` and re-read it when it changes.

- `fabric/` is the `crispy_chattags` mod for Anarchy, Vanilla, Falling and PvP.
  - `/vote` and `/cosmetics` (1.7.0, `RemoteMenu`, registered by `CommandsMixin`, no Fabric API needed): asks the
    lobby's CrispyLobby (`RemoteMenus`, `http://127.0.0.1:25599`, `-Dcrispy.lobbyapi` to change) for the menu, draws
    it as a chest, sends clicks back and shows the reply (next menu, chat lines, sounds). Refused while in combat.
  - Combat state (1.4.0): hitting or being hit by a player puts both in combat for 15 s; on PvP, being in a duel
    (`pvp.duel`) or an Outbreak run (`pve.in`) counts too. Once a second it writes `crispy_combat.json` in the server
    folder (name -> epoch ms when free), which the CrispyTags proxy plugin checks before `/vote` or `/cosmetics`.
  - A mixin on `ServerGamePacketListenerImpl.broadcastChatMessage` swaps the chat-type name for "tag + name".
  - Join, leave and death messages keep the plain name, which the bot uses to track players.
  - Styled Chat (on Anarchy and Vanilla) formats chat itself, so the mixin doesn't apply there. Instead the mod
    registers the Placeholder API placeholder `%crispy:tag%` (the tag plus a space, or nothing). The chat format in
    `config/styled-chat.json` is `<%crispy:tag%${player}> ${message}`; backup in `styled-chat.json.bak-tags`.
  - Chat colours (1.5.0): a player's colour from the lobby's `chatcolors.json` colours their message text. The
    mixin swaps in a coloured unsigned copy of the message; on Styled Chat servers the mod hooks Styled Chat's
    `MESSAGE_CONTENT` event instead (by reflection, so the mod still loads without it). Messages with a link stay
    plain, and `&` codes a player types stay literal.
  - Build with `fabric/build.sh <lib-dir> <javac-25> <sponge-mixin.jar> <placeholder-api.jar>`. The Placeholder API
    jar is nested in styled-chat's jar under `META-INF/jars/`.
- `paper/` is the `CrispyChatTags` plugin for the Lobby and Factions.
  - `/vote` and `/cosmetics` (1.6.0, `RemoteMenu`): on servers without CrispyLobby (Factions) it takes both
    commands (before CrispyFactions' own `/vote`, as the proxy used to), draws the lobby's menus from the reply's
    "simple" items (Factions is 1.21.11, older than the lobby) and refuses while combat-tagged (`crispy_combat.json`).
    Built with `--release 21` against the 26.2 API, for both the lobby (Java 25) and Factions (Java 21).
  - It puts the tag into the player's display name while a chat message is sent, and restores it 2 s later.
  - Clients show that name for signed chat, and EssentialsChat's `{DISPLAYNAME}` uses it.
  - A renderer pass adds the tag if a format left it out.
  - Chat colours (1.4.0): the message text is recoloured from `chatcolors.json` before the format runs, and (1.4.1)
    swapped into the finished line for formats that render their own copy of the message (EssentialsChat), with the
    same rules as the Fabric mod (links stay plain, typed `&` codes stay literal, `rainbow` and `a|b|c` sequences
    go letter by letter).

Colour codes (Fabric 1.6.0, Paper 1.5.0): both use `ColorCodes.java`, the same file as the lobby and the proxy plugin,
so fades (`&#ff5f6d>&#ffc371`) and flag bands (`&#5bcefa/&#f5a9b8/&#ffffff`) look the same everywhere. The Paper
plugin turns hex colours into Spigot's `§x` form for SaberFactions' legacy chat event, and (1.5.1) only colours that
event's message where SaberFactions is installed (`legacy-chat-colors`): EssentialsChat on the Lobby stripped the codes
from it and left the "x" of each hex colour behind.


## Slur filter (Fabric 1.9.0+, Paper 1.7.0+)

Listed slurs are replaced with stars (`you're a ******`), never blocked, so chat keeps flowing. One word list for
everything: the Discord bot's `/opt/crispybot/censor_words.txt` (all servers run as `amp` on the same host and can
read it; `-Dcrispy.censor=<path>` to change). Edit that file and every server and the Discord relay pick it up within
seconds. `Censor.java` is a line-for-line copy of the bot's `censor.py` matching (checked identical on 1,437 test
lines): leetspeak, repeated letters and junk between letters are seen through, words inside longer words are not
(raccoon, Scunthorpe). List syntax: `word` (plus s/es/ed/ing/y/ies endings), `stem*` (any word starting with it),
`=word` (only the word or its plural, for short slurs whose endings are real words: spicy, tardy; the bot reads it as
`word`), multi-word entries match with or without spaces. Both copies of `Censor.java` (fabric/ and paper/) must stay
identical.

- Fabric: public chat is starred before it is coloured (ChatNameMixin, or the Styled Chat hook), so colours stay;
  `CensorChatMixin` stars anything else a client receives (/msg, /me, /teammsg, /say); `CensorLogMixin` stars the
  log line (the bot's cross-server chat reads it); `CensorTextMixin` stars sign lines and book pages/titles before
  they are stored; `CensorAnvilMixin` stars anvil names.
- Paper (`CensorListener`): chat at LOWEST (legacy and Paper events, before the colour/tag passes), private-message
  commands (`/msg`, `/tell`, `/w`, `/r`, `/me`, `/mail`, `/f` ...), `SignChangeEvent`, `PlayerEditBookEvent`,
  `PrepareAnvilEvent`.
- Not covered: messages typed in Discord and sent into the game (Discord has its own moderation), and anything
  already in the world before 1.9.0 (old signs, books, item names).
- 1.9.1 / 1.7.1: a starred chat message is sent as a system message (formatted the same as chat), not as signed
  player chat. With a signed message, Java clients keep the original text and show it on hover ("Message modified by
  the server"). Fabric: `CensorChatMixin` checks the signed original on every outgoing player message. Paper:
  `CensorListener` marks starred events and `onChat` sends those through the system-chat path (Factions already
  sends all chat that way). Unstarred chat is untouched.

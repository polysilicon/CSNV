# Chat tags

These show the vote-cosmetic tags bought in the lobby (`/cosmetics`) before the sender's name in chat, e.g.
`<[Voter] lbxd> hi`. The tag is also in the server log, so the Discord bot's cross-chat and Discord relay carry it
with no bot change. Both versions read the lobby's `plugins/CrispyLobby/tags.json` and re-read it when it changes.

- `fabric/` is the `crispy_chattags` mod for Anarchy, Vanilla, Falling and PvP.
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
  - It puts the tag into the player's display name while a chat message is sent, and restores it 2 s later.
  - Clients show that name for signed chat, and EssentialsChat's `{DISPLAYNAME}` uses it.
  - A renderer pass adds the tag if a format left it out.
  - Chat colours (1.4.0): the message text is recoloured from `chatcolors.json` before the format runs, and (1.4.1)
    swapped into the finished line for formats that render their own copy of the message (EssentialsChat), with the
    same rules as the Fabric mod (links stay plain, typed `&` codes stay literal, `rainbow` and `a|b|c` sequences
    go letter by letter).

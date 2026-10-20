# Chat tags

These show the vote-cosmetic tags bought in the lobby (`/cosmetics`) before the sender's name in chat, e.g.
`<[Voter] lbxd> hi`. The tag is also in the server log, so the Discord bot's cross-chat and Discord relay carry it
with no bot change. Both versions read the lobby's `plugins/CrispyLobby/tags.json` and re-read it when it changes.

- `fabric/` is the `crispy_chattags` mod for Anarchy, Vanilla, Falling and PvP.
  - A mixin on `ServerGamePacketListenerImpl.broadcastChatMessage` swaps the chat-type name for "tag + name".
  - Join, leave and death messages keep the plain name, which the bot uses to track players.
  - Build with `fabric/build.sh <lib-dir> <javac-25> <sponge-mixin.jar>`.
- `paper/` is the `CrispyChatTags` plugin for the Lobby and Factions.
  - It wraps whatever chat renderer EssentialsChat set and puts the tag before the first occurrence of the player's name.

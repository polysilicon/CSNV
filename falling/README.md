# Crispy Falling

Skyblock-style survival on `Falling01` (Fabric 26.2). Each player gets a 50×50 bedrock island, and blocks, animals and
dungeons fall onto it from the sky.

- `gen.py <outdir>` builds the `crispy_falling` datapack (install as `world/datapacks/crispy_falling`).
- `mod/` is the `crispy_falling` server mod (`crispy-falling-1.0.0.jar`, build with `mod/build.sh <lib-dir> <javac>`):
  - `/invite <player>` (or `/island invite <player>`) invites an online player to your island by name;
  - `/island` opens the Island Menu.

  The menu's **Invite a player…** button opens a dialog where you type the username; it runs `/invite`. The mod runs
  `crispy_falling:act/invite_player` as the inviter with the permission level functions need. The invited player gets
  an **[Accept]** button in chat.

Dialogs only load at server start, so menu changes need a restart.

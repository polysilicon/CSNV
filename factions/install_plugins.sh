#!/bin/bash
# Downloads the Crispy Factions plugin stack into a Paper 1.21.11 server's plugins/ folder.
# Usage: install_plugins.sh <server-dir>
set -eu
P="$1/plugins"; mkdir -p "$P"; cd "$P"
g(){ curl -fsSL -m 120 -o "$1" "$2" && echo "ok $1"; }
g OldCombatMechanics.jar https://github.com/kernitus/BukkitOldCombatMechanics/releases/download/v2.7.0/OldCombatMechanics.jar
g SaberFactions.jar      https://github.com/SaberLLC/Saber-Factions/releases/download/4.1.9-STABLE/SaberFactions.jar
g EssentialsX.jar        https://github.com/EssentialsX/Essentials/releases/download/2.22.0/EssentialsX-2.22.0.jar
g EssentialsXChat.jar    https://github.com/EssentialsX/Essentials/releases/download/2.22.0/EssentialsXChat-2.22.0.jar
g EssentialsXSpawn.jar   https://github.com/EssentialsX/Essentials/releases/download/2.22.0/EssentialsXSpawn-2.22.0.jar
g Vault.jar              https://github.com/MilkBowl/Vault/releases/download/1.7.3/Vault.jar
g LuckPerms.jar "$(curl -fsS https://metadata.luckperms.net/data/all | python3 -c 'import sys,json;print(json.load(sys.stdin)["downloads"]["bukkit"])')"
for p in viaversion viabackwards chunky; do
  g $p.jar "$(curl -fsS "https://api.modrinth.com/v2/project/$p/version?loaders=%5B%22paper%22%5D&game_versions=%5B%221.21.11%22%5D" | python3 -c 'import sys,json;print(json.load(sys.stdin)[0]["files"][0]["url"])')"
done
g EconomyShopGUI.jar https://api.spiget.org/v2/resources/69927/download
# HMCWraps (optional, cosmetic wraps): download manually from SpigotMC/Polymart and drop the jar here.
# CrispyFactions: build from ./crispyfactions (see README) and copy CrispyFactions-1.0.0.jar here.

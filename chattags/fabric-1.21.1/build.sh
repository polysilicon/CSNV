#!/bin/bash
# Crispymon (1.21.1) build of crispy_chattags. 1.21.1 is obfuscated, so: compile against a Mojang-named server jar,
# then remap the mod to intermediary names (what Fabric runs on 1.21.1) with tiny-remapper's Mixin support.
# usage: build.sh <monbuild-dir> <crispymon-minecraft-dir> <jdk21-bin>
#   monbuild-dir: server-named.jar, tools/merged.tiny (official/intermediary/named, from tools/MergeMap.java:
#                 Fabric intermediary-1.21.1-v2 + Mojang's 1.21.1 server mappings), tools/tiny-remapper.jar
set -e; D=$(cd "$(dirname "$0")" && pwd); B=$1; C=$2; J=${3:-}
CP=$B/server-named.jar:$(find "$C/libraries" -name "*.jar" | grep -v "/net/minecraft/" | tr '\n' ':')
rm -rf "$D/out" && mkdir -p "$D/out"
"$J"javac --release 21 -proc:none -nowarn -cp "$CP" -d "$D/out" $(find "$D/src" -name "*.java")
cp "$D"/res/*.json "$D/out/"
(cd "$D/out" && "$J"jar cf "$D/named.jar" .)
"$J"java -jar "$B/tools/tiny-remapper.jar" "$D/named.jar" "$D/crispy-chattags-1.10.0+mc1.21.1.jar" "$B/tools/merged.tiny" named intermediary "$B/server-named.jar" --mixin
echo "built $D/crispy-chattags-1.10.0+mc1.21.1.jar"

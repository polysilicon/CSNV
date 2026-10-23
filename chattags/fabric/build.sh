#!/bin/bash
# usage: build.sh <lib-dir> <javac-25> <sponge-mixin.jar> <placeholder-api.jar>   lib-dir as for pvp/spawnmod (server-26.2 + bundler libraries)
set -e; D=$(cd "$(dirname "$0")" && pwd); L=$1; JAVAC=${2:-javac}; MIX=$3; PAPI=$4
CP=$(find "$L" -name "*.jar" | tr '\n' ':')$MIX:$PAPI
rm -rf "$D/out" && mkdir -p "$D/out"
"$JAVAC" --release 25 -proc:none -cp "$CP" -d "$D/out" $(find "$D/src" -name "*.java")
cp "$D"/res/*.json "$D/out/"
(cd "$D/out" && jar cf "$D/crispy-chattags-1.4.0.jar" .)
echo "built $D/crispy-chattags-1.4.0.jar"

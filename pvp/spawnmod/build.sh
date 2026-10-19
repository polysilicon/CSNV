#!/bin/bash
# usage: build.sh <lib-dir> <javac-25>   lib-dir: server-26.2.jar, brigadier, fabric-loader, fabric-api (with nested jars unpacked under fa/)
set -e; D=$(cd "$(dirname "$0")" && pwd); L=$1; JAVAC=${2:-javac}
CP=$(find "$L" -name "*.jar" | tr '\n' ':')
rm -rf "$D/out" && mkdir -p "$D/out"
"$JAVAC" --release 25 -cp "$CP" -d "$D/out" $(find "$D/src" -name "*.java")
cp "$D/res/fabric.mod.json" "$D/out/"
(cd "$D/out" && jar cf "$D/crispy-pvp-spawn-1.1.0.jar" .)
echo "built $D/crispy-pvp-spawn-1.1.0.jar"

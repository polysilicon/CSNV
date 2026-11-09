#!/bin/bash
# usage: build.sh <lib-dir> <javac-25> [placeholder-api.jar]   lib-dir: server-26.2.jar, brigadier, fabric-loader, fabric-api (with nested jars unpacked under fa/)
set -e; D=$(cd "$(dirname "$0")" && pwd); L=$1; JAVAC=${2:-javac}
CP=$(find "$L" -name "*.jar" | tr '\n' ':')${3:+:$3}
rm -rf "$D/out" && mkdir -p "$D/out"
"$JAVAC" --release 25 -proc:none -cp "$CP" -d "$D/out" $(find "$D/src" -name "*.java")
cp "$D"/res/*.json "$D/out/"
(cd "$D/out" && jar cf "$D/crispy-anarchy-1.2.1.jar" .)
echo "built $D/crispy-anarchy-1.2.1.jar"

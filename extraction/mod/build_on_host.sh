#!/bin/bash
# Compile the mod on the AMP host (it has JDK 25 and the exact 26.2 server + Fabric jars). Run there as root:
#   bash build_on_host.sh <src.tgz>   -> /root/ezbuild/crispy-extraction-<ver>.jar
set -e
B=/root/ezbuild; M=/AMPStorage/.ampdata/instances/Extraction01/Minecraft; J=/usr/lib/jvm/temurin-25-jdk-amd64/bin
rm -rf $B/src $B/out && mkdir -p $B/src $B/out $B/lib
tar xzf "$1" -C $B/src
if [ ! -f $B/lib/.ready ]; then
  find $M/libraries $M/.fabric $M/versions -name "*.jar" -exec cp {} $B/lib/ \; 2>/dev/null || true
  mkdir -p $B/lib/fa && (cd $B/lib/fa && unzip -qo $M/mods/fabric-api-*.jar 'META-INF/jars/*' && mv META-INF/jars/*.jar . 2>/dev/null; true)
  touch $B/lib/.ready
fi
CP=$(find $B/lib -name "*.jar" | tr '\n' ':')
if ! $J/javac --release 25 -proc:none -nowarn -cp "$CP" -d $B/out $(find $B/src -name "*.java") > $B/javac.log 2>&1; then
  grep -v "^Note:" $B/javac.log | head -60; echo "BUILD FAILED"; exit 1
fi
cp $B/src/res/*.json $B/out/
V=$(python3 -c "import json;print(json.load(open('$B/out/fabric.mod.json'))['version'])")
(cd $B/out && $J/jar cf $B/crispy-extraction-$V.jar .)
ls -la $B/crispy-extraction-$V.jar

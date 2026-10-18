#!/bin/bash
# Stop Factions01, swap in CrispyFactions 1.1.0, add the combat-tag config section, start.
S=/AMPStorage/.ampdata/instances/Factions01/Minecraft; LOG=/opt/factions/install_cases.log
python3 /opt/factions/frc.py "say Server restarting in 30 seconds to add CS-style cases - back in about a minute" >/dev/null; sleep 20
python3 /opt/factions/frc.py "say Restarting in 10 seconds..." "save-all" >/dev/null; sleep 10
su -s /bin/bash amp -c "ampinstmgr --StopInstance Factions01" >> $LOG 2>&1
for i in $(seq 1 90); do up=0; for d in /proc/[0-9]*; do [ "$(cat $d/comm 2>/dev/null)" = java ] && readlink $d/cwd 2>/dev/null | grep -q Factions01 && up=1; done; [ $up = 0 ] && break; sleep 2; done
mkdir -p /opt/factions/orig && mv $S/plugins/CrispyFactions-1.1.0.jar /opt/factions/orig/ 2>/dev/null
cp /opt/factions/build/CrispyFactions-1.2.0.jar $S/plugins/
python3 - <<'P'
p = "/AMPStorage/.ampdata/instances/Factions01/Minecraft/plugins/CrispyFactions/config.yml"; s = open(p).read()
if "\ncases:" not in s:
    src = open("/opt/factions/build/res/config.yml").read(); a = src.index("# CS2-style weapon cases"); b = len(src)
    s = s.rstrip("\n") + "\n\n" + src[a:b].rstrip("\n") + "\n"; open(p, "w").write(s)
P
chown -R amp:amp $S/plugins
su -s /bin/bash amp -c "ampinstmgr --StartInstance Factions01" >> $LOG 2>&1
echo "$(date -u) done" >> $LOG

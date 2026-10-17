#!/bin/bash
# Stop Factions01 (30s warning), install mcMMO 2.3.002 with the classic config, start, then build the spawn anvils.
S=/AMPStorage/.ampdata/instances/Factions01/Minecraft; LOG=/opt/factions/install_mcmmo.log; R="python3 /opt/factions/frc.py"
$R "say Server restarting in 30 seconds to add mcMMO - back in about a minute" >/dev/null; sleep 20
$R "say Restarting in 10 seconds..." "save-all" >/dev/null; sleep 10
su -s /bin/bash amp -c "ampinstmgr --StopInstance Factions01" >> $LOG 2>&1
for i in $(seq 1 90); do up=0; for d in /proc/[0-9]*; do [ "$(cat $d/comm 2>/dev/null)" = java ] && readlink $d/cwd 2>/dev/null | grep -q Factions01 && up=1; done; [ $up = 0 ] && break; sleep 2; done
cp /opt/factions/mcmmo/mcMMO-2.3.002.jar $S/plugins/
mkdir -p $S/plugins/mcMMO && tar xzf /opt/factions/mcmmo/cfg.tgz -C $S/plugins/mcMMO
chown -R amp:amp $S/plugins
su -s /bin/bash amp -c "ampinstmgr --StartInstance Factions01" >> $LOG 2>&1
L=$S/logs/latest.log
for i in $(seq 1 60); do sleep 3; grep -q "Done (" $L 2>/dev/null && head -1 $L | grep -q "$(date -u +%H:)" && break; done
sleep 5
# Blacksmith corner beside the spawn point: iron block = mcMMO Repair anvil, gold block = Salvage anvil
$R "setblock 7 73 13 minecraft:iron_block" "setblock 7 73 16 minecraft:gold_block" \
   "setblock 6 73 13 minecraft:dark_oak_wall_sign[facing=west]{front_text:{messages:[\"\",{text:\"REPAIR\",color:\"dark_gray\",bold:1b},\"right-click the\",\"iron block\"]},is_waxed:1b}" \
   "setblock 6 73 16 minecraft:dark_oak_wall_sign[facing=west]{front_text:{messages:[\"\",{text:\"SALVAGE\",color:\"gold\",bold:1b},\"right-click the\",\"gold block\"]},is_waxed:1b}" >> $LOG 2>&1
echo "$(date -u) done" >> $LOG

package crispy.ez;

import net.fabricmc.fabric.api.event.lifecycle.v1.ServerTickEvents;
import net.minecraft.ChatFormatting;
import net.minecraft.core.BlockPos;
import net.minecraft.network.chat.Component;
import net.minecraft.server.MinecraftServer;
import net.minecraft.server.level.ServerBossEvent;
import net.minecraft.server.level.ServerLevel;
import net.minecraft.server.level.ServerPlayer;
import net.minecraft.world.BossEvent;
import net.minecraft.world.entity.Entity;
import net.minecraft.world.entity.LivingEntity;

import java.util.HashSet;
import java.util.Set;
import java.util.UUID;

import static crispy.ez.Ui.t;

/**
 * The Commander (1.1.0): a heavily armed boss (function ez:boss/spawn: 260 HP, armour, an M60 hitscan gun, three
 * Riflemen) that lands in the city centre while raiders are in the zone: first FIRST after the server starts, then
 * RESPAWN after each death. Its chunk stays loaded while it lives; a boss bar shows to anyone within 64 blocks.
 * Drops the best loot in the zone (loot table ez:mob/boss). Everyone within 48 blocks when it dies counts for the
 * Commander contract.
 */
final class Boss {
    private Boss() {}

    static final long FIRST = 4 * 60_000L, RESPAWN = 20 * 60_000L;
    static UUID uuid;
    static BlockPos at;
    static long nextAt = -1;
    static final ServerBossEvent BAR = new ServerBossEvent(UUID.randomUUID(), Component.literal("☠ The Commander").withStyle(ChatFormatting.DARK_RED, ChatFormatting.BOLD),
            BossEvent.BossBarColor.RED, BossEvent.BossBarOverlay.NOTCHED_10);

    static void init() {
        ServerTickEvents.END_SERVER_TICK.register(server -> { if (server.getTickCount() % 20 == 0) second(server); });
    }

    static boolean raidersIn(MinecraftServer s) {
        for (ServerPlayer p : s.getPlayerList().getPlayers()) if (Raid.raiding(p) && p.level().dimension().equals(Zone.CITY)) return true;
        return false;
    }

    static void second(MinecraftServer server) {
        ServerLevel lvl = server.getLevel(Zone.CITY);
        if (lvl == null) return;
        long now = System.currentTimeMillis();
        if (nextAt < 0) nextAt = now + FIRST;
        Entity boss = uuid == null ? null : lvl.getEntity(uuid);
        if (uuid != null && (boss == null || !boss.isAlive())) {   // gone some other way (removed, unloaded)
            if (boss == null && at != null && lvl.isLoaded(at)) { reset(lvl); nextAt = now + 60_000L; }
            boss = null;
        }
        if (boss instanceof LivingEntity le) {
            BAR.setProgress(Math.max(0f, le.getHealth() / le.getMaxHealth()));
            Set<ServerPlayer> near = new HashSet<>();
            for (ServerPlayer p : lvl.players()) if (p.distanceToSqr(le) < 64 * 64) near.add(p);
            for (ServerPlayer p : new HashSet<>(BAR.getPlayers())) if (!near.contains(p)) BAR.removePlayer(p);
            for (ServerPlayer p : near) BAR.addPlayer(p);
            return;
        }
        if (uuid == null && now >= nextAt && raidersIn(server)) spawn(server, lvl);
    }

    static void spawn(MinecraftServer server, ServerLevel lvl) {
        BlockPos pos = Zone.street(lvl, Zone.CX, Zone.CZ);
        if (pos == null) pos = Zone.ground(lvl, Zone.CX, Zone.CZ);
        if (pos == null) return;
        at = pos;
        lvl.setChunkForced(pos.getX() >> 4, pos.getZ() >> 4, true);
        Plots.run(server, String.format("execute in lostcities:lostcity positioned %d %d %d run function ez:boss/spawn", pos.getX(), pos.getY(), pos.getZ()));
        Entity e = lvl.getEntitiesOfClass(LivingEntity.class, new net.minecraft.world.phys.AABB(pos).inflate(4), x -> x.entityTags().contains("ez.boss"))
                .stream().findFirst().orElse(null);
        if (e == null) { lvl.setChunkForced(pos.getX() >> 4, pos.getZ() >> 4, false); nextAt = System.currentTimeMillis() + 60_000L; return; }
        uuid = e.getUUID();
        for (ServerPlayer p : server.getPlayerList().getPlayers())
            if (Raid.raiding(p)) {
                p.sendSystemMessage(t("☠ The Commander has landed in the city centre with an escort. Best loot in the zone, if you can take it.", ChatFormatting.DARK_RED, ChatFormatting.BOLD));
                Ui.sound(p, net.minecraft.sounds.SoundEvents.WITHER_SPAWN, 0.4f, 1.4f);
            }
    }

    static void onDeath(LivingEntity dead, ServerPlayer killer) {
        ServerLevel lvl = (ServerLevel) dead.level();
        for (ServerPlayer p : lvl.players()) {
            if (p.distanceToSqr(dead) < 48 * 48) { Raid.State st = Raid.of(p); if (st != null) st.bossPresent = true; }
        }
        for (ServerPlayer p : lvl.getServer().getPlayerList().getPlayers())
            if (Raid.raiding(p)) p.sendSystemMessage(t("☠ The Commander is down" + (killer != null ? ", killed by " + killer.getGameProfile().name() : "") + ". His loot is up for grabs.", ChatFormatting.GOLD));
        reset(lvl);
        nextAt = System.currentTimeMillis() + RESPAWN;
    }

    static void reset(ServerLevel lvl) {
        if (at != null) lvl.setChunkForced(at.getX() >> 4, at.getZ() >> 4, false);
        BAR.removeAllPlayers();
        uuid = null; at = null;
    }
}

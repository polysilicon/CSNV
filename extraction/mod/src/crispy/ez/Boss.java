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

import java.util.List;
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
        // 1.8.3: the Commander is saved with the world, but uuid lived only in memory, so each restart spawned another.
        // The centre stays loaded; before anything else, adopt a Commander already there and remove any extras.
        int ccx = Zone.CX >> 4, ccz = Zone.CZ >> 4;
        if (!lvl.getForceLoadedChunks().contains(net.minecraft.world.level.ChunkPos.pack(ccx, ccz))) lvl.setChunkForced(ccx, ccz, true);
        if (uuid == null) {
            if (!lvl.areEntitiesLoaded(net.minecraft.world.level.ChunkPos.pack(ccx, ccz))) return;   // can't tell yet: never spawn blind
            List<Entity> found = lvl.getEntities((Entity) null, new net.minecraft.world.phys.AABB(Zone.CX - 96, -64, Zone.CZ - 96, Zone.CX + 96, 320, Zone.CZ + 96),
                    x -> x.entityTags().contains("ez.boss") && x.isAlive());
            if (!found.isEmpty()) {
                uuid = found.get(0).getUUID(); at = found.get(0).blockPosition();
                for (int i = 1; i < found.size(); i++) found.get(i).discard();
                if (found.size() > 1) System.out.println("[crispy-extraction] removed " + (found.size() - 1) + " extra Commander(s)");
            }
        }
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
        if (e == null) { nextAt = System.currentTimeMillis() + 60_000L; return; }
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
        BAR.removeAllPlayers();
        uuid = null; at = null;
    }
}

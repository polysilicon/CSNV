package crispy.ez;

import net.fabricmc.fabric.api.event.lifecycle.v1.ServerLifecycleEvents;
import net.fabricmc.fabric.api.event.lifecycle.v1.ServerTickEvents;
import net.minecraft.ChatFormatting;
import net.minecraft.core.BlockPos;
import net.minecraft.core.particles.DustParticleOptions;
import net.minecraft.core.particles.ParticleTypes;
import net.minecraft.server.MinecraftServer;
import net.minecraft.server.level.ServerLevel;
import net.minecraft.server.level.ServerPlayer;
import net.minecraft.world.level.block.state.BlockState;

import java.util.*;

import static crispy.ez.Ui.t;

/**
 * Dynamic zone events (1.1.0), one every 6-9 minutes while raiders are in the zone:
 *  - Supply drop: a barrel of top-tier loot (ez:event/supply) under a red flare column, for 8 minutes.
 *  - Helicopter crash: a smoking wreck with two crates (ez:event/heli) and three Riflemen guarding it, for 12 minutes.
 *  - Hot extract: a temporary extraction point for 3 minutes (a normal ez.exfil marker tagged ez.hot): valuables you
 *    extract with there pay double (Raid.extract).
 * Raiders hear roughly where (the district); a Field Radio on your stash plot gives the exact spot for the first event
 * of each raid. Everything placed is removed again when the event ends (the wreck only replaced air).
 */
final class Events {
    private Events() {}

    enum Kind { SUPPLY, HELI, HOT }
    static final class Ev {
        Kind kind; BlockPos pos; long ends; UUID marker;
        final Map<BlockPos, BlockState> placed = new LinkedHashMap<>();
    }
    static final List<Ev> ACTIVE = new ArrayList<>();
    static final Random RNG = new Random();
    static long nextAt = -1;

    static void init() {
        ServerTickEvents.END_SERVER_TICK.register(server -> { if (server.getTickCount() % 20 == 0) second(server); });
        ServerLifecycleEvents.SERVER_STOPPING.register(server -> {   // leave nothing behind over a restart
            ServerLevel lvl = server.getLevel(Zone.CITY);
            if (lvl != null) for (Ev e : new ArrayList<>(ACTIVE)) end(server, lvl, e);
        });
    }

    static void second(MinecraftServer server) {
        ServerLevel lvl = server.getLevel(Zone.CITY);
        if (lvl == null) return;
        long now = System.currentTimeMillis();
        for (Ev e : new ArrayList<>(ACTIVE)) {
            if (now >= e.ends) { end(server, lvl, e); continue; }
            double x = e.pos.getX() + 0.5, y = e.pos.getY(), z = e.pos.getZ() + 0.5;
            if (e.kind == Kind.SUPPLY) {
                lvl.sendParticles(new DustParticleOptions(0xFF3020, 2.5f), x, y + 20, z, 40, 0.15, 18, 0.15, 0);
                lvl.sendParticles(ParticleTypes.FLAME, x, y + 38, z, 12, 0.6, 0.6, 0.6, 0.02);
            } else if (e.kind == Kind.HELI) {
                lvl.sendParticles(ParticleTypes.CAMPFIRE_SIGNAL_SMOKE, x, y + 2, z, 6, 0.6, 0.4, 0.6, 0.02);
            }
        }
        if (nextAt < 0) nextAt = now + 3 * 60_000L;
        if (now >= nextAt && Boss.raidersIn(server)) {
            nextAt = now + (6 + RNG.nextInt(4)) * 60_000L;
            start(server, lvl);
        }
    }

    static String district(int x, int z) {
        int dx = x - Zone.CX, dz = z - Zone.CZ;
        if (Math.hypot(dx, dz) < 120) return "the city centre";
        return "the " + Raid.compass(dx, dz).getString() + " of the city";
    }

    static void start(MinecraftServer server, ServerLevel lvl) {
        Kind kind = Kind.values()[RNG.nextInt(3)];
        BlockPos pos = null;
        for (int tries = 0; tries < 6 && pos == null; tries++) {
            int x = Zone.CX - Zone.HALF + 80 + RNG.nextInt(2 * Zone.HALF - 160), z = Zone.CZ - Zone.HALF + 80 + RNG.nextInt(2 * Zone.HALF - 160);
            pos = Zone.street(lvl, x, z);
        }
        if (pos == null) return;
        Ev e = new Ev(); e.kind = kind; e.pos = pos;
        lvl.setChunkForced(pos.getX() >> 4, pos.getZ() >> 4, true);
        String at = String.format("execute in lostcities:lostcity positioned %d %d %d run ", pos.getX(), pos.getY(), pos.getZ());
        String what;
        switch (kind) {
            case SUPPLY -> {
                e.ends = System.currentTimeMillis() + 8 * 60_000L;
                put(lvl, e, pos, "minecraft:barrel[facing=up]{LootTable:\"ez:event/supply\"}", server, at);
                what = "📦 A supply drop flare went up in " + district(pos.getX(), pos.getZ()) + ". Look for the red smoke.";
            }
            case HELI -> {
                e.ends = System.currentTimeMillis() + 12 * 60_000L;
                int[][] body = {{0, 0, 0}, {1, 0, 0}, {2, 0, 0}, {-1, 0, 0}, {0, 0, 1}, {1, 0, 1}, {2, 0, 1}, {-1, 0, 1}, {0, 1, 0}, {1, 1, 0}, {0, 1, 1}, {1, 1, 1}};
                for (int[] b : body) put(lvl, e, pos.offset(b[0], b[1], b[2]), "minecraft:black_concrete", server, at);
                for (int i = 3; i <= 5; i++) put(lvl, e, pos.offset(i, 0, 0), "minecraft:gray_concrete", server, at);
                put(lvl, e, pos.offset(5, 1, 0), "minecraft:iron_bars", server, at);
                for (int i = -2; i <= 3; i++) put(lvl, e, pos.offset(i, 2, 0), "minecraft:iron_bars", server, at);
                put(lvl, e, pos.offset(0, 2, 1), "minecraft:campfire", server, at);
                put(lvl, e, pos.offset(-2, 0, 0), "minecraft:barrel[facing=up]{LootTable:\"ez:event/heli\"}", server, at);
                put(lvl, e, pos.offset(-2, 0, 1), "minecraft:barrel[facing=up]{LootTable:\"ez:event/heli\"}", server, at);
                for (int[] g : new int[][]{{3, 3}, {-3, 3}, {0, -3}})
                    Plots.run(server, String.format("execute in lostcities:lostcity positioned %d %d %d run function ez:spawner/rifleman", pos.getX() + g[0], pos.getY(), pos.getZ() + g[1]));
                Plots.run(server, "tag @e[tag=ez.newai] remove ez.newai");
                what = "🚁 A helicopter went down in " + district(pos.getX(), pos.getZ()) + ". Raiders are guarding the crash site.";
            }
            default -> {
                e.ends = System.currentTimeMillis() + 3 * 60_000L;
                Plots.run(server, at + "summon minecraft:marker ~0.5 ~ ~0.5 {Tags:[\"ez.pt\",\"ez.exfil\",\"ez.hot\",\"ez.event\"],CustomName:{text:\"Hot Extract\",color:\"gold\"}}");
                lvl.getEntitiesOfClass(net.minecraft.world.entity.Marker.class, new net.minecraft.world.phys.AABB(pos).inflate(2), m -> m.entityTags().contains("ez.hot"))
                        .stream().findFirst().ifPresent(m -> e.marker = m.getUUID());
                what = "🔥 A hot extract opened in " + district(pos.getX(), pos.getZ()) + " for 3 minutes: valuables extracted there pay double!";
            }
        }
        ACTIVE.add(e);
        for (ServerPlayer p : server.getPlayerList().getPlayers()) {
            if (!Raid.raiding(p)) continue;
            p.sendSystemMessage(t(what, ChatFormatting.YELLOW, ChatFormatting.BOLD));
            Ui.sound(p, net.minecraft.sounds.SoundEvents.FIREWORK_ROCKET_LAUNCH, 1f, 0.7f);
            Raid.State st = Raid.of(p);
            if (st != null && !st.radioUsed && Plots.hasPerk(p, "radio")) {
                st.radioUsed = true;
                int dx = pos.getX() - p.getBlockX(), dz = pos.getZ() - p.getBlockZ();
                p.sendSystemMessage(t("📻 Field Radio: it's at " + pos.getX() + ", " + pos.getZ() + ", " + Math.round(Math.hypot(dx, dz)) + " blocks "
                        + Raid.compass(dx, dz).getString() + " of you.", ChatFormatting.AQUA));
            }
        }
    }

    /** Place a block (only into air or plants, so the city isn't damaged) and remember what was there. */
    static void put(ServerLevel lvl, Ev e, BlockPos p, String block, MinecraftServer server, String at) {
        BlockState was = lvl.getBlockState(p);
        if (!was.isAir() && !was.canBeReplaced()) return;
        e.placed.put(p, was);
        Plots.run(server, String.format("execute in lostcities:lostcity run setblock %d %d %d %s", p.getX(), p.getY(), p.getZ(), block));
    }

    static void end(MinecraftServer server, ServerLevel lvl, Ev e) {
        ACTIVE.remove(e);
        List<BlockPos> rev = new ArrayList<>(e.placed.keySet());
        Collections.reverse(rev);
        for (BlockPos p : rev) {
            if (lvl.getBlockEntity(p) instanceof net.minecraft.world.Container c) c.clearContent();
            lvl.setBlockAndUpdate(p, e.placed.get(p));
        }
        if (e.marker != null) { var m = lvl.getEntity(e.marker); if (m != null) m.discard(); }
        lvl.setChunkForced(e.pos.getX() >> 4, e.pos.getZ() >> 4, false);
    }
}

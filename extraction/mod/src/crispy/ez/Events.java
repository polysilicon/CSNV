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
 * Dynamic zone events (1.1.0; 1.8.0 every 4-6 minutes, placed nearer the centre, four more kinds), while raiders are in the zone:
 *  - Supply drop: a barrel of top-tier loot (ez:event/supply) under a red flare column, for 8 minutes.
 *  - Helicopter crash: a smoking wreck with two crates (ez:event/heli) and three Riflemen guarding it, for 12 minutes.
 *    Since 1.7.1 the wreck is contaminated: radiation within 10 blocks, blocked 25% per hazmat piece worn.
 *  - Hot extract: a temporary extraction point for 3 minutes (a normal ez.exfil marker tagged ez.hot): valuables you
 *    extract with there pay double (Raid.extract).
 * Raiders hear roughly where (the district); a Field Radio on your stash plot gives the exact spot for the first event
 * of each raid. Everything placed is removed again when the event ends (the wreck only replaced air).
 */
final class Events {
    private Events() {}

    enum Kind { SUPPLY, HELI, HOT, CONVOY, HORDE, BOUNTY, LOCKDOWN }   // 1.8.0: the last four
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
                contamination(lvl, e);
            }
        }
        if (nextAt < 0) nextAt = now + 2 * 60_000L;
        if (now >= nextAt && Boss.raidersIn(server)) {
            nextAt = now + (4 + RNG.nextInt(3)) * 60_000L;   // 1.8.0: every 4-6 minutes
            start(server, lvl);
        }
        ambient(server, lvl);
    }

    static String district(int x, int z) {
        int dx = x - Zone.CX, dz = z - Zone.CZ;
        if (Math.hypot(dx, dz) < 120) return "the city centre";
        return "the " + Raid.compass(dx, dz).getString() + " of the city";
    }

    /** 1.8.0: events lean towards the centre (Core 30%, inner 30%, middle 25%, outer 15%), so holding it pays. */
    static int pickRing(int... allowed) {
        int[] w = {0, 15, 25, 30, 30}; int tot = 0;
        for (int r : allowed) tot += w[r];
        int roll = RNG.nextInt(tot);
        for (int r : allowed) { roll -= w[r]; if (roll < 0) return r; }
        return allowed[0];
    }
    static BlockPos spotIn(ServerLevel lvl, int ring) {
        int lo = ring == 4 ? 10 : Zone.RING_R[4 - ring], hi = ring == 1 ? Zone.HALF - 40 : Zone.RING_R[3 - ring];
        for (int tries = 0; tries < 10; tries++) {
            double a = RNG.nextDouble() * Math.PI * 2, r = lo + RNG.nextDouble() * (hi - lo);
            BlockPos b = Zone.street(lvl, Zone.CX + (int) (Math.cos(a) * r), Zone.CZ + (int) (Math.sin(a) * r));
            if (b != null) return b;
        }
        return null;
    }
    static void start(MinecraftServer server, ServerLevel lvl) {
        Kind[] kinds = Kind.values();
        Kind kind = kinds[RNG.nextInt(kinds.length)];
        int ring = switch (kind) { case HORDE -> pickRing(1, 2); case CONVOY -> pickRing(2, 3); case BOUNTY -> pickRing(3, 4); case LOCKDOWN -> 4; default -> pickRing(1, 2, 3, 4); };
        BlockPos pos = null;
        if (kind == Kind.HORDE) {   // on a raider out in the open rings
            List<ServerPlayer> out = lvl.players().stream().filter(pl -> Raid.raiding(pl) && Zone.tier(pl.getBlockX(), pl.getBlockZ()) <= 2).toList();
            if (out.isEmpty()) { kind = Kind.SUPPLY; ring = pickRing(1, 2, 3, 4); }
            else { ServerPlayer v = out.get(RNG.nextInt(out.size())); pos = v.blockPosition(); }
        }
        if (pos == null) pos = spotIn(lvl, ring);
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
                what = "🚁 A helicopter went down in " + district(pos.getX(), pos.getZ()) + ". Raiders guard it, and the wreck is leaking radiation: bring a hazmat suit.";
            }
            case CONVOY -> {
                e.ends = System.currentTimeMillis() + 10 * 60_000L;
                for (int x = -2; x <= 2; x++) for (int z = 0; z <= 1; z++) { put(lvl, e, pos.offset(x, 0, z), "minecraft:green_terracotta", server, at); if (x > -2) put(lvl, e, pos.offset(x, 1, z), "minecraft:green_terracotta", server, at); }
                for (int x : new int[]{-2, 2}) for (int z : new int[]{-1, 2}) put(lvl, e, pos.offset(x, 0, z), "minecraft:black_concrete", server, at);
                put(lvl, e, pos.offset(-3, 0, 0), "minecraft:barrel[facing=up]{LootTable:\"ez:crate/t3\"}", server, at);
                put(lvl, e, pos.offset(-3, 0, 1), "minecraft:barrel[facing=up]{LootTable:\"ez:crate/t3\"}", server, at);
                put(lvl, e, pos.offset(0, 2, 0), "minecraft:campfire", server, at);
                String guard = ring >= 3 ? "rifleman" : "bandit";
                for (int[] g : new int[][]{{4, 2}, {-5, 3}, {0, -3}, {3, -2}})
                    Plots.run(server, String.format("execute in lostcities:lostcity positioned %d %d %d run function ez:spawner/%s", pos.getX() + g[0], pos.getY(), pos.getZ() + g[1], guard));
                Plots.run(server, "tag @e[tag=ez.newai] remove ez.newai");
                what = "🚚 A supply convoy was ambushed in " + district(pos.getX(), pos.getZ()) + ". Its crates are still on the truck, and so are its guards.";
            }
            case HORDE -> {
                e.ends = System.currentTimeMillis() + 60_000L;
                for (int k = 0; k < 8; k++) {
                    double a = RNG.nextDouble() * Math.PI * 2;
                    BlockPos b = Zone.street(lvl, pos.getX() + (int) (Math.cos(a) * 22), pos.getZ() + (int) (Math.sin(a) * 22));
                    if (b != null) Plots.run(server, String.format("execute in lostcities:lostcity positioned %d %d %d run function ez:spawner/infected", b.getX(), b.getY(), b.getZ()));
                }
                Plots.run(server, "tag @e[tag=ez.newai] remove ez.newai");
                lvl.playSound(null, pos, net.minecraft.sounds.SoundEvents.ZOMBIE_AMBIENT, net.minecraft.sounds.SoundSource.HOSTILE, 4f, 0.5f);
                what = "🧟 A horde of infected is closing in around " + district(pos.getX(), pos.getZ()) + ".";
            }
            case BOUNTY -> {
                e.ends = System.currentTimeMillis() + 10 * 60_000L;
                Plots.run(server, at + "function ez:spawner/heavy");
                Plots.run(server, "execute as @e[tag=ez.newai,tag=ez.t_heavy,limit=1] run data merge entity @s {CustomName:{text:\"☠ Bounty: Warlord\",color:\"gold\",bold:true},CustomNameVisible:1b,DeathLootTable:\"ez:event/heli\",PersistenceRequired:1b}");
                Plots.run(server, "execute as @e[tag=ez.newai,tag=ez.t_heavy,limit=1] run tag @s add ez.bounty");
                Plots.run(server, "effect give @e[tag=ez.bounty] minecraft:glowing infinite 0 true");
                for (int[] g : new int[][]{{3, 0}, {-3, 1}})
                    Plots.run(server, String.format("execute in lostcities:lostcity positioned %d %d %d run function ez:spawner/rifleman", pos.getX() + g[0], pos.getY(), pos.getZ() + g[1]));
                Plots.run(server, "tag @e[tag=ez.newai] remove ez.newai");
                what = "🎯 Bounty: a Warlord is moving through " + district(pos.getX(), pos.getZ()) + " with an escort. He's carrying crash-site loot.";
            }
            case LOCKDOWN -> {
                e.ends = System.currentTimeMillis() + 3 * 60_000L;
                // every loaded Core crate: due now (refills within a second, when nobody stands right next to it)
                Plots.run(server, String.format("execute in lostcities:lostcity as @e[type=minecraft:marker,tag=ez.crate,x=%d,y=-64,z=%d,dx=%d,dy=400,dz=%d,scores={ez=4}] run scoreboard players set @s ez.ct -100000",
                        Zone.CX - Zone.RING_R[0], Zone.CZ - Zone.RING_R[0], 2 * Zone.RING_R[0], 2 * Zone.RING_R[0]));
                for (int k = 0; k < 4; k++) {
                    BlockPos b = spotIn(lvl, 4);
                    if (b != null) Plots.run(server, String.format("execute in lostcities:lostcity positioned %d %d %d run function ez:spawner/%s", b.getX(), b.getY(), b.getZ(), k % 2 == 0 ? "heavy" : "rifleman"));
                }
                Plots.run(server, "tag @e[tag=ez.newai] remove ez.newai");
                what = "🚨 Core lockdown: every crate in the Core has been restocked, and reinforcements are moving in. Hold the centre.";
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

    // 1.7.1: the crashed helicopter was carrying something hot. Within RAD_R blocks of the wreck you take RAD_DMG a
    // second; every hazmat piece you wear blocks a quarter of it, a full suit all of it. Green haze marks the area.
    static final double RAD_R = 10, RAD_DMG = 1.5;
    static void contamination(ServerLevel lvl, Ev e) {
        double x = e.pos.getX() + 0.5, y = e.pos.getY(), z = e.pos.getZ() + 0.5;
        for (int i = 0; i < 24; i++) {
            double a = RNG.nextDouble() * Math.PI * 2, r = RAD_R * Math.sqrt(RNG.nextDouble());
            lvl.sendParticles(new DustParticleOptions(0x7CFF4A, 1.6f), x + Math.cos(a) * r, y + 0.4 + RNG.nextDouble() * 2, z + Math.sin(a) * r, 1, 0.1, 0.1, 0.1, 0);
        }
        for (ServerPlayer p : lvl.players()) {
            if (p.isSpectator() || p.isCreative() || Math.hypot(p.getX() - x, p.getZ() - z) > RAD_R || Math.abs(p.getY() - y) > 8) continue;
            int pieces = Armor.pieces(p, "hazmat");
            double dmg = RAD_DMG * (4 - pieces) / 4.0;
            if (dmg > 0) p.hurtServer(lvl, lvl.damageSources().magic(), (float) dmg);
            p.sendSystemMessage(t(pieces == 4 ? "☢ Contaminated wreck: your hazmat suit blocks it all" :
                    "☢ CONTAMINATED: " + String.format("%.2f", dmg) + " damage a second" + (pieces > 0 ? " (hazmat blocks " + pieces * 25 + "%)" : ". A hazmat suit blocks it."),
                    pieces == 4 ? ChatFormatting.YELLOW : ChatFormatting.GREEN, ChatFormatting.BOLD), true);
            if (pieces < 4) Ui.sound(p, net.minecraft.sounds.SoundEvents.BEACON_DEACTIVATE, 0.4f, 2f);
        }
    }

    // 1.8.0 the zone's background: every 20-40 s each raider hears something far off (gunfire, a blast, a
    // helicopter, a siren nearer the Core), from a random direction 60-110 blocks away
    static final Map<UUID, Long> NEXT_AMBIENT = new HashMap<>();
    static final String[][] AMBIENT = {{"minecraft:entity.generic.explode", "0.5"}, {"minecraft:entity.firework_rocket.blast_far", "0.6"},
            {"minecraft:entity.firework_rocket.large_blast_far", "0.5"}, {"minecraft:item.crossbow.shoot", "0.5"}, {"minecraft:entity.iron_golem.hurt", "0.4"},
            {"minecraft:block.bell.resonate", "0.4"}, {"minecraft:entity.zombie.ambient", "0.4"}, {"minecraft:entity.phantom.flap", "0.3"}};
    static void ambient(MinecraftServer server, ServerLevel lvl) {
        long now = System.currentTimeMillis();
        for (ServerPlayer p : lvl.players()) {
            if (!Raid.raiding(p)) continue;
            long next = NEXT_AMBIENT.getOrDefault(p.getUUID(), 0L);
            if (now < next) continue;
            NEXT_AMBIENT.put(p.getUUID(), now + (20 + RNG.nextInt(21)) * 1000L);
            if (next == 0) continue;
            String[] snd = Zone.tier(p.getBlockX(), p.getBlockZ()) >= 3 && RNG.nextInt(4) == 0 ? new String[]{"minecraft:block.beacon.ambient", "0.5"} : AMBIENT[RNG.nextInt(AMBIENT.length)];
            double a = RNG.nextDouble() * Math.PI * 2, d = 60 + RNG.nextInt(50);
            int burst = snd[0].contains("crossbow") ? 3 : 1;
            for (int k = 0; k < burst; k++)
                Plots.run(server, String.format(java.util.Locale.ROOT, "execute in lostcities:lostcity run playsound %s ambient %s %.1f %.1f %.1f 6 %s",
                        snd[0], p.getGameProfile().name(), p.getX() + Math.cos(a) * d, p.getY() + 4, p.getZ() + Math.sin(a) * d, k == 0 ? snd[1] : "0.55"));
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
        if (e.kind == Kind.BOUNTY) Plots.run(server, "kill @e[tag=ez.bounty]");
        lvl.setChunkForced(e.pos.getX() >> 4, e.pos.getZ() >> 4, false);
    }
}

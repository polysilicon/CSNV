package crispy.ez;

import net.fabricmc.fabric.api.command.v2.CommandRegistrationCallback;
import net.fabricmc.fabric.api.event.lifecycle.v1.ServerChunkEvents;
import net.fabricmc.fabric.api.event.lifecycle.v1.ServerTickEvents;
import net.minecraft.commands.Commands;
import net.minecraft.core.BlockPos;
import net.minecraft.core.registries.Registries;
import net.minecraft.resources.Identifier;
import net.minecraft.resources.ResourceKey;
import net.minecraft.server.MinecraftServer;
import net.minecraft.server.level.ServerLevel;
import net.minecraft.server.level.ServerPlayer;
import net.minecraft.world.level.GameType;
import net.minecraft.world.level.Level;
import net.minecraft.world.level.block.entity.BlockEntity;
import net.minecraft.world.level.block.entity.RandomizableContainerBlockEntity;
import net.minecraft.world.level.block.entity.SpawnerBlockEntity;
import net.minecraft.world.level.levelgen.Heightmap;

import java.util.ArrayDeque;
import java.util.ArrayList;
import java.util.Deque;
import java.util.List;
import java.util.Random;

/**
 * The zone is The Lost Cities' city dimension (lostcities:lostcity, profile "extraction"). When one of its chunks
 * inside the zone loads for the first time, its loot chests become Extraction crates (marker ez.crate + tier, refilled
 * by the datapack) or are emptied, and its mob spawners become raider spawn points (marker ez.spawner, nobody spreads
 * them, so raiders appear inside the building). Tier rises toward the centre.
 *
 * Also: game modes (survival in camp so plots can be built, adventure everywhere else) and /ezadmin setup, which puts
 * the extraction points, insertion points and the zone traders on the lowest ground near their target spots (streets,
 * not roofs).
 */
final class Zone {
    private Zone() {}

    static final ResourceKey<Level> CITY = ResourceKey.create(Registries.DIMENSION, Identifier.fromNamespaceAndPath("lostcities", "lostcity"));
    static final int CX = 448, CZ = 448;     // zone centre: lines up with a scale-3 map (64..960), see ZoneMap
    static final int HALF = 400;            // the zone: CX/CZ +- HALF in the city dimension
    static final Deque<long[]> QUEUE = new ArrayDeque<>();   // {x, y, z, kind 0 crate 1 spawner}
    static final Random RNG = new Random();
    static final float CRATE_CHANCE = 0.85f, SPAWNER_CHANCE = 0.35f;

    static int tier(int x, int z) {
        double d = Math.hypot(x - CX, z - CZ);
        return d < 140 ? 3 : d < 280 ? 2 : 1;
    }

    static void init() {
        ServerChunkEvents.CHUNK_LOAD.register((level, chunk, generated) -> {
            if (!level.dimension().equals(CITY)) return;
            int bx = chunk.getPos().getMinBlockX(), bz = chunk.getPos().getMinBlockZ();
            if (bx < CX - HALF - 16 || bx > CX + HALF || bz < CZ - HALF - 16 || bz > CZ + HALF) return;
            for (BlockEntity be : new ArrayList<>(chunk.getBlockEntities().values())) {
                BlockPos p = be.getBlockPos();
                if (be instanceof RandomizableContainerBlockEntity c && c.getLootTable() != null
                        && !c.getLootTable().identifier().getNamespace().equals("ez")) {
                    c.setLootTable(null);   // no vanilla/Lost Cities loot in the zone
                    if (RNG.nextFloat() < CRATE_CHANCE) QUEUE.add(new long[]{p.getX(), p.getY(), p.getZ(), 0});
                } else if (be instanceof SpawnerBlockEntity) {
                    // the city has far more spawners than chests: keep about a third as raider spawn points, remove the rest
                    QUEUE.add(new long[]{p.getX(), p.getY(), p.getZ(), RNG.nextFloat() < SPAWNER_CHANCE ? 1 : 2});
                }
            }
        });
        ServerTickEvents.END_SERVER_TICK.register(server -> {
            for (int n = 0; n < 40 && !QUEUE.isEmpty(); n++) {
                long[] q = QUEUE.poll();
                int x = (int) q[0], y = (int) q[1], z = (int) q[2], t = tier(x, z);
                String at = String.format("execute in lostcities:lostcity positioned %d %d %d ", x, y, z);
                if (q[3] == 0) {
                    Plots.run(server, at + "unless entity @e[type=minecraft:marker,tag=ez.crate,distance=..0.6] run summon minecraft:marker ~0.5 ~ ~0.5 {Tags:[\"ez.crate\",\"ez.new\"]}");
                    Plots.run(server, String.format("scoreboard players set @e[type=minecraft:marker,tag=ez.new] ez %d", t));
                    Plots.run(server, "scoreboard players set @e[type=minecraft:marker,tag=ez.new] ez.ct 0");
                    Plots.run(server, "tag @e[tag=ez.new] remove ez.new");
                } else if (q[3] == 2) {
                    Plots.run(server, at + "run setblock ~ ~ ~ minecraft:air");
                } else {
                    String type = t == 3 ? "raider" : t == 2 ? "bandit" : (RNG.nextBoolean() ? "infected" : "bandit");
                    Plots.run(server, at + "run setblock ~ ~ ~ minecraft:air");
                    Plots.run(server, at + "unless entity @e[type=minecraft:marker,tag=ez.spawner,distance=..2] run summon minecraft:marker ~0.5 ~ ~0.5 {Tags:[\"ez.spawner\",\"ez.nospread\",\"ez.sp_" + type + "\",\"ez.new\"]}");
                    Plots.run(server, "scoreboard players set @e[type=minecraft:marker,tag=ez.new] ez 2");
                    Plots.run(server, "tag @e[tag=ez.new] remove ez.new");
                }
            }
            if (server.getTickCount() % 10 == 0) modes(server);
        });
        CommandRegistrationCallback.EVENT.register((d, ctx, env) -> d.register(Commands.literal("ezadmin")
                .requires(Commands.hasPermission(Commands.LEVEL_GAMEMASTERS))
                .then(Commands.literal("setup").executes(c -> { setup(c.getSource().getServer()); return 1; }))
                .then(Commands.literal("map").executes(c -> { ZoneMap.render(c.getSource().getServer()); return 1; }))));
        ZoneMap.init();
    }

    /** Survival in camp (plots), adventure elsewhere; creative and spectator are left alone. */
    static void modes(MinecraftServer server) {
        for (ServerPlayer p : server.getPlayerList().getPlayers()) {
            GameType g = p.gameMode.getGameModeForPlayer();
            if (g == GameType.CREATIVE || g == GameType.SPECTATOR) continue;
            GameType want = p.level().dimension().equals(Plots.CAMP) ? GameType.SURVIVAL : GameType.ADVENTURE;
            if (g != want) p.setGameMode(want);
        }
    }

    // ---------------------------------------------------------------- setup
    static final int[][] EXFILS = {{0, -360}, {360, 120}, {-330, 330}};
    static final String[] EXFIL_NAMES = {"North Helipad", "East Freight Yard", "South-West Metro"};
    static final int[][] INSERTS = {{-380, -380}, {0, -390}, {380, -380}, {390, 0}, {380, 380}, {0, 390}, {-380, 380}, {-390, 0}};
    static final Object[][] TRADERS = {{"smuggler", "The Smuggler", "dark_green", -120, 60}, {"armsdealer", "Arms Dealer", "dark_red", 150, -90}};

    /** A street spot near (x, z): the lowest point within 32 blocks whose 7 x 7 surroundings are all at the same level
     *  (open street or plaza, not a gap between buildings or a rooftop). Falls back to the lowest point found. */
    static BlockPos ground(ServerLevel lvl, int x, int z) {
        java.util.Map<Long, Integer> h = new java.util.HashMap<>();
        java.util.function.BiFunction<Integer, Integer, Integer> H = (a, b) -> h.computeIfAbsent(((long) a << 32) ^ (b & 0xffffffffL), k -> {
            lvl.getChunk(a >> 4, b >> 4);   // load (and generate) it first, or the heightmap reads as empty
            return lvl.getHeight(Heightmap.Types.MOTION_BLOCKING_NO_LEAVES, a, b);
        });
        BlockPos best = null, low = null;
        for (int dx = -32; dx <= 32; dx += 2) for (int dz = -32; dz <= 32; dz += 2) {
            int cx = x + dx, cz = z + dz, y = H.apply(cx, cz);
            if (y <= lvl.getMinY() + 1) continue;
            if (low == null || y < low.getY()) low = new BlockPos(cx, y, cz);
            if (best != null && y >= best.getY()) continue;
            boolean open = true;
            for (int ox = -3; ox <= 3 && open; ox++) for (int oz = -3; oz <= 3; oz++) {
                int yy = H.apply(cx + ox, cz + oz);
                if (yy != y) { open = false; break; }
            }
            if (open) best = new BlockPos(cx, y, cz);
        }
        return best != null ? best : low;
    }

    static void setup(MinecraftServer server) {
        ServerLevel lvl = server.getLevel(CITY);
        if (lvl == null) return;
        Plots.run(server, "kill @e[type=minecraft:marker,tag=ez.exfil]");
        Plots.run(server, "kill @e[type=minecraft:marker,tag=ez.insert]");
        Plots.run(server, "kill @e[tag=ez.zonetrader]");
        Plots.run(server, "execute in lostcities:lostcity run forceload remove all");
        List<String> done = new ArrayList<>();
        ZoneMap.clearPoints();
        for (int i = 0; i < EXFILS.length; i++) {
            BlockPos b = ground(lvl, CX + EXFILS[i][0], CZ + EXFILS[i][1]);
            ZoneMap.point("exfil", EXFIL_NAMES[i], b);
            Plots.run(server, String.format("execute in lostcities:lostcity run forceload add %d %d", b.getX(), b.getZ()));
            Plots.run(server, String.format("execute in lostcities:lostcity run summon minecraft:marker %d %d %d {Tags:[\"ez.pt\",\"ez.exfil\"],CustomName:{text:\"%s\",color:\"aqua\"}}",
                    b.getX(), b.getY(), b.getZ(), EXFIL_NAMES[i]));
            done.add(EXFIL_NAMES[i] + " " + b.toShortString());
        }
        for (int[] in : INSERTS) {
            BlockPos b = ground(lvl, CX + in[0], CZ + in[1]);
            Plots.run(server, String.format("execute in lostcities:lostcity run forceload add %d %d", b.getX(), b.getZ()));
            Plots.run(server, String.format("execute in lostcities:lostcity run summon minecraft:marker %d %d %d {Tags:[\"ez.pt\",\"ez.insert\"]}", b.getX(), b.getY(), b.getZ()));
        }
        for (Object[] tr : TRADERS) {
            BlockPos b = ground(lvl, CX + (int) tr[3], CZ + (int) tr[4]);
            ZoneMap.point("trader", (String) tr[1], b);
            Plots.run(server, String.format("execute in lostcities:lostcity run forceload add %d %d", b.getX(), b.getZ()));
            Plots.run(server, String.format("execute in lostcities:lostcity run summon minecraft:villager %d %d %d {Tags:[\"ez.npc\",\"ez.zonetrader\",\"ez.shop.%s\"],"
                    + "NoAI:true,Invulnerable:true,PersistenceRequired:true,Silent:true,CustomNameVisible:true,CustomName:{text:\"%s\",color:\"%s\",bold:true},"
                    + "VillagerData:{profession:\"minecraft:cleric\",type:\"minecraft:swamp\",level:5}}", b.getX(), b.getY(), b.getZ(), tr[0], tr[1], tr[2]));
            done.add(tr[1] + " " + b.toShortString());
        }
        ZoneMap.save();
        System.out.println("[crispy-extraction] setup: " + String.join(", ", done));
    }
}

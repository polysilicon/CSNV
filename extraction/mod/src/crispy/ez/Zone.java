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
    static final int HALF = 400;            // the zone: x and z from -HALF to HALF in the city dimension
    static final Deque<long[]> QUEUE = new ArrayDeque<>();   // {x, y, z, kind 0 crate 1 spawner}
    static final Random RNG = new Random();
    static final float CRATE_CHANCE = 0.85f, SPAWNER_CHANCE = 0.35f;

    static int tier(int x, int z) {
        double d = Math.sqrt((double) x * x + (double) z * z);
        return d < 140 ? 3 : d < 280 ? 2 : 1;
    }

    static void init() {
        ServerChunkEvents.CHUNK_LOAD.register((level, chunk, generated) -> {
            if (!level.dimension().equals(CITY)) return;
            int bx = chunk.getPos().getMinBlockX(), bz = chunk.getPos().getMinBlockZ();
            if (bx < -HALF - 16 || bx > HALF || bz < -HALF - 16 || bz > HALF) return;
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
                .then(Commands.literal("setup").executes(c -> { setup(c.getSource().getServer()); return 1; }))));
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

    /** The lowest ground within 24 blocks of (x, z): streets rather than rooftops. */
    static BlockPos ground(ServerLevel lvl, int x, int z) {
        BlockPos best = null;
        for (int dx = -24; dx <= 24; dx += 3) for (int dz = -24; dz <= 24; dz += 3) {
            lvl.getChunk((x + dx) >> 4, (z + dz) >> 4);   // load (and generate) it first, or the heightmap reads as empty
            int y = lvl.getHeight(Heightmap.Types.MOTION_BLOCKING_NO_LEAVES, x + dx, z + dz);
            if (y <= lvl.getMinY() + 1) continue;
            if (best == null || y < best.getY()) best = new BlockPos(x + dx, y, z + dz);
        }
        return best;
    }

    static void setup(MinecraftServer server) {
        ServerLevel lvl = server.getLevel(CITY);
        if (lvl == null) return;
        Plots.run(server, "kill @e[type=minecraft:marker,tag=ez.exfil]");
        Plots.run(server, "kill @e[type=minecraft:marker,tag=ez.insert]");
        Plots.run(server, "kill @e[tag=ez.zonetrader]");
        Plots.run(server, "execute in lostcities:lostcity run forceload remove all");
        List<String> done = new ArrayList<>();
        for (int i = 0; i < EXFILS.length; i++) {
            BlockPos b = ground(lvl, EXFILS[i][0], EXFILS[i][1]);
            Plots.run(server, String.format("execute in lostcities:lostcity run forceload add %d %d", b.getX(), b.getZ()));
            Plots.run(server, String.format("execute in lostcities:lostcity run summon minecraft:marker %d %d %d {Tags:[\"ez.pt\",\"ez.exfil\"],CustomName:{text:\"%s\",color:\"aqua\"}}",
                    b.getX(), b.getY(), b.getZ(), EXFIL_NAMES[i]));
            done.add(EXFIL_NAMES[i] + " " + b.toShortString());
        }
        for (int[] in : INSERTS) {
            BlockPos b = ground(lvl, in[0], in[1]);
            Plots.run(server, String.format("execute in lostcities:lostcity run forceload add %d %d", b.getX(), b.getZ()));
            Plots.run(server, String.format("execute in lostcities:lostcity run summon minecraft:marker %d %d %d {Tags:[\"ez.pt\",\"ez.insert\"]}", b.getX(), b.getY(), b.getZ()));
        }
        for (Object[] tr : TRADERS) {
            BlockPos b = ground(lvl, (int) tr[3], (int) tr[4]);
            Plots.run(server, String.format("execute in lostcities:lostcity run forceload add %d %d", b.getX(), b.getZ()));
            Plots.run(server, String.format("execute in lostcities:lostcity run summon minecraft:villager %d %d %d {Tags:[\"ez.npc\",\"ez.zonetrader\",\"ez.shop.%s\"],"
                    + "NoAI:true,Invulnerable:true,PersistenceRequired:true,Silent:true,CustomNameVisible:true,CustomName:{text:\"%s\",color:\"%s\",bold:true},"
                    + "VillagerData:{profession:\"minecraft:cleric\",type:\"minecraft:swamp\",level:5}}", b.getX(), b.getY(), b.getZ(), tr[0], tr[1], tr[2]));
            done.add(tr[1] + " " + b.toShortString());
        }
        System.out.println("[crispy-extraction] setup: " + String.join(", ", done));
    }
}

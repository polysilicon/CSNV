package crispy.ez;

import net.fabricmc.fabric.api.command.v2.CommandRegistrationCallback;
import net.fabricmc.fabric.api.event.lifecycle.v1.ServerChunkEvents;
import net.fabricmc.fabric.api.event.lifecycle.v1.ServerTickEvents;
import net.fabricmc.fabric.api.event.lifecycle.v1.ServerEntityEvents;
import net.fabricmc.fabric.api.event.player.PlayerBlockBreakEvents;
import net.fabricmc.fabric.api.event.player.UseBlockCallback;
import net.minecraft.ChatFormatting;
import net.minecraft.world.InteractionResult;
import net.minecraft.world.entity.Entity;
import net.minecraft.world.entity.Mob;
import net.minecraft.world.entity.player.Player;
import net.minecraft.world.item.BlockItem;
import net.minecraft.world.phys.AABB;
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
    static final float CRATE_CHANCE = 0.85f, SPAWNER_CHANCE = 0.5f, STREET_SPAWN_CHANCE = 0.2f;   // 1.8.0: livelier
    static final java.util.Queue<Entity> PURGE = new java.util.concurrent.ConcurrentLinkedQueue<>();
    static final int GROUND = 71;           // the profile's groundLevel: outside city chunks nobody digs below it

    /** 1.8.0: four rings, the Core at the centre: the deeper in, the better the loot and the harder the raiders. */
    static final int[] RING_R = {80, 170, 290};          // the Core, inner, middle; outer beyond
    static final int[] RING_CAP = {0, 2, 3, 4, 5};       // raiders a spawn point keeps around it, by ring
    static final String[] RING_NAME = {"", "the outskirts", "the middle ring", "the inner ring", "the Core"};
    static int tier(int x, int z) {
        double d = Math.hypot(x - CX, z - CZ);
        return d < RING_R[0] ? 4 : d < RING_R[1] ? 3 : d < RING_R[2] ? 2 : 1;
    }
    static final java.util.Queue<java.util.UUID> MIGRATE = new java.util.concurrent.ConcurrentLinkedQueue<>();
    static final java.util.Queue<java.util.UUID> UNSTICK = new java.util.concurrent.ConcurrentLinkedQueue<>();
    static int unstuck, removed;
    /** Move a mob out of solid blocks: the nearest spot within 4 (same height +-2) where it fits with ground under it. */
    static void unstick(ServerLevel lvl, Entity m) {
        if (lvl.noCollision(m)) return;
        BlockPos at = m.blockPosition();
        for (int r = 1; r <= 4; r++)
            for (int dy : new int[]{0, 1, -1, 2, -2})
                for (int dx = -r; dx <= r; dx++)
                    for (int dz = -r; dz <= r; dz++) {
                        if (Math.max(Math.abs(dx), Math.abs(dz)) != r) continue;
                        BlockPos q = at.offset(dx, dy, dz);
                        AABB box = m.getType().getDimensions().makeBoundingBox(q.getX() + 0.5, q.getY(), q.getZ() + 0.5);
                        if (lvl.noCollision(m, box) && !lvl.getBlockState(q.below()).getCollisionShape(lvl, q.below()).isEmpty()) {
                            m.teleportTo(q.getX() + 0.5, q.getY(), q.getZ() + 0.5); unstuck++; return;
                        }
                    }
        m.discard(); removed++;
    }

    static void init() {
        ServerChunkEvents.CHUNK_LOAD.register((level, chunk, generated) -> {
            if (!level.dimension().equals(CITY)) return;
            int bx = chunk.getPos().getMinBlockX(), bz = chunk.getPos().getMinBlockZ();
            if (bx < CX - HALF - 16 || bx > CX + HALF || bz < CZ - HALF - 16 || bz > CZ + HALF) return;
            for (BlockEntity be : new ArrayList<>(chunk.getBlockEntities().values()))
                if (be instanceof RandomizableContainerBlockEntity c && c.getLootTable() != null && !c.getLootTable().identifier().getNamespace().equals("ez"))
                    c.setLootTable(null);   // no vanilla/Lost Cities loot in the zone
            // 1.8.9: crates, spawners and furnishing happen once per chunk (Interiors keeps the list), whenever the chunk
            // is loaded and not done yet: the zone map generates chunks and unloads them before a queue gets to them
            long key = net.minecraft.world.level.ChunkPos.pack(chunk.getPos().x(), chunk.getPos().z());
            if (!Interiors.done().contains(key)) Interiors.QUEUE.add(key);
            // fresh street chunks: some get a raider spawn point out in the open, so gunners hold the streets too
            if (generated && RNG.nextFloat() < STREET_SPAWN_CHANCE) {
                int cx = chunk.getPos().x(), cz = chunk.getPos().z();
                Integer street = LC.street(level, cx, cz);
                if (street != null && LC.isStreet(level, cx, cz)) {
                    int x = bx + 4 + RNG.nextInt(8), z = bz + 4 + RNG.nextInt(8);
                    int y = chunk.getHeight(Heightmap.Types.MOTION_BLOCKING_NO_LEAVES, x & 15, z & 15) + 1;
                    if (Math.abs(y - street) <= 1) QUEUE.add(new long[]{x, y, z, 3});
                }
            }
        });
        // no vanilla mobs in the zone or camp: only our raiders (tagged ez.*) and traders
        ServerEntityEvents.ENTITY_LOAD.register((e, level) -> {
            // 1.8.3: a raider that appears inside a wall is moved to open ground (or removed, and the spawner tries again)
            if (e instanceof Mob && level.dimension().equals(CITY) && e.entityTags().contains("ez.ai")) UNSTICK.add(e.getUUID());
            // 1.8.0: crates and spawn points from before the rings get their ring as they load
            if (e instanceof net.minecraft.world.entity.Marker && level.dimension().equals(CITY) && !e.entityTags().contains("ez.v18")
                    && (e.entityTags().contains("ez.crate") || e.entityTags().contains("ez.spawner"))) MIGRATE.add(e.getUUID());
            if (e instanceof Mob && (level.dimension().equals(CITY) || level.dimension().equals(Plots.CAMP))
                    && e.entityTags().stream().noneMatch(t -> t.startsWith("ez."))) PURGE.add(e);
        });
        PlayerBlockBreakEvents.BEFORE.register((world, pl, pos, state, be) -> breakAllowed(pl, world, pos, be));
        UseBlockCallback.EVENT.register((pl, world, hand, hit) -> {
            if (!world.dimension().equals(CITY) || pl.isCreative() || !(pl.getItemInHand(hand).getItem() instanceof BlockItem)) return InteractionResult.PASS;
            if (!nearPoint(world, hit.getBlockPos())) return InteractionResult.PASS;
            if (pl instanceof ServerPlayer sp) sp.sendSystemMessage(Ui.t("You can't build next to an insertion, extraction or trader point.", ChatFormatting.RED), true);
            return InteractionResult.FAIL;
        });
        ServerTickEvents.END_SERVER_TICK.register(server -> {
            for (Entity e; (e = PURGE.poll()) != null; ) if (!e.isRemoved()) e.discard();
            ServerLevel city = server.getLevel(CITY);
            for (java.util.UUID id; city != null && (id = UNSTICK.poll()) != null; ) { Entity m = city.getEntity(id); if (m != null && !m.isRemoved()) unstick(city, m); }
            for (java.util.UUID id; city != null && (id = MIGRATE.poll()) != null; ) {
                Entity m = city.getEntity(id);
                if (m == null || m.entityTags().contains("ez.v18")) continue;
                int t = tier(m.getBlockX(), m.getBlockZ());
                var sb = server.getScoreboard(); var obj = sb.getObjective("ez");
                if (obj == null) continue;
                if (m.entityTags().contains("ez.crate")) sb.getOrCreatePlayerScore(m, obj).set(t);
                else {
                    for (String tg : new ArrayList<>(m.entityTags())) if (tg.startsWith("ez.sp_") || tg.startsWith("ez.ring")) m.removeTag(tg);
                    m.addTag("ez.ring" + t);
                    sb.getOrCreatePlayerScore(m, obj).set(RING_CAP[t]);
                }
                m.addTag("ez.v18");
            }
            for (int n = 0; n < 40 && !QUEUE.isEmpty(); n++) {
                long[] q = QUEUE.poll();
                int x = (int) q[0], y = (int) q[1], z = (int) q[2], t = tier(x, z);
                String at = String.format("execute in lostcities:lostcity positioned %d %d %d ", x, y, z);
                if (q[3] == 0) {
                    Plots.run(server, at + "unless entity @e[type=minecraft:marker,tag=ez.crate,distance=..0.6] run summon minecraft:marker ~ ~ ~ {Tags:[\"ez.crate\",\"ez.new\"]}");
                    Plots.run(server, String.format("scoreboard players set @e[type=minecraft:marker,tag=ez.new] ez %d", t));
                    Plots.run(server, "scoreboard players set @e[type=minecraft:marker,tag=ez.new] ez.ct 0");
                    // 1.8.8: filled now, not when nobody's near (a crate made while you stood by it used to stay empty)
                    Plots.run(server, "execute in lostcities:lostcity as @e[type=minecraft:marker,tag=ez.new] at @s run function ez:crate/refill");
                    Plots.run(server, "tag @e[tag=ez.new] remove ez.new");
                } else if (q[3] == 3) {
                    Plots.run(server, at + "unless entity @e[type=minecraft:marker,tag=ez.spawner,distance=..24] run summon minecraft:marker ~ ~ ~ {Tags:[\"ez.spawner\",\"ez.nospread\",\"ez.street\",\"ez.ring" + t + "\",\"ez.new\"]}");
                    Plots.run(server, "scoreboard players set @e[type=minecraft:marker,tag=ez.new] ez " + RING_CAP[t]);
                    Plots.run(server, "tag @e[tag=ez.new] remove ez.new");
                } else if (q[3] == 2) {
                    Plots.run(server, at + "run setblock ~ ~ ~ minecraft:air");
                } else {
                    Plots.run(server, at + "run setblock ~ ~ ~ minecraft:air");
                    Plots.run(server, at + "unless entity @e[type=minecraft:marker,tag=ez.spawner,distance=..2] run summon minecraft:marker ~ ~ ~ {Tags:[\"ez.spawner\",\"ez.nospread\",\"ez.ring" + t + "\",\"ez.new\"]}");
                    Plots.run(server, "scoreboard players set @e[type=minecraft:marker,tag=ez.new] ez " + RING_CAP[t]);
                    Plots.run(server, "tag @e[tag=ez.new] remove ez.new");
                }
            }
            if (server.getTickCount() % 10 == 0) modes(server);
            if (server.getTickCount() % 200 == 0) keepTraders(server);
            Interiors.tick(server);
        });
        CommandRegistrationCallback.EVENT.register((d, ctx, env) -> d.register(Commands.literal("ezadmin")
                .requires(Commands.hasPermission(Commands.LEVEL_GAMEMASTERS))
                .then(Commands.literal("setup").executes(c -> { setup(c.getSource().getServer()); return 1; }))
                .then(Commands.literal("map").executes(c -> { ZoneMap.render(c.getSource().getServer()); return 1; }))));
        ZoneMap.init();
    }

    /** Survival everywhere (build and break: camp plots and the zone have their own rules); creative and spectator are left alone. */
    static void modes(MinecraftServer server) {
        for (ServerPlayer p : server.getPlayerList().getPlayers()) {
            GameType g = p.gameMode.getGameModeForPlayer();
            if (g == GameType.CREATIVE || g == GameType.SPECTATOR) continue;
            GameType want = GameType.SURVIVAL;   // camp plots are protected by Plots, the zone by breakAllowed
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
        BlockPos s = street(lvl, x, z);
        if (s != null) return s;
        System.out.println("[crispy-extraction] no street near " + x + " " + z + ", using the lowest open spot");
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

    /** The middle of the nearest street chunk to (x, z): a city chunk with no building in it, where the ground is at
     *  the city's street level (not a raised highway or a pile of rubble) and the 5 x 5 around the spot is open and
     *  level. Null if none within 6 chunks or Lost Cities can't be asked. */
    static BlockPos street(ServerLevel lvl, int x, int z) {
        int ccx = x >> 4, ccz = z >> 4;
        BlockPos best = null; double bestD = Double.MAX_VALUE;
        for (int r = 0; r <= 6 && best == null; r++) {          // rings outward: the nearest street wins
            for (int dx = -r; dx <= r; dx++) for (int dz = -r; dz <= r; dz++) {
                if (Math.max(Math.abs(dx), Math.abs(dz)) != r) continue;
                int cx = ccx + dx, cz = ccz + dz;
                if (!LC.isStreet(lvl, cx, cz)) continue;
                int street = LC.street(lvl, cx, cz);
                lvl.getChunk(cx, cz);
                for (int[] o : new int[][]{{8, 8}, {4, 4}, {12, 12}, {4, 12}, {12, 4}}) {
                    int px = (cx << 4) + o[0], pz = (cz << 4) + o[1];
                    int y = lvl.getHeight(Heightmap.Types.MOTION_BLOCKING_NO_LEAVES, px, pz);
                    if (y < street || y > street + 1) continue;      // on the street surface, nothing piled on it
                    boolean open = true;
                    for (int ox = -2; ox <= 2 && open; ox++) for (int oz = -2; oz <= 2; oz++)
                        if (lvl.getHeight(Heightmap.Types.MOTION_BLOCKING_NO_LEAVES, px + ox, pz + oz) != y) { open = false; break; }
                    if (!open) continue;
                    double d = Math.hypot(px - x, pz - z);
                    if (d < bestD) { bestD = d; best = new BlockPos(px, y, pz); }
                    break;
                }
            }
        }
        return best;
    }

    /** Building in the zone: anything above street level goes, except containers (the loot crates) and the ground
     *  around insertion, extraction and trader points. Nothing at or below street level, so nobody tunnels under the
     *  city or into cellars through the floor. */
    static boolean breakAllowed(Player pl, Level world, BlockPos pos, BlockEntity be) {
        if (!world.dimension().equals(CITY) || pl.isCreative()) return true;
        String why = null;
        Integer street = LC.street((ServerLevel) world, pos.getX() >> 4, pos.getZ() >> 4);
        int floor = street != null ? street - 1 : GROUND;   // street = first air block, so the street surface is street - 1
        if (pos.getY() <= floor) why = "You can't dig into the ground here.";
        else if (be instanceof net.minecraft.world.Container) why = "Crates and containers can't be broken.";
        else if (nearPoint(world, pos)) why = "You can't break blocks next to an insertion, extraction or trader point.";
        if (why == null) return true;
        if (pl instanceof ServerPlayer sp) sp.sendSystemMessage(Ui.t(why, ChatFormatting.RED), true);
        return false;
    }

    static boolean nearPoint(Level world, BlockPos pos) {
        return !world.getEntitiesOfClass(Entity.class, new AABB(pos).inflate(4),
                e -> e.entityTags().contains("ez.pt") || e.entityTags().contains("ez.zonetrader")).isEmpty();
    }

    /** The Lost Cities, asked by reflection (so this mod compiles and loads without it). */
    static final class LC {
        static Object imp; static java.lang.reflect.Method getInfo, chunkInfo, realHeight, isCity, building, cityLevel;
        static boolean failed;
        static Object chunk(ServerLevel lvl, int cx, int cz) {
            if (failed) return null;
            try {
                if (imp == null) {
                    imp = Class.forName("mcjty.lostcities.LostCities").getField("lostCitiesImp").get(null);
                    getInfo = Class.forName("mcjty.lostcities.api.ILostCities").getMethod("getLostInfo", Level.class);
                    Class<?> i = Class.forName("mcjty.lostcities.api.ILostCityInformation"), c = Class.forName("mcjty.lostcities.api.ILostChunkInfo");
                    chunkInfo = i.getMethod("getChunkInfo", int.class, int.class); realHeight = i.getMethod("getRealHeight", int.class);
                    isCity = c.getMethod("isCity"); building = c.getMethod("getBuildingType"); cityLevel = c.getMethod("getCityLevel");
                }
                Object info = getInfo.invoke(imp, lvl);
                return info == null ? null : new Object[]{info, chunkInfo.invoke(info, cx, cz)};
            } catch (Throwable t) {
                failed = true;
                System.err.println("[crispy-extraction] can't ask Lost Cities about chunks: " + t);
                return null;
            }
        }
        /** The first air block above the street in this chunk, or null outside cities. */
        static Integer street(ServerLevel lvl, int cx, int cz) {
            try {
                if (!(chunk(lvl, cx, cz) instanceof Object[] a) || a[1] == null || !(boolean) isCity.invoke(a[1])) return null;
                return (int) realHeight.invoke(a[0], (int) cityLevel.invoke(a[1])) + 1;
            } catch (Throwable t) { return null; }
        }
        static boolean isStreet(ServerLevel lvl, int cx, int cz) {
            try {
                return chunk(lvl, cx, cz) instanceof Object[] a && a[1] != null && (boolean) isCity.invoke(a[1]) && building.invoke(a[1]) == null;
            } catch (Throwable t) { return false; }
        }
    }

    /** 1.8.3: every zone trader stands at its map point: summoned when missing, strays (old setups) removed. */
    /** 1.8.9: make a loot crate at a block now (call while its chunk is loaded): marker with its ring's tier, filled. */
    static void makeCrate(MinecraftServer server, BlockPos p) {
        String at = String.format("execute in lostcities:lostcity positioned %d %d %d ", p.getX(), p.getY(), p.getZ());
        Plots.run(server, at + "unless entity @e[type=minecraft:marker,tag=ez.crate,distance=..0.6] run summon minecraft:marker ~ ~ ~ {Tags:[\"ez.crate\",\"ez.v18\",\"ez.new\"]}");
        Plots.run(server, "scoreboard players set @e[type=minecraft:marker,tag=ez.new] ez " + tier(p.getX(), p.getZ()));
        Plots.run(server, "execute in lostcities:lostcity as @e[type=minecraft:marker,tag=ez.new] at @s run function ez:crate/refill");
        Plots.run(server, "tag @e[tag=ez.new] remove ez.new");
    }
    /** 1.8.9: a raider spawn point at a block now (a former mob spawner). */
    static void makeSpawnPoint(MinecraftServer server, BlockPos p) {
        int t = tier(p.getX(), p.getZ());
        String at = String.format("execute in lostcities:lostcity positioned %d %d %d ", p.getX(), p.getY(), p.getZ());
        Plots.run(server, at + "unless entity @e[type=minecraft:marker,tag=ez.spawner,distance=..2] run summon minecraft:marker ~ ~ ~ {Tags:[\"ez.spawner\",\"ez.nospread\",\"ez.v18\",\"ez.ring" + t + "\",\"ez.new\"]}");
        Plots.run(server, "scoreboard players set @e[type=minecraft:marker,tag=ez.new] ez " + RING_CAP[t]);
        Plots.run(server, "tag @e[tag=ez.new] remove ez.new");
    }

    static void keepTraders(MinecraftServer server) {
        ServerLevel lvl = server.getLevel(CITY);
        if (lvl == null) return;
        Shops.load(server);
        for (Object[] tr : TRADERS) {
            ZoneMap.Pt pt = ZoneMap.d().points.stream().filter(q -> q.kind().equals("trader") && q.name().equals(tr[1])).findFirst().orElse(null);
            if (pt == null || !lvl.hasChunk(pt.x() >> 4, pt.z() >> 4)) continue;
            String tag = "ez.shop." + tr[0];
            // 1.8.13: exactly on the marker's column (searching again could pick another spot once the street changed)
            BlockPos b = new BlockPos(pt.x(), lvl.getHeight(Heightmap.Types.MOTION_BLOCKING_NO_LEAVES, pt.x(), pt.z()), pt.z());
            var here = lvl.getEntities((Entity) null, new AABB(b).inflate(3), e -> e.entityTags().contains(tag));
            if (here.isEmpty()) {   // room to stand: clear a street piece in that exact spot
                for (BlockPos q : new BlockPos[]{b, b.above()}) if (!lvl.getBlockState(q).isAir()) lvl.setBlock(q, net.minecraft.world.level.block.Blocks.AIR.defaultBlockState(), 2);
            }
            for (Entity e : lvl.getEntities((Entity) null, new AABB(b).inflate(400), e -> e.entityTags().contains(tag) && !here.contains(e))) e.discard();
            if (!here.isEmpty()) continue;
            String skin = Shops.SKINS.getOrDefault((String) tr[0], "");
            Plots.run(server, String.format("execute in lostcities:lostcity run summon minecraft:mannequin %d %d %d {Tags:[\"ez.npc\",\"ez.zonetrader\",\"ez.shop.%s\"],"
                    + "Invulnerable:true,immovable:true,hide_description:true,CustomNameVisible:true,CustomName:{text:\"%s\",color:\"%s\",bold:true}%s}",
                    b.getX(), b.getY(), b.getZ(), tr[0], tr[1], tr[2],
                    skin.isEmpty() ? "" : ",profile:{properties:[{name:\"textures\",value:\"" + skin + "\"}]}"));
            System.out.println("[crispy-extraction] zone trader placed: " + tr[1] + " at " + b.toShortString());
        }
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
            done.add("insert " + b.toShortString() + " street=" + LC.street(lvl, b.getX() >> 4, b.getZ() >> 4));
        }
        for (Object[] tr : TRADERS) {
            BlockPos b = ground(lvl, CX + (int) tr[3], CZ + (int) tr[4]);
            ZoneMap.point("trader", (String) tr[1], b);
            Plots.run(server, String.format("execute in lostcities:lostcity run forceload add %d %d", b.getX(), b.getZ()));
            // 1.8.3: placed by keepTraders() once the chunk is loaded (a summon into a chunk forceloaded this tick is dropped)
            done.add(tr[1] + " " + b.toShortString());
        }
        ZoneMap.save();
        System.out.println("[crispy-extraction] setup: " + String.join(", ", done));
    }
}

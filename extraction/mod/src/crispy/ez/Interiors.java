package crispy.ez;

import net.fabricmc.fabric.api.event.player.UseBlockCallback;
import net.minecraft.ChatFormatting;
import net.minecraft.commands.arguments.blocks.BlockStateParser;
import net.minecraft.core.BlockPos;
import net.minecraft.core.Direction;
import net.minecraft.core.registries.BuiltInRegistries;
import net.minecraft.core.registries.Registries;
import net.minecraft.server.MinecraftServer;
import net.minecraft.server.level.ServerLevel;
import net.minecraft.server.level.ServerPlayer;
import net.minecraft.world.InteractionResult;
import net.minecraft.world.level.block.Blocks;
import net.minecraft.world.level.block.DoorBlock;
import net.minecraft.world.level.block.LadderBlock;
import net.minecraft.world.level.block.StairBlock;
import net.minecraft.world.level.block.TrapDoorBlock;
import net.minecraft.world.level.block.entity.BlockEntity;
import net.minecraft.world.level.block.entity.SpawnerBlockEntity;
import net.minecraft.world.level.block.state.BlockState;
import net.minecraft.world.level.block.state.properties.BlockStateProperties;
import net.minecraft.world.level.chunk.LevelChunk;

import java.util.*;
import java.util.concurrent.ConcurrentLinkedQueue;

/**
 * Furnished ruins (1.8.4; themed in 1.8.8). Each newly generated zone chunk gets one pass:
 *  - Buildings: every floor of a chunk picks a room theme (office, barracks, storage, clinic, workshop, mess hall,
 *    ransacked) and dresses its rooms: props against the walls (tables, chairs, shelves, lockers, stations ...), a few on
 *    the floor (carpet, rubble), cobwebs high in corners; storage rooms get a loot barrel or two (real crates). Never in
 *    a one-wide corridor and never next to a door, trapdoor, ladder or stairs, so every route stays open.
 *  - The Lost Cities' crafting tables and furnaces become our station blocks (Tool / Reloading Bench, Kiln / Still).
 *  - Streets: now and then a sandbag line, a barricade, a burnt-out car or debris, only where there's room all round.
 *  - Mob spawners: removed (the queued removal in Zone can miss a chunk that unloaded; this and a sweep round raiders
 *    every 30 s catch the rest).
 * Station blocks in the zone are wreckage: right-clicking one says to build your own in your bunker (no vanilla screen,
 * no empty furnace to stash things in).
 */
final class Interiors {
    private Interiors() {}

    static final Queue<Long> QUEUE = new ConcurrentLinkedQueue<>();
    // 1.8.9: chunks already done (crates, spawners, furnishing), kept across restarts; cleared at a city reset
    static final java.nio.file.Path DONE_FILE = java.nio.file.Path.of("config", "crispy_extraction", "zone_chunks.txt");
    static Set<Long> done;
    static int sinceSave;
    static Set<Long> done() {
        if (done == null) {
            done = Collections.synchronizedSet(new HashSet<>());
            try { if (java.nio.file.Files.exists(DONE_FILE)) for (String l : java.nio.file.Files.readAllLines(DONE_FILE)) if (!l.isBlank()) done.add(Long.parseLong(l.trim())); }
            catch (Exception e) { System.err.println("[crispy-extraction] zone_chunks.txt: " + e); }
        }
        return done;
    }
    static void markDone(long key) {
        done().add(key);
        if (++sinceSave >= 20) saveDone();
    }
    static void saveDone() {
        sinceSave = 0;
        try { StringBuilder b = new StringBuilder(); synchronized (done) { for (long k : done) b.append(k).append('\n'); }
              java.nio.file.Files.createDirectories(DONE_FILE.getParent()); java.nio.file.Files.writeString(DONE_FILE, b); }
        catch (Exception e) { System.err.println("[crispy-extraction] zone_chunks.txt: " + e); }
    }
    static final Map<String, BlockState> CACHE = new HashMap<>();
    static int furnished, props, swapped, spawnersRemoved, streetBits, barrels;

    record Theme(String name, String[] wall, String[] floor, float wallP, float floorP, float web, int crates) {}
    // wall props: a block id, or TABLE / CHAIR / SHELF2 / LOCKER / STACK / COUNTER / BEDROLL
    static final Theme[] THEMES = {
        new Theme("office", new String[]{"SHELFRUN", "SHELF2", "TABLE", "TABLE", "CHAIR", "CHAIR", "minecraft:lectern", "minecraft:chiseled_bookshelf", "minecraft:potted_dead_bush", "minecraft:candle[candles=2,lit=false]"},
                new String[]{"minecraft:gray_carpet", "minecraft:light_gray_carpet"}, 0.16f, 0.040f, 0.03f, 1),
        new Theme("barracks", new String[]{"BEDROLL", "BEDROLL", "BEDROLL", "LOCKER", "LOCKER", "minecraft:mud_brick_wall", "CHAIR", "minecraft:lantern"},
                new String[]{"minecraft:brown_carpet", "minecraft:green_carpet"}, 0.18f, 0.030f, 0.03f, 1),
        new Theme("storage", new String[]{"SHELFRUN", "STACK", "STACK", "STACK", "minecraft:hay_block", "minecraft:mud_brick_wall", "minecraft:chipped_anvil", "CRATE"},
                new String[]{"minecraft:cobblestone_slab", "minecraft:spruce_slab"}, 0.20f, 0.030f, 0.05f, 3),
        new Theme("clinic", new String[]{"COUNTER", "COUNTER", "minecraft:brewing_stand", "minecraft:cauldron", "BEDROLL", "minecraft:candle[candles=3,lit=false]", "minecraft:potted_dead_bush"},
                new String[]{"minecraft:white_carpet", "minecraft:light_gray_carpet"}, 0.16f, 0.040f, 0.02f, 1),
        new Theme("workshop", new String[]{"minecraft:stonecutter", "minecraft:fletching_table", "minecraft:smithing_table", "minecraft:chipped_anvil", "minecraft:grindstone[face=floor]", "STACK", "TABLE", "minecraft:lantern"},
                new String[]{"minecraft:cobblestone_slab", "minecraft:gray_carpet"}, 0.18f, 0.030f, 0.04f, 2),
        new Theme("mess", new String[]{"TABLE", "TABLE", "CHAIR", "CHAIR", "CHAIR", "minecraft:smoker", "minecraft:blast_furnace", "minecraft:cauldron", "COUNTER"},
                new String[]{"minecraft:brown_carpet"}, 0.18f, 0.020f, 0.03f, 1),
        new Theme("fortified", new String[]{"minecraft:mud_brick_wall", "minecraft:mud_brick_wall", "minecraft:iron_bars", "STACK", "CRATE", "minecraft:cobweb", "minecraft:chipped_anvil"},
                new String[]{"minecraft:cobweb", "minecraft:cobblestone_slab", "minecraft:gravel"}, 0.22f, 0.060f, 0.06f, 2),
        new Theme("ransacked", new String[]{"STACK", "minecraft:mud_brick_wall", "minecraft:cobblestone_slab", "CHAIR", "SHELF2"},
                new String[]{"minecraft:cobblestone_slab", "minecraft:andesite_slab", "minecraft:gravel", "minecraft:gray_carpet"}, 0.10f, 0.080f, 0.10f, 1),
    };
    static final Set<String> STATION_BLOCKS = Set.of("minecraft:loom", "minecraft:brewing_stand", "minecraft:blast_furnace", "minecraft:fletching_table",
            "minecraft:smoker", "minecraft:stonecutter", "minecraft:smithing_table");

    static BlockState state(ServerLevel lvl, String s) {
        return CACHE.computeIfAbsent(s, k -> {
            try { return BlockStateParser.parseForBlock(lvl.holderLookup(Registries.BLOCK), k, false).blockState(); }
            catch (Exception e) { return Blocks.AIR.defaultBlockState(); }
        });
    }
    static boolean solid(ServerLevel lvl, BlockPos p) { return lvl.getBlockState(p).isFaceSturdy(lvl, p, Direction.UP) && lvl.getBlockState(p).isCollisionShapeFullBlock(lvl, p); }
    static boolean route(BlockState s) {
        return s.getBlock() instanceof DoorBlock || s.getBlock() instanceof TrapDoorBlock || s.getBlock() instanceof LadderBlock || s.getBlock() instanceof StairBlock;
    }
    static void set(ServerLevel lvl, BlockPos p, String s) { lvl.setBlock(p, state(lvl, s), 2); }

    static void tick(MinecraftServer server) {
        ServerLevel lvl = server.getLevel(Zone.CITY);
        if (lvl == null) return;
        if (server.getTickCount() % 600 == 300) sweep(server, lvl);
        for (int i = 0; i < 3; i++) { Long key = QUEUE.poll(); if (key == null) return; one(server, lvl, key); }
    }
    static void one(MinecraftServer server, ServerLevel lvl, long key) {
        int cx = net.minecraft.world.level.ChunkPos.getX(key), cz = net.minecraft.world.level.ChunkPos.getZ(key);
        if (!lvl.hasChunk(cx, cz) || done().contains(key)) return;   // unloaded again: it's queued next time it loads
        LevelChunk ch = lvl.getChunk(cx, cz);
        Random rng = new Random(key * 7 + 1);
        // spawners: about half become raider spawn points; chests and barrels: loot barrels, filled now
        for (BlockEntity be : new ArrayList<>(ch.getBlockEntities().values())) {
            BlockPos p = be.getBlockPos();
            if (be instanceof SpawnerBlockEntity) {
                lvl.setBlock(p, Blocks.AIR.defaultBlockState(), 2); spawnersRemoved++;
                if (rng.nextFloat() < Zone.SPAWN_POINT_CHANCE[Zone.tier(p.getX(), p.getZ())]) Zone.makeSpawnPoint(server, p);
            } else if (be instanceof net.minecraft.world.level.block.entity.ChestBlockEntity || be instanceof net.minecraft.world.level.block.entity.BarrelBlockEntity) {
                crateOrClear(server, lvl, p, rng);
            }
        }
        Integer street = Zone.LC.street(lvl, cx, cz);
        if (street != null) {
            if (Zone.LC.isStreet(lvl, cx, cz)) streetDetail(server, lvl, cx, cz, street, key);
            else furnish(server, lvl, cx, cz, street, key);
        }
        markDone(key);
    }

    /** 1.8.11: loot belongs indoors. A container in a street chunk or under open sky becomes a crate one time in four
     *  (the rest are removed); one inside a building always does. */
    static void crateOrClear(MinecraftServer server, ServerLevel lvl, BlockPos p, Random rng) {
        boolean outside = Zone.LC.isStreet(lvl, p.getX() >> 4, p.getZ() >> 4) || lvl.canSeeSky(p.above());
        if (outside && rng.nextFloat() >= 0.25f) { lvl.removeBlockEntity(p); lvl.setBlock(p, Blocks.AIR.defaultBlockState(), 2); clearedOutside++; return; }
        Zone.makeCrate(server, p);
    }
    static int clearedOutside;

    static void removeSpawners(ServerLevel lvl, LevelChunk ch) {
        for (BlockEntity be : new ArrayList<>(ch.getBlockEntities().values()))
            if (be instanceof SpawnerBlockEntity) { lvl.setBlock(be.getBlockPos(), Blocks.AIR.defaultBlockState(), 2); spawnersRemoved++; }
    }
    /** 1.8.9: every 30 s, over every loaded zone chunk: a chest becomes a filled loot barrel, a mob spawner a raider spawn
     *  point (or nothing), and a chunk not furnished yet is queued. Block entities can appear a moment after a chunk
     *  counts as loaded, so a one-time pass at load can miss them. */
    static void sweep(MinecraftServer server, ServerLevel lvl) {
        Random rng = new Random(server.getTickCount());
        for (int cx = (Zone.CX - Zone.HALF) >> 4; cx <= (Zone.CX + Zone.HALF) >> 4; cx++)
            for (int cz = (Zone.CZ - Zone.HALF) >> 4; cz <= (Zone.CZ + Zone.HALF) >> 4; cz++) {
                if (!lvl.hasChunk(cx, cz)) continue;
                LevelChunk ch = lvl.getChunk(cx, cz);
                for (BlockEntity be : new ArrayList<>(ch.getBlockEntities().values())) {
                    BlockPos p = be.getBlockPos();
                    if (be instanceof SpawnerBlockEntity) {
                        lvl.setBlock(p, Blocks.AIR.defaultBlockState(), 2); spawnersRemoved++;
                        if (rng.nextFloat() < Zone.SPAWN_POINT_CHANCE[Zone.tier(p.getX(), p.getZ())]) Zone.makeSpawnPoint(server, p);
                    } else if (be instanceof net.minecraft.world.level.block.entity.ChestBlockEntity) { crateOrClear(server, lvl, p, rng); swept++; }
                }
                long key = net.minecraft.world.level.ChunkPos.pack(cx, cz);
                if (!done().contains(key) && !QUEUE.contains(key)) QUEUE.add(key);
            }
    }
    static int swept;

    static void furnish(MinecraftServer server, ServerLevel lvl, int cx, int cz, int street, long key) {
        Random rng = new Random(key * 31 + 7);
        int ring = Zone.tier((cx << 4) + 8, (cz << 4) + 8);
        damage(lvl, cx << 4, cz << 4, street, ring, rng);
        List<BlockPos> placed = new ArrayList<>();
        int bx = cx << 4, bz = cz << 4;
        // the Lost Cities' crafting tables and furnaces become our station blocks
        for (int y = street - 8; y <= street + 44; y++)
            for (int x = bx; x < bx + 16; x++)
                for (int z = bz; z < bz + 16; z++) {
                    BlockPos p = new BlockPos(x, y, z);
                    BlockState st = lvl.getBlockState(p);
                    if (st.is(Blocks.CRAFTING_TABLE)) { set(lvl, p, rng.nextBoolean() ? "minecraft:stonecutter" : "minecraft:fletching_table"); swapped++; }
                    else if (st.is(Blocks.FURNACE)) {
                        Direction f = st.hasProperty(BlockStateProperties.HORIZONTAL_FACING) ? st.getValue(BlockStateProperties.HORIZONTAL_FACING) : Direction.NORTH;
                        lvl.removeBlockEntity(p);
                        set(lvl, p, (rng.nextBoolean() ? "minecraft:blast_furnace" : "minecraft:smoker") + "[facing=" + f.getSerializedName() + "]"); swapped++;
                    }
                }
        Map<Integer, Theme> themeOf = new HashMap<>();
        Map<Integer, Integer> cratesOn = new HashMap<>();
        for (int y = street - 6; y <= street + 40; y++)
            for (int x = bx + 1; x < bx + 15; x++)
                for (int z = bz + 1; z < bz + 15; z++) {
                    BlockPos p = new BlockPos(x, y, z);
                    if (!lvl.getBlockState(p).isAir() || !lvl.getBlockState(p.above()).isAir() || !solid(lvl, p.below())) continue;
                    boolean roofed = false;
                    for (int k = 2; k <= 6 && !roofed; k++) roofed = !lvl.getBlockState(p.above(k)).isAir();
                    if (!roofed) continue;
                    boolean n = solid(lvl, p.north()), so = solid(lvl, p.south()), e = solid(lvl, p.east()), w = solid(lvl, p.west());
                    if ((n && so) || (e && w)) continue;   // a corridor
                    boolean near = false;
                    for (int dx = -1; dx <= 1 && !near; dx++) for (int dz = -1; dz <= 1 && !near; dz++) for (int dy = -1; dy <= 1 && !near; dy++)
                        near = route(lvl.getBlockState(p.offset(dx, dy, dz)));
                    if (near) continue;
                    if (placed.stream().anyMatch(q -> q.distManhattan(p) < 2)) continue;   // 1.8.15: denser
                    final int fy = y;
                    Theme th = themeOf.computeIfAbsent(fy, k -> pickTheme(new Random(key * 131 + fy * 7L), ring));
                    int walls = (n ? 1 : 0) + (so ? 1 : 0) + (e ? 1 : 0) + (w ? 1 : 0);
                    if (walls == 1 && rng.nextFloat() < th.wallP()) {
                        Direction toWall = n ? Direction.NORTH : so ? Direction.SOUTH : e ? Direction.EAST : Direction.WEST;
                        String pick = th.wall()[rng.nextInt(th.wall().length)];
                        if (pick.equals("CRATE") || (th.crates() > 0 && cratesOn.getOrDefault(fy, 0) < th.crates() && rng.nextFloat() < 0.35f)) {
                            if (cratesOn.getOrDefault(fy, 0) >= th.crates()) pick = "STACK";
                            else {   // a loot barrel: a real crate (Zone fills it now and refills it like any other)
                                set(lvl, p, "minecraft:barrel[facing=up]");
                                Zone.makeCrate(server, p);
                                cratesOn.merge(fy, 1, Integer::sum); barrels++; placed.add(p); props++;
                                continue;
                            }
                        }
                        prop(lvl, p, pick, toWall, rng);
                        placed.add(p); props++;
                    } else if (walls == 2 && rng.nextFloat() < th.web() && lvl.getBlockState(p.above(2)).isAir() && !lvl.getBlockState(p.above(3)).isAir()) {
                        set(lvl, p.above(2), "minecraft:cobweb");   // high in the corner, over head height
                        placed.add(p); props++;
                    } else if (walls == 0 && ring >= 3 && rng.nextFloat() < (ring == 4 ? 0.035f : 0.02f)) {
                        set(lvl, p, "minecraft:cobweb");   // razor wire: slows you, never seals a room (props stay 3 apart)
                        placed.add(p); props++;
                    } else if (walls == 0 && rng.nextFloat() < th.floorP()) {
                        String f = th.floor()[rng.nextInt(th.floor().length)];
                        set(lvl, p, f);
                        if (f.endsWith("_carpet"))   // a rug: 2x2 where the floor allows
                            for (BlockPos q : new BlockPos[]{p.east(), p.south(), p.east().south()})
                                if (lvl.getBlockState(q).isAir() && solid(lvl, q.below())) set(lvl, q, f);
                        placed.add(p); props++;
                    } else if (walls == 0 && rng.nextFloat() < 0.012f) {   // a light hanging from the ceiling, over head height
                        for (int k = 3; k <= 5; k++) {
                            if (!lvl.getBlockState(p.above(k)).isAir()) {
                                if (k >= 3 && lvl.getBlockState(p.above(k - 1)).isAir()) { set(lvl, p.above(k - 1), "minecraft:lantern[hanging=true]"); props++; }
                                break;
                            }
                        }
                    }
                }
        furnished++;
    }

    /** 1.8.12: deeper rings lean to ransacked and fortified rooms (the outskirts are mostly lived-in). */
    static Theme pickTheme(Random r, int ring) {
        int[] extraRansacked = {0, 0, 2, 4, 6}, fortified = {0, 0, 0, 3, 5};
        List<Theme> bag = new ArrayList<>();
        for (Theme t : THEMES) {
            int w = t.name().equals("ransacked") ? 1 + extraRansacked[ring] : t.name().equals("fortified") ? fortified[ring] : 2;
            for (int i = 0; i < w; i++) bag.add(t);
        }
        return bag.get(r.nextInt(bag.size()));
    }
    /** 1.8.12: the deeper the ring, the rougher the building: windows blown out, cracked stone, scorch marks in the Core.
     *  Only swaps blocks for blocks of the same solidity (glass for air or bars, bricks for cracked bricks), so nothing
     *  that was walkable stops being walkable and no wall opens onto a fall. */
    static void damage(ServerLevel lvl, int bx, int bz, int street, int ring, Random rng) {
        float[] glass = {0, 0, 0.25f, 0.5f, 0.7f}, crack = {0, 0, 0.1f, 0.25f, 0.4f}, scorch = {0, 0, 0, 0.02f, 0.06f};
        if (ring < 2) return;
        for (int y = street - 1; y <= street + 44; y++)
            for (int x = bx; x < bx + 16; x++)
                for (int z = bz; z < bz + 16; z++) {
                    BlockPos p = new BlockPos(x, y, z);
                    BlockState st = lvl.getBlockState(p);
                    if (st.isAir()) continue;
                    String id = BuiltInRegistries.BLOCK.getKey(st.getBlock()).getPath();
                    if (id.contains("glass")) {
                        if (rng.nextFloat() < glass[ring]) set(lvl, p, ring == 4 && rng.nextFloat() < 0.15f ? "minecraft:iron_bars" : "minecraft:air");
                    } else if (rng.nextFloat() < crack[ring]) {
                        String to = switch (id) { case "stone_bricks" -> "minecraft:cracked_stone_bricks"; case "deepslate_bricks" -> "minecraft:cracked_deepslate_bricks";
                            case "deepslate_tiles" -> "minecraft:cracked_deepslate_tiles"; case "polished_blackstone_bricks" -> "minecraft:cracked_polished_blackstone_bricks";
                            case "nether_bricks" -> "minecraft:cracked_nether_bricks"; case "bricks" -> "minecraft:mud_bricks"; default -> null; };
                        if (to != null) set(lvl, p, to);
                    } else if (scorch[ring] > 0 && st.isCollisionShapeFullBlock(lvl, p) && lvl.canSeeSky(p.above()) && rng.nextFloat() < scorch[ring]
                            && (id.contains("concrete") || id.contains("brick") || id.contains("stone") || id.contains("terracotta") || id.contains("andesite"))) {
                        set(lvl, p, rng.nextBoolean() ? "minecraft:blackstone" : "minecraft:coal_block");
                    }
                }
    }

    static void prop(ServerLevel lvl, BlockPos p, String pick, Direction toWall, Random rng) {
        switch (pick) {
            case "TABLE" -> { set(lvl, p, "minecraft:spruce_fence"); set(lvl, p.above(), rng.nextInt(3) == 0 ? "minecraft:candle[candles=1,lit=false]" : "minecraft:spruce_pressure_plate"); }
            case "CHAIR" -> set(lvl, p, "minecraft:spruce_stairs[facing=" + toWall.getSerializedName() + "]");
            case "SHELF2" -> { set(lvl, p, "minecraft:bookshelf"); set(lvl, p.above(), rng.nextBoolean() ? "minecraft:bookshelf" : "minecraft:chiseled_bookshelf"); }
            case "SHELFRUN" -> {   // three shelves along the wall
                Direction along = toWall.getClockWise();
                for (int k = -1; k <= 1; k++) {
                    BlockPos q = p.relative(along, k);
                    if (lvl.getBlockState(q).isAir() && solid(lvl, q.below()) && solid(lvl, q.relative(toWall))) set(lvl, q, rng.nextInt(3) == 0 ? "minecraft:chiseled_bookshelf" : "minecraft:bookshelf");
                }
            }
            case "LOCKER" -> { set(lvl, p, "minecraft:iron_block"); set(lvl, p.above(), "minecraft:iron_block");
                               BlockPos front = p.relative(toWall.getOpposite());
                               if (lvl.getBlockState(front).isAir()) set(lvl, front, "minecraft:iron_trapdoor[facing=" + toWall.getOpposite().getSerializedName() + ",half=top,open=true]"); }
            case "STACK" -> { set(lvl, p, rng.nextBoolean() ? "minecraft:spruce_planks" : "minecraft:stripped_spruce_log"); if (rng.nextBoolean()) set(lvl, p.above(), "minecraft:spruce_slab"); }
            case "COUNTER" -> { set(lvl, p, "minecraft:white_concrete"); if (rng.nextBoolean()) set(lvl, p.above(), "minecraft:candle[candles=2,lit=false]"); }
            case "BEDROLL" -> set(lvl, p, rng.nextBoolean() ? "minecraft:green_carpet" : "minecraft:brown_carpet");
            default -> set(lvl, p, pick);
        }
    }

    /** Roadside detail in a street chunk: 0-2 pieces, only where there's room round them so the street stays open. */
    static void streetDetail(MinecraftServer server, ServerLevel lvl, int cx, int cz, int street, long key) {
        Random rng = new Random(key * 17 + 3);
        int ring = Zone.tier((cx << 4) + 8, (cz << 4) + 8);
        int n = new int[]{0, 1, 2, 3, 4}[ring] + rng.nextInt(2) - (ring == 1 ? 1 : 0);   // outskirts 0-1 ... Core 4-5
        for (int k = 0; k < n; k++) {
            int x = (cx << 4) + 3 + rng.nextInt(10), z = (cz << 4) + 3 + rng.nextInt(10), y = street;
            boolean along = rng.nextBoolean();   // lies along x or along z
            int len = 2 + rng.nextInt(2) + (ring >= 3 ? 1 + rng.nextInt(2) : 0);
            // room: the piece's cells plus one all round, clear for two blocks up, on solid ground
            boolean ok = true;
            for (int a = -1; a <= len && ok; a++) for (int b = -2; b <= 2 && ok; b++) {
                BlockPos q = along ? new BlockPos(x + a, y, z + b) : new BlockPos(x + b, y, z + a);
                ok = lvl.getBlockState(q).isAir() && lvl.getBlockState(q.above()).isAir() && solid(lvl, q.below());
            }
            if (!ok) continue;
            int kind = ring == 1 ? 3 : ring == 2 ? rng.nextInt(4) : rng.nextInt(6);   // outskirts: debris only; inner + Core: wire and rubble too
            for (int a = 0; a < len; a++) {
                BlockPos q = along ? new BlockPos(x + a, y, z) : new BlockPos(x, y, z + a);
                switch (kind) {
                    case 0 -> set(lvl, q, "minecraft:mud_brick_wall");                                   // sandbags
                    case 1 -> set(lvl, q, a % 2 == 0 ? "minecraft:iron_bars" : "minecraft:spruce_fence");  // barricade
                    case 2 -> {                                                                           // burnt-out car
                        set(lvl, q, a == 0 || a == len - 1 ? "minecraft:black_concrete" : "minecraft:gray_concrete");
                        if (a > 0 && a < len - 1) set(lvl, q.above(), "minecraft:gray_concrete");
                        BlockPos side = along ? q.south() : q.east();
                        set(lvl, side, a == 0 || a == len - 1 ? "minecraft:black_concrete" : "minecraft:gray_concrete");
                    }
                    case 4 -> set(lvl, q, "minecraft:cobweb");                                              // razor wire
                    case 5 -> {                                                                           // rubble you climb over
                        set(lvl, q, a == len / 2 ? "minecraft:cobblestone" : "minecraft:cobblestone_slab");
                        BlockPos side = along ? q.south() : q.east();
                        set(lvl, side, "minecraft:cobblestone_slab");
                    }
                    default -> set(lvl, q, rng.nextBoolean() ? "minecraft:cobblestone_slab" : "minecraft:gravel");   // debris
                }
            }
            streetBits++;
        }
    }

    static void init() {
        net.fabricmc.fabric.api.event.lifecycle.v1.ServerLifecycleEvents.SERVER_STOPPING.register(server -> { if (done != null) saveDone(); });
        // 1.8.15: the city's stations work (Stations handles them)
    }
}

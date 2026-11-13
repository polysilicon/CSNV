package crispy.ez;

import net.minecraft.commands.arguments.blocks.BlockStateParser;
import net.minecraft.core.BlockPos;
import net.minecraft.core.Direction;
import net.minecraft.core.registries.Registries;
import net.minecraft.server.MinecraftServer;
import net.minecraft.server.level.ServerLevel;
import net.minecraft.world.level.block.Blocks;
import net.minecraft.world.level.block.DoorBlock;
import net.minecraft.world.level.block.LadderBlock;
import net.minecraft.world.level.block.StairBlock;
import net.minecraft.world.level.block.TrapDoorBlock;
import net.minecraft.world.level.block.state.BlockState;

import java.util.*;
import java.util.concurrent.ConcurrentLinkedQueue;

/**
 * Furnished ruins (1.8.4). The Lost Cities' rooms are mostly bare, so each newly generated building chunk in the zone
 * gets a pass that puts props on indoor floors (a roof within 6 above, solid floor, two blocks of headroom):
 *  - against a wall: bookshelves, tables (fence + pressure plate), chairs (stairs facing the room), workbenches,
 *    cauldrons, anvils, sandbags, potted dead bushes, candles, a lantern now and then;
 *  - high in a corner: a cobweb;
 *  - in the open: a carpet scrap or a rubble slab (nothing taller than half a block, so nobody's path is blocked).
 * Never in a one-wide corridor, and never next to a door, trapdoor, ladder or stairs, so routes stay open. One chunk per
 * tick. Chunks that are already generated aren't touched (they get it after the next city reset).
 */
final class Interiors {
    private Interiors() {}

    static final Queue<Long> QUEUE = new ConcurrentLinkedQueue<>();
    static final Map<String, BlockState> CACHE = new HashMap<>();
    static int furnished, props;
    static final String[] WALL = {"minecraft:bookshelf", "minecraft:chiseled_bookshelf", "minecraft:crafting_table", "minecraft:cauldron", "minecraft:chipped_anvil",
            "minecraft:grindstone[face=floor]", "minecraft:mud_brick_wall", "minecraft:potted_dead_bush", "minecraft:candle[candles=2,lit=false]",
            "minecraft:lantern", "minecraft:composter", "minecraft:smithing_table", "minecraft:hay_block"};
    static final String[] FLOOR = {"minecraft:gray_carpet", "minecraft:brown_carpet", "minecraft:cobblestone_slab", "minecraft:andesite_slab", "minecraft:light_gray_carpet"};

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

    static void tick(MinecraftServer server) {
        Long key = QUEUE.poll();
        if (key == null) return;
        ServerLevel lvl = server.getLevel(Zone.CITY);
        if (lvl == null) return;
        int cx = net.minecraft.world.level.ChunkPos.getX(key), cz = net.minecraft.world.level.ChunkPos.getZ(key);
        if (!lvl.hasChunk(cx, cz) || Zone.LC.isStreet(lvl, cx, cz)) return;
        Integer street = Zone.LC.street(lvl, cx, cz);
        if (street == null) return;
        Random rng = new Random(key * 31 + 7);
        List<BlockPos> placed = new ArrayList<>();
        int bx = cx << 4, bz = cz << 4;
        for (int y = street - 6; y <= street + 40; y++)
            for (int x = bx + 1; x < bx + 15; x++)
                for (int z = bz + 1; z < bz + 15; z++) {
                    BlockPos p = new BlockPos(x, y, z);
                    if (!lvl.getBlockState(p).isAir() || !lvl.getBlockState(p.above()).isAir() || !solid(lvl, p.below())) continue;
                    boolean roofed = false;
                    for (int k = 2; k <= 6 && !roofed; k++) roofed = !lvl.getBlockState(p.above(k)).isAir();
                    if (!roofed) continue;
                    // walls round it; nothing that's a way through nearby
                    boolean n = solid(lvl, p.north()), so = solid(lvl, p.south()), e = solid(lvl, p.east()), w = solid(lvl, p.west());
                    if ((n && so) || (e && w)) continue;   // a corridor
                    boolean near = false;
                    for (int dx = -1; dx <= 1 && !near; dx++) for (int dz = -1; dz <= 1 && !near; dz++) for (int dy = -1; dy <= 1 && !near; dy++)
                        near = route(lvl.getBlockState(p.offset(dx, dy, dz)));
                    if (near) continue;
                    if (placed.stream().anyMatch(q -> q.distManhattan(p) < 3)) continue;
                    int walls = (n ? 1 : 0) + (so ? 1 : 0) + (e ? 1 : 0) + (w ? 1 : 0);
                    if (walls == 1 && rng.nextFloat() < 0.07f) {
                        Direction toWall = n ? Direction.NORTH : so ? Direction.SOUTH : e ? Direction.EAST : Direction.WEST;
                        int pick = rng.nextInt(WALL.length + 3);
                        if (pick == WALL.length) {   // a table
                            lvl.setBlock(p, state(lvl, "minecraft:spruce_fence"), 2);
                            lvl.setBlock(p.above(), state(lvl, "minecraft:spruce_pressure_plate"), 2);
                        } else if (pick == WALL.length + 1) {   // a chair, back to the wall
                            lvl.setBlock(p, state(lvl, "minecraft:spruce_stairs[facing=" + toWall.getSerializedName() + "]"), 2);
                        } else if (pick == WALL.length + 2) {   // shelves, two high
                            lvl.setBlock(p, state(lvl, "minecraft:bookshelf"), 2);
                            lvl.setBlock(p.above(), state(lvl, rng.nextBoolean() ? "minecraft:bookshelf" : "minecraft:chiseled_bookshelf"), 2);
                        } else lvl.setBlock(p, state(lvl, WALL[pick]), 2);
                        placed.add(p); props++;
                    } else if (walls == 2 && rng.nextFloat() < 0.05f && lvl.getBlockState(p.above(2)).isAir() && !lvl.getBlockState(p.above(3)).isAir()) {
                        lvl.setBlock(p.above(2), state(lvl, "minecraft:cobweb"), 2);   // high in the corner, over head height
                        placed.add(p); props++;
                    } else if (walls == 0 && rng.nextFloat() < 0.015f) {
                        lvl.setBlock(p, state(lvl, FLOOR[rng.nextInt(FLOOR.length)]), 2);
                        placed.add(p); props++;
                    }
                }
        furnished++;
    }
}

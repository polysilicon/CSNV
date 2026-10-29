package crispy.falling;

import net.minecraft.ChatFormatting;
import net.minecraft.core.BlockPos;
import net.minecraft.core.registries.Registries;
import net.minecraft.nbt.CompoundTag;
import net.minecraft.nbt.ListTag;
import net.minecraft.network.chat.Component;
import net.minecraft.resources.Identifier;
import net.minecraft.resources.ResourceKey;
import net.minecraft.server.MinecraftServer;
import net.minecraft.server.level.ServerLevel;
import net.minecraft.server.level.ServerPlayer;
import net.minecraft.server.permissions.LevelBasedPermissionSet;
import net.minecraft.world.InteractionHand;
import net.minecraft.world.InteractionResult;
import net.minecraft.world.entity.Entity;
import net.minecraft.world.entity.player.Player;
import net.minecraft.world.level.Level;
import net.minecraft.world.level.block.Blocks;
import net.minecraft.world.level.portal.TeleportTransition;
import net.minecraft.world.phys.BlockHitResult;
import net.minecraft.world.phys.Vec3;

import java.util.Map;
import java.util.WeakHashMap;

/**
 * Each island's own End and Nether boss realms.
 * - End: the datapack's void dimension crispy_skyblock:end (End sky, no dragon). An island's End portal (east of the
 *   island, built by ev/portal) sends you to that island's End island at the same x/z as the island, y 64; it's built
 *   (crispy_skyblock:end/island) the first time anyone goes. EndPortalBlockMixin calls destination().
 * - Nether: the island's Nether plot (under island/8) has a boss arena 16 blocks south of its starter island.
 * - Both have a summoning altar (a lodestone): right-click it once to be asked, again within 10 s to run
 *   crispy_skyblock:boss/summon.
 */
public final class Realms {
    private Realms() {}

    static final ResourceKey<Level> END = ResourceKey.create(Registries.DIMENSION, Identifier.fromNamespaceAndPath(SkyblockMod.NS, "end"));
    static final int END_Y = 64, NFLOOR_Y = 64, ARENA_DZ = 16, RETURN_DZ = -9, CONFIRM_TICKS = 200;
    /** The altar each player last clicked and the tick it was clicked: a second click there in time summons. */
    private static final Map<ServerPlayer, Long> asked = new WeakHashMap<>();
    private static final Map<ServerPlayer, BlockPos> askedAt = new WeakHashMap<>();

    /** Island id for overworld/End x,z (islands sit on the same grid in both), or 0. */
    static int plotAt(int x, int z) {
        int col = Math.floorDiv(x, Portals.GRID), row = Math.floorDiv(z - 2 * Portals.GRID, Portals.GRID);
        return col < 0 || col >= Portals.COLS || row < 0 ? 0 : row * Portals.COLS + col;
    }
    static int cx(int id) { return (id % Portals.COLS) * Portals.GRID + Portals.HALF; }
    static int cz(int id) { return 2 * Portals.GRID + (id / Portals.COLS) * Portals.GRID + Portals.HALF; }

    /** Island id for a Nether x,z: Nether plots are 64 wide around (cx/8, cz/8), 128 apart. */
    static int netherPlotAt(int x, int z) {
        int col = Math.floorDiv(x + 24, 128), row = Math.floorDiv(z - 256 + 24, 128);
        return col < 0 || col >= Portals.COLS || row < 0 ? 0 : row * Portals.COLS + col;
    }
    static int ncx(int id) { return cx(id) / 8; }
    static int ncz(int id) { return cz(id) / 8; }

    static boolean exists(MinecraftServer server, int id) {
        ListTag plots = server.getCommandStorage().get(IslandLevels.DATA).getListOrEmpty("plots");
        return id > 0 && id < plots.size();
    }

    // ------------------------------------------------------------------ the End
    /** Where an overworld End portal at `pos` sends `entity`: its island's End (built on first use), or nowhere. */
    public static TeleportTransition destination(ServerLevel from, Entity entity, BlockPos pos) {
        MinecraftServer server = from.getServer();
        ServerLevel end = server.getLevel(END);
        int id = plotAt(pos.getX(), pos.getZ());
        if (end == null || !exists(server, id)) return null;
        prepare(server, end, id);
        Vec3 to = new Vec3(cx(id) + 0.5, END_Y + 1, cz(id) + 6.5);
        if (entity instanceof ServerPlayer p) p.sendSystemMessage(Component.literal("Welcome to your island's End. Right-click the altar to call its boss.").withStyle(ChatFormatting.LIGHT_PURPLE));
        return new TeleportTransition(end, to, Vec3.ZERO, 180f, 0f, TeleportTransition.PLAY_PORTAL_SOUND);
    }

    /** Build island `id`'s End island the first time (chunks are loaded on the spot). */
    static void prepare(MinecraftServer server, ServerLevel end, int id) {
        ListTag plots = server.getCommandStorage().get(IslandLevels.DATA).getListOrEmpty("plots");
        CompoundTag rec = plots.getCompoundOrEmpty(id);
        if (rec.contains("endb")) return;
        int x = cx(id), z = cz(id);
        for (int a = (x - 16) >> 4; a <= (x + 16) >> 4; a++)
            for (int b = (z - 16) >> 4; b <= (z + 16) >> 4; b++) end.getChunk(a, b);
        run(server, "execute in " + END.identifier() + " positioned " + x + " " + END_Y + " " + z + " run function " + SkyblockMod.NS + ":end/island");
        run(server, "data modify storage " + SkyblockMod.NS + ":d plots[" + id + "].endb set value 1b");
    }

    static void run(MinecraftServer server, String cmd) {
        server.getCommands().performPrefixedCommand(server.createCommandSourceStack().withSuppressedOutput(), cmd);
    }

    // ------------------------------------------------------------------ altars
    /** UseBlockCallback: a lodestone at an End or Nether altar summons that island's boss. */
    static InteractionResult onUseBlock(Player player, Level world, InteractionHand hand, BlockHitResult hit) {
        if (!(player instanceof ServerPlayer p) || !(world instanceof ServerLevel level) || hand != InteractionHand.MAIN_HAND) return InteractionResult.PASS;
        BlockPos pos = hit.getBlockPos();
        if (!level.getBlockState(pos).is(Blocks.LODESTONE)) return InteractionResult.PASS;
        String realm = null;
        int id = 0, sx = 0, sy = 0, sz = 0;
        if (level.dimension() == END) {
            id = plotAt(pos.getX(), pos.getZ());
            if (id > 0 && pos.getX() == cx(id) && pos.getY() == END_Y + 1 && pos.getZ() == cz(id)) {
                realm = "e"; sx = cx(id); sy = END_Y + 1; sz = cz(id) - 4;
            }
        } else if (level.dimension() == Level.NETHER) {
            id = netherPlotAt(pos.getX(), pos.getZ());
            if (id > 0 && pos.getX() == ncx(id) && pos.getY() == NFLOOR_Y + 1 && pos.getZ() == ncz(id) + ARENA_DZ) {
                realm = "n"; sx = ncx(id); sy = NFLOOR_Y + 1; sz = ncz(id) + ARENA_DZ - 4;
            }
        }
        if (realm == null) return InteractionResult.PASS;
        long now = level.getServer().getTickCount();
        Long when = asked.get(p);
        if (when == null || now - when > CONFIRM_TICKS || !pos.equals(askedAt.get(p))) {
            asked.put(p, now);
            askedAt.put(p, pos.immutable());
            p.sendSystemMessage(Component.literal("Are you sure you want to summon a boss right now? ").withStyle(ChatFormatting.GOLD)
                    .append(Component.literal("Right-click the altar again to confirm.").withStyle(ChatFormatting.GRAY)));
            return InteractionResult.SUCCESS;
        }
        asked.remove(p);
        askedAt.remove(p);
        level.getServer().getCommands().performPrefixedCommand(p.createCommandSourceStack().withPermission(LevelBasedPermissionSet.GAMEMASTER).withSuppressedOutput(),
                "function " + SkyblockMod.NS + ":boss/summon {r:\"" + realm + "\",id:" + id + ",x:" + sx + ",y:" + sy + ",z:" + sz + "}");
        return InteractionResult.SUCCESS;
    }

    /** True if `pos` in `level` is part of an altar or the End's way home (players can't break those). */
    static boolean isProtected(Level level, BlockPos pos) {
        if (level.dimension() == END) {
            int id = plotAt(pos.getX(), pos.getZ());
            if (id <= 0) return false;
            int dx = pos.getX() - cx(id), dz = pos.getZ() - cz(id), y = pos.getY();
            if (Math.abs(dx) <= 1 && Math.abs(dz) <= 1 && y >= END_Y && y <= END_Y + 1) return true;                 // altar
            return Math.abs(dx) <= 2 && dz >= RETURN_DZ - 1 && dz <= RETURN_DZ + 1 && y >= END_Y && y <= END_Y + 5;   // gateway home
        }
        if (level.dimension() == Level.NETHER) {
            int id = netherPlotAt(pos.getX(), pos.getZ());
            if (id <= 0) return false;
            int dx = pos.getX() - ncx(id), dz = pos.getZ() - ncz(id) - ARENA_DZ, y = pos.getY();
            return Math.abs(dx) <= 1 && Math.abs(dz) <= 1 && y >= NFLOOR_Y && y <= NFLOOR_Y + 1;
        }
        return false;
    }
}

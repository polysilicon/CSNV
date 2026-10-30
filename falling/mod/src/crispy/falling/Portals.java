package crispy.falling;

import net.minecraft.ChatFormatting;
import net.minecraft.commands.Commands;
import net.minecraft.core.BlockPos;
import net.minecraft.network.chat.Component;
import net.minecraft.server.MinecraftServer;
import net.minecraft.server.level.ServerPlayer;
import net.minecraft.server.permissions.LevelBasedPermissionSet;
import net.minecraft.sounds.SoundEvents;
import net.minecraft.world.entity.player.Player;
import net.minecraft.world.level.Level;
import net.minecraft.world.level.block.entity.BlockEntity;
import net.minecraft.world.level.block.state.BlockState;

import java.util.Map;
import java.util.WeakHashMap;

/**
 * Hub portals. Every island has one 14 blocks north of its centre on a platform over the void (built by the datapack's
 * crispy_skyblock:portal/build); walking through it takes you to the hub. The hub's portal (north of the plaza) takes
 * you home, and each island's End has a gateway home. Portal blocks, End portal platforms and boss altars can't be
 * broken by players (they're blast-proof and immovable anyway). Positions follow the
 * datapack's island grid: plots of 128 on a 1024 grid from z=2048, islands centred at y=100.
 */
public final class Portals {
    private Portals() {}

    static final int GRID = 1024, COLS = 64, HALF = 64, ISLAND_Y = 100, PORTAL_DZ = -14, END_DX = 14, HUB_Y = 100, HUB_PORTAL_Z = -18;
    private static final Map<ServerPlayer, Integer> cooldown = new WeakHashMap<>();
    /** Fixed overworld portals (skyblock.py HUB_ZONE_PORTALS, expansion.py): frame centre x, floor y, z, and the warp. */
    static final Object[][] FIXED = {{-13, HUB_Y, -14, "mines"}, {13, HUB_Y, -14, "woods"}, {-260, 90, -393, "hub"}, {260, 100, -391, "hub"}};
    private static int tick;

    /** Centre of the island portal's frame for the plot containing (x, z), or null outside the grid. */
    static int[] portalFor(int x, int z) {
        int col = Math.floorDiv(x, GRID), row = Math.floorDiv(z - 2 * GRID, GRID);
        if (col < 0 || col >= COLS || row < 0) return null;
        return new int[]{col * GRID + HALF, 2 * GRID + row * GRID + HALF + PORTAL_DZ};
    }

    static void onTick(MinecraftServer server) {
        tick++;
        for (ServerPlayer p : server.getPlayerList().getPlayers()) {
            if (p.isSpectator() || cooldown.getOrDefault(p, 0) > tick) continue;
            int x = p.getBlockX(), y = p.getBlockY(), z = p.getBlockZ();
            String fn = null;
            if (p.level().dimension() == Realms.END) {
                // the End island's gateway home, on its north edge
                int id = Realms.plotAt(x, z);
                if (id > 0 && z == Realms.cz(id) + Realms.RETURN_DZ && Math.abs(x - Realms.cx(id)) <= 1 && y >= Realms.END_Y + 1 && y <= Realms.END_Y + 3) fn = "act/home";
            }
            else if (p.level() != server.overworld()) continue;
            else if (z == HUB_PORTAL_Z && Math.abs(x) <= 1 && y >= HUB_Y + 1 && y <= HUB_Y + 3) fn = "act/home";
            else if (fixed(x, y, z) != null) {
                cooldown.put(p, tick + 60);
                p.playSound(SoundEvents.ENDERMAN_TELEPORT, 0.8f, 1.2f);
                Zones.warp(p, fixed(x, y, z));
                continue;
            }
            else {
                int[] pt = portalFor(x, z);
                if (pt != null && z == pt[1] && Math.abs(x - pt[0]) <= 1 && y >= ISLAND_Y + 1 && y <= ISLAND_Y + 3) fn = "act/hub";
            }
            if (fn == null) continue;
            cooldown.put(p, tick + 60);
            p.playSound(SoundEvents.ENDERMAN_TELEPORT, 0.8f, 1.2f);
            server.getCommands().performPrefixedCommand(p.createCommandSourceStack().withPermission(LevelBasedPermissionSet.GAMEMASTER).withSuppressedOutput(),
                    "function " + SkyblockMod.NS + ":" + fn);
        }
    }

    static String fixed(int x, int y, int z) {
        for (Object[] f : FIXED) {
            int fx = (Integer) f[0], fy = (Integer) f[1], fz = (Integer) f[2];
            if (z == fz && Math.abs(x - fx) <= 1 && y >= fy + 1 && y <= fy + 3) return (String) f[3];
        }
        return null;
    }

    /** PlayerBlockBreakEvents.BEFORE: false stops the break. */
    static boolean canBreak(Level world, Player player, BlockPos pos, BlockState state, BlockEntity be) {
        if (!(player instanceof ServerPlayer p) || !isProtected(world, pos)) return true;
        if (p.isCreative() && Commands.hasPermission(Commands.LEVEL_GAMEMASTERS).test(p.createCommandSourceStack())) return true;
        p.sendSystemMessage(Component.literal("That can't be broken.").withStyle(ChatFormatting.RED));
        return false;
    }

    /** An island's hub portal or End portal platform, or an altar / the End's gateway home. */
    static boolean isProtected(Level world, BlockPos pos) {
        if (world.dimension() != Level.OVERWORLD) return Realms.isProtected(world, pos);
        int[] pt = portalFor(pos.getX(), pos.getZ());
        if (pt == null || pos.getY() < ISLAND_Y - 1 || pos.getY() > ISLAND_Y + 5) return false;
        if (Math.abs(pos.getX() - pt[0]) <= 2 && Math.abs(pos.getZ() - pt[1]) <= 2) return true;                      // hub portal
        return Math.abs(pos.getX() - (pt[0] + END_DX)) <= 3 && Math.abs(pos.getZ() - (pt[1] - PORTAL_DZ)) <= 3;       // End portal
    }
}

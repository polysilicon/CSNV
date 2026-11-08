package crispy.falling;

import net.minecraft.ChatFormatting;
import net.minecraft.commands.Commands;
import net.minecraft.core.BlockPos;
import net.minecraft.nbt.CompoundTag;
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
    static final Object[][] FIXED = {{-13, HUB_Y, -14, "mines"}, {13, HUB_Y, -14, "woods"}, {-260, 90, -393, "hub"}, {260, 100, -391, "hub"},
            {13, 101, 15, "rift"}, {0, 120, -671, "hub"}};   // the Sky Lord's Rift (gated in Zones.warp) and its way back
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
                if (Zones.warp(p, fixed(x, y, z)) < 0) {   // turned away (tag gate): step them back out of the frame
                    var look = p.getLookAngle();
                    double len = Math.max(0.01, Math.hypot(look.x, look.z));
                    p.teleportTo(p.getX() - look.x / len * 2.2, p.getY(), p.getZ() - look.z / len * 2.2);
                }
                continue;
            }
            else {
                int id = Visits.islandAt(p.level(), p.blockPosition());
                int[] hp = id > 0 ? IslandPortals.hub(Upgrades.rec(server, id)) : null;   // moved with /island moveportal hub (2.16.0)
                if (hp != null && z == hp[2] && Math.abs(x - hp[0]) <= 1 && y >= hp[1] + 1 && y <= hp[1] + 3) fn = "act/hub";
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
        int id = Visits.islandAt(world, pos);
        if (id <= 0 || world.getServer() == null) return false;
        CompoundTag r = Upgrades.rec(world.getServer(), id);
        int[] hp = IslandPortals.hub(r), ep = IslandPortals.end(r);   // their own spots if moved (2.16.0)
        int dy = pos.getY() - hp[1];
        // with its own platform (the original spot): from the platform's underside up; moved: just the frame above your floor
        if (Math.abs(pos.getX() - hp[0]) <= 2 && Math.abs(pos.getZ() - hp[2]) <= 2 && dy >= (hp[3] > 0 ? -1 : 1) && dy <= 5) return true;   // hub portal
        dy = pos.getY() - ep[1];
        return Math.abs(pos.getX() - ep[0]) <= 3 && Math.abs(pos.getZ() - ep[2]) <= 3 && dy >= (ep[3] > 0 ? -1 : 1) && dy <= (ep[3] > 0 ? 5 : 2);   // End portal
    }
}

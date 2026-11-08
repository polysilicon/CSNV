package crispy.falling;

import com.mojang.brigadier.builder.LiteralArgumentBuilder;
import net.minecraft.ChatFormatting;
import net.minecraft.commands.CommandSourceStack;
import net.minecraft.commands.Commands;
import net.minecraft.core.BlockPos;
import net.minecraft.nbt.CompoundTag;
import net.minecraft.server.MinecraftServer;
import net.minecraft.server.level.ServerLevel;
import net.minecraft.server.level.ServerPlayer;
import net.minecraft.world.level.Level;
import net.minecraft.world.level.block.Blocks;

import static crispy.falling.Ui.t;

/**
 * Movable island portals and a landing pad for sky drops (2.16.0, from Stuckinchair's feedback).
 * - /island moveportal hub|end: the island's Hub Portal (normally 14 blocks north of the centre, over the void) or its
 *   End portal (14 blocks east, once it has appeared) moves to where you stand on your island. It's only built where
 *   the space is empty (it never replaces anything you built) and stands on your floor (no platform). The old one is
 *   cleared. An End portal you'd already filled with eyes stays filled. Positions: plots[id].hp / plots[id].ep
 *   {x, y (the floor), z, plat (0 = moved: no platform of its own)}; without them the old fixed spots apply.
 * - /island droppad [reset]: sky drops (animals, crates, meteors, dungeons) land within 2 blocks of where you stand,
 *   instead of anywhere near the island centre (it moves the island's drop square ix..ix1 / iz..iz1).
 * Portals.java reads the positions to teleport and protect; the datapack draws the hub portal's particles there.
 */
final class IslandPortals {
    private IslandPortals() {}

    static final int R = 6;   // skyblock.py R: the default drop square is the centre +- R

    /** {x, floor y, z, has a platform of its own (1) or not (0)} of island id's hub portal. */
    static int[] hub(CompoundTag r) {
        CompoundTag hp = r.getCompoundOrEmpty("hp");
        if (!hp.isEmpty()) return new int[]{hp.getIntOr("x", 0), hp.getIntOr("y", 0), hp.getIntOr("z", 0), hp.getIntOr("plat", 0)};
        return new int[]{r.getIntOr("cx", 0), Portals.ISLAND_Y, r.getIntOr("cz", 0) + Portals.PORTAL_DZ, 1};
    }
    /** The same for its End portal (whether or not it has appeared yet: see endExists). */
    static int[] end(CompoundTag r) {
        CompoundTag ep = r.getCompoundOrEmpty("ep");
        if (!ep.isEmpty()) return new int[]{ep.getIntOr("x", 0), ep.getIntOr("y", 0), ep.getIntOr("z", 0), ep.getIntOr("plat", 0)};
        return new int[]{r.getIntOr("cx", 0) + Portals.END_DX, Portals.ISLAND_Y, r.getIntOr("cz", 0), 1};
    }
    static boolean endExists(CompoundTag r) { return r.getBooleanOr("endp", false) || r.contains("endp"); }

    static void island(LiteralArgumentBuilder<CommandSourceStack> root) {
        root.then(Commands.literal("moveportal")
                        .then(Commands.literal("hub").executes(c -> move(c.getSource(), true)))
                        .then(Commands.literal("end").executes(c -> move(c.getSource(), false))))
            .then(Commands.literal("droppad").executes(c -> pad(c.getSource(), false))
                        .then(Commands.literal("reset").executes(c -> pad(c.getSource(), true))));
    }

    /** The member's island, if they're standing on it (overworld, on the ground); otherwise tells them and returns 0. */
    static int standing(CommandSourceStack s, ServerPlayer p) {
        MinecraftServer server = s.getServer();
        int id = SkyblockMod.plot(server, p);
        if (id <= 0) { s.sendFailure(t("You don't have an island yet.", ChatFormatting.RED)); return 0; }
        if (p.level().dimension() != Level.OVERWORLD || !IslandHomes.inside(server, id, p.level(), p.getX(), p.getZ())) {
            s.sendFailure(t("Stand on your island first.", ChatFormatting.RED)); return 0;
        }
        if (!p.onGround()) { s.sendFailure(t("Stand on solid ground first.", ChatFormatting.RED)); return 0; }
        return id;
    }

    static boolean clear(ServerLevel level, int x, int y, int z, int rx, int rz, int y0, int y1) {
        for (int dx = -rx; dx <= rx; dx++)
            for (int dz = -rz; dz <= rz; dz++)
                for (int dy = y0; dy <= y1; dy++)
                    if (!level.getBlockState(new BlockPos(x + dx, y + dy, z + dz)).canBeReplaced()) return false;
        return true;
    }

    static int move(CommandSourceStack s, boolean hubPortal) throws com.mojang.brigadier.exceptions.CommandSyntaxException {
        ServerPlayer p = s.getPlayerOrException();
        MinecraftServer server = s.getServer();
        int id = standing(s, p);
        if (id <= 0) return 0;
        CompoundTag r = Upgrades.rec(server, id);
        if (!hubPortal && !endExists(r)) { s.sendFailure(t("Your island's End portal hasn't appeared yet.", ChatFormatting.RED)); return 0; }
        ServerLevel level = (ServerLevel) p.level();
        int x = p.getBlockX(), y = p.getBlockY() - 1, z = p.getBlockZ();   // y: the floor block under your feet
        int half = hubPortal ? 2 : 3;
        // the whole portal must fit on the island, in empty space, and clear of the other portal
        if (!IslandHomes.inside(server, id, level, x - half, z - half) || !IslandHomes.inside(server, id, level, x + half, z + half)) {
            s.sendFailure(t("Too close to the edge of your island's space.", ChatFormatting.RED)); return 0;
        }
        if (!clear(level, x, y, z, half, half, 1, hubPortal ? 5 : 2)) {
            s.sendFailure(t("Not enough room: the " + (half * 2 + 1) + "x" + (half * 2 + 1) + " area around you (" + (hubPortal ? 5 : 2)
                    + " blocks up) must be empty. Nothing you built gets replaced.", ChatFormatting.RED)); return 0;
        }
        int[] other = hubPortal ? end(r) : hub(r);
        if (Math.abs(other[0] - x) < 7 && Math.abs(other[2] - z) < 7) {
            s.sendFailure(t("Too close to your " + (hubPortal ? "End portal" : "Hub Portal") + " (or where it will appear).", ChatFormatting.RED)); return 0;
        }
        int[] old = hubPortal ? hub(r) : end(r);
        String ns = SkyblockMod.NS, at = "execute in minecraft:overworld positioned ";
        if (hubPortal) {
            Visits.run(server, at + old[0] + " " + old[1] + " " + old[2] + " run function " + ns + ":portal/clear_hub" + (old[3] == 1 ? "_plat" : ""));
            Visits.run(server, at + x + " " + y + " " + z + " run function " + ns + ":portal/place_hub");
            Visits.run(server, "data modify storage " + ns + ":d plots[" + id + "].hp set value {x:" + x + ",y:" + y + ",z:" + z + ",plat:0}");
        } else {
            boolean filled = level.getBlockState(new BlockPos(old[0], old[1] + 1, old[2])).is(Blocks.END_PORTAL);
            Visits.run(server, at + old[0] + " " + old[1] + " " + old[2] + " run function " + ns + ":portal/clear_end" + (old[3] == 1 ? "_plat" : ""));
            Visits.run(server, at + x + " " + y + " " + z + " run function " + ns + ":portal/place_end {e:\"" + filled + "\"}");
            if (filled) Visits.run(server, at + x + " " + y + " " + z + " run fill ~-1 ~1 ~-1 ~1 ~1 ~1 minecraft:end_portal");
            Visits.run(server, "data modify storage " + ns + ":d plots[" + id + "].ep set value {x:" + x + ",y:" + y + ",z:" + z + ",plat:0}");
        }
        p.sendSystemMessage(t("Your " + (hubPortal ? "Hub Portal" : "End portal") + " now stands here.", ChatFormatting.GREEN));
        return 1;
    }

    static int pad(CommandSourceStack s, boolean reset) throws com.mojang.brigadier.exceptions.CommandSyntaxException {
        ServerPlayer p = s.getPlayerOrException();
        MinecraftServer server = s.getServer();
        int id = SkyblockMod.plot(server, p);
        if (id <= 0) { s.sendFailure(t("You don't have an island yet.", ChatFormatting.RED)); return 0; }
        CompoundTag r = Upgrades.rec(server, id);
        int x, z, h;
        if (reset) { x = r.getIntOr("cx", 0); z = r.getIntOr("cz", 0); h = R; }
        else {
            if ((id = standing(s, p)) <= 0) return 0;
            x = p.getBlockX(); z = p.getBlockZ(); h = 2;
            if (!IslandHomes.inside(server, id, p.level(), x - h, z - h) || !IslandHomes.inside(server, id, p.level(), x + h, z + h)) {
                s.sendFailure(t("Too close to the edge of your island's space.", ChatFormatting.RED)); return 0;
            }
        }
        String d = "data modify storage " + SkyblockMod.NS + ":d plots[" + id + "].";
        Visits.run(server, d + "ix set value " + (x - h)); Visits.run(server, d + "ix1 set value " + (x + h));
        Visits.run(server, d + "iz set value " + (z - h)); Visits.run(server, d + "iz1 set value " + (z + h));
        p.sendSystemMessage(t(reset ? "Sky drops land near your island's centre again." : "Sky drops (animals, crates, meteors, dungeons) now land within 2 blocks of here. Keep the sky above clear!", ChatFormatting.GREEN));
        return 1;
    }
}

package crispy.falling;

import net.minecraft.ChatFormatting;
import net.minecraft.nbt.CompoundTag;
import net.minecraft.nbt.ListTag;
import net.minecraft.network.chat.Component;
import net.minecraft.network.chat.numbers.BlankFormat;
import net.minecraft.network.protocol.game.ClientboundSetDisplayObjectivePacket;
import net.minecraft.network.protocol.game.ClientboundSetObjectivePacket;
import net.minecraft.network.protocol.game.ClientboundSetScorePacket;
import net.minecraft.server.MinecraftServer;
import net.minecraft.server.level.ServerPlayer;
import net.minecraft.world.level.Level;
import net.minecraft.world.scores.DisplaySlot;
import net.minecraft.world.scores.Objective;
import net.minecraft.world.scores.criteria.ObjectiveCriteria;

import java.util.*;

/**
 * A Hypixel-style sidebar for each player, sent as packets only to them (nothing is added to the real scoreboard):
 * where they are, their purse, island level and minions. Refreshed every second, re-sent only when a line changes.
 */
public final class Sidebar {
    private Sidebar() {}

    static final String OBJ = "cs_side";
    static final int HUB = 50, GRID = 1024, COLS = 64;
    private static final Map<ServerPlayer, List<String>> shown = new WeakHashMap<>();
    private static int tick;

    static void onTick(MinecraftServer server) {
        if (++tick % 20 != 0) return;
        for (ServerPlayer p : server.getPlayerList().getPlayers()) update(server, p);
    }

    static void update(MinecraftServer server, ServerPlayer p) {
        List<Component> lines = lines(server, p);
        List<String> key = lines.stream().map(Component::getString).toList();
        List<String> before = shown.get(p);
        if (key.equals(before)) return;
        Objective obj = new Objective(server.getScoreboard(), OBJ, ObjectiveCriteria.DUMMY,
                Component.literal("SKYBLOCK").withStyle(ChatFormatting.YELLOW, ChatFormatting.BOLD),
                ObjectiveCriteria.RenderType.INTEGER, false, BlankFormat.INSTANCE);
        if (before == null) {
            p.connection.send(new ClientboundSetObjectivePacket(obj, ClientboundSetObjectivePacket.METHOD_ADD));
            p.connection.send(new ClientboundSetDisplayObjectivePacket(DisplaySlot.SIDEBAR, obj));
        }
        // a line per score holder "l<i>"; the score only orders them, the display text is what's shown
        for (int i = 0; i < lines.size(); i++)
            if (before == null || i >= before.size() || !before.get(i).equals(key.get(i)))
                p.connection.send(new ClientboundSetScorePacket("l" + i, OBJ, lines.size() - i, Optional.of(lines.get(i)), Optional.of(BlankFormat.INSTANCE)));
        shown.put(p, key);
    }

    static List<Component> lines(MinecraftServer server, ServerPlayer p) {
        int plot = SkyblockMod.plot(server, p);
        List<Component> l = new ArrayList<>();
        l.add(Component.literal(" ").withStyle(ChatFormatting.DARK_GRAY));
        l.add(Component.literal(" ⏣ ").withStyle(ChatFormatting.GRAY).append(Component.literal(where(server, p, plot)).withStyle(ChatFormatting.AQUA)));
        l.add(Component.literal("  "));
        l.add(Component.literal("Purse: ").withStyle(ChatFormatting.WHITE).append(Component.literal(Economy.fmt(Economy.coins(server, p))).withStyle(ChatFormatting.GOLD)));
        if (plot > 0) {
            l.add(Component.literal("Island level: ").withStyle(ChatFormatting.WHITE).append(Component.literal(String.valueOf(SkyblockMod.score(server, p, "cs_lvl"))).withStyle(ChatFormatting.AQUA)));
            l.add(Component.literal("Minions: ").withStyle(ChatFormatting.WHITE)
                    .append(Component.literal(Minions.count(server, plot) + "/" + Minions.limit(server, plot)).withStyle(ChatFormatting.GREEN)));
        } else l.add(Component.literal("No island yet").withStyle(ChatFormatting.GRAY));
        l.add(Component.literal("Skill avg: ").withStyle(ChatFormatting.WHITE).append(Component.literal(Skills.average(server, p)).withStyle(ChatFormatting.GOLD)));
        l.add(Component.literal("   "));
        l.add(Component.literal("crispyanarchy.net").withStyle(ChatFormatting.YELLOW));
        return l;
    }

    static String where(MinecraftServer server, ServerPlayer p, int plot) {
        Level lv = p.level();
        if (lv.dimension() == Level.NETHER) return "The Nether";
        if (lv.dimension() == Realms.END) {
            int id = Realms.plotAt(p.getBlockX(), p.getBlockZ());
            return id == plot && plot > 0 ? "Your End" : "The End";
        }
        if (lv.dimension() == Level.END) return "The End";
        int x = p.getBlockX(), z = p.getBlockZ();
        if (Math.abs(x) <= HUB && Math.abs(z) <= HUB) return "Hub";
        int col = Math.floorDiv(x, GRID), row = Math.floorDiv(z - 2 * GRID, GRID), id = row * COLS + col;
        if (id == plot && plot > 0) return "Your Island";
        if (col >= 0 && col < COLS && row >= 0) return "Island #" + id;
        return "The Void";
    }
}

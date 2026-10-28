package crispy.falling;

import net.minecraft.core.registries.BuiltInRegistries;
import net.minecraft.nbt.CompoundTag;
import net.minecraft.nbt.ListTag;
import net.minecraft.network.chat.Component;
import net.minecraft.resources.Identifier;
import net.minecraft.server.MinecraftServer;
import net.minecraft.server.level.ServerLevel;
import net.minecraft.server.level.ServerPlayer;
import net.minecraft.commands.CommandSourceStack;
import net.minecraft.world.level.block.Block;
import net.minecraft.world.level.block.state.BlockState;
import net.minecraft.world.level.chunk.LevelChunk;
import net.minecraft.world.level.chunk.LevelChunkSection;
import net.minecraft.world.scores.Objective;
import net.minecraft.world.scores.PlayerScoreEntry;
import net.minecraft.world.scores.ScoreHolder;

import java.util.*;

/**
 * Island levels: every block in an island's 128x128 plot is worth points (most blocks 1, valuable ones more, fluids and
 * plants nothing); 100 points make a level. /island level counts the caller's island (once a minute per island), and
 * every 5 minutes the islands of online players are recounted quietly. Results go to the cs_lvl score of "#p<id>" and
 * of each member (the datapack's level challenges read it), to storage crispy_skyblock:levels, and to the Top Islands
 * board in the hub (the text_display tagged cs_top).
 */
public final class IslandLevels {
    private IslandLevels() {}

    static final Identifier LEVELS = Identifier.fromNamespaceAndPath(SkyblockMod.NS, "levels");
    static final Identifier DATA = Identifier.fromNamespaceAndPath(SkyblockMod.NS, "d");
    static final int POINTS_PER_LEVEL = 100, TOP = 10, AUTO_TICKS = 6000, COOLDOWN_MS = 60_000;
    static final Map<String, Integer> VALUE = new HashMap<>();
    static {
        for (String b : "air cave_air void_air water lava bubble_column fire soul_fire short_grass tall_grass fern large_fern vine snow bedrock barrier light spawner end_portal_frame end_portal nether_portal moving_piston".split(" "))
            VALUE.put(b, 0);
        Object[][] v = {
            {"stone_bricks", 2}, {"bricks", 2}, {"glass", 2}, {"smooth_stone", 2}, {"terracotta", 2}, {"polished_andesite", 2},
            {"polished_diorite", 2}, {"polished_granite", 2}, {"mud_bricks", 2}, {"deepslate_bricks", 3}, {"tuff_bricks", 3},
            {"obsidian", 5}, {"crying_obsidian", 5}, {"glowstone", 3}, {"sea_lantern", 6}, {"prismarine", 3}, {"prismarine_bricks", 4},
            {"dark_prismarine", 4}, {"end_stone", 2}, {"end_stone_bricks", 3}, {"purpur_block", 3}, {"quartz_block", 4},
            {"amethyst_block", 4}, {"copper_block", 8}, {"lapis_block", 15}, {"redstone_block", 10}, {"iron_block", 20},
            {"gold_block", 30}, {"emerald_block", 120}, {"diamond_block", 150}, {"netherite_block", 600}, {"ancient_debris", 50},
            {"beacon", 300}, {"conduit", 200}, {"enchanting_table", 50}, {"anvil", 30}, {"chipped_anvil", 25}, {"damaged_anvil", 20},
            {"brewing_stand", 15}, {"hopper", 10}, {"jukebox", 20}, {"dragon_head", 400}, {"dragon_egg", 1000},
            {"wither_skeleton_skull", 100}, {"sponge", 20}, {"wet_sponge", 20}, {"shulker_box", 40},
        };
        for (Object[] e : v) VALUE.put((String) e[0], (Integer) e[1]);
    }
    static final Map<Integer, Long> lastRun = new HashMap<>();
    private static int tick;

    static int value(Block b) {
        String id = BuiltInRegistries.BLOCK.getKey(b).getPath();
        Integer v = VALUE.get(id);
        if (v != null) return v;
        if (id.endsWith("_shulker_box")) return 40;
        return 1;
    }

    /** Points for the blocks in island `id`'s plot, or -1 if it has no plot record. */
    static long points(MinecraftServer server, int id) {
        ListTag plots = server.getCommandStorage().get(DATA).getListOrEmpty("plots");
        if (id <= 0 || id >= plots.size()) return -1;
        CompoundTag p = plots.getCompoundOrEmpty(id);
        int x = p.getIntOr("x", 0), z = p.getIntOr("z", 0), x1 = p.getIntOr("x1", 0), z1 = p.getIntOr("z1", 0);
        ServerLevel level = server.overworld();
        Map<Block, Integer> cache = new HashMap<>();
        long total = 0;
        for (int cx = x >> 4; cx <= x1 >> 4; cx++)
            for (int cz = z >> 4; cz <= z1 >> 4; cz++) {
                LevelChunk chunk = level.getChunk(cx, cz);
                for (LevelChunkSection sec : chunk.getSections()) {
                    if (sec.hasOnlyAir()) continue;
                    for (int by = 0; by < 16; by++)
                        for (int bz = 0; bz < 16; bz++)
                            for (int bx = 0; bx < 16; bx++) {
                                BlockState st = sec.getBlockState(bx, by, bz);
                                if (st.isAir()) continue;
                                total += cache.computeIfAbsent(st.getBlock(), IslandLevels::value);
                            }
                }
            }
        return total;
    }

    /** Recount island `id`, store the result everywhere it's shown; returns the level (or -1). */
    static int update(MinecraftServer server, int id) {
        long pts = points(server, id);
        if (pts < 0) return -1;
        int lvl = (int) Math.min(Integer.MAX_VALUE, pts / POINTS_PER_LEVEL);
        Objective lvlObj = server.getScoreboard().getObjective("cs_lvl");
        if (lvlObj != null) {
            server.getScoreboard().getOrCreatePlayerScore(ScoreHolder.forNameOnly("#p" + id), lvlObj).set(lvl);
            for (String m : members(server, id))
                server.getScoreboard().getOrCreatePlayerScore(ScoreHolder.forNameOnly(m), lvlObj).set(lvl);
        }
        CompoundTag root = server.getCommandStorage().get(LEVELS);
        CompoundTag all = root.getCompoundOrEmpty("islands");
        CompoundTag rec = new CompoundTag();
        rec.putInt("level", lvl);
        rec.putLong("points", pts);
        all.put(String.valueOf(id), rec);
        root.put("islands", all);
        server.getCommandStorage().set(LEVELS, root);
        lastRun.put(id, System.currentTimeMillis());
        updateBoard(server);
        return lvl;
    }

    /** Players (not #holders) whose cs_plot is `id`. */
    static List<String> members(MinecraftServer server, int id) {
        List<String> out = new ArrayList<>();
        Objective plot = server.getScoreboard().getObjective("cs_plot");
        if (plot == null) return out;
        for (PlayerScoreEntry e : server.getScoreboard().listPlayerScores(plot))
            if (e.value() == id && !e.owner().startsWith("#")) out.add(e.owner());
        out.sort(String.CASE_INSENSITIVE_ORDER);
        return out;
    }

    /** [id, level] pairs, best first. */
    static List<int[]> ranking(MinecraftServer server) {
        CompoundTag all = server.getCommandStorage().get(LEVELS).getCompoundOrEmpty("islands");
        List<int[]> out = new ArrayList<>();
        for (String k : all.keySet()) {
            int lvl = all.getCompoundOrEmpty(k).getIntOr("level", 0);
            try { if (lvl > 0) out.add(new int[]{Integer.parseInt(k), lvl}); } catch (NumberFormatException ignored) {}
        }
        out.sort((a, b) -> Integer.compare(b[1], a[1]));
        return out;
    }

    static int command(CommandSourceStack s) throws com.mojang.brigadier.exceptions.CommandSyntaxException {
        ServerPlayer p = s.getPlayerOrException();
        MinecraftServer server = s.getServer();
        int id = SkyblockMod.plot(server, p);
        if (id <= 0) { s.sendFailure(Component.literal("You don't have an island yet.")); return 0; }
        long wait = lastRun.getOrDefault(id, 0L) + COOLDOWN_MS - System.currentTimeMillis();
        int lvl;
        if (wait > 0) lvl = SkyblockMod.score(server, p, "cs_lvl");
        else lvl = update(server, id);
        int rank = 0;
        List<int[]> r = ranking(server);
        for (int i = 0; i < r.size(); i++) if (r.get(i)[0] == id) rank = i + 1;
        Component msg = Component.literal("Island level: ").withStyle(net.minecraft.ChatFormatting.GOLD)
                .append(Component.literal(String.valueOf(lvl)).withStyle(net.minecraft.ChatFormatting.WHITE, net.minecraft.ChatFormatting.BOLD))
                .append(Component.literal(rank > 0 ? "   #" + rank + " on the server" : "").withStyle(net.minecraft.ChatFormatting.GRAY))
                .append(Component.literal(wait > 0 ? "  (counted " + (COOLDOWN_MS - wait) / 1000 + "s ago)" : "").withStyle(net.minecraft.ChatFormatting.DARK_GRAY));
        s.sendSuccess(() -> msg, false);
        s.sendSuccess(() -> Component.literal("Every block counts; valuable blocks (iron, gold, diamond blocks, beacons...) count for more. 100 points = 1 level.")
                .withStyle(net.minecraft.ChatFormatting.DARK_GRAY), false);
        return lvl;
    }

    static int top(CommandSourceStack s) {
        MinecraftServer server = s.getServer();
        List<int[]> r = ranking(server);
        s.sendSuccess(() -> Component.literal("Top Islands").withStyle(net.minecraft.ChatFormatting.GOLD, net.minecraft.ChatFormatting.BOLD), false);
        if (r.isEmpty()) s.sendSuccess(() -> Component.literal("No islands on the board yet. /island level puts yours there.").withStyle(net.minecraft.ChatFormatting.GRAY), false);
        for (int i = 0; i < Math.min(TOP, r.size()); i++) {
            int[] e = r.get(i);
            String names = String.join(", ", members(server, e[0]));
            int n = i + 1;
            s.sendSuccess(() -> Component.literal("#" + n + " ").withStyle(n == 1 ? net.minecraft.ChatFormatting.GOLD : net.minecraft.ChatFormatting.YELLOW)
                    .append(Component.literal(names.isEmpty() ? "Island " + e[0] : names).withStyle(net.minecraft.ChatFormatting.WHITE))
                    .append(Component.literal("  level " + e[1]).withStyle(net.minecraft.ChatFormatting.AQUA)), false);
        }
        return r.size();
    }

    static void updateBoard(MinecraftServer server) {
        List<int[]> r = ranking(server);
        StringBuilder json = new StringBuilder("[\"\",{\"text\":\"Top Islands\",\"color\":\"gold\",\"bold\":true}");
        if (r.isEmpty()) json.append(",{\"text\":\"\\nUse /island level to get on the board\",\"color\":\"gray\"}");
        for (int i = 0; i < Math.min(TOP, r.size()); i++) {
            int[] e = r.get(i);
            List<String> m = members(server, e[0]);
            String names = m.isEmpty() ? "Island " + e[0] : m.size() > 2 ? m.get(0) + ", " + m.get(1) + " +" + (m.size() - 2) : String.join(", ", m);
            json.append(",{\"text\":\"\\n").append(i + 1).append(". \",\"color\":\"").append(i == 0 ? "gold" : i < 3 ? "yellow" : "gray").append("\"}")
                .append(",{\"text\":\"").append(esc(names)).append("  \",\"color\":\"white\"}")
                .append(",{\"text\":\"").append(e[1]).append("\",\"color\":\"aqua\"}");
        }
        json.append("]");
        server.getCommands().performPrefixedCommand(server.createCommandSourceStack().withSuppressedOutput(),
                "execute in minecraft:overworld run data modify entity @e[type=minecraft:text_display,tag=cs_top,limit=1] text set value " + json);
    }

    /** Every 5 minutes: recount the islands of everyone online in the overworld. */
    static void onTick(MinecraftServer server) {
        if (++tick % AUTO_TICKS != 0) return;
        Set<Integer> ids = new TreeSet<>();
        for (ServerPlayer p : server.getPlayerList().getPlayers()) {
            int id = SkyblockMod.plot(server, p);
            if (id > 0 && p.level() == server.overworld()) ids.add(id);
        }
        for (int id : ids) update(server, id);
    }

    private static String esc(String s) { return s.replace("\\", "\\\\").replace("\"", "\\\""); }
}

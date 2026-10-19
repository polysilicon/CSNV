package crispy.pvp;

import net.minecraft.server.MinecraftServer;
import net.minecraft.world.scores.Objective;
import net.minecraft.world.scores.PlayerScoreEntry;

import java.util.ArrayList;
import java.util.Comparator;
import java.util.List;

/**
 * Lobby leaderboards: every 5 s, writes the top 5 of a scoreboard objective into a text_display
 * placed by the datapack (pvp:admin/place_leaderboard). Fake players (#...) and zero scores are skipped.
 */
public final class Leaderboards {
    private Leaderboards() {}

    // objective, text_display tag, title, colour
    private static final String[][] BOARDS = {
            {"pvp.kills", "pvp.lb.kills", "⚔ Top Kills", "aqua"},
            {"pvp.best", "pvp.lb.streak", "🔥 Best Kill Streak", "gold"},
            {"pve.best", "pvp.lb.wave", "☣ Best Outbreak Wave", "green"},
    };
    private static final int TOP = 5, EVERY_TICKS = 100;
    private static int tick;

    public static void onTick(MinecraftServer server) {
        if (++tick % EVERY_TICKS != 0) return;
        for (String[] b : BOARDS) {
            Objective obj = server.getScoreboard().getObjective(b[0]);
            if (obj == null) continue;
            List<PlayerScoreEntry> rows = new ArrayList<>();
            for (PlayerScoreEntry e : server.getScoreboard().listPlayerScores(obj))
                if (!e.owner().startsWith("#") && e.value() > 0) rows.add(e);
            rows.sort(Comparator.comparingInt(PlayerScoreEntry::value).reversed());
            StringBuilder json = new StringBuilder("[{\"text\":\"").append(esc(b[2])).append("\",\"color\":\"").append(b[3]).append("\",\"bold\":true}");
            if (rows.isEmpty()) json.append(",{\"text\":\"\\nNo scores yet\",\"color\":\"gray\"}");
            for (int i = 0; i < Math.min(TOP, rows.size()); i++) {
                PlayerScoreEntry e = rows.get(i);
                String medal = i == 0 ? "gold" : i == 1 ? "white" : i == 2 ? "#cd7f32" : "gray";
                json.append(",{\"text\":\"\\n").append(i + 1).append(". \",\"color\":\"").append(medal).append("\"}")
                    .append(",{\"text\":\"").append(esc(e.owner())).append(" \",\"color\":\"white\"}")
                    .append(",{\"text\":\"").append(e.value()).append("\",\"color\":\"").append(b[3]).append("\"}");
            }
            json.append("]");
            // rewritten every time (3 small commands per 5 s), so boards placed or re-placed later fill in on their own
            String text = json.toString();
            server.getCommands().performPrefixedCommand(server.createCommandSourceStack().withSuppressedOutput(),
                    "data modify entity @e[type=minecraft:text_display,tag=" + b[1] + ",limit=1] text set value " + text);
        }
    }

    private static String esc(String s) { return s.replace("\\", "\\\\").replace("\"", "\\\""); }
}

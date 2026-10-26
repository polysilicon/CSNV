package crispy.pvp;

import net.minecraft.server.MinecraftServer;
import net.minecraft.world.scores.Objective;
import net.minecraft.world.scores.PlayerScoreEntry;

import java.util.ArrayList;
import java.util.Comparator;
import java.util.List;

/**
 * The lobby leaderboard: every 5 s, writes the top 3 of each scoreboard objective below into the one big text_display
 * placed by the datapack (pvp:admin/place_leaderboard). Fake players (#...) and zero scores are skipped.
 */
public final class Leaderboards {
    private Leaderboards() {}

    // objective, title, colour
    private static final String[][] BOARDS = {
            {"pvp.kills", "⚔ Top Kills", "aqua"},
            {"pvp.best", "🔥 Best Kill Streak", "gold"},
            {"pvp.elo", "⚔ Duel Rating", "red"},
            {"pve.best", "☣ Best Outbreak Wave", "green"},
            {"tw.best", "🗼 Best Tower Floor", "light_purple"},
    };
    private static final String TAG = "pvp.lb.all";
    private static final String[] MEDAL = {"gold", "white", "#cd7f32"};
    private static final int TOP = 3, EVERY_TICKS = 100;
    private static int tick;

    public static void onTick(MinecraftServer server) {
        if (++tick % EVERY_TICKS != 0) return;
        StringBuilder json = new StringBuilder("[\"\",{\"text\":\"🏆 MULTIVERSE LEADERBOARDS 🏆\",\"color\":\"light_purple\",\"bold\":true}");
        for (String[] b : BOARDS) {
            Objective obj = server.getScoreboard().getObjective(b[0]);
            List<PlayerScoreEntry> rows = new ArrayList<>();
            if (obj != null)
                for (PlayerScoreEntry e : server.getScoreboard().listPlayerScores(obj))
                    if (!e.owner().startsWith("#") && e.value() > 0) rows.add(e);
            rows.sort(Comparator.comparingInt(PlayerScoreEntry::value).reversed());
            json.append(",{\"text\":\"\\n\\n").append(esc(b[1])).append("\",\"color\":\"").append(b[2]).append("\",\"bold\":true}");
            json.append(",{\"text\":\"\\n\"}");
            if (rows.isEmpty()) json.append(",{\"text\":\"No scores yet\",\"color\":\"dark_gray\"}");
            for (int i = 0; i < Math.min(TOP, rows.size()); i++) {
                PlayerScoreEntry e = rows.get(i);
                json.append(",{\"text\":\"").append(i == 0 ? "" : "     ").append(i + 1).append(". \",\"color\":\"").append(MEDAL[i]).append("\"}")
                    .append(",{\"text\":\"").append(esc(e.owner())).append(" \",\"color\":\"white\"}")
                    .append(",{\"text\":\"").append(e.value()).append("\",\"color\":\"").append(b[2]).append("\"}");
            }
        }
        json.append("]");
        // rewritten every time (one small command per 5 s), so a board placed or re-placed later fills in on its own
        server.getCommands().performPrefixedCommand(server.createCommandSourceStack().withSuppressedOutput(),
                "data modify entity @e[type=minecraft:text_display,tag=" + TAG + ",limit=1] text set value " + json);
    }

    private static String esc(String s) { return s.replace("\\", "\\\\").replace("\"", "\\\""); }
}

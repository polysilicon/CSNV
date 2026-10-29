package crispy.pvp;

import net.minecraft.server.MinecraftServer;
import net.minecraft.world.scores.Objective;
import net.minecraft.world.scores.ScoreHolder;

import java.time.LocalDate;
import java.time.ZoneOffset;

/**
 * Limited-time events: every 5 s, sets a fake-player flag on the "pvp" objective that the datapack checks
 * (#halloween pvp = 1 through HALLOWEEN_END, UTC, then 0: Haunted Night's NPC goes away and its lobby won't open).
 */
public final class Events {
    private Events() {}

    static final LocalDate HALLOWEEN_END = LocalDate.of(2026, 11, 7);
    private static int tick;

    public static void onTick(MinecraftServer server) {
        if (++tick % 100 != 0) return;
        Objective obj = server.getScoreboard().getObjective("pvp");
        if (obj == null) return;
        boolean on = !LocalDate.now(ZoneOffset.UTC).isAfter(HALLOWEEN_END);
        server.getScoreboard().getOrCreatePlayerScore(ScoreHolder.forNameOnly("#halloween"), obj).set(on ? 1 : 0);
    }
}

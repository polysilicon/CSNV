package crispy.pvp;

import net.minecraft.server.MinecraftServer;
import net.minecraft.server.level.ServerLevel;
import net.minecraft.world.entity.LivingEntity;
import net.minecraft.world.entity.Mob;
import net.minecraft.world.level.entity.EntityTypeTest;
import net.minecraft.world.scores.Objective;
import net.minecraft.world.scores.ReadOnlyScoreInfo;
import net.minecraft.world.scores.ScoreHolder;
import net.minecraft.world.scores.Scoreboard;

/**
 * Outbreak's Core Defense map (the datapack's core.py): every 10 ticks, a mob tagged pve.seek that isn't after a
 * player walks towards the core at (#corex, #corey, #corez) on the "pve" objective. A walled-in core still gets a
 * path as close as it can, so the mob ends up at the wall, where the datapack has it dig through.
 */
public final class CoreSeek {
    private CoreSeek() {}

    private static int tick;

    public static void onTick(MinecraftServer server) {
        if (++tick % 10 != 0) return;
        Scoreboard sb = server.getScoreboard();
        Objective obj = sb.getObjective("pve");
        if (obj == null) return;
        ReadOnlyScoreInfo xs = sb.getPlayerScoreInfo(ScoreHolder.forNameOnly("#corex"), obj);
        ReadOnlyScoreInfo ys = sb.getPlayerScoreInfo(ScoreHolder.forNameOnly("#corey"), obj);
        ReadOnlyScoreInfo zs = sb.getPlayerScoreInfo(ScoreHolder.forNameOnly("#corez"), obj);
        if (xs == null || ys == null || zs == null) return;
        double x = xs.value() + 0.5, y = ys.value(), z = zs.value() + 0.5;
        ServerLevel level = server.overworld();
        for (Mob m : level.getEntities(EntityTypeTest.forClass(Mob.class), e -> e.entityTags().contains("pve.seek"))) {
            LivingEntity t = m.getTarget();
            if (t != null && t.isAlive()) continue;
            if (m.distanceToSqr(x, y, z) < 6.0) continue;   // already at the core
            m.getNavigation().moveTo(x, y, z, 1.0);
        }
    }
}

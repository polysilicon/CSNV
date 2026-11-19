package crispy.falling;

import net.minecraft.resources.ResourceKey;
import net.minecraft.server.MinecraftServer;
import net.minecraft.server.level.ServerPlayer;
import net.minecraft.world.level.Level;
import net.minecraft.world.phys.Vec3;

import java.util.HashMap;
import java.util.Map;
import java.util.UUID;

/**
 * 2.18.3: a teleport clears the distance you've fallen.
 *
 * Teleports don't reset fall distance, so a player caught falling off the hub (sent back to spawn at y ~-9, after
 * ~110 blocks) or into the void under an island (sent home by the island-bounds check at y -128, after ~230 blocks)
 * landed with all of it and died ("fell from a high place", at hub spawn or on top of their island). Here, once a tick
 * (after the datapack's tick functions, before the client's landing packet is handled), any player who moved more
 * than JUMP blocks since the last tick, or changed dimension, has been teleported: their fall distance is reset.
 * Falling never covers that much in one tick (terminal velocity is under 4 blocks a tick), so normal falls still hurt.
 */
final class FallGuard {
    private FallGuard() {}

    static final double JUMP = 16;
    record Last(ResourceKey<Level> dim, Vec3 pos) {}
    private static final Map<UUID, Last> last = new HashMap<>();
    private static long ticks;

    static void onTick(MinecraftServer server) {
        for (ServerPlayer p : server.getPlayerList().getPlayers()) {
            Last l = last.get(p.getUUID());
            Vec3 now = p.position();
            ResourceKey<Level> dim = p.level().dimension();
            if (l == null || l.dim() != dim || l.pos().distanceToSqr(now) > JUMP * JUMP) {
                if (p.fallDistance > 3) p.resetFallDistance();   // joined, respawned or teleported
            }
            last.put(p.getUUID(), new Last(dim, now));
        }
        if (++ticks % 1200 == 0) last.keySet().removeIf(u -> server.getPlayerList().getPlayer(u) == null);
    }
}

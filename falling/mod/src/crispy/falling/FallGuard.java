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
 * 2.18.3: a teleport into the hub clears the distance you've fallen.
 *
 * Teleports don't reset fall distance, so a player caught falling off the hub (sent back to spawn from y ~-9, after
 * ~110 blocks) landed with all of it and died ("fell from a high place" at hub spawn). Here, once a tick (after the
 * datapack's tick functions, before the client's landing packet is handled), a player who moved more than JUMP blocks
 * since the last tick, or changed dimension, and is now in the hub has been teleported there: their fall distance is
 * reset. Falling never covers that much in one tick (terminal velocity is under 4 blocks a tick).
 * Islands are left alone on purpose: falling off your island into the void kills you as normal (the island-bounds
 * check no longer catches players below the island, see skyblock.py p/bounds2).
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
            boolean jumped = l == null || l.dim() != dim || l.pos().distanceToSqr(now) > JUMP * JUMP;
            if (jumped && p.fallDistance > 3 && HubPlots.inHub(p)) p.resetFallDistance();   // teleported into the hub
            last.put(p.getUUID(), new Last(dim, now));
        }
        if (++ticks % 1200 == 0) last.keySet().removeIf(u -> server.getPlayerList().getPlayer(u) == null);
    }
}

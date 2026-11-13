package crispy.ez;

import net.fabricmc.fabric.api.command.v2.CommandRegistrationCallback;
import net.fabricmc.fabric.api.event.lifecycle.v1.ServerLifecycleEvents;
import net.fabricmc.fabric.api.event.lifecycle.v1.ServerTickEvents;
import net.fabricmc.fabric.api.networking.v1.ServerPlayConnectionEvents;
import net.minecraft.ChatFormatting;
import net.minecraft.commands.Commands;
import net.minecraft.core.particles.DustParticleOptions;
import net.minecraft.server.MinecraftServer;
import net.minecraft.server.level.ServerLevel;
import net.minecraft.server.level.ServerPlayer;

import java.io.IOException;
import java.nio.file.Files;
import java.nio.file.Path;
import java.time.LocalDate;
import java.time.ZoneOffset;
import java.time.temporal.IsoFields;
import java.util.Comparator;
import java.util.HashSet;
import java.util.Set;
import java.util.UUID;
import java.util.stream.Stream;

import static crispy.ez.Ui.t;

/**
 * Weekly city reset and the radiation edge (1.1.0).
 *
 * Reset: on the first server start of a new ISO week (UTC), before the worlds load, the Lost Cities dimension is moved
 * to old_city/last (replacing the previous one), so The Lost Cities generates a fresh city: player-built blocks and
 * blast damage are gone. A few seconds after start the mod re-runs /ezadmin setup and redraws the zone map. Anyone who
 * logs in still standing in the old city is sent to camp with what they carried. The server needs a restart each week
 * (AMP schedule); /ezadmin reset forces one on the next start.
 *
 * Radiation edge: raiders near the zone border see a green haze wall along it, hear a Geiger counter, and get a
 * one-time warning; past it the datapack deals radiation damage (raid/outside). The map draws the border in red.
 */
final class Reset {
    private Reset() {}

    static final Path STATE = Path.of("config", "crispy_extraction", "reset.txt");
    static final Path CITY_DIR = Path.of("world", "dimensions", "lostcities");
    static boolean didReset;
    static int setupAt = -1;
    static final Set<UUID> moved = new HashSet<>();

    static String week() {
        LocalDate d = LocalDate.now(ZoneOffset.UTC);
        return d.get(IsoFields.WEEK_BASED_YEAR) + "-W" + d.get(IsoFields.WEEK_OF_WEEK_BASED_YEAR);
    }

    static void init() {
        ServerLifecycleEvents.SERVER_STARTING.register(server -> {
            try {
                String now = week(), last = Files.exists(STATE) ? Files.readString(STATE).trim() : "";
                if (!last.isEmpty() && !last.equals(now) && Files.isDirectory(CITY_DIR)) {
                    Path old = Path.of("old_city", "last");
                    if (Files.exists(old)) try (Stream<Path> w = Files.walk(old)) { w.sorted(Comparator.reverseOrder()).forEach(p -> p.toFile().delete()); }
                    Files.createDirectories(old.getParent());
                    Files.move(CITY_DIR, old);
                    Files.deleteIfExists(Interiors.DONE_FILE);   // 1.8.9: the new city's chunks are all to do
                    didReset = true;
                    System.out.println("[crispy-extraction] weekly reset: the city will be regenerated (" + last + " -> " + now + ")");
                }
                Files.createDirectories(STATE.getParent());
                Files.writeString(STATE, now);
            } catch (IOException e) { System.err.println("[crispy-extraction] weekly reset failed: " + e); }
        });
        ServerLifecycleEvents.SERVER_STARTED.register(server -> { if (didReset) setupAt = server.getTickCount() + 200; });
        ServerTickEvents.END_SERVER_TICK.register(server -> {
            if (setupAt >= 0 && server.getTickCount() >= setupAt) {
                setupAt = -1;
                Zone.setup(server);
                ZoneMap.render(server);
                System.out.println("[crispy-extraction] weekly reset: points placed, map redrawing");
            }
            if (server.getTickCount() % 10 == 0) edge(server);
        });
        ServerPlayConnectionEvents.JOIN.register((h, sender, server) -> {
            ServerPlayer p = h.player;
            if (didReset && p.level().dimension().equals(Zone.CITY) && moved.add(p.getUUID())) {
                Plots.run(server, "execute as " + p.getGameProfile().name() + " run function ez:to_camp");
                p.sendSystemMessage(t("The city was rebuilt for the new week while you were away. You're back in camp with everything you carried.", ChatFormatting.YELLOW));
            }
        });
        CommandRegistrationCallback.EVENT.register((d, ctx, env) -> d.register(Commands.literal("ezadmin")
                .requires(Commands.hasPermission(Commands.LEVEL_GAMEMASTERS))
                .then(Commands.literal("reset").executes(c -> {
                    try { Files.writeString(STATE, "forced"); } catch (IOException e) { throw new RuntimeException(e); }
                    c.getSource().sendSuccess(() -> net.minecraft.network.chat.Component.literal("The city will be regenerated on the next restart."), true);
                    return 1;
                }))));
    }

    // ---------------------------------------------------------------- the radiation edge
    static final DustParticleOptions HAZE = new DustParticleOptions(0x6CFF3A, 2.0f);
    static final Set<UUID> warned = new HashSet<>();

    static void edge(MinecraftServer server) {
        ServerLevel lvl = server.getLevel(Zone.CITY);
        if (lvl == null) return;
        int x0 = Zone.CX - Zone.HALF, x1 = Zone.CX + Zone.HALF, z0 = Zone.CZ - Zone.HALF, z1 = Zone.CZ + Zone.HALF;
        for (ServerPlayer p : lvl.players()) {
            if (!Raid.raiding(p)) { warned.remove(p.getUUID()); continue; }
            double x = p.getX(), z = p.getZ(), y = p.getY();
            double dW = x - x0, dE = x1 - x, dN = z - z0, dS = z1 - z;
            double d = Math.min(Math.min(dW, dE), Math.min(dN, dS));
            if (d > 28) continue;
            // a curtain of green haze on each border line within reach, 33 blocks wide, around the player
            for (int side = 0; side < 4; side++) {
                double dist = side == 0 ? dW : side == 1 ? dE : side == 2 ? dN : dS;
                if (Math.abs(dist) > 28) continue;
                for (int s = -16; s <= 16; s += 2) for (int h = -1; h <= 7; h += 2) {
                    double px = side == 0 ? x0 : side == 1 ? x1 : x + s, pz = side >= 2 ? (side == 2 ? z0 : z1) : z + s;
                    lvl.sendParticles(p, HAZE, true, false, px, y + h, pz, 1, 0.3, 0.6, 0.3, 0);
                }
            }
            if (d < 14 && warned.add(p.getUUID()))
                p.sendSystemMessage(t("☢ The green haze marks the radiation zone. Step past it and you take damage every second.", ChatFormatting.GREEN, ChatFormatting.BOLD));
            if (d < 12 && (d < 0 || server.getTickCount() % (d < 5 ? 10 : 20) == 0))
                Ui.sound(p, net.minecraft.sounds.SoundEvents.NOTE_BLOCK_HAT, d < 0 ? 0.9f : 0.5f, 1.9f);
        }
    }
}

package crispy.chattags;

import net.fabricmc.loader.api.FabricLoader;
import net.minecraft.server.MinecraftServer;
import net.minecraft.server.level.ServerPlayer;

import java.nio.file.Files;
import java.nio.file.Path;
import java.nio.file.StandardCopyOption;
import java.util.*;

/** Combat state for the proxy. Hitting or being hit by a player puts both in combat for SECONDS; on the PvP server
 *  players in a duel (pvp.duel) or an Outbreak run (pve.in) count as in combat too. Once a second the server writes
 *  crispy_combat.json in its folder (lowercase name -> epoch ms when they're free), which the CrispyTags proxy plugin
 *  reads so /vote and /cosmetics can't be used to leave a fight. */
public final class Combat {
    static final long SECONDS = 15;
    static final Set<String> FIGHT_TAGS = Set.of("pvp.duel", "pve.in");
    static final Path FILE = FabricLoader.getInstance().getGameDir().resolve("crispy_combat.json");
    static final Map<String, Long> until = new HashMap<>();
    static String last = null;
    static int ticks;

    public static void hit(ServerPlayer victim, ServerPlayer attacker) {
        long u = System.currentTimeMillis() + SECONDS * 1000;
        until.put(victim.getGameProfile().name().toLowerCase(Locale.ROOT), u);
        until.put(attacker.getGameProfile().name().toLowerCase(Locale.ROOT), u);
    }

    public static void tick(MinecraftServer server) {
        if (++ticks < 20) return;
        ticks = 0;
        long now = System.currentTimeMillis();
        until.values().removeIf(u -> u <= now);
        Map<String, Long> out = new TreeMap<>(until);
        for (ServerPlayer p : server.getPlayerList().getPlayers())
            if (!Collections.disjoint(p.entityTags(), FIGHT_TAGS)) out.merge(p.getGameProfile().name().toLowerCase(Locale.ROOT), now + 3000, Math::max);
        StringBuilder b = new StringBuilder("{");
        out.forEach((k, v) -> b.append(b.length() > 1 ? "," : "").append('"').append(k).append("\":").append(v));
        String json = b.append('}').toString();
        if (json.equals(last) && out.isEmpty()) return;   // nothing to say: don't rewrite an empty file every second
        try {
            Path tmp = FILE.resolveSibling("crispy_combat.json.tmp");
            Files.writeString(tmp, json);
            Files.move(tmp, FILE, StandardCopyOption.REPLACE_EXISTING, StandardCopyOption.ATOMIC_MOVE);
            last = json;
        } catch (Exception ignored) {}
    }
}

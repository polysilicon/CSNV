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

    // ---- 1.10.0: commands refused in combat, one per line in config/crispy_combat_block.txt ("home", "trigger market",
    // "tpaccept"...; a line matches the command and anything after it). No file = nothing blocked (only Anarchy has one).
    static final Path BLOCK_FILE = FabricLoader.getInstance().getConfigDir().resolve("crispy_combat_block.txt");
    static List<String> blocked = List.of();
    static long blockedMtime = -2;

    static List<String> blocked() {
        try {
            long m = Files.exists(BLOCK_FILE) ? Files.getLastModifiedTime(BLOCK_FILE).toMillis() : -1;
            if (m != blockedMtime) {
                blockedMtime = m;
                List<String> l = new ArrayList<>();
                if (m >= 0) for (String line : Files.readAllLines(BLOCK_FILE)) {
                    line = line.replaceAll("#.*", "").trim().toLowerCase(Locale.ROOT).replaceAll("^/", "").replaceAll("\\s+", " ");
                    if (!line.isEmpty()) l.add(line);
                }
                blocked = l;
            }
        } catch (Exception ignored) {}
        return blocked;
    }

    public static long secondsLeft(ServerPlayer p) {
        Long u = until.get(p.getGameProfile().getName().toLowerCase(Locale.ROOT));
        long left = u == null ? 0 : u - System.currentTimeMillis();
        if (!Collections.disjoint(p.getTags(), FIGHT_TAGS)) left = Math.max(left, 1000);
        return left <= 0 ? 0 : (left + 999) / 1000;
    }

    /** True (and tells the player) if this command is on the list and they're in combat. */
    public static boolean refuse(ServerPlayer p, String command) {
        List<String> list = blocked();
        if (list.isEmpty()) return false;
        long left = secondsLeft(p);
        if (left <= 0) return false;
        String c = command.trim().toLowerCase(Locale.ROOT).replaceAll("^/", "").replaceAll("\\s+", " ");
        int sp = c.indexOf(' '), colon = c.indexOf(':');
        if (colon > 0 && (sp < 0 || colon < sp)) c = c.substring(colon + 1);   // essentialcommands:home -> home
        for (String b : list) {
            if (c.equals(b) || c.startsWith(b + " ")) {
                String root = c.contains(" ") ? c.substring(0, c.indexOf(' ')) : c;
                p.sendSystemMessage(net.minecraft.network.chat.Component.literal("You can't use /" + root + " in combat (" + left + "s left).")
                        .withStyle(s -> s.withColor(0xFF5555)));
                return true;
            }
        }
        return false;
    }

    public static void hit(ServerPlayer victim, ServerPlayer attacker) {
        long u = System.currentTimeMillis() + SECONDS * 1000;
        until.put(victim.getGameProfile().getName().toLowerCase(Locale.ROOT), u);
        until.put(attacker.getGameProfile().getName().toLowerCase(Locale.ROOT), u);
    }

    public static void tick(MinecraftServer server) {
        if (++ticks < 20) return;
        ticks = 0;
        long now = System.currentTimeMillis();
        until.values().removeIf(u -> u <= now);
        Map<String, Long> out = new TreeMap<>(until);
        for (ServerPlayer p : server.getPlayerList().getPlayers())
            if (!Collections.disjoint(p.getTags(), FIGHT_TAGS)) out.merge(p.getGameProfile().getName().toLowerCase(Locale.ROOT), now + 3000, Math::max);
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

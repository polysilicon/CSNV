package crispy.factions;

import com.massivecraft.factions.Faction;
import org.bukkit.Bukkit;
import org.bukkit.Location;
import org.bukkit.configuration.ConfigurationSection;
import org.bukkit.entity.Entity;
import org.bukkit.entity.Player;
import org.bukkit.entity.Projectile;
import org.bukkit.event.EventHandler;
import org.bukkit.event.EventPriority;
import org.bukkit.event.Listener;
import org.bukkit.event.entity.EntityDamageByEntityEvent;
import org.bukkit.event.entity.PlayerDeathEvent;
import org.bukkit.event.player.*;

import java.util.*;

/** PvP combat tag: hitting or being hit by a player tags both for N seconds. While tagged you can't teleport away,
 *  run escape commands or walk into a safezone, and logging out kills you (items drop where you stood). */
public class CombatTag implements Listener {
    final CrispyFactions plugin;
    final Map<UUID, Long> until = new HashMap<>();
    final Map<UUID, Long> lastWarn = new HashMap<>();
    boolean enabled, killOnLogout, blockSafezone;
    long seconds;
    List<String> blocked = List.of();

    CombatTag(CrispyFactions plugin) {
        this.plugin = plugin;
        load();
        Bukkit.getScheduler().runTaskTimer(plugin, this::tick, 20L, 20L);
    }

    void load() {
        ConfigurationSection c = plugin.getConfig().getConfigurationSection("combat-tag");
        enabled = c == null || c.getBoolean("enabled", true);
        seconds = c == null ? 15 : c.getLong("seconds", 15);
        killOnLogout = c == null || c.getBoolean("kill-on-logout", true);
        blockSafezone = c == null || c.getBoolean("block-safezone-entry", true);
        blocked = c == null ? List.of() : c.getStringList("blocked-commands").stream().map(s -> s.toLowerCase(Locale.ROOT).trim()).toList();
        if (!enabled) until.clear();
    }

    boolean exempt(Player p) { return p.hasPermission("crispy.combat.bypass"); }
    long left(Player p) {
        Long u = until.get(p.getUniqueId());
        return u == null ? 0 : Math.max(0, (u - System.currentTimeMillis() + 999) / 1000);
    }
    boolean tagged(Player p) { return left(p) > 0; }

    void tag(Player p) {
        if (exempt(p) || p.isDead()) return;
        if (!tagged(p)) CrispyFactions.msg(p, "&cYou are in combat! &7Don't log out for &f" + seconds + "s&7.");
        until.put(p.getUniqueId(), System.currentTimeMillis() + seconds * 1000);
        p.sendActionBar(CrispyFactions.c("&c⚔ Combat: &f" + seconds + "s"));
    }

    static Player attacker(Entity d) {
        if (d instanceof Player p) return p;
        if (d instanceof Projectile pr && pr.getShooter() instanceof Player p) return p;
        return null;
    }

    @EventHandler(priority = EventPriority.MONITOR, ignoreCancelled = true)
    public void onHit(EntityDamageByEntityEvent e) {
        if (!enabled || !(e.getEntity() instanceof Player victim)) return;
        Player a = attacker(e.getDamager());
        if (a == null || a.equals(victim)) return;
        tag(victim); tag(a);
    }

    /** crispy_combat.json in the server folder (lowercase name -> epoch ms when free), read by the CrispyTags proxy
     *  plugin so the network-wide /vote and /cosmetics can't be used to leave a fight. Rewritten only when it changes. */
    static final java.nio.file.Path FILE = java.nio.file.Path.of("crispy_combat.json");
    String lastFile;
    void writeFile() {
        StringBuilder b = new StringBuilder("{");
        for (Map.Entry<UUID, Long> en : until.entrySet()) {
            Player p = Bukkit.getPlayer(en.getKey());
            if (p != null) b.append(b.length() > 1 ? "," : "").append('"').append(p.getName().toLowerCase(Locale.ROOT)).append("\":").append(en.getValue());
        }
        String json = b.append('}').toString();
        if (json.equals(lastFile)) return;
        try {
            java.nio.file.Path tmp = FILE.resolveSibling("crispy_combat.json.tmp");
            java.nio.file.Files.writeString(tmp, json);
            java.nio.file.Files.move(tmp, FILE, java.nio.file.StandardCopyOption.REPLACE_EXISTING, java.nio.file.StandardCopyOption.ATOMIC_MOVE);
            lastFile = json;
        } catch (Exception ignored) {}
    }

    void tick() {
        writeFile();
        if (until.isEmpty()) return;
        long now = System.currentTimeMillis();
        for (Iterator<Map.Entry<UUID, Long>> it = until.entrySet().iterator(); it.hasNext(); ) {
            Map.Entry<UUID, Long> en = it.next();
            Player p = Bukkit.getPlayer(en.getKey());
            if (p == null) { it.remove(); continue; }
            long s = (en.getValue() - now + 999) / 1000;
            if (s <= 0) { it.remove(); p.sendActionBar(CrispyFactions.c("&a✔ Out of combat")); CrispyFactions.msg(p, "&aYou are no longer in combat."); }
            else p.sendActionBar(CrispyFactions.c("&c⚔ Combat: &f" + s + "s"));
        }
    }

    @EventHandler(priority = EventPriority.MONITOR)
    public void onDeath(PlayerDeathEvent e) { until.remove(e.getEntity().getUniqueId()); }

    @EventHandler(priority = EventPriority.LOWEST)
    public void onQuit(PlayerQuitEvent e) {
        Player p = e.getPlayer();
        boolean was = tagged(p);
        until.remove(p.getUniqueId()); lastWarn.remove(p.getUniqueId());
        if (!was || !killOnLogout || exempt(p)) return;
        // server kicks (restarts, AFK, staff) are not punished; leaving, crashing out or switching servers is
        if (e.getReason() == PlayerQuitEvent.QuitReason.KICKED) return;
        p.setHealth(0.0);
        CrispyFactions.bc("&c" + p.getName() + " &7logged out during combat and was killed.");
    }

    boolean isBlocked(String message) {
        String m = message.toLowerCase(Locale.ROOT).replaceFirst("^/", "").trim();
        int sp = m.indexOf(' ');
        String first = sp < 0 ? m : m.substring(0, sp);
        if (first.contains(":")) m = m.substring(first.indexOf(':') + 1);   // essentials:home -> home
        for (String b : blocked) if (m.equals(b) || m.startsWith(b + " ")) return true;
        return false;
    }

    @EventHandler(priority = EventPriority.LOWEST, ignoreCancelled = true)
    public void onCommand(PlayerCommandPreprocessEvent e) {
        if (!enabled || !tagged(e.getPlayer()) || !isBlocked(e.getMessage())) return;
        e.setCancelled(true);
        CrispyFactions.msg(e.getPlayer(), "&cYou can't use that in combat &7(&f" + left(e.getPlayer()) + "s &7left).");
    }

    static boolean safezone(Location l) { Faction f = CrispyFactions.factionAt(l); return f != null && f.isSafeZone(); }

    @EventHandler(priority = EventPriority.HIGH, ignoreCancelled = true)
    public void onTeleport(PlayerTeleportEvent e) {
        Player p = e.getPlayer();
        if (!enabled || !tagged(p) || e.getTo() == null) return;
        PlayerTeleportEvent.TeleportCause c = e.getCause();
        boolean escape = c == PlayerTeleportEvent.TeleportCause.COMMAND || c == PlayerTeleportEvent.TeleportCause.PLUGIN
                && !e.getFrom().getWorld().equals(e.getTo().getWorld());
        boolean intoSafe = blockSafezone && safezone(e.getTo()) && !safezone(e.getFrom());
        if (!escape && !intoSafe) return;
        e.setCancelled(true);
        CrispyFactions.msg(p, "&cYou can't teleport " + (intoSafe ? "into spawn " : "") + "while in combat &7(&f" + left(p) + "s &7left).");
    }

    @EventHandler(priority = EventPriority.HIGH, ignoreCancelled = true)
    public void onMove(PlayerMoveEvent e) {
        if (!enabled || !blockSafezone || !e.hasChangedBlock()) return;
        Location from = e.getFrom(), to = e.getTo();
        if ((from.getBlockX() >> 4) == (to.getBlockX() >> 4) && (from.getBlockZ() >> 4) == (to.getBlockZ() >> 4) && from.getWorld() == to.getWorld()) return;
        Player p = e.getPlayer();
        if (!tagged(p) || !safezone(to) || safezone(from)) return;
        e.setTo(from.clone().setDirection(to.getDirection()));
        long now = System.currentTimeMillis();
        if (now - lastWarn.getOrDefault(p.getUniqueId(), 0L) > 2000) {
            lastWarn.put(p.getUniqueId(), now);
            CrispyFactions.msg(p, "&cYou can't enter spawn while in combat &7(&f" + left(p) + "s &7left).");
        }
    }
}

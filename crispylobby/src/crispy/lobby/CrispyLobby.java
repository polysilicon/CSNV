package crispy.lobby;

import io.papermc.paper.scoreboard.numbers.NumberFormat;
import net.kyori.adventure.text.Component;
import net.kyori.adventure.text.serializer.legacy.LegacyComponentSerializer;
import org.bukkit.Bukkit;
import org.bukkit.Location;
import org.bukkit.World;
import org.bukkit.event.player.PlayerMoveEvent;
import org.bukkit.event.player.PlayerTeleportEvent;
import org.bukkit.entity.Player;
import org.bukkit.event.EventHandler;
import org.bukkit.event.Listener;
import org.bukkit.event.player.PlayerJoinEvent;
import org.bukkit.event.player.PlayerQuitEvent;
import org.bukkit.plugin.java.JavaPlugin;
import org.bukkit.scoreboard.*;

import java.util.*;

/** Lobby sidebar (replaces DeluxeHub's scoreboard, which crashes on Paper 26.x), lobby spawn handling
 *  (every join lands on the spawn point, anyone above the barrier ceiling is brought back) and the
 *  network stats board + /stats (NetworkStats) and the network vote vault + cosmetics (Votes). */
public class CrispyLobby extends JavaPlugin implements Listener {
    static final LegacyComponentSerializer AMP = LegacyComponentSerializer.legacyAmpersand();
    final Map<UUID, Objective> boards = new HashMap<>();
    NetworkStats stats;
    Votes votes;

    @Override public void onEnable() {
        saveDefaultConfig();
        getServer().getPluginManager().registerEvents(this, this);
        long every = Math.max(1, getConfig().getLong("sidebar.refresh-seconds", 5)) * 20L;
        Bukkit.getScheduler().runTaskTimer(this, () -> Bukkit.getOnlinePlayers().forEach(this::update), every, every);
        for (Player p : Bukkit.getOnlinePlayers()) show(p);
        stats = new NetworkStats(this);
        stats.start();
        votes = new Votes(this);
        getServer().getPluginManager().registerEvents(votes, this);
        if (getServer().getPluginManager().getPlugin("Votifier") != null) getServer().getPluginManager().registerEvents(new VoteListener(votes), this);
        else getLogger().warning("NuVotifier (Votifier) not found: server-list votes won't be received");
        votes.start();
    }

    @Override public void onDisable() { if (stats != null) stats.stop(); if (votes != null) votes.stop(); }

    @Override public boolean onCommand(org.bukkit.command.CommandSender s, org.bukkit.command.Command c, String l, String[] a) {
        if (c.getName().equalsIgnoreCase("vote") || c.getName().equalsIgnoreCase("cosmetics")) return votes.command(s, c.getName(), a);
        if (c.getName().equalsIgnoreCase("stats")) {
            String who = a.length > 0 ? a[0] : s.getName();
            stats.showStats(s, who);
            return true;
        }
        if (a.length >= 1 && a[0].equalsIgnoreCase("leaderboard")) {
            if (a.length >= 2 && a[1].equalsIgnoreCase("here") && s instanceof Player p) {
                stats.moveHere(p); s.sendMessage(AMP.deserialize("&aNetwork stats board moved here."));
            } else if (a.length >= 2 && a[1].equalsIgnoreCase("refresh")) {
                Bukkit.getScheduler().runTaskAsynchronously(this, stats::collect); s.sendMessage(AMP.deserialize("&aRefreshing network stats..."));
            } else s.sendMessage(AMP.deserialize("&7/crispylobby leaderboard here &8| &7/crispylobby leaderboard refresh"));
            return true;
        }
        reloadConfig(); votes.load(); boards.clear(); Bukkit.getOnlinePlayers().forEach(this::show);
        s.sendMessage(AMP.deserialize("&aCrispyLobby reloaded.")); return true;
    }

    String fill(Player p, String s) {
        return s.replace("%player%", p.getName()).replace("%online%", String.valueOf(Bukkit.getOnlinePlayers().size()))
                .replace("%online_max%", String.valueOf(Bukkit.getMaxPlayers())).replace("%world%", p.getWorld().getName());
    }

    void show(Player p) {
        if (!getConfig().getBoolean("sidebar.enabled", true)) return;
        Scoreboard sb = Bukkit.getScoreboardManager().getNewScoreboard();
        Objective o = sb.registerNewObjective("crispy", Criteria.DUMMY, Component.empty());
        o.setDisplaySlot(DisplaySlot.SIDEBAR);
        o.numberFormat(NumberFormat.blank());
        boards.put(p.getUniqueId(), o);
        p.setScoreboard(sb);
        update(p);
    }

    void update(Player p) {
        Objective o = boards.get(p.getUniqueId());
        if (o == null) return;
        o.displayName(AMP.deserialize(fill(p, getConfig().getString("sidebar.title", "&dCrispy"))));
        List<String> lines = getConfig().getStringList("sidebar.lines");
        Scoreboard sb = o.getScoreboard();
        for (String e : new ArrayList<>(sb.getEntries())) if (!e.startsWith("line")) sb.resetScores(e);
        for (int i = 0; i < 15; i++) {
            String entry = "line" + i;
            if (i >= lines.size()) { sb.resetScores(entry); continue; }
            Score sc = o.getScore(entry);
            sc.setScore(lines.size() - i);
            sc.customName(AMP.deserialize(fill(p, lines.get(i))));
        }
    }

    Location spawn() {
        World w = Bukkit.getWorld(getConfig().getString("spawn.world", "world"));
        if (w == null) w = Bukkit.getWorlds().get(0);
        return new Location(w, getConfig().getDouble("spawn.x", 0.5), getConfig().getDouble("spawn.y", 66), getConfig().getDouble("spawn.z", 6.5),
                (float) getConfig().getDouble("spawn.yaw", 0), (float) getConfig().getDouble("spawn.pitch", 0));
    }
    @EventHandler public void onMove(PlayerMoveEvent e) {
        if (!e.hasChangedBlock() || e.getTo().getY() < getConfig().getDouble("spawn.rescue-above-y", 300)) return;
        if (e.getPlayer().getGameMode() == org.bukkit.GameMode.SPECTATOR || e.getPlayer().getGameMode() == org.bukkit.GameMode.CREATIVE) return;
        e.getPlayer().teleport(spawn(), PlayerTeleportEvent.TeleportCause.PLUGIN);
    }

    @EventHandler public void onJoin(PlayerJoinEvent e) {
        Player p = e.getPlayer();
        if (getConfig().getBoolean("spawn.on-join", true)) p.teleport(spawn(), PlayerTeleportEvent.TeleportCause.PLUGIN);
        Bukkit.getScheduler().runTaskLater(this, () -> { if (p.isOnline()) show(p); }, getConfig().getLong("sidebar.join-delay-ticks", 40));
    }
    @EventHandler public void onQuit(PlayerQuitEvent e) { boards.remove(e.getPlayer().getUniqueId()); }
}

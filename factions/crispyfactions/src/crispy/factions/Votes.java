package crispy.factions;

import net.kyori.adventure.text.Component;
import net.kyori.adventure.text.event.ClickEvent;
import net.kyori.adventure.text.event.HoverEvent;
import net.milkbowl.vault.economy.Economy;
import org.bukkit.Bukkit;
import org.bukkit.OfflinePlayer;
import org.bukkit.Sound;
import org.bukkit.command.CommandSender;
import org.bukkit.configuration.ConfigurationSection;
import org.bukkit.configuration.file.YamlConfiguration;
import org.bukkit.entity.Player;
import org.bukkit.event.EventHandler;
import org.bukkit.event.Listener;
import org.bukkit.event.player.PlayerJoinEvent;

import java.io.File;
import java.io.IOException;
import java.time.YearMonth;
import java.time.ZoneId;
import java.util.*;

/** Server-list voting rewards. Votes arrive from NuVotifier (see VoteListener); offline voters get them on join. */
public class Votes implements Listener {
    static final ZoneId ZONE = ZoneId.of("America/Chicago");
    final CrispyFactions plugin;
    final File file; final YamlConfiguration data;
    boolean enabled, broadcast; double money; int cases, keyEvery, partyGoal;

    Votes(CrispyFactions plugin) {
        this.plugin = plugin;
        file = new File(plugin.getDataFolder(), "votes.yml");
        data = YamlConfiguration.loadConfiguration(file);
        load();
    }
    void load() {
        ConfigurationSection c = plugin.getConfig().getConfigurationSection("votes");
        enabled = c == null || c.getBoolean("enabled", true);
        money = c == null ? 5000 : c.getDouble("money", 5000);
        cases = c == null ? 1 : c.getInt("cases", 1);
        keyEvery = c == null ? 5 : c.getInt("bonus-key-every", 5);
        partyGoal = c == null ? 30 : c.getInt("party-goal", 30);
        broadcast = c == null || c.getBoolean("broadcast", true);
    }
    void save() { try { data.save(file); } catch (IOException e) { plugin.getLogger().warning("votes save failed: " + e); } }
    static String month() { return YearMonth.now(ZONE).toString(); }

    /** Called on the main thread for every vote NuVotifier receives. */
    void receive(String username, String service) {
        if (!enabled) return;
        OfflinePlayer op = Bukkit.getOfflinePlayerIfCached(username);
        if (op == null) { plugin.getLogger().info("Vote from " + service + " for unknown player '" + username + "' ignored"); return; }
        String base = "players." + op.getUniqueId();
        int total = data.getInt(base + ".total") + 1;
        data.set(base + ".name", op.getName() == null ? username : op.getName());
        data.set(base + ".total", total);
        data.set(base + ".month." + month(), data.getInt(base + ".month." + month()) + 1);
        data.set(base + ".last", System.currentTimeMillis());
        data.set(base + ".pending", data.getInt(base + ".pending") + 1);
        if (keyEvery > 0 && total % keyEvery == 0) data.set(base + ".pending-keys", data.getInt(base + ".pending-keys") + 1);
        int party = data.getInt("party") + 1;
        data.set("party", party);
        save();
        if (broadcast) CrispyFactions.bc("&a" + data.getString(base + ".name") + " &7voted on &f" + service + "&7! &eVote with &f/vote &7for rewards.");
        Player p = op.getPlayer();
        if (p != null) deliver(p);
        if (partyGoal > 0 && party >= partyGoal) voteParty();
        else if (partyGoal > 0 && (partyGoal - party == 10 || partyGoal - party == 5)) CrispyFactions.bc("&dVote party in &f" + (partyGoal - party) + " &dvotes! &7/vote");
    }

    void deliver(Player p) {
        String base = "players." + p.getUniqueId();
        int n = data.getInt(base + ".pending"), keys = data.getInt(base + ".pending-keys");
        if (n <= 0 && keys <= 0) return;
        data.set(base + ".pending", 0); data.set(base + ".pending-keys", 0); save();
        Economy eco = plugin.cases.eco();
        if (eco != null && money > 0 && n > 0) eco.depositPlayer(p, money * n);
        if (cases > 0 && n > 0) plugin.cases.give(p, plugin.cases.caseItem(cases * n));
        if (keys > 0) plugin.cases.give(p, plugin.cases.keyItem(keys));
        CrispyFactions.msg(p, "&aThanks for voting! &7You got &a" + Cases.money(money * n) + (cases > 0 ? " &7+ &6" + cases * n + " Crispy Case" + (cases * n == 1 ? "" : "s") : "")
                + (keys > 0 ? " &7+ &e" + keys + " bonus Case Key" + (keys == 1 ? "" : "s") + " &7(every " + keyEvery + " votes)" : "") + "&7.");
        p.playSound(p.getLocation(), Sound.ENTITY_PLAYER_LEVELUP, 0.7f, 1.4f);
    }

    void voteParty() {
        data.set("party", 0); save();
        CrispyFactions.bc("&d&l★ VOTE PARTY! ★ &7" + partyGoal + " votes reached: everyone online gets a &eCrispy Case Key&7!");
        for (Player p : Bukkit.getOnlinePlayers()) {
            plugin.cases.give(p, plugin.cases.keyItem(1));
            p.playSound(p.getLocation(), Sound.UI_TOAST_CHALLENGE_COMPLETE, 0.8f, 1f);
        }
    }

    @EventHandler public void onJoin(PlayerJoinEvent e) {
        Player p = e.getPlayer();
        Bukkit.getScheduler().runTaskLater(plugin, () -> { if (p.isOnline()) deliver(p); }, 60L);
    }

    // ------------------------------------------------------------------ /vote
    void command(CommandSender s, String[] a) {
        if (a.length >= 2 && a[0].equalsIgnoreCase("test") && s.hasPermission("crispy.admin")) {
            receive(a[1], a.length > 2 ? a[2] : "TestSite"); CrispyFactions.msg(s, "Simulated a vote for " + a[1] + "."); return;
        }
        if (a.length >= 1 && a[0].equalsIgnoreCase("top")) { top(s); return; }
        if (a.length >= 1 && a[0].equalsIgnoreCase("party") && s.hasPermission("crispy.admin")) { voteParty(); return; }
        CrispyFactions.msg(s, "&e&lVote for Crispy &7- each vote: &a" + Cases.money(money) + (cases > 0 ? " &7+ &6" + cases + " Crispy Case" : "")
                + (keyEvery > 0 ? "&7, bonus &eCase Key &7every " + keyEvery + " votes" : ""));
        List<Map<?, ?>> links = plugin.getConfig().getMapList("votes.links");
        int shown = 0;
        for (Map<?, ?> l : links) {
            String name = String.valueOf(l.get("name")), url = String.valueOf(l.get("url"));
            if (url.contains("CHANGE_ME")) continue;
            s.sendMessage(CrispyFactions.c("&8» &b&n" + name).clickEvent(ClickEvent.openUrl(url)).hoverEvent(HoverEvent.showText(Component.text(url))));
            shown++;
        }
        if (shown == 0) CrispyFactions.msg(s, "&7Vote links are coming soon.");
        if (s instanceof Player p) {
            String base = "players." + p.getUniqueId();
            CrispyFactions.msg(p, "&7Your votes: &f" + data.getInt(base + ".total") + " &7total, &f" + data.getInt(base + ".month." + month()) + " &7this month.");
        }
        if (partyGoal > 0) CrispyFactions.msg(s, "&dVote party: &f" + data.getInt("party") + "&7/&f" + partyGoal + " &7(everyone online gets a Case Key).");
        CrispyFactions.msg(s, "&7Top voters this month: &f/vote top");
    }
    void top(CommandSender s) {
        ConfigurationSection ps = data.getConfigurationSection("players");
        String m = month();
        CrispyFactions.msg(s, "&e&lTop voters &7(" + m + ")");
        if (ps == null) { CrispyFactions.msg(s, "&7No votes yet."); return; }
        List<String> ids = new ArrayList<>(ps.getKeys(false));
        ids.removeIf(id -> ps.getInt(id + ".month." + m) <= 0);
        ids.sort(Comparator.comparingInt((String id) -> -ps.getInt(id + ".month." + m)));
        if (ids.isEmpty()) { CrispyFactions.msg(s, "&7No votes yet this month."); return; }
        int i = 1;
        for (String id : ids.subList(0, Math.min(10, ids.size())))
            s.sendMessage(CrispyFactions.c("&6#" + i++ + " &f" + ps.getString(id + ".name") + " &7- &a" + ps.getInt(id + ".month." + m) + " votes"));
    }
}

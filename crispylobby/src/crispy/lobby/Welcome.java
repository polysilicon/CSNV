package crispy.lobby;

import net.kyori.adventure.text.event.ClickEvent;
import net.kyori.adventure.text.event.HoverEvent;
import net.kyori.adventure.title.Title;
import org.bukkit.Bukkit;
import org.bukkit.Material;
import org.bukkit.Sound;
import org.bukkit.configuration.ConfigurationSection;
import org.bukkit.entity.Player;
import org.bukkit.event.EventHandler;
import org.bukkit.event.EventPriority;
import org.bukkit.event.Listener;
import org.bukkit.event.inventory.InventoryClickEvent;
import org.bukkit.event.inventory.InventoryDragEvent;
import org.bukkit.event.player.PlayerJoinEvent;
import org.bukkit.event.player.PlayerQuitEvent;
import org.bukkit.inventory.Inventory;
import org.bukkit.inventory.InventoryHolder;

import java.time.Duration;
import java.util.*;

/** First join to the network: a title, a "Start here" menu of the worlds (one marked as the best place to start),
 *  a welcome line in the lobby and over the Discord bridge so people say hi, and one nudge if they're still in the
 *  hub a minute later. "First join" = never on the lobby before and no earlier trace on Anarchy or Vanilla
 *  (Votes.firstSeen). /welcome opens the menu for anyone. Config: welcome.* */
final class Welcome implements Listener {
    static final class Menu implements InventoryHolder {
        final Map<Integer, String> actions = new HashMap<>(); Inventory inv;
        @Override public Inventory getInventory() { return inv; }
    }
    static final int[] SLOTS = {10, 11, 12, 13, 14, 15, 16};

    final CrispyLobby plugin;
    final Set<UUID> newcomers = new HashSet<>();   // got the welcome this session and haven't picked a world yet

    Welcome(CrispyLobby plugin) { this.plugin = plugin; }

    ConfigurationSection cfg() {
        ConfigurationSection c = plugin.getConfig().getConfigurationSection("welcome");
        return c != null ? c : plugin.getConfig().createSection("welcome");
    }

    @EventHandler(priority = EventPriority.MONITOR)
    public void onJoin(PlayerJoinEvent e) {
        Player p = e.getPlayer();
        if (!cfg().getBoolean("enabled", true) || p.hasPlayedBefore()) return;
        // after DeluxeHub's join title and firework, so ours isn't drawn over
        Bukkit.getScheduler().runTaskLater(plugin, () -> {
            if (!p.isOnline() || !"9999".equals(plugin.votes.firstSeen(p))) return;   // played Anarchy/Vanilla before the lobby existed
            greet(p);
        }, cfg().getLong("delay-ticks", 50));
    }

    void greet(Player p) {
        ConfigurationSection c = cfg();
        newcomers.add(p.getUniqueId());
        p.showTitle(Title.title(Votes.c(c.getString("title", "&d&lWelcome to Crispy")), Votes.c(c.getString("subtitle", "&fPick a world to start")),
                Title.Times.times(Duration.ofMillis(300), Duration.ofSeconds(3), Duration.ofMillis(600))));
        p.playSound(p.getLocation(), Sound.UI_TOAST_CHALLENGE_COMPLETE, 0.7f, 1.1f);
        for (String l : c.getStringList("chat")) p.sendMessage(Votes.c(l.replace("%player%", p.getName())));
        p.sendMessage(Votes.c("  ").append(link("&b&n[Start here]", "/welcome", "&7Open the world picker"))
                .append(Votes.c("  ")).append(link("&9&n[Discord]", "/welcome discord", "&7Get the invite link"))
                .append(Votes.c("  ")).append(link("&d&n[Vote rewards]", "/vote", "&7Free rewards for voting")));
        if (c.getBoolean("announce", true)) {
            String line = c.getString("announce-line", "&d✦ &f%player% &djoined Crispy for the first time. Say hi!").replace("%player%", p.getName());
            Bukkit.getOnlinePlayers().stream().filter(o -> o != p).forEach(o -> o.sendMessage(Votes.c(line)));
            // the Discord bot relays "<name> text" log lines to Discord and cross-chats them to every server
            if (c.getBoolean("discord-relay", true))
                Bukkit.getConsoleSender().sendMessage("<Welcome> " + p.getName() + " joined Crispy for the first time. Say hi!");
        }
        open(p);
        long nudge = c.getLong("nudge-seconds", 60);
        if (nudge > 0) Bukkit.getScheduler().runTaskLater(plugin, () -> {
            if (!p.isOnline() || !newcomers.remove(p.getUniqueId())) return;
            String rec = recommended();
            ConfigurationSection w = rec == null ? null : c.getConfigurationSection("worlds." + rec);
            p.sendMessage(Votes.c(c.getString("nudge", "&7Not sure where to start?") + " ")
                    .append(w == null ? link("&b&n[Open the world picker]", "/welcome", "&7Pick a world")
                            : link("&b&n[Try " + w.getString("short", rec) + "]", "/welcome go " + rec, "&7Join " + w.getString("short", rec))));
            p.playSound(p.getLocation(), Sound.BLOCK_NOTE_BLOCK_PLING, 0.6f, 1.4f);
        }, nudge * 20L);
    }

    static net.kyori.adventure.text.Component link(String text, String cmd, String hover) {
        return Votes.c(text).clickEvent(ClickEvent.runCommand(cmd)).hoverEvent(HoverEvent.showText(Votes.c(hover)));
    }

    String recommended() {
        ConfigurationSection ws = cfg().getConfigurationSection("worlds");
        if (ws == null) return null;
        for (String k : ws.getKeys(false)) if (ws.getBoolean(k + ".recommended")) return k;
        return null;
    }

    void open(Player p) {
        ConfigurationSection c = cfg();
        Menu m = new Menu();
        m.inv = Bukkit.createInventory(m, 36, Votes.c(c.getString("menu-title", "&8Start here: pick a world")));
        var pane = plugin.votes.item(Material.BLACK_STAINED_GLASS_PANE, " ", List.of(), false);
        for (int i = 0; i < 36; i++) m.inv.setItem(i, pane);
        m.inv.setItem(4, plugin.votes.item(Material.NETHER_STAR, "&d&lWelcome to Crispy", List.of("&7Five worlds and a hub, with chat", "&7that follows you everywhere.",
                "", "&7Click a world to join it. Come back", "&7to the hub any time to switch."), false));
        ConfigurationSection ws = c.getConfigurationSection("worlds");
        int i = 0;
        if (ws != null) for (String k : ws.getKeys(false)) {
            if (i >= SLOTS.length) break;
            ConfigurationSection w = ws.getConfigurationSection(k);
            boolean rec = w.getBoolean("recommended");
            List<String> lore = new ArrayList<>(w.getStringList("lore"));
            lore.add("");
            if (rec) lore.add("&a&l★ Best place to start");
            lore.add(k.equals("hub") ? "&eClick to stay here" : "&eClick to join");
            m.inv.setItem(SLOTS[i], plugin.votes.item(Votes.mat(w.getString("icon"), Material.GRASS_BLOCK), w.getString("name", k), lore, rec));
            m.actions.put(SLOTS[i++], "go " + k);
        }
        m.inv.setItem(30, plugin.votes.item(Material.LAPIS_LAZULI, "&9&lDiscord", List.of("&7Events, clips and help.", "&eClick for the invite link"), false));
        m.actions.put(30, "discord");
        m.inv.setItem(32, plugin.votes.item(Material.AMETHYST_SHARD, "&d&lVote rewards", List.of("&7Vote on server lists for rewards", "&7on any server, plus cosmetics.", "&eClick to open"), false));
        m.actions.put(32, "vote");
        p.openInventory(m.inv);
    }

    void act(Player p, String a) {
        if (a.equals("discord")) {
            p.closeInventory();
            String url = cfg().getString("discord", "https://discord.com/invite/hF2bQgU");
            p.sendMessage(Votes.c("&9&lDiscord &8» ").append(Votes.c("&b&n" + url).clickEvent(ClickEvent.openUrl(url)).hoverEvent(HoverEvent.showText(Votes.c("&7Open in your browser")))));
            return;
        }
        if (a.equals("vote")) { p.closeInventory(); plugin.votes.command(p, "vote", new String[0]); return; }
        if (!a.startsWith("go ")) return;
        String k = a.substring(3);
        ConfigurationSection w = cfg().getConfigurationSection("worlds." + k);
        if (w == null) return;
        newcomers.remove(p.getUniqueId());
        p.closeInventory();
        if (k.equals("hub")) { for (String l : w.getStringList("stay")) p.sendMessage(Votes.c(l)); return; }
        p.sendMessage(Votes.c("&7Sending you to " + w.getString("name", k) + "&7..."));
        plugin.votes.connect(p, w.getString("server", k));
    }

    boolean command(org.bukkit.command.CommandSender s, String[] a) {
        if (!(s instanceof Player p)) { s.sendMessage("Run /welcome in game."); return true; }
        if (a.length >= 2 && a[0].equalsIgnoreCase("go")) act(p, "go " + a[1]);
        else if (a.length >= 1 && a[0].equalsIgnoreCase("discord")) act(p, "discord");
        else if (a.length >= 1 && a[0].equalsIgnoreCase("test") && p.hasPermission("crispylobby.admin")) greet(p);   // the full first-join flow, for staff
        else open(p);
        return true;
    }

    @EventHandler public void onDrag(InventoryDragEvent e) { if (e.getInventory().getHolder() instanceof Menu) e.setCancelled(true); }
    @EventHandler public void onClick(InventoryClickEvent e) {
        if (!(e.getInventory().getHolder() instanceof Menu m) || !(e.getWhoClicked() instanceof Player p)) return;
        e.setCancelled(true);
        if (e.getClickedInventory() != e.getInventory()) return;
        String a = m.actions.get(e.getRawSlot());
        if (a != null) Bukkit.getScheduler().runTask(plugin, () -> act(p, a));
    }
    @EventHandler public void onQuit(PlayerQuitEvent e) { newcomers.remove(e.getPlayer().getUniqueId()); }
}

package crispy.lobby;

import com.google.common.io.ByteArrayDataOutput;
import com.google.common.io.ByteStreams;
import com.google.gson.Gson;
import com.google.gson.GsonBuilder;
import com.google.gson.reflect.TypeToken;
import net.kyori.adventure.text.Component;
import net.kyori.adventure.text.event.ClickEvent;
import net.kyori.adventure.text.event.HoverEvent;
import net.kyori.adventure.text.format.TextDecoration;
import org.bukkit.*;
import org.bukkit.command.CommandSender;
import org.bukkit.configuration.ConfigurationSection;
import org.bukkit.entity.Player;
import org.bukkit.event.EventHandler;
import org.bukkit.event.Listener;
import org.bukkit.event.inventory.InventoryClickEvent;
import org.bukkit.event.inventory.InventoryDragEvent;
import org.bukkit.event.player.PlayerJoinEvent;
import org.bukkit.inventory.Inventory;
import org.bukkit.inventory.InventoryHolder;
import org.bukkit.inventory.ItemStack;
import org.bukkit.inventory.meta.ItemMeta;

import java.io.IOException;
import java.io.Reader;
import java.io.Writer;
import java.nio.file.Files;
import java.nio.file.Path;
import java.nio.file.StandardCopyOption;
import java.time.YearMonth;
import java.time.ZoneId;
import java.util.*;
import java.util.concurrent.ExecutorService;
import java.util.concurrent.Executors;
import java.util.concurrent.atomic.AtomicBoolean;

/** Network vote vault. Votes arrive here (NuVotifier on the lobby, see VoteListener); each vote is one unclaimed
 *  reward plus vote points. In /vote the player picks the server a reward goes to; it is queued and handed over by
 *  RCON the next time they are on that server. Points buy cosmetics that work on every server: tags (shown by the
 *  CrispyTags proxy plugin through TAB, and in chat by the chat-tags plugin/mod on each server, from tags.json) and
 *  chat name colours (namecolors.json, read by the same chat-tags plugin/mod).
 *  All data changes happen on the main thread; one worker thread does the RCON work from snapshots. */
public class Votes implements Listener {
    static final ZoneId ZONE = ZoneId.of("America/Chicago");
    static final Gson GSON = new GsonBuilder().setPrettyPrinting().create();

    static final class PD {
        String name; int unclaimed, points, total;
        Map<String, Integer> months = new HashMap<>(), pending = new HashMap<>();
        Set<String> owned = new HashSet<>();
        String tag, color;
        String trail;   // pre-1.5 walking trails; refunded and cleared on load
    }
    record Server(String key, String label, Material icon, Rcon rcon, List<String> reward, List<String> commands) {}
    record Tag(String id, String display, int cost, Material icon, String joinedBefore, String note) {}
    record NameColor(String id, String name, String code, int cost, Material icon) {}
    // what each retired trail cost, for the refund
    static final Map<String, Integer> TRAIL_REFUND = Map.of("hearts", 3, "flames", 4, "notes", 4, "soul", 5, "sakura", 5,
            "sparks", 6, "runes", 6, "glitch", 10, "endrod", 8, "totem", 12);
    record Job(String lower, String name, int count) {}
    static final class Menu implements InventoryHolder {
        final String kind; final Map<Integer, String> actions = new HashMap<>(); Inventory inv;
        Menu(String kind) { this.kind = kind; }
        @Override public Inventory getInventory() { return inv; }
    }

    final CrispyLobby plugin;
    final Path file, tagsFile, colorsFile;
    Map<String, PD> players = new HashMap<>();
    final LinkedHashMap<String, Server> servers = new LinkedHashMap<>();
    final LinkedHashMap<String, Tag> tags = new LinkedHashMap<>();
    final LinkedHashMap<String, NameColor> colors = new LinkedHashMap<>();
    final ExecutorService worker = Executors.newSingleThreadExecutor(r -> { Thread t = new Thread(r, "CrispyLobby-votes"); t.setDaemon(true); return t; });
    final AtomicBoolean busy = new AtomicBoolean();
    final Set<String> inFlight = new HashSet<>();
    int pointsPerVote; boolean announce, botRelay, rconAnnounce;
    final Map<UUID, String> firstSeen = new HashMap<>();   // uuid -> earliest known date on the network, "yyyy-MM-dd" ("9999" if none)
    Set<String> testUsers = Set.of();

    Votes(CrispyLobby plugin) {
        this.plugin = plugin;
        file = plugin.getDataFolder().toPath().resolve("votes.json");
        tagsFile = plugin.getDataFolder().toPath().resolve("tags.json");
        colorsFile = plugin.getDataFolder().toPath().resolve("namecolors.json");
        try (Reader r = Files.newBufferedReader(file)) {
            Map<String, PD> m = GSON.fromJson(r, new TypeToken<Map<String, PD>>() {}.getType());
            if (m != null) players = m;
        } catch (IOException ignored) {}
        boolean migrated = false;
        for (PD pd : players.values()) {
            if (pd.months == null) pd.months = new HashMap<>();
            if (pd.pending == null) pd.pending = new HashMap<>();
            if (pd.owned == null) pd.owned = new HashSet<>();
            int refund = 0;   // trails were retired in 1.5.0: give their points back
            for (Iterator<String> it = pd.owned.iterator(); it.hasNext(); ) {
                String k = it.next();
                if (k.startsWith("trail:")) { refund += TRAIL_REFUND.getOrDefault(k.substring(6), 0); it.remove(); }
            }
            if (refund > 0 || pd.trail != null) migrated = true;
            if (refund > 0) { pd.points += refund; plugin.getLogger().info("Refunded " + refund + " vote points for retired trails to " + pd.name); }
            pd.trail = null;
        }
        if (migrated) save();
        load();
    }

    ConfigurationSection cfg() { return plugin.getConfig().getConfigurationSection("votes"); }

    void load() {
        ConfigurationSection c = cfg();
        servers.values().forEach(s -> s.rcon().close());
        servers.clear(); tags.clear(); colors.clear();
        if (c == null) return;
        pointsPerVote = c.getInt("points-per-vote", 1);
        announce = c.getBoolean("announce", true);
        botRelay = c.getBoolean("discord-relay", true);
        rconAnnounce = c.getBoolean("rcon-announce", false);
        testUsers = new HashSet<>();
        for (String u : c.getStringList("test-usernames")) testUsers.add(u.toLowerCase(Locale.ROOT));
        Path root = Path.of(plugin.getConfig().getString("network-stats.instances-dir", "/AMPStorage/.ampdata/instances"));
        ConfigurationSection ss = c.getConfigurationSection("servers");
        if (ss != null) for (String k : ss.getKeys(false)) {
            ConfigurationSection s = ss.getConfigurationSection(k);
            servers.put(k, new Server(k, s.getString("label", k), mat(s.getString("icon"), Material.GRASS_BLOCK),
                    new Rcon(k, root.resolve(s.getString("instance", k)).resolve("Minecraft/server.properties")),
                    s.getStringList("reward"), s.getStringList("commands")));
        }
        ConfigurationSection ts = plugin.getConfig().getConfigurationSection("cosmetics.tags");
        if (ts != null) for (String k : ts.getKeys(false))
            tags.put(k, new Tag(k, ts.getString(k + ".display", k), ts.getInt(k + ".cost", 5), mat(ts.getString(k + ".icon"), Material.NAME_TAG),
                    ts.getString(k + ".joined-before"), ts.getString(k + ".note")));
        firstSeen.clear();
        ConfigurationSection cs = plugin.getConfig().getConfigurationSection("cosmetics.name-colors");
        if (cs != null) for (String k : cs.getKeys(false))
            colors.put(k, new NameColor(k, cs.getString(k + ".name", k), cs.getString(k + ".code", "&f"), cs.getInt(k + ".cost", 5),
                    mat(cs.getString(k + ".icon"), Material.WHITE_DYE)));
        writeTags();
    }
    static Material mat(String s, Material def) { Material m = s == null ? null : Material.matchMaterial(s); return m == null ? def : m; }

    void start() {
        Bukkit.getMessenger().registerOutgoingPluginChannel(plugin, "BungeeCord");
        Bukkit.getScheduler().runTaskTimer(plugin, this::cycle, 100L, 100L);
    }
    void stop() { save(); worker.shutdownNow(); servers.values().forEach(s -> s.rcon().close()); }

    void save() {
        try {
            Files.createDirectories(file.getParent());
            Path tmp = file.resolveSibling("votes.json.tmp");
            try (Writer w = Files.newBufferedWriter(tmp)) { GSON.toJson(players, w); }
            Files.move(tmp, file, StandardCopyOption.REPLACE_EXISTING, StandardCopyOption.ATOMIC_MOVE);
        } catch (IOException e) { plugin.getLogger().warning("votes save failed: " + e); }
    }
    /** name (lowercase) -> tag text, for the CrispyTags proxy plugin. */
    void writeTags() {
        Map<String, String> out = new TreeMap<>();
        players.forEach((k, pd) -> { Tag t = pd.tag == null ? null : tags.get(pd.tag); if (t != null) out.put(k, t.display()); });
        try {
            Files.createDirectories(tagsFile.getParent());
            Path tmp = tagsFile.resolveSibling("tags.json.tmp");
            Files.writeString(tmp, GSON.toJson(out));
            Files.move(tmp, tagsFile, StandardCopyOption.REPLACE_EXISTING, StandardCopyOption.ATOMIC_MOVE);
        } catch (IOException e) { plugin.getLogger().warning("tags.json write failed: " + e); }
        Map<String, String> cols = new TreeMap<>();   // name (lowercase) -> "&b", "&6&l" or "rainbow"
        players.forEach((k, pd) -> { NameColor c = pd.color == null ? null : colors.get(pd.color); if (c != null) cols.put(k, c.code()); });
        try {
            Path tmp = colorsFile.resolveSibling("namecolors.json.tmp");
            Files.writeString(tmp, GSON.toJson(cols));
            Files.move(tmp, colorsFile, StandardCopyOption.REPLACE_EXISTING, StandardCopyOption.ATOMIC_MOVE);
        } catch (IOException e) { plugin.getLogger().warning("namecolors.json write failed: " + e); }
    }
    /** A name in a colour code ("&b"), a per-letter sequence ("&c|&6|&e") or "rainbow". */
    static String colored(String name, String code) {
        if ("rainbow".equalsIgnoreCase(code)) code = "&c|&6|&e|&a|&b|&9|&d";
        if (!code.contains("|")) return code + name;
        String[] cyc = code.split("\\|");
        StringBuilder b = new StringBuilder();
        for (int i = 0; i < name.length(); i++) b.append(cyc[i % cyc.length]).append(name.charAt(i));
        return b.toString();
    }

    static String month() { return YearMonth.now(ZONE).toString(); }
    PD pd(String name) {
        PD pd = players.computeIfAbsent(name.toLowerCase(Locale.ROOT), k -> new PD());
        if (pd.name == null || Bukkit.getPlayerExact(name) != null) pd.name = name;
        return pd;
    }
    static Component c(String s) { return CrispyLobby.AMP.deserialize(s).decoration(TextDecoration.ITALIC, false); }
    static void msg(CommandSender s, String m) { s.sendMessage(c("&d&lVote &8» &7" + m)); }

    // ------------------------------------------------------------------ votes in
    /** Main thread. */
    void receive(String user, String service, int n) {
        if (testUsers.contains(user.toLowerCase(Locale.ROOT))) {   // a list site's "send test vote" button
            plugin.getLogger().info("Test vote from " + service + " (username " + user + ") received - voting works.");
            Bukkit.getOnlinePlayers().stream().filter(p -> p.hasPermission("crispylobby.admin"))
                    .forEach(p -> msg(p, "&aTest vote from &f" + service + " &areceived: voting works."));
            return;
        }
        PD pd = pd(user);
        pd.unclaimed += n; pd.points += n * pointsPerVote; pd.total += n;
        pd.months.merge(month(), n, Integer::sum);
        save();
        String line = "&a" + pd.name + " &7voted for CrispyAnarchy on &f" + service + "&7! &eClaim vote rewards in the lobby: &f/vote";
        if (announce) {
            Bukkit.broadcast(c(line));
            // the Discord bot relays "<name> text" lines from this server's log to Discord and (cross-chat) every other server
            if (botRelay) Bukkit.getConsoleSender().sendMessage("<Votes> " + pd.name + " voted for CrispyAnarchy on " + service + "! Claim vote rewards in the lobby: /vote");
            if (rconAnnounce) {
                String json = net.kyori.adventure.text.serializer.gson.GsonComponentSerializer.gson().serialize(CrispyLobby.AMP.deserialize(line));
                List<Server> all = new ArrayList<>(servers.values());
                worker.submit(() -> { for (Server s : all) try { s.rcon().cmd("tellraw @a " + json); } catch (IOException ignored) {} });
            }
        }
        Player p = Bukkit.getPlayerExact(user);
        if (p != null) {
            msg(p, "&aThanks for voting! &7You have &e" + pd.unclaimed + " &7reward" + (pd.unclaimed == 1 ? "" : "s") + " to claim and &d" + pd.points + " &7vote points. &f/vote");
            p.playSound(p.getLocation(), Sound.ENTITY_PLAYER_LEVELUP, 0.7f, 1.4f);
        }
    }

    @EventHandler public void onJoin(PlayerJoinEvent e) {
        Player p = e.getPlayer();
        PD pd = players.get(p.getName().toLowerCase(Locale.ROOT));
        if (pd == null) return;
        pd.name = p.getName();
        if (pd.unclaimed > 0) Bukkit.getScheduler().runTaskLater(plugin, () -> {
            if (p.isOnline()) p.sendMessage(c("&d&lVote &8» &7You have &e" + pd.unclaimed + " &7unclaimed vote reward" + (pd.unclaimed == 1 ? "" : "s") + ". ")
                    .append(c("&a&n[Claim]").clickEvent(ClickEvent.runCommand("/vote")).hoverEvent(HoverEvent.showText(c("&7Open /vote")))));
        }, 60L);
    }

    // ------------------------------------------------------------------ claiming
    void claim(Player p, String server, boolean all) {
        Server s = servers.get(server);
        PD pd = pd(p.getName());
        if (s == null || s.commands().isEmpty()) return;
        if (pd.unclaimed <= 0) { msg(p, "&cNo rewards to claim. &7Vote with &f/vote links&7."); p.playSound(p.getLocation(), Sound.ENTITY_VILLAGER_NO, 0.7f, 1f); return; }
        int n = all ? pd.unclaimed : 1;
        pd.unclaimed -= n;
        pd.pending.merge(server, n, Integer::sum);
        save();
        p.playSound(p.getLocation(), Sound.ENTITY_EXPERIENCE_ORB_PICKUP, 0.8f, 1.2f);
        p.sendMessage(c("&d&lVote &8» &7Sent &e" + n + " &7reward" + (n == 1 ? "" : "s") + " to " + s.label() + "&7. It arrives the next time you're there. ")
                .append(c("&a&n[Go now]").clickEvent(ClickEvent.runCommand("/vote go " + server)).hoverEvent(HoverEvent.showText(c("&7Join " + s.label())))));
        open(p);
    }

    void connect(Player p, String server) {
        if (!servers.containsKey(server)) return;
        ByteArrayDataOutput out = ByteStreams.newDataOutput();
        out.writeUTF("Connect"); out.writeUTF(server);
        p.sendPluginMessage(plugin, "BungeeCord", out.toByteArray());
    }

    // ------------------------------------------------------------------ worker cycle (every 5 s)
    void cycle() {
        if (servers.isEmpty() || !busy.compareAndSet(false, true)) return;
        Map<String, List<Job>> jobs = new HashMap<>();
        players.forEach((k, pd) -> {
            pd.pending.forEach((srv, n) -> { if (n > 0 && !inFlight.contains(srv + "|" + k)) { jobs.computeIfAbsent(srv, x -> new ArrayList<>()).add(new Job(k, pd.name, n)); inFlight.add(srv + "|" + k); } });
        });
        List<Server> all = new ArrayList<>(servers.values());
        worker.submit(() -> {
            Map<String, Map<String, Integer>> delivered = new HashMap<>();
            try {
                for (Server s : all) {
                    List<String> online;
                    try { online = online(s); } catch (IOException e) { continue; }
                    Map<String, Job> mine = new HashMap<>();
                    for (Job j : jobs.getOrDefault(s.key(), List.of())) mine.put(j.lower(), j);
                    for (String name : online) {
                        String k = name.toLowerCase(Locale.ROOT);
                        try {
                            Job j = mine.get(k);
                            if (j == null) continue;
                            for (int i = 0; i < j.count(); i++) for (String cmd : s.commands()) s.rcon().cmd(cmd.replace("%player%", name));
                            s.rcon().cmd("tellraw " + name + " [{\"text\":\"Vote » \",\"color\":\"light_purple\",\"bold\":true},{\"text\":\"Your "
                                    + j.count() + " vote reward" + (j.count() == 1 ? "" : "s") + " arrived. Thanks for voting!\",\"color\":\"green\",\"bold\":false}]");
                            s.rcon().cmd("execute as " + name + " at @s run playsound minecraft:entity.player.levelup master @s ~ ~ ~ 0.7 1.4");
                            delivered.computeIfAbsent(s.key(), x -> new HashMap<>()).put(k, j.count());
                        } catch (IOException e) { plugin.getLogger().warning("vote delivery on " + s.key() + " failed: " + e.getMessage()); break; }
                    }
                }
            } finally {
                Bukkit.getScheduler().runTask(plugin, () -> {
                    jobs.forEach((srv, l) -> l.forEach(j -> inFlight.remove(srv + "|" + j.lower())));
                    if (!delivered.isEmpty()) {
                        delivered.forEach((srv, m) -> m.forEach((k, n) -> {
                            PD pd = players.get(k);
                            if (pd != null) pd.pending.computeIfPresent(srv, (x, v) -> v - n <= 0 ? null : v - n);
                        }));
                        save();
                    }
                    busy.set(false);
                });
            }
        });
    }

    /** Names on a backend, from its "list" output ("There are 1 of a max of 20 players online: a, b"). */
    static List<String> online(Server s) throws IOException {
        String out = s.rcon().cmd("list").replaceAll("§.", "");
        int i = out.indexOf(':');
        if (i < 0) return List.of();
        List<String> names = new ArrayList<>();
        for (String n : out.substring(i + 1).split(",")) { n = n.trim(); if (!n.isEmpty() && !n.contains(" ")) names.add(n); }
        return names;
    }

    // ------------------------------------------------------------------ menus
    ItemStack item(Material m, String name, List<String> lore, boolean glow) {
        ItemStack it = new ItemStack(m);
        ItemMeta meta = it.getItemMeta();
        meta.displayName(c(name));
        meta.lore(lore.stream().map(Votes::c).toList());
        if (glow) meta.setEnchantmentGlintOverride(true);
        meta.addItemFlags(org.bukkit.inventory.ItemFlag.values());
        it.setItemMeta(meta);
        return it;
    }
    Menu menu(String kind, int rows, String title) {
        Menu m = new Menu(kind);
        m.inv = Bukkit.createInventory(m, rows * 9, c(title));
        ItemStack pane = item(Material.BLACK_STAINED_GLASS_PANE, " ", List.of(), false);
        for (int i = 0; i < rows * 9; i++) m.inv.setItem(i, pane);
        return m;
    }
    void put(Menu m, int slot, ItemStack it, String action) { m.inv.setItem(slot, it); if (action != null) m.actions.put(slot, action); }

    void open(Player p) {
        PD pd = pd(p.getName());
        Menu m = menu("main", 5, "&d&lVote Rewards");
        put(m, 4, item(Material.NETHER_STAR, "&d&lYour votes", List.of(
                "&7Unclaimed rewards: &e" + pd.unclaimed, "&7Vote points: &d" + pd.points,
                "&7Votes this month: &f" + pd.months.getOrDefault(month(), 0) + " &8· &7total: &f" + pd.total, "",
                "&7Every vote = &e1 reward &7you can send to any", "&7server below, plus &d" + pointsPerVote + " vote point" + (pointsPerVote == 1 ? "" : "s") + " &7for cosmetics.", "",
                "&eClick for the vote links"), pd.unclaimed > 0), "links");
        int[] slots = {19, 20, 21, 22, 23, 24, 25};
        int i = 0;
        for (Server s : servers.values()) {
            if (s.commands().isEmpty() || i >= slots.length) continue;
            List<String> lore = new ArrayList<>(List.of("&7Each reward here:"));
            s.reward().forEach(r -> lore.add("&8 • " + r));
            int pend = pd.pending.getOrDefault(s.key(), 0);
            lore.add("");
            if (pend > 0) lore.add("&e" + pend + " &7waiting for you there");
            lore.add(pd.unclaimed > 0 ? "&aClick &7to send 1 reward here" : "&8Vote to get rewards to claim");
            if (pd.unclaimed > 1) lore.add("&aShift-click &7to send all &e" + pd.unclaimed);
            put(m, slots[i++], item(s.icon(), s.label(), lore, pend > 0), "claim:" + s.key());
        }
        put(m, 39, item(Material.GOLD_INGOT, "&6&lTop voters", List.of("&7This month's top 10 in chat"), false), "top");
        Tag tg = pd.tag == null ? null : tags.get(pd.tag);
        NameColor nc = pd.color == null ? null : colors.get(pd.color);
        put(m, 41, item(Material.AMETHYST_SHARD, "&b&lCosmetics", List.of("&7Tags and name colours that show on &fevery server&7.",
                "&7Bought with vote points (&d" + pd.points + "&7).", "",
                "&7Tag: " + (tg == null ? "&8none" : tg.display()), "&7Name colour: " + (nc == null ? "&8none" : colored(nc.name(), nc.code())), "", "&eClick to browse"), false), "cosmetics");
        p.openInventory(m.inv);
    }

    static final int[] GRID = {10, 11, 12, 13, 14, 15, 16, 19, 20, 21, 22, 23, 24, 25, 28, 29, 30, 31, 32, 33, 34, 37, 38, 39, 40, 41, 42, 43};
    ItemStack pointsItem(PD pd) {
        return item(Material.AMETHYST_SHARD, "&d&l" + pd.points + " vote point" + (pd.points == 1 ? "" : "s"),
                List.of("&7You get &d" + pointsPerVote + " &7per vote. &f/vote &7for the links."), false);
    }

    /** Cosmetics hub: one button each for tags and name colours. */
    void openCosmetics(Player p) {
        PD pd = pd(p.getName());
        Menu m = menu("cosmetics", 3, "&b&lCosmetics");
        Tag tg = pd.tag == null ? null : tags.get(pd.tag);
        NameColor nc = pd.color == null ? null : colors.get(pd.color);
        long ownTags = tags.keySet().stream().filter(k -> pd.owned.contains("tag:" + k)).count();
        long ownColors = colors.keySet().stream().filter(k -> pd.owned.contains("color:" + k)).count();
        put(m, 11, item(tg == null ? Material.NAME_TAG : tg.icon(), "&f&lTags", List.of("&7Shown with your name in chat, the tab", "&7list and above your head, everywhere.", "",
                "&7Wearing: " + (tg == null ? "&8none" : tg.display()), "&7Owned: &f" + ownTags + "&7/" + tags.size(), "", "&eClick to browse"), tg != null), "tags");
        put(m, 13, pointsItem(pd), null);
        put(m, 15, item(nc == null ? Material.WHITE_DYE : nc.icon(), "&f&lName colours", List.of("&7Your name in colour in chat on", "&7every server (and in cross-chat).", "",
                "&7Using: " + (nc == null ? "&8none" : colored(nc.name(), nc.code())), "&7Owned: &f" + ownColors + "&7/" + colors.size(), "", "&eClick to browse"), nc != null), "colors");
        put(m, 22, item(Material.ARROW, "&7Back to vote rewards", List.of(), false), "back");
        p.openInventory(m.inv);
    }

    void openTags(Player p) {
        PD pd = pd(p.getName());
        Menu m = menu("tags", 6, "&f&lTags &8(&d" + pd.points + " points&8)");
        int i = 0;
        for (Tag t : tags.values()) {
            if (i >= GRID.length) break;
            boolean own = pd.owned.contains("tag:" + t.id()), on = t.id().equals(pd.tag);
            List<String> lore = new ArrayList<>(List.of("&7Preview: &f<" + t.display() + " &f" + p.getName() + "> hi"));
            if (t.note() != null) lore.add("&8" + t.note());
            if (t.joinedBefore() != null) lore.add(joinedBefore(p, t.joinedBefore()) ? "&6Exclusive: &7you joined before " + t.joinedBefore()
                    : "&cOnly for players who joined before " + t.joinedBefore());
            lore.add("");
            lore.add(on ? "&aWearing &7- click to take off" : own ? "&eOwned &7- click to wear" : "&7Cost: &d" + t.cost() + " points");
            if (!own && pd.points < t.cost()) lore.add("&cNot enough points");
            put(m, GRID[i++], item(t.icon(), t.display(), lore, on), "tag:" + t.id());
        }
        if (pd.tag != null) put(m, 48, item(Material.BARRIER, "&cTake off your tag", List.of(), false), "off:tag");
        put(m, 49, item(Material.ARROW, "&7Back", List.of(), false), "cosmetics");
        put(m, 50, pointsItem(pd), null);
        p.openInventory(m.inv);
    }

    void openColors(Player p) {
        PD pd = pd(p.getName());
        Menu m = menu("colors", 6, "&f&lName colours &8(&d" + pd.points + " points&8)");
        int i = 0;
        for (NameColor c : colors.values()) {
            if (i >= GRID.length) break;
            boolean own = pd.owned.contains("color:" + c.id()), on = c.id().equals(pd.color);
            List<String> lore = new ArrayList<>(List.of("&7Preview: &f<" + colored(p.getName(), c.code()) + "&f> hi", "",
                    on ? "&aUsing &7- click to take off" : own ? "&eOwned &7- click to use" : "&7Cost: &d" + c.cost() + " points"));
            if (!own && pd.points < c.cost()) lore.add("&cNot enough points");
            put(m, GRID[i++], item(c.icon(), colored(c.name(), c.code()), lore, on), "color:" + c.id());
        }
        if (pd.color != null) put(m, 48, item(Material.BARRIER, "&cGo back to a plain name", List.of(), false), "off:color");
        put(m, 49, item(Material.ARROW, "&7Back", List.of(), false), "cosmetics");
        put(m, 50, pointsItem(pd), null);
        p.openInventory(m.inv);
    }

    @EventHandler public void onDrag(InventoryDragEvent e) { if (e.getInventory().getHolder() instanceof Menu) e.setCancelled(true); }

    @EventHandler public void onClick(InventoryClickEvent e) {
        if (!(e.getInventory().getHolder() instanceof Menu m) || !(e.getWhoClicked() instanceof Player p)) return;
        e.setCancelled(true);
        if (e.getClickedInventory() != e.getInventory()) return;
        String a = m.actions.get(e.getRawSlot());
        if (a == null) return;
        if (a.equals("links")) { p.closeInventory(); links(p); }
        else if (a.equals("top")) { p.closeInventory(); top(p); }
        else if (a.equals("cosmetics")) openCosmetics(p);
        else if (a.equals("tags")) openTags(p);
        else if (a.equals("colors")) openColors(p);
        else if (a.startsWith("off:")) {
            PD pd = pd(p.getName());
            if (a.equals("off:tag")) pd.tag = null; else pd.color = null;
            writeTags(); save();
            p.playSound(p.getLocation(), Sound.UI_BUTTON_CLICK, 0.6f, 1f);
            if (a.equals("off:tag")) openTags(p); else openColors(p);
        }
        else if (a.equals("back")) open(p);
        else if (a.startsWith("claim:")) claim(p, a.substring(6), e.isShiftClick());
        else if (a.startsWith("tag:") || a.startsWith("color:")) cosmetic(p, a);
    }

    // ------------------------------------------------------------------ "joined before" (the OG tag)
    /** Earliest date the network has for this player: Anarchy (or other) advancement timestamps, the firstPlayed time
     *  Paper left in old player files, and those files' last-saved date. Configured in cosmetics.joined-sources. */
    String firstSeen(Player p) {
        return firstSeen.computeIfAbsent(p.getUniqueId(), u -> {
            String best = "9999";
            Path root = Path.of(plugin.getConfig().getString("network-stats.instances-dir", "/AMPStorage/.ampdata/instances"));
            java.util.regex.Pattern ts = java.util.regex.Pattern.compile("\\d{4}-\\d{2}-\\d{2}(?= \\d{2}:\\d{2}:\\d{2})");
            for (String dir : plugin.getConfig().getStringList("cosmetics.joined-sources.advancements")) {
                try {
                    java.util.regex.Matcher m = ts.matcher(Files.readString(root.resolve(dir).resolve(u + ".json")));
                    while (m.find()) if (m.group().compareTo(best) < 0) best = m.group();
                } catch (IOException ignored) {}
            }
            for (String dir : plugin.getConfig().getStringList("cosmetics.joined-sources.player-data")) {
                Path f = root.resolve(dir).resolve(u + ".dat");
                try {
                    String mod = Files.getLastModifiedTime(f).toInstant().toString().substring(0, 10);
                    if (mod.compareTo(best) < 0) best = mod;
                    byte[] raw;
                    try (var in = new java.util.zip.GZIPInputStream(Files.newInputStream(f))) { raw = in.readAllBytes(); }
                    byte[] key = "firstPlayed".getBytes(java.nio.charset.StandardCharsets.UTF_8);
                    outer:
                    for (int i = 3; i + key.length + 8 <= raw.length; i++) {   // TAG_Long "firstPlayed" = 04 00 0B "firstPlayed" <8 bytes>
                        if (raw[i - 3] != 4 || raw[i - 1] != key.length) continue;
                        for (int j = 0; j < key.length; j++) if (raw[i + j] != key[j]) continue outer;
                        long ms = java.nio.ByteBuffer.wrap(raw, i + key.length, 8).getLong();
                        String d = java.time.Instant.ofEpochMilli(ms).toString().substring(0, 10);
                        if (ms > 0 && d.compareTo(best) < 0) best = d;
                        break;
                    }
                } catch (Exception ignored) {}
            }
            return best;
        });
    }
    boolean joinedBefore(Player p, String date) {
        if (plugin.getConfig().getStringList("cosmetics.joined-sources.extra").stream().anyMatch(n -> n.equalsIgnoreCase(p.getName()))) return true;
        return firstSeen(p).compareTo(date) < 0;
    }

    void cosmetic(Player p, String key) {
        PD pd = pd(p.getName());
        boolean isTag = key.startsWith("tag:");
        String id = key.substring(key.indexOf(':') + 1);
        Tag lim = isTag ? tags.get(id) : null;
        if (lim != null && lim.joinedBefore() != null && !joinedBefore(p, lim.joinedBefore())) {
            msg(p, "&c" + lim.display() + " &cis only for players who joined before &f" + lim.joinedBefore() + "&c.");
            p.playSound(p.getLocation(), Sound.ENTITY_VILLAGER_NO, 0.7f, 1f);
            if (id.equals(pd.tag)) { pd.tag = null; writeTags(); save(); }   // no longer qualifies: take it off
            return;
        }
        int cost = isTag ? (tags.containsKey(id) ? tags.get(id).cost() : -1) : (colors.containsKey(id) ? colors.get(id).cost() : -1);
        if (cost < 0) return;
        if (!pd.owned.contains(key)) {
            if (pd.points < cost) { msg(p, "&cYou need &d" + cost + " &cvote points (you have &d" + pd.points + "&c)."); p.playSound(p.getLocation(), Sound.ENTITY_VILLAGER_NO, 0.7f, 1f); return; }
            pd.points -= cost;
            pd.owned.add(key);
            msg(p, "&aUnlocked!");
            p.playSound(p.getLocation(), Sound.UI_TOAST_CHALLENGE_COMPLETE, 0.6f, 1.2f);
        } else p.playSound(p.getLocation(), Sound.UI_BUTTON_CLICK, 0.6f, 1f);
        if (isTag) { pd.tag = id.equals(pd.tag) ? null : id; writeTags(); }
        else { pd.color = id.equals(pd.color) ? null : id; writeTags(); }
        save();
        if (isTag) openTags(p); else openColors(p);
    }

    void links(CommandSender s) {
        msg(s, "&eVote for CrispyAnarchy &7- every vote is a reward you can send to any server, plus vote points for cosmetics:");
        int shown = 0;
        for (Map<?, ?> l : plugin.getConfig().getMapList("votes.links")) {
            String name = String.valueOf(l.get("name")), url = String.valueOf(l.get("url"));
            if (url.contains("CHANGE_ME")) continue;
            s.sendMessage(c("&8» &b&n" + name).clickEvent(ClickEvent.openUrl(url)).hoverEvent(HoverEvent.showText(Component.text(url))));
            shown++;
        }
        if (shown == 0) msg(s, "&7Vote links are coming soon.");
    }

    void top(CommandSender s) {
        String m = month();
        List<PD> l = new ArrayList<>(players.values());
        l.removeIf(pd -> pd.months.getOrDefault(m, 0) <= 0);
        l.sort(Comparator.comparingInt((PD pd) -> -pd.months.getOrDefault(m, 0)));
        msg(s, "&e&lTop voters &7(" + m + ")");
        if (l.isEmpty()) { msg(s, "&7No votes yet this month."); return; }
        for (int i = 0; i < Math.min(10, l.size()); i++)
            s.sendMessage(c("&6#" + (i + 1) + " &f" + l.get(i).name + " &7- &a" + l.get(i).months.get(m) + " votes"));
    }

    // ------------------------------------------------------------------ /vote and /cosmetics
    boolean command(CommandSender s, String label, String[] a) {
        if (label.equalsIgnoreCase("cosmetics")) {
            if (s instanceof Player p) Bukkit.getScheduler().runTask(plugin, () -> openCosmetics(p)); return true;
        }
        String sub = a.length > 0 ? a[0].toLowerCase(Locale.ROOT) : "";
        boolean admin = s.hasPermission("crispylobby.admin");
        switch (sub) {
            case "links" -> links(s);
            case "top" -> top(s);
            case "go" -> { if (s instanceof Player p && a.length > 1) connect(p, a[1]); }
            case "test", "give" -> {
                if (!admin || a.length < 2) { msg(s, "&7/vote give <player> [amount]"); return true; }
                int n = a.length > 2 ? Math.max(1, Integer.parseInt(a[2])) : 1;
                receive(a[1], sub.equals("test") ? "TestSite" : "an admin", n);
                msg(s, "Gave " + a[1] + " " + n + " vote(s).");
            }
            case "points" -> {
                if (!admin || a.length < 3) { msg(s, "&7/vote points <player> <amount>"); return true; }
                PD pd = pd(a[1]); pd.points = Math.max(0, pd.points + Integer.parseInt(a[2])); save();
                msg(s, a[1] + " now has " + pd.points + " vote points.");
            }
            case "reset" -> {
                if (!admin || a.length < 2) { msg(s, "&7/vote reset <player>  (deletes their vote data)"); return true; }
                PD gone = players.remove(a[1].toLowerCase(Locale.ROOT));
                save(); writeTags();
                msg(s, gone == null ? "No vote data for " + a[1] + "." : "Deleted the vote data for " + a[1] + ".");
            }
            case "reload" -> { if (admin) { plugin.reloadConfig(); load(); msg(s, "Reloaded vote servers and cosmetics."); } }
            // a tick later: the server selector runs /vote and then closes its own window, which would close this one too
            default -> { if (s instanceof Player p) Bukkit.getScheduler().runTask(plugin, () -> open(p)); else links(s); }
        }
        return true;
    }
}

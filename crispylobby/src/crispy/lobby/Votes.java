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
 *  chat name colours (namecolors.json, read by the same chat-tags plugin/mod) and chat colours for the message text
 *  (chatcolors.json, same format, same readers).
 *  All data changes happen on the main thread; one worker thread does the RCON work from snapshots. */
public class Votes implements Listener {
    static final ZoneId ZONE = ZoneId.of("America/Chicago");
    static final Gson GSON = new GsonBuilder().setPrettyPrinting().create();

    static final class PD {
        String name; int unclaimed, points, total;
        Map<String, Integer> months = new HashMap<>(), pending = new HashMap<>();
        Set<String> owned = new HashSet<>();
        String tag, color, chat;
        String trail;   // pre-1.5 walking trails; refunded and cleared on load
    }
    /** A vote-reward server. key names it here and in saved data (pending rewards); proxy is its Velocity name. */
    record Server(String key, String label, Material icon, Rcon rcon, List<String> reward, List<String> commands, String proxy) {}
    /** A tag costs vote points, or (earned tags) has a requirement instead: an advancement, a network stat milestone
     *  (stat + min) or a ranking (stat + top: wearable only while you hold it). stat "VOTES" = this month's votes.
     *  Mastery tags (score + min) unlock at that much mastery XP on a PvP objective (pvp.mx<kit id>); they have their
     *  own page, and head = a player-head texture for the icon. */
    record Tag(String id, String display, int cost, Material icon, String joinedBefore, String note,
               String advancement, String stat, long min, int top, String score, String head, String animation, boolean granted, boolean rare) {
        boolean earned() { return advancement != null || stat != null || score != null; }
        boolean ranked() { return stat != null && top > 0; }
        boolean event() { return score != null && score.startsWith(EVENT_SCORE); }
        /** Earned on Skyblock: one of its advancements, or a Skyblock score (sb.sk_<skill> XP, sb.island_lvl). */
        boolean skyblock() { return (advancement != null && advancement.startsWith(SKYBLOCK_ADV)) || (score != null && score.startsWith(SKYBLOCK_SCORE)); }
        String page() { return event() ? "event" : skyblock() ? "skyblock" : granted ? "special" : score != null ? "mtags" : earned() ? "etags" : "tags"; }
    }
    /** A name or chat colour: bought with vote points, or (score set) earned, free once that score reaches min (1 if
     *  unset): pvp.hw<n> = a Halloween colour (Halloween page), sb.* = a Skyblock colour (Skyblock page). */
    record NameColor(String id, String name, String code, int cost, Material icon, String score, long min, boolean rare) {
        boolean event() { return score != null && score.startsWith(EVENT_SCORE); }
        boolean skyblock() { return score != null && score.startsWith(SKYBLOCK_SCORE); }
        boolean earned() { return score != null; }
    }
    static final String SKYBLOCK_ADV = "crispy_skyblock:", SKYBLOCK_SCORE = "sb.";
    /** Halloween cosmetics: unlocked one at a time by completing Haunted Night in the Multiverse (score pvp.hw<n>). */
    static final String EVENT_SCORE = "pvp.hw";
    // what each retired trail cost, for the refund
    static final Map<String, Integer> TRAIL_REFUND = Map.of("hearts", 3, "flames", 4, "notes", 4, "soul", 5, "sakura", 5,
            "sparks", 6, "runes", 6, "glitch", 10, "endrod", 8, "totem", 12);
    record Job(String lower, String name, int count) {}
    static final class Menu implements InventoryHolder {
        final String kind; final Map<Integer, String> actions = new HashMap<>(); Inventory inv; Component title;
        Menu(String kind) { this.kind = kind; }
        @Override public Inventory getInventory() { return inv; }
    }

    final CrispyLobby plugin;
    final Path file, tagsFile, colorsFile, chatFile;
    Map<String, PD> players = new HashMap<>();
    final LinkedHashMap<String, Server> servers = new LinkedHashMap<>();
    final LinkedHashMap<String, Tag> tags = new LinkedHashMap<>();
    final LinkedHashMap<String, NameColor> colors = new LinkedHashMap<>(), chatColors = new LinkedHashMap<>();
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
        chatFile = plugin.getDataFolder().toPath().resolve("chatcolors.json");
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
        servers.clear(); tags.clear(); colors.clear(); chatColors.clear();
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
                    s.getStringList("reward"), s.getStringList("commands"), s.getString("proxy", k)));
        }
        loadTags(plugin.getConfig().getConfigurationSection("cosmetics.tags"));
        firstSeen.clear();
        loadColors(plugin.getConfig().getConfigurationSection("cosmetics.name-colors"), colors);
        loadColors(plugin.getConfig().getConfigurationSection("cosmetics.chat-colors"), chatColors);
        // in-game edits (/cosmeticsadmin, CosmeticEditor) on top: added or changed entries, then removed ones
        org.bukkit.configuration.file.YamlConfiguration ov = CosmeticEditor.edits(plugin);
        loadTags(ov.getConfigurationSection("tags"));
        loadColors(ov.getConfigurationSection("name-colors"), colors);
        loadColors(ov.getConfigurationSection("chat-colors"), chatColors);
        ov.getStringList("removed.tags").forEach(tags::remove);
        ov.getStringList("removed.name-colors").forEach(colors::remove);
        ov.getStringList("removed.chat-colors").forEach(chatColors::remove);
        writeTags();
    }
    void loadTags(ConfigurationSection ts) {
        if (ts != null) for (String k : ts.getKeys(false)) {
            String stat = ts.getString(k + ".stat");
            if (stat != null && !stat.equals("VOTES") && Arrays.stream(NetworkStats.Cat.values()).noneMatch(x -> x.name().equals(stat))) {
                plugin.getLogger().warning("cosmetics.tags." + k + ": unknown stat " + stat + " (skipped)"); continue;
            }
            tags.put(k, new Tag(k, ts.getString(k + ".display", k), ts.getInt(k + ".cost", 5), mat(ts.getString(k + ".icon"), Material.NAME_TAG),
                    ts.getString(k + ".joined-before"), ts.getString(k + ".note"), ts.getString(k + ".advancement"),
                    ts.getString(k + ".stat"), ts.getLong(k + ".min"), ts.getInt(k + ".top"), ts.getString(k + ".score"), ts.getString(k + ".head"),
                    ts.getString(k + ".animation"), ts.getBoolean(k + ".granted"), ts.getBoolean(k + ".rare")));
        }
    }
    void loadColors(ConfigurationSection cs, Map<String, NameColor> into) {
        if (cs != null) for (String k : cs.getKeys(false))
            into.put(k, new NameColor(k, cs.getString(k + ".name", k), cs.getString(k + ".code", "&f"), cs.getInt(k + ".cost", 5),
                    mat(cs.getString(k + ".icon"), Material.WHITE_DYE), cs.getString(k + ".score"), cs.getLong(k + ".min"), cs.getBoolean(k + ".rare")));
    }
    static Material mat(String s, Material def) { Material m = s == null ? null : Material.matchMaterial(s); return m == null ? def : m; }

    /** The CrispyTags proxy plugin owns /vote and /cosmetics network-wide: it brings the player to the lobby and sends
     *  the command line ("vote top", "cosmetics") here on this channel. Anything sent here only runs those two commands
     *  as that player, so a message straight from a client can't do more than typing them. */
    static final String CHANNEL = "crispy:vote";
    void start() {
        Bukkit.getMessenger().registerOutgoingPluginChannel(plugin, "BungeeCord");
        Bukkit.getMessenger().registerIncomingPluginChannel(plugin, CHANNEL, (ch, p, data) -> {
            String[] w = new String(data, java.nio.charset.StandardCharsets.UTF_8).trim().split("\\s+");
            if (w.length == 0 || !(w[0].equalsIgnoreCase("vote") || w[0].equalsIgnoreCase("cosmetics"))) return;
            Bukkit.getScheduler().runTask(plugin, () -> { if (p.isOnline()) command(p, w[0], Arrays.copyOfRange(w, 1, w.length)); });
        });
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
        // animated tags (a TAB animation name): the proxy's CrispyTags shows %animation:<name>% in the tab list and
        // on name tags instead of the still display (which chat keeps, since a chat line can't animate)
        Map<String, String> anim = new TreeMap<>();
        players.forEach((k, pd) -> { Tag t = pd.tag == null ? null : tags.get(pd.tag); if (t != null && t.animation() != null) anim.put(k, t.animation()); });
        try {
            Files.createDirectories(tagsFile.getParent());
            Path tmp = tagsFile.resolveSibling("tags_anim.json.tmp");
            Files.writeString(tmp, GSON.toJson(anim));
            Files.move(tmp, tagsFile.resolveSibling("tags_anim.json"), StandardCopyOption.REPLACE_EXISTING, StandardCopyOption.ATOMIC_MOVE);
        } catch (IOException e) { plugin.getLogger().warning("tags_anim.json write failed: " + e); }
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
        Map<String, String> chat = new TreeMap<>();   // name (lowercase) -> colour code for their chat messages
        players.forEach((k, pd) -> { NameColor c = pd.chat == null ? null : chatColors.get(pd.chat); if (c != null) chat.put(k, c.code()); });
        try {
            Path tmp = chatFile.resolveSibling("chatcolors.json.tmp");
            Files.writeString(tmp, GSON.toJson(chat));
            Files.move(tmp, chatFile, StandardCopyOption.REPLACE_EXISTING, StandardCopyOption.ATOMIC_MOVE);
        } catch (IOException e) { plugin.getLogger().warning("chatcolors.json write failed: " + e); }
    }
    /** Text in a colour code: see ColorCodes ("&b", "&c|&6|&e", "rainbow", fades "a>b", flags "a/b/c"). */
    static String colored(String name, String code) { return ColorCodes.legacy(code, name); }

    static String month() { return YearMonth.now(ZONE).toString(); }
    PD pd(String name) {
        PD pd = players.computeIfAbsent(name.toLowerCase(Locale.ROOT), k -> new PD());
        if (pd.name == null || Bukkit.getPlayerExact(name) != null) pd.name = name;
        return pd;
    }
    static Component c(String s) { return CrispyLobby.AMP.deserialize(s).decoration(TextDecoration.ITALIC, false); }
    static void msg(CommandSender s, String m) { s.sendMessage(c("&d&lVote &8» &7" + m)); }
    static void msg(Viewer s, String m) { s.sendMessage(c("&d&lVote &8» &7" + m)); }

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
        String line = "&a" + pd.name + " &7voted for CrispyAnarchy on &f" + service + "&7! &eClaim vote rewards: &f/vote";
        if (announce) {
            Bukkit.broadcast(c(line));
            // the Discord bot relays "<name> text" lines from this server's log to Discord and (cross-chat) every other server
            if (botRelay) Bukkit.getConsoleSender().sendMessage("<Votes> " + pd.name + " voted for CrispyAnarchy on " + service + "! Claim vote rewards: /vote");
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
    void claim(Viewer p, String server, boolean all) {
        Server s = servers.get(server);
        PD pd = pd(p.getName());
        if (s == null || s.commands().isEmpty()) return;
        if (pd.unclaimed <= 0) { msg(p, "&cNo rewards to claim. &7Vote with &f/vote links&7."); p.playSound(Sound.ENTITY_VILLAGER_NO, 0.7f, 1f); return; }
        int n = all ? pd.unclaimed : 1;
        pd.unclaimed -= n;
        pd.pending.merge(server, n, Integer::sum);
        save();
        p.playSound(Sound.ENTITY_EXPERIENCE_ORB_PICKUP, 0.8f, 1.2f);
        p.sendMessage(c("&d&lVote &8» &7Sent &e" + n + " &7reward" + (n == 1 ? "" : "s") + " to " + s.label() + "&7. It arrives the next time you're there. ")
                .append(c("&a&n[Go now]").clickEvent(ClickEvent.runCommand("/vote go " + server)).hoverEvent(HoverEvent.showText(c("&7Join " + s.label())))));
        open(p);
    }

    /** Send the player to a vote server, by its key here or its Velocity name. */
    void connect(Viewer p, String server) {
        Server s = servers.containsKey(server) ? servers.get(server)
                : servers.values().stream().filter(x -> x.proxy().equalsIgnoreCase(server)).findFirst().orElse(null);
        if (s == null) return;
        if (p instanceof Viewer.Remote r) { r.connect = s.proxy(); return; }
        Player pl = p instanceof Viewer.Local l ? l.player() : null;
        if (pl == null) return;
        ByteArrayDataOutput out = ByteStreams.newDataOutput();
        out.writeUTF("Connect"); out.writeUTF(s.proxy());
        pl.sendPluginMessage(plugin, "BungeeCord", out.toByteArray());
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
    /** A tag's icon: a textured player head when it has one. */
    ItemStack tagItem(Tag t, List<String> lore, boolean glow) {
        ItemStack it = item(t.head() != null ? Material.PLAYER_HEAD : t.icon(), t.display(), lore, glow);
        if (t.head() != null && it.getItemMeta() instanceof org.bukkit.inventory.meta.SkullMeta sm) {
            com.destroystokyo.paper.profile.PlayerProfile prof = Bukkit.createProfile(UUID.nameUUIDFromBytes(t.head().getBytes()), t.id().length() > 16 ? t.id().substring(0, 16) : t.id());
            prof.setProperty(new com.destroystokyo.paper.profile.ProfileProperty("textures", t.head()));
            sm.setPlayerProfile(prof);
            it.setItemMeta(sm);
        }
        return it;
    }
    Menu menu(String kind, int rows, String title) {
        Menu m = new Menu(kind);
        m.title = c(title);
        m.inv = Bukkit.createInventory(m, rows * 9, m.title);
        ItemStack pane = item(Material.BLACK_STAINED_GLASS_PANE, " ", List.of(), false);
        for (int i = 0; i < rows * 9; i++) m.inv.setItem(i, pane);
        return m;
    }
    void put(Menu m, int slot, ItemStack it, String action) { m.inv.setItem(slot, it); if (action != null) m.actions.put(slot, action); }

    void open(Viewer p) {
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
        NameColor nc = pd.color == null ? null : colors.get(pd.color), cc = pd.chat == null ? null : chatColors.get(pd.chat);
        put(m, 41, item(Material.AMETHYST_SHARD, "&b&lCosmetics", List.of("&7Tags, name colours and chat colours that", "&7show on &fevery server&7.",
                "&7Bought with vote points (&d" + pd.points + "&7).", "",
                "&7Tag: " + (tg == null ? "&8none" : tg.display()), "&7Name colour: " + (nc == null ? "&8none" : colored(nc.name(), nc.code())),
                "&7Chat colour: " + (cc == null ? "&8none" : colored(cc.name(), cc.code())), "", "&eClick to browse"), false), "cosmetics");
        p.openInventory(m.inv);
    }

    static final int[] MGRID = java.util.stream.IntStream.range(9, 45).toArray();   // mastery page: 4 full rows, like the PvP kit menu
    static final long MASTERY_XP = 1500;   // PvP mastery level V (pvp/build.py MASTERY)
    static final int[] GRID = {10, 11, 12, 13, 14, 15, 16, 19, 20, 21, 22, 23, 24, 25, 28, 29, 30, 31, 32, 33, 34, 37, 38, 39, 40, 41, 42, 43};
    ItemStack pointsItem(PD pd) {
        return item(Material.AMETHYST_SHARD, "&d&l" + pd.points + " vote point" + (pd.points == 1 ? "" : "s"),
                List.of("&7You get &d" + pointsPerVote + " &7per vote. &f/vote &7for the links."), false);
    }

    // ------------------------------------------------------------------ Skyblock and special (staff-given) cosmetics
    /** What a Skyblock score requirement means, for lore and messages. */
    static String skyNeed(String score, long min) {
        if (score.equals("sb.island_lvl")) return "&7Reach island level &f" + min + " &7on Skyblock";
        if (score.equals("sb.skills_min")) return "&7Reach level &f" + (int) Math.round(Math.sqrt(min / 100.0)) + " &7in &fevery &7skill on Skyblock";
        String skill = score.startsWith("sb.sk_") ? score.substring(6) : score;
        skill = switch (skill) { case "farm" -> "Farming"; case "mine" -> "Mining"; case "forage" -> "Foraging"; case "combat" -> "Combat"; case "fish" -> "Fishing"; default -> skill; };
        int lv = (int) Math.round(Math.sqrt(min / 100.0));
        return "&7Reach &f" + skill + " " + lv + " &7on Skyblock";
    }
    static String skyHave(String score, long v) {
        if (score.equals("sb.island_lvl")) return "island level " + v;
        int lv = 0; while (lv < 25 && v >= 100L * (lv + 1) * (lv + 1)) lv++;
        return (score.equals("sb.skills_min") ? "lowest skill level " : "level ") + lv;
    }
    List<String> skyblockKeys() {
        List<String> out = new ArrayList<>();
        tags.values().stream().filter(Tag::skyblock).forEach(t -> out.add("tag:" + t.id()));
        colors.values().stream().filter(NameColor::skyblock).forEach(c -> out.add("color:" + c.id()));
        chatColors.values().stream().filter(NameColor::skyblock).forEach(c -> out.add("chat:" + c.id()));
        return out;
    }

    /** Actions ("tag:x", "color:x", "chat:x") for every cosmetic the player can wear now: bought or claimed ones, and
     *  ranked tags while they hold the rank. Tags first, then name colours, then chat colours, in menu order. */
    List<String> owned(Viewer p, PD pd) {
        List<String> out = new ArrayList<>();
        Set<String> advs = null;
        for (Tag t : tags.values()) {
            if (pd.owned.contains("tag:" + t.id()) || t.id().equals(pd.tag)) out.add("tag:" + t.id());
            else if (t.event() && plugin.stats.mastery(p.getName(), t.score()) >= Math.max(1, t.min())) out.add("tag:" + t.id());
            else if (t.ranked()) {
                if (advs == null) advs = advancements(p);
                if (lockReason(p, t, advs) == null) out.add("tag:" + t.id());
            }
        }
        for (NameColor c : colors.values()) if (pd.owned.contains("color:" + c.id()) || eventUnlocked(p, c)) out.add("color:" + c.id());
        for (NameColor c : chatColors.values()) if (pd.owned.contains("chat:" + c.id()) || eventUnlocked(p, c)) out.add("chat:" + c.id());
        return out;
    }

    // ------------------------------------------------------------------ earned tags
    List<String> requirement(Tag t) {
        List<String> l = new ArrayList<>();
        if (t.skyblock()) { l.add(t.advancement() != null ? "&7Skyblock advancement: &f" + (t.note() != null ? t.note() : t.advancement())
                : skyNeed(t.score(), t.min())); }
        else if (t.event()) { l.add("&7Survive &6Haunted Night &7in the Multiverse"); l.add("&8Each completed run unlocks one random"); l.add("&8Halloween cosmetic you don't have yet"); }
        else if (t.score() != null && !t.score().startsWith("pvp.mx")) l.add("&7" + (t.note() != null ? t.note() : t.score() + " " + t.min()));
        else if (t.score() != null) { l.add("&7Master &f" + (t.note() != null ? t.note() : t.id()) + " &7in the Multiverse"); l.add("&8" + String.format("%,d", t.min()) + " mastery XP with that character"); }
        else if (t.advancement() != null) l.add("&7Advancement: &f" + (t.note() != null ? t.note() : t.advancement()));
        else if ("VOTES".equals(t.stat())) l.add("&7Be the &f#1 voter &7this month");
        else if (t.stat() != null) {
            NetworkStats.Cat c = NetworkStats.Cat.valueOf(t.stat());
            if (t.ranked()) l.add("&7Be " + (t.top() == 1 ? "&f#1" : "&ftop " + t.top()) + " &7in &f" + c.title);
            else l.add("&7Reach &f" + NetworkStats.fmt(c, t.min()) + " &7in &f" + c.title);
            if (t.note() != null) l.add("&8" + t.note());
        }
        if (t.ranked()) l.add("&8Only while you hold the spot (checked every few minutes)");
        else l.add("&8Yours to keep once unlocked");
        return l;
    }
    int voteRank(String name) {
        String m = month();
        PD me = players.get(name.toLowerCase(Locale.ROOT));
        int v = me == null ? 0 : me.months.getOrDefault(m, 0);
        if (v <= 0) return 0;
        int above = 0;
        for (PD o : players.values()) if (o.months.getOrDefault(m, 0) > v) above++;
        return above + 1;
    }
    /** null if the player meets the tag's requirement, else a lore line saying where they stand. */
    String lockReason(Viewer p, Tag t, Set<String> advs) {
        if (t.advancement() != null) return advs.contains(t.advancement()) ? null : "&cNot unlocked yet";
        if (t.event()) {
            if (!plugin.stats.loaded()) return "&8Stats are loading, try again in a minute";
            return plugin.stats.mastery(p.getName(), t.score()) >= Math.max(1, t.min()) ? null : "&cNot unlocked yet";
        }
        if (t.score() != null && t.skyblock()) {
            if (!plugin.stats.loaded()) return "&8Stats are loading, try again in a minute";
            long v = plugin.stats.mastery(p.getName(), t.score());
            return v >= t.min() ? null : "&cYou: &f" + skyHave(t.score(), v);
        }
        if (t.score() != null) {
            if (!plugin.stats.loaded()) return "&8Stats are loading, try again in a minute";
            long v = plugin.stats.mastery(p.getName(), t.score());
            return v >= t.min() ? null : "&cYou: &f" + String.format("%,d", v) + " &8/ " + String.format("%,d", t.min()) + (t.score().startsWith("pvp.mx") ? " XP" : "");
        }
        if ("VOTES".equals(t.stat())) {
            int r = voteRank(p.getName());
            return r > 0 && r <= Math.max(1, t.top()) ? null : "&cYou're " + (r == 0 ? "not ranked yet" : "#" + r) + " this month";
        }
        if (t.stat() == null) return null;
        if (!plugin.stats.loaded()) return "&8Stats are loading, try again in a minute";
        NetworkStats.Cat c = NetworkStats.Cat.valueOf(t.stat());
        long v = plugin.stats.value(p.getName(), c);
        if (t.ranked()) {
            int r = plugin.stats.rank(p.getName(), c);
            return r > 0 && r <= t.top() ? null : "&cYou: &f" + NetworkStats.fmt(c, v) + (r > 0 ? " &8(#" + r + ")" : "");
        }
        return v >= t.min() ? null : "&cYou: &f" + NetworkStats.fmt(c, v) + " &8/ " + NetworkStats.fmt(c, t.min());
    }
    final Map<UUID, Map.Entry<Long, Set<String>>> advCache = new HashMap<>();
    /** Every advancement this player has completed on any server (cosmetics.earned-sources.advancements), cached 30 s. */
    Set<String> advancements(Viewer p) {
        Map.Entry<Long, Set<String>> c = advCache.get(p.getUniqueId());
        if (c != null && System.currentTimeMillis() - c.getKey() < 30_000) return c.getValue();
        Set<String> done = new HashSet<>();
        Path root = Path.of(plugin.getConfig().getString("network-stats.instances-dir", "/AMPStorage/.ampdata/instances"));
        for (String dir : plugin.getConfig().getStringList("cosmetics.earned-sources.advancements")) {
            Path f = root.resolve(dir).resolve(p.getUniqueId() + ".json");
            if (!Files.isRegularFile(f)) continue;
            try {
                com.google.gson.JsonObject o = com.google.gson.JsonParser.parseString(Files.readString(f)).getAsJsonObject();
                for (var e : o.entrySet())
                    if (e.getValue().isJsonObject() && e.getValue().getAsJsonObject().has("done") && e.getValue().getAsJsonObject().get("done").getAsBoolean()) done.add(e.getKey());
            } catch (Exception ignored) {}
        }
        advCache.put(p.getUniqueId(), Map.entry(System.currentTimeMillis(), done));
        return done;
    }
    /** After each stats refresh: anyone wearing a ranking tag they no longer hold takes it off. */
    void recheckEarned() {
        boolean changed = false;
        for (PD pd : players.values()) {
            Tag t = pd.tag == null ? null : tags.get(pd.tag);
            if (t == null || !t.ranked() || pd.name == null) continue;
            int r = "VOTES".equals(t.stat()) ? voteRank(pd.name) : plugin.stats.rank(pd.name, NetworkStats.Cat.valueOf(t.stat()));
            if (r > 0 && r <= t.top()) continue;
            pd.tag = null; changed = true;
            Player p = Bukkit.getPlayerExact(pd.name);
            if (p != null) msg(p, "&7You're no longer " + (t.top() == 1 ? "#1" : "top " + t.top()) + " for " + t.display() + "&7, so it came off.");
        }
        if (changed) { writeTags(); save(); }
    }

    static final String[][] COLOR_PAGES = {{"classic", "&f&lClassic", "WHITE_DYE"}, {"fades", "&d&lFades", "AMETHYST_SHARD"}, {"flags", "&b&lFlags", "WHITE_BANNER"}};

    // ------------------------------------------------------------------ Halloween (event) cosmetics
    boolean eventUnlocked(Viewer p, NameColor c) { return c.earned() && plugin.stats.mastery(p.getName(), c.score()) >= Math.max(1, c.min()); }

    @EventHandler public void onDrag(InventoryDragEvent e) { if (e.getInventory().getHolder() instanceof Menu) e.setCancelled(true); }

    @EventHandler public void onClick(InventoryClickEvent e) {
        if (!(e.getInventory().getHolder() instanceof Menu m) || !(e.getWhoClicked() instanceof Player pl)) return;
        e.setCancelled(true);
        if (e.getClickedInventory() != e.getInventory()) return;
        click(new Viewer.Local(pl), m, e.getRawSlot(), e.isShiftClick());
    }

    // ------------------------------------------------------------------ cosmetics menus
    /** One cosmetic on a list page: its icon (lore set), click action, and where it sorts:
     *  0 wearing/using, 1 owned (or unlocked), 2 can get now (claim or buy), 3 locked / not enough points. */
    record Entry(ItemStack item, String action, int state) {}
    static final String[] FILTERS = {"all", "owned", "missing"};
    static final Map<String, String> FILTER_LABEL = Map.of("all", "All", "owned", "Owned", "missing", "Not owned yet");
    final Map<UUID, String> filterOf = new HashMap<>();
    final Map<UUID, Integer> pageOf = new HashMap<>();
    final Map<UUID, String> lastKind = new HashMap<>();

    static final String[][] CATS = {{"tag", "Tags"}, {"color", "Name colours"}, {"chat", "Chat colours"}};
    /** Cosmetics hub: what you're wearing (and Special, for staff-given tags) on top, then the three kinds of
     *  cosmetic. Each opens its own page of sources: the shop, achievements, Multiverse, Skyblock, events. */
    void openCosmetics(Viewer p) {
        PD pd = pd(p.getName());
        UUID u = p.getUniqueId();
        lastKind.put(u, "cosmetics"); filterOf.remove(u);
        Menu m = menu("cosmetics", 4, "&b&lCosmetics");
        put(m, 4, wearing(p, pd), null);
        Set<String> have = new HashSet<>(owned(p, pd));
        if (group("special").stream().anyMatch(have::contains))
            put(m, 8, item(Material.SPYGLASS, "&d&lSpecial", List.of("&7Tags given to you by staff.", "", "&eClick to open"), false), "special");
        put(m, 11, hub(Material.NAME_TAG, "&f&lTags", "Shown with your name in chat, tab", "and above your head, everywhere.", have, catKeys("tag")), "cat:tag");
        put(m, 13, hub(Material.ORANGE_DYE, "&f&lName colours", "Your name in colour in chat", "on every server.", have, catKeys("color")), "cat:color");
        put(m, 15, hub(Material.WRITABLE_BOOK, "&f&lChat colours", "Your messages in colour", "on every server.", have, catKeys("chat")), "cat:chat");
        put(m, 22, item(Material.ENDER_CHEST, "&d&lMy cosmetics", List.of("&7Everything you've unlocked.", "", "&7Unlocked: &f" + have.size(), "", "&eClick to open"), false), "owned");
        put(m, 27, item(Material.ARROW, "&7Back to vote rewards", List.of(), false), "back");
        put(m, 31, pointsItem(pd), null);
        if (pd.tag != null || pd.color != null || pd.chat != null)
            put(m, 35, item(Material.BARRIER, "&cTake everything off", List.of("&7Tag, name colour and chat colour"), false), "off:all");
        p.openInventory(m.inv);
    }

    ItemStack wearing(Viewer p, PD pd) {
        Tag tg = pd.tag == null ? null : tags.get(pd.tag);
        NameColor nc = pd.color == null ? null : colors.get(pd.color);
        NameColor cc = pd.chat == null ? null : chatColors.get(pd.chat);
        String name = nc == null ? "&f" + p.getName() : colored(p.getName(), nc.code());
        String said = cc == null ? "&fhey everyone" : colored("hey everyone", cc.code());
        return item(tg == null || tg.head() != null ? Material.NAME_TAG : tg.icon(), "&f&lYou look like this", List.of(
                "&f<" + (tg == null ? "" : tg.display() + " ") + name + "&f> " + said, "",
                "&7Tag: " + (tg == null ? "&8none" : tg.display()),
                "&7Name colour: " + (nc == null ? "&8none" : colored(nc.name(), nc.code())),
                "&7Chat colour: " + (cc == null ? "&8none" : colored(cc.name(), cc.code()))), tg != null || nc != null || cc != null);
    }

    ItemStack hub(Material icon, String title, String l1, String l2, Set<String> have, List<String> keys) {
        long n = keys.stream().filter(have::contains).count();
        return item(icon, title, List.of("&7" + l1, "&7" + l2, "", "&7Unlocked: &f" + n + "&7/" + keys.size(), "", "&eClick to open"), false);
    }

    /** The sources inside one kind (tag, color, chat): {page kind, icon, title, line 1, line 2}; empty ones are hidden. */
    List<String[]> sources(String type) {
        List<String[]> out = new ArrayList<>();
        if (type.equals("tag")) {
            out.add(new String[]{"tags", "NAME_TAG", "&f&lShop", "Buy tags with", "vote points."});
            out.add(new String[]{"etags", "EXPERIENCE_BOTTLE", "&6&lAchievements", "Advancements, milestones and", "topping a leaderboard (/stats)."});
            out.add(new String[]{"mtags", "NETHER_STAR", "&e&lMultiverse", "Master characters and set", "records in the Multiverse."});
        } else out.add(new String[]{type.equals("color") ? "colors:classic" : "chatcolors:classic", "EMERALD", "&f&lShop", "Buy them with", "vote points."});
        out.add(new String[]{"skyblock:" + type, "OAK_SAPLING", "&a&lSkyblock", "Skyblock advancements, skill", "levels and your island level."});
        out.add(new String[]{"event:" + type, "JACK_O_LANTERN", "&6&lEvents", "Halloween: survive Haunted", "Night in the Multiverse."});
        out.removeIf(s -> group(s[0]).isEmpty());
        return out;
    }
    List<String> catKeys(String type) {
        List<String> out = new ArrayList<>();
        for (String[] s : sources(type)) out.addAll(group(s[0]));
        return out;
    }

    /** One kind of cosmetic: a button per source, centred on the middle row. */
    void openCategory(Viewer p, String type) {
        PD pd = pd(p.getName());
        UUID u = p.getUniqueId();
        lastKind.put(u, "cat:" + type); filterOf.remove(u);
        String title = type.equals("tag") ? "&f&lTags" : type.equals("color") ? "&f&lName colours" : "&f&lChat colours";
        Menu m = menu("cat:" + type, 4, title);
        put(m, 4, wearing(p, pd), null);
        Set<String> have = new HashSet<>(owned(p, pd));
        List<String[]> src = sources(type);
        int[][] layouts = {{13}, {12, 14}, {11, 13, 15}, {10, 12, 14, 16}, {11, 12, 13, 14, 15}};
        int[] slots = layouts[Math.max(0, Math.min(src.size(), 5) - 1)];
        for (int i = 0; i < src.size() && i < slots.length; i++) {
            String[] s = src.get(i);
            List<String> keys = group(s[0]);
            long n = keys.stream().filter(have::contains).count();
            List<String> lore = new ArrayList<>();
            lore.add("&7" + s[3]); lore.add("&7" + s[4]);
            lore.add(""); lore.add("&7Unlocked: &f" + n + "&7/" + keys.size()); lore.add(""); lore.add("&eClick to open");
            put(m, slots[i], item(Material.valueOf(s[1]), s[2], lore, false), s[0]);
        }
        String on = type.equals("tag") ? pd.tag : type.equals("color") ? pd.color : pd.chat;
        if (on != null) put(m, 35, takeOff(type.equals("tag") ? "tag" : type.equals("color") ? "name colour" : "chat colour"), "off:" + type);
        put(m, 27, item(Material.ARROW, "&7Back", List.of(), false), "cosmetics");
        put(m, 31, pointsItem(pd), null);
        p.openInventory(m.inv);
    }

    /** Keys ("tag:x", "color:x", "chat:x") in one list: tags (shop), etags, mtags, special, colors:<page> /
     *  chatcolors:<page> (shops), and <skyblock|event>:<tag|color|chat>. */
    List<String> group(String g) {
        List<String> out = new ArrayList<>();
        int c = g.indexOf(':');
        String head = c < 0 ? g : g.substring(0, c), tail = c < 0 ? "" : g.substring(c + 1);
        switch (head) {
            case "colors" -> colors.values().stream().filter(x -> !x.earned() && (tail.isEmpty() || ColorCodes.page(x.code()).equals(tail))).forEach(x -> out.add("color:" + x.id()));
            case "chatcolors" -> chatColors.values().stream().filter(x -> !x.earned() && (tail.isEmpty() || ColorCodes.page(x.code()).equals(tail))).forEach(x -> out.add("chat:" + x.id()));
            case "skyblock", "event" -> {
                boolean sky = head.equals("skyblock");
                if (tail.isEmpty() || tail.equals("tag")) tags.values().stream().filter(t -> t.page().equals(head)).forEach(t -> out.add("tag:" + t.id()));
                if (tail.isEmpty() || tail.equals("color")) colors.values().stream().filter(x -> sky ? x.skyblock() : x.event()).forEach(x -> out.add("color:" + x.id()));
                if (tail.isEmpty() || tail.equals("chat")) chatColors.values().stream().filter(x -> sky ? x.skyblock() : x.event()).forEach(x -> out.add("chat:" + x.id()));
            }
            default -> tags.values().stream().filter(t -> t.page().equals(head)).forEach(t -> out.add("tag:" + t.id()));
        }
        return out;
    }
    /** Where Back goes from a list page. */
    static String backOf(String kind) {
        if (kind.equals("tags") || kind.equals("etags") || kind.equals("mtags")) return "cat:tag";
        if (kind.startsWith("colors:")) return "cat:color";
        if (kind.startsWith("chatcolors:")) return "cat:chat";
        if (kind.startsWith("skyblock:") || kind.startsWith("event:")) return "cat:" + kind.substring(kind.indexOf(':') + 1);
        return "cosmetics";
    }

    /** One list page: header at slot 4, entries 28 a page sorted wearing → owned → can get → locked (config order
     *  within each), a filter (All / Owned / Not owned yet), arrows, back and points. extra adds tabs etc. */
    void listPage(Viewer p, String kind, String title, ItemStack header, List<Entry> entries, java.util.function.Consumer<Menu> extra) {
        PD pd = pd(p.getName());
        UUID u = p.getUniqueId();
        if (!kind.equals(lastKind.get(u))) { pageOf.put(u, 0); lastKind.put(u, kind); }
        String f = filterOf.getOrDefault(u, "all");
        List<Entry> shown = entries.stream().filter(e -> f.equals("all") || (f.equals("owned") ? e.state() <= 1 : e.state() >= 2))
                .sorted(Comparator.comparingInt(Entry::state)).toList();
        int pages = Math.max(1, (shown.size() + GRID.length - 1) / GRID.length);
        int pg = Math.max(0, Math.min(pageOf.getOrDefault(u, 0), pages - 1));
        pageOf.put(u, pg);
        Menu m = menu(kind, 6, title + (pages > 1 ? " &8(" + (pg + 1) + "/" + pages + ")" : ""));
        if (header != null) put(m, 4, header, null);
        for (int i = 0; i < GRID.length && pg * GRID.length + i < shown.size(); i++) {
            Entry e = shown.get(pg * GRID.length + i);
            put(m, GRID[i], e.item(), e.action());
        }
        if (shown.isEmpty()) put(m, 22, item(Material.GRAY_DYE, "&7Nothing here", List.of(f.equals("all") ? "&8Nothing in this list yet" : "&8Try another filter"), false), null);
        if (pg > 0) put(m, 45, item(Material.ARROW, "&7Previous page", List.of(), false), "pg:-1");
        if (pg < pages - 1) put(m, 53, item(Material.ARROW, "&7Next page", List.of(), false), "pg:1");
        List<String> fl = new ArrayList<>();
        for (String x : FILTERS) fl.add((x.equals(f) ? "&a» " : "&8  ") + FILTER_LABEL.get(x));
        fl.add(""); fl.add("&eClick to change");
        put(m, 47, item(Material.HOPPER, "&e&lShow: &f" + FILTER_LABEL.get(f), fl, false), "filter");
        put(m, 49, item(Material.ARROW, "&7Back", List.of(), false), backOf(kind));
        put(m, 51, pointsItem(pd), null);
        if (extra != null) extra.accept(m);
        p.openInventory(m.inv);
    }

    /** A tag on a list page, with its state and lore (preview, cost or requirement, what a click does). */
    Entry tagEntry(Viewer p, PD pd, Tag t, Set<String> advs) {
        boolean on = t.id().equals(pd.tag), own = pd.owned.contains("tag:" + t.id());
        List<String> lore = new ArrayList<>(List.of(t.rare() ? "&d&l✦ RARE &8Tag" : "&8Tag", "&f<" + t.display() + " &f" + p.getName() + "&f> hi", ""));
        int state;
        if (t.granted()) {
            if (t.note() != null) lore.add("&8" + t.note());
            state = on ? 0 : 1;
            lore.add(on ? "&aWearing &8· &7click to take off" : "&eClick to wear");
        } else if (t.earned()) {
            String lock = lockReason(p, t, advs);
            lore.add(requirement(t).get(0));
            if (lock != null && !on) lore.add(lock);
            state = on ? 0 : lock != null ? 3 : (own || t.ranked() || t.event()) ? 1 : 2;
            if (t.ranked()) lore.add("&8Only while you hold the spot");
            lore.add("");
            lore.add(on ? "&aWearing &8· &7click to take off" : state == 3 ? "&cLocked" : state == 2 ? "&eClick to claim" : "&eClick to wear");
        } else {
            if (t.note() != null) lore.add("&8" + t.note());
            boolean jb = t.joinedBefore() == null || joinedBefore(p, t.joinedBefore());
            if (t.joinedBefore() != null) lore.add(jb ? "&6Exclusive: &7you joined before " + t.joinedBefore() : "&cOnly for players who joined before " + t.joinedBefore());
            state = on ? 0 : own ? 1 : jb && pd.points >= t.cost() ? 2 : 3;
            if (!own) lore.add("&7Cost: &d" + t.cost() + " point" + (t.cost() == 1 ? "" : "s"));
            lore.add("");
            lore.add(on ? "&aWearing &8· &7click to take off" : own ? "&eClick to wear" : state == 2 ? "&eClick to buy" : jb ? "&cNot enough points" : "&cLocked");
        }
        return new Entry(tagItem(t, lore, on), "tag:" + t.id(), state);
    }

    /** A name or chat colour on a list page. */
    Entry colorEntry(Viewer p, PD pd, NameColor c, boolean chat) {
        String key = (chat ? "chat:" : "color:") + c.id();
        boolean on = c.id().equals(chat ? pd.chat : pd.color), own = pd.owned.contains(key);
        String preview = chat ? "&f<" + p.getName() + "> " + colored("hey, gg everyone", c.code()) : "&f<" + colored(p.getName(), c.code()) + "&f> hi";
        List<String> lore = new ArrayList<>(List.of((c.rare() ? "&d&l✦ RARE &8" : "&8") + (chat ? "Chat colour" : "Name colour"), preview, ""));
        int state;
        String use = chat ? "use" : "use";
        if (c.earned()) {
            boolean open = own || eventUnlocked(p, c);
            lore.add(c.skyblock() ? skyNeed(c.score(), c.min()) : "&7Survive &6Haunted Night &7in the Multiverse");
            if (!open && c.skyblock()) lore.add(plugin.stats.loaded() ? "&cYou: &f" + skyHave(c.score(), plugin.stats.mastery(p.getName(), c.score())) : "&8Stats are loading");
            state = on ? 0 : open ? 1 : 3;
            lore.add("");
            lore.add(on ? "&aUsing &8· &7click to take off" : open ? "&eClick to " + use : "&cLocked");
        } else {
            state = on ? 0 : own ? 1 : pd.points >= c.cost() ? 2 : 3;
            if (!own) lore.add("&7Cost: &d" + c.cost() + " point" + (c.cost() == 1 ? "" : "s"));
            lore.add("");
            lore.add(on ? "&aUsing &8· &7click to take off" : own ? "&eClick to " + use : state == 2 ? "&eClick to buy" : "&cNot enough points");
        }
        return new Entry(item(c.icon(), colored(c.name(), c.code()), lore, on), key, state);
    }

    ItemStack takeOff(String what) { return item(Material.BARRIER, "&cTake off your " + what, List.of(), false); }

    void openTags(Viewer p) { openTags(p, "tags"); }
    /** Tag pages: the shop ("tags"), Achievements ("etags") and Multiverse mastery ("mtags"). */
    void openTags(Viewer p, String page) {
        PD pd = pd(p.getName());
        Set<String> advs = page.equals("etags") ? advancements(p) : Set.of();
        List<Entry> es = new ArrayList<>();
        for (Tag t : tags.values()) if (t.page().equals(page)) es.add(tagEntry(p, pd, t, advs));
        ItemStack header = switch (page) {
            case "etags" -> item(Material.EXPERIENCE_BOTTLE, "&6&lAchievements", List.of("&7Free tags for advancements on any server,", "&7network milestones and being #1 on a", "&7leaderboard (/stats).", "", "&8Click one you've unlocked to claim it."), false);
            case "mtags" -> item(Material.NETHER_STAR, "&e&lMultiverse mastery", List.of("&7Master a character in the Multiverse", "&7(level V, &f" + String.format("%,d", MASTERY_XP) + " &7mastery XP) to unlock its tag.",
                    "", "&7+10 XP per PvP kill, +1 per Outbreak kill.", "&f/trigger pvp.mastery &7in the Multiverse shows yours."), false);
            default -> item(Material.NAME_TAG, "&f&lTag shop", List.of("&7Buy tags with vote points.", "&7Every vote gives &d" + pointsPerVote + " &7point" + (pointsPerVote == 1 ? "" : "s") + "."), false);
        };
        String title = page.equals("etags") ? "&6&lAchievements" : page.equals("mtags") ? "&e&lMultiverse mastery" : "&f&lTag shop";
        listPage(p, page, title, header, es, m -> { if (pd.tag != null) put(m, 46, takeOff("tag"), "off:tag"); });
    }

    void openColors(Viewer p, String page) { openColorMenu(p, false, page); }
    void openChatColors(Viewer p, String page) { openColorMenu(p, true, page); }
    /** Name or chat colour shop, with tabs on top for classic colours, fades and flags (ColorCodes.page). */
    void openColorMenu(Viewer p, boolean chat, String page) {
        PD pd = pd(p.getName());
        String base = chat ? "chatcolors" : "colors";
        List<Entry> es = new ArrayList<>();
        for (NameColor c : (chat ? chatColors : colors).values())
            if (!c.earned() && ColorCodes.page(c.code()).equals(page)) es.add(colorEntry(p, pd, c, chat));
        String using = chat ? pd.chat : pd.color;
        listPage(p, base + ":" + page, chat ? "&f&lChat colours" : "&f&lName colours", null, es, m -> {
            for (int t = 0; t < COLOR_PAGES.length; t++)
                put(m, 3 + t, item(Material.valueOf(COLOR_PAGES[t][2]), COLOR_PAGES[t][1], List.of(COLOR_PAGES[t][0].equals(page) ? "&aShowing" : "&eClick to show"),
                        COLOR_PAGES[t][0].equals(page)), base + ":" + COLOR_PAGES[t][0]);
            if (using != null) put(m, 46, takeOff(chat ? "chat colour" : "name colour"), "off:" + (chat ? "chat" : "color"));
        });
    }

    /** One earned source for one kind: skyblock:<type> or event:<type>. */
    List<Entry> groupEntries(Viewer p, PD pd, String g) {
        Set<String> advs = g.startsWith("skyblock") ? advancements(p) : Set.of();
        List<Entry> es = new ArrayList<>();
        for (String k : group(g)) es.add(entry(p, pd, k, advs));
        return es;
    }
    Entry entry(Viewer p, PD pd, String key, Set<String> advs) {
        String id = key.substring(key.indexOf(':') + 1);
        if (key.startsWith("tag:")) return tagEntry(p, pd, tags.get(id), advs);
        boolean chat = key.startsWith("chat:");
        return colorEntry(p, pd, (chat ? chatColors : colors).get(id), chat);
    }
    void wearingOff(Menu m, PD pd) {
        if (pd.tag != null || pd.color != null || pd.chat != null) put(m, 46, item(Material.BARRIER, "&cTake everything off", List.of(), false), "off:all");
    }
    static String typeWord(String type) { return type.equals("tag") ? "tags" : type.equals("color") ? "name colours" : "chat colours"; }
    void offFor(Menu m, PD pd, String type) {
        String on = type.equals("tag") ? pd.tag : type.equals("color") ? pd.color : pd.chat;
        if (on != null) put(m, 46, takeOff(type.equals("tag") ? "tag" : type.equals("color") ? "name colour" : "chat colour"), "off:" + type);
    }

    void openSkyblock(Viewer p, String type) {
        PD pd = pd(p.getName());
        listPage(p, "skyblock:" + type, "&a&lSkyblock " + typeWord(type), item(Material.OAK_SAPLING, "&a&lSkyblock " + typeWord(type), List.of("&7Earned on &bCrispy Skyblock&7: advancements,",
                "&7skill levels (/skills) and your island's", "&7level (/island level).", "", "&8Yours to keep. Progress shows up here", "&8within a few minutes."), false),
                groupEntries(p, pd, "skyblock:" + type), m -> offFor(m, pd, type));
    }

    void openEvent(Viewer p, String type) {
        PD pd = pd(p.getName());
        listPage(p, "event:" + type, "&6&lHalloween " + typeWord(type), item(Material.JACK_O_LANTERN, "&6&lHalloween", List.of("&7Survive &6Haunted Night &7in the Multiverse:",
                "&7every completed run unlocks one Halloween", "&7cosmetic at random (one you don't have yet).", "", "&8Event cosmetics are yours to keep."), false),
                groupEntries(p, pd, "event:" + type), m -> offFor(m, pd, type));
    }


    /** Special: the staff-given (/vote grant) tags this player has. Not in the shop; only reachable from the hub's
     *  Special button, shown to players who own one. */
    void openSpecial(Viewer p) {
        PD pd = pd(p.getName());
        List<Entry> es = new ArrayList<>();
        for (Tag t : tags.values()) if (t.granted() && pd.owned.contains("tag:" + t.id())) es.add(tagEntry(p, pd, t, Set.of()));
        listPage(p, "special", "&d&lSpecial", item(Material.SPYGLASS, "&d&lSpecial tags", List.of("&7Given to you by staff."), false), es,
                m -> { if (pd.tag != null) put(m, 46, takeOff("tag"), "off:tag"); });
    }

    /** My cosmetics: everything unlocked; click one to wear it or take it off. */
    void openOwned(Viewer p) {
        PD pd = pd(p.getName());
        Set<String> advs = advancements(p);
        List<Entry> es = new ArrayList<>();
        for (String k : owned(p, pd)) es.add(entry(p, pd, k, advs));
        listPage(p, "owned", "&d&lMy cosmetics", item(Material.ENDER_CHEST, "&d&lMy cosmetics", List.of("&7Everything you've unlocked.", "&7Click one to wear it or take it off."), false),
                es, m -> wearingOff(m, pd));
    }

    /** Opens the page a menu kind names (after a click on it, or to go to it). */
    void reopen(Viewer p, String kind) {
        switch (kind) {
            case "cosmetics" -> openCosmetics(p);
            case "tags", "etags", "mtags" -> openTags(p, kind);
            case "event" -> openEvent(p, "tag");
            case "skyblock" -> openSkyblock(p, "tag");
            case "special" -> openSpecial(p);
            case "owned" -> openOwned(p);
            case "colors" -> openColorMenu(p, false, "classic");
            case "chatcolors" -> openColorMenu(p, true, "classic");
            default -> {
                if (kind.startsWith("cat:")) openCategory(p, kind.substring(4));
                else if (kind.startsWith("skyblock:")) openSkyblock(p, kind.substring(9));
                else if (kind.startsWith("event:")) openEvent(p, kind.substring(6));
                else if (kind.startsWith("colors:")) openColorMenu(p, false, kind.substring(7));
                else if (kind.startsWith("chatcolors:")) openColorMenu(p, true, kind.substring(11));
            }
        }
    }

    /** A click on one of these menus, here or (RemoteMenus) on another server. */
    void click(Viewer p, Menu m, int slot, boolean shift) {
        String a = m.actions.get(slot);
        if (a == null) return;
        UUID u = p.getUniqueId();
        if (a.equals("links")) { p.closeInventory(); links(p); }
        else if (a.equals("top")) { p.closeInventory(); top(p); }
        else if (a.equals("back")) open(p);
        else if (a.startsWith("claim:")) claim(p, a.substring(6), shift);
        else if (a.startsWith("pg:")) { pageOf.merge(u, Integer.parseInt(a.substring(3)), Integer::sum); reopen(p, m.kind); }
        else if (a.equals("filter")) {
            int i = Arrays.asList(FILTERS).indexOf(filterOf.getOrDefault(u, "all"));
            filterOf.put(u, FILTERS[(i + 1) % FILTERS.length]);
            pageOf.put(u, 0);
            p.playSound(Sound.UI_BUTTON_CLICK, 0.6f, 1f);
            reopen(p, m.kind);
        }
        else if (a.startsWith("off:")) {
            PD pd = pd(p.getName());
            if (a.equals("off:tag") || a.equals("off:all")) pd.tag = null;
            if (a.equals("off:chat") || a.equals("off:all")) pd.chat = null;
            if (a.equals("off:color") || a.equals("off:all")) pd.color = null;
            writeTags(); save();
            p.playSound(Sound.UI_BUTTON_CLICK, 0.6f, 1f);
            reopen(p, m.kind);
        }
        else if (a.startsWith("tag:") || a.startsWith("color:") || a.startsWith("chat:")) { cosmetic(p, a); reopen(p, m.kind); }
        else reopen(p, a);   // go to a page
    }

    // ------------------------------------------------------------------ "joined before" (the OG tag)
    /** Earliest date the network has for this player: Anarchy (or other) advancement timestamps, the firstPlayed time
     *  Paper left in old player files, and those files' last-saved date. Configured in cosmetics.joined-sources. */
    String firstSeen(Viewer p) {
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
    boolean joinedBefore(Viewer p, String date) {
        if (plugin.getConfig().getStringList("cosmetics.joined-sources.extra").stream().anyMatch(n -> n.equalsIgnoreCase(p.getName()))) return true;
        return firstSeen(p).compareTo(date) < 0;
    }

    String firstSeen(Player p) { return firstSeen(new Viewer.Local(p)); }
    void connect(Player p, String server) { connect(new Viewer.Local(p), server); }

    void cosmetic(Viewer p, String key) {
        PD pd = pd(p.getName());
        boolean isTag = key.startsWith("tag:");
        String id = key.substring(key.indexOf(':') + 1);
        Tag lim = isTag ? tags.get(id) : null;
        if (lim != null && lim.joinedBefore() != null && !joinedBefore(p, lim.joinedBefore())) {
            msg(p, "&c" + lim.display() + " &cis only for players who joined before &f" + lim.joinedBefore() + "&c.");
            p.playSound(Sound.ENTITY_VILLAGER_NO, 0.7f, 1f);
            if (id.equals(pd.tag)) { pd.tag = null; writeTags(); save(); }   // no longer qualifies: take it off
            return;
        }
        Tag et = isTag ? tags.get(id) : null;
        if (et != null && et.earned()) {
            boolean wearing = id.equals(pd.tag);
            String lock = wearing ? null : lockReason(p, et, advancements(p));
            if (lock != null) {
                msg(p, et.display() + " &7is locked: " + String.join(" ", requirement(et).subList(0, 1)).replace("&7", "&f"));
                p.playSound(Sound.ENTITY_VILLAGER_NO, 0.7f, 1f);
                return;
            }
            if (!et.ranked() && pd.owned.add(key)) {
                msg(p, "&aUnlocked " + et.display() + "&a!");
                p.playSound(Sound.UI_TOAST_CHALLENGE_COMPLETE, 0.6f, 1.2f);
            } else p.playSound(Sound.UI_BUTTON_CLICK, 0.6f, 1f);
            pd.tag = wearing ? null : id; writeTags(); save();
            return;
        }
        boolean isChat = key.startsWith("chat:");
        Map<String, NameColor> pool = isChat ? chatColors : colors;
        NameColor ev = isTag ? null : pool.get(id);
        if (ev != null && ev.earned()) {
            boolean using = id.equals(isChat ? pd.chat : pd.color);
            if (!using && !eventUnlocked(p, ev)) {
                msg(p, colored(ev.name(), ev.code()) + (ev.skyblock() ? " &7is locked: " + skyNeed(ev.score(), ev.min()).replace("&7", "&f") + "&7."
                        : " &7is locked: survive &6Haunted Night &7in the Multiverse to win Halloween cosmetics."));
                p.playSound(Sound.ENTITY_VILLAGER_NO, 0.7f, 1f);
                return;
            }
            if (pd.owned.add(key)) { msg(p, "&aUnlocked " + colored(ev.name(), ev.code()) + "&a!"); p.playSound(Sound.UI_TOAST_CHALLENGE_COMPLETE, 0.6f, 1.2f); }
            else p.playSound(Sound.UI_BUTTON_CLICK, 0.6f, 1f);
            if (isChat) pd.chat = using ? null : id; else pd.color = using ? null : id;
            writeTags(); save();
            return;
        }
        int cost = isTag ? (tags.containsKey(id) ? tags.get(id).cost() : -1) : (pool.containsKey(id) ? pool.get(id).cost() : -1);
        if (cost < 0) return;
        if (isTag && tags.get(id).granted() && !pd.owned.contains(key)) return;   // staff-given only
        if (!pd.owned.contains(key)) {
            if (pd.points < cost) { msg(p, "&cYou need &d" + cost + " &cvote points (you have &d" + pd.points + "&c)."); p.playSound(Sound.ENTITY_VILLAGER_NO, 0.7f, 1f); return; }
            pd.points -= cost;
            pd.owned.add(key);
            msg(p, "&aUnlocked!");
            p.playSound(Sound.UI_TOAST_CHALLENGE_COMPLETE, 0.6f, 1.2f);
        } else p.playSound(Sound.UI_BUTTON_CLICK, 0.6f, 1f);
        if (isTag) { pd.tag = id.equals(pd.tag) ? null : id; writeTags(); }
        else if (isChat) { pd.chat = id.equals(pd.chat) ? null : id; writeTags(); }
        else { pd.color = id.equals(pd.color) ? null : id; writeTags(); }
        save();
    }

    void links(CommandSender s) { links(new Viewer.Local(s)); }
    void top(CommandSender s) { top(new Viewer.Local(s)); }
    void links(Viewer s) {
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

    void top(Viewer s) {
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
            if (s instanceof Player p) Bukkit.getScheduler().runTask(plugin, () -> openCosmetics(new Viewer.Local(p))); return true;
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
            case "grant", "revoke" -> {   // staff-given cosmetics, e.g. /vote grant Steve tag:creator
                if (!admin || a.length < 3 || !a[2].matches("(tag|color|chat):[a-z0-9_]+")) { msg(s, "&7/vote " + sub + " <player> <tag|color|chat>:<id>"); return true; }
                String key = a[2], id = key.substring(key.indexOf(':') + 1);
                boolean exists = key.startsWith("tag:") ? tags.containsKey(id) : (key.startsWith("chat:") ? chatColors : colors).containsKey(id);
                if (!exists) { msg(s, "&cNo cosmetic called " + key + "."); return true; }
                PD pd = pd(a[1]);
                if (sub.equals("grant")) { pd.owned.add(key); if (key.startsWith("tag:") && pd.tag == null) pd.tag = id; }
                else {
                    pd.owned.remove(key);
                    if (key.startsWith("tag:") && id.equals(pd.tag)) pd.tag = null;
                    if (key.startsWith("color:") && id.equals(pd.color)) pd.color = null;
                    if (key.startsWith("chat:") && id.equals(pd.chat)) pd.chat = null;
                }
                writeTags(); save();
                msg(s, (sub.equals("grant") ? "Gave " : "Took ") + key + (sub.equals("grant") ? " to " : " from ") + a[1] + ".");
                Player t = Bukkit.getPlayerExact(a[1]);
                if (t != null && sub.equals("grant")) msg(t, "&aYou've been given " + (key.startsWith("tag:") ? tags.get(id).display() : key) + "&a! &7/cosmetics to wear it.");
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
            default -> { if (s instanceof Player p) Bukkit.getScheduler().runTask(plugin, () -> open(new Viewer.Local(p))); else links(s); }
        }
        return true;
    }
}

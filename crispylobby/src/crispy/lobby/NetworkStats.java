package crispy.lobby;

import com.google.gson.JsonElement;
import com.google.gson.JsonObject;
import com.google.gson.JsonParser;
import net.kyori.adventure.text.Component;
import org.bukkit.Bukkit;
import org.bukkit.Location;
import org.bukkit.World;
import org.bukkit.command.CommandSender;
import org.bukkit.configuration.ConfigurationSection;
import org.bukkit.entity.Display;
import org.bukkit.entity.Player;
import org.bukkit.entity.TextDisplay;

import java.io.IOException;
import java.nio.file.DirectoryStream;
import java.nio.file.Files;
import java.nio.file.Path;
import java.util.*;
import java.util.regex.Matcher;
import java.util.regex.Pattern;

/**
 * Network-wide player stats for the lobby. Every few minutes (off the main thread) it reads the vanilla stats
 * files of every backend server on this machine plus Factions balances (Essentials userdata), adds them up per
 * player name, and a rotating text_display near spawn shows the top 10 for each category. /stats shows your own.
 */
final class NetworkStats {
    enum Cat {
        PLAYTIME("⌚ Playtime"), PLAYER_KILLS("⚔ Player Kills"), MOB_KILLS("☠ Mob Kills"), DEATHS("✝ Deaths"),
        BLOCKS_MINED("⛏ Blocks Mined"), DISTANCE("➶ Distance Travelled"), JUMPS("⬆ Jumps"), MONEY("$ Richest (Factions)"),
        BALATRO_BLINDS("🃏 Balatro: Blinds Cleared"), BALATRO_HAND("🃏 Balatro: Best Hand"), BALATRO_WINS("🃏 Balatro: Wins");
        final String title;
        Cat(String title) { this.title = title; }
    }

    static final class Row {
        final String name;
        final long[] total = new long[Cat.values().length];
        final Map<String, Long> playtimeByServer = new TreeMap<>();
        Row(String name) { this.name = name; }
    }

    // server label -> {stats dir, usercache.json} relative to the instances folder; overridable in config (network-stats.servers)
    private static final String[][] DEFAULT_SERVERS = {
            {"Lobby", "CrispyLobby01/Minecraft/world/players/stats", "CrispyLobby01/Minecraft/usercache.json"},
            {"Anarchy", "CrispyAnarchy01/Minecraft/world/players/stats", "CrispyAnarchy01/Minecraft/usercache.json"},
            {"Vanilla", "Vanilla01/Minecraft/world/players/stats", "Vanilla01/Minecraft/usercache.json"},
            {"Factions", "Factions01/Minecraft/world/stats", "Factions01/Minecraft/usercache.json"},
            {"Falling", "Falling01/Minecraft/world/players/stats", "Falling01/Minecraft/usercache.json"},
            {"PvP", "CrispyPvP01/Minecraft/world/players/stats", "CrispyPvP01/Minecraft/usercache.json"},
    };
    private static final Pattern MONEY = Pattern.compile("(?m)^money:\\s*'?([0-9.Ee+-]+)'?\\s*$");
    private static final Pattern NAME = Pattern.compile("(?m)^last-account-name:\\s*'?([A-Za-z0-9_.]+)'?\\s*$");

    private final CrispyLobby plugin;
    private volatile Map<String, Row> rows = Map.of();
    private volatile long updatedAt;
    private TextDisplay display;
    private int page;

    NetworkStats(CrispyLobby plugin) { this.plugin = plugin; }

    ConfigurationSection cfg() {
        ConfigurationSection c = plugin.getConfig().getConfigurationSection("network-stats");
        return c != null ? c : plugin.getConfig().createSection("network-stats");
    }

    void start() {
        if (!cfg().getBoolean("enabled", true)) return;
        long refresh = Math.max(1, cfg().getLong("refresh-minutes", 5)) * 60L * 20L;
        long rotate = Math.max(2, cfg().getLong("rotate-seconds", 8)) * 20L;
        Bukkit.getScheduler().runTaskTimerAsynchronously(plugin, this::collect, 20L, refresh);
        Bukkit.getScheduler().runTaskTimer(plugin, this::rotate, 60L, rotate);
    }

    void stop() { if (display != null) display.remove(); display = null; }

    // ------------------------------------------------------------------ collecting (async)
    void collect() {
        Path root = Path.of(cfg().getString("instances-dir", "/AMPStorage/.ampdata/instances"));
        Map<String, String> names = new HashMap<>();             // uuid -> name, from every server's usercache
        List<String[]> servers = new ArrayList<>();
        ConfigurationSection sc = cfg().getConfigurationSection("servers");
        if (sc != null) for (String k : sc.getKeys(false))
            servers.add(new String[]{k, sc.getString(k + ".stats", ""), sc.getString(k + ".usercache", "")});
        else servers.addAll(Arrays.asList(DEFAULT_SERVERS));
        for (String[] s : servers) readUsercache(root.resolve(s[2]), names);

        Map<String, Row> out = new HashMap<>();
        for (String[] s : servers) {
            Path dir = root.resolve(s[1]);
            if (!Files.isDirectory(dir)) continue;
            try (DirectoryStream<Path> ds = Files.newDirectoryStream(dir, "*.json")) {
                for (Path f : ds) {
                    String uuid = f.getFileName().toString().replace(".json", "");
                    String name = names.get(uuid);
                    if (name == null) continue;
                    try { addStats(out.computeIfAbsent(name.toLowerCase(Locale.ROOT), k -> new Row(name)), s[0], JsonParser.parseString(Files.readString(f)).getAsJsonObject()); }
                    catch (Exception ignored) { }
                }
            } catch (IOException e) { plugin.getLogger().warning("network-stats: can't read " + dir + ": " + e.getMessage()); }
        }
        Path ess = root.resolve(cfg().getString("factions-userdata", "Factions01/Minecraft/plugins/Essentials/userdata"));
        if (Files.isDirectory(ess)) {
            try (DirectoryStream<Path> ds = Files.newDirectoryStream(ess, "*.yml")) {
                for (Path f : ds) {
                    try {
                        String y = Files.readString(f);
                        Matcher m = MONEY.matcher(y), n = NAME.matcher(y);
                        String uuid = f.getFileName().toString().replace(".yml", "");
                        String name = n.find() ? n.group(1) : names.get(uuid);
                        if (name == null || !m.find()) continue;
                        out.computeIfAbsent(name.toLowerCase(Locale.ROOT), k -> new Row(name)).total[Cat.MONEY.ordinal()] += (long) Double.parseDouble(m.group(1));
                    } catch (Exception ignored) { }
                }
            } catch (IOException ignored) { }
        }
        // Balatro Craft (this lobby): scores.yml alltime.<uuid>.{name, progress = blinds cleared, best = best hand, wins}
        java.io.File bal = new java.io.File(plugin.getDataFolder().getParentFile(), "BalatroCraft/scores.yml");
        if (bal.isFile()) {
            ConfigurationSection all = org.bukkit.configuration.file.YamlConfiguration.loadConfiguration(bal).getConfigurationSection("alltime");
            if (all != null) for (String id : all.getKeys(false)) {
                String name = all.getString(id + ".name", names.get(id));
                if (name == null) continue;
                Row r = out.computeIfAbsent(name.toLowerCase(Locale.ROOT), k -> new Row(name));
                r.total[Cat.BALATRO_BLINDS.ordinal()] = Math.max(r.total[Cat.BALATRO_BLINDS.ordinal()], all.getLong(id + ".progress"));
                r.total[Cat.BALATRO_HAND.ordinal()] = Math.max(r.total[Cat.BALATRO_HAND.ordinal()], all.getLong(id + ".best"));
                r.total[Cat.BALATRO_WINS.ordinal()] += all.getLong(id + ".wins");
            }
        }
        rows = out;
        updatedAt = System.currentTimeMillis();
    }

    private static void readUsercache(Path f, Map<String, String> names) {
        try {
            for (JsonElement e : JsonParser.parseString(Files.readString(f)).getAsJsonArray()) {
                JsonObject o = e.getAsJsonObject();
                if (o.has("uuid") && o.has("name")) names.putIfAbsent(o.get("uuid").getAsString(), o.get("name").getAsString());
            }
        } catch (Exception ignored) { }
    }

    private static long num(JsonObject o, String k) { return o != null && o.has(k) ? o.get(k).getAsLong() : 0; }

    private static void addStats(Row r, String server, JsonObject root) {
        JsonObject stats = root.getAsJsonObject("stats");
        if (stats == null) return;
        JsonObject custom = stats.getAsJsonObject("minecraft:custom");
        long play = num(custom, "minecraft:play_time");
        if (play == 0) play = num(custom, "minecraft:play_one_minute");   // older worlds
        r.total[Cat.PLAYTIME.ordinal()] += play;
        r.playtimeByServer.merge(server, play, Long::sum);
        r.total[Cat.PLAYER_KILLS.ordinal()] += num(custom, "minecraft:player_kills");
        r.total[Cat.MOB_KILLS.ordinal()] += num(custom, "minecraft:mob_kills");
        r.total[Cat.DEATHS.ordinal()] += num(custom, "minecraft:deaths");
        r.total[Cat.JUMPS.ordinal()] += num(custom, "minecraft:jump");
        if (custom != null) for (Map.Entry<String, JsonElement> e : custom.entrySet())
            if (e.getKey().endsWith("_one_cm")) r.total[Cat.DISTANCE.ordinal()] += e.getValue().getAsLong();
        JsonObject mined = stats.getAsJsonObject("minecraft:mined");
        if (mined != null) for (Map.Entry<String, JsonElement> e : mined.entrySet()) r.total[Cat.BLOCKS_MINED.ordinal()] += e.getValue().getAsLong();
    }

    static String fmt(Cat c, long v) {
        return switch (c) {
            case PLAYTIME -> String.format(Locale.ROOT, "%.1f h", v / 72000.0);
            case DISTANCE -> String.format(Locale.ROOT, "%.1f km", v / 100000.0);
            case MONEY -> v >= 1_000_000 ? String.format(Locale.ROOT, "$%.2fM", v / 1e6) : v >= 1000 ? String.format(Locale.ROOT, "$%.1fk", v / 1e3) : "$" + v;
            default -> String.format(Locale.ROOT, "%,d", v);
        };
    }

    List<Row> top(Cat c, int n) {
        List<Row> list = new ArrayList<>();
        for (Row r : rows.values()) if (r.total[c.ordinal()] > 0) list.add(r);
        list.sort((a, b) -> Long.compare(b.total[c.ordinal()], a.total[c.ordinal()]));
        return list.subList(0, Math.min(n, list.size()));
    }

    // ------------------------------------------------------------------ the board (main thread)
    Location location() {
        World w = Bukkit.getWorld(cfg().getString("location.world", "world"));
        if (w == null) w = Bukkit.getWorlds().get(0);
        return new Location(w, cfg().getDouble("location.x", 0.5), cfg().getDouble("location.y", 68.5), cfg().getDouble("location.z", 12.5));
    }

    void moveHere(Player p) {
        Location l = p.getLocation();
        cfg().set("location.world", l.getWorld().getName());
        cfg().set("location.x", Math.floor(l.getX()) + 0.5);
        cfg().set("location.y", Math.round((l.getY() + 2.0) * 10) / 10.0);
        cfg().set("location.z", Math.floor(l.getZ()) + 0.5);
        plugin.saveConfig();
        stop();
        rotate();
    }

    void rotate() {
        if (!cfg().getBoolean("enabled", true)) return;
        Location loc = location();
        if (display == null || !display.isValid()) {
            if (!loc.isChunkLoaded()) return;
            loc.getWorld().getNearbyEntitiesByType(TextDisplay.class, loc, 3).stream()
                    .filter(e -> e.getScoreboardTags().contains("crispy.netstats")).forEach(org.bukkit.entity.Entity::remove);
            display = loc.getWorld().spawn(loc, TextDisplay.class, d -> {
                d.setPersistent(false);
                d.addScoreboardTag("crispy.netstats");
                d.setBillboard(Display.Billboard.CENTER);
                d.setLineWidth(240);
                d.setBackgroundColor(org.bukkit.Color.fromARGB(110, 0, 0, 0));
            });
        }
        Cat[] cats = Cat.values();
        Cat c = cats[page++ % cats.length];
        int n = Math.max(1, cfg().getInt("top", 10));
        StringBuilder s = new StringBuilder("&d&lCrispyAnarchy Stats\n&e&l").append(c.title).append("\n&7")
                .append(c == Cat.MONEY ? "Factions" : c.name().startsWith("BALATRO") ? "Lobby · /balatro" : "All servers").append("\n");
        List<Row> top = top(c, n);
        if (top.isEmpty()) s.append("\n&8No data yet");
        for (int i = 0; i < top.size(); i++) {
            String col = i == 0 ? "&6" : i == 1 ? "&f" : i == 2 ? "&c" : "&7";
            s.append("\n").append(col).append(i + 1).append(". &f").append(top.get(i).name).append(" &a").append(fmt(c, top.get(i).total[c.ordinal()]));
        }
        long mins = updatedAt == 0 ? -1 : (System.currentTimeMillis() - updatedAt) / 60000;
        s.append("\n\n&8").append(mins < 0 ? "Loading..." : "Updated " + (mins == 0 ? "just now" : mins + " min ago")).append(" · /stats");
        display.text(CrispyLobby.AMP.deserialize(s.toString()));
    }

    // ------------------------------------------------------------------ /stats [player]
    void showStats(CommandSender to, String who) {
        Row r = rows.get(who.toLowerCase(Locale.ROOT));
        if (r == null) { to.sendMessage(CrispyLobby.AMP.deserialize("&cNo stats found for &f" + who + "&c (they update every few minutes).")); return; }
        StringBuilder s = new StringBuilder("&d&l" + r.name + "'s network stats");
        for (Cat c : Cat.values()) {
            List<Row> all = top(c, Integer.MAX_VALUE);
            int rank = all.indexOf(r) + 1;
            s.append("\n&7").append(c.title).append(": &f").append(fmt(c, r.total[c.ordinal()]))
                    .append(rank > 0 ? " &8(#" + rank + ")" : "");
        }
        StringBuilder per = new StringBuilder();
        r.playtimeByServer.forEach((srv, t) -> { if (t > 0) per.append(per.length() == 0 ? "" : "&8, ").append("&7").append(srv).append(" &f").append(fmt(Cat.PLAYTIME, t)); });
        if (per.length() > 0) s.append("\n&7Playtime by server: ").append(per);
        to.sendMessage(CrispyLobby.AMP.deserialize(s.toString()));
    }
}

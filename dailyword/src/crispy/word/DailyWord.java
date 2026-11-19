package crispy.word;

import com.google.gson.Gson;
import com.google.gson.GsonBuilder;
import com.google.gson.JsonObject;
import io.papermc.paper.dialog.Dialog;
import io.papermc.paper.registry.data.dialog.ActionButton;
import io.papermc.paper.registry.data.dialog.DialogBase;
import io.papermc.paper.registry.data.dialog.action.DialogAction;
import io.papermc.paper.registry.data.dialog.body.DialogBody;
import io.papermc.paper.registry.data.dialog.input.DialogInput;
import io.papermc.paper.registry.data.dialog.type.DialogType;
import net.kyori.adventure.text.event.ClickCallback;
import java.time.Duration;
import io.papermc.paper.event.player.AsyncChatEvent;
import net.kyori.adventure.text.Component;
import net.kyori.adventure.text.event.ClickEvent;
import net.kyori.adventure.text.event.HoverEvent;
import net.kyori.adventure.text.format.TextDecoration;
import net.kyori.adventure.text.serializer.legacy.LegacyComponentSerializer;
import net.kyori.adventure.text.serializer.plain.PlainTextComponentSerializer;
import org.bukkit.Bukkit;
import org.bukkit.Material;
import org.bukkit.Sound;
import org.bukkit.command.Command;
import org.bukkit.command.CommandSender;
import org.bukkit.configuration.ConfigurationSection;
import org.bukkit.configuration.file.YamlConfiguration;
import org.bukkit.entity.Player;
import org.bukkit.event.EventHandler;
import org.bukkit.event.EventPriority;
import org.bukkit.event.Listener;
import org.bukkit.event.inventory.InventoryClickEvent;
import org.bukkit.event.inventory.InventoryDragEvent;
import org.bukkit.event.player.PlayerQuitEvent;
import org.bukkit.inventory.Inventory;
import org.bukkit.inventory.InventoryHolder;
import org.bukkit.inventory.ItemFlag;
import org.bukkit.inventory.ItemStack;
import org.bukkit.inventory.meta.ItemMeta;
import org.bukkit.plugin.java.JavaPlugin;

import java.io.File;
import java.io.IOException;
import java.nio.charset.StandardCharsets;
import java.nio.file.Files;
import java.time.LocalDate;
import java.time.ZoneId;
import java.util.*;
import java.util.regex.Pattern;

/**
 * Daily Word: guess the day's five-letter word in six tries, in a chest menu in the lobby.
 *
 * The word comes from the Discord bot (tools/discordbot/dailyword.py), which picks a random unused word every day and
 * writes word.json ({day, number, word}), plus valid.txt (every allowed guess) and answers.txt, into this plugin's
 * folder. If the bot's word is missing or not today's, the plugin picks one itself from answers.txt (seeded by the
 * date, so it's the same for everyone). Days run on America/Chicago, like Balatro Craft's daily run.
 *
 * Guessing: click "Type a guess" and send the word in chat (that message is hidden from chat), or /word <guess>.
 * The board shows each guess as coloured glass named by letter, and the colours are repeated in chat.
 * Stats (played, won, streaks, guess counts) in stats.yml; summary.json is written for the bot's /dailyword.
 * Spoiler guard: a player who has finished today can't post today's word in chat.
 */
public class DailyWord extends JavaPlugin implements Listener {
    static final LegacyComponentSerializer AMP = LegacyComponentSerializer.legacyAmpersand();
    static final String PREFIX = "&8[&a&lDaily &f&lWord&8] &7";
    static final ZoneId ZONE = ZoneId.of("America/Chicago");
    static final int LEN = 5, TRIES = 6;
    static final Pattern WORD = Pattern.compile("[a-z]{5}");
    static final Gson GSON = new GsonBuilder().setPrettyPrinting().create();

    String day, word; int number;
    long wordStamp = -1;
    final Set<String> valid = new HashSet<>();
    final List<String> answers = new ArrayList<>();
    long validStamp = -1, answersStamp = -1;
    File statsFile; YamlConfiguration stats;
    final Set<UUID> typing = new HashSet<>();

    @Override public void onEnable() {
        getDataFolder().mkdirs();
        statsFile = new File(getDataFolder(), "stats.yml"); stats = YamlConfiguration.loadConfiguration(statsFile);
        getServer().getPluginManager().registerEvents(this, this);
        refresh();
        Bukkit.getScheduler().runTaskTimer(this, this::refresh, 20 * 30, 20 * 30);
    }

    static Component c(String s) { return AMP.deserialize(s).decoration(TextDecoration.ITALIC, false); }
    static void msg(CommandSender s, String m) { s.sendMessage(c(PREFIX + m)); }
    static String today() { return LocalDate.now(ZONE).toString(); }

    // ------------------------------------------------------------------ today's word (from the bot, else our own pick)
    void refresh() {
        loadList("valid.txt", valid, true);
        loadList("answers.txt", answers, false);
        String t = today();
        File f = new File(getDataFolder(), "word.json");
        if (f.exists() && f.lastModified() != wordStamp) {
            try {
                JsonObject o = GSON.fromJson(Files.readString(f.toPath()), JsonObject.class);
                wordStamp = f.lastModified();
                String w = o.get("word").getAsString().toLowerCase(Locale.ROOT);
                if (o.get("day").getAsString().equals(t) && WORD.matcher(w).matches()) {
                    if (!t.equals(day) || !w.equals(word)) { day = t; word = w; number = o.get("number").getAsInt(); valid.add(w); newDay(); }
                    return;
                }
            } catch (Exception e) { getLogger().warning("word.json: " + e); }
        }
        if (t.equals(day)) return;
        // no word for today from the bot (yet): pick one ourselves, the same for everyone
        if (answers.isEmpty()) { if (word != null) getLogger().warning("no word for " + t + " and no answers.txt"); return; }
        long h = 1125899906842597L; for (char ch : ("dailyword-" + t).toCharArray()) h = 31 * h + ch;
        day = t; word = answers.get(Math.floorMod(h, answers.size())); number = stats.getInt("last-number") + 1; valid.add(word);
        getLogger().info("no word from the bot for " + t + ": picked one from answers.txt");
        newDay();
    }

    void loadList(String name, Collection<String> into, boolean set) {
        File f = new File(getDataFolder(), name);
        long stamp = f.exists() ? f.lastModified() : -2;
        if (stamp == (set ? validStamp : answersStamp)) return;
        if (set) validStamp = stamp; else answersStamp = stamp;
        if (!f.exists()) return;
        try {
            List<String> lines = Files.readAllLines(f.toPath(), StandardCharsets.UTF_8);
            into.clear();
            for (String l : lines) { String w = l.trim().toLowerCase(Locale.ROOT); if (WORD.matcher(w).matches()) into.add(w); }
        } catch (IOException e) { getLogger().warning(name + ": " + e); }
    }

    void newDay() {
        int prev = stats.getInt("last-number");
        if (number <= prev && !day.equals(stats.getString("last-day"))) number = prev + 1;   // never reuse a number
        stats.set("last-day", day); stats.set("last-number", number);
        stats.set("history." + day + ".number", number);
        stats.set("history." + day + ".word", word);
        save();
        writeSummary();
    }

    // ------------------------------------------------------------------ player state
    ConfigurationSection pl(Player p) {
        String k = "players." + p.getUniqueId();
        ConfigurationSection s = stats.getConfigurationSection(k);
        if (s == null) s = stats.createSection(k);
        s.set("name", p.getName());
        return s;
    }
    List<String> guesses(ConfigurationSection s) { return day != null && day.equals(s.getString("day")) ? new ArrayList<>(s.getStringList("guesses")) : new ArrayList<>(); }
    boolean finished(List<String> g) { return g.contains(word) || g.size() >= TRIES; }

    String guess(Player p, String raw) {
        if (word == null) return "There's no word today yet. Try again in a minute.";
        String g = raw.trim().toLowerCase(Locale.ROOT);
        ConfigurationSection s = pl(p);
        List<String> gs = guesses(s);
        if (finished(gs)) return "You've finished today's word. A new one comes at midnight (Central time).";
        if (!WORD.matcher(g).matches()) return "Guesses are five letters, A to Z.";
        if (!valid.isEmpty() && !valid.contains(g)) return "&f" + g.toUpperCase(Locale.ROOT) + " &cisn't in the word list.";
        if (gs.contains(g)) return "You already tried &f" + g.toUpperCase(Locale.ROOT) + "&c.";
        gs.add(g);
        s.set("day", day); s.set("guesses", gs);
        String hk = "history." + day;
        if (gs.size() == 1) stats.set(hk + ".played", stats.getInt(hk + ".played") + 1);
        p.sendMessage(c(PREFIX + "Guess " + gs.size() + "/" + TRIES + ": " + tiles(g, Score.score(g, word))));
        if (g.equals(word)) {
            int streak = day.equals(nextDay(s.getString("last-done"))) && s.getBoolean("last-won") ? s.getInt("streak") + 1 : 1;
            finish(s, true, streak);
            s.set("dist." + gs.size(), s.getInt("dist." + gs.size()) + 1);
            stats.set(hk + ".solved", stats.getInt(hk + ".solved") + 1);
            stats.set(hk + ".dist." + gs.size(), stats.getInt(hk + ".dist." + gs.size()) + 1);
            List<String> solvers = stats.getStringList(hk + ".solvers"); solvers.add(p.getName() + ":" + gs.size()); stats.set(hk + ".solvers", solvers);
            p.playSound(p.getLocation(), Sound.UI_TOAST_CHALLENGE_COMPLETE, 0.8f, 1.2f);
            msg(p, "&a&lSolved in " + gs.size() + "/" + TRIES + "! &7Streak: &f" + streak + " day" + (streak == 1 ? "" : "s") + "&7. New word at midnight (Central).");
            Component share = c(PREFIX + "&f" + p.getName() + " &7solved Daily Word &f#" + number + " &7in &a" + gs.size() + "/" + TRIES + "&7! ")
                    .append(c("&8[hover]").hoverEvent(HoverEvent.showText(c(grid(gs)))))
                    .append(c(" &a&n[Play]").clickEvent(ClickEvent.runCommand("/word")));
            for (Player o : Bukkit.getOnlinePlayers()) o.sendMessage(share);
        } else if (gs.size() >= TRIES) {
            finish(s, false, 0);
            stats.set(hk + ".failed", stats.getInt(hk + ".failed") + 1);
            p.playSound(p.getLocation(), Sound.ENTITY_VILLAGER_NO, 0.7f, 1f);
            msg(p, "&cOut of guesses. &7The word was &f&l" + word.toUpperCase(Locale.ROOT) + "&7. Your streak resets; try again tomorrow!");
        } else p.playSound(p.getLocation(), Sound.BLOCK_NOTE_BLOCK_HAT, 0.7f, 1.3f);
        save();
        writeSummary();
        return null;
    }
    void finish(ConfigurationSection s, boolean won, int streak) {
        s.set("played", s.getInt("played") + 1);
        if (won) s.set("won", s.getInt("won") + 1);
        s.set("streak", streak);
        if (streak > s.getInt("best")) s.set("best", streak);
        s.set("last-done", day); s.set("last-won", won);
    }
    static String nextDay(String d) { try { return LocalDate.parse(d).plusDays(1).toString(); } catch (Exception e) { return ""; } }

    String tiles(String g, int[] sc) {
        StringBuilder b = new StringBuilder();
        for (int i = 0; i < LEN; i++) b.append(sc[i] == 2 ? "&a&l" : sc[i] == 1 ? "&e&l" : "&8&l").append(Character.toUpperCase(g.charAt(i))).append(" ");
        return b.toString().trim();
    }
    String grid(List<String> gs) {
        StringBuilder b = new StringBuilder("&fDaily Word #" + number + " " + gs.size() + "/" + TRIES);
        for (String g : gs) { b.append("\n"); for (int x : Score.score(g, word)) b.append(x == 2 ? "&a■" : x == 1 ? "&e■" : "&8■"); }
        return b.toString();
    }

    void save() { try { stats.save(statsFile); } catch (IOException e) { getLogger().warning("stats save failed: " + e); } }

    /** summary.json for the Discord bot's /dailyword: today's number and counts (never today's word), yesterday's word
     *  and results, and the best current streaks. */
    void writeSummary() {
        if (day == null) return;
        Map<String, Object> o = new LinkedHashMap<>();
        o.put("day", day); o.put("number", number);
        o.put("today", dayStats(day, false));
        String y = LocalDate.parse(day).minusDays(1).toString();
        if (stats.isConfigurationSection("history." + y)) o.put("yesterday", dayStats(y, true));
        List<Map<String, Object>> streaks = new ArrayList<>();
        ConfigurationSection ps = stats.getConfigurationSection("players");
        if (ps != null) for (String k : ps.getKeys(false)) {
            ConfigurationSection s = ps.getConfigurationSection(k);
            if (s == null) continue;
            String done = s.getString("last-done", "");
            boolean alive = s.getBoolean("last-won") && (done.equals(day) || done.equals(y));
            if (alive && s.getInt("streak") > 0) streaks.add(Map.of("name", s.getString("name", "?"), "streak", s.getInt("streak")));
        }
        streaks.sort((a, b) -> (int) b.get("streak") - (int) a.get("streak"));
        o.put("streaks", streaks.subList(0, Math.min(5, streaks.size())));
        try { Files.writeString(new File(getDataFolder(), "summary.json").toPath(), GSON.toJson(o)); } catch (IOException e) { getLogger().warning("summary: " + e); }
    }
    Map<String, Object> dayStats(String d, boolean withWord) {
        String hk = "history." + d;
        Map<String, Object> m = new LinkedHashMap<>();
        m.put("number", stats.getInt(hk + ".number"));
        if (withWord) m.put("word", stats.getString(hk + ".word", ""));
        m.put("played", stats.getInt(hk + ".played")); m.put("solved", stats.getInt(hk + ".solved")); m.put("failed", stats.getInt(hk + ".failed"));
        List<Integer> dist = new ArrayList<>(); for (int i = 1; i <= TRIES; i++) dist.add(stats.getInt(hk + ".dist." + i)); m.put("dist", dist);
        m.put("solvers", stats.getStringList(hk + ".solvers"));
        return m;
    }

    // ------------------------------------------------------------------ commands
    @Override public boolean onCommand(CommandSender s, Command cmd, String label, String[] a) {
        if (!(s instanceof Player p)) {
            if (a.length > 0 && a[0].equalsIgnoreCase("refresh")) { day = null; wordStamp = -1; refresh(); msg(s, "Daily Word #" + number + " loaded."); }
            else msg(s, "Daily Word #" + number + " (" + day + "). Console: /word refresh");
            return true;
        }
        String sub = a.length > 0 ? a[0].toLowerCase(Locale.ROOT) : "";
        Bukkit.getScheduler().runTask(this, () -> {   // next tick: menus (the hub selector) run this from a click
            if (!p.isOnline()) return;
            if (sub.equals("help")) help(p);
            else if (sub.equals("stats")) showStats(p);
            else if (sub.equals("top")) showTop(p);
            else if (sub.equals("board")) open(p);
            else if (WORD.matcher(sub).matches() || sub.equals("guess") && a.length > 1) {
                String err = guess(p, sub.equals("guess") ? a[1] : sub);
                play(p, err == null ? null : "&c" + err);
            } else play(p, null);
        });
        return true;
    }
    void help(Player p) {
        for (String l : new String[]{
                "&a&lDaily Word &7- guess the day's five-letter word in six tries.",
                "&7After each guess: &a&lgreen &7= right letter, right spot; &e&lyellow &7= in the word, wrong spot; &8&lgrey &7= not in it.",
                "&7Click &fType a guess &7and send it in chat (only you see it), or type &f/word <guess>&7.",
                "&7Everyone gets the same word. A new one at midnight (Central time). Keep your streak going!"}) p.sendMessage(c(l));
    }
    void showStats(Player p) {
        ConfigurationSection s = pl(p);
        int played = s.getInt("played"), won = s.getInt("won");
        msg(p, "&fYour Daily Word stats");
        p.sendMessage(c("&7Played &f" + played + " &8· &7Won &f" + (played == 0 ? 0 : won * 100 / played) + "% &8· &7Streak &f" + s.getInt("streak") + " &8· &7Best &f" + s.getInt("best")));
        StringBuilder b = new StringBuilder("&7Guesses: ");
        for (int i = 1; i <= TRIES; i++) b.append("&f").append(i).append("&8:&a").append(s.getInt("dist." + i)).append(" ");
        p.sendMessage(c(b.toString()));
    }
    void showTop(Player p) {
        msg(p, "&fToday's solvers &7(#" + number + ")");
        List<String> sol = stats.getStringList("history." + day + ".solvers");
        if (sol.isEmpty()) p.sendMessage(c("&7Nobody yet. Be the first!"));
        sol.stream().sorted(Comparator.comparingInt(x -> Integer.parseInt(x.substring(x.lastIndexOf(':') + 1)))).limit(10)
                .forEach(x -> p.sendMessage(c("&f" + x.substring(0, x.lastIndexOf(':')) + " &7in &a" + x.substring(x.lastIndexOf(':') + 1) + "/" + TRIES)));
        ConfigurationSection ps = stats.getConfigurationSection("players");
        if (ps == null) return;
        List<ConfigurationSection> best = ps.getKeys(false).stream().map(ps::getConfigurationSection).filter(Objects::nonNull)
                .filter(x -> x.getInt("best") > 0).sorted(Comparator.comparingInt((ConfigurationSection x) -> -x.getInt("best"))).limit(5).toList();
        if (!best.isEmpty()) p.sendMessage(c("&7Longest streaks: " + String.join("&7, ", best.stream().map(x -> "&f" + x.getString("name") + " &a" + x.getInt("best")).toList())));
    }

    // ------------------------------------------------------------------ the popup (1.1.0)
    /** Bedrock players (Floodgate names start with a dot) may not get Java dialogs: they keep the chest and chat. */
    static boolean bedrock(Player p) { return p.getName().startsWith("."); }

    /** The game screen: the popup for Java players, the chest for Bedrock. note: a line shown above the board. */
    void play(Player p, String note) {
        if (word == null) { msg(p, "&cThere's no word today yet. Try again in a minute."); return; }
        if (bedrock(p)) { if (note != null) msg(p, note); open(p); return; }
        dialog(p, note);
    }

    /** A dialog: the guesses so far in coloured letters, the letters tried, and (until you're done) a text box and a
     *  Guess button. Every guess shows a fresh popup, so you can keep typing without leaving it. */
    void dialog(Player p, String note) {
        ConfigurationSection s = pl(p);
        List<String> gs = guesses(s);
        boolean done = finished(gs);
        int[] keys = new int[26]; Arrays.fill(keys, -1);
        StringBuilder board = new StringBuilder();
        for (int r = 0; r < TRIES; r++) {
            if (r > 0) board.append("\n");
            if (r < gs.size()) {
                String g = gs.get(r); int[] sc = Score.score(g, word);
                for (int i = 0; i < LEN; i++) {
                    keys[g.charAt(i) - 'a'] = Math.max(keys[g.charAt(i) - 'a'], sc[i]);
                    board.append(sc[i] == 2 ? "&a&l" : sc[i] == 1 ? "&e&l" : "&8&l").append(Character.toUpperCase(g.charAt(i))).append("  ");
                }
            } else board.append(r == gs.size() && !done ? "&f_  _  _  _  _" : "&8_  _  _  _  _");
        }
        StringBuilder kb = new StringBuilder();
        String order = "QWERTYUIOPASDFGHJKLZXCVBNM";
        for (int i = 0; i < 26; i++) {
            if (i == 10 || i == 19) kb.append("\n");
            char ch = order.charAt(i); int k = keys[ch - 'A'];
            kb.append(k == 2 ? "&a&l" : k == 1 ? "&e&l" : k == 0 ? "&8&m" : "&f").append(ch).append("&r ");
        }
        List<DialogBody> body = new ArrayList<>();
        if (note != null) body.add(DialogBody.plainMessage(c(note), 300));
        body.add(DialogBody.plainMessage(c(board.toString()), 200));
        if (done) body.add(DialogBody.plainMessage(c(gs.contains(word) ? "&a&lSolved in " + gs.size() + "/" + TRIES + "! &7Streak: &f" + s.getInt("streak")
                : "&cOut of guesses. &7The word was &f&l" + word.toUpperCase(Locale.ROOT)), 300));
        body.add(DialogBody.plainMessage(c(kb.toString()), 300));
        body.add(DialogBody.plainMessage(c("&a■ &7right spot   &e■ &7in the word   &8■ &7not in it"), 300));
        List<DialogInput> inputs = done ? List.of() : List.of(DialogInput.text("guess", c("&7Your guess (" + (gs.size() + 1) + "/" + TRIES + ")"))
                .width(160).maxLength(LEN).labelVisible(true).build());
        ClickCallback.Options once = ClickCallback.Options.builder().uses(1).lifetime(Duration.ofMinutes(30)).build();
        List<ActionButton> buttons = new ArrayList<>();
        if (!done) buttons.add(ActionButton.builder(c("&a&lGuess")).tooltip(c("&7Check your word")).width(110)
                .action(DialogAction.customClick((view, audience) -> {
                    String g = view.getText("guess");
                    Bukkit.getScheduler().runTask(this, () -> {
                        if (!p.isOnline()) return;
                        String err = guess(p, g == null ? "" : g);
                        dialog(p, err == null ? null : "&c" + err);
                    });
                }, once)).build());
        buttons.add(ActionButton.builder(c("&fBoard & stats")).tooltip(c("&7The chest view, your stats and today's solvers")).width(110)
                .action(DialogAction.customClick((view, audience) -> Bukkit.getScheduler().runTask(this, () -> { if (p.isOnline()) open(p); }), once)).build());
        ActionButton close = ActionButton.builder(c("&7Close")).width(110).build();
        Dialog d = Dialog.create(b -> b.empty()
                .base(DialogBase.builder(c("&a&lDaily Word &f#" + number)).canCloseWithEscape(true)
                        .afterAction(DialogBase.DialogAfterAction.CLOSE).body(body).inputs(inputs).build())
                .type(DialogType.multiAction(buttons).exitAction(close).columns(2).build()));
        p.showDialog(d);
    }

    // ------------------------------------------------------------------ the menu
    static final class Menu implements InventoryHolder { Inventory inv; @Override public Inventory getInventory() { return inv; } }
    static ItemStack item(Material m, String name, String... lore) {
        ItemStack it = new ItemStack(m);
        ItemMeta meta = it.getItemMeta();
        meta.displayName(c(name));
        if (lore.length > 0) meta.lore(Arrays.stream(lore).map(DailyWord::c).toList());
        meta.addItemFlags(ItemFlag.values());
        it.setItemMeta(meta);
        return it;
    }

    void open(Player p) {
        if (word == null) { msg(p, "&cThere's no word today yet. Try again in a minute."); return; }
        Menu m = new Menu();
        m.inv = Bukkit.createInventory(m, 54, c("&8Daily Word #" + number));
        ConfigurationSection s = pl(p);
        List<String> gs = guesses(s);
        boolean done = finished(gs);
        int[] keys = new int[26]; Arrays.fill(keys, -1);   // best colour seen per letter
        for (int r = 0; r < TRIES; r++) {
            for (int i = 0; i < LEN; i++) {
                int slot = r * 9 + 2 + i;
                if (r < gs.size()) {
                    String g = gs.get(r); int[] sc = Score.score(g, word);
                    char ch = Character.toUpperCase(g.charAt(i));
                    keys[g.charAt(i) - 'a'] = Math.max(keys[g.charAt(i) - 'a'], sc[i]);
                    Material mat = sc[i] == 2 ? Material.LIME_STAINED_GLASS : sc[i] == 1 ? Material.YELLOW_STAINED_GLASS : Material.GRAY_STAINED_GLASS;
                    m.inv.setItem(slot, item(mat, (sc[i] == 2 ? "&a&l" : sc[i] == 1 ? "&e&l" : "&8&l") + ch,
                            sc[i] == 2 ? "&aRight letter, right spot" : sc[i] == 1 ? "&eIn the word, wrong spot" : "&8Not in the word"));
                } else m.inv.setItem(slot, item(r == gs.size() && !done ? Material.WHITE_STAINED_GLASS_PANE : Material.LIGHT_GRAY_STAINED_GLASS_PANE, "&7Guess " + (r + 1)));
            }
        }
        StringBuilder kb1 = new StringBuilder(), kb2 = new StringBuilder(), kb3 = new StringBuilder();
        String rows = "QWERTYUIOPASDFGHJKLZXCVBNM";
        for (int i = 0; i < 26; i++) {
            char ch = rows.charAt(i); int k = keys[ch - 'A'];
            String col = k == 2 ? "&a&l" : k == 1 ? "&e&l" : k == 0 ? "&8&m" : "&f&l";
            (i < 10 ? kb1 : i < 19 ? kb2 : kb3).append(col).append(ch).append("&r ");
        }
        m.inv.setItem(0, item(Material.BOOK, "&a&lDaily Word &f#" + number, "&7Guess the five-letter word", "&7in six tries. Same word for everyone.",
                "", "&a■ &7right spot  &e■ &7wrong spot  &8■ &7not in it", "", "&eClick for the rules"));
        if (!done) m.inv.setItem(9, item(Material.WRITABLE_BOOK, "&a&lType a guess", bedrock(p) ? "&7Click, then send a five-letter" : "&7Click to type it in a box.",
                bedrock(p) ? "&7word in chat. Only you see it." : "&7Only you see it.", "&8Or: /word <guess>"));
        else m.inv.setItem(9, item(gs.contains(word) ? Material.EMERALD : Material.REDSTONE, gs.contains(word) ? "&a&lSolved in " + gs.size() + "/" + TRIES : "&c&lOut of guesses",
                gs.contains(word) ? "&7Nice! Come back tomorrow." : "&7The word was &f" + word.toUpperCase(Locale.ROOT), "&7New word at midnight (Central)."));
        m.inv.setItem(18, item(Material.PAPER, "&fYour stats", "&7Played &f" + s.getInt("played") + " &8· &7Won &f" + s.getInt("won"),
                "&7Streak &f" + s.getInt("streak") + " &8· &7Best &f" + s.getInt("best"), "", "&eClick for details"));
        m.inv.setItem(27, item(Material.GOLDEN_HELMET, "&eToday's solvers", "&7Solved so far: &f" + stats.getInt("history." + day + ".solved"), "&eClick to list them"));
        m.inv.setItem(8, item(Material.OAK_SIGN, "&fLetters", kb1.toString().trim(), kb2.toString().trim(), kb3.toString().trim(), "",
                "&a■ &7right spot  &e■ &7in the word", "&8■ &7not in it  &f■ &7not tried"));
        m.inv.setItem(45, item(Material.ARROW, "&7« All minigames"));
        ItemStack f = item(Material.BLACK_STAINED_GLASS_PANE, " ");
        for (int i = 0; i < 54; i++) if (m.inv.getItem(i) == null) m.inv.setItem(i, f);
        p.openInventory(m.inv);
    }

    @EventHandler public void onDrag(InventoryDragEvent e) { if (e.getView().getTopInventory().getHolder() instanceof Menu) e.setCancelled(true); }

    @EventHandler public void onClick(InventoryClickEvent e) {
        if (!(e.getView().getTopInventory().getHolder() instanceof Menu)) return;
        e.setCancelled(true);
        if (!(e.getWhoClicked() instanceof Player p) || e.getClickedInventory() != e.getView().getTopInventory()) return;
        int slot = e.getRawSlot();
        Bukkit.getScheduler().runTask(this, () -> {   // next tick: never open or close menus inside a click event
            if (!p.isOnline()) return;
            switch (slot) {
                case 0 -> { p.closeInventory(); help(p); }
                case 9 -> {
                    if (finished(guesses(pl(p)))) return;
                    if (!bedrock(p)) { p.closeInventory(); dialog(p, null); return; }
                    typing.add(p.getUniqueId()); p.closeInventory();
                    msg(p, "&eType your guess in chat &7(five letters, only you see it). &8Changed your mind? Send &fcancel&8.");
                }
                case 18 -> { p.closeInventory(); showStats(p); }
                case 27 -> { p.closeInventory(); showTop(p); }
                case 45 -> { p.closeInventory(); p.performCommand("minigames"); }
                default -> {}
            }
        });
    }

    /** A guess typed in chat (after "Type a guess") never reaches chat; and today's word can't be posted by someone
     *  who has finished it. Runs first, so other chat plugins never see a cancelled message. */
    @EventHandler(priority = EventPriority.LOWEST)
    public void onChat(AsyncChatEvent e) {
        Player p = e.getPlayer();
        String text = PlainTextComponentSerializer.plainText().serialize(e.message()).trim();
        if (typing.remove(p.getUniqueId())) {
            e.setCancelled(true);
            Bukkit.getScheduler().runTask(this, () -> {
                if (!p.isOnline()) return;
                if (text.equalsIgnoreCase("cancel")) { open(p); return; }
                String err = guess(p, text);
                if (err != null) { msg(p, "&c" + err); typing.add(p.getUniqueId()); msg(p, "&7Try another word, or send &fcancel&7."); return; }
                open(p);
            });
            return;
        }
        String w = word;
        if (w == null || !Pattern.compile("(?i)\\b" + w + "\\b").matcher(text).find()) return;
        ConfigurationSection s = stats.getConfigurationSection("players." + p.getUniqueId());
        if (s != null && day.equals(s.getString("day")) && finished(s.getStringList("guesses"))) {
            e.setCancelled(true);
            msg(p, "&cNo spoilers! &7That's today's word, so your message wasn't sent.");
        }
    }

    @EventHandler public void onQuit(PlayerQuitEvent e) { typing.remove(e.getPlayer().getUniqueId()); }
}

package crispy.balatro;

import crispy.balatro.Rules.*;
import net.kyori.adventure.text.Component;
import net.kyori.adventure.text.format.TextDecoration;
import net.kyori.adventure.text.serializer.legacy.LegacyComponentSerializer;
import org.bukkit.Bukkit;
import org.bukkit.Material;
import org.bukkit.Sound;
import org.bukkit.command.Command;
import org.bukkit.command.CommandSender;
import org.bukkit.configuration.ConfigurationSection;
import org.bukkit.configuration.file.YamlConfiguration;
import org.bukkit.entity.Player;
import org.bukkit.event.EventHandler;
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
import org.bukkit.scheduler.BukkitTask;

import java.io.File;
import java.io.IOException;
import java.time.LocalDate;
import java.time.ZoneId;
import java.util.*;

/** Balatro Craft: a poker roguelike played in a chest menu. Ore suits, mobs as jokers, Minecraft bosses, a shop,
 *  saved runs, and a daily seeded run with a leaderboard. */
public class BalatroCraft extends JavaPlugin implements Listener {
    static final LegacyComponentSerializer AMP = LegacyComponentSerializer.legacyAmpersand();
    static final String PREFIX = "&8[&6Balatro&eCraft&8] &7";
    static final ZoneId ZONE = ZoneId.of("America/Chicago");

    final Map<UUID, Run> runs = new HashMap<>();
    final Set<UUID> animating = new HashSet<>();
    File runsDir, scoresFile; YamlConfiguration scores;

    @Override public void onEnable() {
        runsDir = new File(getDataFolder(), "runs"); runsDir.mkdirs();
        scoresFile = new File(getDataFolder(), "scores.yml"); scores = YamlConfiguration.loadConfiguration(scoresFile);
        getServer().getPluginManager().registerEvents(this, this);
    }
    @Override public void onDisable() { runs.forEach(this::saveRun); }

    static Component c(String s) { return AMP.deserialize(s).decoration(TextDecoration.ITALIC, false); }
    static void msg(CommandSender s, String m) { s.sendMessage(c(PREFIX + m)); }
    static String fmt(long n) { return String.format("%,d", n); }
    static String today() { return LocalDate.now(ZONE).toString(); }
    static long dailySeed(String day) { long h = 1125899906842597L; for (char ch : ("balatrocraft-" + day).toCharArray()) h = 31 * h + ch; return h ^ 0x5DEECE66DL; }

    // ------------------------------------------------------------------ storage
    File runFile(UUID u) { return new File(runsDir, u + ".yml"); }
    Run run(UUID u) {
        if (runs.containsKey(u)) return runs.get(u);
        File f = runFile(u);
        Run r = null;
        if (f.exists()) try { r = Run.load(YamlConfiguration.loadConfiguration(f)); } catch (RuntimeException e) { getLogger().warning("bad run file " + f + ": " + e); }
        if (r != null) runs.put(u, r);
        return r;
    }
    void saveRun(UUID u, Run r) { try { Run.toYaml(r).save(runFile(u)); } catch (IOException e) { getLogger().warning("save failed: " + e); } }
    void dropRun(UUID u) { runs.remove(u); runFile(u).delete(); }
    void saveScores() { try { scores.save(scoresFile); } catch (IOException e) { getLogger().warning("scores save failed: " + e); } }

    void record(Player p, Run r) {
        String id = p.getUniqueId().toString();
        update("alltime." + id, p.getName(), r);
        if (r.daily) update("daily." + r.day + "." + id, p.getName(), r);
        if (r.won && !scores.getBoolean("alltime." + id + ".won-" + r.seed)) {
            scores.set("alltime." + id + ".won-" + r.seed, true);
            scores.set("alltime." + id + ".wins", scores.getInt("alltime." + id + ".wins") + 1);
            Bukkit.broadcast(c(PREFIX + "&6" + p.getName() + " &ebeat the Ender Dragon in Balatro Craft" + (r.daily ? " &7(daily run)" : "") + "&e!"));
        }
        saveScores();
    }
    void update(String path, String name, Run r) {
        int prog = r.progress();
        scores.set(path + ".name", name);
        if (prog > scores.getInt(path + ".progress", -1)) scores.set(path + ".progress", prog);
        if (r.bestHand > scores.getLong(path + ".best")) scores.set(path + ".best", r.bestHand);
    }
    static String progressText(int prog) { return prog <= 0 ? "no blinds" : prog + " blind" + (prog == 1 ? "" : "s") + " &8(Ante " + (prog / 3 + 1) + ")"; }
    void showTop(CommandSender s, boolean daily) {
        ConfigurationSection sec = scores.getConfigurationSection(daily ? "daily." + today() : "alltime");
        msg(s, "&e&l" + (daily ? "Today's daily run" : "All-time best") + " &7- blinds cleared, best hand");
        if (sec == null || sec.getKeys(false).isEmpty()) { msg(s, "&7No runs yet."); return; }
        List<ConfigurationSection> rows = sec.getKeys(false).stream().map(sec::getConfigurationSection).filter(Objects::nonNull)
                .sorted(Comparator.comparingInt((ConfigurationSection x) -> -x.getInt("progress")).thenComparingLong(x -> -x.getLong("best"))).limit(10).toList();
        int i = 1;
        for (ConfigurationSection x : rows)
            s.sendMessage(c("&6#" + i++ + " &f" + x.getString("name") + " &7- " + progressText(x.getInt("progress")) + "&7, best hand &f" + fmt(x.getLong("best"))
                    + (x.getInt("wins") > 0 ? " &6★" + x.getInt("wins") : "")));
    }

    // ------------------------------------------------------------------ commands
    @Override
    public boolean onCommand(CommandSender s, Command cmd, String label, String[] a) {
        String sub = a.length > 0 ? a[0].toLowerCase(Locale.ROOT) : "";
        if (sub.equals("top")) { showTop(s, a.length > 1 && a[1].equalsIgnoreCase("daily")); return true; }
        if (sub.equals("reset") && a.length > 1 && s.hasPermission("balatrocraft.admin")) {
            Player t = Bukkit.getPlayerExact(a[1]);
            UUID u = t != null ? t.getUniqueId() : Bukkit.getOfflinePlayer(a[1]).getUniqueId();
            dropRun(u); msg(s, "Cleared the run of " + a[1] + "."); return true;
        }
        if (!(s instanceof Player p)) { msg(s, "/balatro top [daily] | reset <player>"); return true; }
        switch (sub) {
            case "help" -> help(p);
            case "daily" -> startDaily(p);
            case "new" -> startNew(p);
            default -> open(p);
        }
        return true;
    }
    void help(Player p) {
        String[] l = {
            "&6&lBalatro Craft &7- a poker roguelike",
            "&7Click cards to select up to 5, then &aPlay &7or &cDiscard&7. Score = &9Chips &7x &cMult&7.",
            "&7Beat each blind's target score with 4 hands and 3 discards. 3 blinds per ante; beat &5Ante 8 &7to win.",
            "&7Suits: &bDiamonds &cRedstone &aEmeralds &8Coal&7. Mobs are jokers: they change how hands score.",
            "&7Between blinds, spend &a$ &7in the shop: mobs, enchanted books (level up a hand) and tools (change cards).",
            "&7Boss blinds are Minecraft bosses with a curse. &f/balatro daily &7- same seed for everyone, once a day."};
        for (String s : l) p.sendMessage(c(s));
    }
    void startNew(Player p) {
        Run old = run(p.getUniqueId());
        if (old != null && old.state != Run.State.OVER) { msg(p, "&cYou already have a run going. Abandon it first (shift-click the barrier)."); open(p); return; }
        Run r = Run.create(new Random().nextLong(), false, "");
        runs.put(p.getUniqueId(), r); saveRun(p.getUniqueId(), r);
        open(p);
    }
    void startDaily(Player p) {
        String day = today();
        Run old = run(p.getUniqueId());
        if (old != null && old.state != Run.State.OVER) { msg(p, "&cFinish or abandon your current run first."); open(p); return; }
        List<String> played = scores.getStringList("daily-started." + day);
        if (played.contains(p.getUniqueId().toString())) { msg(p, "&cYou've already played today's daily run. New seed at midnight (Central)."); return; }
        played.add(p.getUniqueId().toString()); scores.set("daily-started." + day, played); saveScores();
        Run r = Run.create(dailySeed(day), true, day);
        runs.put(p.getUniqueId(), r); saveRun(p.getUniqueId(), r);
        msg(p, "&eDaily run for &f" + day + "&e: everyone gets the same seed. Good luck!");
        open(p);
    }

    // ------------------------------------------------------------------ GUI
    static final class Menu implements InventoryHolder {
        final String type; Inventory inv;
        Menu(String type) { this.type = type; }
        @Override public Inventory getInventory() { return inv; }
    }
    static ItemStack item(Material m, String name, String... lore) {
        ItemStack it = new ItemStack(m);
        ItemMeta meta = it.getItemMeta();
        meta.displayName(c(name));
        if (lore.length > 0) meta.lore(Arrays.stream(lore).map(BalatroCraft::c).toList());
        meta.addItemFlags(ItemFlag.values());
        it.setItemMeta(meta);
        return it;
    }
    static ItemStack glint(ItemStack it) { ItemMeta m = it.getItemMeta(); m.setEnchantmentGlintOverride(true); it.setItemMeta(m); return it; }
    static ItemStack amount(ItemStack it, int n) { it.setAmount(Math.max(1, Math.min(64, n))); return it; }

    Inventory screen(Player p, String type, int size, String title) {
        Inventory top = p.getOpenInventory().getTopInventory();
        if (top.getHolder() instanceof Menu m && m.type.equals(type) && top.getSize() == size) { top.clear(); return top; }
        Menu m = new Menu(type); m.inv = Bukkit.createInventory(m, size, c(title));
        p.openInventory(m.inv);
        return m.inv;
    }

    void open(Player p) {
        Run r = run(p.getUniqueId());
        if (r == null) mainMenu(p);
        else switch (r.state) { case ROUND -> table(p, r); case SHOP -> shop(p, r); case OVER -> over(p, r); }
    }

    void fill(Inventory inv, Material m, int from, int to) { ItemStack f = item(m, " "); for (int i = from; i <= to; i++) if (inv.getItem(i) == null) inv.setItem(i, f); }

    void mainMenu(Player p) {
        Inventory inv = screen(p, "menu", 27, "&8Balatro Craft");
        inv.setItem(11, glint(item(Material.EMERALD, "&a&lNew Run", "&7A fresh random deck.", "&7Beat Ante 8 to win.")));
        inv.setItem(13, item(Material.BOOK, "&eHow to play", "&7Click for the rules in chat."));
        boolean dailyDone = scores.getStringList("daily-started." + today()).contains(p.getUniqueId().toString());
        inv.setItem(15, item(Material.CLOCK, "&6&lDaily Run", "&7Same seed for everyone today.", dailyDone ? "&cAlready played today" : "&aOne attempt per day"));
        inv.setItem(22, item(Material.GOLDEN_HELMET, "&eLeaderboard", "&7Click: today's daily", "&7Shift-click: all-time"));
        fill(inv, Material.BLACK_STAINED_GLASS_PANE, 0, 26);
    }

    ItemStack cardItem(Run r, Card cd) {
        if (r.faceDown(cd)) return item(Material.GRAY_DYE, "&8? ? ?", "&7Face down (the Warden's Darkness)");
        List<String> lore = new ArrayList<>();
        lore.add("&9+" + (Rules.rankChips(cd.rank) + cd.chips) + " Chips" + (cd.chips > 0 ? " &8(+" + cd.chips + " sharpened)" : ""));
        if (cd.mult > 0) lore.add("&c+" + cd.mult + " Mult");
        if (r.debuffed(cd)) lore.add("&cDebuffed by the boss: scores nothing");
        ItemStack it = item(Rules.suitMaterial(cd.suit), Rules.suitColor(cd.suit) + "&l" + Rules.rankName(cd.rank) + " " + Rules.suitSymbol(cd.suit)
                + " &r" + Rules.suitColor(cd.suit) + Rules.rankLong(cd.rank) + " of " + Rules.suitName(cd.suit), lore.toArray(String[]::new));
        amount(it, cd.rank <= 10 ? cd.rank : 1);
        if (cd.chips > 0 || cd.mult > 0) glint(it);
        return it;
    }
    ItemStack mobItem(Mob m, String extra) {
        List<String> l = new ArrayList<>(List.of(m.desc));
        if (extra != null) l.add(extra);
        return item(Rules.material(m.icon), "&e" + m.title, l.toArray(String[]::new));
    }
    ItemStack toolItem(Tool t, String extra) {
        List<String> l = new ArrayList<>(List.of(t.desc)); if (extra != null) l.add(extra);
        return item(Rules.material(t.icon), "&d" + t.title, l.toArray(String[]::new));
    }
    ItemStack bossItem(Run r) {
        Boss b = r.blind == 2 ? r.boss : null;
        String title = "&fAnte " + r.ante + " &7- " + (b != null ? "&c" + b.title : "&f" + Rules.blindName(r.blind));
        if (b != null) return item(Rules.material(b.icon), title, "&7" + b.effect, "&8Reward: $" + Rules.blindReward(r.blind));
        return item(r.blind == 0 ? Material.WHITE_BANNER : Material.YELLOW_BANNER, title, "&7Next boss: &c" + r.boss.title, "&8" + r.boss.effect, "&8Reward: $" + Rules.blindReward(r.blind));
    }

    void table(Player p, Run r) {
        Inventory inv = screen(p, "table", 54, "&8Balatro Craft &7- Ante " + r.ante + (r.daily ? " &6(daily)" : ""));
        inv.setItem(0, bossItem(r));
        inv.setItem(1, item(Material.TARGET, "&fScore at least &c" + fmt(r.target)));
        inv.setItem(2, item(Material.GLOWSTONE_DUST, "&eRound score: &f" + fmt(r.roundScore), "&7Last hand: &f" + (r.lastHand.isEmpty() ? "-" : r.lastHand)));
        inv.setItem(3, amount(item(Material.LIME_DYE, "&aHands left: &f" + r.handsLeft), r.handsLeft));
        inv.setItem(4, amount(item(Material.RED_DYE, "&cDiscards left: &f" + r.discardsLeft), r.discardsLeft));
        inv.setItem(5, amount(item(Material.EMERALD, "&aMoney: $" + r.money, "&7+$1 interest per $5 (max $5)"), r.money));
        inv.setItem(6, item(Material.BOOK, "&fDeck: &7" + r.drawPile.size() + " left of " + r.deck.size(), "&7Click to list what's left"));
        for (int i = 0; i < Run.TOOL_SLOTS; i++)
            inv.setItem(7 + i, i < r.tools.size() ? toolItem(r.tools.get(i), "&aClick to use on the selected cards") : item(Material.LIGHT_GRAY_STAINED_GLASS_PANE, "&7Empty item slot"));
        for (int i = 0; i < Run.MOB_SLOTS; i++)
            inv.setItem(9 + i, i < r.mobs.size() ? mobItem(r.mobs.get(i), r.mobs.get(i) == Mob.ALLAY && r.effective(i) != null ? "&8(copying " + r.effective(i).title + ")" : null)
                    : item(Material.GRAY_STAINED_GLASS_PANE, "&7Empty mob slot"));
        inv.setItem(15, item(Material.KNOWLEDGE_BOOK, "&dHand levels", "&7Click to list them in chat"));
        inv.setItem(17, item(Material.PAPER, "&fRun info", "&7Best hand: &f" + fmt(r.bestHand), "&7Hands played: &f" + r.handsPlayed, r.daily ? "&6Daily run " + r.day : "&7Seed: &8" + Long.toHexString(r.seed)));
        for (int i = 0; i < r.hand.size() && i < 8; i++) {
            Card cd = r.card(r.hand.get(i));
            inv.setItem(r.selected.contains(cd.id) ? 27 + i : 36 + i, cardItem(r, cd));
        }
        inv.setItem(44, item(Material.HOPPER, "&fSort by " + (r.sortBySuit ? "rank" : "suit")));
        List<Card> sel = r.selectedCards();
        String preview = "&7Select up to " + r.maxPlay() + " cards";
        if (!sel.isEmpty()) { Eval ev = Rules.evaluate(sel); int lv = r.level(ev.hand()); preview = "&f" + ev.hand().title + " &7lvl " + lv + ": &9" + ev.hand().chipsAt(lv) + " &7x &c" + ev.hand().multAt(lv); }
        inv.setItem(45, item(Material.LIME_CONCRETE, "&a&lPlay hand", preview));
        inv.setItem(47, item(Material.RED_CONCRETE, "&c&lDiscard", "&7" + r.discardsLeft + " discard(s) left"));
        inv.setItem(53, item(Material.BARRIER, "&cAbandon run", "&7Shift-click to give up"));
        fill(inv, Material.BLACK_STAINED_GLASS_PANE, 0, 17);
        fill(inv, Material.GREEN_STAINED_GLASS_PANE, 18, 44);
        fill(inv, Material.BLACK_STAINED_GLASS_PANE, 45, 53);
    }

    void shop(Player p, Run r) {
        Inventory inv = screen(p, "shop", 54, "&8Balatro Craft &7- Shop");
        inv.setItem(0, item(Material.CHEST, "&6&lShop", "&7Ante " + r.ante + ", next: " + Rules.blindName(r.blind)));
        inv.setItem(4, amount(item(Material.EMERALD, "&aMoney: $" + r.money), r.money));
        inv.setItem(8, bossItem(r));
        for (int i = 0; i < r.offerMobs.size(); i++) {
            Mob m = r.offerMobs.get(i);
            inv.setItem(10 + 2 * i, m == null ? item(Material.LIGHT_GRAY_STAINED_GLASS_PANE, "&7Sold") : mobItem(m, "&aBuy: $" + m.price));
        }
        for (int i = 0; i < r.offerItems.size(); i++) {
            String o = r.offerItems.get(i); ItemStack it;
            if (o == null) it = item(Material.LIGHT_GRAY_STAINED_GLASS_PANE, "&7Sold");
            else if (o.startsWith("BOOK:")) {
                Hand h = Hand.valueOf(o.substring(5)); int lv = r.level(h);
                it = glint(item(Material.ENCHANTED_BOOK, "&dBook of " + h.title, "&7Level up &f" + h.title + " &7to &f" + (lv + 1),
                        "&9" + h.chipsAt(lv) + " &7x &c" + h.multAt(lv) + " &7-> &9" + h.chipsAt(lv + 1) + " &7x &c" + h.multAt(lv + 1), "&aBuy: $" + Rules.BOOK_PRICE));
            } else { Tool t = Tool.valueOf(o.substring(5)); it = toolItem(t, "&aBuy: $" + t.price); }
            inv.setItem(14 + 2 * i, it);
        }
        for (int i = 0; i < Run.MOB_SLOTS; i++)
            inv.setItem(28 + i, i < r.mobs.size() ? mobItem(r.mobs.get(i), "&cShift-click to sell for $" + r.mobs.get(i).sell()) : item(Material.GRAY_STAINED_GLASS_PANE, "&7Empty mob slot"));
        for (int i = 0; i < Run.TOOL_SLOTS; i++)
            inv.setItem(34 + i, i < r.tools.size() ? toolItem(r.tools.get(i), "&7Use it during a round") : item(Material.LIGHT_GRAY_STAINED_GLASS_PANE, "&7Empty item slot"));
        inv.setItem(45, item(Material.SUNFLOWER, "&eReroll shop", "&7Cost: &a$" + r.rerollCost));
        inv.setItem(49, glint(item(Material.LIME_CONCRETE, "&a&lNext round", "&7" + Rules.blindName(r.blind) + ": score &c" + fmt(Math.round(Rules.anteBase(r.ante) * (r.blind == 0 ? 1 : r.blind == 1 ? 1.5 : r.boss == Boss.ENDER_DRAGON ? 4 : 2))))));
        inv.setItem(53, item(Material.BARRIER, "&cAbandon run", "&7Shift-click to give up"));
        fill(inv, Material.BLACK_STAINED_GLASS_PANE, 0, 53);
    }

    void over(Player p, Run r) {
        Inventory inv = screen(p, "over", 27, "&8Balatro Craft &7- Run over");
        inv.setItem(13, item(r.won ? Material.DRAGON_HEAD : Material.SKELETON_SKULL, r.won ? "&6&lYou won!" : "&c&lGame over",
                "&7Reached &fAnte " + r.ante + " " + Rules.blindName(r.blind), "&7Blinds cleared: &f" + r.progress(), "&7Best hand: &f" + fmt(r.bestHand),
                "&7Hands played: &f" + r.handsPlayed, r.daily ? "&6Daily run " + r.day : "&8Seed " + Long.toHexString(r.seed)));
        inv.setItem(11, glint(item(Material.EMERALD, "&a&lNew Run")));
        inv.setItem(15, item(Material.CLOCK, "&6&lDaily Run"));
        inv.setItem(22, item(Material.GOLDEN_HELMET, "&eLeaderboard", "&7Click: today's daily", "&7Shift-click: all-time"));
        fill(inv, Material.BLACK_STAINED_GLASS_PANE, 0, 26);
    }

    // ------------------------------------------------------------------ clicks
    @EventHandler public void onDrag(InventoryDragEvent e) { if (e.getView().getTopInventory().getHolder() instanceof Menu) e.setCancelled(true); }
    @EventHandler public void onQuit(PlayerQuitEvent e) {
        UUID u = e.getPlayer().getUniqueId(); animating.remove(u);
        Run r = runs.remove(u); if (r != null) saveRun(u, r);
    }

    @EventHandler
    public void onClick(InventoryClickEvent e) {
        if (!(e.getView().getTopInventory().getHolder() instanceof Menu m)) return;
        e.setCancelled(true);
        if (!(e.getWhoClicked() instanceof Player p) || e.getClickedInventory() != e.getView().getTopInventory()) return;
        if (animating.contains(p.getUniqueId())) return;
        int s = e.getRawSlot(); boolean shift = e.isShiftClick();
        Run r = run(p.getUniqueId());
        switch (m.type) {
            case "menu", "over" -> {
                if (s == 11) { if (r != null && r.state == Run.State.OVER) dropRun(p.getUniqueId()); startNew(p); }
                else if (s == 15) { if (r != null && r.state == Run.State.OVER) dropRun(p.getUniqueId()); startDaily(p); }
                else if (s == 13 && m.type.equals("menu")) help(p);
                else if (s == 22) showTop(p, !shift);
            }
            case "table" -> { if (r != null) tableClick(p, r, s, shift); }
            case "shop" -> { if (r != null) shopClick(p, r, s, shift); }
            default -> {}
        }
    }

    void after(Player p, Run r, String err) {
        if (err != null) { msg(p, err); p.playSound(p.getLocation(), Sound.BLOCK_NOTE_BLOCK_BASS, 0.6f, 0.8f); }
        for (String n : r.news) msg(p, n);
        r.news.clear();
        saveRun(p.getUniqueId(), r);
        open(p);
    }

    void tableClick(Player p, Run r, int s, boolean shift) {
        if (r.state != Run.State.ROUND) { open(p); return; }
        if ((s >= 36 && s <= 43) || (s >= 27 && s <= 34)) {
            int i = s >= 36 ? s - 36 : s - 27;
            if (i < r.hand.size()) { after(p, r, r.toggle(r.hand.get(i))); p.playSound(p.getLocation(), Sound.UI_BUTTON_CLICK, 0.4f, 1.8f); }
        } else if (s == 44) { r.sortBySuit = !r.sortBySuit; r.sortHand(); after(p, r, null); }
        else if (s == 47) { String err = r.discard(); if (err == null) p.playSound(p.getLocation(), Sound.ITEM_BOOK_PAGE_TURN, 1f, 1f); after(p, r, err); }
        else if (s == 7 || s == 8) after(p, r, r.useTool(s - 7));
        else if (s == 6) {
            Map<Character, List<String>> by = new TreeMap<>(Comparator.comparingInt((Character ch) -> Rules.SUITS.indexOf(ch)));
            for (int id : r.drawPile) { Card cd = r.card(id); by.computeIfAbsent(cd.suit, k -> new ArrayList<>()).add(Rules.rankName(cd.rank)); }
            msg(p, "&fCards left in your deck (" + r.drawPile.size() + "):");
            by.forEach((suit, l) -> p.sendMessage(c(Rules.suitColor(suit) + Rules.suitSymbol(suit) + " " + Rules.suitName(suit) + ": &f" + String.join(" ", l))));
        } else if (s == 15) {
            msg(p, "&dHand levels &7(chips x mult):");
            for (Hand h : Hand.values()) p.sendMessage(c("&7" + h.title + " &8lvl " + r.level(h) + ": &9" + h.chipsAt(r.level(h)) + " &7x &c" + h.multAt(r.level(h))));
        } else if (s == 53 && shift) { r.state = Run.State.OVER; record(p, r); msg(p, "&7Run abandoned."); after(p, r, null); }
        else if (s == 45) playHand(p, r);
    }

    void shopClick(Player p, Run r, int s, boolean shift) {
        if (r.state != Run.State.SHOP) { open(p); return; }
        String err = null; boolean buy = false;
        if (s == 10 || s == 12) { err = r.buyMob((s - 10) / 2); buy = err == null; }
        else if (s == 14 || s == 16) { err = r.buyItem((s - 14) / 2); buy = err == null; }
        else if (s >= 28 && s <= 32 && shift) err = r.sellMob(s - 28);
        else if (s == 45) err = r.reroll();
        else if (s == 49) { r.nextRound(); p.playSound(p.getLocation(), Sound.BLOCK_CHEST_OPEN, 0.6f, 1.2f); }
        else if (s == 53 && shift) { r.state = Run.State.OVER; record(p, r); msg(p, "&7Run abandoned."); }
        else return;
        if (buy) p.playSound(p.getLocation(), Sound.ENTITY_VILLAGER_YES, 0.6f, 1.1f);
        after(p, r, err);
    }

    // ------------------------------------------------------------------ playing a hand (scored at once, then animated)
    void playHand(Player p, Run r) {
        long before = r.roundScore;
        Object o = r.play();
        if (o instanceof String err) { after(p, r, err); return; }
        if (!(o instanceof Run.Result res)) return;
        saveRun(p.getUniqueId(), r);
        record(p, r);
        Inventory inv = p.getOpenInventory().getTopInventory();
        if (!(inv.getHolder() instanceof Menu m) || !m.type.equals("table")) { after(p, r, null); return; }
        for (int i = 27; i <= 34; i++) inv.setItem(i, item(Material.GREEN_STAINED_GLASS_PANE, " "));
        for (int i = 0; i < res.played().size(); i++) inv.setItem(20 + i, cardItem(r, res.played().get(i)));
        animating.add(p.getUniqueId());
        final int[] k = {0};
        final BukkitTask[] task = new BukkitTask[1];
        task[0] = Bukkit.getScheduler().runTaskTimer(this, () -> {
            if (!p.isOnline() || !animating.contains(p.getUniqueId())) { task[0].cancel(); return; }
            if (k[0] < res.steps().size()) {
                Run.Step st = res.steps().get(k[0]);
                p.sendActionBar(c("&9" + fmt(st.chips()) + " &7x &c" + trim(st.mult()) + "   &7" + st.text()));
                p.playSound(p.getLocation(), Sound.BLOCK_NOTE_BLOCK_PLING, 0.5f, (float) Math.min(2.0, 0.7 + k[0] * 0.08));
                if (st.kind() == 0 && st.index() >= 0) { ItemStack it = inv.getItem(20 + st.index()); if (it != null) inv.setItem(20 + st.index(), glint(it.clone())); }
                if (st.kind() == 1) { ItemStack it = inv.getItem(9 + st.index()); if (it != null) inv.setItem(9 + st.index(), glint(it.clone())); }
                k[0]++;
                return;
            }
            if (k[0] == res.steps().size()) {
                p.sendActionBar(c("&f&l" + res.eval().hand().title + "  &e&l" + fmt(res.total()) + " " + res.note()));
                inv.setItem(2, item(Material.GLOWSTONE_DUST, "&eRound score: &f" + fmt(before + res.total())));
                p.playSound(p.getLocation(), res.total() >= 1000 ? Sound.ENTITY_PLAYER_LEVELUP : Sound.ENTITY_EXPERIENCE_ORB_PICKUP, 0.8f, 1f);
            }
            if (++k[0] >= res.steps().size() + 4) {
                task[0].cancel(); animating.remove(p.getUniqueId());
                if (r.state == Run.State.SHOP) p.playSound(p.getLocation(), Sound.UI_TOAST_CHALLENGE_COMPLETE, 0.7f, 1.2f);
                if (r.state == Run.State.OVER) p.playSound(p.getLocation(), Sound.ENTITY_WITHER_DEATH, 0.4f, 1.2f);
                if (p.getOpenInventory().getTopInventory().getHolder() instanceof Menu) after(p, r, null);
                else { for (String n : r.news) msg(p, n); r.news.clear(); saveRun(p.getUniqueId(), r); }
            }
        }, 4L, 7L);
    }
    static String trim(double d) { return d == Math.floor(d) ? fmt((long) d) : String.format("%.1f", d); }
}

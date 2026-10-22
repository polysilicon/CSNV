package crispy.uno;

import crispy.uno.Game.*;
import net.kyori.adventure.text.Component;
import net.kyori.adventure.text.event.ClickEvent;
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
import org.bukkit.event.inventory.InventoryType;
import org.bukkit.event.player.PlayerQuitEvent;
import org.bukkit.inventory.Inventory;
import org.bukkit.inventory.InventoryHolder;
import org.bukkit.inventory.ItemFlag;
import org.bukkit.inventory.ItemStack;
import org.bukkit.inventory.meta.ItemMeta;
import org.bukkit.inventory.meta.SkullMeta;
import org.bukkit.plugin.java.JavaPlugin;

import java.io.File;
import java.io.IOException;
import java.util.*;

/** UNO in the lobby: tables of 2-8 players (bots can fill seats), played in a chest menu. Game.java has the rules. */
public class UnoCraft extends JavaPlugin implements Listener {
    static final LegacyComponentSerializer AMP = LegacyComponentSerializer.legacyAmpersand();
    static final String PREFIX = "&8[&c&lU&e&lN&a&lO&8] &7";
    static final int MAX_SEATS = 8, TURN_SECONDS = 30, KICK_AFTER_TIMEOUTS = 3, HAND_SLOTS = 27;

    static final class Table {
        final int id; String host; final Game g = new Game(new Random());
        int lastTurn = -1, ticksLeft, botWait, bots;
        final Map<String, Integer> timeouts = new HashMap<>(), page = new HashMap<>();
        Table(int id, String host) { this.id = id; this.host = host; }
        Seat seat(UUID u) { for (Seat s : g.seats) if (s.id.equals(u.toString())) return s; return null; }
        long humans() { return g.seats.stream().filter(s -> !s.bot).count(); }
    }
    static final class Menu implements InventoryHolder {
        final String kind; final Table t; final Map<Integer, String> actions = new HashMap<>(); Inventory inv;
        Menu(String kind, Table t) { this.kind = kind; this.t = t; }
        @Override public Inventory getInventory() { return inv; }
    }

    final Map<Integer, Table> tables = new LinkedHashMap<>();
    final Map<UUID, Table> byPlayer = new HashMap<>();
    int nextId = 1;
    File statsFile; YamlConfiguration stats;

    @Override public void onEnable() {
        getDataFolder().mkdirs();
        statsFile = new File(getDataFolder(), "stats.yml"); stats = YamlConfiguration.loadConfiguration(statsFile);
        getServer().getPluginManager().registerEvents(this, this);
        Bukkit.getScheduler().runTaskTimer(this, this::tick, 10, 10);
    }

    static Component c(String s) { return AMP.deserialize(s).decoration(TextDecoration.ITALIC, false); }
    static void msg(CommandSender s, String m) { s.sendMessage(c(PREFIX + m)); }
    void tell(Table t, String m) { for (Seat s : t.g.seats) if (!s.bot) { Player p = player(s); if (p != null) msg(p, m); } }
    static Player player(Seat s) { return s.bot ? null : Bukkit.getPlayer(UUID.fromString(s.id)); }

    // ------------------------------------------------------------------ commands
    @Override public boolean onCommand(CommandSender s, Command cmd, String label, String[] a) {
        String sub = a.length > 0 ? a[0].toLowerCase(Locale.ROOT) : "";
        if (sub.equals("top")) { showTop(s); return true; }
        if (sub.equals("help")) { help(s); return true; }
        if (!(s instanceof Player p)) { msg(s, "/uno top"); return true; }
        // next tick: the hub selector runs this from inside an inventory click
        Bukkit.getScheduler().runTask(this, () -> {
            if (!p.isOnline()) return;
            switch (sub) {
                case "leave" -> leave(p, true);
                case "join" -> { if (a.length > 1) try { join(p, Integer.parseInt(a[1])); } catch (NumberFormatException e) { msg(p, "&cNo such table."); } }
                case "create", "new" -> create(p);
                default -> open(p);
            }
        });
        return true;
    }
    void help(CommandSender s) {
        for (String l : new String[]{
                "&c&lU&e&lN&a&lO &7- match the top card's &fcolour&7, &fnumber &7or &fsymbol&7. First to empty their hand wins.",
                "&7Click a glowing card to play it. Can't play? Click &fDraw&7: play the card you drew or &fPass&7.",
                "&7Skip, Reverse, Draw Two, Wild (pick a colour) and Wild Draw Four. Reverse with 2 players = Skip.",
                "&7Down to 2 cards? Click &cUNO! &7before you play, or draw 2 cards as a penalty.",
                "&7" + TURN_SECONDS + " s per turn. The host can add bots. &f/uno &7menu, &f/uno leave&7, &f/uno top&7."}) s.sendMessage(c(l));
    }
    void showTop(CommandSender s) {
        msg(s, "&e&lUNO wins");
        ConfigurationSection sec = stats.getConfigurationSection("players");
        if (sec == null) { msg(s, "&7No games yet."); return; }
        List<ConfigurationSection> rows = sec.getKeys(false).stream().map(sec::getConfigurationSection).filter(Objects::nonNull)
                .sorted(Comparator.comparingInt((ConfigurationSection x) -> -x.getInt("wins")).thenComparingInt(x -> x.getInt("played"))).limit(10).toList();
        int i = 1;
        for (ConfigurationSection x : rows) s.sendMessage(c("&6#" + i++ + " &f" + x.getString("name") + " &7- &a" + x.getInt("wins") + " wins &8(" + x.getInt("played") + " games)"));
    }

    // ------------------------------------------------------------------ tables
    void create(Player p) {
        if (byPlayer.containsKey(p.getUniqueId())) { open(p); return; }
        Table t = new Table(nextId++, p.getUniqueId().toString());
        tables.put(t.id, t);
        sit(p, t);
        Component invite = c(PREFIX + "&f" + p.getName() + " &7opened UNO table &f#" + t.id + "&7. ")
                .append(c("&a&n[Click to join]").clickEvent(ClickEvent.runCommand("/uno join " + t.id)));
        for (Player o : Bukkit.getOnlinePlayers()) if (o != p) o.sendMessage(invite);
        room(p, t);
    }
    void join(Player p, int id) {
        Table t = tables.get(id);
        if (byPlayer.get(p.getUniqueId()) == t && t != null) { open(p); return; }
        if (byPlayer.containsKey(p.getUniqueId())) { msg(p, "&cYou're already at a table. &7/uno leave first."); return; }
        if (t == null) { msg(p, "&cThat table is gone."); return; }
        if (t.g.started) { msg(p, "&cThat game has already started."); return; }
        if (t.g.seats.size() >= MAX_SEATS) { msg(p, "&cThat table is full."); return; }
        sit(p, t);
        tell(t, "&f" + p.getName() + " &7joined the table.");
        refresh(t);
        room(p, t);
    }
    void sit(Player p, Table t) { t.g.seats.add(new Seat(p.getUniqueId().toString(), p.getName(), false)); byPlayer.put(p.getUniqueId(), t); }

    void leave(Player p, boolean say) {
        Table t = byPlayer.remove(p.getUniqueId());
        if (t == null) { if (say) msg(p, "&7You're not at an UNO table."); return; }
        Seat s = t.seat(p.getUniqueId());
        if (p.getOpenInventory().getTopInventory().getHolder() instanceof Menu) p.closeInventory();
        if (s != null) t.g.remove(s);
        if (say) msg(p, "&7You left the table.");
        if (!t.g.started) {
            if (t.humans() == 0) { tables.remove(t.id); return; }
            if (t.host.equals(p.getUniqueId().toString()))   // hand the table to the next human
                t.g.seats.stream().filter(x -> !x.bot).findFirst().ifPresent(x -> { t.host = x.id; tell(t, "&f" + x.name + " &7is the host now."); });
            tell(t, "&f" + p.getName() + " &7left the table.");
            refresh(t);
            return;
        }
        if (t.humans() == 0 && !t.g.over) { t.g.over = true; t.g.winner = null; }   // only bots left: no one to play for
        flush(t);
    }

    void start(Player p, Table t) {
        if (!t.host.equals(p.getUniqueId().toString())) { msg(p, "&cOnly the host can start."); return; }
        if (t.g.seats.size() < 2) { msg(p, "&cYou need at least 2 players: add a bot or wait for someone to join."); return; }
        Collections.shuffle(t.g.seats);
        t.g.start();
        tell(t, "&aThe game starts! &7Seats: &f" + String.join("&7, &f", t.g.seats.stream().map(x -> x.name).toList()));
        for (Seat s : t.g.seats) { Player o = player(s); if (o != null) { o.playSound(o.getLocation(), Sound.BLOCK_NOTE_BLOCK_PLING, 1, 1.2f); game(o, t); } }
        flush(t);
    }

    /** Called after every change: send the log, handle the end of the game, redraw the menus, prompt the next player. */
    void flush(Table t) {
        Game g = t.g;
        for (String l : g.log) tell(t, l);
        g.log.clear();
        if (g.over) { end(t); return; }
        if (g.turn != t.lastTurn) {
            t.lastTurn = g.turn; t.ticksLeft = TURN_SECONDS * 20; t.botWait = 0;
            Seat s = g.current();
            Player p = player(s);
            if (p != null) {
                p.sendActionBar(c("&a&lYour turn! &7Top card: " + g.top().text() + (g.top().wild() ? " &7(" + g.color.text() + "&7)" : "")));
                p.playSound(p.getLocation(), Sound.BLOCK_NOTE_BLOCK_BELL, 0.8f, 1.4f);
                // open the table for them unless they're looking at another menu
                if (p.getOpenInventory().getTopInventory().getType() == InventoryType.CRAFTING) game(p, t);
            }
        }
        refresh(t);
    }

    void end(Table t) {
        Game g = t.g;
        tables.remove(t.id);
        Seat w = g.winner;
        for (Seat s : g.seats) {
            if (s.bot) continue;
            UUID u = UUID.fromString(s.id);
            byPlayer.remove(u);
            String path = "players." + s.id;
            stats.set(path + ".name", s.name);
            stats.set(path + ".played", stats.getInt(path + ".played") + 1);
            if (s == w) stats.set(path + ".wins", stats.getInt(path + ".wins") + 1);
            Player p = Bukkit.getPlayer(u);
            if (p != null) {
                if (p.getOpenInventory().getTopInventory().getHolder() instanceof Menu) p.closeInventory();
                p.playSound(p.getLocation(), s == w ? Sound.UI_TOAST_CHALLENGE_COMPLETE : Sound.ENTITY_VILLAGER_NO, 0.8f, 1f);
                msg(p, s == w ? "&6&lYou won! &7Play again with &f/uno&7." : "&7Game over. Play again with &f/uno&7.");
            }
        }
        try { stats.save(statsFile); } catch (IOException e) { getLogger().warning("stats save failed: " + e); }
        if (w != null && !w.bot && g.seats.size() >= 2)
            Bukkit.broadcast(c(PREFIX + "&f" + w.name + " &7won a game of UNO against " + (g.seats.size() - 1) + " other" + (g.seats.size() > 2 ? "s" : "") + "! &8(/uno to play)"));
    }

    void tick() {   // every 10 ticks
        for (Table t : new ArrayList<>(tables.values())) {
            Game g = t.g;
            if (!g.started || g.over) continue;
            Seat s = g.current();
            if (s.bot) {
                if (++t.botWait >= 3) { g.botTurn(); flush(t); }
                continue;
            }
            t.ticksLeft -= 10;
            Player p = player(s);
            if (p != null && t.ticksLeft > 0 && t.ticksLeft <= 200 && t.ticksLeft % 100 == 0)
                p.sendActionBar(c("&c" + t.ticksLeft / 20 + " seconds left in your turn!"));
            if (t.ticksLeft <= 0) {
                int n = t.timeouts.merge(s.id, 1, Integer::sum);
                tell(t, "&f" + s.name + " &7ran out of time.");
                if (n >= KICK_AFTER_TIMEOUTS && p != null) { msg(p, "&cRemoved from the table after " + n + " missed turns."); leave(p, false); continue; }
                g.timeout();
                flush(t);
            }
        }
    }

    // ------------------------------------------------------------------ menus
    static ItemStack item(Material m, String name, String... lore) {
        ItemStack it = new ItemStack(m);
        ItemMeta meta = it.getItemMeta();
        meta.displayName(c(name));
        if (lore.length > 0) meta.lore(Arrays.stream(lore).map(UnoCraft::c).toList());
        meta.addItemFlags(ItemFlag.values());
        it.setItemMeta(meta);
        return it;
    }
    static ItemStack glint(ItemStack it) { ItemMeta m = it.getItemMeta(); m.setEnchantmentGlintOverride(true); it.setItemMeta(m); return it; }
    static void fill(Inventory inv, Material m, int from, int to) { ItemStack f = item(m, " "); for (int i = from; i <= to; i++) if (inv.getItem(i) == null) inv.setItem(i, f); }
    static Material mat(String name) { return Material.valueOf(name); }
    static String dye(Col c) { return switch (c) { case RED -> "RED"; case YELLOW -> "YELLOW"; case GREEN -> "LIME"; case BLUE -> "BLUE"; case WILD -> "BLACK"; }; }

    /** Card look: number cards are concrete (stack size = number, 0 is concrete powder), Skip stained glass,
     *  Reverse glazed terracotta, Draw Two a shulker box, Wild a nether star, Wild Draw Four an end crystal. */
    static ItemStack cardItem(Card cd, String... lore) {
        String d = dye(cd.col);
        ItemStack it = switch (cd.kind) {
            case NUM -> item(mat(d + (cd.num == 0 ? "_CONCRETE_POWDER" : "_CONCRETE")), "&l" + cd.text(), lore);
            case SKIP -> item(mat(d + "_STAINED_GLASS"), "&l" + cd.text(), lore);
            case REVERSE -> item(mat(d + "_GLAZED_TERRACOTTA"), "&l" + cd.text(), lore);
            case DRAW2 -> item(mat(d + "_SHULKER_BOX"), "&l" + cd.text(), lore);
            case WILD -> item(Material.NETHER_STAR, "&d&lW&c&li&e&ll&a&ld", lore);
            case WILD4 -> item(Material.END_CRYSTAL, "&d&lWild &c&lDraw &e&lFour", lore);
        };
        it.setAmount(cd.kind == Kind.NUM ? Math.max(1, cd.num) : cd.kind == Kind.DRAW2 ? 2 : cd.kind == Kind.WILD4 ? 4 : 1);
        return it;
    }
    ItemStack seatItem(Table t, Seat s, boolean turn) {
        ItemStack it;
        if (s.bot) it = item(Material.SKELETON_SKULL, (turn ? "&a▶ " : "&f") + s.name + " &8(bot)");
        else {
            it = item(Material.PLAYER_HEAD, (turn ? "&a▶ " : "&f") + s.name + (s.id.equals(t.host) && !t.g.started ? " &6(host)" : ""));
            SkullMeta m = (SkullMeta) it.getItemMeta();
            Player p = player(s);
            if (p != null) m.setOwningPlayer(p);
            it.setItemMeta(m);
        }
        if (t.g.started) {
            ItemMeta m = it.getItemMeta();
            m.lore(List.of(c("&7Cards: &f" + s.hand.size() + (s.hand.size() == 1 ? " &c&lUNO!" : "")), c(turn ? "&aPlaying now" : "&8Waiting")));
            it.setItemMeta(m);
            it.setAmount(Math.max(1, Math.min(64, s.hand.size())));
            if (turn) glint(it);
        }
        return it;
    }

    Menu menu(String kind, Table t, int rows, String title) {
        Menu m = new Menu(kind, t);
        m.inv = Bukkit.createInventory(m, rows * 9, c(title));
        return m;
    }
    void put(Menu m, int slot, ItemStack it, String action) { m.inv.setItem(slot, it); if (action != null) m.actions.put(slot, action); }

    void open(Player p) {
        Table t = byPlayer.get(p.getUniqueId());
        if (t == null) browse(p);
        else if (!t.g.started) room(p, t);
        else game(p, t);
    }

    void browse(Player p) {
        Menu m = menu("browse", null, 3, "&8UNO tables");
        put(m, 4, item(Material.BOOK, "&c&lU&e&lN&a&lO", "&7Match colour, number or symbol.", "&7First to empty their hand wins.", "", "&eClick for the rules"), "help");
        int slot = 9;
        for (Table t : tables.values()) {
            if (t.g.started || slot > 17) continue;
            Seat host = t.g.seats.stream().filter(x -> x.id.equals(t.host)).findFirst().orElse(null);
            put(m, slot++, item(Material.PAPER, "&fTable #" + t.id + (host != null ? " &7(" + host.name + ")" : ""),
                    "&7Players: &f" + t.g.seats.size() + "/" + MAX_SEATS, "", "&aClick to join"), "join:" + t.id);
        }
        if (slot == 9) put(m, 13, item(Material.GRAY_STAINED_GLASS_PANE, "&7No open tables", "&7Create one below!"), null);
        put(m, 21, glint(item(Material.RED_CONCRETE, "&a&lCreate a table", "&7Invite others or add bots, then start.")), "create");
        put(m, 23, item(Material.GOLDEN_HELMET, "&eTop players", "&7Most UNO wins"), "top");
        fill(m.inv, Material.BLACK_STAINED_GLASS_PANE, 0, 26);
        p.openInventory(m.inv);
    }

    void room(Player p, Table t) {
        Menu m = menu("room", t, 3, "&8UNO table #" + t.id + " - waiting");
        for (int i = 0; i < t.g.seats.size(); i++) put(m, i, seatItem(t, t.g.seats.get(i), false), null);
        boolean host = t.host.equals(p.getUniqueId().toString());
        put(m, 13, item(Material.BOOK, "&fTable #" + t.id, "&7Players: &f" + t.g.seats.size() + "/" + MAX_SEATS,
                "&7Others join with &f/uno join " + t.id, "&7or from &f/uno&7.", "", "&eClick for the rules"), "help");
        if (host) {
            put(m, 19, item(Material.SKELETON_SKULL, "&fAdd a bot", "&7Fill a seat with a computer player."), "addbot");
            put(m, 20, item(Material.WITHER_SKELETON_SKULL, "&fRemove a bot"), "rmbot");
            put(m, 22, glint(item(Material.LIME_CONCRETE, "&a&lStart", t.g.seats.size() < 2 ? "&cNeeds at least 2 players" : "&7Deal 7 cards each and play!")), "start");
        } else put(m, 22, item(Material.CLOCK, "&7Waiting for the host to start..."), null);
        put(m, 25, item(Material.BARRIER, "&cLeave the table"), "leave");
        fill(m.inv, Material.BLACK_STAINED_GLASS_PANE, 0, 26);
        p.openInventory(m.inv);
    }

    /** The game screen: seats on top, then UNO / Draw / top card / colour / leave, then your hand (27 cards a page). */
    void game(Player p, Table t) {
        Menu m = menu("game", t, 6, "&8UNO - table #" + t.id);
        drawGame(p, t, m);
        p.openInventory(m.inv);
    }
    void drawGame(Player p, Table t, Menu m) {
        Game g = t.g;
        m.inv.clear(); m.actions.clear();
        Seat me = t.seat(p.getUniqueId());
        boolean myTurn = me != null && g.current() == me && !g.over;
        for (int i = 0; i < g.seats.size() && i < 8; i++) put(m, i, seatItem(t, g.seats.get(i), i == g.cur), null);
        put(m, 8, item(g.dir > 0 ? Material.SPECTRAL_ARROW : Material.TIPPED_ARROW, "&7Direction: &f" + (g.dir > 0 ? "→ left to right" : "← right to left")), null);
        if (me != null) {
            put(m, 9, me.saidUno ? glint(item(Material.BELL, "&c&lU&e&lN&a&lO&9&l! &7(called)")) :
                    item(Material.BELL, "&c&lU&e&lN&a&lO&9&l!", "&7Click before you play your", "&7second-to-last card, or draw 2."), "uno");
            put(m, 11, g.drewThisTurn && myTurn ? glint(item(Material.HOPPER, "&e&lPass", "&7Keep the card you drew.")) :
                    item(Material.CHEST, "&f&lDraw a card", "&7Deck: &f" + g.deck.size() + " cards", myTurn ? (g.canPlayAny(me) ? "&8(you could play a card)" : "&aNothing fits: draw!") : "&8Wait for your turn"), "draw");
        }
        Card top = g.top();
        put(m, 13, glint(cardItem(top, "&7Top card", top.wild() ? "&7Colour: " + g.color.text() : "")), null);
        put(m, 15, item(mat(dye(g.color) + "_WOOL"), "&7Colour to match: " + g.color.text()), null);
        put(m, 17, item(Material.BARRIER, "&cLeave the game", "&7Shift-click to leave"), "leave");
        if (me != null) {
            int pg = t.page.getOrDefault(me.id, 0), pages = Math.max(1, (me.hand.size() + HAND_SLOTS - 1) / HAND_SLOTS);
            pg = Math.min(pg, pages - 1);
            for (int i = 0; i < HAND_SLOTS; i++) {
                int idx = pg * HAND_SLOTS + i;
                if (idx >= me.hand.size()) break;
                Card cd = me.hand.get(idx);
                boolean ok = myTurn && !g.awaitingColor && g.playable(cd);
                ItemStack it = cardItem(cd, ok ? "&aClick to play" : myTurn ? "&8Doesn't match" : "");
                put(m, 18 + i, ok ? glint(it) : it, "card:" + idx);
            }
            if (pg > 0) put(m, 45, item(Material.ARROW, "&fPrevious cards"), "prev");
            if (pg < pages - 1) put(m, 53, item(Material.ARROW, "&fMore cards", "&7Page " + (pg + 1) + "/" + pages), "next");
            String turn = myTurn ? (g.awaitingColor ? "&d&lPick a colour!" : "&a&lYour turn!") : "&7" + g.current().name + "'s turn";
            put(m, 49, item(Material.CLOCK, turn, "&7You have &f" + me.hand.size() + " &7cards.", myTurn ? "&7Time left: &f" + Math.max(0, t.ticksLeft / 20) + "s" : ""), null);
            put(m, 47, item(Material.BOOK, "&eRules"), "help");
            if (myTurn && g.awaitingColor) {   // colour picker replaces the bottom row
                int[] slots = {46, 48, 50, 52};
                for (int i = 0; i < 4; i++) { Col col = Game.COLORS.get(i); put(m, slots[i], glint(item(mat(dye(col) + "_WOOL"), "&lChoose " + col.text())), "color:" + col.name()); }
            }
        }
        fill(m.inv, Material.BLACK_STAINED_GLASS_PANE, 0, 17);
        fill(m.inv, Material.GREEN_STAINED_GLASS_PANE, 18, 44);
        fill(m.inv, Material.BLACK_STAINED_GLASS_PANE, 45, 53);
    }

    /** Redraw every open menu of this table's players. */
    void refresh(Table t) {
        for (Seat s : t.g.seats) {
            Player p = player(s);
            if (p == null || !(p.getOpenInventory().getTopInventory().getHolder() instanceof Menu m) || m.t != t) continue;
            if (m.kind.equals("game") && t.g.started) drawGame(p, t, m);
            else if (m.kind.equals("room") && !t.g.started) room(p, t);
            else if (m.kind.equals("room")) game(p, t);
        }
    }

    @EventHandler public void onDrag(InventoryDragEvent e) { if (e.getInventory().getHolder() instanceof Menu) e.setCancelled(true); }

    @EventHandler public void onClick(InventoryClickEvent e) {
        if (!(e.getInventory().getHolder() instanceof Menu m) || !(e.getWhoClicked() instanceof Player p)) return;
        e.setCancelled(true);
        if (e.getClickedInventory() != e.getInventory()) return;
        String a = m.actions.get(e.getRawSlot());
        if (a == null) return;
        Table t = m.t;
        switch (a.contains(":") ? a.substring(0, a.indexOf(':')) : a) {
            case "help" -> { p.closeInventory(); help(p); }
            case "top" -> { p.closeInventory(); showTop(p); }
            case "create" -> create(p);
            case "join" -> join(p, Integer.parseInt(a.substring(5)));
            case "leave" -> { if (!m.kind.equals("game") || e.isShiftClick()) leave(p, true); else msg(p, "&7Shift-click to leave the game."); }
            case "addbot" -> {
                if (t.g.started || t.g.seats.size() >= MAX_SEATS) return;
                t.bots++;
                t.g.seats.add(new Seat("bot" + t.bots, "Bot " + t.bots, true));
                refresh(t);
            }
            case "rmbot" -> {
                if (t.g.started) return;
                for (int i = t.g.seats.size() - 1; i >= 0; i--) if (t.g.seats.get(i).bot) { t.g.seats.remove(i); break; }
                refresh(t);
            }
            case "start" -> start(p, t);
            case "prev", "next" -> {
                Seat me = t.seat(p.getUniqueId()); if (me == null) return;
                t.page.merge(me.id, a.equals("next") ? 1 : -1, Integer::sum);
                if (t.page.get(me.id) < 0) t.page.put(me.id, 0);
                drawGame(p, t, m);
            }
            case "card", "draw", "uno", "color" -> act(p, t, a);
            default -> {}
        }
    }

    void act(Player p, Table t, String a) {
        Seat me = t.seat(p.getUniqueId());
        if (me == null || !t.g.started) return;
        String err;
        if (a.startsWith("card:")) err = t.g.play(me, Integer.parseInt(a.substring(5)));
        else if (a.equals("draw")) err = t.g.draw(me);
        else if (a.equals("uno")) err = t.g.uno(me);
        else err = t.g.chooseColor(me, Col.valueOf(a.substring(6)));
        if (err != null) { msg(p, "&c" + err); p.playSound(p.getLocation(), Sound.ENTITY_VILLAGER_NO, 0.6f, 1.2f); return; }
        t.timeouts.remove(me.id);
        p.playSound(p.getLocation(), a.startsWith("card") || a.startsWith("color") ? Sound.ITEM_BOOK_PAGE_TURN : a.equals("uno") ? Sound.BLOCK_BELL_USE : Sound.ITEM_BUNDLE_INSERT, 1, 1);
        flush(t);
    }

    @EventHandler public void onQuit(PlayerQuitEvent e) { leave(e.getPlayer(), false); }
}

package crispy.lobby;

import io.papermc.paper.event.player.AsyncChatEvent;
import net.kyori.adventure.text.Component;
import net.kyori.adventure.text.format.TextDecoration;
import net.kyori.adventure.text.serializer.plain.PlainTextComponentSerializer;
import org.bukkit.Bukkit;
import org.bukkit.Material;
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
import org.bukkit.inventory.ItemStack;
import org.bukkit.inventory.meta.ItemMeta;

import java.io.File;
import java.io.IOException;
import java.util.ArrayList;
import java.util.HashMap;
import java.util.List;
import java.util.Map;
import java.util.UUID;
import java.util.function.Consumer;
import java.util.regex.Pattern;

/**
 * /cosmeticsadmin (/cadmin, crispylobby.admin): add, edit and delete cosmetic tags, name colours and chat colours in
 * game. Changes go to plugins/CrispyLobby/cosmetics-edits.yml, which Votes.load() lays over config.yml's cosmetics
 * (entries there add to or replace config ones, "removed.<kind>" lists drop them), so config.yml is never rewritten.
 * Text (display, name, colour code, note, cost, id) is typed in chat when asked; "cancel" stops.
 */
final class CosmeticEditor implements Listener {
    static final String FILE = "cosmetics-edits.yml";
    static final Pattern ID = Pattern.compile("[a-z0-9_]{1,24}");
    enum Kind {
        TAGS("tags", "Tags", Material.NAME_TAG), NAME("name-colors", "Name Colours", Material.LIME_DYE), CHAT("chat-colors", "Chat Colours", Material.WRITABLE_BOOK);
        final String key, label; final Material icon;
        Kind(String key, String label, Material icon) { this.key = key; this.label = label; this.icon = icon; }
    }
    static final class Menu implements InventoryHolder {
        final Map<Integer, Consumer<InventoryClickEvent>> actions = new HashMap<>(); Inventory inv;
        @Override public Inventory getInventory() { return inv; }
    }

    private final CrispyLobby plugin;
    private final Map<UUID, Consumer<String>> prompts = new HashMap<>();
    private final Map<UUID, String> confirmDelete = new HashMap<>();

    CosmeticEditor(CrispyLobby plugin) { this.plugin = plugin; }

    static YamlConfiguration edits(CrispyLobby plugin) {
        File f = new File(plugin.getDataFolder(), FILE);
        return f.exists() ? YamlConfiguration.loadConfiguration(f) : new YamlConfiguration();
    }

    private void save(YamlConfiguration y) {
        try { y.save(new File(plugin.getDataFolder(), FILE)); }
        catch (IOException e) { plugin.getLogger().warning(FILE + " write failed: " + e); }
        plugin.votes.load();   // re-reads config.yml's cosmetics + the edits, rewrites tags.json etc. for the proxy
    }

    // ---- menus
    static Component t(String amp) { return CrispyLobby.AMP.deserialize(amp).decoration(TextDecoration.ITALIC, false); }
    static ItemStack item(Material m, Component name, List<String> lore) {
        ItemStack it = new ItemStack(m == null || m.isAir() ? Material.PAPER : m);
        ItemMeta meta = it.getItemMeta();
        meta.displayName(name);
        List<Component> l = new ArrayList<>(); for (String s : lore) l.add(t(s)); meta.lore(l);
        it.setItemMeta(meta);
        return it;
    }
    private Menu menu(int rows, String title) {
        Menu m = new Menu();
        m.inv = Bukkit.createInventory(m, rows * 9, t(title));
        ItemStack pane = item(Material.BLACK_STAINED_GLASS_PANE, Component.text(" "), List.of());
        for (int i = 0; i < rows * 9; i++) m.inv.setItem(i, pane);
        return m;
    }
    private void put(Menu m, int slot, ItemStack it, Consumer<InventoryClickEvent> act) { m.inv.setItem(slot, it); if (act != null) m.actions.put(slot, act); }

    void openMain(Player p) {
        Menu m = menu(3, "&8Cosmetics editor");
        int slot = 11;
        for (Kind k : Kind.values()) {
            int n = entries(k).size();
            put(m, slot, item(k.icon, t("&e&l" + k.label), List.of("&7" + n + " entries", "", "&eClick to edit")), e -> openList((Player) e.getWhoClicked(), k, 0));
            slot += 2;
        }
        put(m, 22, item(Material.BARRIER, t("&cClose"), List.of()), e -> e.getWhoClicked().closeInventory());
        p.openInventory(m.inv);
    }

    private Map<String, ?> entries(Kind k) {
        Votes v = plugin.votes;
        return switch (k) { case TAGS -> v.tags; case NAME -> v.colors; case CHAT -> v.chatColors; };
    }

    private static String preview(Kind k, Object o) {
        if (o instanceof Votes.Tag tg) return tg.display();
        Votes.NameColor c = (Votes.NameColor) o;
        return Votes.colored(k == Kind.CHAT ? "Hello there!" : "Steve", c.code());
    }
    private static Material icon(Object o) { return o instanceof Votes.Tag tg ? tg.icon() : ((Votes.NameColor) o).icon(); }
    private static int cost(Object o) { return o instanceof Votes.Tag tg ? tg.cost() : ((Votes.NameColor) o).cost(); }

    void openList(Player p, Kind k, int page) {
        Menu m = menu(6, "&8" + k.label + " &7(page " + (page + 1) + ")");
        List<String> ids = new ArrayList<>(entries(k).keySet());
        int from = page * 45;
        for (int i = 0; i < 45 && from + i < ids.size(); i++) {
            String id = ids.get(from + i);
            Object o = entries(k).get(id);
            List<String> lore = new ArrayList<>(List.of("&8id: " + id));
            if (o instanceof Votes.Tag tg && tg.earned()) lore.add("&7Earned (not bought)");
            else if (o instanceof Votes.NameColor c && c.event()) lore.add("&7Event colour (score " + c.score() + ")");
            else lore.add("&7Cost: &6" + cost(o) + " points");
            if (o instanceof Votes.NameColor c) lore.add("&7Code: &f" + c.code().replace("&", "＆"));
            lore.add(""); lore.add("&eClick to edit");
            put(m, i, item(icon(o), t(o instanceof Votes.NameColor c ? Votes.colored(c.name(), c.code()) + " &8· " + preview(k, o) : preview(k, o)), lore),
                    e -> openEdit((Player) e.getWhoClicked(), k, id));
        }
        put(m, 45, item(Material.ARROW, t("&7Back"), List.of()), e -> openMain((Player) e.getWhoClicked()));
        if (page > 0) put(m, 48, item(Material.ARROW, t("&ePrevious page"), List.of()), e -> openList((Player) e.getWhoClicked(), k, page - 1));
        put(m, 49, item(Material.EMERALD, t("&a&l+ Add new"), List.of("&7You'll type the details in chat")), e -> startAdd((Player) e.getWhoClicked(), k));
        if (from + 45 < ids.size()) put(m, 50, item(Material.ARROW, t("&eNext page"), List.of()), e -> openList((Player) e.getWhoClicked(), k, page + 1));
        p.openInventory(m.inv);
    }

    void openEdit(Player p, Kind k, String id) {
        Object o = entries(k).get(id);
        if (o == null) { openList(p, k, 0); return; }
        Menu m = menu(3, "&8Edit " + k.label + ": " + id);
        put(m, 4, item(icon(o), t(preview(k, o)), List.of("&8id: " + id, "&7Cost: &6" + cost(o))), null);
        if (o instanceof Votes.Tag tg) {
            put(m, 10, item(Material.NAME_TAG, t("&eDisplay text"), List.of("&7Now: " + tg.display().replace("&", "＆"), "&7e.g. ＆6[Crispy]  (＆ colour codes)", "", "&eClick, then type it in chat")),
                    e -> ask(e, "the display text (e.g. &6[Crispy])", s -> set(k, id, "display", s)));
            put(m, 11, item(Material.BOOK, t("&eNote"), List.of("&7Now: " + (tg.note() == null ? "none" : tg.note()), "&7Shown under the tag; type 'none' to clear", "", "&eClick, then type it in chat")),
                    e -> ask(e, "the note ('none' to clear)", s -> set(k, id, "note", s.equalsIgnoreCase("none") ? null : s)));
        } else {
            Votes.NameColor c = (Votes.NameColor) o;
            put(m, 10, item(Material.NAME_TAG, t("&eName"), List.of("&7Now: " + c.name(), "", "&eClick, then type it in chat")),
                    e -> ask(e, "the colour's name (e.g. Ocean)", s -> set(k, id, "name", s)));
            put(m, 11, item(Material.LIME_DYE, t("&eColour code"), List.of("&7Now: " + c.code().replace("&", "＆"),
                            "&7＆b, ＆6＆l, rainbow, fades like ＆#ff0000>＆#0000ff", "", "&eClick, then type it in chat")),
                    e -> ask(e, "the colour code (e.g. &b, &6&l, rainbow, &#ff0000>&#0000ff)", s -> set(k, id, "code", s)));
        }
        put(m, 12, item(Material.GOLD_INGOT, t("&eCost"), List.of("&7Now: &6" + cost(o) + " points", "", "&eClick, then type a number")),
                e -> ask(e, "the cost in vote points", s -> {
                    try { int n = Integer.parseInt(s.trim()); if (n < 0 || n > 9999) throw new NumberFormatException(); set(k, id, "cost", n); }
                    catch (NumberFormatException x) { msg((Player) e.getWhoClicked(), "&cThat's not a number from 0 to 9999."); }
                }));
        put(m, 14, item(Material.ITEM_FRAME, t("&eIcon"), List.of("&7Now: " + icon(o).name().toLowerCase(), "&7Hold an item, then click", "&7to use it as the icon")), e -> {
            Material held = ((Player) e.getWhoClicked()).getInventory().getItemInMainHand().getType();
            if (held.isAir()) { msg((Player) e.getWhoClicked(), "&cHold the item you want as the icon first."); return; }
            set(k, id, "icon", held.name());
            openEdit((Player) e.getWhoClicked(), k, id);
        });
        boolean armed = (k.key + ":" + id).equals(confirmDelete.get(p.getUniqueId()));
        put(m, 16, item(armed ? Material.TNT : Material.LAVA_BUCKET, t(armed ? "&4&lClick again to delete" : "&cDelete"),
                List.of("&7Removes it from the menus.", "&7Players who own it keep the points spent.")), e -> {
            Player pl = (Player) e.getWhoClicked();
            if (!(k.key + ":" + id).equals(confirmDelete.get(pl.getUniqueId()))) { confirmDelete.put(pl.getUniqueId(), k.key + ":" + id); openEdit(pl, k, id); return; }
            confirmDelete.remove(pl.getUniqueId());
            delete(k, id);
            msg(pl, "&aDeleted " + id + ".");
            openList(pl, k, 0);
        });
        put(m, 22, item(Material.ARROW, t("&7Back"), List.of()), e -> openList((Player) e.getWhoClicked(), k, 0));
        p.openInventory(m.inv);
    }

    // ---- edits
    /** Copy an entry (all its fields, from whichever file it came) into the edits file and change one field. */
    private void set(Kind k, String id, String field, Object value) {
        YamlConfiguration y = edits(plugin);
        String base = k.key + "." + id;
        if (!y.isConfigurationSection(base)) {
            ConfigurationSection src = plugin.getConfig().getConfigurationSection("cosmetics." + base);
            if (src != null) for (String f : src.getKeys(false)) y.set(base + "." + f, src.get(f));
        }
        y.set(base + "." + field, value);
        List<String> removed = new ArrayList<>(y.getStringList("removed." + k.key)); removed.remove(id); y.set("removed." + k.key, removed);
        save(y);
    }

    private void delete(Kind k, String id) {
        YamlConfiguration y = edits(plugin);
        y.set(k.key + "." + id, null);
        if (plugin.getConfig().isConfigurationSection("cosmetics." + k.key + "." + id)) {
            List<String> removed = new ArrayList<>(y.getStringList("removed." + k.key));
            if (!removed.contains(id)) removed.add(id);
            y.set("removed." + k.key, removed);
        }
        save(y);
    }

    private void startAdd(Player p, Kind k) {
        p.closeInventory();
        Map<String, Object> f = new HashMap<>();
        promptThen(p, "an id for it (lowercase letters, numbers, _ ; e.g. ocean)", id -> {
            id = id.trim().toLowerCase();
            if (!ID.matcher(id).matches()) { msg(p, "&cIds are 1-24 lowercase letters, numbers or _. Start again from the menu."); return; }
            if (entries(k).containsKey(id)) { msg(p, "&cThere's already one called " + id + ". Start again from the menu."); return; }
            final String fid = id;
            if (k == Kind.TAGS) {
                promptThen(p, "the display text (e.g. &6[Crispy])", disp -> { f.put("display", disp); askCost(p, k, fid, f); });
            } else {
                promptThen(p, "the colour's name (e.g. Ocean)", name -> {
                    f.put("name", name);
                    promptThen(p, "the colour code (e.g. &b, &6&l, rainbow, &#ff0000>&#0000ff)", code -> { f.put("code", code); askCost(p, k, fid, f); });
                });
            }
        });
    }

    private void askCost(Player p, Kind k, String id, Map<String, Object> f) {
        promptThen(p, "the cost in vote points", s -> {
            int n;
            try { n = Integer.parseInt(s.trim()); if (n < 0 || n > 9999) throw new NumberFormatException(); }
            catch (NumberFormatException x) { msg(p, "&cThat's not a number from 0 to 9999. Start again from the menu."); return; }
            f.put("cost", n);
            Material held = p.getInventory().getItemInMainHand().getType();
            f.put("icon", (held.isAir() ? (k == Kind.TAGS ? Material.NAME_TAG : Material.WHITE_DYE) : held).name());
            YamlConfiguration y = edits(plugin);
            f.forEach((key, val) -> y.set(k.key + "." + id + "." + key, val));
            List<String> removed = new ArrayList<>(y.getStringList("removed." + k.key)); removed.remove(id); y.set("removed." + k.key, removed);
            save(y);
            msg(p, "&aAdded " + id + ". It's in the /cosmetics menu now. Icon: the item you're holding (change it here any time).");
            openEdit(p, k, id);
        });
    }

    // ---- chat prompts
    private void ask(InventoryClickEvent e, String what, Consumer<String> then) {
        Player p = (Player) e.getWhoClicked();
        String title = PlainTextComponentSerializer.plainText().serialize(e.getView().title());
        p.closeInventory();
        promptThen(p, what, s -> { then.accept(s); reopenFrom(p, title); });
    }
    private void reopenFrom(Player p, String title) {
        // titles look like "Edit Tags: crispy"
        for (Kind k : Kind.values()) {
            String pre = "Edit " + k.label + ": ";
            if (title.startsWith(pre)) { openEdit(p, k, title.substring(pre.length())); return; }
        }
        openMain(p);
    }
    private void promptThen(Player p, String what, Consumer<String> then) {
        prompts.put(p.getUniqueId(), then);
        msg(p, "&eType " + what + " in chat. &7(or 'cancel')");
    }
    private static void msg(Player p, String s) { p.sendMessage(t("&d[Cosmetics] " + s)); }

    @EventHandler(priority = EventPriority.LOWEST)
    public void onChat(AsyncChatEvent e) {
        Consumer<String> then = prompts.remove(e.getPlayer().getUniqueId());
        if (then == null) return;
        e.setCancelled(true);
        String s = PlainTextComponentSerializer.plainText().serialize(e.originalMessage()).trim();
        Player p = e.getPlayer();
        Bukkit.getScheduler().runTask(plugin, () -> {
            if (s.equalsIgnoreCase("cancel")) { msg(p, "&7Cancelled."); return; }
            then.accept(s);
        });
    }

    @EventHandler public void onClick(InventoryClickEvent e) {
        if (!(e.getView().getTopInventory().getHolder() instanceof Menu m)) return;
        e.setCancelled(true);
        if (e.getClickedInventory() != e.getView().getTopInventory()) return;
        if (!e.getWhoClicked().hasPermission("crispylobby.admin")) { e.getWhoClicked().closeInventory(); return; }
        Consumer<InventoryClickEvent> act = m.actions.get(e.getRawSlot());
        if (act != null) act.accept(e);
    }
    @EventHandler public void onDrag(InventoryDragEvent e) { if (e.getView().getTopInventory().getHolder() instanceof Menu) e.setCancelled(true); }
    @EventHandler public void onQuit(PlayerQuitEvent e) { prompts.remove(e.getPlayer().getUniqueId()); confirmDelete.remove(e.getPlayer().getUniqueId()); }

    boolean command(org.bukkit.command.CommandSender s) {
        if (!(s instanceof Player p)) { s.sendMessage("Run /cosmeticsadmin in game."); return true; }
        if (!p.hasPermission("crispylobby.admin")) { p.sendMessage(t("&cYou don't have permission.")); return true; }
        openMain(p);
        return true;
    }
}

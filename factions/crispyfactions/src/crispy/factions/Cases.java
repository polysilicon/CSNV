package crispy.factions;

import net.kyori.adventure.text.Component;
import net.kyori.adventure.text.format.TextDecoration;
import net.milkbowl.vault.economy.Economy;
import org.bukkit.*;
import org.bukkit.command.CommandSender;
import org.bukkit.configuration.ConfigurationSection;
import org.bukkit.enchantments.Enchantment;
import org.bukkit.entity.Monster;
import org.bukkit.entity.Player;
import org.bukkit.event.EventHandler;
import org.bukkit.event.EventPriority;
import org.bukkit.event.Listener;
import org.bukkit.event.block.Action;
import org.bukkit.event.block.BlockPlaceEvent;
import org.bukkit.event.entity.CreatureSpawnEvent;
import org.bukkit.event.entity.EntityDeathEvent;
import org.bukkit.event.entity.PlayerDeathEvent;
import org.bukkit.event.inventory.InventoryClickEvent;
import org.bukkit.event.inventory.InventoryDragEvent;
import org.bukkit.event.player.PlayerInteractEvent;
import org.bukkit.event.player.PlayerQuitEvent;
import org.bukkit.inventory.EquipmentSlot;
import org.bukkit.inventory.Inventory;
import org.bukkit.inventory.InventoryHolder;
import org.bukkit.inventory.ItemStack;
import org.bukkit.inventory.meta.ItemMeta;
import org.bukkit.persistence.PersistentDataContainer;
import org.bukkit.persistence.PersistentDataType;
import org.bukkit.plugin.RegisteredServiceProvider;
import org.bukkit.scheduler.BukkitTask;

import java.util.*;
import java.util.concurrent.ThreadLocalRandom;

/** CS2-style weapon cases, paid with in-game money only: a Case (mob drop or /cases) plus a Key (/cases) opens a
 *  spinning roulette. Rarity odds match CS2 (Mil-Spec 79.92%, Restricted 15.98%, Classified 3.2%, Covert 0.64%,
 *  Rare Special 0.26%). Skins are real weapons with a wear float and a 10% StatTrak kill counter. */
public class Cases implements Listener {
    record Rarity(String id, String name, String color, double weight, Material pane) {}
    record Reward(Rarity rarity, String label, Material item, int amount, double money, String skin, Map<Enchantment, Integer> ench, String special) {}

    static final String CASE_NAME = "&6&lCrispy Case", KEY_NAME = "&e&lCrispy Case Key";
    static final int FINAL_STEP = 51;           // the winner sits at strip index FINAL_STEP + 4 (the centre slot)

    final CrispyFactions plugin;
    final NamespacedKey K_CASE, K_KEY, K_SKIN, K_FLOAT, K_ST;
    boolean enabled;
    double keyPrice, casePrice, dropChance, stattrakChance;
    Set<String> broadcast = Set.of();
    final List<Rarity> rarities = new ArrayList<>();
    final List<Reward> rewards = new ArrayList<>();
    final Map<UUID, Spin> spins = new HashMap<>();

    Cases(CrispyFactions plugin) {
        this.plugin = plugin;
        K_CASE = new NamespacedKey(plugin, "case"); K_KEY = new NamespacedKey(plugin, "case_key");
        K_SKIN = new NamespacedKey(plugin, "skin"); K_FLOAT = new NamespacedKey(plugin, "skin_float"); K_ST = new NamespacedKey(plugin, "stattrak");
        load();
    }

    // ------------------------------------------------------------------ config
    void load() {
        rarities.clear(); rewards.clear();
        ConfigurationSection c = plugin.getConfig().getConfigurationSection("cases");
        enabled = c != null && c.getBoolean("enabled", true);
        if (c == null) return;
        keyPrice = c.getDouble("key-price", 15000); casePrice = c.getDouble("case-price", 2500);
        dropChance = c.getDouble("drop-chance", 0.004); stattrakChance = c.getDouble("stattrak-chance", 0.10);
        broadcast = new HashSet<>(c.getStringList("broadcast-rarities"));
        ConfigurationSection rs = c.getConfigurationSection("rarities");
        if (rs != null) for (String id : rs.getKeys(false)) {
            ConfigurationSection r = rs.getConfigurationSection(id);
            rarities.add(new Rarity(id, r.getString("name", id), r.getString("color", "&7"), r.getDouble("weight"),
                    Material.matchMaterial(r.getString("pane", "GRAY_STAINED_GLASS_PANE"))));
        }
        for (Map<?, ?> m : c.getMapList("rewards")) {
            try {
                Rarity r = rarity(String.valueOf(m.get("rarity")));
                if (r == null) { plugin.getLogger().warning("cases: unknown rarity in " + m); continue; }
                Material item = m.get("item") == null ? null : Material.matchMaterial(String.valueOf(m.get("item")));
                Map<Enchantment, Integer> ench = new LinkedHashMap<>();
                if (m.get("enchants") instanceof Map<?, ?> em) for (Map.Entry<?, ?> e : em.entrySet()) {
                    Enchantment en = Registry.ENCHANTMENT.get(NamespacedKey.minecraft(String.valueOf(e.getKey()).toLowerCase(Locale.ROOT)));
                    if (en != null) ench.put(en, ((Number) e.getValue()).intValue());
                }
                double money = m.get("money") == null ? 0 : ((Number) m.get("money")).doubleValue();
                String skin = m.get("skin") == null ? null : String.valueOf(m.get("skin"));
                String special = m.get("special") == null ? null : String.valueOf(m.get("special"));
                int amount = m.get("amount") == null ? 1 : ((Number) m.get("amount")).intValue();
                String label = m.get("name") != null ? String.valueOf(m.get("name"))
                        : skin != null ? skin : money > 0 ? "$" + String.format("%,.0f", money) : amount + " " + pretty(item);
                if (item == null && money <= 0 && special == null) { plugin.getLogger().warning("cases: reward has nothing to give: " + m); continue; }
                rewards.add(new Reward(r, label, item, amount, money, skin, ench, special));
            } catch (RuntimeException ex) { plugin.getLogger().warning("cases: bad reward " + m + ": " + ex); }
        }
        for (Rarity r : rarities) if (rewards.stream().noneMatch(w -> w.rarity == r)) plugin.getLogger().warning("cases: rarity " + r.id + " has no rewards");
    }
    Rarity rarity(String id) { for (Rarity r : rarities) if (r.id.equals(id)) return r; return null; }
    static String pretty(Material m) {
        if (m == null) return "?";
        StringBuilder b = new StringBuilder();
        for (String w : m.name().toLowerCase(Locale.ROOT).split("_")) b.append(b.isEmpty() ? "" : " ").append(Character.toUpperCase(w.charAt(0))).append(w.substring(1));
        return b.toString();
    }
    static String money(double d) { return "$" + String.format("%,.0f", d); }

    Economy eco() {
        RegisteredServiceProvider<Economy> rsp = Bukkit.getServicesManager().getRegistration(Economy.class);
        return rsp == null ? null : rsp.getProvider();
    }

    // ------------------------------------------------------------------ items
    static Component text(String legacy) { return CrispyFactions.c(legacy).decoration(TextDecoration.ITALIC, false); }
    ItemStack named(Material m, String name, List<String> lore) {
        ItemStack it = new ItemStack(m);
        ItemMeta meta = it.getItemMeta();
        meta.displayName(text(name));
        if (lore != null) meta.lore(lore.stream().map(Cases::text).toList());
        it.setItemMeta(meta);
        return it;
    }
    ItemStack caseItem(int n) {
        ItemStack it = named(Material.CHEST, CASE_NAME, List.of("&7A CS-style weapon case.", "&7Right-click to look inside.", "&7Needs a &eCrispy Case Key &7(&f/cases&7)."));
        ItemMeta m = it.getItemMeta(); m.getPersistentDataContainer().set(K_CASE, PersistentDataType.BYTE, (byte) 1); m.setEnchantmentGlintOverride(true); it.setItemMeta(m);
        it.setAmount(n); return it;
    }
    ItemStack keyItem(int n) {
        ItemStack it = named(Material.TRIPWIRE_HOOK, KEY_NAME, List.of("&7Unlocks one &6Crispy Case&7."));
        ItemMeta m = it.getItemMeta(); m.getPersistentDataContainer().set(K_KEY, PersistentDataType.BYTE, (byte) 1); m.setEnchantmentGlintOverride(true); it.setItemMeta(m);
        it.setAmount(n); return it;
    }
    boolean has(ItemStack it, NamespacedKey k) { return it != null && it.hasItemMeta() && it.getItemMeta().getPersistentDataContainer().has(k); }

    static String wear(double f) {
        return f < 0.07 ? "Factory New" : f < 0.15 ? "Minimal Wear" : f < 0.38 ? "Field-Tested" : f < 0.45 ? "Well-Worn" : "Battle-Scarred";
    }
    List<String> skinLore(Rarity r, double fl, Integer kills) {
        List<String> l = new ArrayList<>();
        l.add(r.color + r.name);
        l.add("&7Exterior: &f" + wear(fl) + " &8(" + String.format("%.4f", fl) + ")");
        if (kills != null) l.add("&6StatTrak™ Confirmed Kills: &f" + kills);
        l.add("&8Crispy Case");
        return l;
    }
    ItemStack skinItem(Reward w) {
        ThreadLocalRandom rnd = ThreadLocalRandom.current();
        double fl = rnd.nextDouble();
        boolean st = rnd.nextDouble() < stattrakChance;
        String name = w.rarity.color + (st ? "StatTrak™ " : "") + w.skin + " &7(" + wear(fl) + ")";
        ItemStack it = named(w.item, name, skinLore(w.rarity, fl, st ? 0 : null));
        ItemMeta m = it.getItemMeta();
        for (Map.Entry<Enchantment, Integer> e : w.ench.entrySet()) m.addEnchant(e.getKey(), e.getValue(), true);
        PersistentDataContainer pdc = m.getPersistentDataContainer();
        pdc.set(K_SKIN, PersistentDataType.STRING, w.rarity.id + "|" + w.skin);
        pdc.set(K_FLOAT, PersistentDataType.DOUBLE, fl);
        if (st) pdc.set(K_ST, PersistentDataType.INTEGER, 0);
        it.setItemMeta(m);
        return it;
    }
    ItemStack icon(Reward w) {
        Material m = w.special != null && w.special.equals("aegis") ? Material.NETHER_STAR : w.item != null ? w.item : Material.GOLD_INGOT;
        ItemStack it = named(m, w.rarity.color + w.label, List.of(w.rarity.color + w.rarity.name));
        if (w.item != null && w.money <= 0 && w.skin == null) it.setAmount(Math.max(1, Math.min(w.amount, it.getMaxStackSize())));
        if (!w.ench.isEmpty()) { ItemMeta meta = it.getItemMeta(); meta.setEnchantmentGlintOverride(true); it.setItemMeta(meta); }
        return it;
    }
    ItemStack pane(Rarity r) { return named(r == null ? Material.BLACK_STAINED_GLASS_PANE : r.pane, " ", null); }

    void give(Player p, ItemStack it) { p.getInventory().addItem(it).values().forEach(left -> p.getWorld().dropItemNaturally(p.getLocation(), left)); }
    void award(Player p, Reward w) {
        if (w.money > 0) { Economy e = eco(); if (e != null) e.depositPlayer(p, w.money); }
        if (w.special != null && w.special.equals("aegis")) give(p, plugin.star(1));
        if (w.skin != null && w.item != null) give(p, skinItem(w));
        else if (w.item != null) {
            int left = w.amount, max = new ItemStack(w.item).getMaxStackSize();
            while (left > 0) { int n = Math.min(left, max); ItemStack it = new ItemStack(w.item, n); if (!w.ench.isEmpty()) it.addUnsafeEnchantments(w.ench); give(p, it); left -= n; }
        }
    }

    Reward roll() {
        double total = 0; for (Rarity r : rarities) if (rewards.stream().anyMatch(w -> w.rarity == r)) total += r.weight;
        double x = ThreadLocalRandom.current().nextDouble() * total;
        Rarity pick = null;
        for (Rarity r : rarities) {
            if (rewards.stream().noneMatch(w -> w.rarity == r)) continue;
            pick = r; x -= r.weight; if (x < 0) break;
        }
        final Rarity fr = pick;
        List<Reward> pool = rewards.stream().filter(w -> w.rarity == fr).toList();
        return pool.get(ThreadLocalRandom.current().nextInt(pool.size()));
    }

    // ------------------------------------------------------------------ GUIs
    static class Menu implements InventoryHolder {
        final String type; Inventory inv; Spin spin;
        Menu(String type) { this.type = type; }
        @Override public Inventory getInventory() { return inv; }
    }
    Inventory create(Menu m, int size, String title) { m.inv = Bukkit.createInventory(m, size, CrispyFactions.c(title)); return m.inv; }

    void openShop(Player p) {
        Menu m = new Menu("shop"); Inventory inv = create(m, 27, "&8Crispy Cases");
        for (int i = 0; i < 27; i++) inv.setItem(i, pane(null));
        inv.setItem(11, named(Material.CHEST, "&6&lBuy a Crispy Case", List.of("&7Price: &a" + money(casePrice), "&7Cases also drop from monsters.")));
        inv.setItem(13, named(Material.SPYGLASS, "&eWhat's inside?", List.of("&7See every item and the odds.")));
        inv.setItem(15, named(Material.TRIPWIRE_HOOK, "&e&lBuy a Case Key", List.of("&7Price: &a" + money(keyPrice), "&7One key opens one case.")));
        inv.setItem(22, named(Material.BOOK, "&fHow it works", List.of("&7Hold a case and right-click it,", "&7then press &aUnlock &7with a key in", "&7your inventory. In-game money only.")));
        p.openInventory(inv);
    }
    void openPreview(Player p) {
        Menu m = new Menu("preview"); Inventory inv = create(m, 54, "&8Crispy Case - contents");
        int slot = 0;
        for (Rarity r : rarities) for (Reward w : rewards) if (w.rarity == r && slot < 45) {
            ItemStack ic = icon(w); ItemMeta meta = ic.getItemMeta();
            List<Component> lore = new ArrayList<>(Objects.requireNonNullElse(meta.lore(), List.of()));
            lore.add(text("&7Rarity odds: &f" + r.weight + "%"));
            meta.lore(lore); ic.setItemMeta(meta);
            inv.setItem(slot++, ic);
        }
        for (int i = 45; i < 54; i++) inv.setItem(i, pane(null));
        inv.setItem(45, named(Material.ARROW, "&7Back", null));
        inv.setItem(49, named(Material.TRIPWIRE_HOOK, "&a&lUnlock Case", List.of("&7Uses 1 &6Crispy Case &7and 1 &eCase Key", "&7from your inventory.")));
        p.openInventory(inv);
    }

    boolean take(Player p, NamespacedKey k) {
        ItemStack[] cont = p.getInventory().getStorageContents();
        for (int i = 0; i < cont.length; i++) if (has(cont[i], k)) {
            ItemStack it = cont[i];
            if (it.getAmount() > 1) it.setAmount(it.getAmount() - 1); else p.getInventory().setItem(i, null);
            return true;
        }
        return false;
    }
    int count(Player p, NamespacedKey k) {
        int n = 0; for (ItemStack it : p.getInventory().getStorageContents()) if (has(it, k)) n += it.getAmount(); return n;
    }

    void unlock(Player p) {
        if (!enabled || rewards.isEmpty()) { CrispyFactions.msg(p, "&cCases are switched off."); return; }
        if (spins.containsKey(p.getUniqueId())) return;
        if (count(p, K_CASE) < 1) { p.closeInventory(); CrispyFactions.msg(p, "&cYou don't have a Crispy Case. Buy one in &f/cases &cor find one on monsters."); return; }
        if (count(p, K_KEY) < 1) { p.closeInventory(); CrispyFactions.msg(p, "&cYou need a &eCrispy Case Key&c: &f/cases &c(" + money(keyPrice) + ")."); return; }
        take(p, K_CASE); take(p, K_KEY);
        Spin s = new Spin(p, roll());
        spins.put(p.getUniqueId(), s);
        s.start();
    }

    class Spin {
        final Player p; final Reward win; final List<Reward> strip = new ArrayList<>(); final Menu menu = new Menu("spin");
        int step = 0, wait = 0; BukkitTask task; boolean done;
        Spin(Player p, Reward win) {
            this.p = p; this.win = win;
            for (int i = 0; i < FINAL_STEP + 9; i++) strip.add(roll());
            strip.set(FINAL_STEP + 4, win);
        }
        void start() {
            Inventory inv = create(menu, 27, "&8Unlocking Crispy Case...");
            menu.spin = this;
            render();
            p.openInventory(inv);
            task = Bukkit.getScheduler().runTaskTimer(plugin, this::tick, 2L, 1L);
        }
        void render() {
            Inventory inv = menu.inv;
            for (int k = 0; k < 9; k++) {
                Reward w = strip.get(step + k);
                inv.setItem(9 + k, icon(w));
                inv.setItem(k, pane(w.rarity)); inv.setItem(18 + k, pane(w.rarity));
            }
            inv.setItem(4, named(Material.HOPPER, "&f▼", null)); inv.setItem(22, named(Material.HOPPER, "&f▲", null));
        }
        void tick() {
            if (done) return;
            if (wait > 0) { wait--; return; }
            render();
            if (p.isOnline()) p.playSound(p.getLocation(), Sound.UI_BUTTON_CLICK, 0.4f, 1.6f);
            if (step >= FINAL_STEP) { finish(); return; }
            step++;
            int over = step - 30;
            wait = over <= 0 ? 0 : (over * over) / 40;
        }
        void finish() {
            if (done) return;
            done = true;
            if (task != null) task.cancel();
            spins.remove(p.getUniqueId());
            award(p, win);
            CrispyFactions.msg(p, "You unboxed " + win.rarity.color + win.label + " &7(" + win.rarity.color + win.rarity.name + "&7)");
            if (p.isOnline()) {
                Sound snd = switch (win.rarity.id) { case "gold", "covert" -> Sound.UI_TOAST_CHALLENGE_COMPLETE; case "classified" -> Sound.ENTITY_PLAYER_LEVELUP; default -> Sound.ENTITY_EXPERIENCE_ORB_PICKUP; };
                p.playSound(p.getLocation(), snd, 1f, 1f);
            }
            if (broadcast.contains(win.rarity.id)) CrispyFactions.bc(p.getName() + " &7unboxed " + win.rarity.color + win.label + "&7!");
        }
    }

    void shutdown() { for (Spin s : new ArrayList<>(spins.values())) s.finish(); }

    // ------------------------------------------------------------------ events
    @EventHandler(priority = EventPriority.HIGH)
    public void onClick(InventoryClickEvent e) {
        if (!(e.getView().getTopInventory().getHolder() instanceof Menu m)) return;
        e.setCancelled(true);
        if (!(e.getWhoClicked() instanceof Player p) || e.getClickedInventory() != e.getView().getTopInventory()) return;
        int s = e.getRawSlot();
        switch (m.type) {
            case "shop" -> {
                if (s == 13) openPreview(p);
                else if (s == 11 || s == 15) buy(p, s == 15);
            }
            case "preview" -> {
                if (s == 45) openShop(p);
                else if (s == 49) unlock(p);
            }
            default -> {}
        }
    }
    @EventHandler public void onDrag(InventoryDragEvent e) { if (e.getView().getTopInventory().getHolder() instanceof Menu) e.setCancelled(true); }

    void buy(Player p, boolean key) {
        double price = key ? keyPrice : casePrice;
        Economy eco = eco();
        if (eco == null) { CrispyFactions.msg(p, "&cThe economy isn't available right now."); return; }
        if (!eco.has(p, price)) { CrispyFactions.msg(p, "&cYou need " + money(price) + "."); return; }
        if (!eco.withdrawPlayer(p, price).transactionSuccess()) { CrispyFactions.msg(p, "&cPayment failed."); return; }
        give(p, key ? keyItem(1) : caseItem(1));
        CrispyFactions.msg(p, "Bought a " + (key ? "&eCase Key" : "&6Crispy Case") + " &7for &a" + money(price) + "&7.");
        p.playSound(p.getLocation(), Sound.ENTITY_EXPERIENCE_ORB_PICKUP, 0.6f, 1.2f);
    }

    @EventHandler(priority = EventPriority.HIGH)
    public void onUse(PlayerInteractEvent e) {
        if (e.getHand() != EquipmentSlot.HAND || (e.getAction() != Action.RIGHT_CLICK_AIR && e.getAction() != Action.RIGHT_CLICK_BLOCK)) return;
        ItemStack it = e.getItem();
        boolean isCase = has(it, K_CASE);
        if (!isCase && !has(it, K_KEY)) return;
        e.setCancelled(true);
        if (isCase) openPreview(e.getPlayer()); else openShop(e.getPlayer());
    }
    @EventHandler(priority = EventPriority.LOWEST, ignoreCancelled = true)
    public void onPlace(BlockPlaceEvent e) { if (has(e.getItemInHand(), K_CASE) || has(e.getItemInHand(), K_KEY)) e.setCancelled(true); }

    @EventHandler(priority = EventPriority.MONITOR)
    public void onMobDeath(EntityDeathEvent e) {
        if (!enabled || !(e.getEntity() instanceof Monster mob) || mob.getKiller() == null) return;
        if (mob.getEntitySpawnReason() == CreatureSpawnEvent.SpawnReason.SPAWNER) return;   // no case farming on spawners
        if (ThreadLocalRandom.current().nextDouble() >= dropChance) return;
        e.getDrops().add(caseItem(1));
        Player k = mob.getKiller();
        CrispyFactions.msg(k, "&6A Crispy Case dropped! &7Open it with a key from &f/cases&7.");
        k.playSound(k.getLocation(), Sound.BLOCK_NOTE_BLOCK_PLING, 1f, 1.4f);
    }

    @EventHandler(priority = EventPriority.MONITOR)
    public void onKill(PlayerDeathEvent e) {
        Player k = e.getEntity().getKiller();
        if (k == null || k.equals(e.getEntity())) return;
        ItemStack it = k.getInventory().getItemInMainHand();
        if (!has(it, K_ST)) return;
        ItemMeta m = it.getItemMeta(); PersistentDataContainer pdc = m.getPersistentDataContainer();
        int kills = pdc.getOrDefault(K_ST, PersistentDataType.INTEGER, 0) + 1;
        pdc.set(K_ST, PersistentDataType.INTEGER, kills);
        String[] sk = pdc.getOrDefault(K_SKIN, PersistentDataType.STRING, "|").split("\\|", 2);
        Rarity r = rarity(sk[0]);
        if (r != null) m.lore(skinLore(r, pdc.getOrDefault(K_FLOAT, PersistentDataType.DOUBLE, 0.5), kills).stream().map(Cases::text).toList());
        it.setItemMeta(m);
    }

    @EventHandler public void onQuit(PlayerQuitEvent e) { Spin s = spins.get(e.getPlayer().getUniqueId()); if (s != null) s.finish(); }

    // ------------------------------------------------------------------ command
    void command(CommandSender s, String[] a) {
        if (a.length >= 3 && a[0].equalsIgnoreCase("give") && s.hasPermission("crispy.admin")) {
            Player t = Bukkit.getPlayerExact(a[1]); if (t == null) { CrispyFactions.msg(s, "&cPlayer not online."); return; }
            int n = a.length > 3 ? Integer.parseInt(a[3]) : 1;
            give(t, a[2].equalsIgnoreCase("key") ? keyItem(n) : caseItem(n));
            CrispyFactions.msg(s, "Gave " + n + " " + a[2] + "(s) to " + t.getName()); return;
        }
        if (!(s instanceof Player p)) { CrispyFactions.msg(s, "/cases give <player> case|key [n]"); return; }
        if (!enabled) { CrispyFactions.msg(p, "&cCases are switched off."); return; }
        openShop(p);
    }
}

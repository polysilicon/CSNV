package crispy.factions;

import com.destroystokyo.paper.event.player.PlayerArmorChangeEvent;
import com.massivecraft.factions.*;
import com.massivecraft.factions.struct.Role;
import net.kyori.adventure.text.Component;
import net.kyori.adventure.text.serializer.legacy.LegacyComponentSerializer;
import net.kyori.adventure.text.serializer.plain.PlainTextComponentSerializer;
import net.kyori.adventure.title.Title;
import org.bukkit.*;
import org.bukkit.block.*;
import org.bukkit.command.*;
import org.bukkit.configuration.file.YamlConfiguration;
import org.bukkit.entity.*;
import org.bukkit.event.*;
import org.bukkit.event.block.*;
import org.bukkit.event.entity.*;
import org.bukkit.event.inventory.PrepareSmithingEvent;
import org.bukkit.event.player.*;
import org.bukkit.inventory.EquipmentSlot;
import org.bukkit.inventory.ItemStack;
import org.bukkit.inventory.meta.ItemMeta;
import org.bukkit.persistence.PersistentDataType;
import org.bukkit.plugin.java.JavaPlugin;
import org.bukkit.potion.PotionEffect;
import org.bukkit.potion.PotionEffectType;

import java.io.File;
import java.io.IOException;
import java.time.*;
import java.time.format.DateTimeFormatter;
import java.util.*;

public class CrispyFactions extends JavaPlugin implements Listener {
    static final LegacyComponentSerializer AMP = LegacyComponentSerializer.legacyAmpersand();
    static final LegacyComponentSerializer SEC = LegacyComponentSerializer.legacySection();
    static final PlainTextComponentSerializer PLAIN = PlainTextComponentSerializer.plainText();
    static final String PREFIX = "&8[&cFactions&8] &7";
    static final String STAR_PLAIN = "✦ Aegis Vacation Star (25 Raid-Hours) ✦";
    static final String STAR_NAME = "&b&l✦ Aegis Vacation Star &7(25 Raid-Hours) ✦";
    static final String COLLECTOR_PLAIN = "Cactus Collector";
    static final String COLLECTOR_NAME = "&a&lCactus Collector";
    static final DateTimeFormatter FMT = DateTimeFormatter.ofPattern("EEE MMM d, h:mm a z");

    RaidWindow raid;
    boolean scheduleOn = true;
    /** Explosions may damage claims right now (always true when the schedule is switched off). */
    boolean raidOpen() { return !scheduleOn || raid.isOpen(); }
    NamespacedKey KEY_STAR, KEY_COLLECTOR;
    File dataFile; YamlConfiguration data;
    boolean lastOpen; final Set<Integer> warned = new HashSet<>();
    // obsidian durability
    record Dmg(double amount, long last) {}
    final Map<String, Dmg> obby = new HashMap<>();
    final Map<UUID, Long> lastActive = new HashMap<>();
    CombatTag combat;

    // ------------------------------------------------------------------ lifecycle
    @Override public void onEnable() {
        saveDefaultConfig();
        KEY_STAR = new NamespacedKey(this, "aegis_star");
        KEY_COLLECTOR = new NamespacedKey(this, "cactus_collector");
        raid = new RaidWindow(getConfig().getConfigurationSection("raid-window"));
        dataFile = new File(getDataFolder(), "data.yml");
        data = YamlConfiguration.loadConfiguration(dataFile);
        raid.force = data.getString("raid-force", "auto");
        scheduleOn = getConfig().getBoolean("raid-window.enabled", true);
        lastOpen = raidOpen();
        getServer().getPluginManager().registerEvents(this, this);
        combat = new CombatTag(this);
        getServer().getPluginManager().registerEvents(combat, this);
        Bukkit.getScheduler().runTaskTimer(this, this::tickWindow, 100L, 20L * 20);
        Bukkit.getScheduler().runTaskTimer(this, this::tickAegis, 20L * 60, 20L * 60);
        Bukkit.getScheduler().runTaskTimer(this, this::tickAfk, 20L * 60, 20L * 60);
        Bukkit.getScheduler().runTaskTimer(this, this::tickPhase2, 20L * 30, 20L * 60 * 10);
        for (Player p : Bukkit.getOnlinePlayers()) lastActive.put(p.getUniqueId(), System.currentTimeMillis());
        getLogger().info("Raid window is " + (lastOpen ? "OPEN" : "closed") + " (" + raid.zone + ")");
    }
    @Override public void onDisable() { save(); }
    void save() { try { data.save(dataFile); } catch (IOException e) { getLogger().warning("save failed: " + e); } }

    static Component c(String s) { return AMP.deserialize(s); }
    static void msg(CommandSender s, String m) { s.sendMessage(c(PREFIX + m)); }
    static void bc(String m) { Bukkit.broadcast(c(PREFIX + m)); }

    // ------------------------------------------------------------------ factions helpers
    static Faction factionAt(Location l) { return Board.getInstance().getFactionAt(new FLocation(l)); }
    static FPlayer fp(Player p) { return FPlayers.getInstance().getByPlayer(p); }
    static boolean claimed(Faction f) { return f != null && f.isNormal(); }

    // ------------------------------------------------------------------ raid window
    String fmt(ZonedDateTime t) { return t == null ? "never" : t.format(FMT); }

    void tickWindow() {
        if (!scheduleOn) return;
        boolean open = raid.isOpen();
        if (open != lastOpen) {
            lastOpen = open; warned.clear();
            Title t = open ? Title.title(c("&c&lRAID WINDOW OPEN"), c("&7TNT & creepers now damage claims until " + raid.closesAt(raid.now()).toLocalTime()))
                           : Title.title(c("&a&lPEACETIME"), c("&7Claims are safe from explosions"));
            for (Player p : Bukkit.getOnlinePlayers()) { p.showTitle(t); p.playSound(p.getLocation(), open ? Sound.ENTITY_WITHER_SPAWN : Sound.BLOCK_BEACON_ACTIVATE, 0.6f, 1f); }
            bc(open ? "&c&lThe raid window is now OPEN. &7Explosions damage faction claims until &e" + fmt(raid.closesAt(raid.now()))
                    : "&a&lThe raid window has CLOSED. &7Claims are protected until &e" + fmt(raid.nextOpen(raid.now())));
        }
        if (!open && raid.force.equals("auto")) {
            ZonedDateTime nx = raid.nextOpen(raid.now());
            if (nx != null) {
                long min = Duration.between(raid.now(), nx).toMinutes();
                for (int w : new int[]{60, 15, 5, 1}) if (min < w && min >= w - 1 && warned.add(w)) bc("&eThe raid window opens in &c" + w + " minute" + (w > 1 ? "s" : "") + "&e!");
            }
        }
    }

    /** True when explosions must not touch this claim right now. */
    boolean claimProtected(Faction f) {
        if (!claimed(f)) return false;
        return !raidOpen() || aegisActive(f.getId());
    }

    @EventHandler(priority = EventPriority.HIGH, ignoreCancelled = true)
    public void onEntityExplode(EntityExplodeEvent e) { handleExplosion(e.getLocation(), e.blockList(), e.getEntity()); }
    @EventHandler(priority = EventPriority.HIGH, ignoreCancelled = true)
    public void onBlockExplode(BlockExplodeEvent e) { handleExplosion(e.getBlock().getLocation(), e.blockList(), null); }

    void handleExplosion(Location loc, List<Block> blocks, Entity source) {
        blocks.removeIf(b -> claimProtected(factionAt(b.getLocation())));
        for (Block b : blocks) unregisterCollector(b);
        // obsidian durability (TNT / creepers), water protects
        if (source == null || !getConfig().getBoolean("obsidian.enabled", true)) return;
        double hit;
        if (source instanceof TNTPrimed || source instanceof org.bukkit.entity.minecart.ExplosiveMinecart) hit = getConfig().getDouble("obsidian.tnt-damage", 1.0);
        else if (source instanceof Creeper cr) hit = getConfig().getDouble("obsidian.creeper-damage", 5.0 / 3.0) * (cr.isPowered() ? 2 : 1);
        else return;
        Block origin = loc.getBlock();
        if (origin.isLiquid() || isWaterlogged(origin)) return;             // TNT that lands in water does nothing
        double durability = getConfig().getDouble("obsidian.durability", 5.0);
        int r = getConfig().getInt("obsidian.radius", 3);
        long now = System.currentTimeMillis(), reset = getConfig().getLong("obsidian.reset-minutes", 30) * 60_000L;
        Set<Material> types = EnumSet.noneOf(Material.class);
        for (String m : getConfig().getStringList("obsidian.blocks")) { Material mm = Material.matchMaterial(m); if (mm != null) types.add(mm); }
        for (int dx = -r; dx <= r; dx++) for (int dy = -r; dy <= r; dy++) for (int dz = -r; dz <= r; dz++) {
            if (dx * dx + dy * dy + dz * dz > r * r + 1) continue;
            Block b = origin.getRelative(dx, dy, dz);
            if (!types.contains(b.getType())) continue;
            if (claimProtected(factionAt(b.getLocation()))) continue;
            if (fluidAdjacent(b)) continue;
            String k = b.getWorld().getName() + ":" + b.getX() + ":" + b.getY() + ":" + b.getZ();
            Dmg old = obby.get(k);
            double amt = (old == null || now - old.last > reset ? 0 : old.amount) + hit;
            if (amt >= durability - 1e-6) {
                var bd = b.getBlockData();
                obby.remove(k); b.setType(Material.AIR);
                b.getWorld().spawnParticle(Particle.BLOCK, b.getLocation().add(.5, .5, .5), 20, bd);
            } else {
                obby.put(k, new Dmg(amt, now));
                float prog = (float) Math.min(0.95, amt / durability);
                for (Player p : b.getWorld().getPlayers()) if (p.getLocation().distanceSquared(b.getLocation()) < 64 * 64) p.sendBlockDamage(b.getLocation(), prog, b.hashCode());
            }
        }
    }
    static boolean isWaterlogged(Block b) { return b.getBlockData() instanceof org.bukkit.block.data.Waterlogged w && w.isWaterlogged(); }
    static boolean fluidAdjacent(Block b) {
        for (BlockFace f : new BlockFace[]{BlockFace.UP, BlockFace.DOWN, BlockFace.NORTH, BlockFace.SOUTH, BlockFace.EAST, BlockFace.WEST}) {
            Block n = b.getRelative(f);
            if (n.isLiquid() || isWaterlogged(n)) return true;
        }
        return false;
    }

    // ------------------------------------------------------------------ Aegis Vacation Star
    ItemStack star(int amount) {
        ItemStack it = new ItemStack(Material.NETHER_STAR, amount);
        ItemMeta m = it.getItemMeta();
        m.displayName(c(STAR_NAME).decoration(net.kyori.adventure.text.format.TextDecoration.ITALIC, false));
        m.lore(List.of(c("&7Right-click inside your claim as &fLeader&7/&fCo-Leader"), c("&7during peacetime to bank &b25 raid-window hours"),
                c("&7of explosion protection for your faction."), c("&8Only ticks while the raid window is open."), c("&8While active your faction cannot raid.")));
        m.setEnchantmentGlintOverride(true);
        m.getPersistentDataContainer().set(KEY_STAR, PersistentDataType.BYTE, (byte) 1);
        it.setItemMeta(m); return it;
    }
    ItemStack collector(int amount) {
        ItemStack it = new ItemStack(Material.HOPPER, amount);
        ItemMeta m = it.getItemMeta();
        m.displayName(c(COLLECTOR_NAME).decoration(net.kyori.adventure.text.format.TextDecoration.ITALIC, false));
        m.lore(List.of(c("&7Collects every cactus that drops in its chunk."), c("&8One per chunk.")));
        m.getPersistentDataContainer().set(KEY_COLLECTOR, PersistentDataType.BYTE, (byte) 1);
        it.setItemMeta(m); return it;
    }
    /** The item from /kit or the plugin carries a PDC tag; the /shop copy is recognised by its coloured name (anvils can't add colour). */
    boolean isSpecial(ItemStack it, Material type, NamespacedKey key, String plain, String colour) {
        if (it == null || it.getType() != type || !it.hasItemMeta()) return false;
        ItemMeta m = it.getItemMeta();
        if (m.getPersistentDataContainer().has(key)) return true;
        Component n = m.displayName();
        return n != null && PLAIN.serialize(n).equals(plain) && SEC.serialize(n).contains(colour);
    }
    boolean isStar(ItemStack it) { return isSpecial(it, Material.NETHER_STAR, KEY_STAR, STAR_PLAIN, "§b"); }
    boolean isCollector(ItemStack it) { return isSpecial(it, Material.HOPPER, KEY_COLLECTOR, COLLECTOR_PLAIN, "§a"); }

    String fpath(String fid) { return "aegis." + fid; }
    boolean aegisActive(String fid) { return data.getLong(fpath(fid) + ".remaining", 0) > 0; }

    void tickAegis() {
        if (!raidOpen()) return;
        var sec = data.getConfigurationSection("aegis");
        if (sec == null) return;
        boolean changed = false;
        for (String fid : sec.getKeys(false)) {
            long rem = sec.getLong(fid + ".remaining", 0);
            if (rem <= 0) continue;
            rem -= 60; changed = true;
            if (rem <= 0) {
                sec.set(fid + ".remaining", 0);
                sec.set(fid + ".cooldown-until", System.currentTimeMillis() + getConfig().getLong("aegis.cooldown-days", 14) * 86_400_000L);
                Faction f = Factions.getInstance().getFactionById(fid);
                if (f != null) for (Player p : f.getOnlinePlayers()) msg(p, "&cYour faction's Aegis Vacation Star has expired. &7Claims are raidable during raid windows again.");
            } else sec.set(fid + ".remaining", rem);
        }
        if (changed) save();
    }

    @EventHandler(priority = EventPriority.HIGH)
    public void onUseStar(PlayerInteractEvent e) {
        if (e.getHand() != EquipmentSlot.HAND || !(e.getAction() == org.bukkit.event.block.Action.RIGHT_CLICK_AIR || e.getAction() == org.bukkit.event.block.Action.RIGHT_CLICK_BLOCK)) return;
        ItemStack it = e.getItem();
        if (!isStar(it)) return;
        e.setCancelled(true);
        Player p = e.getPlayer(); FPlayer f = fp(p); Faction fac = f == null ? null : f.getFaction();
        if (fac == null || !fac.isNormal()) { msg(p, "&cYou need to be in a faction."); return; }
        if (f.getRole() != Role.LEADER && f.getRole() != Role.COLEADER) { msg(p, "&cOnly the faction Leader or a Co-Leader can activate an Aegis Star."); return; }
        if (factionAt(p.getLocation()) != fac) { msg(p, "&cStand inside your own faction's claim to activate it."); return; }
        if (scheduleOn) {
            if (raid.isOpen()) { msg(p, "&cYou can't activate an Aegis Star during a raid window."); return; }
            ZonedDateTime nx = raid.nextOpen(raid.now());
            long bufH = getConfig().getLong("aegis.no-activation-hours-before-window", 6);
            if (nx != null && Duration.between(raid.now(), nx).toMinutes() < bufH * 60) {
                msg(p, "&cToo close to the next raid window (&e" + fmt(nx) + "&c). Aegis Stars can't be activated within " + bufH + " hours of a window opening."); return;
            }
        }
        String fid = fac.getId();
        if (aegisActive(fid)) { msg(p, "&cYour faction already has an active Aegis Star (&e" + hours(data.getLong(fpath(fid) + ".remaining")) + "&c left)."); return; }
        long cd = data.getLong(fpath(fid) + ".cooldown-until", 0);
        if (cd > System.currentTimeMillis()) { msg(p, "&cYour faction can activate another Aegis Star in &e" + days(cd - System.currentTimeMillis()) + "&c."); return; }
        long secs = getConfig().getLong("aegis.raid-hours", 25) * 3600L;
        data.set(fpath(fid) + ".remaining", secs); data.set(fpath(fid) + ".activated-by", p.getName()); data.set(fpath(fid) + ".activated-at", System.currentTimeMillis());
        save();
        it.setAmount(it.getAmount() - 1);
        p.getWorld().playSound(p.getLocation(), Sound.BLOCK_BEACON_POWER_SELECT, 1f, 1.2f);
        p.getWorld().spawnParticle(Particle.END_ROD, p.getLocation().add(0, 1, 0), 80, 1, 1, 1, 0.05);
        for (Player m : fac.getOnlinePlayers()) msg(m, "&b&l✦ Aegis Vacation Star activated by &f" + p.getName() + "&b&l! &7Your claims are protected for &b" + getConfig().getLong("aegis.raid-hours", 25)
                + (scheduleOn ? " raid-window hours" : " hours") + "&7. &cWhile active, your faction cannot raid.");
        bc("&b" + fac.getTag() + " &7is on vacation (Aegis Vacation Star).");
    }
    static String hours(long secs) { return String.format("%.1fh", secs / 3600.0); }
    static String days(long ms) { long h = ms / 3_600_000L; return (h / 24) + "d " + (h % 24) + "h"; }

    boolean aegisMember(Player p) { FPlayer f = fp(p); return f != null && f.getFaction() != null && f.getFaction().isNormal() && aegisActive(f.getFaction().getId()); }
    boolean enemyClaim(Player p, Location l) { Faction at = factionAt(l); FPlayer f = fp(p); return claimed(at) && (f == null || at != f.getFaction()); }

    // Two-way pacifism lock
    @EventHandler(priority = EventPriority.HIGH, ignoreCancelled = true)
    public void onTntPrime(TNTPrimeEvent e) {
        if (e.getPrimingEntity() instanceof Player p && aegisMember(p) && enemyClaim(p, e.getBlock().getLocation())) {
            e.setCancelled(true); msg(p, "&cYour faction is on Aegis vacation: you can't ignite TNT in enemy territory.");
        }
    }
    @EventHandler(priority = EventPriority.HIGH, ignoreCancelled = true)
    public void onDispense(BlockDispenseEvent e) {
        Material m = e.getItem().getType();
        if (m != Material.TNT && m != Material.CREEPER_SPAWN_EGG) return;
        Faction at = factionAt(e.getBlock().getLocation());
        if (claimed(at) && aegisActive(at.getId())) e.setCancelled(true);   // no cannons fired from an Aegis faction's land
    }
    @EventHandler(priority = EventPriority.HIGH, ignoreCancelled = true)
    public void onEgg(PlayerInteractEvent e) {
        if (e.getItem() == null || e.getItem().getType() != Material.CREEPER_SPAWN_EGG || e.getClickedBlock() == null) return;
        if (aegisMember(e.getPlayer()) && enemyClaim(e.getPlayer(), e.getClickedBlock().getLocation())) {
            e.setCancelled(true); msg(e.getPlayer(), "&cYour faction is on Aegis vacation: you can't place creepers in enemy territory.");
        }
    }

    // /kit aegis
    @EventHandler(priority = EventPriority.LOWEST)
    public void onKit(PlayerCommandPreprocessEvent e) {
        String m = e.getMessage().toLowerCase(Locale.ROOT).trim().replaceAll("\\s+", " ");
        if (!(m.equals("/kit aegis") || m.equals("/ekit aegis") || m.equals("/essentials:kit aegis") || m.equals("/essentials:ekit aegis"))) return;
        e.setCancelled(true);
        Player p = e.getPlayer();
        double hrs = p.getStatistic(Statistic.PLAY_ONE_MINUTE) / 20.0 / 3600.0, need = getConfig().getDouble("aegis.kit.min-playtime-hours", 10);
        if (hrs < need) { msg(p, "&cYou need &e" + (int) need + "h &cof playtime for the free Aegis Star (you have &e" + String.format("%.1f", hrs) + "h&c)."); return; }
        LocalDate anchor = LocalDate.parse(getConfig().getString("aegis.kit.first-friday", "2026-10-16"));
        ZonedDateTime start = anchor.atStartOfDay(raid.zone), now = raid.now();
        if (now.isBefore(start)) { msg(p, "&cThe first free Aegis Star drop is on &e" + fmt(start) + "&c."); return; }
        long cycle = Duration.between(start, now).toDays() / 14;
        String path = "kit-claims." + p.getUniqueId();
        if (data.getLong(path, -1) == cycle) {
            msg(p, "&cYou've already claimed this cycle's Aegis Star. Next drop: &e" + fmt(start.plusDays(14 * (cycle + 1)))); return;
        }
        data.set(path, cycle); save();
        p.getInventory().addItem(star(1)).values().forEach(left -> p.getWorld().dropItemNaturally(p.getLocation(), left));
        msg(p, "&bYou received this cycle's free &lAegis Vacation Star&b! &7Next drop: &e" + fmt(start.plusDays(14 * (cycle + 1))));
    }

    // ------------------------------------------------------------------ cactus collector hopper
    static String bkey(Block b) { return b.getWorld().getName() + ":" + b.getX() + ":" + b.getY() + ":" + b.getZ(); }
    static String ckey(Chunk ch) { return ch.getWorld().getName() + ":" + ch.getX() + ":" + ch.getZ(); }
    @EventHandler(priority = EventPriority.MONITOR, ignoreCancelled = true)
    public void onPlaceCollector(BlockPlaceEvent e) {
        if (!isCollector(e.getItemInHand())) return;
        String ck = ckey(e.getBlock().getChunk());
        if (data.contains("collectors." + ck)) {
            Block old = blockFromKey(data.getString("collectors." + ck));
            if (old != null && old.getType() == Material.HOPPER) { e.setCancelled(true); msg(e.getPlayer(), "&cThis chunk already has a Cactus Collector."); return; }
        }
        data.set("collectors." + ck, bkey(e.getBlock())); save();
        if (e.getBlock().getState() instanceof Hopper h) { h.customName(c(COLLECTOR_NAME)); h.update(); }
        msg(e.getPlayer(), "&aCactus Collector placed. &7It collects every cactus that drops in this chunk.");
    }
    Block blockFromKey(String k) {
        if (k == null) return null; String[] p = k.split(":"); World w = Bukkit.getWorld(p[0]);
        return w == null ? null : w.getBlockAt(Integer.parseInt(p[1]), Integer.parseInt(p[2]), Integer.parseInt(p[3]));
    }
    void unregisterCollector(Block b) {
        if (b.getType() != Material.HOPPER) return;
        String ck = ckey(b.getChunk());
        if (bkey(b).equals(data.getString("collectors." + ck))) { data.set("collectors." + ck, null); save(); }
    }
    @EventHandler(priority = EventPriority.MONITOR, ignoreCancelled = true)
    public void onBreakCollector(BlockBreakEvent e) {
        Block b = e.getBlock();
        if (b.getType() != Material.HOPPER || !bkey(b).equals(data.getString("collectors." + ckey(b.getChunk())))) return;
        unregisterCollector(b);
        e.setDropItems(false);
        b.getWorld().dropItemNaturally(b.getLocation().add(.5, .5, .5), collector(1));
    }
    @EventHandler(priority = EventPriority.HIGH, ignoreCancelled = true)
    public void onItemSpawn(ItemSpawnEvent e) {
        ItemStack it = e.getEntity().getItemStack();
        if (it.getType() != Material.CACTUS) return;
        String k = data.getString("collectors." + ckey(e.getLocation().getChunk()));
        if (k == null) return;
        Block b = blockFromKey(k);
        if (b == null || !(b.getState(false) instanceof Hopper h)) return;
        var left = h.getInventory().addItem(it);
        if (left.isEmpty()) e.setCancelled(true); else e.getEntity().setItemStack(left.values().iterator().next());
    }

    // ------------------------------------------------------------------ 1.8-era item rules
    static boolean banned(Material m) {
        String n = m.name();
        return m == Material.MACE || m == Material.TRIDENT || n.startsWith("NETHERITE_") && !n.equals("NETHERITE_SCRAP") && !n.equals("NETHERITE_INGOT") && !n.equals("NETHERITE_BLOCK") && !n.equals("NETHERITE_UPGRADE_SMITHING_TEMPLATE");
    }
    @EventHandler(priority = EventPriority.HIGH, ignoreCancelled = true)
    public void onPvp(EntityDamageByEntityEvent e) {
        if (!(e.getEntity() instanceof Player)) return;
        Entity d = e.getDamager();
        if (d instanceof EnderCrystal || d instanceof Trident) { e.setCancelled(true); return; }
        if (d instanceof Player a && banned(a.getInventory().getItemInMainHand().getType())) {
            e.setCancelled(true); msg(a, "&cThat weapon is disabled in PvP on this server (1.8 combat).");
        }
    }
    @EventHandler(ignoreCancelled = true)
    public void onTrident(ProjectileLaunchEvent e) { if (e.getEntity() instanceof Trident) e.setCancelled(true); }
    @EventHandler(ignoreCancelled = true)
    public void onGlide(EntityToggleGlideEvent e) { if (e.isGliding()) { e.setCancelled(true); if (e.getEntity() instanceof Player p) msg(p, "&cElytras are disabled."); } }
    @EventHandler(ignoreCancelled = true)
    public void onTotem(EntityResurrectEvent e) { if (e.getEntity() instanceof Player) e.setCancelled(true); }
    @EventHandler
    public void onSmith(PrepareSmithingEvent e) { if (e.getResult() != null && e.getResult().getType().name().startsWith("NETHERITE_")) e.setResult(null); }
    @EventHandler(ignoreCancelled = true)
    public void onCrystal(PlayerInteractEvent e) {
        if (e.getItem() != null && e.getItem().getType() == Material.END_CRYSTAL && e.getPlayer().getWorld().getEnvironment() != World.Environment.THE_END) {
            e.setCancelled(true); msg(e.getPlayer(), "&cEnd crystals can only be placed in the End.");
        }
    }
    @EventHandler
    public void onArmor(PlayerArmorChangeEvent e) {
        Material m = e.getNewItem().getType();
        if (m != Material.ELYTRA && !m.name().startsWith("NETHERITE_")) return;
        Player p = e.getPlayer();
        Bukkit.getScheduler().runTask(this, () -> {
            var inv = p.getInventory();
            ItemStack[] armor = inv.getArmorContents();
            for (int i = 0; i < armor.length; i++) {
                ItemStack a = armor[i];
                if (a != null && (a.getType() == Material.ELYTRA || a.getType().name().startsWith("NETHERITE_"))) {
                    armor[i] = null;
                    inv.addItem(a).values().forEach(left -> p.getWorld().dropItemNaturally(p.getLocation(), left));
                }
            }
            inv.setArmorContents(armor);
            msg(p, "&cElytras and netherite armour can't be worn here (1.8-era PvP).");
        });
    }

    // ------------------------------------------------------------------ AFK kick (ranks get 2h)
    @EventHandler public void onMove(PlayerMoveEvent e) { if (e.hasChangedOrientation() || e.hasChangedBlock()) lastActive.put(e.getPlayer().getUniqueId(), System.currentTimeMillis()); }
    @EventHandler public void onChat(AsyncPlayerChatEvent e) { lastActive.put(e.getPlayer().getUniqueId(), System.currentTimeMillis()); }
    @EventHandler public void onJoin(PlayerJoinEvent e) { lastActive.put(e.getPlayer().getUniqueId(), System.currentTimeMillis()); }
    @EventHandler public void onQuit(PlayerQuitEvent e) { lastActive.remove(e.getPlayer().getUniqueId()); }
    void tickAfk() {
        long now = System.currentTimeMillis();
        for (Player p : Bukkit.getOnlinePlayers()) {
            if (p.hasPermission("crispy.afk.exempt")) continue;
            long lim = (p.hasPermission("crispy.afk.extended") ? getConfig().getLong("afk.rank-minutes", 120) : getConfig().getLong("afk.default-minutes", 30)) * 60_000L;
            if (now - lastActive.getOrDefault(p.getUniqueId(), now) > lim) p.kick(c("&cKicked for being AFK too long."));
        }
    }

    // ------------------------------------------------------------------ Phase 2 (day 11) shop unlock
    void tickPhase2() {
        if (data.getBoolean("phase2-unlocked", false)) return;
        LocalDate launch = LocalDate.parse(getConfig().getString("phase2.launch-date", "2026-10-16"));
        if (raid.now().isBefore(launch.plusDays(getConfig().getLong("phase2.unlock-after-days", 10)).atStartOfDay(raid.zone))) return;
        unlockPhase2();
    }
    void unlockPhase2() {
        File f = new File(getDataFolder().getParentFile(), "EconomyShopGUI/sections/Phase2.yml");
        if (f.exists()) {
            YamlConfiguration y = YamlConfiguration.loadConfiguration(f);
            y.set("enable", true);
            try { y.save(f); } catch (IOException ex) { getLogger().warning("phase2: " + ex); return; }
            for (String cmd : getConfig().getStringList("phase2.reload-commands")) Bukkit.dispatchCommand(Bukkit.getConsoleSender(), cmd);
        }
        data.set("phase2-unlocked", true); save();
        bc("&6&lPHASE 2 UNLOCKED! &eIron Golem spawners are now in &f/shop&e and iron ingots sell for &a$" + getConfig().getInt("phase2.iron-sell", 40) + "&e each.");
    }

    // ------------------------------------------------------------------ commands
    @Override
    public boolean onCommand(CommandSender s, Command cmd, String label, String[] a) {
        switch (cmd.getName().toLowerCase(Locale.ROOT)) {
            case "raidwindow" -> {
                if (!scheduleOn) { msg(s, "&cRaids are allowed at any time &7(the raid schedule is switched off)."); return true; }
                if (a.length == 2 && a[0].equalsIgnoreCase("force") && s.hasPermission("crispy.admin")) {
                    raid.force = a[1].toLowerCase(Locale.ROOT); data.set("raid-force", raid.force); save(); tickWindow();
                    msg(s, "Raid window override: &e" + raid.force); return true;
                }
                ZonedDateTime now = raid.now();
                if (raid.isOpen()) msg(s, "&c&lRAID WINDOW OPEN &7until &e" + fmt(raid.closesAt(now)));
                else msg(s, "&a&lPEACETIME &7- next raid window opens &e" + fmt(raid.nextOpen(now)));
                if (!raid.force.equals("auto")) msg(s, "&8(admin override active: " + raid.force + ")");
                msg(s, "&7Weeknights &e6pm-11pm&7, weekends &enoon-midnight &7(Eastern).");
                return true;
            }
            case "aegis" -> {
                if (a.length >= 2 && a[0].equalsIgnoreCase("give") && s.hasPermission("crispy.admin")) {
                    Player t = Bukkit.getPlayerExact(a[1]); if (t == null) { msg(s, "&cPlayer not online."); return true; }
                    int n = a.length > 2 ? Integer.parseInt(a[2]) : 1;
                    t.getInventory().addItem(star(n)); msg(s, "Gave " + n + " Aegis Star(s) to " + t.getName()); return true;
                }
                if (a.length >= 2 && a[0].equalsIgnoreCase("collector") && s.hasPermission("crispy.admin")) {
                    Player t = Bukkit.getPlayerExact(a[1]); if (t == null) { msg(s, "&cPlayer not online."); return true; }
                    t.getInventory().addItem(collector(a.length > 2 ? Integer.parseInt(a[2]) : 1)); msg(s, "Gave Cactus Collector to " + t.getName()); return true;
                }
                if (a.length >= 2 && a[0].equalsIgnoreCase("reset") && s.hasPermission("crispy.admin")) {
                    Faction f = Factions.getInstance().getByTag(a[1]); if (f == null) { msg(s, "&cNo faction " + a[1]); return true; }
                    data.set(fpath(f.getId()), null); save(); msg(s, "Cleared Aegis state for " + f.getTag()); return true;
                }
                if (!(s instanceof Player p)) { msg(s, "/aegis give|collector <player> [n], /aegis reset <faction>"); return true; }
                FPlayer f = fp(p);
                if (f == null || !f.getFaction().isNormal()) { msg(p, "You're not in a faction."); return true; }
                String fid = f.getFaction().getId();
                long rem = data.getLong(fpath(fid) + ".remaining", 0), cd = data.getLong(fpath(fid) + ".cooldown-until", 0);
                if (rem > 0) msg(p, "&bAegis active: &f" + hours(rem) + " &braid-window hours left (only counts down while the window is open).");
                else if (cd > System.currentTimeMillis()) msg(p, "&7No Aegis active. Next activation allowed in &e" + days(cd - System.currentTimeMillis()));
                else msg(p, "&7No Aegis active. Your faction can activate an Aegis Star during peacetime.");
                return true;
            }
            case "combat" -> {
                if (!(s instanceof Player p)) return true;
                if (combat.tagged(p)) msg(p, "&cYou are in combat for &f" + combat.left(p) + "s &cmore. Logging out now will kill you.");
                else msg(p, "&aYou are not in combat.");
                return true;
            }
            case "nv" -> {
                if (!(s instanceof Player p)) return true;
                if (p.hasPotionEffect(PotionEffectType.NIGHT_VISION)) { p.removePotionEffect(PotionEffectType.NIGHT_VISION); msg(p, "Night vision &coff"); }
                else { p.addPotionEffect(new PotionEffect(PotionEffectType.NIGHT_VISION, PotionEffect.INFINITE_DURATION, 0, false, false, true)); msg(p, "Night vision &aon"); }
                return true;
            }
            case "crispyfactions" -> {
                if (a.length > 0 && a[0].equalsIgnoreCase("reload")) {
                    reloadConfig(); raid = new RaidWindow(getConfig().getConfigurationSection("raid-window")); raid.force = data.getString("raid-force", "auto");
                    scheduleOn = getConfig().getBoolean("raid-window.enabled", true); lastOpen = raidOpen();
                    combat.load();
                    msg(s, "Reloaded."); return true;
                }
                if (a.length > 0 && a[0].equalsIgnoreCase("phase2")) { unlockPhase2(); msg(s, "Phase 2 unlocked."); return true; }
                msg(s, "/crispyfactions reload | phase2");
                return true;
            }
        }
        return false;
    }
}

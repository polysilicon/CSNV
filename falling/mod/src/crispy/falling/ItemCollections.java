package crispy.falling;

import com.google.gson.Gson;
import com.google.gson.GsonBuilder;
import com.google.gson.reflect.TypeToken;
import net.minecraft.ChatFormatting;
import net.minecraft.core.BlockPos;
import net.minecraft.network.chat.Component;
import net.minecraft.resources.ResourceKey;
import net.minecraft.server.MinecraftServer;
import net.minecraft.server.level.ServerLevel;
import net.minecraft.server.level.ServerPlayer;
import net.minecraft.sounds.SoundEvents;
import net.minecraft.stats.Stats;
import net.minecraft.world.entity.Entity;
import net.minecraft.world.entity.item.ItemEntity;
import net.minecraft.world.entity.player.Player;
import net.minecraft.world.item.Item;
import net.minecraft.world.item.ItemStack;
import net.minecraft.world.item.Items;
import net.minecraft.world.level.Level;
import net.minecraft.world.level.block.entity.BlockEntity;
import net.minecraft.world.level.block.state.BlockState;
import net.minecraft.world.level.storage.LevelResource;

import java.nio.file.Files;
import java.nio.file.Path;
import java.util.*;

/**
 * Collections, Hypixel style: every resource you gather counts toward its collection, and each collection has nine
 * tiers (I-IX). A new tier pays coins and XP in the collection's skill. /collections (Island Menu, Guide) shows them.
 *
 * What counts: items you pick up off the ground that nobody dropped (mined, chopped, harvested, mob loot, fishing),
 * items handed straight to you in resource zones (ZoneRules), and half of what you collect from your minions (2.17.1).
 * What doesn't: anything a player dropped or lost on death (ServerPlayer.drop tags it cs_nocoll), drops from blocks a
 * player placed (Skills.Placed, so placing and breaking bought blocks can't farm it), and anything bought or crafted
 * (it goes straight into the inventory, never through a pickup).
 *
 * The first time a player joins after collections arrived, each collection starts from their vanilla "picked up"
 * statistic for that item, and the tiers that reaches pay their coins (not skill XP, so nobody gets a wall of
 * level-ups). Counts are kept in <world>/crispy_collections.json.
 */
public final class ItemCollections {
    private ItemCollections() {}

    static final String NOCOLL = "cs_nocoll";
    static final long[] BASE = {50, 100, 250, 500, 1_000, 2_500, 5_000, 10_000, 25_000};
    static final String[] ROMAN = {"", "I", "II", "III", "IV", "V", "VI", "VII", "VIII", "IX"};

    record Coll(String key, String name, Item item, Skills.Skill skill, long[] tiers) {}

    static final Map<Skills.Skill, List<Coll>> BY_SKILL = new EnumMap<>(Skills.Skill.class);
    static final Map<Item, Coll> BY_ITEM = new HashMap<>();
    static final Map<String, Coll> BY_KEY = new LinkedHashMap<>();

    static void c(Skills.Skill s, Item item, String name, double scale) {
        long[] t = new long[BASE.length];
        for (int i = 0; i < t.length; i++) t[i] = nice(BASE[i] * scale);
        String key = net.minecraft.core.registries.BuiltInRegistries.ITEM.getKey(item).getPath();
        Coll col = new Coll(key, name, item, s, t);
        BY_SKILL.computeIfAbsent(s, k -> new ArrayList<>()).add(col);
        BY_ITEM.put(item, col);
        BY_KEY.put(key, col);
    }
    /** Round to 1, 2, 2.5 or 5 times a power of ten, so thresholds read cleanly. */
    static long nice(double v) {
        if (v <= 1) return 1;
        double p = Math.pow(10, Math.floor(Math.log10(v)));
        for (double m : new double[]{1, 2, 2.5, 5, 10}) if (v <= m * p * 1.15) return Math.round(m * p);
        return Math.round(10 * p);
    }
    static {
        Skills.Skill F = Skills.Skill.FARMING, M = Skills.Skill.MINING, W = Skills.Skill.FORAGING, C = Skills.Skill.COMBAT, X = Skills.Skill.FISHING;
        c(F, Items.WHEAT, "Wheat", 1); c(F, Items.WHEAT_SEEDS, "Seeds", 1); c(F, Items.CARROT, "Carrot", 1); c(F, Items.POTATO, "Potato", 1);
        c(F, Items.BEETROOT, "Beetroot", 1); c(F, Items.PUMPKIN, "Pumpkin", 0.5); c(F, Items.MELON_SLICE, "Melon", 1); c(F, Items.SUGAR_CANE, "Sugar Cane", 1);
        c(F, Items.CACTUS, "Cactus", 1); c(F, Items.COCOA_BEANS, "Cocoa Beans", 1); c(F, Items.BAMBOO, "Bamboo", 1); c(F, Items.SWEET_BERRIES, "Sweet Berries", 1);
        c(F, Items.RED_MUSHROOM, "Red Mushroom", 0.5); c(F, Items.BROWN_MUSHROOM, "Brown Mushroom", 0.5); c(F, Items.NETHER_WART, "Nether Wart", 0.5);
        c(F, Items.FEATHER, "Feather", 0.5); c(F, Items.LEATHER, "Leather", 0.5); c(F, Items.CHICKEN, "Raw Chicken", 0.5); c(F, Items.BEEF, "Raw Beef", 0.5);
        c(F, Items.PORKCHOP, "Raw Porkchop", 0.5); c(F, Items.MUTTON, "Mutton", 0.5); c(F, Items.RABBIT_HIDE, "Rabbit Hide", 0.2); c(F, Economy.item("minecraft:white_wool"), "Wool", 0.5);
        c(M, Items.COBBLESTONE, "Cobblestone", 2); c(M, Items.COAL, "Coal", 1); c(M, Items.RAW_COPPER, "Copper", 1); c(M, Items.RAW_IRON, "Iron", 1);
        c(M, Items.RAW_GOLD, "Gold", 1); c(M, Items.LAPIS_LAZULI, "Lapis Lazuli", 1); c(M, Items.REDSTONE, "Redstone", 1); c(M, Items.DIAMOND, "Diamond", 0.5);
        c(M, Items.EMERALD, "Emerald", 0.1); c(M, Items.QUARTZ, "Nether Quartz", 0.5); c(M, Items.OBSIDIAN, "Obsidian", 0.2); c(M, Items.ANCIENT_DEBRIS, "Ancient Debris", 0.02);
        c(M, Items.SAND, "Sand", 1); c(M, Items.GRAVEL, "Gravel", 1); c(M, Items.FLINT, "Flint", 0.5); c(M, Items.CLAY_BALL, "Clay", 1);
        c(M, Items.ICE, "Ice", 0.5); c(M, Items.NETHERRACK, "Netherrack", 1); c(M, Items.END_STONE, "End Stone", 1); c(M, Items.GLOWSTONE_DUST, "Glowstone", 0.5);
        c(W, Items.OAK_LOG, "Oak", 1); c(W, Items.BIRCH_LOG, "Birch", 1); c(W, Items.SPRUCE_LOG, "Spruce", 1); c(W, Items.DARK_OAK_LOG, "Dark Oak", 1);
        c(W, Items.JUNGLE_LOG, "Jungle", 1); c(W, Items.ACACIA_LOG, "Acacia", 1); c(W, Items.CHERRY_LOG, "Cherry", 1); c(W, Items.MANGROVE_LOG, "Mangrove", 1);
        c(C, Items.ROTTEN_FLESH, "Rotten Flesh", 1); c(C, Items.BONE, "Bone", 1); c(C, Items.STRING, "String", 1); c(C, Items.SPIDER_EYE, "Spider Eye", 0.5);
        c(C, Items.GUNPOWDER, "Gunpowder", 0.5); c(C, Items.SLIME_BALL, "Slimeball", 0.5); c(C, Items.ENDER_PEARL, "Ender Pearl", 0.2); c(C, Items.BLAZE_ROD, "Blaze Rod", 0.2);
        c(C, Items.MAGMA_CREAM, "Magma Cream", 0.2); c(C, Items.GHAST_TEAR, "Ghast Tear", 0.05);
        c(X, Items.COD, "Raw Cod", 1); c(X, Items.SALMON, "Raw Salmon", 0.5); c(X, Items.TROPICAL_FISH, "Tropical Fish", 0.2); c(X, Items.PUFFERFISH, "Pufferfish", 0.2);
        c(X, Items.INK_SAC, "Ink Sac", 0.5); c(X, Items.LILY_PAD, "Lily Pad", 0.2); c(X, Items.NAUTILUS_SHELL, "Nautilus Shell", 0.02);
    }

    // 2.17.1: halved (was 100 x n^2), so collections top up an income instead of replacing it
    static long coins(int tier) { return 50L * tier * tier; }       // I: 50 ... IX: 4,050 (14,250 for a whole collection)
    static int xp(int tier) { return 20 * tier * tier; }             // I: 20 ... IX: 1,620 skill XP

    // ------------------------------------------------------------------ data
    static final class PData { Map<String, Long> count = new HashMap<>(); Map<String, Integer> tier = new HashMap<>(); boolean seeded; String name;
        Map<String, Integer> minionOdd = new HashMap<>(); }   // minion items count half: the odd one left over, per collection
    static final Gson GSON = new GsonBuilder().setPrettyPrinting().create();
    static Map<String, PData> data;
    static boolean dirty;

    static Path file(MinecraftServer server) { return server.getWorldPath(LevelResource.ROOT).resolve("crispy_collections.json"); }
    static Map<String, PData> all(MinecraftServer server) {
        if (data == null) {
            data = new HashMap<>();
            try {
                Path f = file(server);
                if (Files.exists(f)) {
                    Map<String, PData> m = GSON.fromJson(Files.readString(f), new TypeToken<Map<String, PData>>() {}.getType());
                    if (m != null) data.putAll(m);
                }
            } catch (Exception e) { System.err.println("[crispy-skyblock] can't read crispy_collections.json: " + e); }
        }
        return data;
    }
    static PData of(ServerPlayer p) {
        PData d = all(p.level().getServer()).computeIfAbsent(p.getUUID().toString(), k -> new PData());
        d.name = p.getScoreboardName();
        return d;
    }
    static void save(MinecraftServer server) {
        if (!dirty || data == null) return;
        try {
            Path f = file(server), tmp = f.resolveSibling(f.getFileName() + ".tmp");
            Files.writeString(tmp, GSON.toJson(data));
            Files.move(tmp, f, java.nio.file.StandardCopyOption.REPLACE_EXISTING, java.nio.file.StandardCopyOption.ATOMIC_MOVE);
            dirty = false;
        } catch (Exception e) { System.err.println("[crispy-skyblock] can't write crispy_collections.json: " + e); }
    }
    static long count(PData d, Coll c) { return d.count.getOrDefault(c.key, 0L); }
    static int tier(PData d, Coll c) { return d.tier.getOrDefault(c.key, 0); }

    // ------------------------------------------------------------------ counting
    /** Count n of this item toward p's collection (anything that isn't a collection item is ignored). */
    public static void add(ServerPlayer p, Item item, int n) {
        Coll c = BY_ITEM.get(item);
        if (c == null || n <= 0 || p.isCreative()) return;
        PData d = of(p);
        long now = count(d, c) + n;
        d.count.put(c.key, now);
        dirty = true;
        int t = tier(d, c);
        while (t < c.tiers.length && now >= c.tiers[t]) {
            t++;
            d.tier.put(c.key, t);
            MinecraftServer server = p.level().getServer();
            Economy.add(server, p, coins(t));
            p.sendSystemMessage(Ui.t("✦ COLLECTION ", ChatFormatting.GOLD, ChatFormatting.BOLD)
                    .append(Ui.t(c.name + " " + ROMAN[t], ChatFormatting.YELLOW, ChatFormatting.BOLD))
                    .append(Ui.t("  +" + Economy.fmt(coins(t)) + " coins · +" + xp(t) + " " + c.skill.title + " XP", ChatFormatting.GRAY)));
            p.playSound(SoundEvents.PLAYER_LEVELUP, 0.7f, 1.6f);
            Skills.gain(p, c.skill, xp(t));
        }
    }

    /** What a player collects from their minions counts at half rate, so gathering yourself is twice as fast as AFK
     *  minions. An odd item carries over to the next collect. */
    static void addFromMinion(ServerPlayer p, Item item, int n) {
        Coll c = BY_ITEM.get(item);
        if (c == null || n <= 0 || p.isCreative()) return;
        PData d = of(p);
        if (d.minionOdd == null) d.minionOdd = new HashMap<>();
        int total = n + d.minionOdd.getOrDefault(c.key, 0);
        d.minionOdd.put(c.key, total % 2);
        dirty = true;
        add(p, item, total / 2);
    }

    // pickup bookkeeping for ItemEntityMixin (playerTouch isn't re-entrant and the server is single-threaded)
    static Item touchItem; static int touchBefore; static boolean touchOk;
    public static void touchStart(ItemEntity e) {
        ItemStack s = e.getItem();
        touchItem = s.getItem(); touchBefore = s.getCount();
        touchOk = BY_ITEM.containsKey(touchItem) && !(e.getOwner() instanceof Player) && !e.entityTags().contains(NOCOLL);
    }
    public static void touchEnd(ItemEntity e, Player player) {
        if (!touchOk || !(player instanceof ServerPlayer p)) return;
        touchOk = false;
        // fully picked up: vanilla discards the entity and then puts the old count back on its stack
        int picked = e.isRemoved() ? touchBefore : touchBefore - e.getItem().getCount();
        if (picked > 0) add(p, touchItem, picked);
    }
    /** ZoneRules hands zone drops straight to the nearest player instead of a pickup. */
    static void zonePickup(ServerPlayer p, ItemEntity e, Item item, int n) {
        if (!(e.getOwner() instanceof Player) && !e.entityTags().contains(NOCOLL)) add(p, item, n);
    }
    /** From ServerPlayerMixin: anything a player drops (Q, closing a menu, on death) never counts again. */
    public static void markDropped(ItemEntity e) { if (e != null) e.addTag(NOCOLL); }

    // drops from player-placed blocks: remember where such a block is being broken, tag the items that appear there
    record Supp(ResourceKey<Level> dim, BlockPos pos, int tick) {}
    static final List<Supp> SUPP = new ArrayList<>();
    static boolean beforeBreak(Level world, Player player, BlockPos pos, BlockState state, BlockEntity be) {
        if (world instanceof ServerLevel lvl && Skills.Placed.has(lvl, pos)) SUPP.add(new Supp(lvl.dimension(), pos, lvl.getServer().getTickCount()));
        return true;
    }
    static void onEntityLoad(Entity e, ServerLevel lvl) {
        if (SUPP.isEmpty() || !(e instanceof ItemEntity ie)) return;
        int now = lvl.getServer().getTickCount();
        for (Supp s : SUPP)
            if (s.dim == lvl.dimension() && now - s.tick <= 1 && ie.distanceToSqr(s.pos.getX() + 0.5, s.pos.getY() + 0.5, s.pos.getZ() + 0.5) <= 2.25) { ie.addTag(NOCOLL); return; }
    }

    static int ticks;
    static void onTick(MinecraftServer server) {
        if (!SUPP.isEmpty()) { int now = server.getTickCount(); SUPP.removeIf(s -> now - s.tick > 1); }
        if (++ticks % 1200 == 0) save(server);   // once a minute
    }

    /** First join after collections arrived: start each collection from the vanilla picked-up stat. */
    static void onJoin(ServerPlayer p) {
        PData d = of(p);
        if (d.seeded) return;
        d.seeded = true; dirty = true;
        long coins = 0; int tiers = 0;
        for (Coll c : BY_KEY.values()) {
            int seen = p.getStats().getValue(Stats.ITEM_PICKED_UP, c.item);
            if (seen <= count(d, c)) continue;
            d.count.put(c.key, (long) seen);
            int t = tier(d, c);
            while (t < c.tiers.length && seen >= c.tiers[t]) { t++; coins += coins(t); tiers++; }
            d.tier.put(c.key, t);
        }
        if (coins > 0) Economy.add(p.level().getServer(), p, coins);
        p.sendSystemMessage(Ui.t("✦ NEW: Collections! ", ChatFormatting.GOLD, ChatFormatting.BOLD).append(Ui.t(tiers > 0
                ? "What you've gathered so far already unlocked " + tiers + " tier" + (tiers == 1 ? "" : "s") + " (+" + Economy.fmt(coins) + " coins). "
                : "Everything you gather now counts toward a collection. ", ChatFormatting.YELLOW)).append(Ui.t("/collections", ChatFormatting.AQUA)));
    }

    // ------------------------------------------------------------------ menus
    static final int[] GRID = {10, 11, 12, 13, 14, 15, 16, 19, 20, 21, 22, 23, 24, 25, 28, 29, 30, 31, 32, 33, 34, 37, 38, 39, 40, 41, 42, 43};

    static int command(net.minecraft.commands.CommandSourceStack src) throws com.mojang.brigadier.exceptions.CommandSyntaxException {
        open(src.getPlayerOrException()); return 1;
    }

    static void open(ServerPlayer p) {
        Ui.open(p, Ui.t("Collections", ChatFormatting.DARK_GRAY), 5, m -> {
            PData d = of(p);
            int got = 0, max = 0;
            for (Coll c : BY_KEY.values()) { got += tier(d, c); max += c.tiers.length; }
            m.put(4, Ui.item(Items.PAINTING, Ui.t("Collections", ChatFormatting.GOLD, ChatFormatting.BOLD), List.of(
                    Ui.t("Gather resources to unlock tiers.", ChatFormatting.GRAY),
                    Ui.t("Every tier pays coins and skill XP.", ChatFormatting.GRAY), Component.empty(),
                    Ui.t("Tiers unlocked: ", ChatFormatting.GRAY).append(Ui.t(got + " / " + max, ChatFormatting.YELLOW)),
                    bar(got, max)), true), null);
            int[] slots = {20, 21, 22, 23, 24};
            Skills.Skill[] all = Skills.Skill.values();
            for (int i = 0; i < all.length; i++) {
                Skills.Skill s = all[i];
                List<Coll> list = BY_SKILL.getOrDefault(s, List.of());
                int g = 0, mx = 0, maxed = 0;
                for (Coll c : list) { int t = tier(d, c); g += t; mx += c.tiers.length; if (t == c.tiers.length) maxed++; }
                m.put(slots[i], Ui.item(s.icon, Ui.t(s.title + " Collections", s.color, ChatFormatting.BOLD), List.of(
                        Ui.t(list.size() + " collections · " + maxed + " maxed", ChatFormatting.GRAY),
                        Ui.t("Tiers: ", ChatFormatting.GRAY).append(Ui.t(g + " / " + mx, ChatFormatting.YELLOW)), bar(g, mx),
                        Component.empty(), Ui.t("Click to view", ChatFormatting.DARK_GRAY)), false), (pl, c) -> category(pl, s));
            }
            m.put(40, Ui.item(Items.BARRIER, Ui.t("Close", ChatFormatting.RED), List.of(), false), (pl, c) -> pl.closeContainer());
        });
    }

    static void category(ServerPlayer p, Skills.Skill s) {
        Ui.open(p, Ui.t(s.title + " Collections", ChatFormatting.DARK_GRAY), 6, m -> {
            PData d = of(p);
            List<Coll> list = BY_SKILL.getOrDefault(s, List.of());
            for (int i = 0; i < list.size() && i < GRID.length; i++) {
                Coll c = list.get(i);
                long n = count(d, c); int t = tier(d, c);
                List<Component> lore = new ArrayList<>();
                lore.add(Ui.t("Collected: ", ChatFormatting.GRAY).append(Ui.t(Economy.fmt(n), ChatFormatting.YELLOW)));
                if (t < c.tiers.length) {
                    long from = t == 0 ? 0 : c.tiers[t - 1], to = c.tiers[t];
                    lore.add(Ui.t("Progress to " + c.name + " " + ROMAN[t + 1] + ": ", ChatFormatting.GRAY)
                            .append(Ui.t(Economy.fmt(n) + " / " + Economy.fmt(to), ChatFormatting.YELLOW)));
                    lore.add(bar(n - from, to - from));
                    lore.add(Ui.t("Reward: ", ChatFormatting.GRAY).append(Ui.t("+" + Economy.fmt(coins(t + 1)) + " coins · +" + xp(t + 1) + " " + s.title + " XP", ChatFormatting.GREEN)));
                } else lore.add(Ui.t("MAXED", ChatFormatting.GOLD, ChatFormatting.BOLD));
                lore.add(Component.empty());
                lore.add(Ui.t("Click to see every tier", ChatFormatting.DARK_GRAY));
                ItemStack icon = n == 0 ? new ItemStack(Economy.item("minecraft:gray_dye")) : new ItemStack(c.item);
                m.put(GRID[i], Ui.item(icon, Ui.t(c.name + (t > 0 ? " " + ROMAN[t] : ""), n == 0 ? ChatFormatting.DARK_GRAY : t == c.tiers.length ? ChatFormatting.GOLD : ChatFormatting.YELLOW,
                        ChatFormatting.BOLD), lore, t == c.tiers.length), (pl, cl) -> detail(pl, c));
            }
            m.put(48, Ui.item(Items.ARROW, Ui.t("Back", ChatFormatting.YELLOW), List.of(), false), (pl, c) -> open(pl));
            m.put(49, Ui.item(Items.BARRIER, Ui.t("Close", ChatFormatting.RED), List.of(), false), (pl, c) -> pl.closeContainer());
        });
    }

    static void detail(ServerPlayer p, Coll c) {
        Ui.open(p, Ui.t(c.name + " Collection", ChatFormatting.DARK_GRAY), 4, m -> {
            PData d = of(p);
            long n = count(d, c); int t = tier(d, c);
            m.put(4, Ui.item(new ItemStack(c.item), Ui.t(c.name + (t > 0 ? " " + ROMAN[t] : ""), ChatFormatting.YELLOW, ChatFormatting.BOLD), List.of(
                    Ui.t("Collected: ", ChatFormatting.GRAY).append(Ui.t(Economy.fmt(n), ChatFormatting.YELLOW)),
                    Ui.t("Counts: what you pick up from mining, farming,", ChatFormatting.DARK_GRAY),
                    Ui.t("mobs and fishing, and half of what your minions gather.", ChatFormatting.DARK_GRAY),
                    Ui.t("Not: bought, crafted, dropped, or from placed blocks.", ChatFormatting.DARK_GRAY)), false), null);
            for (int i = 0; i < c.tiers.length; i++) {
                boolean done = i < t;
                m.put(9 + i, Ui.item(done ? Economy.item("minecraft:lime_stained_glass_pane") : i == t ? Economy.item("minecraft:yellow_stained_glass_pane") : Economy.item("minecraft:red_stained_glass_pane"),
                        Ui.t(c.name + " " + ROMAN[i + 1], done ? ChatFormatting.GREEN : i == t ? ChatFormatting.YELLOW : ChatFormatting.RED, ChatFormatting.BOLD), List.of(
                        Ui.t("Requires " + Economy.fmt(c.tiers[i]) + " collected", ChatFormatting.GRAY),
                        Ui.t("Reward: +" + Economy.fmt(coins(i + 1)) + " coins · +" + xp(i + 1) + " " + c.skill.title + " XP", ChatFormatting.GRAY),
                        Component.empty(), done ? Ui.t("UNLOCKED", ChatFormatting.GREEN, ChatFormatting.BOLD)
                                : i == t ? Ui.t(Economy.fmt(n) + " / " + Economy.fmt(c.tiers[i]), ChatFormatting.YELLOW) : Ui.t("Locked", ChatFormatting.RED)), done), null);
            }
            m.put(31, Ui.item(Items.ARROW, Ui.t("Back", ChatFormatting.YELLOW), List.of(), false), (pl, cl) -> category(pl, c.skill));
        });
    }

    static Component bar(long have, long need) {
        int filled = need <= 0 ? 20 : (int) Math.max(0, Math.min(20, Math.round(20.0 * have / need)));
        return Ui.t("■".repeat(filled), ChatFormatting.GREEN).append(Ui.t("■".repeat(20 - filled), ChatFormatting.DARK_GRAY));
    }
}

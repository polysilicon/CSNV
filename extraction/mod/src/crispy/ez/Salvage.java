package crispy.ez;

import com.google.gson.JsonArray;
import com.google.gson.JsonObject;
import com.google.gson.JsonParser;
import net.minecraft.ChatFormatting;
import net.minecraft.core.component.DataComponents;
import net.minecraft.network.chat.Component;
import net.minecraft.server.MinecraftServer;
import net.minecraft.server.level.ServerPlayer;
import net.minecraft.world.item.ItemStack;
import net.minecraft.world.item.Items;

import java.nio.file.Files;
import java.util.*;

import static crispy.ez.Ui.t;

/**
 * Salvage Bench (1.8.16, a grindstone; zone workshops' grindstones work too). Its menu lists the armour and guns you
 * carry (not what you wear) and breaks one down per click into resources (shops.json "salvage": armour set -> outputs,
 * gun item_model -> tier -> outputs; "salvage_items": key -> SNBT). A piece worn past half its durability gives half.
 * Shift-click breaks down every carried copy of that kind.
 */
final class Salvage {
    private Salvage() {}

    record Out(String key, int n) {}
    static final Map<String, List<Out>> ARMOR = new HashMap<>(), TIER = new HashMap<>();
    static final Map<String, String> GUNS = new HashMap<>();
    static final Map<String, List<Out>> MELEE = new HashMap<>();   // 1.8.24, by ez key
    static final Map<String, ItemStack> ITEMS = new HashMap<>();

    static void load(MinecraftServer server) {
        if (!ITEMS.isEmpty()) return;
        try {
            JsonObject root = JsonParser.parseString(Files.readString(Stations.FILE)).getAsJsonObject();
            JsonObject s = root.getAsJsonObject("salvage");
            for (var e : s.getAsJsonObject("armor").entrySet()) ARMOR.put(e.getKey(), outs(e.getValue().getAsJsonArray()));
            for (var e : s.getAsJsonObject("gun_tier").entrySet()) TIER.put(e.getKey(), outs(e.getValue().getAsJsonArray()));
            for (var e : s.getAsJsonObject("guns").entrySet()) GUNS.put(e.getKey(), e.getValue().getAsString());
            if (s.has("melee")) for (var e : s.getAsJsonObject("melee").entrySet()) MELEE.put(e.getKey(), outs(e.getValue().getAsJsonArray()));
            for (var e : root.getAsJsonObject("salvage_items").entrySet()) ITEMS.put(e.getKey(), Shops.parse(server, e.getValue().getAsString()));
        } catch (Exception ex) { System.err.println("[crispy-extraction] salvage: " + ex); ARMOR.clear(); TIER.clear(); GUNS.clear(); ITEMS.clear(); }
    }
    static List<Out> outs(JsonArray a) {
        List<Out> l = new ArrayList<>();
        for (var x : a) { JsonArray p = x.getAsJsonArray(); l.add(new Out(p.get(0).getAsString().replace("ez:", ""), p.get(1).getAsInt())); }
        return l;
    }

    /** What this stack breaks down into (one item; already halved if it's badly worn), or null if it can't be salvaged. */
    static List<Out> yields(ItemStack s) {
        if (s.isEmpty()) return null;
        List<Out> base = null;
        String set = Armor.set(s);
        if (set != null) base = ARMOR.get(set);
        else if (MELEE.containsKey(Shops.ezKey(s))) base = MELEE.get(Shops.ezKey(s));
        else if (Relief.isGun(s)) { String tier = GUNS.get(String.valueOf(s.get(DataComponents.ITEM_MODEL))); base = tier == null ? null : TIER.get(tier); }
        if (base == null) return null;
        if (!worn(s)) return base;
        List<Out> half = new ArrayList<>();
        for (int i = 0; i < base.size(); i++) { int n = base.get(i).n() / 2; if (i == 0) n = Math.max(1, n); if (n > 0) half.add(new Out(base.get(i).key(), n)); }
        return half;
    }
    static boolean worn(ItemStack s) { return s.isDamageableItem() && s.getDamageValue() * 2 > s.getMaxDamage(); }
    static String kind(ItemStack s) {
        String set = Armor.set(s);
        if (set != null) return "a:" + set + ":" + Armor.slot(s);
        return MELEE.containsKey(Shops.ezKey(s)) ? "m:" + Shops.ezKey(s) : "g:" + s.get(DataComponents.ITEM_MODEL);
    }
    static String describe(List<Out> outs) {
        StringBuilder b = new StringBuilder();
        for (Out o : outs) { if (b.length() > 0) b.append(", "); ItemStack it = ITEMS.get(o.key()); b.append(o.n()).append("× ").append(it == null ? o.key() : it.getHoverName().getString()); }
        return b.toString();
    }

    static void open(ServerPlayer p) {
        load(p.level().getServer());
        Ui.open(p, t("Salvage Bench", ChatFormatting.DARK_GRAY), 6, m -> {
            m.put(4, Ui.item(Items.GRINDSTONE, t("Salvage Bench", ChatFormatting.AQUA, ChatFormatting.BOLD), List.of(
                    t("Click spare armour, a gun or a blade to break it down.", ChatFormatting.GRAY),
                    t("Shift-click: every one of that kind you carry.", ChatFormatting.GRAY),
                    t("Worn armour (what you have on) is never touched.", ChatFormatting.GRAY),
                    t("Badly damaged pieces give half.", ChatFormatting.GRAY),
                    t("Sell Gun Parts and Armour Plate to the Broker,", ChatFormatting.DARK_AQUA),
                    t("or craft with them at the Reloading and Tool Benches.", ChatFormatting.DARK_AQUA)), false), null);
            var inv = p.getInventory();
            int shown = 0;
            for (int i = 0; i < 36 && shown < 36; i++) {
                ItemStack s = inv.getItem(i);
                List<Out> y = yields(s);
                if (y == null) continue;
                final int slot = i;
                List<Component> lore = new ArrayList<>();
                lore.add(t("Breaks down into:", ChatFormatting.GRAY));
                lore.add(t("  " + describe(y), ChatFormatting.GREEN));
                if (worn(s)) lore.add(t("Badly worn: half the yield", ChatFormatting.GOLD));
                lore.add(t("Click: salvage", ChatFormatting.YELLOW));
                m.put(9 + shown++, Ui.item(s.copyWithCount(1), s.getHoverName().copy(), lore, false), (pl, c) -> {
                    if (c.shift()) all(pl, kind(pl.getInventory().getItem(slot))); else one(pl, slot, true);
                });
            }
            if (shown == 0) m.put(22, Ui.item(Items.BARRIER, t("Nothing to salvage", ChatFormatting.GRAY), List.of(
                    t("Carry spare armour or guns (in your inventory,", ChatFormatting.DARK_GRAY), t("not worn) and open the bench again.", ChatFormatting.DARK_GRAY)), false), null);
            m.put(49, Ui.item(Items.BARRIER, t("Close", ChatFormatting.RED), List.of(), false), (pl, c) -> pl.closeContainer());
        });
    }

    /** Breaks down the item in inventory slot i. Returns what it gave (empty if nothing). */
    static List<Out> one(ServerPlayer p, int i, boolean tell) {
        load(p.level().getServer());
        ItemStack s = p.getInventory().getItem(i);
        List<Out> y = yields(s);
        if (y == null) return List.of();
        String name = s.getHoverName().getString();
        s.shrink(1); p.getInventory().setChanged();
        for (Out o : y) { ItemStack it = ITEMS.get(o.key()); if (it != null) Shops.give(p, it.copyWithCount(o.n())); }
        if (tell) {
            Shops.ok(p, "Salvaged " + name + ": " + describe(y) + ".");
            Ui.sound(p, net.minecraft.sounds.SoundEvents.GRINDSTONE_USE, 0.8f, 1f);
        }
        Trace.d(p, "salvage " + name);
        return y;
    }
    static void all(ServerPlayer p, String kind) {
        Map<String, Integer> got = new LinkedHashMap<>(); int n = 0;
        for (int i = 0; i < 36; i++) {
            ItemStack s = p.getInventory().getItem(i);
            if (yields(s) == null || !kind.equals(kind(s))) continue;
            while (yields(p.getInventory().getItem(i)) != null) { for (Out o : one(p, i, false)) got.merge(o.key(), o.n(), Integer::sum); n++; }
        }
        if (n == 0) return;
        List<Out> sum = new ArrayList<>(); got.forEach((k, v) -> sum.add(new Out(k, v)));
        Shops.ok(p, "Salvaged " + n + " item" + (n == 1 ? "" : "s") + ": " + describe(sum) + ".");
        Ui.sound(p, net.minecraft.sounds.SoundEvents.GRINDSTONE_USE, 0.8f, 1f);
    }
}

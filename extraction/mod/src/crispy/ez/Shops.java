package crispy.ez;

import com.google.gson.JsonArray;
import com.google.gson.JsonElement;
import com.google.gson.JsonObject;
import com.google.gson.JsonParser;
import net.fabricmc.fabric.api.event.player.UseEntityCallback;
import net.minecraft.ChatFormatting;
import net.minecraft.core.component.DataComponents;
import net.minecraft.nbt.NbtOps;
import net.minecraft.nbt.TagParser;
import net.minecraft.network.chat.Component;
import net.minecraft.server.MinecraftServer;
import net.minecraft.server.level.ServerPlayer;
import net.minecraft.sounds.SoundEvents;
import net.minecraft.sounds.SoundSource;
import net.minecraft.world.InteractionHand;
import net.minecraft.world.InteractionResult;
import net.minecraft.world.entity.player.Inventory;
import net.minecraft.world.item.ItemStack;
import net.minecraft.world.item.Items;
import net.minecraft.world.item.component.CustomData;

import java.nio.file.Files;
import java.nio.file.Path;
import java.util.ArrayList;
import java.util.HashMap;
import java.util.List;
import java.util.Map;
import java.util.function.Predicate;

import static crispy.ez.Ui.t;

/**
 * Chest-menu traders. A trader is any entity tagged ez.shop.<id> (villagers in camp and in the zone); right-click
 * opens the shop menu instead of vanilla trading. Shops, prices and the Credits item come from
 * config/crispy_extraction/shops.json, written by extraction/build.py (re-read when it changes).
 * Money is items: Credits are counted and taken from the inventory, so you can only spend what you carry.
 */
final class Shops {
    private Shops() {}

    static final Path FILE = Path.of("config", "crispy_extraction", "shops.json");
    record Buy(ItemStack item, int price) {}
    record Sell(String key, ItemStack icon, int price) {}
    record Shop(String title, List<Buy> buy, List<Sell> sell) {}

    static ItemStack credit = ItemStack.EMPTY;
    static final Map<String, Shop> SHOPS = new HashMap<>();
    static long mtime = Long.MIN_VALUE;

    static void init() {
        UseEntityCallback.EVENT.register((player, world, hand, entity, hit) -> {
            if (!(player instanceof ServerPlayer p)) return InteractionResult.PASS;
            String id = null;
            for (String tag : entity.entityTags()) if (tag.startsWith("ez.shop.")) id = tag.substring(8);
            if (id == null) return InteractionResult.PASS;
            if (hand == InteractionHand.MAIN_HAND) {
                if (id.equals("plots")) Plots.menu(p);
                else if (id.equals("contracts")) Contracts.menu(p);
                else open(p, id);
            }
            return InteractionResult.SUCCESS;
        });
    }

    static ItemStack parse(MinecraftServer server, String snbt) throws com.mojang.brigadier.exceptions.CommandSyntaxException {
        var ops = server.registryAccess().createSerializationContext(NbtOps.INSTANCE);
        return ItemStack.CODEC.parse(ops, TagParser.parseCompoundFully(snbt)).getOrThrow();
    }

    static void load(MinecraftServer server) {
        try {
            long m = Files.getLastModifiedTime(FILE).toMillis();
            if (m == mtime) return;
            JsonObject root = JsonParser.parseString(Files.readString(FILE)).getAsJsonObject();
            credit = parse(server, root.get("credit").getAsString());
            SHOPS.clear();
            for (Map.Entry<String, JsonElement> e : root.getAsJsonObject("shops").entrySet()) {
                JsonObject s = e.getValue().getAsJsonObject();
                List<Buy> buy = new ArrayList<>();
                for (JsonElement b : s.getAsJsonArray("buy")) {
                    JsonObject o = b.getAsJsonObject();
                    buy.add(new Buy(parse(server, o.get("item").getAsString()), o.get("price").getAsInt()));
                }
                List<Sell> sell = new ArrayList<>();
                JsonArray sl = s.getAsJsonArray("sell");
                if (sl != null) for (JsonElement b : sl) {
                    JsonObject o = b.getAsJsonObject();
                    sell.add(new Sell(o.get("key").getAsString(), parse(server, o.get("item").getAsString()), o.get("price").getAsInt()));
                }
                SHOPS.put(e.getKey(), new Shop(s.get("title").getAsString(), buy, sell));
            }
            mtime = m;
        } catch (Exception ex) {
            System.err.println("[crispy-extraction] can't load " + FILE + ": " + ex);
        }
    }

    // ---------------------------------------------------------------- money
    static boolean isCredit(ItemStack s) { return Coins.value(s) > 0; }   // a Gold Coin or a Coin Bag
    static String ezKey(ItemStack s) {
        CustomData cd = s.get(DataComponents.CUSTOM_DATA);
        return cd == null ? "" : cd.copyTag().getString("ez").orElse("");
    }
    static int count(ServerPlayer p, Predicate<ItemStack> f) {
        Inventory inv = p.getInventory(); int n = 0;
        for (int i = 0; i < inv.getContainerSize(); i++) { ItemStack s = inv.getItem(i); if (!s.isEmpty() && f.test(s)) n += s.getCount(); }
        return n;
    }
    static void take(ServerPlayer p, Predicate<ItemStack> f, int n) {
        Inventory inv = p.getInventory();
        for (int i = 0; i < inv.getContainerSize() && n > 0; i++) {
            ItemStack s = inv.getItem(i);
            if (s.isEmpty() || !f.test(s)) continue;
            int k = Math.min(n, s.getCount()); s.shrink(k); n -= k;
        }
        inv.setChanged();
    }
    static void give(ServerPlayer p, ItemStack s) {
        while (!s.isEmpty()) {
            ItemStack part = s.split(Math.max(1, Math.min(s.getCount(), s.getMaxStackSize())));
            if (!p.getInventory().add(part)) p.drop(part, false);
        }
    }
    static int credits(ServerPlayer p) { return Coins.count(p); }
    static boolean pay(ServerPlayer p, int price) { return Coins.take(p, price); }
    static void giveCredits(ServerPlayer p, int n) { Coins.give(p, n); }
    /** Medical station on your stash plot: bandages and medkits 40% cheaper. */
    static int priceFor(ServerPlayer p, Buy b) {
        String k = ezKey(b.item);
        if ((k.equals("bandage") || k.equals("medkit")) && Plots.hasPerk(p, "med")) return Math.max(1, (int) Math.ceil(b.price * 0.6));
        return b.price;
    }

    static void ok(ServerPlayer p, String msg) {
        p.level().playSound(null, p.blockPosition(), SoundEvents.EXPERIENCE_ORB_PICKUP, SoundSource.PLAYERS, 0.6f, 1.2f);
        p.sendSystemMessage(t(msg, ChatFormatting.GREEN));
    }
    static void no(ServerPlayer p, String msg) {
        p.level().playSound(null, p.blockPosition(), SoundEvents.VILLAGER_NO, SoundSource.PLAYERS, 0.6f, 1f);
        p.sendSystemMessage(t(msg, ChatFormatting.RED));
    }

    static ItemStack balanceIcon(ServerPlayer p) {
        return Ui.item(Coins.coin.isEmpty() ? new ItemStack(Items.SUNFLOWER) : Coins.coin.copyWithCount(1),
                t("Your coins: " + credits(p), ChatFormatting.GOLD, ChatFormatting.BOLD),
                List.of(t("Gold Coins are items: only what you carry counts.", ChatFormatting.GRAY),
                        t("A Coin Bag is worth 64 coins.", ChatFormatting.GRAY)), true);
    }

    // ---------------------------------------------------------------- the menu
    static void open(ServerPlayer p, String id) {
        load(p.level().getServer());
        Shop shop = SHOPS.get(id);
        if (shop == null) { no(p, "This trader has nothing for you right now."); return; }
        Ui.open(p, t(shop.title, ChatFormatting.DARK_GRAY), 6, m -> {
            m.put(4, balanceIcon(p), null);
            for (int i = 0; i < shop.buy.size() && i < 27; i++) {
                Buy b = shop.buy.get(i);
                int price = priceFor(p, b);
                boolean bulk = b.item.getMaxStackSize() > 1;
                List<Component> lore = new ArrayList<>(b.item.getOrDefault(DataComponents.LORE, net.minecraft.world.item.component.ItemLore.EMPTY).lines());
                lore.add(t(""));
                lore.add(t("Price: " + Coins.fmt(price) + (b.item.getCount() > 1 ? " for " + b.item.getCount() : "")
                        + (price < b.price ? " (medical station)" : ""), ChatFormatting.GOLD));
                lore.add(t("Click: buy" + (bulk ? "   Shift-click: buy 5" : ""), ChatFormatting.YELLOW));
                ItemStack icon = b.item.copy();
                icon.set(DataComponents.LORE, new net.minecraft.world.item.component.ItemLore(lore.stream().map(c -> (Component) c.copy().withStyle(st -> st.withItalic(false))).toList()));
                m.put(9 + i, icon, (pl, c) -> {
                    int times = (c.shift() && bulk) ? 5 : 1;
                    if (!pay(pl, price * times)) { no(pl, "You need " + Coins.fmt(price * times) + " for that."); return; }
                    for (int k = 0; k < times; k++) give(pl, b.item.copy());
                    ok(pl, "Bought " + (times > 1 ? times + "x " : "") + b.item.getHoverName().getString() + " for " + Coins.fmt(price * times) + ".");
                });
            }
            for (int i = 0; i < shop.sell.size() && i < 9; i++) {
                Sell s = shop.sell.get(i);
                int have = count(p, st -> s.key.equals(ezKey(st)));
                m.put(36 + i, Ui.item(s.icon.copyWithCount(Math.max(1, Math.min(64, have))), t("Sell " + s.icon.getHoverName().getString(), ChatFormatting.AQUA),
                        List.of(t(Coins.fmt(s.price) + " each", ChatFormatting.GOLD), t("You have " + have, ChatFormatting.GRAY), t("Click: sell all of them", ChatFormatting.YELLOW)), false),
                        (pl, c) -> {
                            int n = count(pl, st -> s.key.equals(ezKey(st)));
                            if (n == 0) { no(pl, "You don't have any to sell."); return; }
                            take(pl, st -> s.key.equals(ezKey(st)), n);
                            giveCredits(pl, n * s.price);
                            ok(pl, "Sold " + n + "x " + s.icon.getHoverName().getString() + " for " + Coins.fmt(n * s.price) + ".");
                        });
            }
            if (!shop.sell.isEmpty()) m.put(31, Ui.item(Items.EMERALD, t("↓ Sells to this trader ↓", ChatFormatting.AQUA, ChatFormatting.BOLD),
                    List.of(t("Click an item below to sell all you carry.", ChatFormatting.GRAY)), false), null);
            coinButtons(m);
            m.put(49, Ui.item(Items.BARRIER, t("Close", ChatFormatting.RED), List.of(), false), (pl, c) -> pl.closeContainer());
        });
    }

    /** Condense loose coins into bags, or break a bag for change (slots 47 and 51 of a 6-row menu). */
    static void coinButtons(Ui.Menu m) {
        m.put(47, Ui.item(Coins.bag.isEmpty() ? new ItemStack(Items.BUNDLE) : Coins.bag.copyWithCount(1), t("Condense coins into bags", ChatFormatting.BLUE), List.of(
                t("Every 64 Gold Coins you carry", ChatFormatting.GRAY), t("become one Coin Bag.", ChatFormatting.GRAY)), false),
                (pl, c) -> { int n = Coins.condense(pl); if (n > 0) ok(pl, "Condensed into " + n + " Coin Bag" + (n == 1 ? "" : "s") + "."); else no(pl, "You need 64 loose coins for a bag."); });
        m.put(51, Ui.item(Coins.coin.isEmpty() ? new ItemStack(Items.SUNFLOWER) : Coins.coin.copyWithCount(1), t("Break a Coin Bag", ChatFormatting.GOLD), List.of(
                t("Turn one Coin Bag back into 64 coins.", ChatFormatting.GRAY), t("(Paying never needs this: change is automatic.)", ChatFormatting.DARK_GRAY)), false),
                (pl, c) -> { if (Coins.breakBag(pl)) ok(pl, "Broke a Coin Bag into 64 coins."); else no(pl, "You don't have a Coin Bag."); });
    }
}

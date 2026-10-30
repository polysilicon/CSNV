package crispy.falling;

import com.google.gson.Gson;
import com.google.gson.GsonBuilder;
import com.mojang.brigadier.CommandDispatcher;
import com.mojang.brigadier.arguments.IntegerArgumentType;
import com.mojang.brigadier.arguments.StringArgumentType;
import net.minecraft.ChatFormatting;
import net.minecraft.commands.CommandSourceStack;
import net.minecraft.commands.Commands;
import net.minecraft.core.registries.BuiltInRegistries;
import net.minecraft.nbt.CompoundTag;
import net.minecraft.nbt.ListTag;
import net.minecraft.network.chat.Component;
import net.minecraft.server.MinecraftServer;
import net.minecraft.server.level.ServerPlayer;
import net.minecraft.server.permissions.LevelBasedPermissionSet;
import net.minecraft.sounds.SoundEvents;
import net.minecraft.world.item.Item;
import net.minecraft.world.item.ItemStack;
import net.minecraft.world.item.Items;
import net.minecraft.world.level.storage.LevelResource;
import net.minecraft.world.scores.Objective;
import net.minecraft.world.scores.ScoreHolder;

import java.nio.file.Files;
import java.nio.file.Path;
import java.util.*;

import static crispy.falling.Ui.t;

/**
 * The Bazaar: players trade the shop's farmable items with each other at their own prices.
 * - Sell offers: the items are held by the Bazaar until someone buys them (or the seller cancels).
 * - Buy orders: the coins are held until someone sells into them; the items wait to be claimed in "My orders".
 * - Instant buy takes the cheapest sell offers; instant sell fills the highest buy orders. A new offer or order that
 *   crosses the book fills straight away at the waiting side's price. Sellers get paid even while offline (cs_coins by
 *   name), less a 1% tax.
 * - /bazaar (/bz) or the Bazaar NPC in the hub. Amounts and prices are typed into a dialog (/bazaar offer|order
 *   <item> <amount> <price>). Orders are kept in <world>/crispy_bazaar.json.
 */
final class Bazaar {
    private Bazaar() {}

    static final double TAX = 0.01;
    static final int MAX_ORDERS = 20;   // per player

    static final class Order {
        long id; boolean sell; String item, owner, name; int price, left, claim; long time;
    }
    static final class Book { long next = 1; List<Order> orders = new ArrayList<>(); }
    private static Book book;
    private static final Gson GSON = new GsonBuilder().setPrettyPrinting().create();

    static Path file(MinecraftServer server) { return server.getWorldPath(LevelResource.ROOT).resolve("crispy_bazaar.json"); }
    static Book book(MinecraftServer server) {
        if (book == null) {
            try { book = GSON.fromJson(Files.readString(file(server)), Book.class); } catch (Exception e) { book = null; }
            if (book == null) book = new Book();
        }
        return book;
    }
    static void save(MinecraftServer server) {
        try { Files.writeString(file(server), GSON.toJson(book(server))); } catch (Exception e) { System.err.println("[crispy_skyblock] bazaar save failed: " + e); }
    }

    static String id(Item it) { return BuiltInRegistries.ITEM.getKey(it).toString(); }
    static String nice(Item it) { return new ItemStack(it).getHoverName().getString(); }

    /** Tradeable items: everything the shop lists, in its categories. */
    static boolean tradeable(MinecraftServer server, Item it) { return it != Items.AIR && Economy.prices(server).containsKey(it); }

    static List<Order> sells(MinecraftServer server, String item) {
        return book(server).orders.stream().filter(o -> o.sell && o.left > 0 && o.item.equals(item))
                .sorted(Comparator.comparingInt((Order o) -> o.price).thenComparingLong(o -> o.time)).toList();
    }
    static List<Order> buys(MinecraftServer server, String item) {
        return book(server).orders.stream().filter(o -> !o.sell && o.left > 0 && o.item.equals(item))
                .sorted(Comparator.comparingInt((Order o) -> -o.price).thenComparingLong(o -> o.time)).toList();
    }
    static int volume(List<Order> l) { return l.stream().mapToInt(o -> o.left).sum(); }

    /** Coins to a player by name (works while they're offline). */
    static void pay(MinecraftServer server, String name, long coins) {
        Objective obj = server.getScoreboard().getObjective("cs_coins");
        if (obj == null || coins <= 0) return;
        var s = server.getScoreboard().getOrCreatePlayerScore(ScoreHolder.forNameOnly(name), obj);
        s.set((int) Math.min(Integer.MAX_VALUE, s.get() + coins));
    }
    static long afterTax(long gross) { return gross - Math.round(gross * TAX); }
    static void tell(MinecraftServer server, String uuid, Component msg) {
        try { ServerPlayer p = server.getPlayerList().getPlayer(UUID.fromString(uuid)); if (p != null) p.sendSystemMessage(msg); } catch (Exception ignored) {}
    }

    // ------------------------------------------------------------------ trading
    static void instantBuy(ServerPlayer p, Item it, int want) {
        MinecraftServer server = p.level().getServer();
        String key = id(it);
        long cost = 0; int got = 0;
        for (Order o : sells(server, key)) { int k = Math.min(o.left, want - got); cost += (long) k * o.price; got += k; if (got >= want) break; }
        if (got == 0) { p.sendSystemMessage(t("Nobody is selling " + nice(it) + " right now. Place a buy order instead.", ChatFormatting.RED)); return; }
        if (Economy.coins(server, p) < cost) { p.sendSystemMessage(t("You need " + Economy.fmt(cost) + " coins for " + got + " " + nice(it) + ".", ChatFormatting.RED)); return; }
        Economy.add(server, p, -cost);
        int left = got;
        for (Order o : sells(server, key)) {
            int k = Math.min(o.left, left);
            o.left -= k; left -= k;
            pay(server, o.name, afterTax((long) k * o.price));
            tell(server, o.owner, t("Bazaar: sold " + k + " " + nice(it) + " for " + Economy.fmt(afterTax((long) k * o.price)) + " coins.", ChatFormatting.GOLD));
            if (left == 0) break;
        }
        Economy.give(p, it, got);
        cleanup(server);
        p.sendSystemMessage(t("Bought " + got + " " + nice(it) + " for " + Economy.fmt(cost) + " coins.", ChatFormatting.GREEN));
        p.playSound(SoundEvents.EXPERIENCE_ORB_PICKUP, 0.6f, 1.4f);
    }

    static void instantSell(ServerPlayer p, Item it, int want) {
        MinecraftServer server = p.level().getServer();
        String key = id(it);
        want = Math.min(want, Economy.count(p, it));
        if (want <= 0) { p.sendSystemMessage(t("You have no " + nice(it) + " to sell.", ChatFormatting.RED)); return; }
        long earned = 0; int sold = 0;
        for (Order o : buys(server, key)) {
            int k = Math.min(o.left, want - sold);
            if (k <= 0) break;
            o.left -= k; o.claim += k; sold += k; earned += (long) k * o.price;
            tell(server, o.owner, t("Bazaar: your buy order got " + k + " " + nice(it) + ". Claim it in /bazaar > My orders.", ChatFormatting.GOLD));
        }
        if (sold == 0) { p.sendSystemMessage(t("Nobody is buying " + nice(it) + " right now. Create a sell offer instead.", ChatFormatting.RED)); return; }
        Economy.take(p, it, sold);
        Economy.add(server, p, afterTax(earned));
        cleanup(server);
        p.sendSystemMessage(t("Sold " + sold + " " + nice(it) + " for " + Economy.fmt(afterTax(earned)) + " coins (after 1% tax).", ChatFormatting.GREEN));
        p.playSound(SoundEvents.EXPERIENCE_ORB_PICKUP, 0.6f, 1.2f);
    }

    static int mine(MinecraftServer server, ServerPlayer p) {
        String u = p.getStringUUID();
        return (int) book(server).orders.stream().filter(o -> o.owner.equals(u) && (o.left > 0 || o.claim > 0)).count();
    }

    static int createSell(ServerPlayer p, Item it, int amount, int price) {
        MinecraftServer server = p.level().getServer();
        if (!tradeable(server, it) || amount <= 0 || price <= 0) { p.sendSystemMessage(t("That can't be sold on the Bazaar.", ChatFormatting.RED)); return 0; }
        if (mine(server, p) >= MAX_ORDERS) { p.sendSystemMessage(t("You have " + MAX_ORDERS + " orders already. Claim or cancel some first.", ChatFormatting.RED)); return 0; }
        int have = Economy.count(p, it);
        if (have < amount) { p.sendSystemMessage(t("You only have " + have + " " + nice(it) + ".", ChatFormatting.RED)); return 0; }
        Economy.take(p, it, amount);
        String key = id(it);
        int left = amount; long earned = 0;
        for (Order o : buys(server, key)) {   // someone already pays at least this much
            if (o.price < price || left == 0) break;
            int k = Math.min(o.left, left);
            o.left -= k; o.claim += k; left -= k; earned += (long) k * o.price;
            tell(server, o.owner, t("Bazaar: your buy order got " + k + " " + nice(it) + ". Claim it in /bazaar > My orders.", ChatFormatting.GOLD));
        }
        if (earned > 0) { Economy.add(server, p, afterTax(earned)); p.sendSystemMessage(t("Sold " + (amount - left) + " " + nice(it) + " straight away for " + Economy.fmt(afterTax(earned)) + " coins.", ChatFormatting.GREEN)); }
        if (left > 0) add(server, p, true, key, price, left);
        save(server);
        if (left > 0) p.sendSystemMessage(t("Sell offer placed: " + left + " " + nice(it) + " at " + Economy.fmt(price) + " each.", ChatFormatting.GREEN));
        return 1;
    }

    static int createBuy(ServerPlayer p, Item it, int amount, int price) {
        MinecraftServer server = p.level().getServer();
        if (!tradeable(server, it) || amount <= 0 || price <= 0) { p.sendSystemMessage(t("That can't be bought on the Bazaar.", ChatFormatting.RED)); return 0; }
        if (mine(server, p) >= MAX_ORDERS) { p.sendSystemMessage(t("You have " + MAX_ORDERS + " orders already. Claim or cancel some first.", ChatFormatting.RED)); return 0; }
        long total = (long) amount * price;
        if (!Economy.add(server, p, -total)) { p.sendSystemMessage(t("A buy order for " + amount + " at " + Economy.fmt(price) + " needs " + Economy.fmt(total) + " coins.", ChatFormatting.RED)); return 0; }
        String key = id(it);
        int left = amount; long refund = 0; int got = 0;
        for (Order o : sells(server, key)) {   // someone already sells at this price or less
            if (o.price > price || left == 0) break;
            int k = Math.min(o.left, left);
            o.left -= k; left -= k; got += k;
            refund += (long) k * (price - o.price);
            pay(server, o.name, afterTax((long) k * o.price));
            tell(server, o.owner, t("Bazaar: sold " + k + " " + nice(it) + " for " + Economy.fmt(afterTax((long) k * o.price)) + " coins.", ChatFormatting.GOLD));
        }
        if (got > 0) { Economy.give(p, it, got); Economy.add(server, p, refund); p.sendSystemMessage(t("Bought " + got + " " + nice(it) + " straight away.", ChatFormatting.GREEN)); }
        if (left > 0) add(server, p, false, key, price, left);
        save(server);
        if (left > 0) p.sendSystemMessage(t("Buy order placed: " + left + " " + nice(it) + " at " + Economy.fmt(price) + " each.", ChatFormatting.GREEN));
        return 1;
    }

    static void add(MinecraftServer server, ServerPlayer p, boolean sell, String item, int price, int amount) {
        Book b = book(server);
        Order o = new Order();
        o.id = b.next++; o.sell = sell; o.item = item; o.owner = p.getStringUUID(); o.name = p.getScoreboardName();
        o.price = price; o.left = amount; o.time = System.currentTimeMillis();
        b.orders.add(o);
    }

    static void cleanup(MinecraftServer server) {
        book(server).orders.removeIf(o -> o.left <= 0 && o.claim <= 0);
        save(server);
    }

    /** Claim a buy order's items, or cancel an order (the rest of the items or coins come back). */
    static void claimOrCancel(ServerPlayer p, Order o) {
        MinecraftServer server = p.level().getServer();
        Item it = Economy.item(o.item);
        if (o.claim > 0) {
            Economy.give(p, it, o.claim);
            p.sendSystemMessage(t("Claimed " + o.claim + " " + nice(it) + ".", ChatFormatting.GREEN));
            o.claim = 0;
        } else if (o.left > 0) {
            if (o.sell) Economy.give(p, it, o.left); else Economy.add(server, p, (long) o.left * o.price);
            p.sendSystemMessage(t("Cancelled: " + (o.sell ? o.left + " " + nice(it) + " returned." : Economy.fmt((long) o.left * o.price) + " coins refunded."), ChatFormatting.YELLOW));
            o.left = 0;
        }
        cleanup(server);
    }

    // ------------------------------------------------------------------ menus
    static final int[] GRID = {10, 11, 12, 13, 14, 15, 16, 19, 20, 21, 22, 23, 24, 25, 28, 29, 30, 31, 32, 33, 34, 37, 38, 39, 40, 41, 42, 43};

    static void open(ServerPlayer p) { openCategory(p, 0); }

    static void openCategory(ServerPlayer p, int cat) {
        MinecraftServer server = p.level().getServer();
        ListTag cats = Economy.cfg(server).getListOrEmpty("shop");
        Ui.open(p, t("Bazaar", ChatFormatting.DARK_GRAY), 6, m -> {
            for (int i = 0; i < cats.size() && i < 7; i++) {
                CompoundTag c = cats.getCompoundOrEmpty(i);
                int ci = i;
                m.put(1 + i, Ui.item(Economy.item(c.getStringOr("icon", "minecraft:chest")), t(c.getStringOr("name", "?"), ci == cat ? ChatFormatting.GREEN : ChatFormatting.YELLOW, ChatFormatting.BOLD),
                        List.of(t(ci == cat ? "You're here" : "Click to browse", ChatFormatting.GRAY)), ci == cat), (pl, c2) -> openCategory(pl, ci));
            }
            ListTag items = cats.getCompoundOrEmpty(cat).getListOrEmpty("items");
            for (int i = 0, s = 0; i < items.size() && s < GRID.length; i++) {
                Item it = Economy.item(items.getCompoundOrEmpty(i).getStringOr("id", ""));
                if (it == Items.AIR) continue;
                List<Order> sl = sells(server, id(it)), bl = buys(server, id(it));
                List<Component> lore = new ArrayList<>();
                lore.add(t("Buy price: ", ChatFormatting.GRAY).append(sl.isEmpty() ? t("none", ChatFormatting.DARK_GRAY) : t(Economy.fmt(sl.get(0).price) + " coins", ChatFormatting.GOLD)));
                lore.add(t("Sell price: ", ChatFormatting.GRAY).append(bl.isEmpty() ? t("none", ChatFormatting.DARK_GRAY) : t(Economy.fmt(bl.get(0).price) + " coins", ChatFormatting.GOLD)));
                lore.add(t(volume(sl) + " for sale · " + volume(bl) + " wanted", ChatFormatting.DARK_GRAY));
                lore.add(Component.empty()); lore.add(t("Click to trade", ChatFormatting.YELLOW));
                m.put(GRID[s++], Ui.item(it, t(nice(it), ChatFormatting.WHITE), lore, false), (pl, c2) -> openProduct(pl, it, cat));
            }
            m.put(49, Ui.item(Items.BOOK, t("My orders", ChatFormatting.GOLD, ChatFormatting.BOLD), List.of(t("Claim bought items, cancel offers", ChatFormatting.GRAY)), false), (pl, c2) -> openMine(pl));
            m.put(53, Ui.item(Items.BARRIER, t("Close", ChatFormatting.RED), List.of(), false), (pl, c2) -> pl.closeContainer());
            m.put(45, Ui.item(Items.GOLD_NUGGET, t("Purse: " + Economy.fmt(Economy.coins(server, p)) + " coins", ChatFormatting.GOLD), List.of(t("1% tax on every sale", ChatFormatting.DARK_GRAY)), false), null);
        });
    }

    static void openProduct(ServerPlayer p, Item it, int cat) {
        MinecraftServer server = p.level().getServer();
        Ui.open(p, t("Bazaar · " + nice(it), ChatFormatting.DARK_GRAY), 4, m -> {
            List<Order> sl = sells(server, id(it)), bl = buys(server, id(it));
            int have = Economy.count(p, it);
            m.put(4, Ui.item(it, t(nice(it), ChatFormatting.WHITE, ChatFormatting.BOLD), List.of(
                    t("Cheapest offer: " + (sl.isEmpty() ? "none" : Economy.fmt(sl.get(0).price)) + " · " + volume(sl) + " for sale", ChatFormatting.GRAY),
                    t("Best buy order: " + (bl.isEmpty() ? "none" : Economy.fmt(bl.get(0).price)) + " · " + volume(bl) + " wanted", ChatFormatting.GRAY),
                    t("You have " + have, ChatFormatting.DARK_GRAY)), false), null);
            int[] buyN = {1, 16, 64};
            for (int i = 0; i < 3; i++) {
                int n = buyN[i];
                m.put(10 + i, Ui.item(new ItemStack(Items.GOLD_INGOT, n), t("Buy " + n + " now", ChatFormatting.GREEN), List.of(t("From the cheapest sell offers", ChatFormatting.GRAY)), false),
                        (pl, c) -> instantBuy(pl, it, n));
            }
            m.put(14, Ui.item(Items.HOPPER, t("Sell 1 now", ChatFormatting.GOLD), List.of(t("To the best buy order", ChatFormatting.GRAY)), false), (pl, c) -> instantSell(pl, it, 1));
            m.put(15, Ui.item(Items.CHEST, t("Sell all " + have + " now", ChatFormatting.GOLD), List.of(t("To the best buy orders", ChatFormatting.GRAY)), false), (pl, c) -> instantSell(pl, it, Integer.MAX_VALUE));
            m.put(19, Ui.item(Items.OAK_SIGN, t("Create sell offer", ChatFormatting.AQUA, ChatFormatting.BOLD), List.of(t("Pick an amount and your price;", ChatFormatting.GRAY),
                    t("the items wait on the Bazaar until bought", ChatFormatting.GRAY)), false), (pl, c) -> dialog(pl, it, true, sl.isEmpty() ? Economy.prices(server).get(it).sell() * 2 : Math.max(1, sl.get(0).price - 1)));
            m.put(25, Ui.item(Items.WRITABLE_BOOK, t("Create buy order", ChatFormatting.AQUA, ChatFormatting.BOLD), List.of(t("Pick an amount and your price;", ChatFormatting.GRAY),
                    t("the coins wait until someone sells", ChatFormatting.GRAY)), false), (pl, c) -> dialog(pl, it, false, bl.isEmpty() ? Math.max(1, Economy.prices(server).get(it).sell()) : bl.get(0).price + 1));
            m.put(31, Ui.item(Items.ARROW, t("Back", ChatFormatting.GRAY), List.of(), false), (pl, c) -> openCategory(pl, cat));
            m.put(35, Ui.item(Items.BOOK, t("My orders", ChatFormatting.GOLD), List.of(), false), (pl, c) -> openMine(pl));
        });
    }

    static void openMine(ServerPlayer p) {
        MinecraftServer server = p.level().getServer();
        Ui.open(p, t("Bazaar · My orders", ChatFormatting.DARK_GRAY), 6, m -> {
            String u = p.getStringUUID();
            List<Order> mineL = book(server).orders.stream().filter(o -> o.owner.equals(u)).toList();
            for (int i = 0; i < mineL.size() && i < GRID.length; i++) {
                Order o = mineL.get(i);
                Item it = Economy.item(o.item);
                List<Component> lore = new ArrayList<>();
                lore.add(t((o.sell ? "Sell offer" : "Buy order") + " at " + Economy.fmt(o.price) + " each", o.sell ? ChatFormatting.GOLD : ChatFormatting.AQUA));
                lore.add(t(o.left + " left", ChatFormatting.GRAY));
                if (o.claim > 0) lore.add(t(o.claim + " ready to claim", ChatFormatting.GREEN));
                lore.add(Component.empty());
                lore.add(t(o.claim > 0 ? "Click to claim" : "Click to cancel", ChatFormatting.YELLOW));
                m.put(GRID[i], Ui.item(it, t(nice(it), ChatFormatting.WHITE), lore, o.claim > 0), (pl, c) -> claimOrCancel(pl, o));
            }
            if (mineL.isEmpty()) m.put(22, Ui.item(Economy.item("minecraft:gray_dye"), t("No orders yet", ChatFormatting.GRAY), List.of(), false), null);
            m.put(49, Ui.item(Items.ARROW, t("Back", ChatFormatting.GRAY), List.of(), false), (pl, c) -> open(pl));
        });
    }

    /** A dialog asking for amount and price; it runs /bazaar offer|order <item> <amount> <price>. */
    static void dialog(ServerPlayer p, Item it, boolean sell, int suggest) {
        p.closeContainer();
        String what = sell ? "Sell offer" : "Buy order",
               cmd = (sell ? "bazaar offer " : "bazaar order ") + BuiltInRegistries.ITEM.getKey(it).getPath() + " $(amount) $(price)";   // unquoted: no ':'

        String body = sell ? "The items are taken now and wait on the Bazaar until someone buys them. You get paid (less 1%) even while offline."
                           : "The coins are taken now. When someone sells, the items wait for you in /bazaar > My orders.";
        String snbt = "{type:\"minecraft:notice\",title:{text:\"" + what + ": " + nice(it) + "\",color:\"gold\"},"
                + "body:[{type:\"minecraft:plain_message\",contents:{text:\"" + body + "\"}}],"
                + "inputs:[{type:\"minecraft:text\",key:\"amount\",label:{text:\"Amount\"},initial:\"" + (sell ? Math.max(1, Economy.count(p, it)) : 64) + "\",max_length:6},"
                + "{type:\"minecraft:text\",key:\"price\",label:{text:\"Price each (coins)\"},initial:\"" + suggest + "\",max_length:9}],"
                + "action:{label:{text:\"Place " + what.toLowerCase(Locale.ROOT) + "\",color:\"green\"},action:{type:\"minecraft:dynamic/run_command\",template:\"" + cmd + "\"}},"
                + "can_close_with_escape:1b,pause:0b,after_action:\"close\"}";
        MinecraftServer server = p.level().getServer();
        server.getCommands().performPrefixedCommand(server.createCommandSourceStack().withSuppressedOutput().withPermission(LevelBasedPermissionSet.GAMEMASTER),
                "dialog show " + p.getScoreboardName() + " " + snbt);
    }

    static void register(CommandDispatcher<CommandSourceStack> d) {
        for (String name : new String[]{"bazaar", "bz"}) {
            d.register(Commands.literal(name).executes(c -> { open(c.getSource().getPlayerOrException()); return 1; })
                    .then(Commands.literal("offer").then(Commands.argument("item", StringArgumentType.string())
                            .then(Commands.argument("amount", IntegerArgumentType.integer(1, 100000)).then(Commands.argument("price", IntegerArgumentType.integer(1, 10000000))
                                    .executes(c -> createSell(c.getSource().getPlayerOrException(), Economy.item(StringArgumentType.getString(c, "item")),
                                            IntegerArgumentType.getInteger(c, "amount"), IntegerArgumentType.getInteger(c, "price")))))))
                    .then(Commands.literal("order").then(Commands.argument("item", StringArgumentType.string())
                            .then(Commands.argument("amount", IntegerArgumentType.integer(1, 100000)).then(Commands.argument("price", IntegerArgumentType.integer(1, 10000000))
                                    .executes(c -> createBuy(c.getSource().getPlayerOrException(), Economy.item(StringArgumentType.getString(c, "item")),
                                            IntegerArgumentType.getInteger(c, "amount"), IntegerArgumentType.getInteger(c, "price"))))))));
        }
    }
}

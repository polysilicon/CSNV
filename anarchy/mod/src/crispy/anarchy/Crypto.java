package crispy.anarchy;

import com.google.gson.Gson;
import com.google.gson.JsonArray;
import com.google.gson.JsonObject;
import net.fabricmc.fabric.api.event.lifecycle.v1.ServerTickEvents;
import net.fabricmc.fabric.api.event.player.UseEntityCallback;
import net.fabricmc.loader.api.FabricLoader;
import net.minecraft.ChatFormatting;
import net.minecraft.nbt.NbtOps;
import net.minecraft.nbt.TagParser;
import net.minecraft.network.chat.Component;
import net.minecraft.server.MinecraftServer;
import net.minecraft.server.level.ServerPlayer;
import net.minecraft.sounds.SoundEvents;
import net.minecraft.sounds.SoundSource;
import net.minecraft.world.InteractionHand;
import net.minecraft.world.InteractionResult;
import net.minecraft.world.entity.npc.villager.Villager;
import net.minecraft.world.entity.player.Inventory;
import net.minecraft.world.item.Item;
import net.minecraft.world.item.ItemStack;
import net.minecraft.world.item.Items;

import java.nio.file.Files;
import java.nio.file.Path;
import java.util.ArrayList;
import java.util.List;
import java.util.Random;

import static crispy.anarchy.Ui.t;

/**
 * The market's Crypto Exchange (1.2.0): a villager tagged crispy_crypto opens a chest menu that buys and sells the old
 * market's Bitcoin (BTC) heads for Gold Coins at a price that moves like a real coin.
 *
 * Price: a random walk on the log price, one step a minute of real time (caught up after the server sleeps), pulled
 * gently back towards BASE so it wanders rather than drifting off for good, with a rare pump or crash. Trades move it
 * too: every Bitcoin bought pushes it up IMPACT, every one sold pushes it down, so dumping a pile crashes the price.
 * You buy at the price + SPREAD and sell at the price - SPREAD, so buying and selling straight back always loses.
 * Coins: Gold Coins and Coin Bags (64 coins) both pay; change comes back as coins, payouts as bags + coins.
 * State (price, 24 h of minute prices) lives in config/crispy_crypto.json.
 */
final class Crypto {
    private Crypto() {}

    static final double BASE = 128, MIN = 16, MAX = 2048;
    static final double VOL = 0.015;          // ~1.5 % a minute (~12 % an hour)
    static final double REVERT = 0.002;       // pull back towards BASE per minute
    static final double EVENT_CHANCE = 0.003; // a pump or crash about every 5-6 hours
    static final double IMPACT = 0.004;       // price moves 0.4 % per Bitcoin traded
    static final double SPREAD = 0.03;        // buy +3 %, sell -3 %
    static final int HISTORY = 1440;          // minutes kept (24 h)

    static final String BTC_TEXTURE = "eyJ0ZXh0dXJlcyI6eyJTS0lOIjp7InVybCI6Imh0dHA6Ly90ZXh0dXJlcy5taW5lY3JhZnQubmV0L3RleHR1cmUvNjY3ZGEzNzlmNTFkODVkNzRmZGJhMzlhMTY0ZDNmNTA2MmVmMmZmYzBiM2UwNGQzMzkzNzY3NzM5MzFhNGUifX19";
    static final String BTC_SNBT = "{id:\"minecraft:player_head\",count:1,components:{\"minecraft:custom_name\":{text:\"Bitcoin (BTC)\",italic:false,color:\"blue\"},\"minecraft:profile\":{id:[I;67411088,-739686879,-1666252800,-1432276700],properties:[{name:\"textures\",value:\"" + BTC_TEXTURE + "\"}]}}}";

    static final Path FILE = FabricLoader.getInstance().getConfigDir().resolve("crispy_crypto.json");
    static final Random RNG = new Random();
    static double price = BASE;
    static long lastStep;                       // epoch minute of the last step
    static final List<Double> history = new ArrayList<>();   // oldest first, one per minute
    static ItemStack btc;
    static int tick;

    // ------------------------------------------------------------------ setup
    static void init() {
        load();
        ServerTickEvents.END_SERVER_TICK.register(server -> {
            if (btc == null) makeItem(server);
            if (++tick % 200 == 0) catchUp();
        });
        UseEntityCallback.EVENT.register((player, world, hand, entity, hit) -> {
            if (!(entity instanceof Villager) || !entity.entityTags().contains("crispy_crypto")) return InteractionResult.PASS;
            if (hand == InteractionHand.MAIN_HAND && player instanceof ServerPlayer p) open(p);
            return InteractionResult.SUCCESS;
        });
    }

    static void makeItem(MinecraftServer server) {
        try {
            var ops = server.registryAccess().createSerializationContext(NbtOps.INSTANCE);
            btc = ItemStack.CODEC.parse(ops, TagParser.parseCompoundFully(BTC_SNBT)).getOrThrow();
        } catch (Exception e) {
            System.err.println("[crispy-anarchy] can't build the Bitcoin item: " + e);
            btc = ItemStack.EMPTY;
        }
    }

    static boolean isBtc(ItemStack s) {
        if (!s.is(Items.PLAYER_HEAD) || !Coins.name(s).contains("Bitcoin")) return false;
        var profile = s.get(net.minecraft.core.component.DataComponents.PROFILE);
        if (profile == null) return false;
        for (var prop : profile.partialProfile().properties().get("textures"))
            if (BTC_TEXTURE.equals(prop.value())) return true;
        return false;
    }

    // ------------------------------------------------------------------ price
    static long nowMinute() { return System.currentTimeMillis() / 60_000L; }

    /** Step the price once per real minute since the last step (at most a day's worth). */
    static void catchUp() {
        long now = nowMinute();
        if (lastStep == 0) lastStep = now;
        long steps = Math.min(HISTORY, now - lastStep);
        if (steps <= 0) return;
        for (long i = 0; i < steps; i++) step();
        lastStep = now;
        save();
    }

    static void step() {
        double lp = Math.log(price);
        lp += REVERT * (Math.log(BASE) - lp) + VOL * RNG.nextGaussian();
        if (RNG.nextDouble() < EVENT_CHANCE) lp += (RNG.nextBoolean() ? 1 : -1) * (0.15 + 0.25 * RNG.nextDouble());
        price = clamp(Math.exp(lp));
        history.add(price);
        while (history.size() > HISTORY) history.remove(0);
    }

    static double clamp(double p) { return Math.max(MIN, Math.min(MAX, p)); }
    static long buyPrice() { return (long) Math.ceil(price * (1 + SPREAD)); }
    static long sellPrice() { return Math.max(1, (long) Math.floor(price * (1 - SPREAD))); }

    /** Cost of buying n now (each Bitcoin pushes the price up before the next). */
    static long quoteBuy(int n) {
        double p = price; long total = 0;
        for (int i = 0; i < n; i++) { total += (long) Math.ceil(p * (1 + SPREAD)); p = clamp(p * (1 + IMPACT)); }
        return total;
    }
    static long quoteSell(int n) {
        double p = price; long total = 0;
        for (int i = 0; i < n; i++) { total += Math.max(1, (long) Math.floor(p * (1 - SPREAD))); p = clamp(p * (1 - IMPACT)); }
        return total;
    }

    static double ago(int minutes) {
        if (history.isEmpty()) return price;
        int i = history.size() - 1 - minutes;
        return history.get(Math.max(0, i));
    }

    // ------------------------------------------------------------------ wallet (Gold Coins + Coin Bags)
    static long coins(Inventory inv) {
        long n = 0;
        for (int i = 0; i < inv.getContainerSize(); i++) {
            ItemStack s = inv.getItem(i);
            if (Coins.isCoin(s)) n += s.getCount();
            else if (Coins.isBag(s)) n += 64L * s.getCount();
        }
        return n;
    }
    static int btcCount(Inventory inv) {
        int n = 0;
        for (int i = 0; i < inv.getContainerSize(); i++) if (isBtc(inv.getItem(i))) n += inv.getItem(i).getCount();
        return n;
    }

    /** Take `cost` coins: loose coins first, then open bags and give the change back. */
    static void pay(ServerPlayer p, long cost) {
        Inventory inv = p.getInventory();
        long left = cost;
        for (int i = 0; i < inv.getContainerSize() && left > 0; i++) {
            ItemStack s = inv.getItem(i);
            if (!Coins.isCoin(s)) continue;
            int k = (int) Math.min(left, s.getCount());
            s.shrink(k); left -= k;
        }
        for (int i = 0; i < inv.getContainerSize() && left > 0; i++) {
            ItemStack s = inv.getItem(i);
            if (!Coins.isBag(s)) continue;
            while (left > 0 && !s.isEmpty()) {
                s.shrink(1);
                long change = 64 - Math.min(64, left);
                left -= Math.min(64, left);
                if (change > 0) give(p, Coins.coinStack(), change);
            }
        }
        inv.setChanged();
    }

    /** Give `amount` coins as Coin Bags (64) plus loose Gold Coins. */
    static void payout(ServerPlayer p, long amount) {
        give(p, Coins.bagStack(), amount / 64);
        give(p, Coins.coinStack(), amount % 64);
    }

    static void give(ServerPlayer p, ItemStack proto, long count) {
        while (count > 0) {
            int k = (int) Math.min(count, proto.getMaxStackSize());
            ItemStack s = proto.copyWithCount(k);
            if (!p.getInventory().add(s)) p.drop(s, false);
            count -= k;
        }
    }

    static void takeBtc(Inventory inv, int n) {
        for (int i = 0; i < inv.getContainerSize() && n > 0; i++) {
            ItemStack s = inv.getItem(i);
            if (!isBtc(s)) continue;
            int k = Math.min(n, s.getCount());
            s.shrink(k); n -= k;
        }
        inv.setChanged();
    }

    // ------------------------------------------------------------------ trading
    static void buy(ServerPlayer p, int n) {
        catchUp();
        if (btc == null || btc.isEmpty() || Coins.coinStack().isEmpty()) { p.sendSystemMessage(t("The exchange is offline right now.", ChatFormatting.RED)); return; }
        long cost = quoteBuy(n);
        long have = coins(p.getInventory());
        if (have < cost) { p.sendSystemMessage(t("You need " + cost + " Gold Coins for " + n + " BTC (you have " + have + ").", ChatFormatting.RED)); return; }
        pay(p, cost);
        give(p, btc, n);
        for (int i = 0; i < n; i++) price = clamp(price * (1 + IMPACT));
        save();
        p.level().playSound(null, p.blockPosition(), SoundEvents.EXPERIENCE_ORB_PICKUP, SoundSource.PLAYERS, 0.7f, 1.4f);
        p.sendSystemMessage(t("Bought " + n + " BTC for " + cost + " Gold Coins.", ChatFormatting.GREEN));
        System.out.println("[crispy-anarchy] crypto: " + p.getScoreboardName() + " bought " + n + " BTC for " + cost);
    }

    static void sell(ServerPlayer p, int n) {
        catchUp();
        if (Coins.coinStack().isEmpty()) { p.sendSystemMessage(t("The exchange is offline right now.", ChatFormatting.RED)); return; }
        n = Math.min(n, btcCount(p.getInventory()));
        if (n <= 0) { p.sendSystemMessage(t("You don't have any Bitcoin (BTC) to sell.", ChatFormatting.RED)); return; }
        long got = quoteSell(n);
        takeBtc(p.getInventory(), n);
        payout(p, got);
        for (int i = 0; i < n; i++) price = clamp(price * (1 - IMPACT));
        save();
        p.level().playSound(null, p.blockPosition(), SoundEvents.EXPERIENCE_ORB_PICKUP, SoundSource.PLAYERS, 0.7f, 0.8f);
        p.sendSystemMessage(t("Sold " + n + " BTC for " + got + " Gold Coins.", ChatFormatting.GOLD));
        System.out.println("[crispy-anarchy] crypto: " + p.getScoreboardName() + " sold " + n + " BTC for " + got);
    }

    static Item it(String id) { return net.minecraft.core.registries.BuiltInRegistries.ITEM.getValue(net.minecraft.resources.Identifier.withDefaultNamespace(id)); }

    // ------------------------------------------------------------------ the menu
    static String pct(double now, double then) {
        double c = (now / then - 1) * 100;
        return (c >= 0 ? "+" : "") + String.format("%.1f", c) + "%";
    }
    static ChatFormatting col(double now, double then) { return now >= then ? ChatFormatting.GREEN : ChatFormatting.RED; }

    static void open(ServerPlayer p) {
        catchUp();
        Ui.open(p, t("₿ Crypto Exchange", ChatFormatting.DARK_GRAY), 6, m -> {
            double h1 = ago(60), h24 = ago(HISTORY - 1);
            double hi = price, lo = price;
            for (double v : history) { hi = Math.max(hi, v); lo = Math.min(lo, v); }
            ItemStack icon = btc == null || btc.isEmpty() ? new ItemStack(Items.GOLD_NUGGET) : btc.copy();
            m.put(4, Ui.item(icon, t("Bitcoin (BTC)", ChatFormatting.BLUE, ChatFormatting.BOLD), List.of(
                    t("Price: " + String.format("%.1f", price) + " Gold Coins", ChatFormatting.WHITE),
                    t("1h: " + pct(price, h1) + "   24h: " + pct(price, h24), col(price, h24)),
                    t("24h high " + String.format("%.0f", hi) + " · low " + String.format("%.0f", lo), ChatFormatting.GRAY),
                    Component.empty(),
                    t("You buy at " + buyPrice() + ", sell at " + sellPrice(), ChatFormatting.YELLOW),
                    t("Every trade moves the price.", ChatFormatting.DARK_GRAY)), false), null);

            // chart: the last 3 hours in 9 columns of 20 minutes, 4 rows tall (slots 9-44)
            int cols = 9, rows = 4, span = 20;
            double[] pts = new double[cols];
            for (int c = 0; c < cols; c++) pts[c] = ago((cols - 1 - c) * span);
            double cmin = pts[0], cmax = pts[0];
            for (double v : pts) { cmin = Math.min(cmin, v); cmax = Math.max(cmax, v); }
            for (int c = 0; c < cols; c++) {
                int h = cmax - cmin < 0.01 ? 2 : 1 + (int) Math.round((pts[c] - cmin) / (cmax - cmin) * (rows - 1));
                boolean up = c == 0 ? pts[c] >= ago(cols * span) : pts[c] >= pts[c - 1];
                int mins = (cols - 1 - c) * span;
                Component label = t((mins == 0 ? "Now" : mins + " min ago") + ": " + String.format("%.1f", pts[c]), up ? ChatFormatting.GREEN : ChatFormatting.RED);
                for (int r = 0; r < rows; r++) {
                    int slot = 9 + (rows - 1 - r) * 9 + c;   // bottom row first
                    Item pane = r < h ? (up ? it("lime_stained_glass_pane") : it("red_stained_glass_pane")) : it("black_stained_glass_pane");
                    m.put(slot, Ui.item(pane, label, List.of(t("Each column is 20 minutes.", ChatFormatting.DARK_GRAY)), false), null);
                }
            }

            Inventory inv = p.getInventory();
            long have = coins(inv); int own = btcCount(inv);
            int[] amounts = {1, 8, 64};
            for (int i = 0; i < 3; i++) {
                final int idx = i, n = amounts[i];
                long cost = quoteBuy(n);
                m.put(45 + idx, Ui.item(it("lime_dye"), t("Buy " + n + " BTC", ChatFormatting.GREEN, ChatFormatting.BOLD), List.of(
                        t("Costs " + cost + " Gold Coins", have >= cost ? ChatFormatting.WHITE : ChatFormatting.RED),
                        t("(Coin Bags count as 64)", ChatFormatting.DARK_GRAY)), false), (pl, c) -> buy(pl, n));
                int sn = idx == 2 ? Math.max(1, own) : n;
                long got = quoteSell(Math.min(sn, Math.max(1, own)));
                m.put(51 + idx, Ui.item(it("red_dye"), t(idx == 2 ? "Sell all (" + own + ") BTC" : "Sell " + n + " BTC", ChatFormatting.RED, ChatFormatting.BOLD), List.of(
                        t(own > 0 ? "Pays about " + got + " Gold Coins" : "You have no BTC", own > 0 ? ChatFormatting.WHITE : ChatFormatting.DARK_GRAY),
                        t("Selling a lot at once sinks the price", ChatFormatting.DARK_GRAY)), false), (pl, c) -> sell(pl, idx == 2 ? btcCount(pl.getInventory()) : n));
            }
            m.put(49, Ui.item(Items.GOLD_INGOT, t("Your wallet", ChatFormatting.GOLD, ChatFormatting.BOLD), List.of(
                    t(have + " Gold Coins (bags included)", ChatFormatting.WHITE),
                    t(own + " BTC ≈ " + quoteSell(own) + " coins if sold now", ChatFormatting.BLUE),
                    Component.empty(),
                    t("The price moves every minute, like", ChatFormatting.DARK_GRAY), t("real crypto. Buy low, sell high!", ChatFormatting.DARK_GRAY)), false), null);
        });
    }

    // ------------------------------------------------------------------ save / load
    static void save() {
        try {
            JsonObject o = new JsonObject();
            o.addProperty("price", price);
            o.addProperty("lastStep", lastStep);
            JsonArray h = new JsonArray();
            for (double v : history) h.add(Math.round(v * 100) / 100.0);
            o.add("history", h);
            Files.writeString(FILE, new Gson().toJson(o));
        } catch (Exception e) { System.err.println("[crispy-anarchy] can't save " + FILE + ": " + e); }
    }

    static void load() {
        try {
            if (!Files.exists(FILE)) { price = BASE; lastStep = nowMinute(); history.add(price); return; }
            JsonObject o = new Gson().fromJson(Files.readString(FILE), JsonObject.class);
            price = clamp(o.get("price").getAsDouble());
            lastStep = o.get("lastStep").getAsLong();
            for (var e : o.getAsJsonArray("history")) history.add(e.getAsDouble());
        } catch (Exception e) {
            System.err.println("[crispy-anarchy] can't read " + FILE + ", starting at " + BASE + ": " + e);
            price = BASE; lastStep = nowMinute();
        }
    }
}

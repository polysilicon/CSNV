package crispy.falling;

import com.mojang.brigadier.CommandDispatcher;
import com.mojang.brigadier.arguments.IntegerArgumentType;
import net.minecraft.ChatFormatting;
import net.minecraft.commands.CommandSourceStack;
import net.minecraft.commands.Commands;
import net.minecraft.commands.arguments.EntityArgument;
import net.minecraft.core.registries.BuiltInRegistries;
import net.minecraft.nbt.CompoundTag;
import net.minecraft.nbt.ListTag;
import net.minecraft.network.chat.Component;
import net.minecraft.resources.Identifier;
import net.minecraft.server.MinecraftServer;
import net.minecraft.server.level.ServerPlayer;
import net.minecraft.world.entity.player.Inventory;
import net.minecraft.world.item.Item;
import net.minecraft.world.item.ItemStack;
import net.minecraft.world.item.Items;
import net.minecraft.world.scores.Objective;
import net.minecraft.world.scores.PlayerScoreEntry;
import net.minecraft.world.scores.ScoreHolder;

import java.text.NumberFormat;
import java.util.*;

/**
 * Coins (the cs_coins score), /coins, /coins top, /pay and the merchant prices. Prices, shop categories and minion
 * types come from the datapack (storage crispy_skyblock:eco cfg, see falling/skyblock.py), read fresh each time.
 */
public final class Economy {
    private Economy() {}

    static final Identifier ECO = Identifier.fromNamespaceAndPath(SkyblockMod.NS, "eco");
    static final NumberFormat FMT = NumberFormat.getIntegerInstance(Locale.US);

    static CompoundTag cfg(MinecraftServer server) { return server.getCommandStorage().get(ECO).getCompoundOrEmpty("cfg"); }

    static String fmt(long n) { return FMT.format(n); }

    // ------------------------------------------------------------------ coins
    static int coins(MinecraftServer server, ServerPlayer p) { return SkyblockMod.score(server, p, "cs_coins"); }

    /** Add (or with a negative amount take) coins; false if the objective is missing or they can't afford it. */
    static boolean add(MinecraftServer server, ServerPlayer p, long delta) {
        Objective obj = server.getScoreboard().getObjective("cs_coins");
        if (obj == null) return false;
        var score = server.getScoreboard().getOrCreatePlayerScore(p, obj);
        long now = score.get() + delta;
        if (now < 0) return false;
        score.set((int) Math.min(Integer.MAX_VALUE, now));
        return true;
    }

    // ------------------------------------------------------------------ prices
    record Price(Item item, int buy, int sell) {}

    /** item -> price, across every shop category. */
    static Map<Item, Price> prices(MinecraftServer server) {
        Map<Item, Price> out = new LinkedHashMap<>();
        ListTag cats = cfg(server).getListOrEmpty("shop");
        for (int c = 0; c < cats.size(); c++) {
            ListTag items = cats.getCompoundOrEmpty(c).getListOrEmpty("items");
            for (int i = 0; i < items.size(); i++) {
                CompoundTag e = items.getCompoundOrEmpty(i);
                Item it = item(e.getStringOr("id", ""));
                if (it != Items.AIR) out.put(it, new Price(it, e.getIntOr("buy", 0), e.getIntOr("sell", 0)));
            }
        }
        return out;
    }

    static Item item(String id) {
        try { return BuiltInRegistries.ITEM.getValue(Identifier.parse(id)); } catch (Exception e) { return Items.AIR; }
    }

    /** A plain stack (no custom name, minion data...) that a merchant will take. */
    static boolean plain(ItemStack s) { return !s.isEmpty() && s.getComponentsPatch().isEmpty(); }

    static int count(ServerPlayer p, Item item) {
        Inventory inv = p.getInventory();
        int n = 0;
        for (int i = 0; i < 36; i++) { ItemStack s = inv.getItem(i); if (s.is(item) && plain(s)) n += s.getCount(); }
        return n;
    }

    /** Take up to n plain items from the main inventory; returns how many were taken. */
    static int take(ServerPlayer p, Item item, int n) {
        Inventory inv = p.getInventory();
        int left = n;
        for (int i = 0; i < 36 && left > 0; i++) {
            ItemStack s = inv.getItem(i);
            if (!s.is(item) || !plain(s)) continue;
            int t = Math.min(left, s.getCount());
            s.shrink(t);
            left -= t;
        }
        inv.setChanged();
        return n - left;
    }

    /** Give items, dropping what doesn't fit at the player's feet. */
    static void give(ServerPlayer p, Item item, int n) {
        int max = new ItemStack(item).getMaxStackSize();
        while (n > 0) {
            int k = Math.min(n, max);
            ItemStack s = new ItemStack(item, k);
            if (!p.getInventory().add(s) && !s.isEmpty()) p.drop(s, false);
            n -= k;
        }
    }

    // ------------------------------------------------------------------ commands
    static void register(CommandDispatcher<CommandSourceStack> d) {
        for (String name : new String[]{"coins", "bal", "purse"}) {
            d.register(Commands.literal(name)
                    .executes(c -> {
                        ServerPlayer p = c.getSource().getPlayerOrException();
                        c.getSource().sendSuccess(() -> Component.literal("Purse: ").withStyle(ChatFormatting.GRAY)
                                .append(Component.literal(fmt(coins(c.getSource().getServer(), p)) + " coins").withStyle(ChatFormatting.GOLD)), false);
                        return 1;
                    })
                    .then(Commands.literal("top").executes(c -> top(c.getSource())))
                    .then(Commands.literal("give").requires(Commands.hasPermission(Commands.LEVEL_GAMEMASTERS))
                            .then(Commands.argument("player", EntityArgument.player()).then(Commands.argument("amount", IntegerArgumentType.integer())
                                    .executes(c -> {
                                        ServerPlayer t = EntityArgument.getPlayer(c, "player");
                                        int a = IntegerArgumentType.getInteger(c, "amount");
                                        add(c.getSource().getServer(), t, a);
                                        c.getSource().sendSuccess(() -> Component.literal(t.getGameProfile().name() + " now has " + fmt(coins(c.getSource().getServer(), t)) + " coins"), true);
                                        return 1;
                                    })))));
        }
        d.register(Commands.literal("pay").then(Commands.argument("player", EntityArgument.player())
                .then(Commands.argument("amount", IntegerArgumentType.integer(1)).executes(c -> {
                    ServerPlayer me = c.getSource().getPlayerOrException(), to = EntityArgument.getPlayer(c, "player");
                    int a = IntegerArgumentType.getInteger(c, "amount");
                    MinecraftServer server = c.getSource().getServer();
                    if (me == to) { c.getSource().sendFailure(Component.literal("You can't pay yourself.")); return 0; }
                    if (!add(server, me, -a)) { c.getSource().sendFailure(Component.literal("You only have " + fmt(coins(server, me)) + " coins.")); return 0; }
                    add(server, to, a);
                    me.sendSystemMessage(Component.literal("You paid ").withStyle(ChatFormatting.GRAY).append(Component.literal(to.getGameProfile().name()).withStyle(ChatFormatting.WHITE))
                            .append(Component.literal(" " + fmt(a) + " coins").withStyle(ChatFormatting.GOLD)));
                    to.sendSystemMessage(Component.literal(me.getGameProfile().name()).withStyle(ChatFormatting.WHITE).append(Component.literal(" paid you ").withStyle(ChatFormatting.GRAY))
                            .append(Component.literal(fmt(a) + " coins").withStyle(ChatFormatting.GOLD)));
                    return 1;
                }))));
    }

    static int top(CommandSourceStack s) {
        MinecraftServer server = s.getServer();
        Objective obj = server.getScoreboard().getObjective("cs_coins");
        List<PlayerScoreEntry> rows = new ArrayList<>();
        if (obj != null) for (PlayerScoreEntry e : server.getScoreboard().listPlayerScores(obj)) if (!e.owner().startsWith("#") && e.value() > 0) rows.add(e);
        rows.sort(Comparator.comparingInt(PlayerScoreEntry::value).reversed());
        s.sendSuccess(() -> Component.literal("Richest players").withStyle(ChatFormatting.GOLD, ChatFormatting.BOLD), false);
        if (rows.isEmpty()) s.sendSuccess(() -> Component.literal("Nobody has any coins yet.").withStyle(ChatFormatting.GRAY), false);
        for (int i = 0; i < Math.min(10, rows.size()); i++) {
            PlayerScoreEntry e = rows.get(i);
            int n = i + 1;
            s.sendSuccess(() -> Component.literal("#" + n + " ").withStyle(ChatFormatting.YELLOW).append(Component.literal(e.owner() + "  ").withStyle(ChatFormatting.WHITE))
                    .append(Component.literal(fmt(e.value()) + " coins").withStyle(ChatFormatting.GOLD)), false);
        }
        return rows.size();
    }

    static ScoreHolder holder(String name) { return ScoreHolder.forNameOnly(name); }
}

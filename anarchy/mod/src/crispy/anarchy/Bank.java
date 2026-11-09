package crispy.anarchy;

import net.fabricmc.fabric.api.event.player.UseEntityCallback;
import net.minecraft.ChatFormatting;
import net.minecraft.core.component.DataComponents;
import net.minecraft.network.chat.Component;
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

import java.util.List;

import static crispy.anarchy.Ui.t;

/**
 * The market's Banker as a chest menu (1.2.1): a villager tagged crispy_bank. Same rates as its old trades:
 * 36 emeralds or diamonds (blocks count as 9) = 1 Gold Coin, a netherite block = 16 Gold Coins, 64 Gold Coins = 1
 * Coin Bag. Click does one, shift-click does as many as you can. Only plain items count (a named "Meteorite"
 * netherite block isn't netherite). Payments take loose coins first, then open Coin Bags and give change.
 */
final class Bank {
    private Bank() {}

    static final int PER_COIN = 36;   // emeralds or diamonds per Gold Coin
    static final int NETHERITE = 16;  // Gold Coins per netherite block

    static void init() {
        UseEntityCallback.EVENT.register((player, world, hand, entity, hit) -> {
            if (!(entity instanceof Villager) || !entity.entityTags().contains("crispy_bank")) return InteractionResult.PASS;
            if (hand == InteractionHand.MAIN_HAND && player instanceof ServerPlayer p) open(p);
            return InteractionResult.SUCCESS;
        });
    }

    static boolean plain(ItemStack s) { return !s.has(DataComponents.CUSTOM_NAME) && !s.has(DataComponents.CUSTOM_DATA); }

    static int count(Inventory inv, Item item) {
        int n = 0;
        for (int i = 0; i < inv.getContainerSize(); i++) { ItemStack s = inv.getItem(i); if (s.is(item) && plain(s)) n += s.getCount(); }
        return n;
    }
    static void take(Inventory inv, Item item, int n) {
        for (int i = 0; i < inv.getContainerSize() && n > 0; i++) {
            ItemStack s = inv.getItem(i);
            if (!s.is(item) || !plain(s)) continue;
            int k = Math.min(n, s.getCount()); s.shrink(k); n -= k;
        }
        inv.setChanged();
    }
    static void give(ServerPlayer p, Item item, long n) { Crypto.give(p, new ItemStack(item), n); }

    /** Units of a gem (singles + 9 per block). */
    static long units(Inventory inv, Item single, Item block) { return count(inv, single) + 9L * count(inv, block); }
    /** Take `need` units, blocks first; breaks a block and gives change if the singles run short. */
    static void takeUnits(ServerPlayer p, Item single, Item block, long need) {
        Inventory inv = p.getInventory();
        int blocks = count(inv, block), singles = count(inv, single);
        int useBlocks = (int) Math.min(blocks, need / 9);
        long rem = need - 9L * useBlocks;
        if (rem <= singles) { take(inv, block, useBlocks); take(inv, single, (int) rem); return; }
        // not enough singles: one more block, change back
        take(inv, block, useBlocks + 1);
        long change = 9 - rem;
        if (change > 0) give(p, single, change);
    }
    static void giveUnits(ServerPlayer p, Item single, Item block, long units) {
        give(p, block, units / 9);
        give(p, single, units % 9);
    }

    static long looseCoins(Inventory inv) {
        long n = 0;
        for (int i = 0; i < inv.getContainerSize(); i++) if (Coins.isCoin(inv.getItem(i))) n += inv.getItem(i).getCount();
        return n;
    }
    static long bags(Inventory inv) {
        long n = 0;
        for (int i = 0; i < inv.getContainerSize(); i++) if (Coins.isBag(inv.getItem(i))) n += inv.getItem(i).getCount();
        return n;
    }

    static void done(ServerPlayer p, String what) {
        p.level().playSound(null, p.blockPosition(), SoundEvents.EXPERIENCE_ORB_PICKUP, SoundSource.PLAYERS, 0.6f, 1.2f);
        p.sendSystemMessage(t(what, ChatFormatting.GREEN));
        System.out.println("[crispy-anarchy] bank: " + p.getScoreboardName() + " " + what);
    }
    static void no(ServerPlayer p, String why) { p.sendSystemMessage(t(why, ChatFormatting.RED)); }
    static boolean ready(ServerPlayer p) {
        if (Coins.coinStack().isEmpty() || Coins.bagStack().isEmpty()) { no(p, "The bank is closed right now."); return false; }
        return true;
    }

    // ------------------------------------------------------------------ actions
    static void gemToCoins(ServerPlayer p, Item single, Item block, String name, boolean all) {
        if (!ready(p)) return;
        long have = units(p.getInventory(), single, block);
        long coins = all ? have / PER_COIN : Math.min(1, have / PER_COIN);
        if (coins <= 0) { no(p, "You need " + PER_COIN + " " + name + " (blocks count as 9) for a Gold Coin."); return; }
        takeUnits(p, single, block, coins * PER_COIN);
        Crypto.payout(p, coins);
        done(p, "Exchanged " + coins * PER_COIN + " " + name + " for " + coins + " Gold Coin" + (coins == 1 ? "" : "s") + ".");
    }
    static void coinsToGem(ServerPlayer p, Item single, Item block, String name, boolean all) {
        if (!ready(p)) return;
        long have = Crypto.coins(p.getInventory());
        long coins = all ? Math.min(have, 64) : Math.min(1, have);
        if (coins <= 0) { no(p, "You need a Gold Coin (or a Coin Bag)."); return; }
        Crypto.pay(p, coins);
        giveUnits(p, single, block, coins * PER_COIN);
        done(p, "Exchanged " + coins + " Gold Coin" + (coins == 1 ? "" : "s") + " for " + coins * PER_COIN + " " + name + ".");
    }
    static void netheriteToCoins(ServerPlayer p, boolean all) {
        if (!ready(p)) return;
        int have = count(p.getInventory(), Items.NETHERITE_BLOCK);
        int n = all ? have : Math.min(1, have);
        if (n <= 0) { no(p, "You need a (plain) netherite block."); return; }
        take(p.getInventory(), Items.NETHERITE_BLOCK, n);
        Crypto.payout(p, (long) n * NETHERITE);
        done(p, "Exchanged " + n + " netherite block" + (n == 1 ? "" : "s") + " for " + n * NETHERITE + " Gold Coins.");
    }
    static void coinsToNetherite(ServerPlayer p, boolean all) {
        if (!ready(p)) return;
        long have = Crypto.coins(p.getInventory());
        long n = all ? Math.min(have / NETHERITE, 64) : Math.min(1, have / NETHERITE);
        if (n <= 0) { no(p, "You need " + NETHERITE + " Gold Coins for a netherite block."); return; }
        Crypto.pay(p, n * NETHERITE);
        give(p, Items.NETHERITE_BLOCK, n);
        done(p, "Exchanged " + n * NETHERITE + " Gold Coins for " + n + " netherite block" + (n == 1 ? "" : "s") + ".");
    }
    static void packBags(ServerPlayer p, boolean all) {
        if (!ready(p)) return;
        long loose = looseCoins(p.getInventory());
        long n = all ? loose / 64 : Math.min(1, loose / 64);
        if (n <= 0) { no(p, "You need 64 loose Gold Coins for a Coin Bag."); return; }
        Inventory inv = p.getInventory();
        long left = n * 64;
        for (int i = 0; i < inv.getContainerSize() && left > 0; i++) {
            ItemStack s = inv.getItem(i);
            if (!Coins.isCoin(s)) continue;
            int k = (int) Math.min(left, s.getCount()); s.shrink(k); left -= k;
        }
        inv.setChanged();
        Crypto.give(p, Coins.bagStack(), n);
        done(p, "Packed " + n * 64 + " Gold Coins into " + n + " Coin Bag" + (n == 1 ? "" : "s") + ".");
    }
    static void openBags(ServerPlayer p, boolean all) {
        if (!ready(p)) return;
        long have = bags(p.getInventory());
        long n = all ? Math.min(have, 16) : Math.min(1, have);   // 16 bags = 1024 coins, enough inventory for one go
        if (n <= 0) { no(p, "You don't have a Coin Bag."); return; }
        Inventory inv = p.getInventory();
        long left = n;
        for (int i = 0; i < inv.getContainerSize() && left > 0; i++) {
            ItemStack s = inv.getItem(i);
            if (!Coins.isBag(s)) continue;
            int k = (int) Math.min(left, s.getCount()); s.shrink(k); left -= k;
        }
        inv.setChanged();
        Crypto.give(p, Coins.coinStack(), n * 64);
        done(p, "Opened " + n + " Coin Bag" + (n == 1 ? "" : "s") + " into " + n * 64 + " Gold Coins.");
    }

    // ------------------------------------------------------------------ the menu
    static List<Component> lore(String click, String shift) {
        return List.of(t("Click: " + click, ChatFormatting.YELLOW), t("Shift-click: " + shift, ChatFormatting.GOLD));
    }

    static void open(ServerPlayer p) {
        Ui.open(p, t("Bank", ChatFormatting.DARK_GRAY), 6, m -> {
            Inventory inv = p.getInventory();
            long loose = looseCoins(inv), bags = bags(inv);
            ItemStack coinIcon = Coins.coinStack().isEmpty() ? new ItemStack(Items.SUNFLOWER) : Coins.coinStack().copy();
            ItemStack bagIcon = Coins.bagStack().isEmpty() ? new ItemStack(Items.PLAYER_HEAD) : Coins.bagStack().copy();
            m.put(4, Ui.item(Items.GOLD_INGOT, t("Bank", ChatFormatting.GOLD, ChatFormatting.BOLD), List.of(
                    t("Gold Coins: " + loose + "   Coin Bags: " + bags, ChatFormatting.WHITE),
                    t("Total: " + (loose + 64 * bags) + " Gold Coins", ChatFormatting.GRAY),
                    Component.empty(),
                    t(PER_COIN + " emeralds or diamonds = 1 Gold Coin", ChatFormatting.DARK_GRAY),
                    t("(blocks count as 9)", ChatFormatting.DARK_GRAY),
                    t("1 netherite block = " + NETHERITE + " Gold Coins", ChatFormatting.DARK_GRAY),
                    t("64 Gold Coins = 1 Coin Bag", ChatFormatting.DARK_GRAY)), false), null);

            Object[][] gems = {{Items.EMERALD, Items.EMERALD_BLOCK, "emeralds", 19}, {Items.DIAMOND, Items.DIAMOND_BLOCK, "diamonds", 28}};
            for (Object[] g : gems) {
                Item single = (Item) g[0], block = (Item) g[1]; String name = (String) g[2]; int row = (Integer) g[3];
                long u = units(inv, single, block);
                m.put(row - 1, Ui.item(block, t(name.substring(0, 1).toUpperCase() + name.substring(1), ChatFormatting.AQUA, ChatFormatting.BOLD),
                        List.of(t("You have " + u + " (" + u / PER_COIN + " coins' worth)", ChatFormatting.GRAY)), false), null);
                m.put(row, Ui.item(single, t("Sell " + name + " for Gold Coins", ChatFormatting.GREEN), lore(PER_COIN + " → 1 coin", "all of them"), false),
                        (pl, c) -> gemToCoins(pl, single, block, name, c.shift()));
                m.put(row + 2, Ui.item(coinIcon.copy(), t("Buy " + name + " with Gold Coins", ChatFormatting.RED), lore("1 coin → " + PER_COIN, "64 coins' worth"), false),
                        (pl, c) -> coinsToGem(pl, single, block, name, c.shift()));
            }
            int nb = count(inv, Items.NETHERITE_BLOCK);
            m.put(36, Ui.item(Items.NETHERITE_BLOCK, t("Netherite", ChatFormatting.DARK_PURPLE, ChatFormatting.BOLD),
                    List.of(t("You have " + nb + " plain netherite blocks", ChatFormatting.GRAY)), false), null);
            m.put(37, Ui.item(Items.NETHERITE_INGOT, t("Sell netherite blocks", ChatFormatting.GREEN), lore("1 block → " + NETHERITE + " coins", "all of them"), false),
                    (pl, c) -> netheriteToCoins(pl, c.shift()));
            m.put(39, Ui.item(coinIcon.copy(), t("Buy netherite blocks", ChatFormatting.RED), lore(NETHERITE + " coins → 1 block", "as many as you can (up to 64)"), false),
                    (pl, c) -> coinsToNetherite(pl, c.shift()));

            m.put(23, Ui.item(bagIcon.copy(), t("Coin Bags", ChatFormatting.BLUE, ChatFormatting.BOLD), List.of(t("64 Gold Coins each", ChatFormatting.GRAY)), false), null);
            m.put(24, Ui.item(coinIcon.copy(), t("Pack coins into bags", ChatFormatting.GREEN), lore("64 coins → 1 bag", "all your loose coins"), false),
                    (pl, c) -> packBags(pl, c.shift()));
            m.put(25, Ui.item(bagIcon.copy(), t("Open a Coin Bag", ChatFormatting.YELLOW), lore("1 bag → 64 coins", "up to 16 bags"), false),
                    (pl, c) -> openBags(pl, c.shift()));

            m.put(49, Ui.item(Items.BOOK, t("Crypto Exchange", ChatFormatting.BLUE), List.of(
                    t("Bitcoin (BTC) is traded next door:", ChatFormatting.GRAY), t("its price moves every minute.", ChatFormatting.GRAY)), false), null);
        });
    }
}

package crispy.falling;

import net.minecraft.ChatFormatting;
import net.minecraft.core.component.DataComponents;
import net.minecraft.nbt.CompoundTag;
import net.minecraft.nbt.ListTag;
import net.minecraft.network.chat.Component;
import net.minecraft.network.chat.MutableComponent;
import net.minecraft.server.MinecraftServer;
import net.minecraft.server.level.ServerPlayer;
import net.minecraft.sounds.SoundEvents;
import net.minecraft.sounds.SoundSource;
import net.minecraft.world.SimpleContainer;
import net.minecraft.world.SimpleMenuProvider;
import net.minecraft.world.entity.player.Inventory;
import net.minecraft.world.entity.player.Player;
import net.minecraft.world.inventory.ChestMenu;
import net.minecraft.world.inventory.ContainerInput;
import net.minecraft.world.inventory.MenuType;
import net.minecraft.world.item.Item;
import net.minecraft.world.item.ItemStack;
import net.minecraft.world.item.Items;
import net.minecraft.world.item.component.ItemLore;

import java.util.ArrayList;
import java.util.List;
import java.util.Map;

/**
 * The merchants' shop: a 6-row chest with a tab per category (top row), the category's items in the middle, and
 * purse / sell everything / close along the bottom. Left-click buys one, shift-left buys a stack, right-click sells
 * one, shift-right sells every one you carry. Only plain items (no custom name or data) are bought or sold.
 */
public final class Shop {
    private Shop() {}

    static final int[] GRID = {10, 11, 12, 13, 14, 15, 16, 19, 20, 21, 22, 23, 24, 25, 28, 29, 30, 31, 32, 33, 34, 37, 38, 39, 40, 41, 42, 43};
    static final int PURSE = 45, SELL_ALL = 49, CLOSE = 53, TAB0 = 2;

    static void open(MinecraftServer server, ServerPlayer p, String key) {
        ListTag cats = Economy.cfg(server).getListOrEmpty("shop");
        int idx = 0;
        for (int i = 0; i < cats.size(); i++) if (cats.getCompoundOrEmpty(i).getStringOr("key", "").equals(key)) idx = i;
        if (cats.isEmpty()) { p.sendSystemMessage(Component.literal("The shop isn't set up.").withStyle(ChatFormatting.RED)); return; }
        CompoundTag cat = cats.getCompoundOrEmpty(idx);
        SimpleContainer box = new SimpleContainer(54);
        Component title = Component.literal(cat.getStringOr("npc", "Merchant") + " - " + cat.getStringOr("name", ""));
        int finalIdx = idx;
        p.openMenu(new SimpleMenuProvider((id, inv, pl) -> new Menu(id, inv, box, server, cats, finalIdx), title));
    }

    static ItemStack named(Item item, Component name, List<Component> lore, boolean glint) {
        ItemStack s = new ItemStack(item);
        s.set(DataComponents.CUSTOM_NAME, name.copy().withStyle(st -> st.withItalic(false)));
        List<Component> l = new ArrayList<>();
        for (Component c : lore) l.add(c.copy().withStyle(st -> st.withItalic(false)));
        s.set(DataComponents.LORE, new ItemLore(l));
        if (glint) s.set(DataComponents.ENCHANTMENT_GLINT_OVERRIDE, true);
        return s;
    }

    static MutableComponent t(String s, ChatFormatting... f) { return Component.literal(s).withStyle(f); }

    static final class Menu extends ChestMenu {
        final SimpleContainer box;
        final MinecraftServer server;
        final ListTag cats;
        final int cat;
        final Item[] slotItem = new Item[54];
        final int[] buy = new int[54], sell = new int[54];

        Menu(int id, Inventory inv, SimpleContainer box, MinecraftServer server, ListTag cats, int cat) {
            super(MenuType.GENERIC_9x6, id, inv, box, 6);
            this.box = box; this.server = server; this.cats = cats; this.cat = cat;
            fill((ServerPlayer) inv.player);
        }

        void fill(ServerPlayer p) {
            ItemStack pane = named(Economy.item("minecraft:black_stained_glass_pane"), Component.literal(""), List.of(), false);
            for (int i = 0; i < 54; i++) { box.setItem(i, pane.copy()); slotItem[i] = null; }
            for (int i = 0; i < cats.size() && i < 7; i++) {
                CompoundTag c = cats.getCompoundOrEmpty(i);
                box.setItem(TAB0 + i - (cats.size() > 5 ? 1 : 0), named(Economy.item(c.getStringOr("icon", "minecraft:chest")),
                        t(c.getStringOr("name", "?"), i == cat ? ChatFormatting.GREEN : ChatFormatting.YELLOW, ChatFormatting.BOLD),
                        List.of(t(i == cat ? "You're here" : "Click to browse", ChatFormatting.GRAY)), i == cat));
            }
            ListTag items = cats.getCompoundOrEmpty(cat).getListOrEmpty("items");
            for (int i = 0; i < items.size() && i < GRID.length; i++) {
                CompoundTag e = items.getCompoundOrEmpty(i);
                Item it = Economy.item(e.getStringOr("id", ""));
                if (it == Items.AIR) continue;
                int b = e.getIntOr("buy", 0), s = e.getIntOr("sell", 0), have = Economy.count(p, it);
                int stack = Math.min(64, new ItemStack(it).getMaxStackSize());
                List<Component> lore = new ArrayList<>();
                if (b > 0) {
                    lore.add(t("Buy: ", ChatFormatting.GRAY).append(t(Economy.fmt(b) + " coins", ChatFormatting.GOLD)));
                    if (stack > 1) lore.add(t("Shift-click: buy " + stack + " for ", ChatFormatting.DARK_GRAY).append(t(Economy.fmt((long) b * stack), ChatFormatting.GOLD)));
                } else lore.add(t("Not for sale here", ChatFormatting.DARK_GRAY));
                if (s > 0) {
                    lore.add(t("Sell: ", ChatFormatting.GRAY).append(t(Economy.fmt(s) + " coins each", ChatFormatting.GOLD)));
                    lore.add(t("Right-click sell 1, shift-right sell all", ChatFormatting.DARK_GRAY));
                    if (have > 0) lore.add(t("You have " + have + " (worth " + Economy.fmt((long) have * s) + ")", ChatFormatting.GREEN));
                } else lore.add(t("The merchant won't buy this", ChatFormatting.DARK_GRAY));
                ItemStack shown = new ItemStack(it);
                shown.set(DataComponents.LORE, new ItemLore(lore.stream().map(c -> (Component) c.copy().withStyle(st -> st.withItalic(false))).toList()));
                box.setItem(GRID[i], shown);
                slotItem[GRID[i]] = it; buy[GRID[i]] = b; sell[GRID[i]] = s;
            }
            long worth = 0;
            Map<Item, Economy.Price> prices = Economy.prices(server);
            for (int i = 0; i < 36; i++) {
                ItemStack s = p.getInventory().getItem(i);
                Economy.Price pr = prices.get(s.getItem());
                if (pr != null && pr.sell() > 0 && Economy.plain(s)) worth += (long) pr.sell() * s.getCount();
            }
            box.setItem(PURSE, named(Items.GOLD_NUGGET, t("Purse: ", ChatFormatting.GRAY).append(t(Economy.fmt(Economy.coins(server, p)) + " coins", ChatFormatting.GOLD)),
                    List.of(t("/coins top shows the richest players", ChatFormatting.DARK_GRAY)), false));
            box.setItem(SELL_ALL, named(Items.HOPPER, t("Sell everything", ChatFormatting.GREEN, ChatFormatting.BOLD),
                    List.of(t("Sells every item in your inventory", ChatFormatting.GRAY), t("that any merchant buys.", ChatFormatting.GRAY),
                            t("Worth: ", ChatFormatting.GRAY).append(t(Economy.fmt(worth) + " coins", ChatFormatting.GOLD))), worth > 0));
            box.setItem(CLOSE, named(Items.BARRIER, t("Close", ChatFormatting.RED), List.of(), false));
        }

        @Override
        public void clicked(int slot, int button, ContainerInput input, Player player) {
            if (!(player instanceof ServerPlayer p) || slot < 0 || slot >= 54) { sendAllDataToRemote(); return; }
            int tabs = Math.min(7, cats.size());
            int tab = slot - TAB0 + (cats.size() > 5 ? 1 : 0);
            if (slot < 9 && tab >= 0 && tab < tabs) {
                if (tab != cat) { open(server, p, cats.getCompoundOrEmpty(tab).getStringOr("key", "")); return; }
            } else if (slot == CLOSE) { p.closeContainer(); return; }
            else if (slot == SELL_ALL) sellAll(p);
            else if (slotItem[slot] != null) {
                boolean shift = input == ContainerInput.QUICK_MOVE;
                if (button == 0 && (input == ContainerInput.PICKUP || shift)) buy(p, slot, shift);
                else if (button == 1 && (input == ContainerInput.PICKUP || shift)) sell(p, slot, shift);
            }
            fill(p);
            sendAllDataToRemote();
        }

        void buy(ServerPlayer p, int slot, boolean stack) {
            Item it = slotItem[slot];
            int price = buy[slot];
            if (price <= 0) { p.sendSystemMessage(t("The merchant doesn't sell that.", ChatFormatting.RED)); return; }
            int n = stack ? Math.min(64, new ItemStack(it).getMaxStackSize()) : 1;
            long cost = (long) price * n;
            if (!Economy.add(server, p, -cost)) {
                p.sendSystemMessage(t("You need " + Economy.fmt(cost) + " coins (you have " + Economy.fmt(Economy.coins(server, p)) + ").", ChatFormatting.RED));
                p.playSound(SoundEvents.VILLAGER_NO, 0.7f, 1f);
                return;
            }
            Economy.give(p, it, n);
            p.playSound(SoundEvents.EXPERIENCE_ORB_PICKUP, 0.6f, 1.2f);
        }

        void sell(ServerPlayer p, int slot, boolean all) {
            Item it = slotItem[slot];
            int price = sell[slot];
            if (price <= 0) { p.sendSystemMessage(t("The merchant won't buy that.", ChatFormatting.RED)); return; }
            int have = Economy.count(p, it);
            if (have == 0) { p.sendSystemMessage(t("You don't have any.", ChatFormatting.RED)); return; }
            int n = Economy.take(p, it, all ? have : 1);
            Economy.add(server, p, (long) price * n);
            p.sendSystemMessage(t("Sold " + n + " ", ChatFormatting.GRAY).append(new ItemStack(it).getHoverName().copy().withStyle(ChatFormatting.WHITE))
                    .append(t(" for " + Economy.fmt((long) price * n) + " coins", ChatFormatting.GOLD)));
            p.playSound(SoundEvents.EXPERIENCE_ORB_PICKUP, 0.6f, 1.6f);
        }

        void sellAll(ServerPlayer p) {
            Map<Item, Economy.Price> prices = Economy.prices(server);
            long total = 0;
            int items = 0;
            for (int i = 0; i < 36; i++) {
                ItemStack s = p.getInventory().getItem(i);
                Economy.Price pr = prices.get(s.getItem());
                if (pr == null || pr.sell() <= 0 || !Economy.plain(s)) continue;
                total += (long) pr.sell() * s.getCount();
                items += s.getCount();
                p.getInventory().setItem(i, ItemStack.EMPTY);
            }
            if (items == 0) { p.sendSystemMessage(t("Nothing in your inventory that the merchants buy.", ChatFormatting.RED)); return; }
            Economy.add(server, p, total);
            p.sendSystemMessage(t("Sold " + items + " items for ", ChatFormatting.GRAY).append(t(Economy.fmt(total) + " coins", ChatFormatting.GOLD)));
            p.playSound(SoundEvents.PLAYER_LEVELUP, 0.5f, 1.4f);
        }

        @Override
        public ItemStack quickMoveStack(Player player, int slot) { return ItemStack.EMPTY; }

        @Override
        public boolean stillValid(Player player) { return true; }
    }
}

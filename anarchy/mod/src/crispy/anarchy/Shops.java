package crispy.anarchy;

import net.minecraft.ChatFormatting;
import net.minecraft.core.registries.BuiltInRegistries;
import net.minecraft.nbt.CompoundTag;
import net.minecraft.nbt.ListTag;
import net.minecraft.network.chat.Component;
import net.minecraft.resources.Identifier;
import net.minecraft.server.MinecraftServer;
import net.minecraft.server.level.ServerPlayer;
import net.minecraft.server.permissions.LevelBasedPermissionSet;
import net.minecraft.world.item.Item;
import net.minecraft.world.item.ItemStack;
import net.minecraft.world.item.Items;
import net.minecraft.world.scores.Objective;
import net.minecraft.world.scores.ReadOnlyScoreInfo;

import java.util.ArrayList;
import java.util.List;

import static crispy.anarchy.Ui.t;

/**
 * The two shop menus. What's for sale comes from the datapacks (storage cyber:shop and crispy_enchants:shop, written on
 * load); a click sets the datapack's buy score and runs its buy function as the player, so the datapack does the
 * near-the-vendor check, takes the diamonds, netherite or XP, and gives the item. The menu then redraws, so the
 * "you have" counts stay current.
 */
final class Shops {
    private Shops() {}

    static Item item(String id) {
        Item it = BuiltInRegistries.ITEM.getValue(Identifier.withDefaultNamespace(id));
        return it == null || it == Items.AIR ? Items.PAPER : it;
    }
    static ChatFormatting color(String name) {
        try { return ChatFormatting.valueOf(name.toUpperCase(java.util.Locale.ROOT)); } catch (IllegalArgumentException e) { return ChatFormatting.WHITE; }
    }
    static int score(ServerPlayer p, String objective) {
        Objective o = p.level().getServer().getScoreboard().getObjective(objective);
        if (o == null) return 0;
        ReadOnlyScoreInfo s = p.level().getServer().getScoreboard().getPlayerScoreInfo(p, o);
        return s == null ? 0 : s.value();
    }
    static int scoreOf(MinecraftServer server, String holder, String objective) {
        Objective o = server.getScoreboard().getObjective(objective);
        if (o == null) return 0;
        ReadOnlyScoreInfo s = server.getScoreboard().getPlayerScoreInfo(net.minecraft.world.scores.ScoreHolder.forNameOnly(holder), o);
        return s == null ? 0 : s.value();
    }
    static int count(ServerPlayer p, Item it) {
        int n = 0;
        var inv = p.getInventory();
        for (int i = 0; i < inv.getContainerSize(); i++) if (inv.getItem(i).is(it)) n += inv.getItem(i).getCount();
        return n;
    }
    /** Runs commands as the player, at the player (so @s and distance checks are theirs), with function-level rights. */
    static void run(ServerPlayer p, String... cmds) {
        var src = p.createCommandSourceStack().withPermission(LevelBasedPermissionSet.GAMEMASTER).withSuppressedOutput();
        for (String c : cmds) p.level().getServer().getCommands().performPrefixedCommand(src, c);
    }
    static CompoundTag storage(MinecraftServer server, String id) { return server.getCommandStorage().get(Identifier.parse(id)); }

    // ------------------------------------------------------------------ Ripperdoc
    static final int[] GRID = {10, 11, 12, 13, 14, 15, 16, 19, 20, 21, 22, 23, 24, 25, 28, 29, 30, 31, 32, 33, 34};

    static void ripperdoc(ServerPlayer p) {
        MinecraftServer server = p.level().getServer();
        ListTag items = storage(server, "cyber:shop").getListOrEmpty("items");
        if (items.isEmpty()) { p.sendSystemMessage(t("The Ripperdoc isn't open yet.", ChatFormatting.RED)); return; }
        Ui.open(p, t("⚕ Ripperdoc ⚕", ChatFormatting.DARK_AQUA), 6, m -> {
            int cap = score(p, "cy.cap"), limit = scoreOf(server, "#limit", "cy");
            m.put(4, Ui.item(Items.IRON_CHESTPLATE, t("⚕ Ripperdoc ⚕", ChatFormatting.AQUA, ChatFormatting.BOLD), List.of(
                    t("Chrome for sale. One implant per body slot;", ChatFormatting.GRAY),
                    t("hold right-click with it to install.", ChatFormatting.GRAY),
                    t("Over " + limit + " capacity you risk cyberpsychosis.", ChatFormatting.RED),
                    t("All installed implants drop when you die.", ChatFormatting.GOLD)), false), null);
            for (int i = 0; i < items.size() && i < GRID.length; i++) {
                CompoundTag it = items.getCompoundOrEmpty(i);
                int id = it.getIntOr("id", 0), slot = it.getIntOr("slot", 0), n = it.getIntOr("n", 1), cost = it.getIntOr("cap", 0);
                String payItem = it.getStringOr("item", "diamond"), name = it.getStringOr("name", "?");
                int have = count(p, item(payItem));
                List<Component> lore = new ArrayList<>();
                if (slot > 0) lore.add(t(it.getStringOr("slotname", "") + " · capacity " + cost, ChatFormatting.DARK_GRAY));
                ListTag ll = it.getListOrEmpty("lore");
                for (int j = 0; j < ll.size(); j++) lore.add(t(ll.getStringOr(j, ""), ChatFormatting.GRAY));
                lore.add(Component.empty());
                String pay = n + " " + (payItem.equals("diamond") ? "Diamond" + (n == 1 ? "" : "s") : "Netherite Ingot" + (n == 1 ? "" : "s"));
                lore.add(t("Price: " + pay, ChatFormatting.GOLD).append(t("  (you have " + have + ")", have >= n ? ChatFormatting.GREEN : ChatFormatting.RED)));
                int inSlot = slot > 0 ? score(p, "cy.s" + slot) : 0;
                if (slot > 0 && inSlot == id) lore.add(t("✔ You have this installed", ChatFormatting.GREEN));
                else if (slot > 0 && inSlot != 0) lore.add(t("Your " + it.getStringOr("slotname", "") + " slot is taken: remove that first to install", ChatFormatting.YELLOW));
                if (slot > 0 && cap + cost > limit) lore.add(t("Takes you to " + (cap + cost) + "/" + limit + " capacity: cyberpsychosis risk", ChatFormatting.RED));
                lore.add(t(have >= n ? "Click to buy" : "You can't afford this", have >= n ? ChatFormatting.YELLOW : ChatFormatting.DARK_GRAY));
                ItemStack icon = Ui.item(item(it.getStringOr("icon", "paper")), t(name, color(it.getStringOr("color", "white")), ChatFormatting.BOLD), lore, inSlot == id && slot > 0);
                m.put(GRID[i], icon, (pl, c) -> run(pl, "scoreboard players set @s cy.buy " + id, "function cyber:doc/buy"));
            }
            m.put(48, Ui.item(Items.SHEARS, t("Remove an implant…", ChatFormatting.YELLOW, ChatFormatting.BOLD), List.of(
                    t("Take one out and get the item back (free).", ChatFormatting.GRAY)), false), (pl, c) -> remover(pl));
            m.put(50, Ui.item(Items.COMPARATOR, t("Capacity: " + cap + "/" + limit, cap > limit ? ChatFormatting.RED : ChatFormatting.AQUA, ChatFormatting.BOLD), List.of(
                    t("Every implant uses capacity.", ChatFormatting.GRAY),
                    t("Click for your full status in chat", ChatFormatting.DARK_GRAY)), false), (pl, c) -> { pl.closeContainer(); run(pl, "function cyber:status"); });
        });
    }

    static void remover(ServerPlayer p) {
        MinecraftServer server = p.level().getServer();
        CompoundTag shop = storage(server, "cyber:shop");
        ListTag slots = shop.getListOrEmpty("slots"), items = shop.getListOrEmpty("items");
        Ui.open(p, t("Remove an implant", ChatFormatting.DARK_GRAY), 3, m -> {
            int[] at = {10, 11, 12, 13, 14, 15, 16, 21, 23};
            for (int i = 0; i < slots.size() && i < at.length; i++) {
                CompoundTag s = slots.getCompoundOrEmpty(i);
                int slot = s.getIntOr("slot", 0), inSlot = score(p, "cy.s" + slot);
                String sname = s.getStringOr("name", "?");
                CompoundTag found = null;
                for (int j = 0; j < items.size(); j++) if (items.getCompoundOrEmpty(j).getIntOr("id", -1) == inSlot) found = items.getCompoundOrEmpty(j);
                if (inSlot == 0) m.put(at[i], Ui.item(item("gray_stained_glass_pane"), t(sname + ": empty", ChatFormatting.DARK_GRAY), List.of(), false), null);
                else {
                    String name = found == null ? "an implant" : found.getStringOr("name", "an implant");
                    m.put(at[i], Ui.item(item(found == null ? "paper" : found.getStringOr("icon", "paper")),
                            t(sname + ": " + name, found == null ? ChatFormatting.WHITE : color(found.getStringOr("color", "white")), ChatFormatting.BOLD),
                            List.of(t("Click to remove it (free)", ChatFormatting.YELLOW), t("It goes back into your inventory", ChatFormatting.GRAY)), false),
                            (pl, c) -> run(pl, "scoreboard players set @s cy.rm " + slot, "function cyber:doc/remove"));
                }
            }
            m.put(18, Ui.item(Items.ARROW, t("Back", ChatFormatting.YELLOW), List.of(), false), (pl, c) -> ripperdoc(pl));
        });
    }

    // ------------------------------------------------------------------ Enchanter
    /** The player's total XP in points (what the Enchanter charges). */
    static int xpPoints(ServerPlayer p) {
        int l = p.experienceLevel;
        double base = l <= 16 ? l * l + 6 * l : l <= 31 ? 2.5 * l * l - 40.5 * l + 360 : 4.5 * l * l - 162.5 * l + 2220;
        return (int) Math.round(base + p.experienceProgress * p.getXpNeededForNextLevel());
    }
    static String fmt(int n) { return String.format("%,d", n); }

    static void enchanter(ServerPlayer p) {
        MinecraftServer server = p.level().getServer();
        CompoundTag shop = storage(server, "crispy_enchants:shop");
        ListTag tiers = shop.getListOrEmpty("tiers");
        if (tiers.isEmpty()) { p.sendSystemMessage(t("The Enchanter isn't open yet.", ChatFormatting.RED)); return; }
        Ui.open(p, t("✦ Enchanter ✦", ChatFormatting.DARK_PURPLE), 4, m -> {
            int xp = xpPoints(p);
            m.put(4, Ui.item(Items.ENCHANTING_TABLE, t("✦ Enchanter ✦", ChatFormatting.LIGHT_PURPLE, ChatFormatting.BOLD), List.of(
                    t("Buy random custom enchantment books with XP,", ChatFormatting.GRAY),
                    t("then combine them with your gear in an anvil.", ChatFormatting.GRAY),
                    Component.empty(), t("Your XP: " + fmt(xp) + " points", ChatFormatting.GREEN)), false), null);
            int[] at = {10, 11, 12, 13, 14, 15, 16, 19, 20, 21};
            for (int i = 0; i < tiers.size() && i < at.length; i++) {
                CompoundTag tr = tiers.getCompoundOrEmpty(i);
                int id = tr.getIntOr("id", 0), price = tr.getIntOr("price", 0);
                boolean ok = xp >= price;
                m.put(at[i], Ui.item(Items.ENCHANTED_BOOK, t(tr.getStringOr("name", "?") + " book", color(tr.getStringOr("color", "white")), ChatFormatting.BOLD), List.of(
                        t("A random " + tr.getStringOr("name", "") + " enchantment book", ChatFormatting.GRAY),
                        t("(" + tr.getIntOr("count", 0) + " possible)", ChatFormatting.DARK_GRAY), Component.empty(),
                        t("Price: " + fmt(price) + " XP points", ChatFormatting.GOLD),
                        t(ok ? "Click to buy" : "You need " + fmt(price - xp) + " more XP", ok ? ChatFormatting.YELLOW : ChatFormatting.RED)), false),
                        (pl, c) -> run(pl, "scoreboard players set @s ce.buy " + id, "function crispy_enchants:enchanter/buy"));
            }
            CompoundTag h = shop.getCompoundOrEmpty("heroic");
            int hp = h.getIntOr("price", 50000);
            m.put(31, Ui.item(Items.NETHER_STAR, t("Heroic upgrade (held item)", ChatFormatting.LIGHT_PURPLE, ChatFormatting.BOLD), List.of(
                    t("Upgrades a base enchantment on the item", ChatFormatting.GRAY),
                    t("in your hand to its Heroic version", ChatFormatting.GRAY),
                    t("(e.g. Overload III → Godly Overload).", ChatFormatting.GRAY), Component.empty(),
                    t("Price: " + fmt(hp) + " XP points", ChatFormatting.GOLD),
                    t(xp >= hp ? "Click to upgrade your held item" : "You need " + fmt(hp - xp) + " more XP", xp >= hp ? ChatFormatting.YELLOW : ChatFormatting.RED)), true),
                    (pl, c) -> run(pl, "scoreboard players set @s ce.buy " + h.getIntOr("id", 50), "function crispy_enchants:enchanter/buy"));
        });
    }
}

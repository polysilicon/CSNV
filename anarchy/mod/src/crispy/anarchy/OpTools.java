package crispy.anarchy;

import net.fabricmc.fabric.api.command.v2.CommandRegistrationCallback;
import net.minecraft.ChatFormatting;
import net.minecraft.commands.CommandSourceStack;
import net.minecraft.commands.Commands;
import net.minecraft.commands.arguments.EntityArgument;
import net.minecraft.network.chat.Component;
import net.minecraft.server.level.ServerPlayer;
import net.minecraft.world.Container;
import net.minecraft.world.SimpleMenuProvider;
import net.minecraft.world.entity.player.Inventory;
import net.minecraft.world.entity.player.Player;
import net.minecraft.world.inventory.ChestMenu;
import net.minecraft.world.inventory.MenuType;
import net.minecraft.world.inventory.Slot;
import net.minecraft.world.item.ItemStack;

/**
 * Op tools (1.1.2): /ecsee <player> opens an online player's ender chest, /invsee <player> their inventory (main,
 * armour and offhand), as a chest menu on the real containers, so taking or adding items changes theirs straight away.
 * Ops only (permission level 2); every use is logged to the console.
 */
final class OpTools {
    private OpTools() {}

    static void init() {
        CommandRegistrationCallback.EVENT.register((d, ctx, env) -> {
            d.register(Commands.literal("ecsee").requires(Commands.hasPermission(Commands.LEVEL_GAMEMASTERS))
                    .then(Commands.argument("player", EntityArgument.player())
                            .executes(c -> ecsee(c.getSource(), EntityArgument.getPlayer(c, "player")))));
            d.register(Commands.literal("invsee").requires(Commands.hasPermission(Commands.LEVEL_GAMEMASTERS))
                    .then(Commands.argument("player", EntityArgument.player())
                            .executes(c -> invsee(c.getSource(), EntityArgument.getPlayer(c, "player")))));
        });
    }

    static int ecsee(CommandSourceStack s, ServerPlayer target) throws com.mojang.brigadier.exceptions.CommandSyntaxException {
        ServerPlayer op = s.getPlayerOrException();
        op.openMenu(new SimpleMenuProvider((id, inv, pl) -> ChestMenu.threeRows(id, inv, target.getEnderChestInventory()),
                Component.literal(target.getScoreboardName() + "'s Ender Chest")));
        log(op, "ender chest", target);
        return 1;
    }

    static int invsee(CommandSourceStack s, ServerPlayer target) throws com.mojang.brigadier.exceptions.CommandSyntaxException {
        ServerPlayer op = s.getPlayerOrException();
        Container view = new InvView(target.getInventory());
        op.openMenu(new SimpleMenuProvider((id, inv, pl) -> {
            ChestMenu m = new ChestMenu(MenuType.GENERIC_9x5, id, inv, view, 5);
            // the last 4 of the 45 slots aren't part of the inventory (it has 41): lock them
            for (int i = InvView.REAL; i < 45; i++) {
                Slot old = m.slots.get(i);
                Slot locked = new Slot(view, i, old.x, old.y) {
                    @Override public boolean mayPlace(ItemStack st) { return false; }
                    @Override public boolean mayPickup(Player p) { return false; }
                };
                locked.index = i;
                m.slots.set(i, locked);
            }
            return m;
        }, Component.literal(target.getScoreboardName() + "'s Inventory (row 4 = hotbar, then armour + offhand)")));
        log(op, "inventory", target);
        return 1;
    }

    static void log(ServerPlayer op, String what, ServerPlayer target) {
        System.out.println("[crispy-anarchy] " + op.getScoreboardName() + " opened " + target.getScoreboardName() + "'s " + what);
        op.sendSystemMessage(Component.literal("Opened " + target.getScoreboardName() + "'s " + what + ". Changes apply to theirs right away.")
                .withStyle(ChatFormatting.GRAY));
    }

    /** A 45-slot view over a player's 41-slot inventory: 0-35 main (0-8 hotbar), 36-39 armour, 40 offhand, 41-44 unused. */
    static final class InvView implements Container {
        static final int REAL = 41;
        final Inventory inv;
        InvView(Inventory inv) { this.inv = inv; }
        // show the hotbar on the 4th row (like the player's own screen): view rows 0-2 = main 9-35, row 3 = hotbar 0-8
        static int map(int i) { return i < 27 ? i + 9 : i < 36 ? i - 27 : i; }
        @Override public int getContainerSize() { return 45; }
        @Override public boolean isEmpty() { return inv.isEmpty(); }
        @Override public ItemStack getItem(int i) { return i < REAL ? inv.getItem(map(i)) : ItemStack.EMPTY; }
        @Override public ItemStack removeItem(int i, int n) { return i < REAL ? inv.removeItem(map(i), n) : ItemStack.EMPTY; }
        @Override public ItemStack removeItemNoUpdate(int i) { return i < REAL ? inv.removeItemNoUpdate(map(i)) : ItemStack.EMPTY; }
        @Override public void setItem(int i, ItemStack st) { if (i < REAL) inv.setItem(map(i), st); }
        @Override public void setChanged() { inv.setChanged(); }
        @Override public boolean stillValid(Player p) { return inv.player.isAlive() && !inv.player.isRemoved(); }
        @Override public void clearContent() {}
    }
}

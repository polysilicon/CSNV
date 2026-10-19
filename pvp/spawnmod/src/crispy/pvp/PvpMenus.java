package crispy.pvp;

import net.minecraft.nbt.CompoundTag;
import net.minecraft.nbt.ListTag;
import net.minecraft.nbt.NbtOps;
import net.minecraft.nbt.Tag;
import net.minecraft.network.chat.Component;
import net.minecraft.network.chat.ComponentSerialization;
import net.minecraft.resources.Identifier;
import net.minecraft.resources.RegistryOps;
import net.minecraft.server.MinecraftServer;
import net.minecraft.server.level.ServerPlayer;
import net.minecraft.world.SimpleContainer;
import net.minecraft.world.SimpleMenuProvider;
import net.minecraft.world.entity.player.Inventory;
import net.minecraft.world.entity.player.Player;
import net.minecraft.world.inventory.ChestMenu;
import net.minecraft.world.inventory.ContainerInput;
import net.minecraft.world.inventory.MenuType;
import net.minecraft.world.item.ItemStack;

/**
 * Chest-style menus defined by the crispy_pvp datapack in storage pvp:menus, e.g.
 * {kits:{title:{text:"Kits"},rows:4,fill:{id:"minecraft:black_stained_glass_pane"},items:[{slot:11,item:{...},cmd:"trigger pvp.kit set 1"}]}}
 * Clicking an item closes the menu and runs its cmd as the player; every other click is ignored.
 */
public final class PvpMenus {
    private PvpMenus() {}

    @SuppressWarnings("unchecked")
    private static final MenuType<ChestMenu>[] TYPES = new MenuType[]{MenuType.GENERIC_9x1, MenuType.GENERIC_9x2,
            MenuType.GENERIC_9x3, MenuType.GENERIC_9x4, MenuType.GENERIC_9x5, MenuType.GENERIC_9x6};

    public static boolean open(MinecraftServer server, ServerPlayer player, String key) {
        CompoundTag menu = server.getCommandStorage().get(Identifier.fromNamespaceAndPath("pvp", "menus")).getCompoundOrEmpty(key);
        if (menu.isEmpty()) return false;
        int rows = Math.max(1, Math.min(6, menu.getIntOr("rows", 3)));
        RegistryOps<Tag> ops = server.registryAccess().createSerializationContext(NbtOps.INSTANCE);
        SimpleContainer box = new SimpleContainer(rows * 9);
        String[] cmds = new String[rows * 9];
        Tag fill = menu.get("fill");
        if (fill != null) {
            ItemStack pane = ItemStack.CODEC.parse(ops, fill).result().orElse(ItemStack.EMPTY);
            for (int i = 0; i < rows * 9; i++) box.setItem(i, pane.copy());
        }
        ListTag items = menu.getListOrEmpty("items");
        for (int i = 0; i < items.size(); i++) {
            CompoundTag entry = items.getCompoundOrEmpty(i);
            int slot = entry.getIntOr("slot", -1);
            Tag item = entry.get("item");
            if (slot < 0 || slot >= rows * 9 || item == null) continue;
            box.setItem(slot, ItemStack.CODEC.parse(ops, item).result().orElse(ItemStack.EMPTY));
            cmds[slot] = entry.getStringOr("cmd", "");
        }
        Tag t = menu.get("title");
        Component title = t == null ? Component.literal(key) : ComponentSerialization.CODEC.parse(ops, t).result().orElse(Component.literal(key));
        MenuType<ChestMenu> type = TYPES[rows - 1];
        player.openMenu(new SimpleMenuProvider((id, inv, p) -> new Menu(type, id, inv, box, rows, cmds, server), title));
        return true;
    }

    static final class Menu extends ChestMenu {
        private final String[] cmds;
        private final MinecraftServer server;

        Menu(MenuType<ChestMenu> type, int id, Inventory inv, SimpleContainer box, int rows, String[] cmds, MinecraftServer server) {
            super(type, id, inv, box, rows);
            this.cmds = cmds;
            this.server = server;
        }

        @Override
        public void clicked(int slot, int button, ContainerInput input, Player player) {
            if (player instanceof ServerPlayer sp && slot >= 0 && slot < cmds.length && cmds[slot] != null && !cmds[slot].isEmpty()) {
                String cmd = cmds[slot];
                sp.closeContainer();
                server.getCommands().performPrefixedCommand(sp.createCommandSourceStack().withSuppressedOutput(), cmd);
                return;
            }
            sendAllDataToRemote();   // undo whatever the client predicted
        }

        @Override
        public ItemStack quickMoveStack(Player player, int slot) { return ItemStack.EMPTY; }

        @Override
        public boolean stillValid(Player player) { return true; }
    }
}

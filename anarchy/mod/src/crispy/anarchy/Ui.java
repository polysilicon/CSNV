package crispy.anarchy;

import net.minecraft.ChatFormatting;
import net.minecraft.core.component.DataComponents;
import net.minecraft.network.chat.Component;
import net.minecraft.network.chat.MutableComponent;
import net.minecraft.server.level.ServerPlayer;
import net.minecraft.world.SimpleContainer;
import net.minecraft.world.SimpleMenuProvider;
import net.minecraft.world.entity.player.Inventory;
import net.minecraft.world.entity.player.Player;
import net.minecraft.world.inventory.ChestMenu;
import net.minecraft.world.inventory.ContainerInput;
import net.minecraft.world.inventory.MenuType;
import net.minecraft.world.item.Item;
import net.minecraft.world.item.ItemStack;
import net.minecraft.world.item.component.ItemLore;

import java.util.HashMap;
import java.util.List;
import java.util.Map;
import java.util.function.Consumer;

/**
 * Chest menus built in code (the Ripperdoc and the Enchanter): a filler puts items in and binds actions to slots;
 * after any click the filler runs again, so the menu always shows the current state. Nothing can be taken out.
 */
final class Ui {
    private Ui() {}

    record Click(int button, boolean shift) { boolean right() { return button == 1; } }
    interface Action { void run(ServerPlayer p, Click c); }

    static MutableComponent t(String s, ChatFormatting... f) { return Component.literal(s).withStyle(f).withStyle(st -> st.withItalic(false)); }

    static ItemStack item(Item it, Component name, List<? extends Component> lore, boolean glow) { return item(new ItemStack(it), name, lore, glow); }
    static ItemStack item(ItemStack s, Component name, List<? extends Component> lore, boolean glow) {
        s.set(DataComponents.CUSTOM_NAME, name.copy().withStyle(st -> st.withItalic(false)));
        s.set(DataComponents.LORE, new ItemLore(lore.stream().map(c -> (Component) c.copy().withStyle(st -> st.withItalic(false))).toList()));
        if (glow) s.set(DataComponents.ENCHANTMENT_GLINT_OVERRIDE, true);
        return s;
    }

    static final class Menu extends ChestMenu {
        final SimpleContainer box;
        final int rows;
        final Map<Integer, Action> actions = new HashMap<>();
        final Consumer<Menu> filler;
        final ServerPlayer viewer;

        Menu(int id, Inventory inv, SimpleContainer box, int rows, Consumer<Menu> filler) {
            super(switch (rows) { case 1 -> MenuType.GENERIC_9x1; case 2 -> MenuType.GENERIC_9x2; case 3 -> MenuType.GENERIC_9x3;
                                  case 4 -> MenuType.GENERIC_9x4; case 5 -> MenuType.GENERIC_9x5; default -> MenuType.GENERIC_9x6; }, id, inv, box, rows);
            this.box = box; this.rows = rows; this.filler = filler; this.viewer = (ServerPlayer) inv.player;
            refill();
        }

        void refill() {
            actions.clear();
            ItemStack pane = item(net.minecraft.core.registries.BuiltInRegistries.ITEM.getValue(net.minecraft.resources.Identifier.withDefaultNamespace("black_stained_glass_pane")), Component.literal(" "), List.of(), false);
            for (int i = 0; i < rows * 9; i++) box.setItem(i, pane.copy());
            filler.accept(this);
        }

        void put(int slot, ItemStack s, Action a) { box.setItem(slot, s); if (a != null) actions.put(slot, a); else actions.remove(slot); }

        @Override
        public void clicked(int slot, int button, ContainerInput input, Player player) {
            if (player instanceof ServerPlayer p && slot >= 0 && slot < rows * 9) {
                Action a = actions.get(slot);
                boolean shift = input == ContainerInput.QUICK_MOVE;
                if (a != null && (input == ContainerInput.PICKUP || shift)) {
                    a.run(p, new Click(button, shift));
                    if (p.containerMenu == this) refill();
                }
            }
            sendAllDataToRemote();
        }

        @Override public ItemStack quickMoveStack(Player player, int slot) { return ItemStack.EMPTY; }
    }

    static void open(ServerPlayer p, Component title, int rows, Consumer<Menu> filler) {
        SimpleContainer box = new SimpleContainer(rows * 9);
        p.openMenu(new SimpleMenuProvider((id, inv, pl) -> new Menu(id, inv, box, rows, filler), title));
    }
}

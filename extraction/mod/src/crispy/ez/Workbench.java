package crispy.ez;

import net.fabricmc.fabric.api.command.v2.CommandRegistrationCallback;
import net.fabricmc.fabric.api.event.player.UseBlockCallback;
import net.minecraft.ChatFormatting;
import net.minecraft.commands.Commands;
import net.minecraft.core.component.DataComponents;
import net.minecraft.nbt.CompoundTag;
import net.minecraft.network.chat.Component;
import net.minecraft.server.level.ServerPlayer;
import net.minecraft.world.InteractionResult;
import net.minecraft.world.entity.player.Inventory;
import net.minecraft.world.item.ItemStack;
import net.minecraft.world.item.Items;
import net.minecraft.world.item.component.CustomData;
import net.minecraft.world.item.component.ItemLore;
import net.minecraft.world.level.block.Blocks;

import java.util.ArrayList;
import java.util.List;

import static crispy.ez.Ui.t;

/**
 * Gun Workbench (a stash upgrade, 1.1.0). Mods a gun you carry: Extended Magazine (+50% rounds) and Quick Reload (35%
 * faster). The mod is written on the gun item as custom_data {ezmod:{mag:1b,rl:1b}}; the datapack's magazine code
 * (gun/reload_*, gun/fill_*, the ammo gate) reads it from the gun in your main hand. Mods stay with the gun, so a gun
 * looted off you keeps them.
 */
final class Workbench {
    private Workbench() {}

    static final int COST = 40;
    record Mod(String key, String name, String line) {}
    static final Mod[] MODS = {new Mod("mag", "Extended Magazine", "+50% rounds per magazine"), new Mod("rl", "Quick Reload", "Reloads 35% faster")};

    static void init() {
        UseBlockCallback.EVENT.register((pl, world, hand, hit) -> {
            if (!(pl instanceof ServerPlayer p) || !world.dimension().equals(Plots.CAMP)) return InteractionResult.PASS;
            if (!world.getBlockState(hit.getBlockPos()).is(Blocks.SMITHING_TABLE) || !Plots.hasPerk(p, "workbench")) return InteractionResult.PASS;
            Plots.Plot plot = Plots.of(p);
            if (plot == null || !Plots.inside(plot, hit.getBlockPos())) return InteractionResult.PASS;
            if (hand == net.minecraft.world.InteractionHand.MAIN_HAND) open(p);
            return InteractionResult.SUCCESS;
        });
        CommandRegistrationCallback.EVENT.register((d, ctx, env) -> d.register(Commands.literal("workbench").executes(c -> {
            ServerPlayer p = c.getSource().getPlayerOrException();
            if (!p.level().dimension().equals(Plots.CAMP)) { Shops.no(p, "The workbench is on your plot in camp."); return 0; }
            if (!Plots.hasPerk(p, "workbench")) { Shops.no(p, "Buy a Gun Workbench for your plot from the Plot Manager first."); return 0; }
            open(p); return 1;
        })));
    }

    static boolean isGun(ItemStack s) { return Relief.isGun(s); }
    static boolean has(ItemStack s, String mod) {
        CustomData cd = s.get(DataComponents.CUSTOM_DATA);
        return cd != null && cd.copyTag().getCompoundOrEmpty("ezmod").getBooleanOr(mod, false);
    }

    static void apply(ItemStack s, Mod mod) {
        CompoundTag tag = s.getOrDefault(DataComponents.CUSTOM_DATA, CustomData.EMPTY).copyTag();
        CompoundTag mods = tag.getCompoundOrEmpty("ezmod");
        mods.putBoolean(mod.key(), true);
        tag.put("ezmod", mods);
        s.set(DataComponents.CUSTOM_DATA, CustomData.of(tag));
        List<Component> lore = new ArrayList<>(s.getOrDefault(DataComponents.LORE, ItemLore.EMPTY).lines());
        lore.add(0, t("✚ " + mod.name() + ": " + mod.line(), ChatFormatting.AQUA));
        s.set(DataComponents.LORE, new ItemLore(lore));
    }

    static void open(ServerPlayer p) {
        Ui.open(p, t("Gun Workbench", ChatFormatting.DARK_GRAY), 4, m -> {
            m.put(4, Shops.balanceIcon(p), null);
            Inventory inv = p.getInventory();
            int col = 0;
            for (int i = 0; i < inv.getContainerSize() && col < 9; i++) {
                ItemStack g = inv.getItem(i);
                if (!isGun(g)) continue;
                final int slot = i;
                m.put(9 + col, g.copy(), null);
                for (int r = 0; r < MODS.length; r++) {
                    Mod mod = MODS[r];
                    boolean done = has(g, mod.key());
                    m.put(18 + 9 * r + col, Ui.item(done ? Items.EMERALD : (r == 0 ? Items.IRON_INGOT : Items.FEATHER),
                            t((done ? "✔ " : "") + mod.name(), done ? ChatFormatting.GREEN : ChatFormatting.YELLOW), List.of(
                                    t(mod.line(), ChatFormatting.GRAY), t(done ? "Fitted" : "Cost: " + Coins.fmt(COST), done ? ChatFormatting.GREEN : ChatFormatting.GOLD)), done),
                            done ? null : (pl, c) -> {
                                ItemStack now = pl.getInventory().getItem(slot);
                                if (!isGun(now) || has(now, mod.key())) return;
                                if (!Shops.pay(pl, COST)) { Shops.no(pl, "You need " + Coins.fmt(COST) + "."); return; }
                                apply(now, mod);
                                pl.getInventory().setChanged();
                                Shops.ok(pl, mod.name() + " fitted to your " + now.getHoverName().getString() + ".");
                            });
                }
                col++;
            }
            if (col == 0) m.put(13, Ui.item(Items.BARRIER, t("No guns on you", ChatFormatting.RED), List.of(t("Carry the gun you want to mod.", ChatFormatting.GRAY)), false), null);
            m.put(31, Ui.item(Items.BARRIER, t("Close", ChatFormatting.RED), List.of(), false), (pl, c) -> pl.closeContainer());
        });
    }
}

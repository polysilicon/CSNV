package crispy.ez;

import net.fabricmc.fabric.api.event.player.PlayerBlockBreakEvents;
import net.fabricmc.fabric.api.event.player.UseBlockCallback;
import net.minecraft.core.BlockPos;
import net.minecraft.core.component.DataComponents;
import net.minecraft.core.registries.BuiltInRegistries;
import net.minecraft.server.MinecraftServer;
import net.minecraft.server.level.ServerLevel;
import net.minecraft.server.level.ServerPlayer;
import net.minecraft.world.Container;
import net.minecraft.world.Containers;
import net.minecraft.world.InteractionResult;
import net.minecraft.world.item.ItemStack;
import net.minecraft.world.item.component.CustomData;
import net.minecraft.world.level.block.Blocks;
import net.minecraft.world.level.block.entity.BlockEntity;
import net.minecraft.world.level.chunk.LevelChunk;

import java.util.Set;

/**
 * Plot storage limits (1.2.0). Vanilla containers can't be placed in camp; storage is the Stash Crate (a barrel named
 * "Stash Crate", custom_data ez:"stash", sold by the Builder), and a plot holds at most LIMIT[plot size] containers.
 * Breaking a crate on your plot drops what's in it and gives the crate back as a Stash Crate, so it can be moved.
 */
final class Storage {
    private Storage() {}

    static final int[] LIMIT = {4, 7, 10};   // by plot size 16 / 24 / 32
    static final String CRATE_BLOCK = "minecraft:barrel[facing=up]{CustomName:{text:\"Stash Crate\",color:\"gold\",italic:false}}";
    static final Set<String> CONTAINERS = Set.of("minecraft:chest", "minecraft:trapped_chest", "minecraft:barrel", "minecraft:ender_chest",
            "minecraft:hopper", "minecraft:dropper", "minecraft:dispenser", "minecraft:crafter", "minecraft:decorated_pot", "minecraft:chest_minecart",
            "minecraft:hopper_minecart");

    static boolean isCrate(ItemStack s) {
        CustomData cd = s.get(DataComponents.CUSTOM_DATA);
        return s.is(net.minecraft.world.item.Items.BARREL) && cd != null && "stash".equals(cd.copyTag().getString("ez").orElse(""));
    }
    static boolean banned(ItemStack s) {
        String id = BuiltInRegistries.ITEM.getKey(s.getItem()).toString();
        return CONTAINERS.contains(id) || id.endsWith("shulker_box") || id.endsWith("_chest_boat");
    }
    static int limit(Plots.Plot p) { return LIMIT[Math.min(p.level, LIMIT.length - 1)]; }

    /** Containers on the plot now. */
    static int count(MinecraftServer server, Plots.Plot p) {
        ServerLevel camp = server.getLevel(Plots.CAMP);
        if (camp == null) return 0;
        int x = Plots.cx(p.index), z = Plots.cz(p.index), h = Plots.half(p), n = 0;
        for (int qx = (x - h) >> 4; qx <= (x + h) >> 4; qx++)
            for (int qz = (z - h) >> 4; qz <= (z + h) >> 4; qz++) {
                LevelChunk ch = camp.getChunk(qx, qz);
                for (BlockEntity be : ch.getBlockEntities().values())
                    if (be instanceof Container && !(be instanceof net.minecraft.world.level.block.entity.AbstractFurnaceBlockEntity)
                            && !(be instanceof net.minecraft.world.level.block.entity.BrewingStandBlockEntity)
                            && !(be instanceof net.minecraft.world.level.block.entity.JukeboxBlockEntity)
                            && Plots.inside(p, be.getBlockPos())) n++;
            }
        return n;
    }

    static void init() {
        UseBlockCallback.EVENT.register((pl, world, hand, hit) -> {
            if (!(pl instanceof ServerPlayer p) || !world.dimension().equals(Plots.CAMP) || p.isCreative()) return InteractionResult.PASS;
            ItemStack held = p.getItemInHand(hand);
            if (isCrate(held)) {
                Plots.Plot plot = Plots.of(p);
                if (plot == null) return InteractionResult.PASS;   // the plot protection refuses it anyway
                int n = count(p.level().getServer(), plot), max = limit(plot);
                if (n >= max) {
                    Shops.no(p, "Your bunker holds " + max + " Stash Crates" + (plot.level + 1 < LIMIT.length ? ". A bigger bunker holds more (Bunker Manager)." : "."));
                    return InteractionResult.FAIL;
                }
                p.sendSystemMessage(Ui.t("Stash Crate " + (n + 1) + " / " + max, net.minecraft.ChatFormatting.GOLD), true);
                return InteractionResult.PASS;
            }
            if (banned(held)) {
                Shops.no(p, "Bunker storage is Stash Crates only: buy them from the Builder.");
                return InteractionResult.FAIL;
            }
            return InteractionResult.PASS;
        });
        PlayerBlockBreakEvents.BEFORE.register((world, pl, pos, state, be) -> {
            if (!(pl instanceof ServerPlayer p) || !world.dimension().equals(Plots.CAMP) || p.isCreative() || !state.is(Blocks.BARREL)) return true;
            Plots.Plot plot = Plots.of(p);
            if (plot == null || !Plots.inside(plot, pos)) return true;
            if (be instanceof Container c) Containers.dropContents(world, pos, c);
            world.removeBlock(pos, false);
            Shops.give(p, crate(p.level().getServer()));
            return false;
        });
    }

    static ItemStack crateItem;
    static ItemStack crate(MinecraftServer server) {
        if (crateItem == null) {
            Shops.load(server);
            Shops.Shop b = Shops.SHOPS.get("builder");
            if (b != null) for (Shops.Buy x : b.buy()) if (isCrate(x.item())) crateItem = x.item().copyWithCount(1);
        }
        return crateItem == null ? new ItemStack(net.minecraft.world.item.Items.BARREL) : crateItem.copy();
    }
}

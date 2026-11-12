package crispy.ez;

import net.fabricmc.fabric.api.command.v2.CommandRegistrationCallback;
import net.minecraft.ChatFormatting;
import net.minecraft.commands.Commands;
import net.minecraft.core.component.DataComponents;
import net.minecraft.server.MinecraftServer;
import net.minecraft.server.level.ServerLevel;
import net.minecraft.server.level.ServerPlayer;
import net.minecraft.world.Container;
import net.minecraft.world.item.ItemStack;
import net.minecraft.world.item.Items;
import net.minecraft.world.level.block.entity.BlockEntity;
import net.minecraft.world.level.chunk.LevelChunk;

import java.util.HashMap;
import java.util.Map;
import java.util.UUID;

import static crispy.ez.Ui.t;

/**
 * Relief kit: a player who has lost everything (no gun and under BROKE coins, counting both their inventory and every
 * container on their stash plot) gets a basic kit back in camp: a pistol, ammo, bandages and food (function
 * ez:kit/give). It's checked automatically after a death (the datapack runs /ezkit), and players can ask with /kit in
 * camp. At most one kit every COOLDOWN per player, and it carries no coins, so it can't be farmed for money.
 */
final class Relief {
    private Relief() {}

    static final int BROKE = 20;                       // a pistol costs 20 at the Quartermaster
    static final long COOLDOWN = 10 * 60 * 1000L;
    static final Map<UUID, Long> LAST = new HashMap<>();

    static void init() {
        CommandRegistrationCallback.EVENT.register((d, ctx, env) -> {
            d.register(Commands.literal("ezkit").requires(Commands.hasPermission(Commands.LEVEL_GAMEMASTERS))
                    .executes(c -> { if (c.getSource().getEntity() instanceof ServerPlayer p) check(p, false); return 1; }));
            d.register(Commands.literal("kit").executes(c -> {
                ServerPlayer p = c.getSource().getPlayerOrException();
                if (!p.level().dimension().equals(Plots.CAMP)) p.sendSystemMessage(t("Ask for a relief kit back in camp.", ChatFormatting.RED));
                else check(p, true);
                return 1;
            }));
        });
    }

    static boolean isGun(ItemStack s) { return s.is(Items.CLAY_BALL) && s.has(DataComponents.ITEM_MODEL); }

    /** {guns, credits} in a container. */
    static void scan(Container c, int[] acc) {
        for (int i = 0; i < c.getContainerSize(); i++) {
            ItemStack s = c.getItem(i);
            if (s.isEmpty()) continue;
            if (isGun(s)) acc[0]++;
            else acc[1] += Coins.value(s);
        }
    }

    static void check(ServerPlayer p, boolean asked) {
        MinecraftServer server = p.level().getServer();
        Shops.load(server);
        int[] acc = {0, 0};
        scan(p.getInventory(), acc);
        String where = "on you";
        Plots.Plot plot = Plots.of(p);
        ServerLevel camp = server.getLevel(Plots.CAMP);
        if (acc[0] == 0 && acc[1] < BROKE && plot != null && camp != null) {
            int x = Plots.cx(plot.index), z = Plots.cz(plot.index), h = Plots.half(plot);
            for (int cx = (x - h) >> 4; cx <= (x + h) >> 4; cx++)
                for (int cz = (z - h) >> 4; cz <= (z + h) >> 4; cz++) {
                    LevelChunk ch = camp.getChunk(cx, cz);
                    for (BlockEntity be : ch.getBlockEntities().values())
                        if (be instanceof Container c && Plots.inside(plot, be.getBlockPos())) scan(c, acc);
                }
            where = "in your stash";
        }
        if (acc[0] > 0 || acc[1] >= BROKE) {
            if (asked) p.sendSystemMessage(t("You still have " + (acc[0] > 0 ? "a gun" : Coins.fmt(acc[1])) + " " + where
                    + ". Relief kits are for players who've lost everything.", ChatFormatting.YELLOW));
            return;
        }
        long now = System.currentTimeMillis(), last = LAST.getOrDefault(p.getUUID(), 0L);
        if (now - last < COOLDOWN) {
            if (asked) p.sendSystemMessage(t("Your next relief kit is ready in " + Math.max(1, (COOLDOWN - (now - last) + 59_999) / 60_000) + " min.", ChatFormatting.YELLOW));
            return;
        }
        LAST.put(p.getUUID(), now);
        Plots.run(server, "execute as " + p.getGameProfile().name() + " run function ez:kit/give");
    }
}

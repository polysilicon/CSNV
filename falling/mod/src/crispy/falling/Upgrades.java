package crispy.falling;

import net.minecraft.ChatFormatting;
import net.minecraft.core.BlockPos;
import net.minecraft.nbt.CompoundTag;
import net.minecraft.nbt.ListTag;
import net.minecraft.network.chat.Component;
import net.minecraft.server.MinecraftServer;
import net.minecraft.server.level.ServerLevel;
import net.minecraft.server.level.ServerPlayer;
import net.minecraft.server.permissions.LevelBasedPermissionSet;
import net.minecraft.sounds.SoundEvents;
import net.minecraft.world.item.Item;
import net.minecraft.world.item.Items;
import net.minecraft.world.level.Level;
import net.minecraft.world.level.block.Blocks;
import net.minecraft.world.level.block.state.BlockState;
import net.minecraft.world.scores.Objective;

import java.util.ArrayList;
import java.util.List;

import static crispy.falling.Ui.t;

/**
 * Island upgrades, bought with coins by any member from /island upgrades (Island Menu > Island upgrades). Tiers live
 * on the island's record in storage crispy_skyblock:d plots[id]: us (size), um (minion slots), uc (co-op slots),
 * ug (ore generator).
 * - Size: 128 > 160 > 192 > 256 blocks square, around the island's centre. Moves the plot's x/z/x1/z1 corners (the
 *   island level scan and chunk loading follow them) and sd (size - 1, which the datapack's bounds checks use), and
 *   fills the new ground with the island's biome.
 * - Minion slots: +2 per tier (Minions.limit). Co-op: 4 > 6 > 8 members (checked when inviting).
 * - Ore generator: cobblestone made by lava meeting water on the island sometimes comes out as ore (LiquidBlockMixin).
 */
public final class Upgrades {
    private Upgrades() {}

    static final int[] SIZES = {128, 160, 192, 256};
    static final long[] SIZE_COST = {0, 25_000, 75_000, 200_000};
    static final long[] MINION_COST = {0, 10_000, 30_000, 90_000};
    static final int[] COOP_CAP = {4, 6, 8};
    static final long[] COOP_COST = {0, 15_000, 50_000};
    static final long[] GEN_COST = {0, 5_000, 25_000, 75_000};
    // ore generator: per tier, ore -> % chance (cumulative odds are checked in order)
    static final Object[][][] GEN = {
            {},
            {{Blocks.COAL_ORE, 8}, {Blocks.IRON_ORE, 4}, {Blocks.COPPER_ORE, 4}},
            {{Blocks.COAL_ORE, 8}, {Blocks.IRON_ORE, 5}, {Blocks.COPPER_ORE, 4}, {Blocks.GOLD_ORE, 3}, {Blocks.LAPIS_ORE, 3}, {Blocks.REDSTONE_ORE, 3}},
            {{Blocks.COAL_ORE, 8}, {Blocks.IRON_ORE, 6}, {Blocks.COPPER_ORE, 4}, {Blocks.GOLD_ORE, 4}, {Blocks.LAPIS_ORE, 3}, {Blocks.REDSTONE_ORE, 3},
             {Blocks.DIAMOND_ORE, 1}, {Blocks.EMERALD_ORE, 1}}};

    static CompoundTag rec(MinecraftServer server, int id) {
        ListTag plots = server.getCommandStorage().get(IslandLevels.DATA).getListOrEmpty("plots");
        return id > 0 && id < plots.size() ? plots.getCompoundOrEmpty(id) : new CompoundTag();
    }
    static int tier(MinecraftServer server, int id, String key) { return rec(server, id).getIntOr(key, 0); }
    static void run(MinecraftServer server, String cmd) {
        server.getCommands().performPrefixedCommand(server.createCommandSourceStack().withSuppressedOutput().withPermission(LevelBasedPermissionSet.GAMEMASTER), cmd);
    }
    static void setField(MinecraftServer server, int id, String key, int v) { run(server, "data modify storage crispy_skyblock:d plots[" + id + "]." + key + " set value " + v); }

    /** Members of the island: everyone (online or not) whose cs_plot is this island. */
    static int members(MinecraftServer server, int id) {
        Objective o = server.getScoreboard().getObjective("cs_plot");
        if (o == null) return 0;
        int n = 0;
        for (var e : server.getScoreboard().listPlayerScores(o)) if (!e.owner().startsWith("#") && e.value() == id) n++;
        return n;
    }
    static int coopCap(MinecraftServer server, int id) { return COOP_CAP[Math.min(COOP_CAP.length - 1, tier(server, id, "uc"))]; }

    static void applySize(MinecraftServer server, int id, int size) {
        CompoundTag r = rec(server, id);
        int cx = r.getIntOr("cx", 0), cz = r.getIntOr("cz", 0), x = cx - size / 2, z = cz - size / 2;
        setField(server, id, "x", x); setField(server, id, "z", z);
        setField(server, id, "x1", x + size - 1); setField(server, id, "z1", z + size - 1); setField(server, id, "sd", size - 1);
        run(server, "execute in minecraft:overworld run forceload add " + x + " " + z + " " + (x + size - 1) + " " + (z + size - 1));
        run(server, "function crispy_skyblock:island/biome with storage crispy_skyblock:d plots[" + id + "]");
    }

    // ------------------------------------------------------------------ the menu
    static int open(net.minecraft.commands.CommandSourceStack src) throws com.mojang.brigadier.exceptions.CommandSyntaxException {
        ServerPlayer p = src.getPlayerOrException();
        if (SkyblockMod.plot(src.getServer(), p) <= 0) { src.sendFailure(Component.literal("You need an island first.")); return 0; }
        open(p);
        return 1;
    }

    static void open(ServerPlayer p) {
        MinecraftServer server = p.level().getServer();
        Ui.open(p, t("Island upgrades", ChatFormatting.DARK_GRAY), 3, m -> {
            int id = SkyblockMod.plot(server, p);
            int us = tier(server, id, "us"), um = tier(server, id, "um"), uc = tier(server, id, "uc"), ug = tier(server, id, "ug");
            m.put(10, card(Items.GRASS_BLOCK, "Island size", us, SIZE_COST, "Your island grows to " + (us + 1 < SIZES.length ? SIZES[us + 1] + "x" + SIZES[us + 1] : "the max"),
                    "Now: " + SIZES[us] + "x" + SIZES[us] + " blocks"), (pl, c) -> buy(pl, "us", SIZE_COST, us, () -> applySize(server, id, SIZES[us + 1]), "Island size: " + (us + 1 < SIZES.length ? SIZES[us + 1] : 0) + " blocks"));
            m.put(12, card(Items.ARMOR_STAND, "Minion slots", um, MINION_COST, "+2 minion slots",
                    "Now: +" + 2 * um + " slots (" + Minions.limit(server, id) + " in total)"), (pl, c) -> buy(pl, "um", MINION_COST, um, () -> {}, "Minion slots: +" + 2 * (um + 1)));
            m.put(14, card(Items.PLAYER_HEAD, "Co-op slots", uc, COOP_COST, "Up to " + (uc + 1 < COOP_CAP.length ? COOP_CAP[uc + 1] : COOP_CAP[uc]) + " members",
                    "Now: " + members(server, id) + "/" + COOP_CAP[uc] + " members"), (pl, c) -> buy(pl, "uc", COOP_COST, uc, () -> {}, "Co-op: " + COOP_CAP[Math.min(COOP_CAP.length - 1, uc + 1)] + " members"));
            m.put(16, card(Items.COBBLESTONE, "Ore generator", ug, GEN_COST, genLine(ug + 1),
                    "Now: " + (ug == 0 ? "plain cobblestone" : genLine(ug))), (pl, c) -> buy(pl, "ug", GEN_COST, ug, () -> {}, "Ore generator tier " + (ug + 1)));
            m.put(22, Ui.item(Items.GOLD_NUGGET, t("Purse: " + Economy.fmt(Economy.coins(server, p)) + " coins", ChatFormatting.GOLD),
                    List.of(t("Any island member can buy upgrades", ChatFormatting.DARK_GRAY)), false), null);
        });
    }

    static String genLine(int tier) {
        if (tier <= 0 || tier >= GEN.length) return tier <= 0 ? "plain cobblestone" : "maxed";
        List<String> parts = new ArrayList<>();
        for (Object[] e : GEN[tier]) parts.add(((net.minecraft.world.level.block.Block) e[0]).getName().getString().replace(" Ore", "") + " " + e[1] + "%");
        return "Cobble gens make ore: " + String.join(", ", parts);
    }

    static net.minecraft.world.item.ItemStack card(Item icon, String name, int tier, long[] cost, String next, String now) {
        boolean max = tier + 1 >= cost.length;
        List<Component> lore = new ArrayList<>();
        lore.add(t(now, ChatFormatting.GRAY));
        lore.add(Component.empty());
        if (max) lore.add(t("Fully upgraded!", ChatFormatting.GREEN));
        else {
            lore.add(t("Next (tier " + (tier + 1) + "/" + (cost.length - 1) + "): ", ChatFormatting.YELLOW).append(t(next, ChatFormatting.WHITE)));
            lore.add(t("Cost: " + Economy.fmt(cost[tier + 1]) + " coins", ChatFormatting.GOLD));
            lore.add(Component.empty()); lore.add(t("Click to upgrade", ChatFormatting.YELLOW));
        }
        return Ui.item(icon, t(name + " " + tier + "/" + (cost.length - 1), ChatFormatting.GREEN, ChatFormatting.BOLD), lore, max);
    }

    static void buy(ServerPlayer p, String key, long[] cost, int tier, Runnable apply, String what) {
        MinecraftServer server = p.level().getServer();
        int id = SkyblockMod.plot(server, p);
        if (tier + 1 >= cost.length) { p.sendSystemMessage(t("That's fully upgraded.", ChatFormatting.GOLD)); return; }
        if (!Economy.add(server, p, -cost[tier + 1])) { p.sendSystemMessage(t("You need " + Economy.fmt(cost[tier + 1]) + " coins.", ChatFormatting.RED)); return; }
        setField(server, id, key, tier + 1);
        apply.run();
        run(server, "tellraw @a[scores={cs_plot=" + id + "}] [{\"text\":\"⬆ \",\"color\":\"green\"},{\"selector\":\"" + p.getScoreboardName()
                + "\",\"color\":\"yellow\"},{\"text\":\" upgraded the island: " + what + "\",\"color\":\"green\"}]");
        p.playSound(SoundEvents.PLAYER_LEVELUP, 0.8f, 1.4f);
    }

    // ------------------------------------------------------------------ ore generator (LiquidBlockMixin)
    /** What lava meeting water at pos becomes: on an island with an ore generator, cobblestone is sometimes an ore. */
    public static BlockState generated(Level level, BlockPos pos, BlockState state) {
        if (!(level instanceof ServerLevel sl) || !state.is(Blocks.COBBLESTONE) || level.dimension() != Level.OVERWORLD) return state;
        int id = Realms.plotAt(pos.getX(), pos.getZ());
        if (id <= 0) return state;
        int tier = tier(sl.getServer(), id, "ug");
        if (tier <= 0) return state;
        int roll = level.getRandom().nextInt(100), acc = 0;
        for (Object[] e : GEN[Math.min(tier, GEN.length - 1)]) {
            acc += (Integer) e[1];
            if (roll < acc) return ((net.minecraft.world.level.block.Block) e[0]).defaultBlockState();
        }
        return state;
    }
}

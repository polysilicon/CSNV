package crispy.falling;

import com.mojang.brigadier.CommandDispatcher;
import com.mojang.brigadier.arguments.StringArgumentType;
import net.minecraft.ChatFormatting;
import net.minecraft.commands.CommandSourceStack;
import net.minecraft.commands.Commands;
import net.minecraft.core.BlockPos;
import net.minecraft.core.registries.BuiltInRegistries;
import net.minecraft.nbt.CompoundTag;
import net.minecraft.nbt.ListTag;
import net.minecraft.server.MinecraftServer;
import net.minecraft.server.level.ServerLevel;
import net.minecraft.server.level.ServerPlayer;
import net.minecraft.server.permissions.LevelBasedPermissionSet;
import net.minecraft.world.InteractionHand;
import net.minecraft.world.InteractionResult;
import net.minecraft.world.entity.player.Player;
import net.minecraft.world.item.BlockItem;
import net.minecraft.world.item.BucketItem;
import net.minecraft.world.item.ItemStack;
import net.minecraft.world.item.Items;
import net.minecraft.world.level.Level;
import net.minecraft.world.level.block.Blocks;
import net.minecraft.world.level.block.entity.BlockEntity;
import net.minecraft.world.level.block.state.BlockState;
import net.minecraft.world.phys.BlockHitResult;

import java.util.*;

import static crispy.falling.Ui.t;

/**
 * Resource zones (the Deep Mines, Whispering Woods; built and listed by expansion.py in storage
 * crispy_skyblock:eco cfg.zones): shared areas where only the zone's resource blocks can be mined, nothing can be
 * placed, and a mined block turns to bedrock and grows back after the zone's `secs`. The datapack spawns the mobs.
 * /warp (or the Warps NPC in the hub) gets you there and back.
 */
final class Zones {
    private Zones() {}

    record Zone(String key, String name, int x1, int y1, int z1, int x2, int y2, int z2, Set<String> allow, int secs, double[] warp) {
        boolean contains(BlockPos p) { return p.getX() >= x1 && p.getX() <= x2 && p.getY() >= y1 && p.getY() <= y2 && p.getZ() >= z1 && p.getZ() <= z2; }
    }
    record Pending(BlockState state, long due) {}

    private static List<Zone> zones;
    private static final Map<Long, Pending> pending = new HashMap<>();   // overworld positions waiting to grow back
    private static long tick;

    static List<Zone> zones(MinecraftServer server) {
        if (zones == null || zones.isEmpty()) {
            List<Zone> out = new ArrayList<>();
            ListTag l = Economy.cfg(server).getListOrEmpty("zones");
            for (int i = 0; i < l.size(); i++) {
                CompoundTag z = l.getCompoundOrEmpty(i);
                Set<String> allow = new HashSet<>();
                ListTag a = z.getListOrEmpty("allow");
                for (int j = 0; j < a.size(); j++) allow.add(a.getStringOr(j, ""));
                ListTag w = z.getListOrEmpty("warp");
                double[] warp = new double[w.size()];
                for (int j = 0; j < w.size(); j++) warp[j] = w.getDoubleOr(j, 0);
                out.add(new Zone(z.getStringOr("key", ""), z.getStringOr("name", ""), z.getIntOr("x1", 0), z.getIntOr("y1", 0), z.getIntOr("z1", 0),
                        z.getIntOr("x2", 0), z.getIntOr("y2", 0), z.getIntOr("z2", 0), allow, z.getIntOr("secs", 45), warp));
            }
            zones = out;
        }
        return zones;
    }
    static Zone at(Level level, BlockPos pos) {
        if (!(level instanceof ServerLevel sl) || level.dimension() != Level.OVERWORLD) return null;
        for (Zone z : zones(sl.getServer())) if (z.contains(pos)) return z;
        return null;
    }
    static boolean staff(ServerPlayer p) { return p.isCreative() && Commands.hasPermission(Commands.LEVEL_GAMEMASTERS).test(p.createCommandSourceStack()); }

    // ------------------------------------------------------------------ hooks
    /** PlayerBlockBreakEvents.BEFORE: in a zone, only its resource blocks. */
    static boolean canBreak(Level world, Player player, BlockPos pos, BlockState state, BlockEntity be) {
        if (!(player instanceof ServerPlayer p)) return true;
        Zone z = at(world, pos);
        if (z == null || staff(p)) return true;
        if (!state.is(Blocks.BEDROCK) && z.allow().contains(BuiltInRegistries.BLOCK.getKey(state.getBlock()).toString())) return true;
        p.sendOverlayMessage(t(state.is(Blocks.BEDROCK) ? "That's still growing back." : "You can only gather the resources here.", ChatFormatting.RED));
        return false;
    }

    /** PlayerBlockBreakEvents.AFTER: the mined block becomes bedrock until it grows back. */
    static void onBreak(Level world, Player player, BlockPos pos, BlockState state, BlockEntity be) {
        if (!(player instanceof ServerPlayer p) || staff(p)) return;
        Zone z = at(world, pos);
        if (z == null) return;
        world.setBlock(pos, Blocks.BEDROCK.defaultBlockState(), 3);
        pending.put(pos.asLong(), new Pending(state, tick + z.secs() * 20L));
    }

    /** UseBlockCallback: nothing can be placed (blocks, buckets) in a zone. */
    static InteractionResult onUseBlock(Player player, Level world, InteractionHand hand, BlockHitResult hit) {
        if (!(player instanceof ServerPlayer p) || staff(p)) return InteractionResult.PASS;
        ItemStack held = p.getItemInHand(hand);
        if (!(held.getItem() instanceof BlockItem) && !(held.getItem() instanceof BucketItem)) return InteractionResult.PASS;
        if (at(world, hit.getBlockPos()) == null && at(world, hit.getBlockPos().relative(hit.getDirection())) == null) return InteractionResult.PASS;
        p.sendOverlayMessage(t("You can't build here.", ChatFormatting.RED));
        return InteractionResult.FAIL;
    }

    static void onTick(MinecraftServer server) {
        tick++;
        if (tick % 10 != 0 || pending.isEmpty()) return;
        ServerLevel ow = server.overworld();
        pending.entrySet().removeIf(e -> {
            if (e.getValue().due() > tick) return false;
            BlockPos pos = BlockPos.of(e.getKey());
            if (!ow.isLoaded(pos)) return false;
            if (ow.getBlockState(pos).is(Blocks.BEDROCK)) ow.setBlock(pos, e.getValue().state(), 3);
            return true;
        });
    }

    /** Server stopping: put everything back now, so no bedrock is left behind. */
    static void restoreAll(MinecraftServer server) {
        ServerLevel ow = server.overworld();
        for (var e : pending.entrySet()) {
            BlockPos pos = BlockPos.of(e.getKey());
            if (ow.getBlockState(pos).is(Blocks.BEDROCK)) ow.setBlock(pos, e.getValue().state(), 3);
        }
        pending.clear();
    }

    // ------------------------------------------------------------------ warps
    static void openWarps(ServerPlayer p) {
        MinecraftServer server = p.level().getServer();
        Ui.open(p, t("Warps", ChatFormatting.DARK_GRAY), 3, m -> {
            m.put(10, Ui.item(Items.LODESTONE, t("Hub", ChatFormatting.GOLD, ChatFormatting.BOLD), List.of(t("Merchants, the Bazaar, the portal home", ChatFormatting.GRAY)), false),
                    (pl, c) -> warp(pl, "hub"));
            m.put(12, Ui.item(Items.GRASS_BLOCK, t("Your island", ChatFormatting.GREEN, ChatFormatting.BOLD), List.of(t("Home", ChatFormatting.GRAY)), false),
                    (pl, c) -> warp(pl, "home"));
            m.put(22, Ui.item(Items.OAK_SIGN, t("Market District", ChatFormatting.GOLD, ChatFormatting.BOLD), List.of(t("Plots for shops and houses · /plots", ChatFormatting.GRAY)), false),
                    (pl, c) -> warp(pl, "plots"));
            List<Zone> zs = zones(server);
            int[] slots = {14, 16};
            for (int i = 0; i < zs.size() && i < slots.length; i++) {
                Zone z = zs.get(i);
                boolean mines = z.key().equals("mines");
                m.put(slots[i], Ui.item(mines ? Items.IRON_PICKAXE : Items.IRON_AXE, t(z.name(), mines ? ChatFormatting.GRAY : ChatFormatting.DARK_GREEN, ChatFormatting.BOLD),
                        List.of(t(mines ? "A deep quarry: ores grow back, richer further down" : "A forest whose logs grow back", ChatFormatting.GRAY),
                                t("Hostile mobs roam here", ChatFormatting.RED), t("You can't build here", ChatFormatting.DARK_GRAY)), false),
                        (pl, c) -> warp(pl, z.key()));
            }
        });
    }

    static int warp(ServerPlayer p, String where) {
        MinecraftServer server = p.level().getServer();
        p.closeContainer();
        String cmd = switch (where) {
            case "hub" -> "function crispy_skyblock:act/hub";
            case "home" -> "function crispy_skyblock:act/home";
            case "plots", "district" -> { HubPlots.warp(p); yield ""; }
            default -> {
                Zone z = zones(server).stream().filter(x -> x.key().equals(where)).findFirst().orElse(null);
                if (z == null || z.warp().length < 4) yield null;
                yield "function crispy_skyblock:zones/tp {x:" + z.warp()[0] + ",y:" + z.warp()[1] + ",z:" + z.warp()[2] + ",yaw:" + z.warp()[3] + "}";
            }
        };
        if (cmd != null && cmd.isEmpty()) return 1;
        if (cmd == null) { p.sendSystemMessage(t("No warp called " + where + ". Try hub, home, plots, mines or woods.", ChatFormatting.RED)); return 0; }
        server.getCommands().performPrefixedCommand(p.createCommandSourceStack().withSuppressedOutput().withPermission(LevelBasedPermissionSet.GAMEMASTER), cmd);
        return 1;
    }

    static void register(CommandDispatcher<CommandSourceStack> d) {
        d.register(Commands.literal("warp").executes(c -> { openWarps(c.getSource().getPlayerOrException()); return 1; })
                .then(Commands.argument("where", StringArgumentType.word())
                        .suggests((c, b) -> { for (String s : new String[]{"hub", "home", "plots", "mines", "woods"}) b.suggest(s); return b.buildFuture(); })
                        .executes(c -> warp(c.getSource().getPlayerOrException(), StringArgumentType.getString(c, "where")))));
    }
}

package crispy.falling;

import com.mojang.brigadier.CommandDispatcher;
import com.mojang.brigadier.arguments.StringArgumentType;
import net.minecraft.ChatFormatting;
import net.minecraft.commands.CommandSourceStack;
import net.minecraft.commands.Commands;
import net.minecraft.commands.arguments.EntityArgument;
import net.minecraft.core.BlockPos;
import net.minecraft.nbt.CompoundTag;
import net.minecraft.nbt.ListTag;
import net.minecraft.nbt.StringTag;
import net.minecraft.network.chat.Component;
import net.minecraft.resources.Identifier;
import net.minecraft.server.MinecraftServer;
import net.minecraft.server.level.ServerPlayer;
import net.minecraft.server.permissions.LevelBasedPermissionSet;
import net.minecraft.sounds.SoundEvents;
import net.minecraft.world.InteractionHand;
import net.minecraft.world.InteractionResult;
import net.minecraft.world.entity.Entity;
import net.minecraft.world.entity.decoration.ArmorStand;
import net.minecraft.world.entity.decoration.ItemFrame;
import net.minecraft.world.entity.player.Player;
import net.minecraft.world.item.BlockItem;
import net.minecraft.world.item.BucketItem;
import net.minecraft.world.item.ItemStack;
import net.minecraft.world.item.Items;
import net.minecraft.world.level.Level;
import net.minecraft.world.level.block.Blocks;
import net.minecraft.world.level.block.SignBlock;
import net.minecraft.world.level.block.entity.BaseContainerBlockEntity;
import net.minecraft.world.level.block.entity.BlockEntity;
import net.minecraft.world.level.block.state.BlockState;
import net.minecraft.world.phys.BlockHitResult;
import net.minecraft.world.phys.EntityHitResult;
import net.minecraft.world.scores.Objective;
import net.minecraft.world.scores.ReadOnlyScoreInfo;
import net.minecraft.world.scores.ScoreHolder;

import java.util.*;

import static crispy.falling.Ui.t;

/**
 * Market District plots (laid out by district.py, listed in storage crispy_skyblock:eco cfg.hubplots): players buy one
 * from the Realtor, a plot's sign or /plots, for shops and houses. Ownership lives in storage crispy_skyblock:hubplots
 * as p<n>: {owner (UUID), name, trust: [UUIDs], tnames: [names]}.
 * - The owner, players they trust and the owner's island co-op can build in the plot (16x16, 4 below the floor to 32
 *   above). Standing in it they're tagged cs_hpbuild and the datapack puts them in survival; elsewhere it's adventure.
 * - Nothing outside the plots can be broken or placed; chests, item frames and armor stands in a plot are the
 *   builders' own. TNT, fire and lava can't be used in the district.
 * - Abandoning a plot refunds cfg.hubplot_refund % and clears it back to grass (district/reset).
 */
final class HubPlots {
    private HubPlots() {}

    static final Identifier STORE = Identifier.fromNamespaceAndPath(SkyblockMod.NS, "hubplots");
    record Plot(int n, int x1, int z1, int x2, int z2, int y1, int y2, int sx, int sy, int sz) {
        boolean contains(BlockPos p) { return p.getX() >= x1 && p.getX() <= x2 && p.getZ() >= z1 && p.getZ() <= z2 && p.getY() >= y1 && p.getY() <= y2; }
        boolean isSign(BlockPos p) { return p.getX() == sx && p.getY() == sy && p.getZ() == sz; }
    }
    private static List<Plot> plots;
    private static int[] box;
    private static long tick;
    private static final Map<UUID, String> confirm = new HashMap<>();   // a click waiting for its second, confirming click

    static List<Plot> plots(MinecraftServer server) {
        if (plots == null || plots.isEmpty()) {
            List<Plot> out = new ArrayList<>();
            ListTag l = Economy.cfg(server).getListOrEmpty("hubplots");
            for (int i = 0; i < l.size(); i++) {
                CompoundTag c = l.getCompoundOrEmpty(i);
                out.add(new Plot(c.getIntOr("n", 0), c.getIntOr("x1", 0), c.getIntOr("z1", 0), c.getIntOr("x2", 0), c.getIntOr("z2", 0),
                        c.getIntOr("y1", 0), c.getIntOr("y2", 0), c.getIntOr("sx", 0), c.getIntOr("sy", 0), c.getIntOr("sz", 0)));
            }
            plots = out;
            ListTag b = Economy.cfg(server).getListOrEmpty("district");
            box = new int[6];
            for (int i = 0; i < 6 && i < b.size(); i++) box[i] = b.getIntOr(i, 0);
        }
        return plots;
    }
    static Plot plot(MinecraftServer server, int n) { for (Plot p : plots(server)) if (p.n() == n) return p; return null; }
    static Plot at(MinecraftServer server, BlockPos pos) { for (Plot p : plots(server)) if (p.contains(pos)) return p; return null; }
    static boolean inDistrict(Level level, BlockPos pos) {
        if (level.dimension() != Level.OVERWORLD || level.getServer() == null) return false;
        plots(level.getServer());
        return pos.getX() >= box[0] && pos.getX() <= box[3] && pos.getY() >= box[1] - 60 && pos.getY() <= box[4] && pos.getZ() >= box[2] && pos.getZ() <= box[5];
    }
    static long price(MinecraftServer server) { return Economy.cfg(server).getLongOr("hubplot_price", 20_000); }
    static int refund(MinecraftServer server) { return Economy.cfg(server).getIntOr("hubplot_refund", 50); }

    // ------------------------------------------------------------------ ownership
    static CompoundTag all(MinecraftServer server) { return server.getCommandStorage().get(STORE); }
    static CompoundTag rec(MinecraftServer server, int n) { return all(server).getCompoundOrEmpty("p" + n); }
    static void save(MinecraftServer server, int n, CompoundTag r) {
        CompoundTag a = all(server);
        if (r == null) a.remove("p" + n); else a.put("p" + n, r);
        server.getCommandStorage().set(STORE, a);
    }
    static boolean owned(MinecraftServer server, int n) { return !rec(server, n).getStringOr("owner", "").isEmpty(); }
    static int ownedBy(MinecraftServer server, UUID id) {
        for (Plot p : plots(server)) if (rec(server, p.n()).getStringOr("owner", "").equals(id.toString())) return p.n();
        return 0;
    }
    static List<String> list(CompoundTag r, String key) {
        List<String> out = new ArrayList<>();
        ListTag l = r.getListOrEmpty(key);
        for (int i = 0; i < l.size(); i++) out.add(l.getStringOr(i, ""));
        return out;
    }
    static int islandOf(MinecraftServer server, String name) {
        Objective o = server.getScoreboard().getObjective("cs_plot");
        if (o == null || name.isEmpty()) return 0;
        ReadOnlyScoreInfo s = server.getScoreboard().getPlayerScoreInfo(ScoreHolder.forNameOnly(name), o);
        return s == null ? 0 : s.value();
    }
    static boolean canBuild(ServerPlayer p, Plot plot) {
        MinecraftServer server = p.level().getServer();
        CompoundTag r = rec(server, plot.n());
        String owner = r.getStringOr("owner", "");
        if (owner.isEmpty()) return false;
        String me = p.getStringUUID();
        if (owner.equals(me) || list(r, "trust").contains(me)) return true;
        int isl = islandOf(server, r.getStringOr("name", ""));
        return isl > 0 && isl == SkyblockMod.plot(server, p);
    }
    static boolean staff(ServerPlayer p) { return p.isCreative() && Commands.hasPermission(Commands.LEVEL_GAMEMASTERS).test(p.createCommandSourceStack()); }

    // ------------------------------------------------------------------ ticking: build tag and labels
    static void onTick(MinecraftServer server) {
        tick++;
        if (tick % 5 == 0)
            for (ServerPlayer p : server.getPlayerList().getPlayers()) {
                Plot pl = p.level() == server.overworld() ? at(server, p.blockPosition()) : null;
                boolean build = pl != null && !p.isSpectator() && canBuild(p, pl);
                if (build) p.addTag("cs_hpbuild"); else p.removeTag("cs_hpbuild");
            }
        if (tick % 600 == 100) for (Plot pl : plots(server)) label(server, pl);
    }

    static void label(MinecraftServer server, Plot pl) {
        CompoundTag r = rec(server, pl.n());
        String name = r.getStringOr("name", "");
        String line = name.isEmpty() ? "\\nFor sale · " + Economy.fmt(price(server)) + " coins" : "\\nOwned by " + name;
        String col = name.isEmpty() ? "green" : "gold";
        Upgrades.run(server, "data modify entity @e[type=minecraft:text_display,tag=cs_hpl_" + pl.n() + ",limit=1] text set value {text:\"Plot " + pl.n()
                + "\",color:\"" + col + "\",bold:1b,extra:[{text:\"" + line + "\",color:\"gray\",bold:0b}]}");
    }

    // ------------------------------------------------------------------ protection hooks
    static boolean canBreak(Level world, Player player, BlockPos pos, BlockState state, BlockEntity be) {
        if (!(player instanceof ServerPlayer p) || !inDistrict(world, pos) || staff(p)) return true;
        Plot pl = at(world.getServer(), pos);
        if (pl != null && canBuild(p, pl)) return true;
        p.sendOverlayMessage(t(pl == null ? "You can only build in your plot." : "That's someone else's plot.", ChatFormatting.RED));
        return false;
    }

    static boolean banned(ItemStack s) {
        return s.is(Items.TNT) || s.is(Items.TNT_MINECART) || s.is(Items.FLINT_AND_STEEL) || s.is(Items.FIRE_CHARGE) || s.is(Items.LAVA_BUCKET)
                || s.is(Items.END_CRYSTAL) || s.is(Items.RESPAWN_ANCHOR);
    }

    static InteractionResult onUseBlock(Player player, Level world, InteractionHand hand, BlockHitResult hit) {
        if (!(player instanceof ServerPlayer p) || !inDistrict(world, hit.getBlockPos())) return InteractionResult.PASS;
        MinecraftServer server = world.getServer();
        BlockPos pos = hit.getBlockPos();
        BlockState state = world.getBlockState(pos);
        if (state.getBlock() instanceof SignBlock)
            for (Plot pl : plots(server)) if (pl.isSign(pos)) { if (hand == InteractionHand.MAIN_HAND) open(p); return InteractionResult.SUCCESS; }
        if (staff(p)) return InteractionResult.PASS;
        ItemStack held = p.getItemInHand(hand);
        if (banned(held)) { p.sendOverlayMessage(t("That's not allowed in the Market District.", ChatFormatting.RED)); return InteractionResult.FAIL; }
        Plot pl = at(server, pos);
        boolean mine = pl != null && canBuild(p, pl);
        if (held.getItem() instanceof BlockItem || held.getItem() instanceof BucketItem) {
            Plot target = at(server, state.canBeReplaced() ? pos : pos.relative(hit.getDirection()));
            if (target == null || !canBuild(p, target)) {
                p.sendOverlayMessage(t("You can only build in your plot.", ChatFormatting.RED));
                return InteractionResult.FAIL;
            }
        }
        if (pl != null && !mine && world.getBlockEntity(pos) instanceof BaseContainerBlockEntity) {
            p.sendOverlayMessage(t("That belongs to the plot's owner.", ChatFormatting.RED));
            return InteractionResult.FAIL;
        }
        return InteractionResult.PASS;
    }

    static boolean protectedEntity(Entity e) { return e instanceof ItemFrame || e instanceof ArmorStand; }
    static InteractionResult onEntity(Player player, Level world, Entity entity) {
        if (!(player instanceof ServerPlayer p) || !protectedEntity(entity) || !inDistrict(world, entity.blockPosition()) || staff(p)) return InteractionResult.PASS;
        Plot pl = at(world.getServer(), entity.blockPosition());
        if (pl != null && canBuild(p, pl)) return InteractionResult.PASS;
        return InteractionResult.FAIL;
    }

    // ------------------------------------------------------------------ the menu
    static final int[] SLOT_COL = {1, 2, 6, 7};

    static void open(ServerPlayer p) {
        MinecraftServer server = p.level().getServer();
        Ui.open(p, t("Market District plots", ChatFormatting.DARK_GRAY), 6, m -> {
            int mine = ownedBy(server, p.getUUID());
            String pend = confirm.getOrDefault(p.getUUID(), "");
            for (Plot pl : plots(server)) {
                int idx = pl.n() - 1, slot = (idx / 4 + 1) * 9 + SLOT_COL[idx % 4];
                CompoundTag r = rec(server, pl.n());
                String owner = r.getStringOr("name", "");
                List<Component> lore = new ArrayList<>();
                ItemStack icon;
                if (owner.isEmpty()) {
                    lore.add(t("For sale: " + Economy.fmt(price(server)) + " coins", ChatFormatting.GOLD));
                    lore.add(t("16x16, build 32 blocks up and 4 down", ChatFormatting.GRAY));
                    lore.add(Component.empty());
                    if (mine > 0) lore.add(t("You already own plot " + mine, ChatFormatting.RED));
                    else lore.add(t(pend.equals("buy" + pl.n()) ? "Click again to buy it" : "Click to buy", ChatFormatting.YELLOW));
                    lore.add(t("Right-click to go and look", ChatFormatting.DARK_GRAY));
                    icon = Ui.item(Items.GRASS_BLOCK, t("Plot " + pl.n(), ChatFormatting.GREEN, ChatFormatting.BOLD), lore, pend.equals("buy" + pl.n()));
                } else {
                    boolean yours = pl.n() == mine;
                    lore.add(t("Owned by " + owner, ChatFormatting.GRAY));
                    List<String> tn = list(r, "tnames");
                    if (!tn.isEmpty()) lore.add(t("Trusted: " + String.join(", ", tn), ChatFormatting.DARK_GRAY));
                    lore.add(Component.empty());
                    lore.add(t("Click to visit", ChatFormatting.YELLOW));
                    icon = Ui.item(yours ? Items.GOLD_BLOCK : Items.BRICKS, t("Plot " + pl.n() + (yours ? " (yours)" : ""), yours ? ChatFormatting.GOLD : ChatFormatting.RED, ChatFormatting.BOLD), lore, yours);
                }
                m.put(slot, icon, (pl2, c) -> click(pl2, pl, c));
            }
            m.put(4, Ui.item(Items.OAK_SIGN, t("Market District", ChatFormatting.GOLD, ChatFormatting.BOLD), List.of(
                    t("Buy a plot for your shop or house.", ChatFormatting.GRAY),
                    t("You, players you trust and your island", ChatFormatting.GRAY), t("co-op can build there.", ChatFormatting.GRAY),
                    t("One plot each.", ChatFormatting.DARK_GRAY)), false), null);
            m.put(49, Ui.item(Items.GOLD_NUGGET, t("Purse: " + Economy.fmt(Economy.coins(server, p)) + " coins", ChatFormatting.GOLD), List.of(), false), null);
            m.put(45, Ui.item(Items.LODESTONE, t("Go to the district", ChatFormatting.AQUA), List.of(), false), (pl2, c) -> warp(pl2));
            if (mine > 0) {
                m.put(47, Ui.item(Items.PLAYER_HEAD, t("Trusted players", ChatFormatting.AQUA), List.of(
                        t("/plots trust <player>", ChatFormatting.GRAY), t("/plots untrust <player>", ChatFormatting.GRAY),
                        t("Your island co-op can always build", ChatFormatting.DARK_GRAY)), false), null);
                long back = price(server) * refund(server) / 100;
                boolean armed = pend.equals("abandon");
                m.put(51, Ui.item(Items.BARRIER, t(armed ? "Click again to abandon plot " + mine : "Abandon plot " + mine, ChatFormatting.RED, ChatFormatting.BOLD), List.of(
                        t("Clears everything built on it", ChatFormatting.RED), t("Refund: " + Economy.fmt(back) + " coins", ChatFormatting.GOLD)), armed),
                        (pl2, c) -> abandon(pl2));
                m.put(53, Ui.item(Items.COMPASS, t("Go to your plot", ChatFormatting.GREEN), List.of(), false), (pl2, c) -> visit(pl2, plot(server, mine)));
            }
        });
    }

    static void click(ServerPlayer p, Plot pl, Ui.Click c) {
        MinecraftServer server = p.level().getServer();
        if (owned(server, pl.n()) || c.right()) { visit(p, pl); return; }
        if (ownedBy(server, p.getUUID()) > 0) { p.sendSystemMessage(t("You already own a plot. Abandon it first to buy another.", ChatFormatting.RED)); return; }
        if (!confirm.getOrDefault(p.getUUID(), "").equals("buy" + pl.n())) { confirm.put(p.getUUID(), "buy" + pl.n()); return; }
        confirm.remove(p.getUUID());
        if (!Economy.add(server, p, -price(server))) { p.sendSystemMessage(t("You need " + Economy.fmt(price(server)) + " coins.", ChatFormatting.RED)); return; }
        CompoundTag r = new CompoundTag();
        r.putString("owner", p.getStringUUID());
        r.putString("name", p.getScoreboardName());
        save(server, pl.n(), r);
        label(server, pl);
        p.playSound(SoundEvents.PLAYER_LEVELUP, 0.8f, 1.2f);
        Upgrades.run(server, "tellraw @a [{\"text\":\"🏠 \",\"color\":\"gold\"},{\"selector\":\"" + p.getScoreboardName()
                + "\",\"color\":\"yellow\"},{\"text\":\" bought plot " + pl.n() + " in the Market District!\",\"color\":\"gold\"}]");
        p.closeContainer();
        visit(p, pl);
    }

    static void abandon(ServerPlayer p) {
        MinecraftServer server = p.level().getServer();
        int n = ownedBy(server, p.getUUID());
        if (n == 0) return;
        if (!confirm.getOrDefault(p.getUUID(), "").equals("abandon")) { confirm.put(p.getUUID(), "abandon"); return; }
        confirm.remove(p.getUUID());
        Plot pl = plot(server, n);
        long back = price(server) * refund(server) / 100;
        save(server, n, null);
        Upgrades.run(server, "function " + SkyblockMod.NS + ":district/reset {x1:" + pl.x1() + ",z1:" + pl.z1() + ",x2:" + pl.x2() + ",z2:" + pl.z2() + "}");
        Economy.add(server, p, back);
        label(server, pl);
        p.sendSystemMessage(t("You gave up plot " + n + " and got " + Economy.fmt(back) + " coins back.", ChatFormatting.YELLOW));
        p.closeContainer();
    }

    static void visit(ServerPlayer p, Plot pl) {
        if (pl == null) return;
        p.closeContainer();
        p.level().getServer().getCommands().performPrefixedCommand(p.createCommandSourceStack().withSuppressedOutput().withPermission(LevelBasedPermissionSet.GAMEMASTER),
                "function " + SkyblockMod.NS + ":district/tp {x:" + (pl.sx() + 0.5) + ",y:" + pl.sy() + ",z:" + (pl.sz() - 1.5) + ",yaw:0}");
    }
    static int warp(ServerPlayer p) {
        ListTag w = Economy.cfg(p.level().getServer()).getListOrEmpty("district_warp");
        p.closeContainer();
        p.level().getServer().getCommands().performPrefixedCommand(p.createCommandSourceStack().withSuppressedOutput().withPermission(LevelBasedPermissionSet.GAMEMASTER),
                "function " + SkyblockMod.NS + ":district/tp {x:" + w.getDoubleOr(0, 0.5) + ",y:" + w.getDoubleOr(1, 101) + ",z:" + w.getDoubleOr(2, 55.5) + ",yaw:" + w.getDoubleOr(3, 0) + "}");
        return 1;
    }

    // ------------------------------------------------------------------ commands
    static int trust(CommandSourceStack src, ServerPlayer who, boolean add) throws com.mojang.brigadier.exceptions.CommandSyntaxException {
        ServerPlayer p = src.getPlayerOrException();
        MinecraftServer server = src.getServer();
        int n = ownedBy(server, p.getUUID());
        if (n == 0) { src.sendFailure(Component.literal("You don't own a plot. /plots to buy one.")); return 0; }
        CompoundTag r = rec(server, n);
        List<String> ids = list(r, "trust"), names = list(r, "tnames");
        int i = ids.indexOf(who.getStringUUID());
        if (add && i < 0) { ids.add(who.getStringUUID()); names.add(who.getScoreboardName()); }
        if (!add && i >= 0) { ids.remove(i); names.remove(i); }
        ListTag a = new ListTag(), b = new ListTag();
        for (String s : ids) a.add(StringTag.valueOf(s));
        for (String s : names) b.add(StringTag.valueOf(s));
        r.put("trust", a); r.put("tnames", b);
        save(server, n, r);
        p.sendSystemMessage(t(add ? who.getScoreboardName() + " can now build on plot " + n + "." : who.getScoreboardName() + " can no longer build on plot " + n + ".", ChatFormatting.GREEN));
        return 1;
    }

    static void register(CommandDispatcher<CommandSourceStack> d) {
        d.register(Commands.literal("plots").executes(c -> { open(c.getSource().getPlayerOrException()); return 1; })
                .then(Commands.literal("trust").then(Commands.argument("player", EntityArgument.player())
                        .executes(c -> trust(c.getSource(), EntityArgument.getPlayer(c, "player"), true))))
                .then(Commands.literal("untrust").then(Commands.argument("player", EntityArgument.player())
                        .executes(c -> trust(c.getSource(), EntityArgument.getPlayer(c, "player"), false))))
                .then(Commands.literal("home").executes(c -> {
                    ServerPlayer p = c.getSource().getPlayerOrException();
                    int n = ownedBy(c.getSource().getServer(), p.getUUID());
                    if (n == 0) { c.getSource().sendFailure(Component.literal("You don't own a plot. /plots to buy one.")); return 0; }
                    visit(p, plot(c.getSource().getServer(), n));
                    return 1;
                }))
                .then(Commands.literal("evict").requires(Commands.hasPermission(Commands.LEVEL_GAMEMASTERS))
                        .then(Commands.argument("plot", com.mojang.brigadier.arguments.IntegerArgumentType.integer(1, 64)).executes(c -> {
                            MinecraftServer server = c.getSource().getServer();
                            int n = com.mojang.brigadier.arguments.IntegerArgumentType.getInteger(c, "plot");
                            Plot pl = plot(server, n);
                            if (pl == null) { c.getSource().sendFailure(Component.literal("No plot " + n)); return 0; }
                            save(server, n, null);
                            label(server, pl);
                            c.getSource().sendSuccess(() -> Component.literal("Plot " + n + " is for sale again (its builds are left as they are)."), true);
                            return 1;
                        }))));
    }
}

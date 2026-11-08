package crispy.falling;

import com.mojang.brigadier.CommandDispatcher;
import net.minecraft.ChatFormatting;
import net.minecraft.commands.CommandSourceStack;
import net.minecraft.commands.Commands;
import net.minecraft.commands.arguments.EntityArgument;
import net.minecraft.core.BlockPos;
import net.minecraft.server.MinecraftServer;
import net.minecraft.server.level.ServerPlayer;
import net.minecraft.server.permissions.LevelBasedPermissionSet;
import net.minecraft.world.InteractionHand;
import net.minecraft.world.InteractionResult;
import net.minecraft.world.entity.Entity;
import net.minecraft.world.entity.player.Player;
import net.minecraft.world.item.BucketItem;
import net.minecraft.world.level.Level;
import net.minecraft.world.level.block.entity.BlockEntity;
import net.minecraft.world.level.block.state.BlockState;
import net.minecraft.world.phys.BlockHitResult;
import net.minecraft.world.phys.Vec3;

import java.util.*;

import static crispy.falling.Ui.t;

/**
 * Player travel and island visits.
 * - /tpa <player> (go to them), /tpahere <player> (bring them to you), /tpaccept [player], /tpdeny [player].
 * - /visit <player>: ask to visit their island; they (or anyone online from that island) click [Allow] or [Deny].
 *   An allowed visitor lands on the island's spawn spot (the same one /island home uses).
 * Requests last 60 s; one request every 10 s per player. Accepted teleports wait 3 s and are cancelled if the
 * traveller moves, so nobody can use them to dodge a fight.
 * Island protection: on an overworld island, only its members (cs_plot) and staff in creative can break, place, use
 * blocks, buckets or entities there. Visitors (and anyone who got there by /tpa) can look but not touch.
 * A traveller gets a visitor's pass for the island they arrive on (cs_vis, see pass()), so the island-bounds check
 * doesn't send them straight back home.
 */
final class Visits {
    private Visits() {}

    enum Kind { TPA, TPAHERE, VISIT }
    /** from asked to: TPA from goes to `to`; TPAHERE `to` goes to from; VISIT from goes to island `island`. */
    record Req(UUID from, UUID to, Kind kind, int island, long expires) {}
    record Pending(UUID who, Vec3 start, long due, Runnable go) {}

    private static final List<Req> reqs = new ArrayList<>();
    private static final Map<UUID, Long> lastSent = new HashMap<>();
    private static final Map<UUID, Pending> pending = new HashMap<>();
    private static final int EXPIRE = 60 * 20, COOLDOWN = 10 * 20, WARMUP = 3 * 20;

    static void register(CommandDispatcher<CommandSourceStack> d) {
        d.register(Commands.literal("tpa").then(Commands.argument("player", EntityArgument.player())
                .executes(c -> request(c.getSource(), EntityArgument.getPlayer(c, "player"), Kind.TPA))));
        d.register(Commands.literal("tpahere").then(Commands.argument("player", EntityArgument.player())
                .executes(c -> request(c.getSource(), EntityArgument.getPlayer(c, "player"), Kind.TPAHERE))));
        d.register(Commands.literal("visit").then(Commands.argument("player", EntityArgument.player())
                .executes(c -> request(c.getSource(), EntityArgument.getPlayer(c, "player"), Kind.VISIT))));
        d.register(Commands.literal("tpaccept").executes(c -> answer(c.getSource(), null, true))
                .then(Commands.argument("player", EntityArgument.player())
                        .executes(c -> answer(c.getSource(), EntityArgument.getPlayer(c, "player"), true))));
        d.register(Commands.literal("tpdeny").executes(c -> answer(c.getSource(), null, false))
                .then(Commands.argument("player", EntityArgument.player())
                        .executes(c -> answer(c.getSource(), EntityArgument.getPlayer(c, "player"), false))));
    }

    // ------------------------------------------------------------------ requests
    static int request(CommandSourceStack s, ServerPlayer target, Kind kind) throws com.mojang.brigadier.exceptions.CommandSyntaxException {
        ServerPlayer me = s.getPlayerOrException();
        MinecraftServer server = s.getServer();
        long now = server.getTickCount();
        if (me == target) { s.sendFailure(t(kind == Kind.VISIT ? "That's your own island: /island home." : "You can't send that to yourself.", ChatFormatting.RED)); return 0; }
        Long last = lastSent.get(me.getUUID());
        if (last != null && now - last < COOLDOWN) { s.sendFailure(t("Wait a few seconds before sending another request.", ChatFormatting.RED)); return 0; }
        int island = 0;
        if (kind == Kind.VISIT) {
            island = SkyblockMod.plot(server, target);
            if (island <= 0) { s.sendFailure(t(target.getScoreboardName() + " doesn't have an island yet.", ChatFormatting.RED)); return 0; }
            if (island == SkyblockMod.plot(server, me)) { s.sendFailure(t("You're on that island already: /island home.", ChatFormatting.RED)); return 0; }
        }
        final int isl = island;
        reqs.removeIf(r -> r.from().equals(me.getUUID()) && r.to().equals(target.getUUID()));
        reqs.add(new Req(me.getUUID(), target.getUUID(), kind, isl, now + EXPIRE));
        lastSent.put(me.getUUID(), now);
        String n = me.getScoreboardName();
        String what = switch (kind) {
            case TPA -> " wants to teleport to you.";
            case TPAHERE -> " wants you to teleport to them.";
            case VISIT -> " wants to visit your island. Visitors can look around but can't build, break or open anything.";
        };
        String yes = kind == Kind.VISIT ? "Allow" : "Accept";
        // sent straight to the player (a tellraw aimed at a UUID is refused: "the provided selector includes entities",
        // which is why requests never arrived before 2.15.3)
        target.sendSystemMessage(t("✈ ", ChatFormatting.AQUA).append(t(n, ChatFormatting.YELLOW)).append(t(what + " ", ChatFormatting.AQUA))
                .append(button("[" + yes + "]", ChatFormatting.GREEN, "/tpaccept " + n, yes + " " + n + "'s request"))
                .append(t(" ", ChatFormatting.AQUA))
                .append(button("[Deny]", ChatFormatting.RED, "/tpdeny " + n, "Deny " + n + "'s request")));
        me.sendSystemMessage(t("Request sent to " + target.getScoreboardName() + ". It expires in 60 seconds.", ChatFormatting.AQUA));
        return 1;
    }

    private static net.minecraft.network.chat.MutableComponent button(String label, ChatFormatting color, String cmd, String hover) {
        return t(label, color).withStyle(st -> st.withBold(true).withClickEvent(new net.minecraft.network.chat.ClickEvent.RunCommand(cmd))
                .withHoverEvent(new net.minecraft.network.chat.HoverEvent.ShowText(t(hover, ChatFormatting.GRAY))));
    }

    static int answer(CommandSourceStack s, ServerPlayer from, boolean accept) throws com.mojang.brigadier.exceptions.CommandSyntaxException {
        ServerPlayer me = s.getPlayerOrException();
        MinecraftServer server = s.getServer();
        long now = server.getTickCount();
        reqs.removeIf(r -> r.expires() < now);
        Req req = null;
        for (int i = reqs.size() - 1; i >= 0; i--) {   // newest first
            Req r = reqs.get(i);
            if (r.to().equals(me.getUUID()) && (from == null || r.from().equals(from.getUUID()))) { req = r; break; }
        }
        if (req == null) { s.sendFailure(t("You have no request" + (from == null ? "" : " from " + from.getScoreboardName()) + " to answer.", ChatFormatting.RED)); return 0; }
        reqs.remove(req);
        ServerPlayer asker = server.getPlayerList().getPlayer(req.from());
        if (asker == null) { s.sendFailure(t("They're not online any more.", ChatFormatting.RED)); return 0; }
        if (!accept) {
            me.sendSystemMessage(t("Request from " + asker.getScoreboardName() + " denied.", ChatFormatting.GRAY));
            asker.sendSystemMessage(t(me.getScoreboardName() + " denied your request.", ChatFormatting.RED));
            return 1;
        }
        switch (req.kind()) {
            case TPA -> travel(asker, () -> { pass(server, asker, island(server, me)); run(server, "tp " + asker.getUUID() + " " + me.getUUID()); }, "to " + me.getScoreboardName());
            case TPAHERE -> travel(me, () -> { pass(server, me, island(server, asker)); run(server, "tp " + me.getUUID() + " " + asker.getUUID()); }, "to " + asker.getScoreboardName());
            case VISIT -> {
                int island = req.island();
                travel(asker, () -> {
                    pass(server, asker, island);
                    run(server, "execute as " + asker.getUUID() + " run function " + SkyblockMod.NS + ":p/home2 with storage " + SkyblockMod.NS + ":d plots[" + island + "]");
                    asker.sendSystemMessage(t("Welcome to " + me.getScoreboardName() + "'s island! You can look around, but not build or open anything. /island home takes you back.", ChatFormatting.AQUA));
                }, "to " + me.getScoreboardName() + "'s island");
            }
        }
        me.sendSystemMessage(t("Accepted " + asker.getScoreboardName() + "'s request.", ChatFormatting.GREEN));
        return 1;
    }

    /** Teleport after WARMUP ticks if `who` stays put. */
    private static void travel(ServerPlayer who, Runnable go, String where) {
        pending.put(who.getUUID(), new Pending(who.getUUID(), who.position(), who.level().getServer().getTickCount() + WARMUP, go));
        who.sendSystemMessage(t("Teleporting " + where + " in 3 seconds. Don't move.", ChatFormatting.AQUA));
    }

    static void onTick(MinecraftServer server) {
        if (pending.isEmpty()) return;
        long now = server.getTickCount();
        for (Iterator<Pending> it = pending.values().iterator(); it.hasNext(); ) {
            Pending p = it.next();
            ServerPlayer who = server.getPlayerList().getPlayer(p.who());
            if (who == null) { it.remove(); continue; }
            if (who.position().distanceToSqr(p.start()) > 1.0) {
                it.remove();
                who.sendSystemMessage(t("Teleport cancelled: you moved.", ChatFormatting.RED));
                continue;
            }
            if (now >= p.due()) { it.remove(); p.go().run(); }
        }
    }

    static void forget(ServerPlayer p) {
        pending.remove(p.getUUID());
        reqs.removeIf(r -> r.from().equals(p.getUUID()) || r.to().equals(p.getUUID()));
        lastSent.remove(p.getUUID());
    }

    /** The island a player is on as far as visits go: the one they're visiting (cs_vis), else their own. */
    static int island(MinecraftServer server, ServerPlayer p) {
        int v = SkyblockMod.score(server, p, "cs_vis");
        return v > 0 ? v : SkyblockMod.plot(server, p);
    }

    /** A visitor's pass (2.15.3): cs_vis = the island they may stay on. The datapack's island-bounds checks (p/bounds,
     *  p/nbounds, p/ebounds) let them stay while they're inside that island's space and drop the pass once they leave
     *  it; before this, an accepted /tpa or /visit was undone a moment later by the bounds check. */
    static void pass(MinecraftServer server, ServerPlayer p, int island) {
        if (island > 0 && island != SkyblockMod.plot(server, p)) run(server, "scoreboard players set " + p.getScoreboardName() + " cs_vis " + island);
        else run(server, "scoreboard players reset " + p.getScoreboardName() + " cs_vis");   // by name: a UUID here is a separate score holder
    }

    static void run(MinecraftServer server, String cmd) {
        server.getCommands().performPrefixedCommand(server.createCommandSourceStack().withPermission(LevelBasedPermissionSet.GAMEMASTER).withSuppressedOutput(), cmd);
    }

    // ------------------------------------------------------------------ staff
    /** /island tp <player|id> (ops): go to anyone's island, online or not, keeping your gamemode. */
    static int staffTp(CommandSourceStack s, String who) throws com.mojang.brigadier.exceptions.CommandSyntaxException {
        ServerPlayer me = s.getPlayerOrException();
        MinecraftServer server = s.getServer();
        int id = 0;
        if (who.matches("\\d+")) id = Integer.parseInt(who);
        else {
            var o = server.getScoreboard().getObjective("cs_plot");
            if (o != null) for (var e : server.getScoreboard().listPlayerScores(o))
                if (e.owner().equalsIgnoreCase(who) && e.value() > 0) { id = e.value(); who = e.owner(); break; }
        }
        var plots = server.getCommandStorage().get(net.minecraft.resources.Identifier.fromNamespaceAndPath(SkyblockMod.NS, "d")).getListOrEmpty("plots");
        if (id <= 0 || id >= plots.size() || !plots.getCompoundOrEmpty(id).contains("cx")) {
            s.sendFailure(t("No island found for " + who + ".", ChatFormatting.RED)); return 0;
        }
        var pl = plots.getCompoundOrEmpty(id);
        int cx = pl.getIntOr("cx", 0), cz = pl.getIntOr("cz", 0);
        run(server, "execute in minecraft:overworld run tp " + me.getUUID() + " " + cx + ".5 " + (Portals.ISLAND_Y + 1) + " " + cz + ".5");
        List<String> members = new ArrayList<>();
        var o = server.getScoreboard().getObjective("cs_plot");
        if (o != null) for (var e : server.getScoreboard().listPlayerScores(o)) if (!e.owner().startsWith("#") && e.value() == id) members.add(e.owner());
        me.sendSystemMessage(t("Island #" + id + " (" + String.join(", ", members) + ")", ChatFormatting.GOLD));
        return 1;
    }

    static java.util.concurrent.CompletableFuture<com.mojang.brigadier.suggestion.Suggestions> suggestIslanders(
            com.mojang.brigadier.context.CommandContext<CommandSourceStack> c, com.mojang.brigadier.suggestion.SuggestionsBuilder b) {
        var o = c.getSource().getServer().getScoreboard().getObjective("cs_plot");
        String pre = b.getRemaining().toLowerCase(Locale.ROOT);
        if (o != null) for (var e : c.getSource().getServer().getScoreboard().listPlayerScores(o))
            if (!e.owner().startsWith("#") && e.value() > 0 && e.owner().toLowerCase(Locale.ROOT).startsWith(pre)) b.suggest(e.owner());
        return b.buildFuture();
    }

    // ------------------------------------------------------------------ island protection
    /** The overworld island (cs_plot id) at pos, 0 if none (hub, zones, void outside the grid). Same grid as Sidebar. */
    static int islandAt(Level level, BlockPos pos) {
        if (level.dimension() != Level.OVERWORLD) return 0;
        int col = Math.floorDiv(pos.getX(), Sidebar.GRID), row = Math.floorDiv(pos.getZ() - 2 * Sidebar.GRID, Sidebar.GRID);
        if (col < 0 || col >= Sidebar.COLS || row < 0) return 0;
        return row * Sidebar.COLS + col;
    }

    /** True when p may not touch things at pos: someone else's island, and not staff. Tells them why. */
    static boolean outsider(Player player, Level level, BlockPos pos) {
        if (!(player instanceof ServerPlayer p) || level.isClientSide()) return false;
        int id = islandAt(level, pos);
        if (id <= 0 || HubPlots.staff(p) || SkyblockMod.plot(level.getServer(), p) == id) return false;
        p.sendOverlayMessage(t("You're visiting this island: you can't change anything here.", ChatFormatting.RED));
        return true;
    }

    static boolean canBreak(Level world, Player player, BlockPos pos, BlockState state, BlockEntity be) { return !outsider(player, world, pos); }

    static InteractionResult onUseBlock(Player player, Level world, InteractionHand hand, BlockHitResult hit) {
        return outsider(player, world, hit.getBlockPos()) ? InteractionResult.FAIL : InteractionResult.PASS;
    }

    static InteractionResult onUseItem(Player player, Level world, InteractionHand hand) {
        if (!(player.getItemInHand(hand).getItem() instanceof BucketItem)) return InteractionResult.PASS;
        return outsider(player, world, player.blockPosition()) ? InteractionResult.FAIL : InteractionResult.PASS;
    }

    /** Right-clicking or hitting animals, minions, frames and the like; players are left to the PvP rules. */
    static InteractionResult onEntity(Player player, Level world, Entity e) {
        if (e instanceof Player || e.entityTags().contains("cs_npc")) return InteractionResult.PASS;
        return outsider(player, world, e.blockPosition()) ? InteractionResult.FAIL : InteractionResult.PASS;
    }
}

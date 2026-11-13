package crispy.ez;

import com.mojang.authlib.GameProfile;
import net.fabricmc.fabric.api.command.v2.CommandRegistrationCallback;
import net.fabricmc.fabric.api.entity.FakePlayer;
import net.fabricmc.fabric.api.event.player.PlayerBlockBreakEvents;
import net.fabricmc.fabric.api.event.player.UseBlockCallback;
import net.fabricmc.fabric.api.event.player.UseEntityCallback;
import net.minecraft.commands.CommandSourceStack;
import net.minecraft.commands.Commands;
import net.minecraft.core.BlockPos;
import net.minecraft.core.Direction;
import net.minecraft.core.registries.BuiltInRegistries;
import net.minecraft.network.chat.Component;
import net.minecraft.server.MinecraftServer;
import net.minecraft.server.level.ServerLevel;
import net.minecraft.world.InteractionHand;
import net.minecraft.world.InteractionResult;
import net.minecraft.world.entity.Entity;
import net.minecraft.world.item.ItemStack;
import net.minecraft.world.item.Items;
import net.minecraft.world.level.ClipContext;
import net.minecraft.world.level.block.Blocks;
import net.minecraft.world.level.block.state.BlockState;
import net.minecraft.world.phys.AABB;
import net.minecraft.world.phys.BlockHitResult;
import net.minecraft.world.phys.EntityHitResult;
import net.minecraft.world.phys.HitResult;
import net.minecraft.world.phys.Vec3;
import org.slf4j.Logger;
import org.slf4j.LoggerFactory;

import java.util.ArrayList;
import java.util.List;
import java.util.UUID;
import java.util.function.Predicate;

/**
 * /ezadmin selftest (1.5.0): checks every camp and bunker interaction the way a player meets it, with a fake player.
 *  - Reach: from where a player would stand, a ray to what they'd click (the game's own outline shapes for blocks,
 *    pick boxes for entities, like the client). The first thing it hits must be the trigger, not a wall or a roof.
 *  - Behaviour: the same click is sent through the real handlers (UseBlock/UseEntity/break events) and the result
 *    checked: the right menu opened, the player arrived where they should, the action was refused or allowed.
 *  - Geometry: spawn and arrival points are standable; the bunker doorway is open; the stairwell climbs one block
 *    at a time with headroom.
 * The bunker checks run in a temporary test bunker (a fake player's plot), again after growing it 16 -> 24, and the
 * test bunker is removed afterwards. Results go to whoever ran it and to the log ("[ez-selftest]").
 */
final class SelfTest {
    private SelfTest() {}

    static final Logger LOG = LoggerFactory.getLogger("ez-selftest");
    static final GameProfile PROFILE = new GameProfile(UUID.nameUUIDFromBytes("crispy-ez-selftest".getBytes()), "ez_selftest");

    static void init() {
        CommandRegistrationCallback.EVENT.register((d, ctx, env) -> d.register(Commands.literal("ezadmin")
                .requires(Commands.hasPermission(Commands.LEVEL_GAMEMASTERS))
                .then(Commands.literal("selftest").executes(c -> {
                    // not from inside the command: since 1.20.3 commands run during another command wait until it ends,
                    // so the test bunker's build commands would only land after the checks. Start on the next tick.
                    pending = c.getSource();
                    c.getSource().sendSuccess(() -> Component.literal("Self-test starting..."), false);
                    return 1; }))));
        net.fabricmc.fabric.api.event.lifecycle.v1.ServerTickEvents.END_SERVER_TICK.register(server -> {
            if (pending != null) { CommandSourceStack src = pending; pending = null; run(src); }
            step(server);
        });
    }
    static CommandSourceStack pending;

    // ---------------------------------------------------------------- results
    static final List<String> fails = new ArrayList<>();
    static int passed;
    static CommandSourceStack out;
    static void check(String name, boolean ok, String detail) {
        String line = (ok ? "PASS " : "FAIL ") + name + (detail.isEmpty() ? "" : "  (" + detail + ")");
        LOG.info("[ez-selftest] {}", line);
        if (ok) passed++; else fails.add(line);
        out.sendSuccess(() -> Component.literal(line).withStyle(ok ? net.minecraft.ChatFormatting.GREEN : net.minecraft.ChatFormatting.RED), false);
    }

    // ---------------------------------------------------------------- what a click hits
    record Hit(Entity entity, BlockPos pos, BlockState state, double dist) {
        String describe() { return entity != null ? BuiltInRegistries.ENTITY_TYPE.getKey(entity.getType()).getPath() + entity.entityTags()
                : pos == null ? "nothing" : BuiltInRegistries.BLOCK.getKey(state.getBlock()).getPath() + "@" + pos.toShortString(); }
    }
    /** The first thing a player's click would land on, looking from eye at target (reach 4.5, like survival). */
    static Hit firstHit(ServerLevel lvl, Entity self, Vec3 eye, Vec3 target) {
        Vec3 end = eye.add(target.subtract(eye).normalize().scale(4.5));
        BlockHitResult b = lvl.clip(new ClipContext(eye, end, ClipContext.Block.OUTLINE, ClipContext.Fluid.NONE, self));
        double bd = b.getType() == HitResult.Type.MISS ? Double.MAX_VALUE : eye.distanceTo(b.getLocation());
        Entity best = null; double ed = Double.MAX_VALUE;
        // other players aren't part of the layout: someone standing in front of a trader shouldn't fail its check
        for (Entity e : lvl.getEntities(self, new AABB(eye, end).inflate(2), e -> e.isPickable() && !(e instanceof net.minecraft.world.entity.player.Player))) {
            AABB box = e.getBoundingBox().inflate(e.getPickRadius());
            double dd = box.contains(eye) ? 0 : box.clip(eye, end).map(eye::distanceTo).orElse(Double.MAX_VALUE);
            if (dd < ed) { ed = dd; best = e; }
        }
        if (best != null && ed <= bd) return new Hit(best, null, null, ed);
        if (bd < Double.MAX_VALUE) return new Hit(null, b.getBlockPos(), lvl.getBlockState(b.getBlockPos()), bd);
        return new Hit(null, null, null, Double.MAX_VALUE);
    }
    static void reach(String name, ServerLevel lvl, Entity self, Vec3 feet, Vec3 target, Predicate<Hit> ok) {
        Hit h = firstHit(lvl, self, feet.add(0, 1.62, 0), target);
        check(name, ok.test(h), "first hit: " + h.describe() + (h.dist < 99 ? String.format(", %.1f blocks", h.dist) : ""));
    }
    static boolean empty(ServerLevel lvl, BlockPos p) { return lvl.getBlockState(p).getCollisionShape(lvl, p).isEmpty(); }
    /** A player can stand at feet: solid underneath, two blocks of room. */
    static boolean standable(ServerLevel lvl, double x, double y, double z) {
        BlockPos f = BlockPos.containing(x, y, z);
        return !empty(lvl, f.below()) && empty(lvl, f) && empty(lvl, f.above());
    }
    static boolean near(Entity e, double x, double y, double z) { return e.position().distanceTo(new Vec3(x, y, z)) < 1.5; }
    static InteractionResult useBlock(FakePlayerRef f, ServerLevel lvl, BlockPos pos, Direction face) {
        f.p.setItemInHand(InteractionHand.MAIN_HAND, f.held);
        return UseBlockCallback.EVENT.invoker().interact(f.p, lvl, InteractionHand.MAIN_HAND, new BlockHitResult(Vec3.atCenterOf(pos), face, pos, false));
    }
    static InteractionResult useEntity(FakePlayerRef f, ServerLevel lvl, Entity e) {
        f.p.setItemInHand(InteractionHand.MAIN_HAND, f.held);
        return UseEntityCallback.EVENT.invoker().interact(f.p, lvl, InteractionHand.MAIN_HAND, e, new EntityHitResult(e));
    }
    static final class FakePlayerRef { FakePlayer p; ItemStack held = ItemStack.EMPTY; }

    // ---------------------------------------------------------------- the run
    // 1.6.0: in phases, ~3 s apart, so lighting is measured after the light engine has caught up with a fresh build
    static final List<Runnable> phases = new ArrayList<>();
    static int wait;
    static void run(CommandSourceStack src) {
        out = src; fails.clear(); passed = 0; Design.report = new com.google.gson.JsonObject();
        MinecraftServer server = src.getServer();
        ServerLevel camp = server.getLevel(Plots.CAMP);
        if (camp == null) { src.sendFailure(Component.literal("No camp dimension.")); return; }
        FakePlayerRef f = new FakePlayerRef();
        f.p = FakePlayer.get(camp, PROFILE);
        Plots.load();
        Plots.plots.remove(PROFILE.id().toString());   // a leftover from an aborted run
        Plots.loadArea(server, -20, -20, 20, 20);
        Plots.Plot[] p = new Plots.Plot[1];
        phases.clear();
        phases.add(() -> { campChecks(server, camp, f); Design.camp(server, camp); Design.realBunkers(server, camp); p[0] = bunkerChecks(server, camp, f); });
        phases.add(() -> { bunkerLevel(server, camp, f, p[0], 0); p[0].level = 1; Plots.lay(server, p[0], false, 0); });
        phases.add(() -> { bunkerLevel(server, camp, f, p[0], 1); bunkerRest(server, camp, f, p[0]); Design.ids(server); Design.armor(server); Design.crafting(server); finish(server, camp, f); });
        wait = 0;
    }
    static void step(MinecraftServer server) {
        if (phases.isEmpty() || --wait > 0) return;
        Runnable r = phases.remove(0); wait = 60;
        try { r.run(); }
        catch (Exception e) {
            check("selftest ran to the end", false, e.toString());
            LOG.error("[ez-selftest] crashed", e);
            phases.clear();
            ServerLevel camp = server.getLevel(Plots.CAMP);
            finish(server, camp, null);
        }
    }
    static void finish(MinecraftServer server, ServerLevel camp, FakePlayerRef f) {
        cleanup(server, camp);
        if (f != null) f.p.setItemInHand(InteractionHand.MAIN_HAND, ItemStack.EMPTY);
        Design.write(passed, fails);
        String sum = passed + " passed, " + fails.size() + " failed";
        LOG.info("[ez-selftest] {}", sum);
        out.sendSuccess(() -> Component.literal("Self-test: " + sum).withStyle(fails.isEmpty() ? net.minecraft.ChatFormatting.GREEN : net.minecraft.ChatFormatting.RED,
                net.minecraft.ChatFormatting.BOLD), false);
    }

    static void campChecks(MinecraftServer server, ServerLevel camp, FakePlayerRef f) {
        check("camp spawn is standable", standable(camp, Plots.CAMP_SPAWN[0], Plots.CAMP_SPAWN[1], Plots.CAMP_SPAWN[2]), "");
        check("bunker exit point in camp is standable", standable(camp, Plots.CAMP_EXIT[0], Plots.CAMP_EXIT[1], Plots.CAMP_EXIT[2]), "");
        // every trader: from 2.5 blocks in front of it, the click lands on it, and opens its menu
        List<Entity> npcs = camp.getEntities((Entity) null, new AABB(-20, 60, -20, 20, 70, 20), e -> e.entityTags().stream().anyMatch(t -> t.startsWith("ez.shop.")));
        check("five traders in camp", npcs.size() == 5, npcs.size() + " found");
        for (Entity npc : npcs) {
            String shop = npc.entityTags().stream().filter(t -> t.startsWith("ez.shop.")).findFirst().orElse("?").substring(8);
            double yaw = Math.toRadians(npc.getYRot());
            Vec3 front = npc.position().add(-Math.sin(yaw) * 2.5, 0, Math.cos(yaw) * 2.5);
            reach("click reaches the " + shop + " trader", camp, f.p, front, npc.position().add(0, 1.1, 0), h -> h.entity == npc);
            Ui.LAST.remove(f.p.getUUID());
            InteractionResult r = useEntity(f, camp, npc);
            String title = Ui.LAST.get(f.p.getUUID());
            check("the " + shop + " trader opens its menu", r != InteractionResult.PASS && title != null, "result " + r + ", menu " + title);
        }
        // the deploy pad: from the road north of it
        reach("click reaches the deploy pad", camp, f.p, new Vec3(0.5, 64, 7.0), new Vec3(0.5, 64.2, 12.5), h -> h.entity != null && h.entity.entityTags().contains("ez.deploy"));
        // the blockhouse door: from the bottom of its steps and from the top
        Predicate<Hit> door = h -> (h.entity != null && h.entity.entityTags().contains("ez.bunkerdoor")) || (h.state != null && Plots.isCampDoor(camp, h.pos, h.state));
        reach("click reaches the bunker door (from the bottom step)", camp, f.p, new Vec3(12.5, 62, 15.3), new Vec3(12.5, 63, 16.0), door);
        reach("click reaches the bunker door (from the top of the steps)", camp, f.p, new Vec3(12.5, 64, 12.5), new Vec3(12.5, 62.8, 16.0), door);
        check("blockhouse steps: top standable", standable(camp, 12.5, 64, 12.5), "");
        check("blockhouse steps: bottom standable", standable(camp, 12.5, 62, 15.5), "");
    }

    static Plots.Plot bunkerChecks(MinecraftServer server, ServerLevel camp, FakePlayerRef f) {
        // the door with no bunker yet opens the claim menu
        Ui.LAST.remove(f.p.getUUID());
        InteractionResult r0 = useBlock(f, camp, new BlockPos(Plots.DOOR_X, 62, Plots.DOOR_Z), Direction.NORTH);
        check("door without a bunker opens the claim menu", r0 == InteractionResult.SUCCESS && "Your Bunker".equals(Ui.LAST.get(f.p.getUUID())), "result " + r0 + ", menu " + Ui.LAST.get(f.p.getUUID()));
        Plots.Plot p = Plots.claim(f.p);
        p.name = PROFILE.name();
        return p;
    }

    /** Checks on the test bunker at one size; run a few seconds after it was laid, so the light engine has caught up. */
    static void bunkerLevel(MinecraftServer server, ServerLevel camp, FakePlayerRef f, Plots.Plot p, int level) {
            String tag = " [" + Plots.SIZES[level] + "x" + Plots.SIZES[level] + "]";
        int x = Plots.cx(p.index), z = Plots.cz(p.index), h = Plots.half(p), F = Plots.FLOOR, z0 = z - h;
        // in through the camp door: block and box
        Plots.move(f.p, Plots.CAMP_EXIT[0], Plots.CAMP_EXIT[1], Plots.CAMP_EXIT[2], 0f);
        InteractionResult r = useBlock(f, camp, new BlockPos(Plots.DOOR_X, 62, Plots.DOOR_Z), Direction.NORTH);
        check("camp door block takes you to your bunker" + tag, r == InteractionResult.SUCCESS && near(f.p, x + 0.5, F + 1, z + h - 2.5), "result " + r + ", now at " + f.p.blockPosition().toShortString());
        Entity doorBox = camp.getEntities((Entity) null, new AABB(10, 60, 13, 15, 66, 18), e -> e.entityTags().contains("ez.bunkerdoor")).stream().findFirst().orElse(null);
        Plots.move(f.p, Plots.CAMP_EXIT[0], Plots.CAMP_EXIT[1], Plots.CAMP_EXIT[2], 0f);
        r = doorBox == null ? InteractionResult.PASS : useEntity(f, camp, doorBox);
        check("camp door box takes you to your bunker" + tag, r == InteractionResult.SUCCESS && near(f.p, x + 0.5, F + 1, z + h - 2.5), "box " + (doorBox != null) + ", result " + r);
        check("bunker arrival point is standable" + tag, standable(camp, x + 0.5, F + 1, z + h - 2.5), "");
        // the doorway and the stairwell
        check("doorway in the north wall is open" + tag, empty(camp, new BlockPos(x, F + 1, z0 - 1)) && empty(camp, new BlockPos(x, F + 2, z0 - 1)), "");
        double[][] path = new double[8][];
        path[0] = new double[]{x + 0.5, F + 1, z0 - 1.5};
        for (int st = 0; st < 5; st++) path[1 + st] = new double[]{x + 0.5, F + 2 + st, z0 - 2.5 - st};
        path[6] = new double[]{x + 0.5, F + 6, z0 - 6.5};
        path[7] = new double[]{x + 0.5, F + 6, z0 - 7.5};
        boolean walk = true; String bad = "";
        for (int i = 0; i < path.length; i++) {
            if (!standable(camp, path[i][0], path[i][1], path[i][2])) { walk = false; bad = "can't stand at step " + i + " " + BlockPos.containing(path[i][0], path[i][1], path[i][2]).toShortString(); break; }
            if (i > 0 && path[i][1] - path[i - 1][1] > 1) { walk = false; bad = "step " + i + " is more than a block up"; break; }
        }
        check("stairwell climbs to the hatch" + tag, walk, bad);
        // the hatch: reach from the landing (straight up and at an angle), then block and box
        Vec3 land = new Vec3(x + 0.5, F + 6, z0 - 7.5);
        Predicate<Hit> hatch = hh -> (hh.entity != null && hh.entity.entityTags().contains("ez.bunkerexit")) || (hh.state != null && Plots.isHatch(camp, hh.pos, hh.state));
        reach("click reaches the hatch, looking up" + tag, camp, f.p, land, new Vec3(x + 0.5, F + 9.9, z0 - 7.5), hatch);
        reach("click reaches the hatch, at an angle" + tag, camp, f.p, new Vec3(x + 0.5, F + 6, z0 - 6.6), new Vec3(x + 1.3, F + 9.9, z0 - 8.3), hatch);
        Plots.move(f.p, land.x, land.y, land.z, 0f);
        r = useBlock(f, camp, new BlockPos(x, F + 9, z0 - 8), Direction.DOWN);
        check("hatch block takes you up to camp" + tag, r == InteractionResult.SUCCESS && near(f.p, Plots.CAMP_EXIT[0], Plots.CAMP_EXIT[1], Plots.CAMP_EXIT[2]), "result " + r + ", now at " + f.p.blockPosition().toShortString());
        Entity exitBox = camp.getEntities((Entity) null, new AABB(land, land).inflate(3), e -> e.entityTags().contains("ez.bunkerexit") && e instanceof net.minecraft.world.entity.Interaction).stream().findFirst().orElse(null);
        Plots.move(f.p, land.x, land.y, land.z, 0f);
        r = exitBox == null ? InteractionResult.PASS : useEntity(f, camp, exitBox);
        check("hatch box takes you up to camp" + tag, r == InteractionResult.SUCCESS && near(f.p, Plots.CAMP_EXIT[0], Plots.CAMP_EXIT[1], Plots.CAMP_EXIT[2]), "box " + (exitBox != null) + ", result " + r);
        // nothing of the shell left inside the room
        int stray = 0; String shell = Plots.shell(p);
        for (int bx = x - h; bx < x + h; bx++) for (int bz = z - h; bz < z + h; bz++) for (int by = F + 1; by <= F + 6; by++)
            if (BuiltInRegistries.BLOCK.getKey(camp.getBlockState(new BlockPos(bx, by, bz)).getBlock()).toString().equals(shell)) stray++;
        check("no wall blocks left inside the room" + tag, stray == 0, stray + " found");
        Design.bunker(server, camp, p, tag);
            }

    /** Protection, storage, workbench and finish, on the grown bunker. */
    static void bunkerRest(MinecraftServer server, ServerLevel camp, FakePlayerRef f, Plots.Plot p) {
        int x = Plots.cx(p.index), z = Plots.cz(p.index), h = Plots.half(p), F = Plots.FLOOR, z0 = z - h;
        Plots.move(f.p, x + 0.5, F + 1, z + 0.5, 0f);
        // protection
        boolean wall = PlayerBlockBreakEvents.BEFORE.invoker().beforeBlockBreak(camp, f.p, new BlockPos(x - h - 1, F + 3, z), camp.getBlockState(new BlockPos(x - h - 1, F + 3, z)), null);
        check("bunker walls can't be broken", !wall, "");
        boolean floor = PlayerBlockBreakEvents.BEFORE.invoker().beforeBlockBreak(camp, f.p, new BlockPos(x + 2, F, z + 2), camp.getBlockState(new BlockPos(x + 2, F, z + 2)), null);
        check("the floor inside can be dug", floor, "");
        // storage: a vanilla chest is refused; Stash Crates up to the limit, then refused
        f.held = new ItemStack(Items.CHEST);
        check("a vanilla chest can't be placed", useBlock(f, camp, new BlockPos(x, F, z), Direction.UP) == InteractionResult.FAIL, "");
        f.held = Storage.crate(server);
        int max = Storage.limit(p), placed = Storage.count(server, p); boolean limitOk = true;
        for (int i = 0; placed < max && i < 20; i++) {
            InteractionResult cr = useBlock(f, camp, new BlockPos(x - h + 2 + i, F, z), Direction.UP);
            if (cr == InteractionResult.FAIL) { limitOk = false; break; }
            Plots.run(server, Plots.inCamp(String.format("setblock %d %d %d %s", x - h + 2 + i, F + 1, z, Storage.CRATE_BLOCK)));
            placed = Storage.count(server, p);
        }
        InteractionResult over = useBlock(f, camp, new BlockPos(x, F, z + 3), Direction.UP);
        check("Stash Crates allowed up to the limit, then refused", limitOk && placed == max && over == InteractionResult.FAIL, placed + "/" + max + ", one more: " + over);
        f.held = ItemStack.EMPTY;
        // workbench: nothing without the upgrade, the menu with it
        BlockPos table = new BlockPos(x + 3, F + 1, z + 3);
        Plots.run(server, Plots.inCamp(String.format("setblock %d %d %d minecraft:smithing_table", table.getX(), table.getY(), table.getZ())));
        Ui.LAST.remove(f.p.getUUID());
        useBlock(f, camp, table, Direction.UP);
        boolean without = !"Gun Workbench".equals(Ui.LAST.get(f.p.getUUID()));
        p.perks.add("workbench");
        Ui.LAST.remove(f.p.getUUID());
        InteractionResult wr = useBlock(f, camp, table, Direction.UP);
        check("workbench needs the upgrade, then opens", without && wr == InteractionResult.SUCCESS && "Gun Workbench".equals(Ui.LAST.get(f.p.getUUID())), "result " + wr);
        p.perks.remove("workbench");
        // wall finish: walls change, a block of the same kind inside doesn't
        BlockPos marker = new BlockPos(x - 3, F + 1, z - 3), wallPos = new BlockPos(x + h, F + 3, z), ceil = new BlockPos(x - 1, F + 7, z + 1);
        String before = Plots.shell(p);
        Plots.run(server, Plots.inCamp(String.format("setblock %d %d %d %s", marker.getX(), marker.getY(), marker.getZ(), before)));
        Plots.restyle(server, p, before, "minecraft:stone_bricks");
        boolean wallChanged = camp.getBlockState(wallPos).is(Blocks.STONE_BRICKS), ceilChanged = camp.getBlockState(ceil).is(Blocks.STONE_BRICKS);
        boolean insideKept = BuiltInRegistries.BLOCK.getKey(camp.getBlockState(marker).getBlock()).toString().equals(before);
        Plots.restyle(server, p, "minecraft:stone_bricks", before);
        check("wall finish changes walls and ceiling, not the room", wallChanged && ceilChanged && insideKept, "walls " + wallChanged + ", ceiling " + ceilChanged + ", inside kept " + insideKept);
        }

    /** Remove the test bunker (its blocks, entities and record). */
    static void cleanup(MinecraftServer server, ServerLevel camp) {
        Plots.Plot p = Plots.plots.remove(PROFILE.id().toString());
        if (p == null) return;
        Plots.save();
        int x = Plots.cx(p.index), z = Plots.cz(p.index), c = Plots.CELL / 2;
        Plots.loadArea(server, x - c, z - c - 12, x + c, z + c);
        for (int y = Plots.FLOOR - 1; y <= Plots.FLOOR + 11; y++)
            Plots.run(server, Plots.inCamp(String.format("fill %d %d %d %d %d %d minecraft:air", x - c, y, z - c, x + c - 1, y, z + c - 1)));
        for (Entity e : camp.getEntities((Entity) null, new AABB(x - c, Plots.FLOOR - 2, z - c, x + c, Plots.FLOOR + 14, z + c), e -> !(e instanceof net.minecraft.world.entity.player.Player)))
            e.discard();
    }
}

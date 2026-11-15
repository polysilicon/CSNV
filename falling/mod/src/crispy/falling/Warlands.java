package crispy.falling;

import com.mojang.brigadier.CommandDispatcher;
import net.minecraft.ChatFormatting;
import net.minecraft.commands.CommandSourceStack;
import net.minecraft.commands.Commands;
import net.minecraft.commands.arguments.EntityArgument;
import net.minecraft.nbt.CompoundTag;
import net.minecraft.nbt.ListTag;
import net.minecraft.server.MinecraftServer;
import net.minecraft.server.level.ServerPlayer;
import net.minecraft.server.permissions.LevelBasedPermissionSet;
import net.minecraft.world.entity.LivingEntity;
import net.minecraft.world.entity.Mob;
import net.minecraft.world.entity.player.Player;

import java.util.*;

import static crispy.falling.Ui.t;

/**
 * The Warlands (2.18.0): Skyblock's PvPvE zone (layout and mobs: expansion.py + warlands/island.py; a resource zone
 * like the others for mining, regrowth and the gathered marks). What's different, here:
 * - Access: not open yet. Only ops and players tagged {@link #TESTER} (/warlands tester <player>) can /warp warlands;
 *   for anyone else it doesn't exist, and it isn't in the warps menu. Cfg warlands.open (1b) will open it later.
 * - Entry: a random drop-in. /warp warlands drops you in above one of the drop points (cfg warlands.drops), the one
 *   furthest from other players among a few random picks, with slow falling, so nobody can camp an entrance. You're
 *   protected from other players for PROTECT_TICKS (attacking someone ends it).
 * - PvP is on (HubPlots.noPvp asks {@link #pvpBlocked}); dying drops everything (ZoneRules.onPlayerDeath skips the
 *   stash here). Mobs are Lv 30-45, the Treasure Node's guardians Lv 50 (ZoneRules.levelUp).
 * - Leaving: /warp anywhere else from inside takes EXIT_TICKS of standing still unhurt (any damage cancels it). The
 *   combat tag (chat-tags mod, config/crispy_combat_block.txt) blocks warping out at all for 15 s after a fight.
 * - War Spoils (an item; datapack loot tables warlands/spoils_*): 10% of mob kills drop one, guardians 2-4.
 */
final class Warlands {
    private Warlands() {}

    static final String KEY = "warlands", TESTER = "cs_warlands_tester";
    static final int PROTECT_TICKS = 15 * 20, EXIT_TICKS = 5 * 20, DROP_HEIGHT = 14, SPACING = 25;
    private static final Map<UUID, Long> protect = new HashMap<>();
    record Exit(String where, long start) {}
    private static final Map<UUID, Exit> exits = new HashMap<>();
    private static long tick;

    static boolean is(Zones.Zone z) { return z != null && z.key().equals(KEY); }
    static boolean in(Player p) { return is(Zones.at(p.level(), p.blockPosition())); }
    static boolean op(ServerPlayer p) { return Commands.hasPermission(Commands.LEVEL_GAMEMASTERS).test(p.createCommandSourceStack()); }
    static CompoundTag cfg(MinecraftServer s) { return Economy.cfg(s).getCompoundOrEmpty("warlands"); }
    static boolean allowed(ServerPlayer p) {
        return op(p) || p.entityTags().contains(TESTER) || cfg(p.level().getServer()).getBooleanOr("open", false);
    }

    // ------------------------------------------------------------------ getting in
    static void dropIn(ServerPlayer p) {
        MinecraftServer server = p.level().getServer();
        ListTag drops = cfg(server).getListOrEmpty("drops");
        if (drops.isEmpty()) { p.sendSystemMessage(t("The Warlands aren't built yet.", ChatFormatting.RED)); return; }
        List<ServerPlayer> others = new ArrayList<>();
        for (ServerPlayer o : server.getPlayerList().getPlayers()) if (o != p && in(o) && o.isAlive() && !o.isSpectator()) others.add(o);
        Random r = new Random();
        int[] best = null; double bestD = -1;
        for (int i = 0; i < 12; i++) {   // a few random picks: the first far enough from everyone, else the furthest
            ListTag d = drops.getListOrEmpty(r.nextInt(drops.size()));
            int x = d.getIntOr(0, 0), y = d.getIntOr(1, 0), z = d.getIntOr(2, 0);
            double near = Double.MAX_VALUE;
            for (ServerPlayer o : others) near = Math.min(near, Math.hypot(o.getX() - x, o.getZ() - z));
            if (near > bestD) { bestD = near; best = new int[]{x, y, z}; }
            if (near >= SPACING) break;
        }
        float yaw = r.nextInt(360) - 180;
        run(p, "function crispy_skyblock:zones/tp {x:" + (best[0] + 0.5) + ",y:" + (best[1] + DROP_HEIGHT) + ",z:" + (best[2] + 0.5) + ",yaw:" + yaw + "}");
        run(p, "effect give @s minecraft:slow_falling 12 0 true");
        protect.put(p.getUUID(), tick + PROTECT_TICKS);
        p.sendSystemMessage(t("⚔ You drop into the Warlands. ", ChatFormatting.DARK_RED, ChatFormatting.BOLD)
                .append(t("PvP is on and you drop everything if you die. You're protected for 15 s (until you attack).", ChatFormatting.GRAY)));
    }

    // ------------------------------------------------------------------ PvP
    /** HubPlots.noPvp, when both players are in the Warlands: blocked only by fresh-drop protection. */
    static boolean pvpBlocked(Player victim, Player attacker) {
        if (attacker instanceof ServerPlayer a) protect.remove(a.getUUID());   // attacking ends your own protection
        Long until = protect.get(victim.getUUID());
        if (until == null || until < tick) return false;
        if (attacker instanceof ServerPlayer a) a.sendOverlayMessage(t("They just dropped in: protected for a few more seconds.", ChatFormatting.RED));
        return true;
    }

    // ------------------------------------------------------------------ getting out
    /** Zones.warp, when someone in the Warlands warps anywhere else: a short channel instead of leaving at once. */
    static boolean startExit(ServerPlayer p, String where) {
        if (!in(p) || Zones.staff(p) || where.equals(KEY)) return false;
        exits.put(p.getUUID(), new Exit(where, tick));
        p.sendSystemMessage(t("Leaving the Warlands in 5 s: don't take any damage.", ChatFormatting.YELLOW));
        return true;
    }

    static void onTick(MinecraftServer server) {
        tick++;
        if (tick % 200 == 0) protect.values().removeIf(u -> u < tick);
        if (exits.isEmpty()) return;
        for (Iterator<Map.Entry<UUID, Exit>> it = exits.entrySet().iterator(); it.hasNext(); ) {
            var e = it.next();
            ServerPlayer p = server.getPlayerList().getPlayer(e.getKey());
            if (p == null || !p.isAlive() || !in(p)) { it.remove(); continue; }
            if (p.hurtTime > 0) { it.remove(); p.sendOverlayMessage(t("Hit! Leaving cancelled.", ChatFormatting.RED)); continue; }
            long left = EXIT_TICKS - (tick - e.getValue().start());
            if (left > 0) { if (left % 20 == 0) p.sendOverlayMessage(t("Leaving the Warlands in " + left / 20 + "...", ChatFormatting.YELLOW)); continue; }
            it.remove();
            Zones.doWarp(p, e.getValue().where());
        }
    }

    // ------------------------------------------------------------------ mobs
    static int level(Mob m) {
        if (m.entityTags().contains("cs_wguard")) return 50;
        return 30 + m.getRandom().nextInt(16);
    }
    /** ZoneRules.onMobDeath: War Spoils from Warlands mobs. */
    static void mobDied(LivingEntity dead) {
        if (!(dead.level() instanceof net.minecraft.server.level.ServerLevel sl) || !in0(dead)) return;
        boolean guard = dead.entityTags().contains("cs_wguard");
        if (!guard && dead.getRandom().nextFloat() >= 0.10f) return;
        sl.getServer().getCommands().performPrefixedCommand(sl.getServer().createCommandSourceStack().withSuppressedOutput(),
                String.format(Locale.ROOT, "execute in minecraft:overworld run loot spawn %.2f %.2f %.2f loot crispy_skyblock:warlands/%s",
                        dead.getX(), dead.getY() + 0.5, dead.getZ(), guard ? "spoils_guard" : "spoils_mob"));
    }
    private static boolean in0(LivingEntity e) { return is(Zones.at(e.level(), e.blockPosition())); }

    // ------------------------------------------------------------------ helpers and staff commands
    static void run(ServerPlayer p, String cmd) {
        p.level().getServer().getCommands().performPrefixedCommand(p.createCommandSourceStack().withSuppressedOutput().withPermission(LevelBasedPermissionSet.GAMEMASTER), cmd);
    }

    /** /warlands tester <player> (toggle access), /warlands go (drop in), /warlands build (build or rebuild it). Ops only. */
    static void register(CommandDispatcher<CommandSourceStack> d) {
        d.register(Commands.literal("warlands").requires(Commands.hasPermission(Commands.LEVEL_GAMEMASTERS))
                .then(Commands.literal("tester").then(Commands.argument("player", EntityArgument.player()).executes(c -> {
                    ServerPlayer target = EntityArgument.getPlayer(c, "player");
                    boolean on = !target.entityTags().contains(TESTER);
                    if (on) target.addTag(TESTER); else target.removeTag(TESTER);
                    c.getSource().sendSuccess(() -> t(target.getScoreboardName() + (on ? " can now /warp warlands." : " can no longer /warp warlands."), ChatFormatting.GOLD), false);
                    if (on) target.sendSystemMessage(t("You've been let into the Warlands for testing: /warp warlands. PvP is on there!", ChatFormatting.GOLD));
                    return 1;
                })))
                .then(Commands.literal("go").executes(c -> { dropIn(c.getSource().getPlayerOrException()); return 1; }))
                .then(Commands.literal("build").executes(c -> {
                    c.getSource().getServer().getCommands().performPrefixedCommand(c.getSource().withPermission(LevelBasedPermissionSet.GAMEMASTER),
                            "function crispy_skyblock:zones/build_warlands");
                    return 1;
                })));
    }
}

package crispy.ez;

import net.fabricmc.fabric.api.command.v2.CommandRegistrationCallback;
import net.fabricmc.fabric.api.event.player.AttackBlockCallback;
import net.fabricmc.fabric.api.event.player.UseBlockCallback;
import net.fabricmc.fabric.api.event.player.UseEntityCallback;
import net.minecraft.commands.Commands;
import net.minecraft.core.registries.BuiltInRegistries;
import net.minecraft.network.chat.Component;
import net.minecraft.world.InteractionResult;
import net.minecraft.world.entity.player.Player;
import net.minecraft.world.level.Level;
import org.slf4j.Logger;
import org.slf4j.LoggerFactory;

/**
 * Click tracing (1.5.0), off by default: /ezadmin trace on|off. While on, every block use, entity use and block hit in
 * camp (and the bunkers, which are in the camp dimension) is logged with the player, the target, where the click
 * landed, how far it was from their eyes and which hand; the mod's own handlers add one line for what they decided
 * (Trace.d). Registered before every other handler, so it sees each click first. Logs go to the server log as
 * "[ez-trace] ...".
 */
final class Trace {
    private Trace() {}

    static final Logger LOG = LoggerFactory.getLogger("ez-trace");
    static boolean on;

    static boolean watched(Level w) { return w.dimension().equals(Plots.CAMP) || w.dimension().equals(Zone.CITY); }
    static String who(Player p) { return p.getGameProfile().name(); }
    static String v(net.minecraft.world.phys.Vec3 x) { return String.format("(%.2f %.2f %.2f)", x.x, x.y, x.z); }

    /** A handler's decision. */
    static void d(Player p, String what) { if (on) LOG.info("[ez-trace] {} -> {}", who(p), what); }

    static void init() {
        UseBlockCallback.EVENT.register((pl, world, hand, hit) -> {
            if (on && watched(world)) {
                var st = world.getBlockState(hit.getBlockPos());
                LOG.info("[ez-trace] {} use-block {} at {} face {} hit {} eye-dist {} hand {} holding {}", who(pl),
                        BuiltInRegistries.BLOCK.getKey(st.getBlock()), hit.getBlockPos().toShortString(), hit.getDirection(), v(hit.getLocation()),
                        String.format("%.2f", pl.getEyePosition().distanceTo(hit.getLocation())), hand,
                        BuiltInRegistries.ITEM.getKey(pl.getItemInHand(hand).getItem()));
            }
            return InteractionResult.PASS;
        });
        UseEntityCallback.EVENT.register((pl, world, hand, e, hit) -> {
            if (on && watched(world))
                LOG.info("[ez-trace] {} use-entity {} tags {} at {} eye-dist {} hand {}", who(pl), BuiltInRegistries.ENTITY_TYPE.getKey(e.getType()),
                        e.entityTags(), v(e.position()), String.format("%.2f", pl.getEyePosition().distanceTo(hit != null ? hit.getLocation() : e.position())), hand);
            return InteractionResult.PASS;
        });
        AttackBlockCallback.EVENT.register((pl, world, hand, pos, dir) -> {
            if (on && watched(world))
                LOG.info("[ez-trace] {} hit-block {} at {} face {}", who(pl), BuiltInRegistries.BLOCK.getKey(world.getBlockState(pos).getBlock()), pos.toShortString(), dir);
            return InteractionResult.PASS;
        });
        CommandRegistrationCallback.EVENT.register((d, ctx, env) -> d.register(Commands.literal("ezadmin")
                .requires(Commands.hasPermission(Commands.LEVEL_GAMEMASTERS))
                .then(Commands.literal("trace")
                        .then(Commands.literal("on").executes(c -> { on = true; c.getSource().sendSuccess(() -> Component.literal("Click tracing on: see [ez-trace] in the server log."), true); return 1; }))
                        .then(Commands.literal("off").executes(c -> { on = false; c.getSource().sendSuccess(() -> Component.literal("Click tracing off."), true); return 1; })))));
    }
}

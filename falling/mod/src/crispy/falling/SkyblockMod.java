package crispy.falling;

import net.fabricmc.api.ModInitializer;
import net.fabricmc.fabric.api.command.v2.CommandRegistrationCallback;
import net.fabricmc.fabric.api.event.lifecycle.v1.ServerTickEvents;
import net.fabricmc.fabric.api.event.player.PlayerBlockBreakEvents;
import net.fabricmc.fabric.api.event.player.UseBlockCallback;
import net.fabricmc.fabric.api.event.player.UseItemCallback;
import net.fabricmc.fabric.api.event.player.UseEntityCallback;
import net.minecraft.world.InteractionHand;
import net.minecraft.world.InteractionResult;
import net.minecraft.commands.CommandSourceStack;
import net.minecraft.commands.Commands;
import net.minecraft.commands.arguments.EntityArgument;
import net.minecraft.network.chat.Component;
import net.minecraft.server.MinecraftServer;
import net.minecraft.server.level.ServerPlayer;
import net.minecraft.server.permissions.LevelBasedPermissionSet;
import net.minecraft.world.scores.Objective;
import net.minecraft.world.scores.ReadOnlyScoreInfo;

import com.mojang.brigadier.CommandDispatcher;
import com.mojang.brigadier.builder.LiteralArgumentBuilder;

/**
 * Commands for the crispy_skyblock datapack (Skyblock on Falling01):
 * /island (alias /is) opens the Island Menu; /island choose the starter island picker; /island challenges (or
 * /challenges) the challenge menu; /island level works out your island's level; /island top lists the best islands;
 * /invite <player> (or /island invite <player>) invites someone by name. Also coins and the merchants' shop
 * (Economy, Shop), minions (Minions), the per-player sidebar (Sidebar) and the hub portals (Portals).
 * Menus are chest GUIs defined by the datapack in storage crispy_skyblock:menus (SkyMenus); levels are counted from
 * the blocks in the island's plot (IslandLevels).
 */
public class SkyblockMod implements ModInitializer {
    static final String NS = "crispy_skyblock";

    @Override
    public void onInitialize() {
        ServerTickEvents.END_SERVER_TICK.register(IslandLevels::onTick);
        ServerTickEvents.END_SERVER_TICK.register(Minions::onTick);
        ServerTickEvents.END_SERVER_TICK.register(Sidebar::onTick);
        ServerTickEvents.END_SERVER_TICK.register(Portals::onTick);
        PlayerBlockBreakEvents.BEFORE.register(Portals::canBreak);
        UseBlockCallback.EVENT.register(Realms::onUseBlock);
        UseBlockCallback.EVENT.register(Minions::onUseBlock);
        UseItemCallback.EVENT.register(Gear::onUseItem);
        UseEntityCallback.EVENT.register((player, world, hand, entity, hit) -> {
            // merchants: villagers tagged cs_npc + cs_shop_<category> open that shop instead of trading
            if (entity.entityTags().contains("cs_npc")) {
                if (hand == InteractionHand.MAIN_HAND && player instanceof ServerPlayer p)
                    for (String t : entity.entityTags())
                        if (t.startsWith("cs_shop_")) Shop.open(p.level().getServer(), p, t.substring(8));
                return InteractionResult.SUCCESS;
            }
            return Minions.onUseEntity(player, world, hand, entity);
        });
        CommandRegistrationCallback.EVENT.register((d, ctx, sel) -> {
            Economy.register(d);
            d.register(Commands.literal("invite").then(Commands.argument("player", EntityArgument.player())
                    .executes(c -> invite(c.getSource(), EntityArgument.getPlayer(c, "player")))));
            d.register(Commands.literal("challenges")
                    .executes(c -> menu(c.getSource(), "challenges")));
            d.register(Commands.literal("gear")
                    .executes(c -> menu(c.getSource(), "gear")));
            register(d, "island");
            register(d, "is");
        });
    }

    static void register(CommandDispatcher<CommandSourceStack> d, String name) {
        LiteralArgumentBuilder<CommandSourceStack> root = Commands.literal(name)
                .executes(c -> run(c.getSource(), "trigger cs_act set 7"))
                .then(Commands.literal("invite").then(Commands.argument("player", EntityArgument.player())
                        .executes(c -> invite(c.getSource(), EntityArgument.getPlayer(c, "player")))))
                .then(Commands.literal("choose").executes(c -> choose(c.getSource())))
                .then(Commands.literal("challenges").executes(c -> menu(c.getSource(), "challenges")))
                .then(Commands.literal("gear").executes(c -> menu(c.getSource(), "gear")))
                .then(Commands.literal("level").executes(c -> IslandLevels.command(c.getSource())))
                .then(Commands.literal("top").executes(c -> IslandLevels.top(c.getSource())))
                // run by the datapack after a new island, so an island left empty drops off the board right away
                .then(Commands.literal("refreshboard").requires(Commands.hasPermission(Commands.LEVEL_GAMEMASTERS))
                        .executes(c -> { IslandLevels.updateBoard(c.getSource().getServer()); return 1; }));
        d.register(root);
    }

    /** The starter island picker: for players without an island, or who chose "Start a new island". */
    static int choose(CommandSourceStack s) throws com.mojang.brigadier.exceptions.CommandSyntaxException {
        ServerPlayer p = s.getPlayerOrException();
        if (plot(s.getServer(), p) > 0 && !p.entityTags().contains("cs_new")) {
            s.sendFailure(Component.literal("You already have an island. Use Start a new island in the Island Menu to pick another."));
            return 0;
        }
        return menu(s, "islands");
    }

    static int menu(CommandSourceStack s, String key) throws com.mojang.brigadier.exceptions.CommandSyntaxException {
        ServerPlayer p = s.getPlayerOrException();
        if (!SkyMenus.open(s.getServer(), p, key)) { s.sendFailure(Component.literal("That menu isn't set up.")); return 0; }
        return 1;
    }

    static int invite(CommandSourceStack s, ServerPlayer target) throws com.mojang.brigadier.exceptions.CommandSyntaxException {
        ServerPlayer me = s.getPlayerOrException();
        if (me == target) { s.sendFailure(Component.literal("You can't invite yourself.")); return 0; }
        String name = target.getGameProfile().name().replace("\\", "").replace("\"", "");
        return run(s, "function " + NS + ":act/invite_player {name:\"" + name + "\"}");
    }

    static int run(CommandSourceStack s, String cmd) {
        s.getServer().getCommands().performPrefixedCommand(s.withPermission(LevelBasedPermissionSet.GAMEMASTER), cmd);
        return 1;
    }

    /** The player's island id (cs_plot), 0 if none. */
    static int plot(MinecraftServer server, ServerPlayer p) { return score(server, p, "cs_plot"); }

    static int score(MinecraftServer server, ServerPlayer p, String objective) {
        Objective obj = server.getScoreboard().getObjective(objective);
        if (obj == null) return 0;
        ReadOnlyScoreInfo info = server.getScoreboard().getPlayerScoreInfo(p, obj);
        return info == null ? 0 : info.value();
    }
}

package crispy.falling;

import net.fabricmc.api.ModInitializer;
import net.fabricmc.fabric.api.command.v2.CommandRegistrationCallback;
import net.minecraft.commands.CommandSourceStack;
import net.minecraft.commands.Commands;
import net.minecraft.commands.arguments.EntityArgument;
import net.minecraft.network.chat.Component;
import net.minecraft.server.level.ServerPlayer;
import net.minecraft.server.permissions.LevelBasedPermissionSet;

/**
 * /invite <player> (also /island invite <player>): invite someone to your Crispy Falling island by name, from
 * anywhere. Runs the datapack's crispy_falling:act/invite_player as the inviter, with the permission functions need.
 * /island opens the Island Menu. The menu's "Invite a player…" button asks for a name and runs /invite.
 */
public class InviteCommand implements ModInitializer {
    @Override
    public void onInitialize() {
        CommandRegistrationCallback.EVENT.register((d, ctx, sel) -> {
            d.register(Commands.literal("invite").then(Commands.argument("player", EntityArgument.player()).executes(c -> invite(c.getSource(), EntityArgument.getPlayer(c, "player")))));
            d.register(Commands.literal("island")
                    .executes(c -> run(c.getSource(), "trigger cf_act set 7"))
                    .then(Commands.literal("invite").then(Commands.argument("player", EntityArgument.player())
                            .executes(c -> invite(c.getSource(), EntityArgument.getPlayer(c, "player"))))));
        });
    }

    static int invite(CommandSourceStack s, ServerPlayer target) throws com.mojang.brigadier.exceptions.CommandSyntaxException {
        ServerPlayer me = s.getPlayerOrException();
        if (me == target) { s.sendFailure(Component.literal("You can't invite yourself.")); return 0; }
        String name = target.getGameProfile().name().replace("\\", "").replace("\"", "");
        return run(s, "function crispy_falling:act/invite_player {name:\"" + name + "\"}");
    }

    static int run(CommandSourceStack s, String cmd) {
        s.getServer().getCommands().performPrefixedCommand(s.withPermission(LevelBasedPermissionSet.GAMEMASTER), cmd);
        return 1;
    }
}

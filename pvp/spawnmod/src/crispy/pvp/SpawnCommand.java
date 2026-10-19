package crispy.pvp;

import com.mojang.brigadier.arguments.StringArgumentType;
import net.fabricmc.api.ModInitializer;
import net.fabricmc.fabric.api.command.v2.CommandRegistrationCallback;
import net.minecraft.commands.CommandSourceStack;
import net.minecraft.commands.Commands;
import net.minecraft.network.chat.Component;

/**
 * /spawn and /lobby run the datapack's "/trigger pvp.spawn" (which keeps its 10 s combat lock).
 * /pvpmenu <name> opens a chest menu from storage pvp:menus (see PvpMenus).
 */
public class SpawnCommand implements ModInitializer {
    @Override
    public void onInitialize() {
        CommandRegistrationCallback.EVENT.register((dispatcher, context, selection) -> {
            for (String name : new String[]{"spawn", "lobby"}) {
                dispatcher.register(Commands.literal(name).requires(CommandSourceStack::isPlayer).executes(c -> {
                    CommandSourceStack s = c.getSource();
                    s.getServer().getCommands().performPrefixedCommand(s.withSuppressedOutput(), "trigger pvp.spawn");
                    return 1;
                }));
            }
            // no requires(isPlayer) here: datapack functions use it, and they're parsed with a non-player source
            dispatcher.register(Commands.literal("pvpmenu")
                    .then(Commands.argument("name", StringArgumentType.word()).executes(c -> {
                        CommandSourceStack s = c.getSource();
                        String key = StringArgumentType.getString(c, "name");
                        if (!PvpMenus.open(s.getServer(), s.getPlayerOrException(), key))
                            s.sendFailure(Component.literal("No menu called " + key));
                        return 1;
                    })));
        });
    }
}

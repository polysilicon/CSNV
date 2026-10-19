package crispy.pvp;

import net.fabricmc.api.ModInitializer;
import net.fabricmc.fabric.api.command.v2.CommandRegistrationCallback;
import net.minecraft.commands.CommandSourceStack;
import net.minecraft.commands.Commands;

/** /spawn and /lobby on Crispy PvP: run the datapack's "/trigger pvp.spawn" (which keeps its 10 s combat lock). */
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
        });
    }
}

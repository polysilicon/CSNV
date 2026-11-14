package crispy.pvp;

import net.fabricmc.fabric.api.command.v2.CommandRegistrationCallback;
import net.minecraft.commands.Commands;
import net.minecraft.server.level.ServerPlayer;
import net.minecraft.world.InteractionHand;

/**
 * Which hand an ability item (gun) was really used from. Minecraft tries the main hand first and, if it thinks that
 * item is on cooldown, also sends an off-hand use, so neither the click order nor the hands' contents say which item
 * the server actually used up. /pvphand, run as the player first thing in pvp:ability/used (the consume_item reward,
 * which runs while the item is still being used), reads the server's own record (getUsedItemHand) and tags the player
 * pvp.usedoff for the off hand, or clears it for the main hand. /pvpsync resends the inventory after a hand-back.
 */
final class HandTag {
    private HandTag() {}

    static void init() {
        CommandRegistrationCallback.EVENT.register((d, ctx, env) -> d.register(Commands.literal("pvphand")
                .requires(Commands.hasPermission(Commands.LEVEL_GAMEMASTERS))
                .executes(c -> {
                    if (c.getSource().getEntity() instanceof ServerPlayer p) {
                        boolean off = p.isUsingItem() && p.getUsedItemHand() == InteractionHand.OFF_HAND;
                        if (off) p.addTag("pvp.usedoff"); else p.removeTag("pvp.usedoff");
                        return off ? 2 : 1;
                    }
                    return 0;
                })));
        // /pvpsync: send the player's whole inventory again. A click the client thought was off-hand (main gun on
        // cooldown on its side) hides the off-hand gun on screen; if the server used the main gun instead, the
        // off hand never changes server-side, so nothing would ever tell the client to show it again.
        CommandRegistrationCallback.EVENT.register((d, ctx, env) -> d.register(Commands.literal("pvpsync")
                .requires(Commands.hasPermission(Commands.LEVEL_GAMEMASTERS))
                .executes(c -> {
                    if (!(c.getSource().getEntity() instanceof ServerPlayer p)) return 0;
                    p.inventoryMenu.sendAllDataToRemote();
                    if (p.containerMenu != p.inventoryMenu) p.containerMenu.sendAllDataToRemote();
                    return 1;
                })));
    }
}

package crispy.pvp;

import net.fabricmc.fabric.api.event.player.UseItemCallback;
import net.minecraft.core.component.DataComponents;
import net.minecraft.server.level.ServerPlayer;
import net.minecraft.world.InteractionHand;
import net.minecraft.world.InteractionResult;
import net.minecraft.world.item.ItemStack;
import net.minecraft.world.item.Items;

/**
 * Which hand an ability item (gun) is really used from. Minecraft tries the main hand first and, if that item is on
 * cooldown, falls through to the off hand; a datapack can't tell which one fired. This tags the player pvp.usedoff
 * when the off hand is used (and clears it for the main hand), so pvp:ability/used fires and hands back the right
 * gun. Registered before every other item-use listener and always lets the use go on.
 */
final class HandTag {
    private HandTag() {}

    static void init() {
        UseItemCallback.EVENT.register((player, world, hand) -> {
            if (player instanceof ServerPlayer p) {
                ItemStack st = p.getItemInHand(hand);
                if (st.is(Items.CLAY_BALL) && st.has(DataComponents.ITEM_MODEL)) {
                    if (hand == InteractionHand.OFF_HAND) p.addTag("pvp.usedoff"); else p.removeTag("pvp.usedoff");
                }
            }
            return InteractionResult.PASS;
        });
    }
}

package crispy.falling;

import net.minecraft.ChatFormatting;
import net.minecraft.core.component.DataComponents;
import net.minecraft.nbt.CompoundTag;
import net.minecraft.network.chat.Component;
import net.minecraft.server.level.ServerPlayer;
import net.minecraft.server.permissions.LevelBasedPermissionSet;
import net.minecraft.world.InteractionHand;
import net.minecraft.world.InteractionResult;
import net.minecraft.world.entity.player.Player;
import net.minecraft.world.item.ItemStack;
import net.minecraft.world.item.component.CustomData;
import net.minecraft.world.level.Level;

/**
 * Crafted gear with a right-click ability (the datapack's gear recipes: Aspect of the End, Rogue Sword...). The item's
 * custom_data holds {cs_ability:"<key>", cs_cd:<ticks>}; right-clicking it runs crispy_skyblock:gear/ab/<key> as and
 * at the player and puts the item on cooldown (its use_cooldown group, so each ability has its own sweep).
 */
public final class Gear {
    private Gear() {}

    static InteractionResult onUseItem(Player player, Level world, InteractionHand hand) {
        if (!(player instanceof ServerPlayer p) || player.isSpectator()) return InteractionResult.PASS;
        ItemStack stack = p.getItemInHand(hand);
        CustomData cd = stack.get(DataComponents.CUSTOM_DATA);
        if (cd == null) return InteractionResult.PASS;
        CompoundTag tag = cd.copyTag();
        String key = tag.getStringOr("cs_ability", "");
        if (key.isEmpty() || !key.matches("[a-z0-9_]+")) return InteractionResult.PASS;
        if (p.getCooldowns().isOnCooldown(stack)) {
            p.sendOverlayMessage(Component.literal("That ability is still recharging.").withStyle(ChatFormatting.RED));
            return InteractionResult.FAIL;
        }
        p.getCooldowns().addCooldown(stack, Math.max(1, tag.getIntOr("cs_cd", 20)));
        p.level().getServer().getCommands().performPrefixedCommand(
                p.createCommandSourceStack().withPermission(LevelBasedPermissionSet.GAMEMASTER).withSuppressedOutput(),
                "function " + SkyblockMod.NS + ":gear/ab/" + key);
        return InteractionResult.SUCCESS;
    }
}

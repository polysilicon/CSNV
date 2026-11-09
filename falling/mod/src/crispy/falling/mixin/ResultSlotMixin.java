package crispy.falling.mixin;

import crispy.falling.Compact;
import net.minecraft.world.entity.player.Player;
import net.minecraft.world.inventory.CraftingContainer;
import net.minecraft.world.inventory.ResultSlot;
import net.minecraft.world.item.ItemStack;
import org.spongepowered.asm.mixin.Final;
import org.spongepowered.asm.mixin.Mixin;
import org.spongepowered.asm.mixin.Shadow;
import org.spongepowered.asm.mixin.injection.At;
import org.spongepowered.asm.mixin.injection.Inject;
import org.spongepowered.asm.mixin.injection.callback.CallbackInfo;

/** Enchanted-resource crafts use 32 from each slot, not 1 (Compact.consume). */
@Mixin(ResultSlot.class)
public abstract class ResultSlotMixin {
    @Shadow @Final private CraftingContainer craftSlots;

    @Inject(method = "onTake", at = @At("HEAD"))
    private void crispy$enchanted(Player player, ItemStack stack, CallbackInfo ci) {
        Compact.consume(player, craftSlots);
    }
}

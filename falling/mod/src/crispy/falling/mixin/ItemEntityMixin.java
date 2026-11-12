package crispy.falling.mixin;

import crispy.falling.ItemCollections;
import net.minecraft.world.entity.item.ItemEntity;
import net.minecraft.world.entity.player.Player;
import org.spongepowered.asm.mixin.Mixin;
import org.spongepowered.asm.mixin.injection.At;
import org.spongepowered.asm.mixin.injection.Inject;
import org.spongepowered.asm.mixin.injection.callback.CallbackInfo;

/** Collections: how much of an item a player actually picked up (ItemCollections.touchStart/touchEnd). */
@Mixin(ItemEntity.class)
public abstract class ItemEntityMixin {
    @Inject(method = "playerTouch", at = @At("HEAD"))
    private void crispy$touchStart(Player player, CallbackInfo ci) {
        ItemCollections.touchStart((ItemEntity) (Object) this);
    }

    @Inject(method = "playerTouch", at = @At("TAIL"))
    private void crispy$touchEnd(Player player, CallbackInfo ci) {
        ItemCollections.touchEnd((ItemEntity) (Object) this, player);
    }
}

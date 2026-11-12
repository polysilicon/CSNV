package crispy.falling.mixin;

import crispy.falling.ItemCollections;
import crispy.falling.ZoneRules;
import net.minecraft.world.entity.item.ItemEntity;
import net.minecraft.world.item.ItemStack;
import net.minecraft.server.level.ServerPlayer;
import net.minecraft.world.damagesource.DamageSource;
import net.minecraft.world.entity.player.Player;
import org.spongepowered.asm.mixin.Mixin;
import org.spongepowered.asm.mixin.injection.At;
import org.spongepowered.asm.mixin.injection.Inject;
import org.spongepowered.asm.mixin.injection.callback.CallbackInfo;
import org.spongepowered.asm.mixin.injection.callback.CallbackInfoReturnable;

/** No PvP in the hub (HubPlots.noPvp): covers melee and arrows/tridents, which vanilla also checks with canHarmPlayer.
 * Dying in a resource zone: put aside everything not gathered there before the death drops (ZoneRules). */
@Mixin(ServerPlayer.class)
public abstract class ServerPlayerMixin {
    @Inject(method = "die", at = @At("HEAD"))
    private void crispy$zoneDeath(DamageSource source, CallbackInfo ci) {
        ZoneRules.onPlayerDeath((ServerPlayer) (Object) this);
    }

    /** Collections: whatever a player drops (Q, a closed menu, death) never counts toward a collection again. */
    @Inject(method = "drop(Lnet/minecraft/world/item/ItemStack;ZZ)Lnet/minecraft/world/entity/item/ItemEntity;", at = @At("RETURN"))
    private void crispy$dropped(ItemStack stack, boolean randomly, boolean thrower, CallbackInfoReturnable<ItemEntity> cir) {
        ItemCollections.markDropped(cir.getReturnValue());
    }

    @Inject(method = "canHarmPlayer", at = @At("HEAD"), cancellable = true)
    private void crispy$hubNoPvp(Player other, CallbackInfoReturnable<Boolean> cir) {
        if (ZoneRules.noPvp((ServerPlayer) (Object) this, other)) cir.setReturnValue(false);
    }
}

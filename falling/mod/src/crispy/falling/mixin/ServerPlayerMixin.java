package crispy.falling.mixin;

import crispy.falling.ZoneRules;
import net.minecraft.server.level.ServerPlayer;
import net.minecraft.world.damagesource.DamageSource;
import org.spongepowered.asm.mixin.Mixin;
import org.spongepowered.asm.mixin.injection.At;
import org.spongepowered.asm.mixin.injection.Inject;
import org.spongepowered.asm.mixin.injection.callback.CallbackInfo;

/** Dying in a resource zone: put aside everything not gathered there before the death drops (ZoneRules). */
@Mixin(ServerPlayer.class)
public abstract class ServerPlayerMixin {
    @Inject(method = "die", at = @At("HEAD"))
    private void crispy$zoneDeath(DamageSource source, CallbackInfo ci) {
        ZoneRules.onPlayerDeath((ServerPlayer) (Object) this);
    }
}

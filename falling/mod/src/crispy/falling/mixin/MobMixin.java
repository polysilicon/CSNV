package crispy.falling.mixin;

import crispy.falling.ZoneRules;
import net.minecraft.world.entity.Mob;
import org.spongepowered.asm.mixin.Mixin;
import org.spongepowered.asm.mixin.injection.At;
import org.spongepowered.asm.mixin.injection.Inject;
import org.spongepowered.asm.mixin.injection.callback.CallbackInfoReturnable;

/** Resource-zone mobs (tag cs_zone_mob) don't burn in daylight. */
@Mixin(Mob.class)
public abstract class MobMixin {
    @Inject(method = "isSunBurnTick", at = @At("HEAD"), cancellable = true)
    private void crispy$noSunBurn(CallbackInfoReturnable<Boolean> cir) {
        if (ZoneRules.isZoneMob((Mob) (Object) this)) cir.setReturnValue(false);
    }
}

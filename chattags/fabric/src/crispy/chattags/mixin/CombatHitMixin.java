package crispy.chattags.mixin;

import crispy.chattags.Combat;
import net.minecraft.server.level.ServerLevel;
import net.minecraft.server.level.ServerPlayer;
import net.minecraft.world.damagesource.DamageSource;
import net.minecraft.world.entity.LivingEntity;
import org.spongepowered.asm.mixin.Mixin;
import org.spongepowered.asm.mixin.injection.At;
import org.spongepowered.asm.mixin.injection.Inject;
import org.spongepowered.asm.mixin.injection.callback.CallbackInfoReturnable;

/** A player hurt by another player (melee, arrows, anything that credits them) puts both in combat. */
@Mixin(LivingEntity.class)
public abstract class CombatHitMixin {
    @Inject(method = "hurtServer", at = @At("RETURN"))
    private void crispy$combat(ServerLevel level, DamageSource source, float amount, CallbackInfoReturnable<Boolean> cir) {
        if (cir.getReturnValueZ() && (Object) this instanceof ServerPlayer victim && source.getEntity() instanceof ServerPlayer attacker && attacker != victim)
            Combat.hit(victim, attacker);
    }
}

package crispy.chattags.mixin;

import crispy.chattags.Combat;
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
    @Inject(method = "hurt", at = @At("RETURN"))   // 1.21.1: hurt(DamageSource, float); hurtServer came later
    private void crispy$combat(DamageSource source, float amount, CallbackInfoReturnable<Boolean> cir) {
        if (cir.getReturnValueZ() && (Object) this instanceof ServerPlayer victim && source.getEntity() instanceof ServerPlayer attacker && attacker != victim)
            Combat.hit(victim, attacker);
    }
}

package crispy.chattags.mixin;

import crispy.chattags.Gates;
import net.minecraft.server.level.ServerPlayer;
import net.minecraft.world.InteractionHand;
import net.minecraft.world.InteractionResult;
import net.minecraft.world.entity.Entity;
import net.minecraft.world.entity.player.Player;
import net.minecraft.world.phys.Vec3;
import org.spongepowered.asm.mixin.Mixin;
import org.spongepowered.asm.mixin.injection.At;
import org.spongepowered.asm.mixin.injection.Inject;
import org.spongepowered.asm.mixin.injection.callback.CallbackInfoReturnable;

/** Entities tagged needtag.<id> (a shop villager, say) only answer players wearing that cosmetic tag (Gates). */
@Mixin(Player.class)
public abstract class GateInteractMixin {
    @Inject(method = "interactOn", at = @At("HEAD"), cancellable = true)
    private void crispy$gate(Entity entity, InteractionHand hand, Vec3 at, CallbackInfoReturnable<InteractionResult> cir) {
        if ((Object) this instanceof ServerPlayer p && hand == InteractionHand.MAIN_HAND && !Gates.mayInteract(p, entity)) cir.setReturnValue(InteractionResult.FAIL);
        else if ((Object) this instanceof ServerPlayer p2 && hand == InteractionHand.OFF_HAND && entity.entityTags().stream().anyMatch(t -> t.startsWith("needtag.") && !Gates.wearing(p2, t.substring(8))))
            cir.setReturnValue(InteractionResult.FAIL);   // the off-hand try right after: refuse quietly
    }
}

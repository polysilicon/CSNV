package crispy.falling.mixin;

import crispy.falling.Realms;
import net.minecraft.core.BlockPos;
import net.minecraft.server.level.ServerLevel;
import net.minecraft.world.entity.Entity;
import net.minecraft.world.level.block.NetherPortalBlock;
import net.minecraft.world.level.portal.TeleportTransition;
import org.spongepowered.asm.mixin.Mixin;
import org.spongepowered.asm.mixin.injection.At;
import org.spongepowered.asm.mixin.injection.Inject;
import org.spongepowered.asm.mixin.injection.callback.CallbackInfoReturnable;

/** Visitors can't use a Nether portal on someone else's island (2.16.0). */
@Mixin(NetherPortalBlock.class)
public abstract class NetherPortalMixin {
    @Inject(method = "getPortalDestination", at = @At("HEAD"), cancellable = true)
    private void crispy$noVisitors(ServerLevel level, Entity entity, BlockPos pos, CallbackInfoReturnable<TeleportTransition> cir) {
        if (Realms.visitorBlocked(level, entity, pos, "Nether")) cir.setReturnValue(null);
    }
}

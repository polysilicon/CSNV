package crispy.falling.mixin;

import crispy.falling.Skills;
import net.minecraft.server.level.ServerPlayer;
import net.minecraft.world.InteractionResult;
import net.minecraft.world.item.BlockItem;
import net.minecraft.world.item.context.BlockPlaceContext;
import org.spongepowered.asm.mixin.Mixin;
import org.spongepowered.asm.mixin.injection.At;
import org.spongepowered.asm.mixin.injection.Inject;
import org.spongepowered.asm.mixin.injection.callback.CallbackInfoReturnable;

/** Remembers where players place blocks, so breaking them again gives no skill XP (Skills.Placed). */
@Mixin(BlockItem.class)
public abstract class BlockItemMixin {
    @Inject(method = "place", at = @At("RETURN"))
    private void crispy$placed(BlockPlaceContext ctx, CallbackInfoReturnable<InteractionResult> cir) {
        if (cir.getReturnValue().consumesAction() && ctx.getPlayer() instanceof ServerPlayer && !ctx.getLevel().isClientSide())
            Skills.Placed.add(ctx.getLevel(), ctx.getClickedPos());
    }
}

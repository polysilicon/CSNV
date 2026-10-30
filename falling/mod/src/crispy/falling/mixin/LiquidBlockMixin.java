package crispy.falling.mixin;

import crispy.falling.Upgrades;
import net.minecraft.core.BlockPos;
import net.minecraft.world.level.Level;
import net.minecraft.world.level.block.LiquidBlock;
import net.minecraft.world.level.block.state.BlockState;
import org.spongepowered.asm.mixin.Mixin;
import org.spongepowered.asm.mixin.injection.At;
import org.spongepowered.asm.mixin.injection.Redirect;

/** The ore generator island upgrade: cobblestone from lava meeting water may come out as an ore (Upgrades.generated). */
@Mixin(LiquidBlock.class)
public abstract class LiquidBlockMixin {
    @Redirect(method = "shouldSpreadLiquid", at = @At(value = "INVOKE",
            target = "Lnet/minecraft/world/level/Level;setBlockAndUpdate(Lnet/minecraft/core/BlockPos;Lnet/minecraft/world/level/block/state/BlockState;)Z"))
    private boolean crispy$oreGen(Level level, BlockPos pos, BlockState state) {
        return level.setBlockAndUpdate(pos, Upgrades.generated(level, pos, state));
    }
}

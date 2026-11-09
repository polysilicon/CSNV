package crispy.falling.mixin;

import crispy.falling.Compact;
import net.minecraft.server.level.ServerLevel;
import net.minecraft.world.item.crafting.CraftingInput;
import net.minecraft.world.item.crafting.CraftingRecipe;
import net.minecraft.world.item.crafting.RecipeHolder;
import net.minecraft.world.level.block.CrafterBlock;
import org.spongepowered.asm.mixin.Mixin;
import org.spongepowered.asm.mixin.injection.At;
import org.spongepowered.asm.mixin.injection.Inject;
import org.spongepowered.asm.mixin.injection.callback.CallbackInfoReturnable;

import java.util.Optional;

/** Crafters can't make gear that needs enchanted resources, nor use enchanted items in other recipes. */
@Mixin(CrafterBlock.class)
public abstract class CrafterBlockMixin {
    @Inject(method = "getPotentialResults", at = @At("RETURN"), cancellable = true)
    private static void crispy$enchanted(ServerLevel level, CraftingInput input, CallbackInfoReturnable<Optional<RecipeHolder<CraftingRecipe>>> cir) {
        var found = cir.getReturnValue();
        if (found == null || found.isEmpty()) return;
        boolean anyEnchanted = false;
        for (var s : input.items()) if (Compact.enchanted(s)) { anyEnchanted = true; break; }
        if (anyEnchanted || Compact.needsEnchanted(level.getServer(), found.get())) cir.setReturnValue(Optional.empty());
    }
}

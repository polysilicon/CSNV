package crispy.chattags.mixin;

import crispy.chattags.Censor;
import net.minecraft.world.inventory.AnvilMenu;
import org.spongepowered.asm.mixin.Mixin;
import org.spongepowered.asm.mixin.injection.At;
import org.spongepowered.asm.mixin.injection.ModifyVariable;

/** Anvil renames: listed slurs in the new item name are starred. */
@Mixin(AnvilMenu.class)
public abstract class CensorAnvilMixin {
    @ModifyVariable(method = "setItemName", at = @At("HEAD"), argsOnly = true)
    private String crispy$name(String name) { return Censor.apply(name); }
}

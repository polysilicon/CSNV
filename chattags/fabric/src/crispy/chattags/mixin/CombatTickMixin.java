package crispy.chattags.mixin;

import crispy.chattags.Combat;
import net.minecraft.server.MinecraftServer;
import org.spongepowered.asm.mixin.Mixin;
import org.spongepowered.asm.mixin.injection.At;
import org.spongepowered.asm.mixin.injection.Inject;
import org.spongepowered.asm.mixin.injection.callback.CallbackInfo;

import java.util.function.BooleanSupplier;

/** Once a second (Combat counts ticks): write the combat file for the proxy. */
@Mixin(MinecraftServer.class)
public abstract class CombatTickMixin {
    @Inject(method = "tickServer", at = @At("TAIL"))
    private void crispy$combatTick(BooleanSupplier hasTime, CallbackInfo ci) { Combat.tick((MinecraftServer) (Object) this); }
}

package crispy.chattags.mixin;

import com.mojang.brigadier.CommandDispatcher;
import crispy.chattags.RemoteMenu;
import net.minecraft.commands.CommandSourceStack;
import net.minecraft.commands.Commands;
import org.spongepowered.asm.mixin.Final;
import org.spongepowered.asm.mixin.Mixin;
import org.spongepowered.asm.mixin.Shadow;
import org.spongepowered.asm.mixin.injection.At;
import org.spongepowered.asm.mixin.injection.Inject;
import org.spongepowered.asm.mixin.injection.callback.CallbackInfo;

/** Registers /vote and /cosmetics (RemoteMenu) with the game's commands, without needing Fabric API. */
@Mixin(Commands.class)
public abstract class CommandsMixin {
    @Shadow @Final private CommandDispatcher<CommandSourceStack> dispatcher;

    @Inject(method = "<init>", at = @At("TAIL"))
    private void crispy$remoteMenus(CallbackInfo ci) { RemoteMenu.register(dispatcher); }
}

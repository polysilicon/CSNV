package crispy.chattags.mixin;

import crispy.chattags.Censor;
import net.minecraft.network.chat.Component;
import net.minecraft.server.MinecraftServer;
import org.spongepowered.asm.mixin.Mixin;
import org.spongepowered.asm.mixin.injection.At;
import org.spongepowered.asm.mixin.injection.ModifyVariable;

/** The chat line in the server log is starred too: the Discord bot's cross-server chat reads it from there. */
@Mixin(MinecraftServer.class)
public abstract class CensorLogMixin {
    @ModifyVariable(method = "logChatMessage", at = @At("HEAD"), argsOnly = true)
    private Component crispy$log(Component message) {
        String text = message.getString(), c = Censor.apply(text);
        return c == text ? message : Component.literal(c);
    }
}

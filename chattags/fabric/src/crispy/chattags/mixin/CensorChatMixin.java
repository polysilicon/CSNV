package crispy.chattags.mixin;

import crispy.chattags.Censor;
import net.minecraft.network.chat.ChatType;
import net.minecraft.network.chat.Component;
import net.minecraft.network.chat.OutgoingChatMessage;
import net.minecraft.network.chat.PlayerChatMessage;
import net.minecraft.server.level.ServerPlayer;
import org.spongepowered.asm.mixin.Mixin;
import org.spongepowered.asm.mixin.injection.At;
import org.spongepowered.asm.mixin.injection.ModifyVariable;

/** Every player message a client receives (/msg, /me, /teammsg, /say and anything the chat hooks missed): starred if
 *  it still contains a listed slur. Public chat is starred earlier (ChatNameMixin / Styled Chat hook) so it keeps its
 *  colours; this only flattens a message that slipped through. */
@Mixin(ServerPlayer.class)
public abstract class CensorChatMixin {
    @ModifyVariable(method = "sendChatMessage", at = @At("HEAD"), argsOnly = true)
    private OutgoingChatMessage crispy$outgoing(OutgoingChatMessage msg) {
        if (!(msg instanceof OutgoingChatMessage.Player p)) return msg;
        PlayerChatMessage m = p.message();
        String text = m.decoratedContent().getString(), c = Censor.apply(text);
        return c == text ? msg : new OutgoingChatMessage.Player(m.withUnsignedContent(Component.literal(c)));
    }
}

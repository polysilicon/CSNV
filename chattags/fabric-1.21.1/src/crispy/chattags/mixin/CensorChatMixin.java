package crispy.chattags.mixin;

import crispy.chattags.Censor;
import net.minecraft.network.chat.ChatType;
import net.minecraft.network.chat.Component;
import net.minecraft.network.chat.OutgoingChatMessage;
import net.minecraft.network.chat.PlayerChatMessage;
import net.minecraft.server.level.ServerPlayer;
import org.spongepowered.asm.mixin.Mixin;
import org.spongepowered.asm.mixin.injection.At;
import org.spongepowered.asm.mixin.injection.Inject;
import org.spongepowered.asm.mixin.injection.callback.CallbackInfo;

/** Every player message a client receives (public chat, /msg, /me, /teammsg, /say). If the signed original still
 *  contains a listed slur, the message goes out as a plain server message (formatted exactly like chat) instead of
 *  signed player chat: a signed message lets Java clients show the original text on hover ("modified by the server").
 *  Public chat was already starred and coloured earlier (ChatNameMixin / Styled Chat hook), so that shown text is
 *  kept; anything that slipped through is starred here. Same idea as No Chat Reports' convertToGameMessage. */
@Mixin(ServerPlayer.class)
public abstract class CensorChatMixin {
    @Inject(method = "sendChatMessage", at = @At("HEAD"), cancellable = true)
    private void crispy$outgoing(OutgoingChatMessage msg, boolean filtered, ChatType.Bound type, CallbackInfo ci) {
        if (!(msg instanceof OutgoingChatMessage.Player p)) return;
        PlayerChatMessage m = p.message();
        String body = m.signedContent(), shown = m.decoratedContent().getString();
        boolean bodyDirty = Censor.dirty(body), shownDirty = Censor.dirty(shown);
        if (!bodyDirty && !shownDirty) return;
        Component content = shownDirty ? Component.literal(Censor.apply(shown)) : m.decoratedContent();
        ((ServerPlayer) (Object) this).sendSystemMessage(type.decorate(content));
        ci.cancel();
    }
}

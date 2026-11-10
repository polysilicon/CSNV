package crispy.chattags.mixin;

import crispy.chattags.Censor;
import crispy.chattags.Tags;
import net.minecraft.network.chat.ChatType;
import net.minecraft.network.chat.Component;
import net.minecraft.network.chat.PlayerChatMessage;
import net.minecraft.resources.ResourceKey;
import net.minecraft.server.level.ServerPlayer;
import net.minecraft.server.network.ServerGamePacketListenerImpl;
import net.minecraft.world.entity.Entity;
import org.spongepowered.asm.mixin.Mixin;
import org.spongepowered.asm.mixin.Shadow;
import net.fabricmc.loader.api.FabricLoader;
import org.spongepowered.asm.mixin.injection.At;
import org.spongepowered.asm.mixin.injection.ModifyVariable;
import org.spongepowered.asm.mixin.injection.Redirect;

/** Player chat only: the sender name becomes "[Tag] name" (name in its bought colour) (also in the server log, which the Discord bot relays),
 *  and the message is shown in their chat colour. Join, leave and death messages keep the plain name. */
@Mixin(ServerGamePacketListenerImpl.class)
public abstract class ChatNameMixin {
    @Shadow public ServerPlayer player;

    /** The chat colour: the message's shown text (the signed text is kept). Styled Chat servers do this in ChatTags. */
    @ModifyVariable(method = "broadcastChatMessage", at = @At("HEAD"), argsOnly = true)
    private PlayerChatMessage crispy$chatColor(PlayerChatMessage message) {
        if (FabricLoader.getInstance().isModLoaded("styledchat")) return message;
        String text = message.signedContent(), clean = Censor.apply(text);   // slurs starred (Censor), then coloured
        String code = Tags.chatCode(player.getGameProfile().name(), clean);
        if (code == null) return clean == text ? message : message.withUnsignedContent(Component.literal(clean));
        return message.withUnsignedContent(Tags.colored(code, clean));
    }

    @Redirect(method = "broadcastChatMessage", at = @At(value = "INVOKE",
            target = "Lnet/minecraft/network/chat/ChatType;bind(Lnet/minecraft/resources/ResourceKey;Lnet/minecraft/world/entity/Entity;)Lnet/minecraft/network/chat/ChatType$Bound;"))
    private ChatType.Bound crispy$taggedName(ResourceKey<ChatType> type, Entity entity) {
        Component name = Tags.chatName(player.getGameProfile().name(), entity.getDisplayName());
        return name == null ? ChatType.bind(type, entity) : ChatType.bind(type, player.level().registryAccess(), name);
    }
}

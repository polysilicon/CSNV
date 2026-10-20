package crispy.chattags.mixin;

import crispy.chattags.Tags;
import net.minecraft.network.chat.ChatType;
import net.minecraft.network.chat.Component;
import net.minecraft.resources.ResourceKey;
import net.minecraft.server.level.ServerPlayer;
import net.minecraft.server.network.ServerGamePacketListenerImpl;
import net.minecraft.world.entity.Entity;
import org.spongepowered.asm.mixin.Mixin;
import org.spongepowered.asm.mixin.Shadow;
import org.spongepowered.asm.mixin.injection.At;
import org.spongepowered.asm.mixin.injection.Redirect;

/** Player chat only: the sender name becomes "[Tag] name" (also in the server log, which the Discord bot relays).
 *  Join, leave and death messages keep the plain name. */
@Mixin(ServerGamePacketListenerImpl.class)
public abstract class ChatNameMixin {
    @Shadow public ServerPlayer player;

    @Redirect(method = "broadcastChatMessage", at = @At(value = "INVOKE",
            target = "Lnet/minecraft/network/chat/ChatType;bind(Lnet/minecraft/resources/ResourceKey;Lnet/minecraft/world/entity/Entity;)Lnet/minecraft/network/chat/ChatType$Bound;"))
    private ChatType.Bound crispy$taggedName(ResourceKey<ChatType> type, Entity entity) {
        String tag = Tags.get(player.getGameProfile().name());
        if (tag == null) return ChatType.bind(type, entity);
        Component name = Tags.legacy(tag).append(Component.literal(" ")).append(entity.getDisplayName());
        return ChatType.bind(type, player.level().registryAccess(), name);
    }
}

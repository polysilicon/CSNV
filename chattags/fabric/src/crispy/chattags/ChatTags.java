package crispy.chattags;

import eu.pb4.placeholders.api.PlaceholderResult;
import eu.pb4.placeholders.api.Placeholders;
import net.fabricmc.api.ModInitializer;
import net.fabricmc.loader.api.FabricLoader;
import net.minecraft.network.chat.Component;
import net.minecraft.resources.Identifier;

/** On servers with Styled Chat (which formats chat itself, so the mixin never runs there), registers the Placeholder
 *  API placeholder %crispy:tag%: the sender's tag plus a space, or nothing. Use it in styled-chat.json, e.g.
 *  "chat": "<%crispy:tag%${player}> ${message}". */
public class ChatTags implements ModInitializer {
    @Override public void onInitialize() {
        if (FabricLoader.getInstance().isModLoaded("placeholder-api")) Placeholder.register();
    }

    static final class Placeholder {   // separate class: only loaded when Placeholder API is present
        static void register() {
            Placeholders.registerServer(Identifier.fromNamespaceAndPath("crispy", "tag"), (ctx, arg) -> {
                if (!ctx.hasServerPlayer()) return PlaceholderResult.value("");
                String tag = Tags.get(ctx.serverPlayer().getGameProfile().name());
                return tag == null ? PlaceholderResult.value("") : PlaceholderResult.value(Tags.legacy(tag).append(Component.literal(" ")));
            });
        }
    }
}

package crispy.chattags;

import eu.pb4.placeholders.api.PlaceholderResult;
import eu.pb4.placeholders.api.Placeholders;
import net.fabricmc.api.ModInitializer;
import net.fabricmc.loader.api.FabricLoader;
import net.minecraft.network.chat.Component;
import net.minecraft.resources.Identifier;

/** On servers with Styled Chat (which formats chat itself, so the mixin never runs there), registers the Placeholder
 *  API placeholders %crispy:tag% (the sender's tag plus a space, or nothing) and %crispy:name% (their name in its
 *  bought colour, or plain). In styled-chat.json: "chat": "<%crispy:tag%%crispy:name%> ${message}". */
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
            Placeholders.registerServer(Identifier.fromNamespaceAndPath("crispy", "name"), (ctx, arg) -> {
                if (!ctx.hasServerPlayer()) return PlaceholderResult.value("");
                var p = ctx.serverPlayer();
                Component c = Tags.coloredName(p.getGameProfile().name());
                return PlaceholderResult.value(c != null ? c : p.getDisplayName());
            });
        }
    }
}

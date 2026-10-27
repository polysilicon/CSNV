package crispy.chattags;

import eu.pb4.placeholders.api.PlaceholderContext;
import eu.pb4.placeholders.api.PlaceholderResult;
import eu.pb4.placeholders.api.Placeholders;
import eu.pb4.placeholders.api.node.TextNode;
import net.fabricmc.api.ModInitializer;
import net.fabricmc.loader.api.FabricLoader;
import net.minecraft.network.chat.Component;
import net.minecraft.resources.Identifier;

import java.lang.reflect.Proxy;

/** On servers with Styled Chat (which formats chat itself, so the mixin never runs there), registers the Placeholder
 *  API placeholders %crispy:tag% (the sender's tag plus a space, or nothing) and %crispy:name% (their name in its
 *  bought colour, or plain). In styled-chat.json: "chat": "<%crispy:tag%%crispy:name%> ${message}".
 *  Chat colours (chatcolors.json): with Styled Chat through its MESSAGE_CONTENT event, otherwise in ChatNameMixin. */
public class ChatTags implements ModInitializer {
    @Override public void onInitialize() {
        if (FabricLoader.getInstance().isModLoaded("placeholder-api")) Placeholder.register();
        if (FabricLoader.getInstance().isModLoaded("styledchat")) StyledChat.register();
    }

    /** Styled Chat isn't a compile dependency: its event is found by reflection. */
    static final class StyledChat {
        static void register() {
            try {
                Class<?> iface = Class.forName("eu.pb4.styledchat.StyledChatEvents$MessageEvent");
                Object event = Class.forName("eu.pb4.styledchat.StyledChatEvents").getField("MESSAGE_CONTENT").get(null);
                Object listener = Proxy.newProxyInstance(iface.getClassLoader(), new Class<?>[]{iface}, (proxy, m, args) -> {
                    if (m.getDeclaringClass() == Object.class) {
                        return switch (m.getName()) { case "hashCode" -> System.identityHashCode(proxy); case "equals" -> proxy == args[0]; default -> "crispy chat colours"; };
                    }
                    return recolor((TextNode) args[0], (PlaceholderContext) args[1]);
                });
                Class.forName("net.fabricmc.fabric.api.event.Event").getMethod("register", Object.class).invoke(event, listener);
            } catch (ReflectiveOperationException | RuntimeException e) {
                System.err.println("[crispy_chattags] couldn't hook Styled Chat for chat colours: " + e);
            }
        }

        static TextNode recolor(TextNode node, PlaceholderContext ctx) {
            if (ctx == null || !ctx.hasPlayer()) return node;
            String text = node.toComponent(ctx).getString();
            String code = Tags.chatCode(ctx.player().getGameProfile().name(), text);
            return code == null ? node : TextNode.convert(Tags.colored(code, text));
        }
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

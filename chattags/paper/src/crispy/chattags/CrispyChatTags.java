package crispy.chattags;

import com.google.gson.Gson;
import com.google.gson.reflect.TypeToken;
import io.papermc.paper.chat.ChatRenderer;
import io.papermc.paper.event.player.AsyncChatEvent;
import net.kyori.adventure.text.Component;
import net.kyori.adventure.text.TextReplacementConfig;
import net.kyori.adventure.text.serializer.legacy.LegacyComponentSerializer;
import org.bukkit.Bukkit;
import org.bukkit.event.EventHandler;
import org.bukkit.event.EventPriority;
import org.bukkit.event.Listener;
import org.bukkit.plugin.java.JavaPlugin;

import java.nio.file.Files;
import java.nio.file.Path;
import java.util.Locale;
import java.util.Map;

/** Shows vote-cosmetic tags (from the lobby's tags.json) before the sender's name in chat, for every viewer and the
 *  console, so the Discord bot's relay carries them too. Works over EssentialsChat: the finished line is rewritten. */
public class CrispyChatTags extends JavaPlugin implements Listener {
    static final LegacyComponentSerializer AMP = LegacyComponentSerializer.legacyAmpersand();
    volatile Map<String, String> tags = Map.of();
    long mtime = -1;
    Path file;

    @Override public void onEnable() {
        saveDefaultConfig();
        file = Path.of(getConfig().getString("tags-file", "/AMPStorage/.ampdata/instances/CrispyLobby01/Minecraft/plugins/CrispyLobby/tags.json"));
        getServer().getPluginManager().registerEvents(this, this);
        Bukkit.getScheduler().runTaskTimerAsynchronously(this, this::reload, 20L, 60L);
    }

    void reload() {
        try {
            long m = Files.getLastModifiedTime(file).toMillis();
            if (m == mtime) return;
            Map<String, String> t = new Gson().fromJson(Files.readString(file), new TypeToken<Map<String, String>>() {}.getType());
            tags = t == null ? Map.of() : t;
            mtime = m;
        } catch (Exception ignored) {}
    }

    @EventHandler(priority = EventPriority.HIGHEST, ignoreCancelled = true)
    public void onChat(AsyncChatEvent e) {
        String tag = tags.get(e.getPlayer().getName().toLowerCase(Locale.ROOT));
        if (tag == null) return;
        Component tagC = AMP.deserialize(tag);
        String name = e.getPlayer().getName();
        ChatRenderer inner = e.renderer();
        e.renderer((source, displayName, message, viewer) -> {
            Component line = inner.render(source, displayName, message, viewer);
            boolean[] hit = {false};
            Component out = line.replaceText(TextReplacementConfig.builder().matchLiteral(name).once()
                    .replacement(b -> { hit[0] = true; return tagC.append(Component.text(" ")).append(b); }).build());
            return hit[0] ? out : tagC.append(Component.text(" ")).append(line);
        });
    }
}

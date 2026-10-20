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
 *  console, so the Discord bot's relay carries them too. The tag goes into the player's display name while the message
 *  is sent (that name is what clients show for signed chat, and what EssentialsChat's {DISPLAYNAME} uses), and is put
 *  back a moment later so join/quit/death messages stay plain. A renderer pass adds it if a chat format left it out. */
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

    final Map<java.util.UUID, Component> original = new java.util.concurrent.ConcurrentHashMap<>();
    final Map<java.util.UUID, Integer> pending = new java.util.concurrent.ConcurrentHashMap<>();

    @EventHandler(priority = EventPriority.LOWEST, ignoreCancelled = true)
    public void tagName(AsyncChatEvent e) {
        org.bukkit.entity.Player p = e.getPlayer();
        String tag = tags.get(p.getName().toLowerCase(Locale.ROOT));
        if (tag == null) return;
        original.putIfAbsent(p.getUniqueId(), p.displayName());
        p.displayName(AMP.deserialize(tag).append(Component.text(" ")).append(original.get(p.getUniqueId())));
        int n = pending.merge(p.getUniqueId(), 1, Integer::sum);
        Bukkit.getScheduler().runTaskLater(this, () -> {   // restore once the last message in flight has gone out
            if (pending.getOrDefault(p.getUniqueId(), 0) != n) return;
            pending.remove(p.getUniqueId());
            Component o = original.remove(p.getUniqueId());
            if (o != null && p.isOnline()) p.displayName(o);
        }, 40L);
    }

    @EventHandler public void onQuit(org.bukkit.event.player.PlayerQuitEvent e) {
        Component o = original.remove(e.getPlayer().getUniqueId());
        pending.remove(e.getPlayer().getUniqueId());
        if (o != null) e.getPlayer().displayName(o);
    }

    @EventHandler(priority = EventPriority.HIGHEST, ignoreCancelled = true)
    public void onChat(AsyncChatEvent e) {
        String tag = tags.get(e.getPlayer().getName().toLowerCase(Locale.ROOT));
        if (tag == null) return;
        Component tagC = AMP.deserialize(tag);
        String tagText = net.kyori.adventure.text.serializer.plain.PlainTextComponentSerializer.plainText().serialize(tagC);
        String name = e.getPlayer().getName();
        ChatRenderer inner = e.renderer();
        e.renderer((source, displayName, message, viewer) -> {
            Component line = inner.render(source, displayName, message, viewer);
            if (net.kyori.adventure.text.serializer.plain.PlainTextComponentSerializer.plainText().serialize(line).contains(tagText)) return line;
            boolean[] hit = {false};
            Component out = line.replaceText(TextReplacementConfig.builder().matchLiteral(name).once()
                    .replacement(b -> { hit[0] = true; return tagC.append(Component.text(" ")).append(b); }).build());
            return hit[0] ? out : tagC.append(Component.text(" ")).append(line);
        });
    }
}

package crispy.chattags;

import com.google.gson.Gson;
import com.google.gson.reflect.TypeToken;
import io.papermc.paper.chat.ChatRenderer;
import io.papermc.paper.event.player.AsyncChatEvent;
import net.kyori.adventure.audience.Audience;
import net.kyori.adventure.text.Component;
import net.kyori.adventure.text.TextReplacementConfig;
import net.kyori.adventure.text.format.Style;
import net.kyori.adventure.text.format.TextColor;
import net.kyori.adventure.text.format.TextDecoration;
import net.kyori.adventure.text.serializer.legacy.LegacyComponentSerializer;
import net.kyori.adventure.text.serializer.legacy.LegacyFormat;
import net.kyori.adventure.text.serializer.plain.PlainTextComponentSerializer;
import org.bukkit.Bukkit;
import org.bukkit.entity.Player;
import org.bukkit.event.EventHandler;
import org.bukkit.event.EventPriority;
import org.bukkit.event.Listener;
import org.bukkit.event.player.PlayerQuitEvent;
import org.bukkit.plugin.java.JavaPlugin;

import java.nio.file.Files;
import java.nio.file.Path;
import java.util.*;
import java.util.concurrent.ConcurrentHashMap;

/** Shows the lobby's vote cosmetics in chat: the tag (tags.json) before the sender's name and the name in its bought
 *  colour (namecolors.json), for every viewer and the console, so the Discord bot's relay carries the tag too.
 *  The message itself is shown in the sender's chat colour (chatcolors.json), unless it has a link.
 *  - The tagged name goes into the player's display name while the message is sent (what clients show for signed chat
 *    and what EssentialsChat's {DISPLAYNAME} uses), and is put back 2 s later so join/quit/death messages stay plain.
 *  - The finished line is rewritten if a format left the tag out or the colour off the message (EssentialsChat).
 *  - The old AsyncPlayerChatEvent is tagged too, for plugins that format chat there (SaberFactions).
 *  - system-chat: true sends tagged lines as plain server messages instead of signed chat, for servers where version
 *    translation shows clients the original signed message (Factions, 1.21.11 under ViaVersion). */
public class CrispyChatTags extends JavaPlugin implements Listener {
    static final LegacyComponentSerializer AMP = LegacyComponentSerializer.legacyAmpersand();
    static final PlainTextComponentSerializer PLAIN = PlainTextComponentSerializer.plainText();

    static final class Source {
        final Path file; volatile Map<String, String> map = Map.of(); long mtime = -1;
        Source(Path file) { this.file = file; }
        void reload() {
            try {
                long m = Files.getLastModifiedTime(file).toMillis();
                if (m == mtime) return;
                Map<String, String> t = new Gson().fromJson(Files.readString(file), new TypeToken<Map<String, String>>() {}.getType());
                map = t == null ? Map.of() : t;
                mtime = m;
            } catch (Exception ignored) {}
        }
        String get(String name) { return map.get(name.toLowerCase(Locale.ROOT)); }
    }

    Source tags, colors, chat;
    boolean systemChat;
    final Map<UUID, Component> original = new ConcurrentHashMap<>();
    final Map<UUID, Integer> pending = new ConcurrentHashMap<>();

    @Override public void onEnable() {
        saveDefaultConfig();
        Path dir = Path.of(getConfig().getString("lobby-dir", "/AMPStorage/.ampdata/instances/CrispyLobby01/Minecraft/plugins/CrispyLobby"));
        tags = new Source(dir.resolve("tags.json"));
        colors = new Source(dir.resolve("namecolors.json"));
        chat = new Source(dir.resolve("chatcolors.json"));
        systemChat = getConfig().getBoolean("system-chat", false);
        getServer().getPluginManager().registerEvents(this, this);
        Bukkit.getScheduler().runTaskTimerAsynchronously(this, () -> { tags.reload(); colors.reload(); chat.reload(); }, 20L, 60L);
    }

    /** The sender's chat colour code, or null (none, or the message has a link). */
    String chatCode(String name, String text) {
        String code = chat.get(name);
        return code == null || text.contains("http://") || text.contains("https://") ? null : code;
    }
    /** "&6&l" or "&#ff8800&l" -> that style. */
    static Style style(String code) {
        Style st = Style.empty();
        for (int i = 0; i + 1 < code.length(); i++) {
            if (code.charAt(i) != '&' && code.charAt(i) != '\u00a7') continue;
            if (code.charAt(i + 1) == '#' && i + 8 <= code.length()) {   // &#rrggbb (fades and flags)
                try { st = Style.style(TextColor.color(Integer.parseInt(code.substring(i + 2, i + 8), 16))); } catch (NumberFormatException ignored) {}
                i += 7;
                continue;
            }
            LegacyFormat f = LegacyComponentSerializer.parseChar(code.charAt(++i));
            if (f == null) continue;
            if (f.reset()) st = Style.empty();
            else if (f.color() != null) st = Style.style(f.color());
            else if (f.decoration() != null) st = st.decoration(f.decoration(), TextDecoration.State.TRUE);
        }
        return st;
    }
    /** The text, always literal (& codes typed in chat are not formatting), in a colour code (see ColorCodes: one style,
     *  a per-letter cycle, "rainbow", a fade or flag bands). */
    static Component colored(String code, String text) {
        if (!ColorCodes.perLetter(code)) return Component.text(text, style(code));
        String[] l = ColorCodes.letters(code, text);
        Component out = Component.empty();
        for (int i = 0; i < text.length(); i++) {
            String ch = String.valueOf(text.charAt(i));
            out = out.append(l[i] == null ? Component.text(ch) : Component.text(ch, style(l[i])));
        }
        return out;
    }
    /** The same with section codes, for the old chat event (SaberFactions builds its lines from that message). A hex
     *  colour becomes Spigot's \u00a7x\u00a7r\u00a7r\u00a7g\u00a7g\u00a7b\u00a7b. */
    static String legacyColored(String code, String text) {
        text = text.replace("\u00a7", "");   // only the cosmetic's codes are converted: & codes the player typed stay literal
        if (!ColorCodes.perLetter(code)) return section(code) + text;
        String[] l = ColorCodes.letters(code, text);
        StringBuilder b = new StringBuilder();
        for (int i = 0; i < text.length(); i++) b.append(l[i] == null ? "" : section(l[i])).append(text.charAt(i));
        return b.toString();
    }
    /** "&#ff8800&l" -> section codes. */
    static String section(String amp) {
        StringBuilder b = new StringBuilder();
        for (int i = 0; i < amp.length(); i++) {
            char c = amp.charAt(i);
            if (c == '&' && i + 7 < amp.length() && amp.charAt(i + 1) == '#') {
                b.append("\u00a7x");
                for (int k = i + 2; k < i + 8; k++) b.append('\u00a7').append(amp.charAt(k));
                i += 7;
            } else if (c == '&' && i + 1 < amp.length() && "0123456789abcdefklmnorABCDEFKLMNOR".indexOf(amp.charAt(i + 1)) >= 0) b.append('\u00a7');
            else b.append(c);
        }
        return b.toString();
    }

    Component coloredName(String name) {
        String code = colors.get(name);
        return code == null ? null : colored(code, name);
    }
    /** "[Tag] " + coloured name (or the given name component), or null when the player has neither cosmetic. */
    Component chatName(String name, Component plain) {
        String tag = tags.get(name);
        Component col = coloredName(name);
        if (tag == null && col == null) return null;
        return (tag == null ? Component.empty() : AMP.deserialize(tag).append(Component.text(" "))).append(col != null ? col : plain);
    }

    // Plugins on the old chat event (SaberFactions builds and sends every line itself to relation-colour names) run
    // before AsyncChatEvent, so the name has to be tagged there too.
    @SuppressWarnings("deprecation")
    @EventHandler(priority = EventPriority.LOWEST, ignoreCancelled = true)
    public void tagNameLegacy(org.bukkit.event.player.AsyncPlayerChatEvent e) {
        tagName(e.getPlayer());
        String code = chatCode(e.getPlayer().getName(), e.getMessage());
        if (code != null) e.setMessage(legacyColored(code, e.getMessage()));
    }

    @EventHandler(priority = EventPriority.LOWEST, ignoreCancelled = true)
    public void tagName(AsyncChatEvent e) { tagName(e.getPlayer()); }

    void tagName(Player p) {
        original.putIfAbsent(p.getUniqueId(), p.displayName());
        Component tagged = chatName(p.getName(), original.get(p.getUniqueId()));
        if (tagged == null) { original.remove(p.getUniqueId()); return; }
        p.displayName(tagged);
        int n = pending.merge(p.getUniqueId(), 1, Integer::sum);
        Bukkit.getScheduler().runTaskLater(this, () -> {   // restore once the last message in flight has gone out
            if (pending.getOrDefault(p.getUniqueId(), 0) != n) return;
            pending.remove(p.getUniqueId());
            Component o = original.remove(p.getUniqueId());
            if (o != null && p.isOnline()) p.displayName(o);
        }, 40L);
    }

    @EventHandler public void onQuit(PlayerQuitEvent e) {
        Component o = original.remove(e.getPlayer().getUniqueId());
        pending.remove(e.getPlayer().getUniqueId());
        if (o != null) e.getPlayer().displayName(o);
    }

    /** EssentialsChat renders its own copy of the message text and ignores the event's message, so put the coloured
     *  message in place of the last plain copy of it in the finished line (the last, so a message that matches the
     *  sender's name doesn't colour the name). A format that already used the coloured message has no plain copy left
     *  for a sequence colour, and swapping a one-colour copy for itself changes nothing. */
    static Component recolor(Component line, String text, Component msgColored) {
        int[] count = {0};
        line.replaceText(TextReplacementConfig.builder().matchLiteral(text).replacement(b -> { count[0]++; return b; }).build());
        if (count[0] == 0) return line;
        int last = count[0];
        return line.replaceText(TextReplacementConfig.builder().matchLiteral(text)
                .condition((result, n, replaced) -> n == last ? net.kyori.adventure.text.PatternReplacementResult.REPLACE
                        : net.kyori.adventure.text.PatternReplacementResult.CONTINUE)
                .replacement(b -> msgColored).build());
    }

    @EventHandler(priority = EventPriority.HIGHEST, ignoreCancelled = true)
    public void onChat(AsyncChatEvent e) {
        String name = e.getPlayer().getName();
        String text = PLAIN.serialize(e.message()), code = chatCode(name, text);
        Component msgColored = code == null || text.isBlank() ? null : colored(code, text);
        if (msgColored != null) e.message(msgColored);
        Component tagged = chatName(name, Component.text(name));
        if (tagged == null && msgColored == null) return;
        String taggedText = tagged == null ? null : PLAIN.serialize(tagged);
        ChatRenderer inner = e.renderer();
        ChatRenderer r = (source, displayName, message, viewer) -> {
            Component line = inner.render(source, displayName, message, viewer);
            if (msgColored != null) line = recolor(line, text, msgColored);
            if (tagged == null || PLAIN.serialize(line).contains(taggedText)) return line;   // the format already used the tagged display name
            boolean[] hit = {false};
            Component out = line.replaceText(TextReplacementConfig.builder().matchLiteral(name).once()
                    .replacement(b -> { hit[0] = true; return tagged; }).build());
            return hit[0] ? out : tagged.append(Component.text(" ")).append(line);
        };
        if (!systemChat) { e.renderer(r); return; }
        Set<Audience> viewers = new HashSet<>(e.viewers());
        Player src = e.getPlayer();
        Component dn = src.displayName(), msg = e.message();
        e.setCancelled(true);
        for (Audience v : viewers) v.sendMessage(r.render(src, dn, msg, v));
    }
}

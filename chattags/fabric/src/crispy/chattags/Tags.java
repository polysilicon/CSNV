package crispy.chattags;

import com.google.gson.Gson;
import com.google.gson.reflect.TypeToken;
import net.minecraft.ChatFormatting;
import net.minecraft.network.chat.Component;
import net.minecraft.network.chat.MutableComponent;
import net.minecraft.network.chat.Style;
import net.minecraft.network.chat.TextColor;

import java.nio.file.Files;
import java.nio.file.Path;
import java.util.Locale;
import java.util.Map;

/** Vote cosmetics from the lobby: tags.json (name -> "&a[Voter]"), namecolors.json and chatcolors.json (name -> "&b",
 *  a sequence "&c|&6|&e", "rainbow", a fade or flag bands, see ColorCodes; the third colours the message text), each re-read when the file changes. */
public final class Tags {
    static final Path DIR = Path.of(System.getProperty("crispytags.dir", "/AMPStorage/.ampdata/instances/CrispyLobby01/Minecraft/plugins/CrispyLobby"));
    static final Source TAGS = new Source(DIR.resolve("tags.json")), COLORS = new Source(DIR.resolve("namecolors.json")),
            CHAT = new Source(DIR.resolve("chatcolors.json"));

    static final class Source {
        final Path file; volatile Map<String, String> map = Map.of(); long mtime = -1, checked;
        Source(Path file) { this.file = file; }
        String get(String name) {
            long now = System.currentTimeMillis();
            if (now - checked > 3000) {   // at most one stat every 3 s
                checked = now;
                try {
                    long m = Files.getLastModifiedTime(file).toMillis();
                    if (m != mtime) {
                        Map<String, String> t = new Gson().fromJson(Files.readString(file), new TypeToken<Map<String, String>>() {}.getType());
                        map = t == null ? Map.of() : t;
                        mtime = m;
                    }
                } catch (Exception ignored) {}
            }
            return map.get(name.toLowerCase(Locale.ROOT));
        }
    }

    public static String get(String name) { return TAGS.get(name); }

    /** The name in the player's bought colour, or null if they have none. */
    public static MutableComponent coloredName(String name) {
        String code = COLORS.get(name);
        return code == null ? null : colored(code, name);
    }

    /** The player's chat colour code, or null if they have none. Messages with a link keep their own formatting. */
    public static String chatCode(String name, String message) {
        String code = CHAT.get(name);
        return code == null || message.contains("http://") || message.contains("https://") ? null : code;
    }

    /** text in a colour code (see ColorCodes: "&b", "&6&l", "&#ff8800", a per-letter sequence "&c|&6|&e", "rainbow",
     *  a fade "a>b>c" or flag bands "a/b/c"). The text is always literal: & codes typed in chat are not formatting. */
    public static MutableComponent colored(String code, String text) {
        if (!ColorCodes.perLetter(code)) return Component.literal(text).setStyle(style(code));
        String[] l = ColorCodes.letters(code, text);
        MutableComponent out = Component.empty();
        for (int i = 0; i < text.length(); i++) {
            String ch = String.valueOf(text.charAt(i));
            out.append(l[i] == null ? Component.literal(ch) : Component.literal(ch).setStyle(style(l[i])));
        }
        return out;
    }

    /** "&6&l" -> that style. */
    static Style style(String code) {
        Style st = Style.EMPTY;
        for (int i = 0; i + 1 < code.length(); i++) {
            if (code.charAt(i) != '&' && code.charAt(i) != '\u00a7') continue;
            if (code.charAt(i + 1) == '#' && i + 8 <= code.length()) {   // &#rrggbb (fades and flags)
                try { st = Style.EMPTY.withColor(TextColor.fromRgb(Integer.parseInt(code.substring(i + 2, i + 8), 16))); } catch (NumberFormatException ignored) {}
                i += 7;
                continue;
            }
            ChatFormatting f = ChatFormatting.getByCode(code.charAt(i + 1));
            char c = Character.toLowerCase(code.charAt(i + 1));
            boolean color = (c >= '0' && c <= '9') || (c >= 'a' && c <= 'f');
            if (f != null) st = f == ChatFormatting.RESET ? Style.EMPTY : color ? Style.EMPTY.applyFormat(f) : st.applyFormat(f);
            i++;
        }
        return st;
    }

    /** "[Tag] " + coloured name (or the display name), or null when the player has neither cosmetic. */
    public static Component chatName(String name, Component displayName) {
        String tag = get(name);
        MutableComponent col = coloredName(name);
        if (tag == null && col == null) return null;
        MutableComponent out = Component.empty();
        if (tag != null) out.append(legacy(tag)).append(Component.literal(" "));
        return out.append(col != null ? col : displayName);
    }

    /** "&a[Voter]" -> a coloured component (&0-&f, &k-&o, &r). */
    public static MutableComponent legacy(String s) {
        MutableComponent out = Component.empty();
        Style style = Style.EMPTY;
        StringBuilder run = new StringBuilder();
        for (int i = 0; i < s.length(); i++) {
            char c = s.charAt(i);
            ChatFormatting f = (c == '&' || c == '§') && i + 1 < s.length() ? ChatFormatting.getByCode(s.charAt(i + 1)) : null;
            if (f == null) { run.append(c); continue; }
            if (!run.isEmpty()) { out.append(Component.literal(run.toString()).setStyle(style)); run.setLength(0); }
            char code = Character.toLowerCase(s.charAt(i + 1));
            boolean color = (code >= '0' && code <= '9') || (code >= 'a' && code <= 'f');
            style = f == ChatFormatting.RESET ? Style.EMPTY : color ? Style.EMPTY.applyFormat(f) : style.applyFormat(f);
            i++;
        }
        if (!run.isEmpty()) out.append(Component.literal(run.toString()).setStyle(style));
        return out;
    }
}

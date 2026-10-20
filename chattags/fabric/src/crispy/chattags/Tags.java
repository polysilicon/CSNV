package crispy.chattags;

import com.google.gson.Gson;
import com.google.gson.reflect.TypeToken;
import net.minecraft.ChatFormatting;
import net.minecraft.network.chat.Component;
import net.minecraft.network.chat.MutableComponent;
import net.minecraft.network.chat.Style;

import java.nio.file.Files;
import java.nio.file.Path;
import java.util.Locale;
import java.util.Map;

/** Vote cosmetics from the lobby: tags.json (name -> "&a[Voter]") and namecolors.json (name -> "&b" or "rainbow"),
 *  each re-read when the file changes. */
public final class Tags {
    static final Path DIR = Path.of(System.getProperty("crispytags.dir", "/AMPStorage/.ampdata/instances/CrispyLobby01/Minecraft/plugins/CrispyLobby"));
    static final Source TAGS = new Source(DIR.resolve("tags.json")), COLORS = new Source(DIR.resolve("namecolors.json"));
    static final ChatFormatting[] RAINBOW = {ChatFormatting.RED, ChatFormatting.GOLD, ChatFormatting.YELLOW, ChatFormatting.GREEN,
            ChatFormatting.AQUA, ChatFormatting.BLUE, ChatFormatting.LIGHT_PURPLE};

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
        if (code == null) return null;
        if (!code.equalsIgnoreCase("rainbow")) return legacy(code + name);
        MutableComponent out = Component.empty();
        for (int i = 0; i < name.length(); i++) out.append(Component.literal(String.valueOf(name.charAt(i))).withStyle(RAINBOW[i % RAINBOW.length]));
        return out;
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

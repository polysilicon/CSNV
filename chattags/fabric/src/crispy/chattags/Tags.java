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

/** Vote-cosmetic tags (name -> "&a[Voter]") from the lobby's tags.json, re-read when the file changes. */
public final class Tags {
    static final Path FILE = Path.of(System.getProperty("crispytags.file",
            "/AMPStorage/.ampdata/instances/CrispyLobby01/Minecraft/plugins/CrispyLobby/tags.json"));
    private static volatile Map<String, String> tags = Map.of();
    private static long mtime = -1, checked;

    public static String get(String name) {
        long now = System.currentTimeMillis();
        if (now - checked > 3000) {   // at most one stat every 3 s
            checked = now;
            try {
                long m = Files.getLastModifiedTime(FILE).toMillis();
                if (m != mtime) {
                    Map<String, String> t = new Gson().fromJson(Files.readString(FILE), new TypeToken<Map<String, String>>() {}.getType());
                    tags = t == null ? Map.of() : t;
                    mtime = m;
                }
            } catch (Exception ignored) {}
        }
        return tags.get(name.toLowerCase(Locale.ROOT));
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

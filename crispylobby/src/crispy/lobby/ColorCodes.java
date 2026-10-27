package crispy.lobby;

import java.util.regex.Pattern;

/** Cosmetic colour codes (name and chat colours). The same file is in the lobby, both chat-tags builds and the proxy
 *  plugin, and the Discord bot has a Python port (cosmetics.py), so a code looks the same everywhere:
 *  - "&b", "&6&l", "&#ff8800": one style for the whole text
 *  - "a|b|c": the codes cycle letter by letter ("rainbow" is "&c|&6|&e|&a|&b|&9|&d")
 *  - "a>b>c": a smooth fade across the whole text, through each stop's colour; formats (&l, &o...) come from the first stop
 *  - "a/b/c": the text is split into equal bands, like a flag
 *  Spaces don't use up a colour. */
final class ColorCodes {
    private ColorCodes() {}

    static final String RAINBOW = "&c|&6|&e|&a|&b|&9|&d";
    private static final int[] LEGACY = {0x000000, 0x0000AA, 0x00AA00, 0x00AAAA, 0xAA0000, 0xAA00AA, 0xFFAA00, 0xAAAAAA,
            0x555555, 0x5555FF, 0x55FF55, 0x55FFFF, 0xFF5555, 0xFF55FF, 0xFFFF55, 0xFFFFFF};

    static String expand(String code) { return code.equalsIgnoreCase("rainbow") ? RAINBOW : code; }

    /** True when the code styles each letter on its own (a cycle, fade or bands). */
    static boolean perLetter(String code) {
        code = expand(code);
        return code.contains("|") || code.contains(">") || code.contains("/");
    }

    /** "fades", "flags" or "classic": which page of the colour menus the code belongs on. */
    static String page(String code) { return code.contains(">") ? "fades" : code.contains("/") ? "flags" : "classic"; }

    /** One plain code ("&#rrggbb&l", "&c") per character of text, null for spaces. Only for perLetter codes. */
    static String[] letters(String code, String text) {
        code = expand(code);
        char sep = code.contains(">") ? '>' : code.contains("/") ? '/' : '|';
        String[] stops = code.split(Pattern.quote(String.valueOf(sep)));
        String fmt = sep == '>' ? formats(stops[0]) : "";
        int n = 0;
        for (int i = 0; i < text.length(); i++) if (!Character.isWhitespace(text.charAt(i))) n++;
        String[] out = new String[text.length()];
        for (int i = 0, j = 0; i < text.length(); i++) {
            if (Character.isWhitespace(text.charAt(i))) continue;
            out[i] = switch (sep) {
                case '>' -> fade(stops, n <= 1 ? 0 : (double) j / (n - 1)) + fmt;
                case '/' -> stops[Math.min(stops.length - 1, j * stops.length / n)];
                default -> stops[j % stops.length];
            };
            j++;
        }
        return out;
    }

    /** The colour t (0..1) of the way through the stops, as "&#rrggbb". */
    static String fade(String[] stops, double t) {
        if (stops.length == 1) return String.format("&#%06x", rgb(stops[0]));
        double pos = t * (stops.length - 1);
        int seg = Math.min((int) pos, stops.length - 2);
        double f = pos - seg;
        int a = rgb(stops[seg]), b = rgb(stops[seg + 1]), out = 0;
        for (int shift = 16; shift >= 0; shift -= 8) {
            int x = a >> shift & 255, y = b >> shift & 255;
            out |= (int) Math.round(x + (y - x) * f) << shift;
        }
        return String.format("&#%06x", out);
    }

    /** The colour of a code: its last "&#rrggbb" or "&0".."&f" (white if it has none). */
    static int rgb(String code) {
        int col = 0xFFFFFF;
        for (int i = 0; i + 1 < code.length(); i++) {
            if (code.charAt(i) != '&' && code.charAt(i) != '§') continue;
            char c = Character.toLowerCase(code.charAt(i + 1));
            if (c == '#' && i + 8 <= code.length()) {
                try { col = Integer.parseInt(code.substring(i + 2, i + 8), 16); i += 7; } catch (NumberFormatException ignored) {}
            } else if (Character.digit(c, 16) >= 0) col = LEGACY[Character.digit(c, 16)];
        }
        return col;
    }

    /** Just the format codes (&l &o &n &m) of a code. */
    static String formats(String code) {
        StringBuilder b = new StringBuilder();
        for (int i = 0; i + 1 < code.length(); i++)
            if ((code.charAt(i) == '&' || code.charAt(i) == '§') && "lonmLONM".indexOf(code.charAt(i + 1)) >= 0)
                b.append('&').append(Character.toLowerCase(code.charAt(++i)));
        return b.toString();
    }

    /** The text with & codes before each letter ("&#ff0000H&#ee1100i" for a fade), for menus and TAB. */
    static String legacy(String code, String text) {
        if (!perLetter(code)) return code + text;
        String[] l = letters(code, text);
        StringBuilder b = new StringBuilder();
        for (int i = 0; i < text.length(); i++) b.append(l[i] == null ? "" : l[i]).append(text.charAt(i));
        return b.toString();
    }
}

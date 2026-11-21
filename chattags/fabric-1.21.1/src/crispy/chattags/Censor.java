package crispy.chattags;

import java.nio.file.Files;
import java.nio.file.Path;
import java.util.ArrayList;
import java.util.List;
import java.util.regex.Matcher;
import java.util.regex.Pattern;

/**
 * Slur filter: replaces listed words with stars. A Java copy of the Discord bot's censor.py (same word list file,
 * same matching), so chat in game and the Discord relay star exactly the same things. Shared by the Fabric mod and
 * the Paper plugin: keep both copies identical.
 *
 * Word list: one entry per line ("#" comments). "word" matches the whole word plus simple endings (s, es, z, ed, ing,
 * y, ies); "=word" matches only the word itself or its plural (for short slurs whose endings make real words:
 * spicy, tardy); "stem*" matches any word starting with the stem; entries with spaces match with or without them. Matching
 * sees through leetspeak (n1gg3r), repeated letters (niiigger) and junk between letters (n.i.g.g.e.r) but never
 * inside a longer word (raccoon, Scunthorpe). The file is re-read when it changes (checked at most every 5 s).
 * Path: -Dcrispy.censor=..., default the bot's /opt/crispybot/censor_words.txt. Missing file = no filtering.
 */
public final class Censor {
    private Censor() {}

    static final Path FILE = Path.of(System.getProperty("crispy.censor", "/opt/crispybot/censor_words.txt"));
    private static final String LEET_FROM = "01!|34@5$7+8962";   // same table as censor.py's LEET
    private static final String LEET_TO   = "oiiieaassttbggz";
    private static final String SEP = "[\\W_]*";

    private static volatile Pattern rx;
    private static long mtime = Long.MIN_VALUE, checked;

    static char norm(char c) {
        c = Character.toLowerCase(c);
        int i = LEET_FROM.indexOf(c);
        return i < 0 ? c : LEET_TO.charAt(i);
    }

    private static synchronized void load() {
        long now = System.currentTimeMillis();
        if (now - checked < 5000 && mtime != Long.MIN_VALUE) return;
        checked = now;
        try {
            long m = Files.exists(FILE) ? Files.getLastModifiedTime(FILE).toMillis() : -1;
            if (m == mtime) return;
            mtime = m;
            if (m < 0) { rx = null; return; }
            List<String> parts = new ArrayList<>();
            for (String line : Files.readAllLines(FILE)) {
                int h = line.indexOf('#');
                String w = (h >= 0 ? line.substring(0, h) : line).strip().toLowerCase();
                if (w.isEmpty()) continue;
                boolean exact = w.startsWith("=");   // censor.py ignores the "=", so the list stays valid for the bot
                if (exact) w = w.substring(1).strip();
                boolean prefix = w.endsWith("*");
                while (w.endsWith("*")) w = w.substring(0, w.length() - 1);
                List<String> letters = new ArrayList<>();
                for (char c : w.toCharArray()) {
                    c = norm(c);
                    if (Character.isLetterOrDigit(c)) letters.add(Pattern.quote(String.valueOf(c)) + "+");
                }
                if (letters.isEmpty()) continue;
                parts.add(String.join(SEP, letters) + (prefix ? "[a-z]*" : exact ? "s?" : "(?:s|es|z|ed|ing|y|ies)?"));
            }
            rx = parts.isEmpty() ? null
                    : Pattern.compile("(?<![a-z])(?:" + String.join("|", parts) + ")(?![a-z])", Pattern.UNICODE_CHARACTER_CLASS);
        } catch (Exception e) {
            System.err.println("[crispy censor] can't read " + FILE + ": " + e);
        }
    }

    /** The text with every listed word replaced by stars (at least 3), or the same String object if nothing matched. */
    public static String apply(String text) {
        if (text == null || text.isEmpty()) return text;
        load();
        Pattern p = rx;
        if (p == null) return text;
        char[] n = new char[text.length()];
        for (int i = 0; i < n.length; i++) n[i] = norm(text.charAt(i));   // same length, so spans map straight back
        Matcher m = p.matcher(new String(n));
        StringBuilder out = null;
        int last = 0;
        while (m.find()) {
            if (out == null) out = new StringBuilder(text.length());
            out.append(text, last, m.start());
            int alnum = 0;
            for (int i = m.start(); i < m.end(); i++) if (Character.isLetterOrDigit(text.charAt(i))) alnum++;
            out.append("*".repeat(Math.max(3, alnum)));
            last = m.end();
        }
        if (out == null) return text;
        return out.append(text, last, text.length()).toString();
    }

    public static boolean dirty(String text) { return apply(text) != text; }
}

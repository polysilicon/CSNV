package crispy.word;

/** Scoring one guess, independent of Minecraft so the test can check it. */
public final class Score {
    private Score() {}

    public static final int ABSENT = 0, PRESENT = 1, CORRECT = 2;

    /** Standard rules, repeated letters included: greens first, then yellows only while unmatched copies remain. */
    public static int[] score(String guess, String answer) {
        int n = answer.length();
        int[] out = new int[n], left = new int[26];
        for (int i = 0; i < n; i++) {
            if (guess.charAt(i) == answer.charAt(i)) out[i] = CORRECT;
            else left[answer.charAt(i) - 'a']++;
        }
        for (int i = 0; i < n; i++) {
            if (out[i] == CORRECT) continue;
            int c = guess.charAt(i) - 'a';
            if (left[c] > 0) { out[i] = PRESENT; left[c]--; }
        }
        return out;
    }

    public static boolean solved(int[] s) { for (int x : s) if (x != CORRECT) return false; return true; }
}

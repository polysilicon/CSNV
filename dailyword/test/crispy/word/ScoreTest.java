package crispy.word;

import java.util.Arrays;

/** Checks the scoring rules, repeated letters especially. Run: java -cp tout:out crispy.word.ScoreTest */
public class ScoreTest {
    static int fails;
    static void check(String guess, String answer, String want) {
        int[] s = Score.score(guess, answer);
        StringBuilder b = new StringBuilder();
        for (int x : s) b.append(x == 2 ? 'G' : x == 1 ? 'Y' : '.');
        if (!b.toString().equals(want)) { fails++; System.out.println("FAIL " + guess + " vs " + answer + ": " + b + " want " + want); }
    }
    public static void main(String[] a) {
        check("crane", "crane", "GGGGG");
        check("trace", "crane", ".GGYG");   // t absent, r green, a green, c yellow, e green
        check("speed", "abide", "..Y.Y");    // e: one yellow (first e), second e absent; d yellow
        check("eerie", "there", "Y.Y.G");
        check("llama", "hello", "YY...");
        check("allee", "eagle", "YY.YG");
        check("mamma", "maxim", "GGY..");
        check("abbey", "kebab", "YYGY.");
        if (!Score.solved(Score.score("pearl", "pearl")) || Score.solved(Score.score("pearl", "pears"))) { fails++; System.out.println("FAIL solved"); }
        // every result has exactly as many coloured tiles of a letter as the answer allows
        String[] w = {"crane", "eerie", "speed", "mamma", "llama", "allee", "kebab", "abbey", "geese", "lever"};
        for (String g : w) for (String ans : w) {
            int[] s = Score.score(g, ans);
            for (char ch = 'a'; ch <= 'z'; ch++) {
                int col = 0, inAns = 0;
                for (int i = 0; i < 5; i++) { if (g.charAt(i) == ch && s[i] > 0) col++; if (ans.charAt(i) == ch) inAns++; }
                if (col > inAns) { fails++; System.out.println("FAIL count " + g + " " + ans + " " + ch + " " + Arrays.toString(s)); }
            }
        }
        System.out.println(fails == 0 ? "ALL OK" : fails + " FAILED");
        if (fails > 0) System.exit(1);
    }
}

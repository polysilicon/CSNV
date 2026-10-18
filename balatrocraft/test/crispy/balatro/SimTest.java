package crispy.balatro;

import crispy.balatro.Rules.*;
import org.bukkit.configuration.file.YamlConfiguration;
import java.util.*;

public class SimTest {
    static int fails = 0;
    static void check(boolean ok, String what) { if (!ok) { fails++; System.out.println("FAIL " + what); } }
    static List<Card> cards(String... s) { List<Card> l = new ArrayList<>(); int id = 0;
        for (String x : s) { char suit = x.charAt(x.length() - 1); String r = x.substring(0, x.length() - 1);
            int rank = switch (r) { case "J" -> 11; case "Q" -> 12; case "K" -> 13; case "A" -> 14; default -> Integer.parseInt(r); };
            l.add(new Card(id++, rank, suit, 0, 0)); } return l; }
    public static void main(String[] a) throws Exception {
        check(Rules.evaluate(cards("2D")).hand() == Hand.HIGH_CARD, "high");
        check(Rules.evaluate(cards("2D", "2R")).hand() == Hand.PAIR, "pair");
        check(Rules.evaluate(cards("2D", "2R", "5C", "5E")).hand() == Hand.TWO_PAIR, "twopair");
        check(Rules.evaluate(cards("9D", "9R", "9C")).hand() == Hand.THREE, "three");
        check(Rules.evaluate(cards("AD", "2R", "3C", "4E", "5D")).hand() == Hand.STRAIGHT, "wheel");
        check(Rules.evaluate(cards("10D", "JR", "QC", "KE", "AD")).hand() == Hand.STRAIGHT, "broadway");
        check(Rules.evaluate(cards("JD", "QR", "KC", "AE", "2D")).hand() == Hand.HIGH_CARD, "no wraparound");
        check(Rules.evaluate(cards("2D", "7D", "9D", "JD", "KD")).hand() == Hand.FLUSH, "flush");
        check(Rules.evaluate(cards("3D", "3R", "3C", "8E", "8D")).hand() == Hand.FULL_HOUSE, "fullhouse");
        check(Rules.evaluate(cards("4D", "4R", "4C", "4E", "8D")).hand() == Hand.FOUR, "four");
        check(Rules.evaluate(cards("4D", "4R", "4C", "4E", "8D")).scoring().size() == 4, "four scoring");
        check(Rules.evaluate(cards("5D", "6D", "7D", "8D", "9D")).hand() == Hand.STRAIGHT_FLUSH, "sflush");
        check(Rules.evaluate(cards("5D", "5D", "5D", "5D", "5D")).hand() == Hand.FLUSH_FIVE, "flushfive");
        check(Rules.evaluate(cards("5D", "5R", "5D", "5D", "5D")).hand() == Hand.FIVE, "five");
        check(Rules.evaluate(cards("5D", "5D", "5D", "8D", "8D")).hand() == Hand.FLUSH_HOUSE, "flushhouse");
        check(Rules.evaluate(cards("KD", "2R", "7C")).scoring().get(0).rank == 13, "high card scores top");

        Random rnd = new Random(1);
        int runs = 2000, wins = 0, maxAnte = 0; long hands = 0; Map<String, Integer> endAnte = new TreeMap<>();
        for (int n = 0; n < runs; n++) {
            Run r = Run.create(rnd.nextLong(), false, "");
            int guard = 0;
            while (r.state != Run.State.OVER && guard++ < 3000) {
                if (r.state == Run.State.SHOP) {
                    // simple policy: buy mobs, books, tools when affordable, then next round
                    for (int i = 0; i < 2; i++) r.buyMob(i);
                    for (int i = 0; i < 2; i++) r.buyItem(i);
                    if (r.ante > 12) { r.state = Run.State.OVER; break; }
                    r.nextRound(); continue;
                }
                // round: use tools on random cards sometimes
                if (!r.tools.isEmpty() && rnd.nextInt(3) == 0) { r.selected.clear(); r.toggle(r.hand.get(0)); r.useTool(0); }
                // pick best 5-card subset by base hand rank (cheap policy): try all subsets of size<=maxPlay
                List<Integer> h = new ArrayList<>(r.hand); int best = -1; List<Integer> pick = null;
                int k = h.size();
                for (int mask = 1; mask < (1 << k); mask++) {
                    if (Integer.bitCount(mask) > r.maxPlay()) continue;
                    List<Card> sel = new ArrayList<>(); List<Integer> ids = new ArrayList<>();
                    for (int i = 0; i < k; i++) if ((mask & (1 << i)) != 0) { sel.add(r.card(h.get(i))); ids.add(h.get(i)); }
                    Eval ev = Rules.evaluate(sel); int lv = r.level(ev.hand());
                    int sc = ev.hand().chipsAt(lv) * ev.hand().multAt(lv) * 10 + ev.scoring().stream().mapToInt(c -> Rules.rankChips(c.rank)).sum();
                    if (sc > best) { best = sc; pick = ids; }
                }
                r.selected.clear(); for (int id : pick) r.toggle(id);
                boolean weak = best < 300 && r.discardsLeft > 0 && rnd.nextBoolean();
                if (weak) { r.selected.clear(); for (int id : h.subList(Math.max(0, h.size() - 3), h.size())) r.toggle(id); check(r.discard() == null, "discard"); continue; }
                Object o = r.play(); hands++;
                check(o instanceof Run.Result, "play result " + o);
                // invariants
                check(r.hand.size() <= 8, "hand size");
                Set<Integer> all = new HashSet<>(); for (Card c : r.deck) check(all.add(c.id), "dup id");
                for (int id : r.hand) check(r.card(id) != null, "hand card in deck");
                for (int id : r.drawPile) check(r.card(id) != null, "draw card in deck");
                // save/load round trip
                if (n % 50 == 0) {
                    YamlConfiguration y = Run.toYaml(r); Run b = Run.load(YamlConfiguration.loadConfiguration(new java.io.StringReader(y.saveToString())));
                    check(Run.toYaml(b).saveToString().equals(y.saveToString()), "roundtrip");
                }
            }
            check(guard < 3000, "run terminates");
            if (r.won) wins++;
            maxAnte = Math.max(maxAnte, r.ante);
            endAnte.merge(String.format("%02d", r.ante), 1, Integer::sum);
        }
        System.out.println("runs " + runs + ", hands " + hands + ", wins " + wins + ", max ante " + maxAnte);
        System.out.println("ante reached: " + endAnte);
        // daily determinism
        Run d1 = Run.create(42, true, "x"), d2 = Run.create(42, true, "x");
        check(Run.toYaml(d1).saveToString().equals(Run.toYaml(d2).saveToString()), "same seed same start");
        System.out.println(fails == 0 ? "ALL OK" : fails + " failures");
    }
}

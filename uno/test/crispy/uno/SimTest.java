package crispy.uno;

import crispy.uno.Game.*;
import java.util.*;

/** Plays thousands of all-bot games and checks the rules' invariants: no cards lost or duplicated, every game ends,
 *  every play was legal, and players leaving mid-game are handled. */
public class SimTest {
    static int fails = 0;
    static void check(boolean ok, String what) { if (!ok) { fails++; if (fails < 20) System.out.println("FAIL: " + what); } }

    public static void main(String[] args) {
        check(Game.fullDeck().size() == 108, "deck has 108 cards");
        Random seeds = new Random(42);
        int games = 3000, turns = 0, maxTurns = 0, leaves = 0;
        Map<Integer, Integer> winsBySeat = new HashMap<>();
        for (int g = 0; g < games; g++) {
            Game game = new Game(new Random(seeds.nextLong()));
            int players = 2 + g % 7;
            for (int i = 0; i < players; i++) game.seats.add(new Seat("b" + i, "Bot" + i, true));
            game.start();
            check(game.cardCount() == 108, "cards after deal");
            for (Seat s : game.seats) check(s.hand.size() >= 7, "dealt 7");
            int t = 0;
            boolean leaver = g % 10 == 0;
            while (!game.over && t < 5000) {
                Seat s = game.current();
                int before = game.discard.size();
                Card top = game.top();
                Col colBefore = game.color;
                game.botTurn();
                if (game.discard.size() == before + 1) {
                    Card played = game.top();
                    check(played.wild() || played.col == colBefore || (played.kind != Kind.NUM && played.kind == top.kind)
                            || (played.kind == Kind.NUM && top.kind == Kind.NUM && played.num == top.num), "legal play: " + played + " on " + top + " / " + colBefore);
                }
                check(game.cardCount() == 108, "card count stays 108 (turn " + t + ")");
                check(!game.awaitingColor, "bots always pick a colour");
                if (leaver && t == 15 && game.seats.size() > 2) { game.remove(game.seats.get(1)); leaves++; check(game.cardCount() == 108, "count after leave"); }
                t++;
            }
            check(game.over, "game " + g + " ended (players " + players + ")");
            check(game.winner == null || game.winner.hand.isEmpty() || game.seats.size() < 2 || game.stalls > 0, "winner emptied their hand");
            turns += t; maxTurns = Math.max(maxTurns, t);
            if (game.winner != null) winsBySeat.merge(game.seats.indexOf(game.winner), 1, Integer::sum);
        }
        // timeouts: a human who never acts still lets the game finish
        for (int g = 0; g < 200; g++) {
            Game game = new Game(new Random(g));
            game.seats.add(new Seat("h", "Human", false));
            game.seats.add(new Seat("b", "Bot", true));
            game.start();
            int t = 0;
            while (!game.over && t < 8000) { if (game.current().bot) game.botTurn(); else game.timeout(); t++; }
            check(game.over, "timeout game " + g + " ended");
            check(game.cardCount() == 108, "timeout game count");
        }
        // UNO penalty
        Game u = new Game(new Random(1));
        Seat a = new Seat("a", "A", false), b = new Seat("b", "B", false);
        u.seats.add(a); u.seats.add(b); u.start();
        u.cur = 0; u.awaitingColor = false; u.drawn = null; u.drewThisTurn = false;
        a.hand.clear(); a.hand.add(new Card(Col.RED, Kind.NUM, 5)); a.hand.add(new Card(Col.RED, Kind.NUM, 6));
        u.discard.add(new Card(Col.RED, Kind.NUM, 1)); u.color = Col.RED;
        u.play(a, 0);
        check(a.hand.size() == 3, "no UNO call: 1 + 2 penalty cards (got " + a.hand.size() + ")");

        System.out.printf("games: %d, avg turns %.1f, max %d, leaves %d, wins by seat %s%n", games, turns / (double) games, maxTurns, leaves, new TreeMap<>(winsBySeat));
        System.out.println(fails == 0 ? "ALL OK" : fails + " FAILURES");
        if (fails > 0) System.exit(1);
    }
}

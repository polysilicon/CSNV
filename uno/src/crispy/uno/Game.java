package crispy.uno;

import java.util.*;

/** UNO rules, independent of Minecraft so SimTest can play thousands of games.
 *  Standard 108-card deck and rules: match colour, number or symbol; Skip, Reverse, Draw Two, Wild, Wild Draw Four.
 *  Drawing: draw one card; if it can be played you may play it (only that card) or pass, otherwise your turn ends.
 *  Call UNO before playing your second-to-last card, or draw 2 as a penalty. No stacking, no Draw Four challenges.
 *  Events are appended to {@link #log} (with &-colour codes) for the UI to show. */
public final class Game {
    public enum Col { RED("&c", "Red"), YELLOW("&e", "Yellow"), GREEN("&a", "Green"), BLUE("&9", "Blue"), WILD("&d", "Wild");
        public final String code, title;
        Col(String code, String title) { this.code = code; this.title = title; }
        public String text() { return code + title; }
    }
    public enum Kind { NUM, SKIP, REVERSE, DRAW2, WILD, WILD4 }
    public static final List<Col> COLORS = List.of(Col.RED, Col.YELLOW, Col.GREEN, Col.BLUE);

    public static final class Card {   // a class, not a record: identical cards must stay distinct objects
        public final Col col; public final Kind kind; public final int num;
        Card(Col col, Kind kind, int num) { this.col = col; this.kind = kind; this.num = num; }
        public boolean wild() { return col == Col.WILD; }
        public String name() {
            return switch (kind) {
                case NUM -> col.title + " " + num;
                case SKIP -> col.title + " Skip";
                case REVERSE -> col.title + " Reverse";
                case DRAW2 -> col.title + " Draw Two";
                case WILD -> "Wild";
                case WILD4 -> "Wild Draw Four";
            };
        }
        public String text() { return col.code + name(); }
        @Override public String toString() { return name(); }
    }
    static final Comparator<Card> ORDER = Comparator.comparing((Card c) -> c.col).thenComparing(c -> c.kind).thenComparingInt(c -> c.num);

    public static final class Seat {
        public final String id, name; public final boolean bot;
        public final List<Card> hand = new ArrayList<>();
        public boolean saidUno;
        public Seat(String id, String name, boolean bot) { this.id = id; this.name = name; this.bot = bot; }
    }

    public final List<Seat> seats = new ArrayList<>();
    public final Deque<Card> deck = new ArrayDeque<>();
    public final List<Card> discard = new ArrayList<>();
    public final List<String> log = new ArrayList<>();
    public Col color;
    public int cur, dir = 1, turn, stalls;   // stalls: passes in a row with the deck empty            // turn counts every change of turn (the UI uses it to reset timers)
    public boolean started, over, awaitingColor, drewThisTurn;
    public Card drawn;                         // drawn this turn and playable: the only card that may be played now
    public Seat winner;
    final Random rnd;

    public Game(Random rnd) { this.rnd = rnd; }

    public static List<Card> fullDeck() {
        List<Card> d = new ArrayList<>();
        for (Col c : COLORS) {
            d.add(new Card(c, Kind.NUM, 0));
            for (int n = 1; n <= 9; n++) { d.add(new Card(c, Kind.NUM, n)); d.add(new Card(c, Kind.NUM, n)); }
            for (Kind k : List.of(Kind.SKIP, Kind.REVERSE, Kind.DRAW2)) { d.add(new Card(c, k, 0)); d.add(new Card(c, k, 0)); }
        }
        for (int i = 0; i < 4; i++) { d.add(new Card(Col.WILD, Kind.WILD, 0)); d.add(new Card(Col.WILD, Kind.WILD4, 0)); }
        return d;
    }

    public Seat current() { return seats.get(cur); }
    public Card top() { return discard.get(discard.size() - 1); }
    public int next(int from, int steps) { int n = seats.size(); return Math.floorMod(from + dir * steps, n); }
    public Seat nextSeat() { return seats.get(next(cur, 1)); }

    public void start() {
        List<Card> d = fullDeck();
        Collections.shuffle(d, rnd);
        deck.clear(); deck.addAll(d); discard.clear();
        for (Seat s : seats) { s.hand.clear(); s.saidUno = false; give(s, 7, false); }
        Card first = deck.poll();
        while (first.kind == Kind.WILD4) { deck.addLast(first); first = deck.poll(); }   // a Wild Draw Four can't start the pile
        discard.add(first);
        started = true; cur = 0; dir = 1;
        color = first.wild() ? COLORS.get(rnd.nextInt(4)) : first.col;
        log.add("&7First card: " + first.text() + (first.wild() ? " &7(colour: " + color.text() + "&7)" : ""));
        switch (first.kind) {
            case SKIP -> { log.add("&f" + current().name + " &7is skipped."); advance(1); }
            case REVERSE -> { if (seats.size() > 2) { dir = -1; log.add("&7Play goes the other way."); } else { log.add("&f" + current().name + " &7is skipped."); advance(1); } }
            case DRAW2 -> { log.add("&f" + current().name + " &7draws 2 and is skipped."); give(current(), 2, true); advance(1); }
            default -> {}
        }
        turn++;
    }

    public boolean playable(Card c) {
        if (drawn != null && c != drawn) return false;
        if (c.wild()) return true;
        Card t = top();
        return c.col == color || (c.kind == Kind.NUM ? t.kind == Kind.NUM && t.num == c.num : c.kind == t.kind);
    }
    public boolean canPlayAny(Seat s) { return s.hand.stream().anyMatch(this::playable); }

    String turnCheck(Seat s) {
        if (!started || over) return "The game isn't running.";
        if (s != current()) return "It's not your turn.";
        return null;
    }

    /** Play card i from s's hand. A wild leaves the turn open until {@link #chooseColor}. Returns an error or null. */
    public String play(Seat s, int i) {
        String e = turnCheck(s); if (e != null) return e;
        if (awaitingColor) return "Pick a colour first.";
        if (i < 0 || i >= s.hand.size()) return "No such card.";
        Card c = s.hand.get(i);
        if (!playable(c)) return drawn != null ? "You can only play the card you just drew (or pass)." : "That card doesn't match " + color.text() + " &7or " + top().text() + "&7.";
        s.hand.remove(i);
        discard.add(c);
        drawn = null; stalls = 0;
        if (c.wild()) { awaitingColor = true; log.add("&f" + s.name + " &7plays " + c.text() + "&7..."); return null; }
        color = c.col;
        log.add("&f" + s.name + " &7plays " + c.text() + "&7.");
        finish(s, c);
        return null;
    }

    public String chooseColor(Seat s, Col col) {
        String e = turnCheck(s); if (e != null) return e;
        if (!awaitingColor) return "There's no colour to pick.";
        if (col == Col.WILD) return "Pick red, yellow, green or blue.";
        color = col; awaitingColor = false;
        log.add("&f" + s.name + " &7picks " + col.text() + "&7.");
        finish(s, top());
        return null;
    }

    void finish(Seat s, Card c) {
        if (s.hand.isEmpty()) { over = true; winner = s; log.add("&6&l" + s.name + " wins!"); return; }
        if (s.hand.size() == 1) {
            if (s.saidUno) log.add("&c&lU&e&lN&a&lO&9&l! &f" + s.name + " &7has one card left.");
            else { log.add("&f" + s.name + " &7forgot to call &cUNO&7: draws 2."); give(s, 2, true); }
        }
        switch (c.kind) {
            case SKIP -> { log.add("&f" + nextSeat().name + " &7is skipped."); advance(2); }
            case REVERSE -> {
                if (seats.size() == 2) { log.add("&f" + nextSeat().name + " &7is skipped."); advance(2); }
                else { dir = -dir; log.add("&7Play goes the other way."); advance(1); }
            }
            case DRAW2 -> { Seat n = nextSeat(); log.add("&f" + n.name + " &7draws 2 and is skipped."); give(n, 2, true); advance(2); }
            case WILD4 -> { Seat n = nextSeat(); log.add("&f" + n.name + " &7draws 4 and is skipped."); give(n, 4, true); advance(2); }
            default -> advance(1);
        }
    }

    /** Draw a card; clicking again after drawing a playable card passes. */
    public String draw(Seat s) {
        String e = turnCheck(s); if (e != null) return e;
        if (awaitingColor) return "Pick a colour first.";
        if (drewThisTurn) { log.add("&f" + s.name + " &7passes."); advance(1); return null; }
        Card c = take();
        drewThisTurn = true;
        if (c == null) {
            log.add("&f" + s.name + " &7can't draw (no cards left) and passes.");
            if (++stalls >= seats.size()) {   // nobody can play and there's nothing to draw: fewest cards wins
                over = true;
                winner = seats.stream().min(Comparator.comparingInt(x -> x.hand.size())).orElse(null);
                log.add("&7Nobody can play and the deck is empty. &6&l" + winner.name + " wins &7with the fewest cards!");
                return null;
            }
            advance(1); return null;
        }
        s.hand.add(c); s.hand.sort(ORDER); s.saidUno = false;
        if (playable(c)) { drawn = c; log.add("&f" + s.name + " &7draws a card."); }
        else { log.add("&f" + s.name + " &7draws a card and passes."); advance(1); }
        return null;
    }

    public String uno(Seat s) {
        if (!started || over) return "The game isn't running.";
        if (s.hand.size() != 2 || s != current()) return "Call UNO on your turn, when you have 2 cards (before you play one).";
        if (s.saidUno) return "You already called it.";
        s.saidUno = true;
        log.add("&f" + s.name + " &7shouts &c&lU&e&lN&a&lO&9&l!");
        return null;
    }

    void give(Seat s, int n, boolean sort) {
        for (int i = 0; i < n; i++) { Card c = take(); if (c == null) break; s.hand.add(c); }
        if (s.hand.size() > 1) s.saidUno = false;
        s.hand.sort(ORDER);
    }

    Card take() {
        if (deck.isEmpty() && discard.size() > 1) {   // reshuffle everything but the top card
            Card t = discard.remove(discard.size() - 1);
            List<Card> d = new ArrayList<>(discard);
            discard.clear(); discard.add(t);
            Collections.shuffle(d, rnd);
            deck.addAll(d);
            log.add("&8The discard pile is shuffled into a new deck.");
        }
        return deck.poll();
    }

    void advance(int steps) { cur = next(cur, steps); drawn = null; drewThisTurn = false; turn++; }

    /** The current player ran out of time: finish their colour pick, or draw and pass. */
    public void timeout() {
        Seat s = current();
        if (awaitingColor) { chooseColor(s, bestColor(s)); return; }
        if (!drewThisTurn) draw(s);
        if (!over && current() == s && !awaitingColor) draw(s);   // drew a playable card: pass
    }

    public static Col bestColor(Seat s) {
        int[] n = new int[4];
        for (Card c : s.hand) if (!c.wild()) n[c.col.ordinal()]++;
        int best = 0;
        for (int i = 1; i < 4; i++) if (n[i] > n[best]) best = i;
        return COLORS.get(best);
    }

    /** One bot turn: play the best card it can (actions first if the next player is close to winning), else draw. */
    public void botTurn() {
        Seat s = current();
        if (!s.bot || over) return;
        if (awaitingColor) { chooseColor(s, bestColor(s)); return; }
        int i = pick(s);
        if (i < 0) {
            draw(s);
            if (over || current() != s || drawn == null) return;
            i = s.hand.indexOf(drawn);
        }
        if (s.hand.size() == 2) uno(s);
        play(s, i);
        if (awaitingColor && current() == s) chooseColor(s, bestColor(s));
    }

    int pick(Seat s) {
        boolean threat = nextSeat().hand.size() <= 2;
        int best = -1, bestScore = Integer.MIN_VALUE;
        for (int i = 0; i < s.hand.size(); i++) {
            Card c = s.hand.get(i);
            if (!playable(c)) continue;
            int score = switch (c.kind) {
                case NUM -> 10 + c.num;
                case SKIP, REVERSE -> threat ? 40 : 15;
                case DRAW2 -> threat ? 50 : 18;
                case WILD -> threat ? 5 : 2;     // keep wilds for when nothing else fits
                case WILD4 -> threat ? 60 : 1;
            };
            if (!c.wild() && c.col == color) score += 3;
            if (score > bestScore) { bestScore = score; best = i; }
        }
        return best;
    }

    /** Remove a seat (left the server or the table). Their cards go back into the deck. */
    public void remove(Seat s) {
        int i = seats.indexOf(s);
        if (i < 0) return;
        if (!started) { seats.remove(i); return; }
        if (over) return;
        boolean wasCurrent = i == cur;
        if (wasCurrent && awaitingColor) { color = bestColor(s); awaitingColor = false; }
        List<Card> back = new ArrayList<>(s.hand); s.hand.clear();
        Collections.shuffle(back, rnd); deck.addAll(back);
        seats.remove(i);
        log.add("&f" + s.name + " &7left the game.");
        if (seats.size() < 2) {
            over = true; winner = seats.isEmpty() ? null : seats.get(0);
            if (winner != null) log.add("&6&l" + winner.name + " wins! &7(everyone else left)");
            return;
        }
        if (i < cur) cur--;
        else if (wasCurrent) { cur = dir > 0 ? i % seats.size() : Math.floorMod(i - 1, seats.size()); drawn = null; drewThisTurn = false; turn++; }
        cur = Math.floorMod(cur, seats.size());
    }

    /** Every card is in exactly one place (deck, discard pile or a hand). */
    public int cardCount() { return deck.size() + discard.size() + seats.stream().mapToInt(x -> x.hand.size()).sum(); }
}

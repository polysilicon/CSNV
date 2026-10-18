package crispy.balatro;

import crispy.balatro.Rules.*;
import org.bukkit.configuration.ConfigurationSection;
import org.bukkit.configuration.file.YamlConfiguration;

import java.util.*;

/** One player's run: all state and every rule. The GUI only renders this and calls its actions. */
final class Run {
    enum State { ROUND, SHOP, PACK, OVER }
    record Step(int kind, int index, String text, long chips, double mult) {}   // kind 0 = played card, 1 = mob, 2 = other
    record Result(Eval eval, List<Card> played, List<Step> steps, long total, String note) {}

    static final int HAND_SIZE = 8, HANDS = 4, DISCARDS = 3, MOB_SLOTS = 5, TOOL_SLOTS = 2, MAX_SELECT = 5, CREEPER_MIN_DECK = 30;

    long seed; boolean daily; String day = "";
    Rng rng;
    int nextId;
    final List<Card> deck = new ArrayList<>();
    final List<Integer> drawPile = new ArrayList<>(), hand = new ArrayList<>();
    final LinkedHashSet<Integer> selected = new LinkedHashSet<>();
    int ante = 1, blind = 0; Boss boss;
    long target, roundScore; int handsLeft, discardsLeft; boolean firstHand;
    int money = 4;
    final EnumMap<Hand, Integer> levels = new EnumMap<>(Hand.class);
    final List<Mob> mobs = new ArrayList<>();
    final List<Tool> tools = new ArrayList<>();
    final List<Mob> offerMobs = new ArrayList<>();
    final List<String> offerItems = new ArrayList<>();
    int rerollCost = 5;
    String offerPack;                               // STANDARD / JUMBO, null when bought
    final List<Card> packChoices = new ArrayList<>(); int packPicks;
    State state = State.ROUND;
    boolean won, sortBySuit;
    long bestHand; int handsPlayed;
    String lastHand = "";
    final List<String> news = new ArrayList<>();   // messages for the player after an action

    // ------------------------------------------------------------------ setup
    static Run create(long seed, boolean daily, String day) {
        Run r = new Run();
        r.seed = seed; r.daily = daily; r.day = day; r.rng = new Rng(seed);
        for (char s : Rules.SUITS.toCharArray()) for (int rank = 2; rank <= 14; rank++) r.deck.add(new Card(r.nextId++, rank, s, 0, 0));
        for (Hand h : Hand.values()) r.levels.put(h, 1);
        r.boss = r.pickBoss();
        r.startRound();
        return r;
    }

    Card card(int id) { for (Card c : deck) if (c.id == id) return c; return null; }
    int level(Hand h) { return levels.getOrDefault(h, 1); }

    Boss pickBoss() {
        if (ante % Rules.WIN_ANTE == 0) return Boss.ENDER_DRAGON;
        Boss[] pool = Arrays.stream(Boss.values()).filter(b -> b != Boss.ENDER_DRAGON).toArray(Boss[]::new);
        return pool[rng.nextInt(pool.length)];
    }
    Boss activeBoss() { return state == State.ROUND && blind == 2 ? boss : null; }
    long computeTarget() {
        double m = blind == 0 ? 1 : blind == 1 ? 1.5 : boss == Boss.ENDER_DRAGON ? 4 : 2;
        return Math.round(Rules.anteBase(ante) * m);
    }
    int maxPlay() { return activeBoss() == Boss.ELDER_GUARDIAN ? 3 : 5; }
    boolean faceDown(Card c) { return activeBoss() == Boss.WARDEN && Rules.isFace(c.rank); }
    boolean debuffed(Card c) { Boss b = activeBoss(); return b != null && b.debuffSuit() == c.suit; }

    /** The mob whose ability slot i uses (Allay copies the mob to its right, following chains of Allays). */
    Mob effective(int i) {
        for (int j = i; j < mobs.size(); j++) if (mobs.get(j) != Mob.ALLAY) return mobs.get(j);
        return null;
    }
    int countEffective(Mob m) { int n = 0; for (int i = 0; i < mobs.size(); i++) if (effective(i) == m) n++; return n; }

    void startRound() {
        state = State.ROUND;
        target = computeTarget(); roundScore = 0; firstHand = true;
        handsLeft = HANDS + countEffective(Mob.IRON_GOLEM);
        discardsLeft = activeBoss() == Boss.RAVAGER ? 0 : DISCARDS + countEffective(Mob.ENDERMAN);
        drawPile.clear(); hand.clear(); selected.clear();
        for (Card c : deck) drawPile.add(c.id);
        rng.shuffle(drawPile);
        drawToFull();
    }
    void drawToFull() { while (hand.size() < HAND_SIZE && !drawPile.isEmpty()) hand.add(drawPile.remove(drawPile.size() - 1)); sortHand(); }
    void sortHand() {
        Comparator<Integer> byRank = Comparator.comparingInt((Integer id) -> -card(id).rank).thenComparing(id -> Rules.SUITS.indexOf(card(id).suit));
        Comparator<Integer> bySuit = Comparator.comparingInt((Integer id) -> Rules.SUITS.indexOf(card(id).suit)).thenComparing(id -> -card(id).rank);
        hand.sort(sortBySuit ? bySuit : byRank);
    }

    // ------------------------------------------------------------------ round actions
    String toggle(int id) {
        if (state != State.ROUND || !hand.contains(id)) return null;
        if (selected.remove(id)) return null;
        if (selected.size() >= MAX_SELECT) return "&cYou can select at most 5 cards.";
        selected.add(id); return null;
    }
    List<Card> selectedCards() { List<Card> l = new ArrayList<>(); for (int id : hand) if (selected.contains(id)) l.add(card(id)); return l; }

    String discard() {
        if (state != State.ROUND) return null;
        if (selected.isEmpty()) return "&cSelect the cards to discard first.";
        if (discardsLeft <= 0) return "&cNo discards left.";
        hand.removeAll(selected); selected.clear(); discardsLeft--;
        drawToFull();
        return null;
    }

    Object play() {
        if (state != State.ROUND) return null;
        if (selected.isEmpty()) return "&cSelect up to " + maxPlay() + " cards to play.";
        if (selected.size() > maxPlay()) return "&cThe Elder Guardian only lets you play " + maxPlay() + " cards.";
        List<Card> played = selectedCards();
        Eval ev = Rules.evaluate(played);
        int lv = level(ev.hand());
        long chips = ev.hand().chipsAt(lv); double mult = ev.hand().multAt(lv);
        List<Step> steps = new ArrayList<>();
        steps.add(new Step(2, -1, "&f" + ev.hand().title + " &7lvl " + lv, chips, mult));
        int earned = 0;
        for (Card c : ev.scoring()) {
            int idx = played.indexOf(c);
            if (debuffed(c)) { steps.add(new Step(0, idx, c.label() + " &cdebuffed", chips, mult)); continue; }
            chips += Rules.rankChips(c.rank) + c.chips; mult += c.mult;
            steps.add(new Step(0, idx, c.label() + " &9+" + (Rules.rankChips(c.rank) + c.chips) + (c.mult > 0 ? " &c+" + c.mult : ""), chips, mult));
            for (int i = 0; i < mobs.size(); i++) {
                Mob m = effective(i); if (m == null) continue;
                String t = null;
                if (m == Mob.FOX && c.suit == 'E') { chips += 30; t = "&9+30"; }
                else if (m == Mob.BEE && c.suit == 'R') { mult += 4; t = "&c+4 Mult"; }
                else if (m == Mob.AXOLOTL && c.suit == 'D') { mult += 3; t = "&c+3 Mult"; }
                else if (m == Mob.PIGLIN && Rules.isFace(c.rank)) { earned++; t = "&a+$1"; }
                if (t != null) steps.add(new Step(1, i, mobs.get(i).title + " " + t, chips, mult));
            }
        }
        int coal = (int) played.stream().filter(c -> c.suit == 'C' && !debuffed(c)).count();
        for (int i = 0; i < mobs.size(); i++) {
            Mob m = effective(i); if (m == null) continue;
            String t = null;
            switch (m) {
                case ZOMBIE -> { mult += 4; t = "&c+4 Mult"; }
                case SKELETON -> { chips += 50; t = "&9+50"; }
                case CREEPER -> { mult += 20; t = "&c+20 Mult"; }
                case SPIDER -> { if (ev.pairs() >= 1) { mult += 8; t = "&c+8 Mult"; } }
                case SLIME -> { if (ev.maxSame() >= 3) { mult += 12; t = "&c+12 Mult"; } }
                case BLAZE -> { if (ev.flush()) { mult += 12; t = "&c+12 Mult"; } }
                case WITHER_SKELETON -> { if (coal >= 3) { mult *= 3; t = "&cx3 Mult"; } }
                case GHAST -> { if (played.size() <= 3) { mult *= 2; t = "&cx2 Mult"; } }
                case PHANTOM -> { if (discardsLeft > 0) { mult += 3 * discardsLeft; t = "&c+" + (3 * discardsLeft) + " Mult"; } }
                case COW -> { if (!drawPile.isEmpty()) { chips += 2L * drawPile.size(); t = "&9+" + (2 * drawPile.size()); } }
                default -> {}
            }
            if (t != null) steps.add(new Step(1, i, mobs.get(i).title + " " + t, chips, mult));
        }
        long total = (long) Math.floor(chips * mult);
        String note = "";
        if (activeBoss() == Boss.WITHER && firstHand) { total /= 2; note = "&8(halved by the Wither)"; }
        money += earned;
        // apply
        hand.removeAll(selected); selected.clear();
        handsLeft--; handsPlayed++; firstHand = false;
        roundScore += total; bestHand = Math.max(bestHand, total);
        lastHand = ev.hand().title + ": " + String.format("%,d", total);
        for (int i = 0; i < countEffective(Mob.CREEPER); i++) {
            if (deck.size() > CREEPER_MIN_DECK && rng.nextInt(6) == 0 && !drawPile.isEmpty()) {
                int id = drawPile.remove(rng.nextInt(drawPile.size()));
                Card gone = card(id); deck.remove(gone);
                news.add("&a&lSsss... BOOM! &7The Creeper blew " + gone.label() + " &7out of your deck.");
            }
        }
        if (roundScore >= target) winRound();
        else if (handsLeft <= 0) lose();
        else { drawToFull(); if (hand.isEmpty()) lose(); }
        return new Result(ev, played, steps, total, note);
    }

    void lose() { state = State.OVER; news.add("&cOut of hands. &7You reached &fAnte " + ante + " " + Rules.blindName(blind) + "&7."); }

    /** Blinds cleared so far (leaderboard progress). */
    int progress() { return (ante - 1) * 3 + blind; }

    void winRound() {
        int interest = Math.min(money / 5, 5), base = Rules.blindReward(blind), villagers = 3 * countEffective(Mob.VILLAGER);
        int reward = base + handsLeft + interest + villagers;
        money += reward;
        news.add("&a&lBlind defeated! &7Cash out: &a$" + reward + " &8(blind $" + base + ", hands left $" + handsLeft + ", interest $" + interest
                + (villagers > 0 ? ", villagers $" + villagers : "") + ")");
        if (blind == 2) {
            ante++; blind = 0; boss = pickBoss();
            if (ante == Rules.WIN_ANTE + 1 && !won) { won = true; news.add("&6&l★ YOU BEAT THE ENDER DRAGON! ★ &eYou won the run. Keep going in endless mode!"); }
        } else blind++;
        state = State.SHOP; rerollCost = 5; genShop();
    }

    // ------------------------------------------------------------------ shop
    void genShop() {
        offerMobs.clear(); offerItems.clear();
        List<Mob> pool = new ArrayList<>(List.of(Mob.values())); pool.removeAll(mobs);
        rng.shuffle(pool);
        for (int i = 0; i < 2 && i < pool.size(); i++) offerMobs.add(pool.get(i));
        Hand[] books = Arrays.copyOfRange(Hand.values(), 0, 9);
        for (int i = 0; i < 2; i++) {
            if (rng.nextInt(2) == 0) offerItems.add("BOOK:" + books[rng.nextInt(books.length)].name());
            else offerItems.add("TOOL:" + Tool.values()[rng.nextInt(Tool.values().length)].name());
        }
        offerPack = rng.nextInt(5) < 3 ? "STANDARD" : "JUMBO";
    }
    static int packPrice(String p) { return "JUMBO".equals(p) ? 6 : 4; }
    static int packSize(String p) { return "JUMBO".equals(p) ? 5 : 3; }
    static int packPickCount(String p) { return "JUMBO".equals(p) ? 2 : 1; }
    String buyPack() {
        if (state != State.SHOP || offerPack == null) return null;
        int price = packPrice(offerPack);
        if (money < price) return "&cYou need $" + price + ".";
        money -= price;
        packChoices.clear();
        for (int i = 0; i < packSize(offerPack); i++) {
            Card c = new Card(-1, 2 + rng.nextInt(13), Rules.SUITS.charAt(rng.nextInt(4)), 0, 0);
            int roll = rng.nextInt(10);
            if (roll < 2) c.chips = 30; else if (roll < 3) c.mult = 4;     // 30% come pre-enchanted
            packChoices.add(c);
        }
        packPicks = packPickCount(offerPack); offerPack = null; state = State.PACK;
        return null;
    }
    String pickCard(int i) {
        if (state != State.PACK || i >= packChoices.size() || packChoices.get(i) == null) return null;
        Card c = packChoices.get(i);
        Card added = new Card(nextId++, c.rank, c.suit, c.chips, c.mult);
        deck.add(added); packChoices.set(i, null);
        news.add("&aAdded " + added.label() + " &ato your deck &7(" + deck.size() + " cards).");
        if (--packPicks <= 0) closePack();
        return null;
    }
    void closePack() { if (state == State.PACK) { packChoices.clear(); packPicks = 0; state = State.SHOP; } }
    String reroll() {
        if (state != State.SHOP) return null;
        if (money < rerollCost) return "&cA reroll costs $" + rerollCost + ".";
        money -= rerollCost; rerollCost++; genShop(); return null;
    }
    String buyMob(int i) {
        if (state != State.SHOP || i >= offerMobs.size() || offerMobs.get(i) == null) return null;
        Mob m = offerMobs.get(i);
        if (mobs.size() >= MOB_SLOTS) return "&cYour mob slots are full (sell one with shift-click).";
        if (money < m.price) return "&cYou need $" + m.price + ".";
        money -= m.price; mobs.add(m); offerMobs.set(i, null); return null;
    }
    String buyItem(int i) {
        if (state != State.SHOP || i >= offerItems.size() || offerItems.get(i) == null) return null;
        String[] it = offerItems.get(i).split(":");
        if (it[0].equals("BOOK")) {
            if (money < Rules.BOOK_PRICE) return "&cYou need $" + Rules.BOOK_PRICE + ".";
            Hand h = Hand.valueOf(it[1]); money -= Rules.BOOK_PRICE; levels.merge(h, 1, Integer::sum);
            news.add("&d" + h.title + " &7is now level &f" + level(h) + " &8(" + h.chipsAt(level(h)) + " x " + h.multAt(level(h)) + ")");
        } else {
            Tool t = Tool.valueOf(it[1]);
            if (money < t.price) return "&cYou need $" + t.price + ".";
            if (t == Tool.EMERALDS) { money -= t.price; int add = Math.min(money, 20); money += add; news.add("&aEmerald Bundle: +$" + add); }
            else { if (tools.size() >= TOOL_SLOTS) return "&cYour item slots are full."; money -= t.price; tools.add(t); }
        }
        offerItems.set(i, null); return null;
    }
    String sellMob(int i) {
        if (i >= mobs.size()) return null;
        Mob m = mobs.remove(i); money += m.sell(); news.add("&7Sold " + m.title + " for &a$" + m.sell()); return null;
    }
    void nextRound() { if (state == State.SHOP) startRound(); }

    // ------------------------------------------------------------------ tools (used during a round on the selected cards)
    String useTool(int i) {
        if (state != State.ROUND || i >= tools.size()) return null;
        Tool t = tools.get(i);
        List<Card> sel = selectedCards();
        if (sel.isEmpty()) return "&cSelect up to " + t.max + " card(s) first, then click the item.";
        if (sel.size() > t.max) return "&c" + t.title + " works on at most " + t.max + " card(s).";
        switch (t) {
            case SHARPNESS -> sel.forEach(c -> c.chips += 30);
            case FORTUNE -> sel.forEach(c -> c.mult += 4);
            case SMELTING -> sel.forEach(c -> c.suit = 'D');
            case STRENGTH -> sel.forEach(c -> c.rank = c.rank == 14 ? 2 : c.rank + 1);
            case SILK_TOUCH -> { Card c = sel.get(0); Card copy = new Card(nextId++, c.rank, c.suit, c.chips, c.mult); deck.add(copy); drawPile.add(rng.nextInt(drawPile.size() + 1), copy.id); }
            case LAVA -> { for (Card c : sel) { hand.remove((Integer) c.id); deck.remove(c); } }
            default -> {}
        }
        tools.remove(i); selected.clear(); sortHand();
        news.add("&7Used &f" + t.title + "&7.");
        return null;
    }

    // ------------------------------------------------------------------ persistence
    void save(ConfigurationSection y) {
        y.set("seed", seed); y.set("daily", daily); y.set("day", day); y.set("rng", rng.s); y.set("next-id", nextId);
        y.set("deck", deck.stream().map(Card::save).toList());
        y.set("draw", new ArrayList<>(drawPile)); y.set("hand", new ArrayList<>(hand)); y.set("selected", new ArrayList<>(selected));
        y.set("ante", ante); y.set("blind", blind); y.set("boss", boss.name());
        y.set("target", target); y.set("round-score", roundScore); y.set("hands-left", handsLeft); y.set("discards-left", discardsLeft); y.set("first-hand", firstHand);
        y.set("money", money);
        for (Hand h : Hand.values()) y.set("levels." + h.name(), level(h));
        y.set("mobs", mobs.stream().map(Enum::name).toList()); y.set("tools", tools.stream().map(Enum::name).toList());
        y.set("offer-mobs", offerMobs.stream().map(m -> m == null ? "-" : m.name()).toList());
        y.set("offer-items", offerItems.stream().map(s -> s == null ? "-" : s).toList());
        y.set("offer-pack", offerPack == null ? "-" : offerPack);
        y.set("pack-choices", packChoices.stream().map(c -> c == null ? "-" : c.save()).toList()); y.set("pack-picks", packPicks);
        y.set("reroll", rerollCost); y.set("state", state.name()); y.set("won", won); y.set("sort-suit", sortBySuit);
        y.set("best-hand", bestHand); y.set("hands-played", handsPlayed); y.set("last-hand", lastHand);
    }
    static Run load(ConfigurationSection y) {
        Run r = new Run();
        r.seed = y.getLong("seed"); r.daily = y.getBoolean("daily"); r.day = y.getString("day", ""); r.rng = new Rng(y.getLong("rng")); r.nextId = y.getInt("next-id");
        for (String s : y.getStringList("deck")) r.deck.add(Card.load(s));
        r.drawPile.addAll(y.getIntegerList("draw")); r.hand.addAll(y.getIntegerList("hand")); r.selected.addAll(y.getIntegerList("selected"));
        r.ante = y.getInt("ante", 1); r.blind = y.getInt("blind"); r.boss = Boss.valueOf(y.getString("boss", "WITHER"));
        r.target = y.getLong("target"); r.roundScore = y.getLong("round-score"); r.handsLeft = y.getInt("hands-left"); r.discardsLeft = y.getInt("discards-left"); r.firstHand = y.getBoolean("first-hand");
        r.money = y.getInt("money");
        for (Hand h : Hand.values()) r.levels.put(h, y.getInt("levels." + h.name(), 1));
        for (String s : y.getStringList("mobs")) r.mobs.add(Mob.valueOf(s));
        for (String s : y.getStringList("tools")) r.tools.add(Tool.valueOf(s));
        for (String s : y.getStringList("offer-mobs")) r.offerMobs.add(s.equals("-") ? null : Mob.valueOf(s));
        for (String s : y.getStringList("offer-items")) r.offerItems.add(s.equals("-") ? null : s);
        String op = y.getString("offer-pack", "-"); r.offerPack = op.equals("-") ? null : op;
        for (String s : y.getStringList("pack-choices")) r.packChoices.add(s.equals("-") ? null : Card.load(s));
        r.packPicks = y.getInt("pack-picks");
        r.rerollCost = y.getInt("reroll", 5); r.state = State.valueOf(y.getString("state", "ROUND")); r.won = y.getBoolean("won"); r.sortBySuit = y.getBoolean("sort-suit");
        r.bestHand = y.getLong("best-hand"); r.handsPlayed = y.getInt("hands-played"); r.lastHand = y.getString("last-hand", "");
        return r;
    }
    static YamlConfiguration toYaml(Run r) { YamlConfiguration y = new YamlConfiguration(); r.save(y); return y; }
}

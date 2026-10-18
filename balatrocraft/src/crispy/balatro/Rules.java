package crispy.balatro;

import org.bukkit.Material;

import java.util.*;

/** All game data: hand types, cards, mobs (jokers), bosses and shop items. */
final class Rules {
    private Rules() {}

    // ------------------------------------------------------------------ RNG with a saveable state (xorshift64*)
    static final class Rng {
        long s;
        Rng(long seed) { s = seed == 0 ? 0x9E3779B97F4A7C15L : seed; }
        long next() { s ^= s >>> 12; s ^= s << 25; s ^= s >>> 27; return s * 0x2545F4914F6CDD1DL; }
        int nextInt(int n) { return (int) Math.floorMod(next() >>> 1, (long) n); }
        double nextDouble() { return (next() >>> 11) * 0x1.0p-53; }
        <T> void shuffle(List<T> l) { for (int i = l.size() - 1; i > 0; i--) Collections.swap(l, i, nextInt(i + 1)); }
    }

    // ------------------------------------------------------------------ cards
    static final String SUITS = "DREC";
    static String suitName(char s) { return switch (s) { case 'D' -> "Diamonds"; case 'R' -> "Redstone"; case 'E' -> "Emeralds"; default -> "Coal"; }; }
    static String suitSymbol(char s) { return switch (s) { case 'D' -> "◆"; case 'R' -> "❤"; case 'E' -> "♣"; default -> "♠"; }; }
    static String suitColor(char s) { return switch (s) { case 'D' -> "&b"; case 'R' -> "&c"; case 'E' -> "&a"; default -> "&8"; }; }
    static Material suitMaterial(char s) { return switch (s) { case 'D' -> Material.DIAMOND; case 'R' -> Material.REDSTONE; case 'E' -> Material.EMERALD; default -> Material.COAL; }; }
    static String rankName(int r) { return switch (r) { case 11 -> "J"; case 12 -> "Q"; case 13 -> "K"; case 14 -> "A"; default -> String.valueOf(r); }; }
    static String rankLong(int r) { return switch (r) { case 11 -> "Jack"; case 12 -> "Queen"; case 13 -> "King"; case 14 -> "Ace"; default -> String.valueOf(r); }; }
    static int rankChips(int r) { return r == 14 ? 11 : Math.min(r, 10); }
    static boolean isFace(int r) { return r >= 11 && r <= 13; }

    static final class Card {
        final int id; int rank; char suit; int chips; int mult;
        Card(int id, int rank, char suit, int chips, int mult) { this.id = id; this.rank = rank; this.suit = suit; this.chips = chips; this.mult = mult; }
        String save() { return id + ":" + rank + ":" + suit + ":" + chips + ":" + mult; }
        static Card load(String s) { String[] p = s.split(":"); return new Card(Integer.parseInt(p[0]), Integer.parseInt(p[1]), p[2].charAt(0), Integer.parseInt(p[3]), Integer.parseInt(p[4])); }
        String label() { return suitColor(suit) + rankName(rank) + " " + suitSymbol(suit); }
    }

    // ------------------------------------------------------------------ hand types
    enum Hand {
        HIGH_CARD("High Card", 5, 1, 10, 1), PAIR("Pair", 10, 2, 15, 1), TWO_PAIR("Two Pair", 20, 2, 20, 1),
        THREE("Three of a Kind", 30, 3, 20, 2), STRAIGHT("Straight", 30, 4, 30, 3), FLUSH("Flush", 35, 4, 15, 2),
        FULL_HOUSE("Full House", 40, 4, 25, 2), FOUR("Four of a Kind", 60, 7, 30, 3), STRAIGHT_FLUSH("Straight Flush", 100, 8, 40, 4),
        FIVE("Five of a Kind", 120, 12, 35, 3), FLUSH_HOUSE("Flush House", 140, 14, 40, 4), FLUSH_FIVE("Flush Five", 160, 16, 50, 3);
        final String title; final int chips, mult, lvChips, lvMult;
        Hand(String t, int c, int m, int lc, int lm) { title = t; chips = c; mult = m; lvChips = lc; lvMult = lm; }
        int chipsAt(int lv) { return chips + lvChips * (lv - 1); }
        int multAt(int lv) { return mult + lvMult * (lv - 1); }
    }

    record Eval(Hand hand, List<Card> scoring, boolean flush, int maxSame, int pairs) {}

    static Eval evaluate(List<Card> cards) {
        Map<Integer, List<Card>> byRank = new TreeMap<>(Comparator.reverseOrder());
        for (Card c : cards) byRank.computeIfAbsent(c.rank, k -> new ArrayList<>()).add(c);
        int n = cards.size();
        boolean flush = n == 5 && cards.stream().allMatch(c -> c.suit == cards.get(0).suit);
        boolean straight = false;
        if (n == 5 && byRank.size() == 5) {
            List<Integer> r = new ArrayList<>(byRank.keySet()); Collections.sort(r);
            straight = r.get(4) - r.get(0) == 4 || r.equals(List.of(2, 3, 4, 5, 14));
        }
        List<List<Card>> groups = new ArrayList<>(byRank.values());
        groups.sort((a, b) -> b.size() != a.size() ? b.size() - a.size() : b.get(0).rank - a.get(0).rank);
        int top = groups.isEmpty() ? 0 : groups.get(0).size(), second = groups.size() > 1 ? groups.get(1).size() : 0;
        int pairs = (int) groups.stream().filter(g -> g.size() >= 2).count();
        Hand h; List<Card> sc;
        if (top == 5 && flush) { h = Hand.FLUSH_FIVE; sc = cards; }
        else if (top == 3 && second == 2 && flush) { h = Hand.FLUSH_HOUSE; sc = cards; }
        else if (top == 5) { h = Hand.FIVE; sc = cards; }
        else if (straight && flush) { h = Hand.STRAIGHT_FLUSH; sc = cards; }
        else if (top == 4) { h = Hand.FOUR; sc = groups.get(0); }
        else if (top == 3 && second == 2) { h = Hand.FULL_HOUSE; sc = cards; }
        else if (flush) { h = Hand.FLUSH; sc = cards; }
        else if (straight) { h = Hand.STRAIGHT; sc = cards; }
        else if (top == 3) { h = Hand.THREE; sc = groups.get(0); }
        else if (top == 2 && second == 2) { h = Hand.TWO_PAIR; sc = new ArrayList<>(groups.get(0)); sc.addAll(groups.get(1)); }
        else if (top == 2) { h = Hand.PAIR; sc = groups.get(0); }
        else { h = Hand.HIGH_CARD; sc = groups.isEmpty() ? List.of() : List.of(groups.get(0).get(0)); }
        // keep the scoring cards in the order they were played
        List<Card> ordered = new ArrayList<>(); for (Card c : cards) if (sc.contains(c)) ordered.add(c);
        return new Eval(h, ordered, flush, top, pairs);
    }

    // ------------------------------------------------------------------ mobs (jokers)
    enum Mob {
        ZOMBIE("Zombie", "ZOMBIE_SPAWN_EGG", 4, "&c+4 &7Mult"),
        SKELETON("Skeleton", "SKELETON_SPAWN_EGG", 4, "&9+50 &7Chips"),
        CREEPER("Creeper", "CREEPER_SPAWN_EGG", 5, "&c+20 &7Mult. &71 in 6 chance after each hand", "&7to blow a card out of your deck"),
        SPIDER("Spider", "SPIDER_SPAWN_EGG", 5, "&c+8 &7Mult if the hand", "&7contains a &fPair"),
        SLIME("Slime", "SLIME_SPAWN_EGG", 6, "&c+12 &7Mult if the hand contains", "&fThree of a Kind"),
        BLAZE("Blaze", "BLAZE_SPAWN_EGG", 6, "&c+12 &7Mult if the hand", "&7is a &fFlush"),
        FOX("Fox", "FOX_SPAWN_EGG", 5, "&7Each scored &aEmerald &7card", "&7gives &9+30 &7Chips"),
        BEE("Bee", "BEE_SPAWN_EGG", 5, "&7Each scored &cRedstone &7card", "&7gives &c+4 &7Mult"),
        AXOLOTL("Axolotl", "AXOLOTL_SPAWN_EGG", 5, "&7Each scored &bDiamond &7card", "&7gives &c+3 &7Mult"),
        WITHER_SKELETON("Wither Skeleton", "WITHER_SKELETON_SPAWN_EGG", 8, "&cx3 &7Mult if the hand has", "&73 or more &8Coal &7cards"),
        PIGLIN("Piglin", "PIGLIN_SPAWN_EGG", 6, "&7Earn &a$1 &7for each", "&7scored face card"),
        VILLAGER("Villager", "VILLAGER_SPAWN_EGG", 6, "&7Earn &a$3 &7at the end", "&7of every round"),
        COW("Cow", "COW_SPAWN_EGG", 6, "&9+2 &7Chips for every card", "&7left in your deck"),
        PHANTOM("Phantom", "PHANTOM_SPAWN_EGG", 6, "&c+3 &7Mult for every", "&7discard you have left"),
        GHAST("Ghast", "GHAST_SPAWN_EGG", 7, "&cx2 &7Mult if you play", "&73 or fewer cards"),
        IRON_GOLEM("Iron Golem", "IRON_GOLEM_SPAWN_EGG", 8, "&f+1 &7hand every round"),
        ENDERMAN("Enderman", "ENDERMAN_SPAWN_EGG", 7, "&f+1 &7discard every round"),
        ALLAY("Allay", "ALLAY_SPAWN_EGG", 8, "&7Copies the ability of", "&7the mob to its right");
        final String title, icon; final int price; final String[] desc;
        Mob(String t, String icon, int price, String... desc) { title = t; this.icon = icon; this.price = price; this.desc = desc; }
        int sell() { return Math.max(1, price / 2); }
    }

    // ------------------------------------------------------------------ bosses
    enum Boss {
        WARDEN("The Warden", "WARDEN_SPAWN_EGG", "Darkness: face cards are dealt face down"),
        ELDER_GUARDIAN("Elder Guardian", "ELDER_GUARDIAN_SPAWN_EGG", "Mining Fatigue: play at most 3 cards"),
        WITHER("The Wither", "WITHER_SPAWN_EGG", "Wither: your first hand scores half"),
        RAVAGER("Ravager", "RAVAGER_SPAWN_EGG", "No discards this round"),
        EVOKER("Evoker", "EVOKER_SPAWN_EGG", "Coal cards are debuffed"),
        WITCH("Witch", "WITCH_SPAWN_EGG", "Redstone cards are debuffed"),
        PILLAGER("Pillager", "PILLAGER_SPAWN_EGG", "Emerald cards are debuffed"),
        DROWNED("Drowned", "DROWNED_SPAWN_EGG", "Diamond cards are debuffed"),
        ENDER_DRAGON("Ender Dragon", "DRAGON_HEAD", "Final boss: needs 4x the ante score");
        final String title, icon, effect;
        Boss(String t, String icon, String e) { title = t; this.icon = icon; effect = e; }
        char debuffSuit() { return switch (this) { case EVOKER -> 'C'; case WITCH -> 'R'; case PILLAGER -> 'E'; case DROWNED -> 'D'; default -> 0; }; }
    }

    // ------------------------------------------------------------------ shop items (books level a hand; tools change cards)
    enum Tool {
        SHARPNESS("Sharpening Stone", "FLINT", 3, 2, "&7Up to 2 selected cards get", "&9+30 &7Chips permanently"),
        FORTUNE("Rabbit's Foot", "RABBIT_FOOT", 3, 2, "&7Up to 2 selected cards get", "&c+4 &7Mult permanently"),
        SMELTING("Blast Furnace", "BLAST_FURNACE", 3, 3, "&7Up to 3 selected cards", "&7become &bDiamonds"),
        STRENGTH("Blaze Powder", "BLAZE_POWDER", 3, 2, "&7Up to 2 selected cards", "&7go up one rank"),
        SILK_TOUCH("Silk Touch", "STRING", 4, 1, "&7Copy 1 selected card", "&7into your deck"),
        LAVA("Lava Bucket", "LAVA_BUCKET", 3, 2, "&7Destroy up to 2", "&7selected cards"),
        EMERALDS("Emerald Bundle", "EMERALD_BLOCK", 4, 0, "&7Double your money", "&7(max &a+$20&7), used at once");
        final String title, icon; final int price, max; final String[] desc;
        Tool(String t, String icon, int price, int max, String... desc) { title = t; this.icon = icon; this.price = price; this.max = max; this.desc = desc; }
    }
    static final int BOOK_PRICE = 3;

    // ------------------------------------------------------------------ blinds
    static final long[] ANTE_BASE = {300, 700, 1600, 3500, 7000, 12000, 20000, 30000};
    static final int WIN_ANTE = 8;
    static long anteBase(int ante) {
        if (ante <= ANTE_BASE.length) return ANTE_BASE[ante - 1];
        long v = ANTE_BASE[ANTE_BASE.length - 1];
        for (int a = ANTE_BASE.length; a < ante; a++) v = Math.round(v * 1.6 / 1000.0) * 1000;
        return v;
    }
    static String blindName(int idx) { return idx == 0 ? "Small Blind" : idx == 1 ? "Big Blind" : "Boss Blind"; }
    static int blindReward(int idx) { return 3 + idx; }
    static Material material(String name) { Material m = Material.matchMaterial(name); return m == null ? Material.PAPER : m; }
}

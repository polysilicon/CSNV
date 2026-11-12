package crispy.ez;

import net.fabricmc.fabric.api.command.v2.CommandRegistrationCallback;
import net.minecraft.ChatFormatting;
import net.minecraft.commands.Commands;
import net.minecraft.core.BlockPos;
import net.minecraft.core.GlobalPos;
import net.minecraft.core.component.DataComponents;
import net.minecraft.nbt.CompoundTag;
import net.minecraft.network.chat.Component;
import net.minecraft.server.level.ServerLevel;
import net.minecraft.server.level.ServerPlayer;
import net.minecraft.world.entity.player.Inventory;
import net.minecraft.world.item.ItemStack;
import net.minecraft.world.item.Items;
import net.minecraft.world.item.component.CustomData;
import net.minecraft.world.item.component.ItemLore;
import net.minecraft.world.item.component.LodestoneTracker;
import net.minecraft.world.level.block.Blocks;
import net.minecraft.world.level.block.entity.BarrelBlockEntity;

import java.util.*;

import static crispy.ez.Ui.t;

/**
 * Contracts (1.1.0): the Fixer by the helipad (or /contracts in camp) offers each player three jobs; take one before
 * deploying. It pays when you extract alive with it done; dying fails it.
 *  - RECOVER: an Intel Cache is put in a barrel on a street in one district; a Contract Tracker compass points at it.
 *    Extract carrying it.
 *  - ELIMINATE: kill N of one enemy type (or players) on that raid.
 *  - EXFIL: extract from one named extraction point.
 *  - BOSS: be within 48 blocks when the Commander dies.
 */
final class Contracts {
    private Contracts() {}

    enum Kind { RECOVER, ELIMINATE, EXFIL, BOSS }
    record Offer(Kind kind, String target, int count, int reward, String text) {}
    record Result(int reward, String text) {}

    static final class PState {
        List<Offer> offers = new ArrayList<>();
        Offer active; int progress; BlockPos cache; String intelId;
    }
    static final Map<UUID, PState> STATE = new HashMap<>();
    static final Random RNG = new Random();
    static final String[][] DISTRICTS = {{"the north", "0", "-250"}, {"the east", "250", "0"}, {"the south", "0", "250"}, {"the west", "-250", "0"},
            {"the city centre", "0", "0"}};
    static final Object[][] ELIM = {{"rifleman", 3, 70}, {"bandit", 5, 50}, {"raider", 4, 60}, {"infected", 8, 35}, {"player", 1, 80}};

    static PState of(ServerPlayer p) {
        PState s = STATE.computeIfAbsent(p.getUUID(), k -> new PState());
        if (s.offers.isEmpty()) s.offers = roll();
        return s;
    }

    static List<Offer> roll() {
        List<Offer> pool = new ArrayList<>();
        String[] d = DISTRICTS[RNG.nextInt(DISTRICTS.length)];
        boolean centre = d[0].contains("centre");
        pool.add(new Offer(Kind.RECOVER, d[0], 1, centre ? 90 : 60, "Recover the Intel Cache from " + d[0]));
        Object[] e = ELIM[RNG.nextInt(ELIM.length)];
        pool.add(new Offer(Kind.ELIMINATE, (String) e[0], (int) e[1], (int) e[2], "Kill " + e[1] + " " + (e[0].equals("player") && (int) e[1] == 1 ? "player" : Raid.TYPE_NAME.get(e[0]))));
        String ex = Zone.EXFIL_NAMES[RNG.nextInt(Zone.EXFIL_NAMES.length)];
        pool.add(new Offer(Kind.EXFIL, ex, 1, 40, "Extract from the " + ex));
        pool.add(new Offer(Kind.BOSS, "boss", 1, 150, "Be there when the Commander falls (within 48 blocks)"));
        Collections.shuffle(pool, RNG);
        return new ArrayList<>(pool.subList(0, 3));
    }

    static void init() {
        CommandRegistrationCallback.EVENT.register((d, ctx, env) -> d.register(Commands.literal("contracts").executes(c -> {
            ServerPlayer p = c.getSource().getPlayerOrException();
            menu(p); return 1;
        })));
    }

    static ItemStack icon(Kind k) {
        return new ItemStack(switch (k) { case RECOVER -> Items.HEART_OF_THE_SEA; case ELIMINATE -> Items.IRON_SWORD; case EXFIL -> Items.FEATHER; case BOSS -> Items.WITHER_SKELETON_SKULL; });
    }

    static void menu(ServerPlayer p) {
        Ui.open(p, t("The Fixer: contracts", ChatFormatting.DARK_GRAY), 4, m -> {
            PState s = of(p);
            m.put(4, Ui.item(Items.WRITABLE_BOOK, t("Contracts", ChatFormatting.RED, ChatFormatting.BOLD), List.of(
                    t("Take one job before you deploy.", ChatFormatting.GRAY), t("It pays when you extract alive", ChatFormatting.GRAY),
                    t("with it done. Die and it fails.", ChatFormatting.GRAY)), false), null);
            if (s.active != null) {
                Offer o = s.active;
                m.put(13, Ui.item(icon(o.kind()), t("Active: " + o.text(), ChatFormatting.GREEN, ChatFormatting.BOLD), List.of(
                        t(progress(s), ChatFormatting.GRAY), t("Reward: " + Coins.fmt(o.reward()), ChatFormatting.GOLD)), true), null);
                if (!Raid.raiding(p))
                    m.put(22, Ui.item(Items.BARRIER, t("Abandon this contract", ChatFormatting.RED), List.of(t("Pick another one instead.", ChatFormatting.GRAY)), false),
                            (pl, c) -> { abandon(pl, s); Shops.ok(pl, "Contract abandoned."); });
            } else {
                int[] slots = {11, 13, 15};
                for (int i = 0; i < s.offers.size(); i++) {
                    Offer o = s.offers.get(i);
                    m.put(slots[i], Ui.item(icon(o.kind()), t(o.text(), ChatFormatting.YELLOW, ChatFormatting.BOLD), List.of(
                            t("Reward: " + Coins.fmt(o.reward()), ChatFormatting.GOLD), Component.empty(),
                            t(Raid.raiding(p) ? "Take contracts in camp, before deploying." : "Click to take this job", ChatFormatting.DARK_GRAY)), false),
                            Raid.raiding(p) ? null : (pl, c) -> { s.active = o; s.progress = 0; Shops.ok(pl, "Contract taken: " + o.text() + ". Deploy at the helipad."); });
                }
                m.put(31, Ui.item(Items.CLOCK, t("New offers", ChatFormatting.AQUA), List.of(t("Cost: " + Coins.fmt(5), ChatFormatting.GOLD)), false),
                        (pl, c) -> { if (!Shops.pay(pl, 5)) { Shops.no(pl, "You need 5 coins."); return; } s.offers = roll(); });
            }
            m.put(35, Ui.item(Items.BARRIER, t("Close", ChatFormatting.RED), List.of(), false), (pl, c) -> pl.closeContainer());
        });
    }

    static String progress(PState s) {
        Offer o = s.active;
        return switch (o.kind()) {
            case ELIMINATE -> "Progress: " + Math.min(s.progress, o.count()) + " / " + o.count() + " (this raid)";
            case RECOVER -> "Find the cache with the Contract Tracker, then extract.";
            case EXFIL -> "Extract from the " + o.target() + ".";
            case BOSS -> "The Commander roams the city centre.";
        };
    }

    static void abandon(ServerPlayer p, PState s) {
        cleanup(p, s);
        s.active = null; s.progress = 0; s.offers = roll();
    }

    // ---------------------------------------------------------------- raid hooks
    static void onDeploy(ServerPlayer p) {
        PState s = of(p);
        if (s.active == null) {
            p.sendSystemMessage(t("Tip: take a contract from the Fixer by the helipad before you deploy, for bonus coins.", ChatFormatting.DARK_GRAY));
            return;
        }
        s.progress = 0;
        p.sendSystemMessage(t("📋 Contract: " + s.active.text() + " (" + Coins.fmt(s.active.reward()) + ")", ChatFormatting.GOLD));
        if (s.active.kind() == Kind.RECOVER) plantCache(p, s);
    }

    static void plantCache(ServerPlayer p, PState s) {
        ServerLevel lvl = p.level().getServer().getLevel(Zone.CITY);
        if (lvl == null) return;
        String[] d = Arrays.stream(DISTRICTS).filter(x -> x[0].equals(s.active.target())).findFirst().orElse(DISTRICTS[4]);
        int x = Zone.CX + Integer.parseInt(d[1]) + RNG.nextInt(121) - 60, z = Zone.CZ + Integer.parseInt(d[2]) + RNG.nextInt(121) - 60;
        BlockPos at = Zone.street(lvl, x, z);
        if (at == null) at = Zone.ground(lvl, x, z);
        if (at == null) return;
        lvl.setBlockAndUpdate(at, Blocks.BARREL.defaultBlockState());
        s.intelId = UUID.randomUUID().toString().substring(0, 8);
        s.cache = at;
        if (lvl.getBlockEntity(at) instanceof BarrelBlockEntity b) b.setItem(13, intel(s.intelId));
        ItemStack tracker = new ItemStack(Items.COMPASS);
        tracker.set(DataComponents.LODESTONE_TRACKER, new LodestoneTracker(Optional.of(GlobalPos.of(Zone.CITY, at)), false));
        tracker.set(DataComponents.CUSTOM_NAME, t("Contract Tracker", ChatFormatting.GOLD, ChatFormatting.BOLD));
        tracker.set(DataComponents.LORE, new ItemLore(List.of(t("Points at the Intel Cache (" + d[0] + ").", ChatFormatting.GRAY))));
        CompoundTag tag = new CompoundTag(); tag.putString("ez", "tracker");
        tracker.set(DataComponents.CUSTOM_DATA, CustomData.of(tag));
        Shops.give(p, tracker);
        p.sendSystemMessage(t("The Intel Cache is in a barrel on a street in " + d[0] + ". Follow the Contract Tracker.", ChatFormatting.YELLOW));
    }

    static ItemStack intel(String id) {
        ItemStack s = new ItemStack(Items.HEART_OF_THE_SEA);
        s.set(DataComponents.CUSTOM_NAME, t("Intel Cache", ChatFormatting.AQUA, ChatFormatting.BOLD));
        s.set(DataComponents.LORE, new ItemLore(List.of(t("Contract item: extract with it to", ChatFormatting.GRAY), t("get paid by the Fixer.", ChatFormatting.GRAY))));
        CompoundTag tag = new CompoundTag(); tag.putString("ez", "intel"); tag.putString("id", id);
        s.set(DataComponents.CUSTOM_DATA, CustomData.of(tag));
        return s;
    }

    static void onKill(ServerPlayer p, String type) {
        PState s = STATE.get(p.getUUID());
        if (s == null || s.active == null || s.active.kind() != Kind.ELIMINATE || !s.active.target().equals(type)) return;
        s.progress++;
        if (s.progress <= s.active.count())
            p.sendSystemMessage(t("📋 Contract: " + s.progress + " / " + s.active.count() + (s.progress >= s.active.count() ? " done! Now extract." : ""), ChatFormatting.GOLD), true);
    }

    static Result onExtract(ServerPlayer p, String exfil, Raid.State st) {
        PState s = STATE.get(p.getUUID());
        if (s == null || s.active == null) return null;
        Offer o = s.active;
        boolean done = switch (o.kind()) {
            case ELIMINATE -> s.progress >= o.count();
            case EXFIL -> exfil.equalsIgnoreCase(o.target());
            case BOSS -> st.bossPresent || st.kills.containsKey("boss");
            case RECOVER -> takeIntel(p, s.intelId);
        };
        cleanup(p, s);
        if (!done) {
            String why = switch (o.kind()) {
                case ELIMINATE -> "only " + s.progress + " / " + o.count() + " kills";
                case EXFIL -> "you extracted from " + exfil + ", not the " + o.target();
                case BOSS -> "the Commander didn't fall near you";
                case RECOVER -> "you didn't bring the Intel Cache";
            };
            return new Result(0, o.text() + ": not done (" + why + "). It's still yours: try again next raid.");
        }
        s.active = null; s.progress = 0; s.offers = roll();
        return new Result(o.reward(), o.text() + ": done! +" + Coins.fmt(o.reward()));
    }

    static Result onDied(ServerPlayer p) {
        PState s = STATE.get(p.getUUID());
        if (s == null || s.active == null) return null;
        Offer o = s.active;
        cleanup(p, s);
        s.active = null; s.progress = 0; s.offers = roll();
        return new Result(0, o.text() + ": failed (you died).");
    }

    static boolean takeIntel(ServerPlayer p, String id) {
        if (id == null) return false;
        Inventory inv = p.getInventory();
        for (int i = 0; i < inv.getContainerSize(); i++) {
            ItemStack s = inv.getItem(i);
            CustomData cd = s.get(DataComponents.CUSTOM_DATA);
            if (cd != null && "intel".equals(cd.copyTag().getString("ez").orElse("")) && id.equals(cd.copyTag().getString("id").orElse(""))) {
                inv.setItem(i, ItemStack.EMPTY); return true;
            }
        }
        return false;
    }

    /** Remove the tracker compass and the cache barrel (if nobody took the cache, the barrel goes too). */
    static void cleanup(ServerPlayer p, PState s) {
        Inventory inv = p.getInventory();
        for (int i = 0; i < inv.getContainerSize(); i++) {
            CustomData cd = inv.getItem(i).get(DataComponents.CUSTOM_DATA);
            if (cd != null && "tracker".equals(cd.copyTag().getString("ez").orElse(""))) inv.setItem(i, ItemStack.EMPTY);
        }
        if (s.cache != null) {
            ServerLevel lvl = p.level().getServer().getLevel(Zone.CITY);
            if (lvl != null && lvl.isLoaded(s.cache) && lvl.getBlockState(s.cache).is(Blocks.BARREL)) {
                if (lvl.getBlockEntity(s.cache) instanceof BarrelBlockEntity b) b.clearContent();
                lvl.removeBlock(s.cache, false);
            }
            s.cache = null;
        }
    }
}

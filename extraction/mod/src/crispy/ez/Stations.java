package crispy.ez;

import com.google.gson.JsonArray;
import com.google.gson.JsonElement;
import com.google.gson.JsonObject;
import com.google.gson.JsonParser;
import net.fabricmc.fabric.api.event.player.UseBlockCallback;
import net.minecraft.ChatFormatting;
import net.minecraft.core.registries.BuiltInRegistries;
import net.minecraft.network.chat.Component;
import net.minecraft.server.MinecraftServer;
import net.minecraft.server.level.ServerPlayer;
import net.minecraft.world.InteractionHand;
import net.minecraft.world.InteractionResult;
import net.minecraft.world.item.ItemStack;
import net.minecraft.world.item.Items;

import java.nio.file.Files;
import java.nio.file.Path;
import java.util.*;
import java.util.function.Predicate;

import static crispy.ez.Ui.t;

/**
 * Bunker crafting stations (1.8.0). Six vanilla blocks with no vanilla use left (recipes are filtered out) become
 * stations when they stand in your own bunker: Sewing Table (loom), Med Bench (brewing stand), Kiln (blast furnace),
 * Reloading Bench (fletching table), Still (smoker), Tool Bench (stonecutter). Recipes come from shops.json
 * "stations" (written by the datapack build). Inputs are matched exactly: "ez:<key>" is one of our items (custom_data
 * ez), anything else a plain vanilla item. Timed recipes (Kiln, Still) become jobs saved on the plot: up to 3 per
 * station type, collected from the station's menu when done, so they run while you raid.
 */
final class Stations {
    private Stations() {}

    static final Path FILE = Path.of("config", "crispy_extraction", "shops.json");
    record In(String match, int n) {}
    record Recipe(String key, String label, ItemStack out, int n, List<In> in, int seconds, String perkDouble) {}
    record Station(String key, String block, String title, List<Recipe> recipes) {}
    static final Map<String, Station> BY_BLOCK = new LinkedHashMap<>();
    static final int MAX_JOBS = 3;

    static void load(MinecraftServer server) {
        if (!BY_BLOCK.isEmpty()) return;
        try {
            JsonObject root = JsonParser.parseString(Files.readString(FILE)).getAsJsonObject();
            if (!root.has("stations")) return;
            for (var e : root.getAsJsonObject("stations").entrySet()) {
                JsonObject s = e.getValue().getAsJsonObject();
                List<Recipe> rs = new ArrayList<>();
                for (JsonElement re : s.getAsJsonArray("recipes")) {
                    JsonObject r = re.getAsJsonObject();
                    List<In> in = new ArrayList<>();
                    for (JsonElement ie : r.getAsJsonArray("in")) { JsonArray a = ie.getAsJsonArray(); in.add(new In(a.get(0).getAsString(), a.get(1).getAsInt())); }
                    rs.add(new Recipe(r.get("key").getAsString(), r.get("label").getAsString(), Shops.parse(server, r.get("out").getAsString()), r.get("n").getAsInt(), in,
                            r.get("seconds").getAsInt(), r.has("perk_double") ? r.get("perk_double").getAsString() : null));
                }
                BY_BLOCK.put(s.get("block").getAsString(), new Station(e.getKey(), s.get("block").getAsString(), s.get("title").getAsString(), rs));
            }
        } catch (Exception ex) { System.err.println("[crispy-extraction] stations: " + ex); BY_BLOCK.clear(); }
    }

    // ---------------------------------------------------------------- inputs
    static Predicate<ItemStack> matcher(String m) {
        if (m.startsWith("ez:")) { String k = m.substring(3); return st -> k.equals(Shops.ezKey(st)); }
        return st -> Shops.ezKey(st).isEmpty() && BuiltInRegistries.ITEM.getKey(st.getItem()).toString().equals(m);   // 1.8.1: ezKey is "" (not null) for a plain item
    }
    static String inName(MinecraftServer server, String m) {
        for (Station s : BY_BLOCK.values()) for (Recipe r : s.recipes()) if (m.startsWith("ez:") && m.substring(3).equals(Shops.ezKey(r.out()))) return r.out().getHoverName().getString();
        if (m.startsWith("ez:")) {
            Shops.load(server);
            for (Shops.Shop sh : Shops.SHOPS.values()) {
                for (Shops.Sell se : sh.sell()) if (se.key().equals(m.substring(3))) return se.icon().getHoverName().getString();
                for (Shops.Buy b : sh.buy()) if (m.substring(3).equals(Shops.ezKey(b.item()))) return b.item().getHoverName().getString();
            }
            return m.substring(3);
        }
        var it = BuiltInRegistries.ITEM.getValue(net.minecraft.resources.Identifier.parse(m));
        return new ItemStack(it).getHoverName().getString();
    }
    static boolean canMake(ServerPlayer p, Recipe r, int times) {
        for (In i : r.in()) if (Shops.count(p, matcher(i.match())) < i.n() * times) return false;
        return true;
    }
    static void takeInputs(ServerPlayer p, Recipe r, int times) { for (In i : r.in()) Shops.take(p, matcher(i.match()), i.n() * times); }
    static int outputs(ServerPlayer p, Recipe r) { return r.perkDouble() != null && Plots.hasPerk(p, r.perkDouble()) ? 2 : 1; }

    // ---------------------------------------------------------------- jobs (timed recipes)
    static final class Job { String station; String recipe; long ready; }
    static List<Job> jobs(Plots.Plot p) { if (p.jobs == null) p.jobs = new ArrayList<>(); return p.jobs; }
    static Recipe recipe(Station s, String key) { return s.recipes().stream().filter(r -> r.key().equals(key)).findFirst().orElse(null); }
    static String left(long ms) { long s = Math.max(0, ms / 1000); return s / 60 + ":" + String.format("%02d", s % 60); }

    // ---------------------------------------------------------------- the menu
    static void open(ServerPlayer p, Station s) {
        if (s.key().equals("salvage")) { Salvage.open(p); return; }   // 1.8.16: no recipes, a menu of what you carry
        MinecraftServer server = p.level().getServer();
        Plots.Plot plot = Plots.of(p);
        Ui.open(p, t(s.title(), ChatFormatting.DARK_GRAY), 6, m -> {
            m.put(4, Ui.item(Items.BOOK, t(s.title(), ChatFormatting.AQUA, ChatFormatting.BOLD), List.of(
                    t("Click a recipe to make it.", ChatFormatting.GRAY), t("Shift-click: make 5 (instant recipes).", ChatFormatting.GRAY),
                    t("Timed recipes keep going while you raid.", ChatFormatting.GRAY)), false), null);
            for (int i = 0; i < s.recipes().size() && i < 27; i++) {
                Recipe r = s.recipes().get(i);
                List<Component> lore = new ArrayList<>();
                lore.add(t("Makes " + r.n() * outputs(p, r) + (outputs(p, r) > 1 ? " (Medical Station: doubled)" : ""), ChatFormatting.GREEN));
                lore.add(t("Needs:", ChatFormatting.GRAY));
                for (In in : r.in()) {
                    int have = Shops.count(p, matcher(in.match()));
                    lore.add(t("  " + in.n() + "× " + inName(server, in.match()) + "  (have " + have + ")", have >= in.n() ? ChatFormatting.WHITE : ChatFormatting.RED));
                }
                if (r.seconds() > 0) lore.add(t("Takes " + left(r.seconds() * 1000L) + " (runs while you're away)", ChatFormatting.GOLD));
                lore.add(t(canMake(p, r, 1) ? "Click: make" : "Missing ingredients", canMake(p, r, 1) ? ChatFormatting.YELLOW : ChatFormatting.DARK_GRAY));
                ItemStack icon = r.out().copyWithCount(Math.min(64, r.n()));
                m.put(9 + i, Ui.item(icon, t(r.label(), ChatFormatting.AQUA), lore, false), (pl, c) -> craft(pl, s, r, c.shift() && r.seconds() == 0 ? 5 : 1));
            }
            // timed jobs in progress
            if (plot != null && !p.level().dimension().equals(Zone.CITY) && s.recipes().stream().anyMatch(r -> r.seconds() > 0)) {
                List<Job> mine = jobs(plot).stream().filter(j -> j.station.equals(s.key())).toList();
                for (int k = 0; k < MAX_JOBS; k++) {
                    int slot = 45 + k;
                    if (k >= mine.size()) { m.put(slot, Ui.item(Items.GLASS_PANE, t("Free slot", ChatFormatting.GRAY), List.of(), false), null); continue; }
                    Job j = mine.get(k); Recipe r = recipe(s, j.recipe);
                    if (r == null) continue;
                    long rem = j.ready - System.currentTimeMillis();
                    boolean done = rem <= 0;
                    m.put(slot, Ui.item(r.out().copyWithCount(Math.min(64, r.n())), t((done ? "✔ Ready: " : "⏳ ") + r.label(), done ? ChatFormatting.GREEN : ChatFormatting.GOLD),
                            List.of(t(done ? "Click: collect" : "Ready in " + left(rem), ChatFormatting.GRAY)), done), done ? (pl, c) -> collect(pl, s, j) : null);
                }
            }
            m.put(49, Ui.item(Items.BARRIER, t("Close", ChatFormatting.RED), List.of(), false), (pl, c) -> pl.closeContainer());
        });
    }

    static void craft(ServerPlayer p, Station s, Recipe r, int times) {
        Plots.Plot plot = Plots.of(p);
        boolean inZone = p.level().dimension().equals(Zone.CITY);
        if (r.seconds() > 0 && (plot == null || inZone)) { Shops.no(p, r.label() + " takes time: start it at a " + s.title() + " in your bunker."); return; }
        if (r.seconds() > 0 && jobs(plot).stream().filter(j -> j.station.equals(s.key())).count() >= MAX_JOBS) {
            Shops.no(p, "This " + s.title() + " is busy: collect a finished job first (" + MAX_JOBS + " at a time)."); return;
        }
        if (!canMake(p, r, times)) {
            int can = 0; while (can < times && canMake(p, r, can + 1)) can++;
            if (can == 0) { Shops.no(p, "You're missing ingredients for " + r.label() + "."); return; }
            times = can;
        }
        takeInputs(p, r, times);
        if (r.seconds() > 0) {
            Job j = new Job(); j.station = s.key(); j.recipe = r.key(); j.ready = System.currentTimeMillis() + r.seconds() * 1000L;
            jobs(plot).add(j); Plots.save();
            Shops.ok(p, r.label() + " started: ready in " + left(r.seconds() * 1000L) + ".");
        } else {
            int n = times * outputs(p, r);
            for (int k = 0; k < n; k++) Shops.give(p, r.out().copy());
            Shops.ok(p, "Made " + (n > 1 ? n + "× " : "") + r.label() + ".");
            Ui.sound(p, net.minecraft.sounds.SoundEvents.UI_STONECUTTER_TAKE_RESULT, 0.8f, 1.1f);
        }
        open(p, s);
    }
    static void collect(ServerPlayer p, Station s, Job j) {
        Plots.Plot plot = Plots.of(p);
        if (plot == null || !jobs(plot).contains(j) || j.ready > System.currentTimeMillis()) return;
        Recipe r = recipe(s, j.recipe);
        jobs(plot).remove(j); Plots.save();
        if (r != null) { Shops.give(p, r.out().copy()); Shops.ok(p, "Collected " + r.label() + "."); }
        open(p, s);
    }

    static void init() {
        UseBlockCallback.EVENT.register((pl, world, hand, hit) -> {
            if (!(pl instanceof ServerPlayer p) || p.isShiftKeyDown()) return InteractionResult.PASS;
            boolean zone = world.dimension().equals(Zone.CITY);
            if (!zone && !world.dimension().equals(Plots.CAMP)) return InteractionResult.PASS;
            load(p.level().getServer());
            String id = BuiltInRegistries.BLOCK.getKey(world.getBlockState(hit.getBlockPos()).getBlock()).toString();
            if (zone && id.equals("minecraft:furnace")) id = "minecraft:blast_furnace";   // a furnace the city kept is a Kiln too
            Station s = BY_BLOCK.get(id);
            if (s == null) return InteractionResult.PASS;
            if (zone) {   // 1.8.15: the city's stations work too (instant recipes; timed ones run in your bunker)
                if (hand == InteractionHand.MAIN_HAND) { Trace.d(p, "zone station " + s.key()); open(p, s); }
                return InteractionResult.SUCCESS;
            }
            Plots.Plot plot = Plots.of(p);
            if (plot == null || !Plots.inside(plot, hit.getBlockPos())) return InteractionResult.FAIL;   // someone else's: no vanilla UI either
            if (hand == InteractionHand.MAIN_HAND) { Trace.d(p, "station " + s.key()); open(p, s); }
            return InteractionResult.SUCCESS;
        });
    }
}

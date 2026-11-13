package crispy.ez;

import com.google.gson.Gson;
import com.google.gson.reflect.TypeToken;
import net.fabricmc.fabric.api.event.lifecycle.v1.ServerTickEvents;
import net.fabricmc.fabric.api.event.player.UseBlockCallback;
import net.fabricmc.fabric.api.event.player.UseEntityCallback;
import net.fabricmc.fabric.api.networking.v1.ServerPlayConnectionEvents;
import net.minecraft.core.registries.BuiltInRegistries;
import net.minecraft.server.level.ServerPlayer;
import net.minecraft.world.InteractionHand;
import net.minecraft.world.InteractionResult;
import net.minecraft.world.entity.Entity;
import net.minecraft.world.item.BlockItem;
import net.minecraft.world.phys.Vec3;
import org.slf4j.Logger;
import org.slf4j.LoggerFactory;

import java.nio.file.Files;
import java.nio.file.Path;
import java.util.*;

/**
 * New-player flow logging (1.6.0), always on. Lines go to the server log as "[ez-flow] ..." for
 * tools/analytics/extraction_flow.py:
 *   join <name> first=<true|false>
 *   milestone <name> <trader|helipad|bunker> first=<bool> since_first_join=<s> since_join=<s>
 *   miss <name> <what was clicked> at <x y z> eye-dist <d> nearest <target> <d>
 * A miss is a right-click in the camp itself (not a bunker) that nothing handled: no menu, no move, no decision. The
 * first time each player reaches a milestone is kept in config/crispy_extraction/flow.json, so "first" survives restarts.
 */
final class Flow {
    private Flow() {}

    static final Logger LOG = LoggerFactory.getLogger("ez-flow");
    static final Path FILE = Path.of("config", "crispy_extraction", "flow.json");
    static Map<String, Map<String, Long>> seen;
    static final Map<UUID, Long> joined = new HashMap<>();
    static final Map<UUID, String> pending = new HashMap<>();   // a click waiting to be handled, checked at the tick's end
    static final Set<UUID> handled = new HashSet<>();
    // the camp's click targets, for "nearest" on a miss (name, x, y, z)
    static final Object[][] TARGETS = {{"Quartermaster", -12.5, 65.0, -6.5}, {"Builder", -12.5, 65.0, 6.5}, {"The Broker", 13.5, 65.0, -6.5},
            {"Bunker Manager", 13.5, 65.0, 5.5}, {"The Fixer", 0.5, 65.0, -12.5}, {"helipad", 0.5, 64.0, 12.5}, {"bunker door", 12.5, 62.5, 16.0}};

    static void load() {
        if (seen != null) return;
        try { seen = Files.exists(FILE) ? new Gson().fromJson(Files.readString(FILE), new TypeToken<Map<String, Map<String, Long>>>() {}.getType()) : null; }
        catch (Exception e) { seen = null; }
        if (seen == null) seen = new HashMap<>();
    }
    static void save() {
        try { Files.createDirectories(FILE.getParent()); Files.writeString(FILE, new Gson().toJson(seen)); } catch (Exception ignored) {}
    }

    static boolean inCamp(ServerPlayer p) {
        Vec3 v = p.position();
        return p.level().dimension().equals(Plots.CAMP) && Math.abs(v.x) < 22 && Math.abs(v.z) < 22 && v.y > 55 && v.y < 85;
    }

    /** A handler did something with this player's click. */
    static void handled(ServerPlayer p) { handled.add(p.getUUID()); }

    /** A milestone: trader (a trader's menu), helipad (deployed), bunker (arrived in their bunker). */
    static void mark(ServerPlayer p, String what) {
        handled(p);
        if (p instanceof net.fabricmc.fabric.api.entity.FakePlayer) return;   // the self-test
        load();
        Map<String, Long> m = seen.computeIfAbsent(p.getUUID().toString(), k -> new HashMap<>());
        long now = System.currentTimeMillis();
        boolean first = !m.containsKey(what);
        if (first) { m.put(what, now); save(); }
        long fj = m.getOrDefault("first_join", now), j = joined.getOrDefault(p.getUUID(), now);
        LOG.info("[ez-flow] milestone {} {} first={} since_first_join={} since_join={}", p.getGameProfile().name(), what, first, (now - fj) / 1000, (now - j) / 1000);
    }

    static String near(Vec3 at) {
        String best = "?"; double bd = 1e9;
        for (Object[] t : TARGETS) {
            double d = at.distanceTo(new Vec3((double) t[1], (double) t[2], (double) t[3]));
            if (d < bd) { bd = d; best = (String) t[0]; }
        }
        return best + " " + String.format("%.1f", bd);
    }

    static void init() {
        ServerPlayConnectionEvents.JOIN.register((h, sender, server) -> {
            load();
            ServerPlayer p = h.getPlayer();
            Map<String, Long> m = seen.computeIfAbsent(p.getUUID().toString(), k -> new HashMap<>());
            boolean first = !m.containsKey("first_join");
            if (first) { m.put("first_join", System.currentTimeMillis()); save(); }
            joined.put(p.getUUID(), System.currentTimeMillis());
            LOG.info("[ez-flow] join {} first={}", p.getGameProfile().name(), first);
        });
        ServerPlayConnectionEvents.DISCONNECT.register((h, server) -> joined.remove(h.getPlayer().getUUID()));
        UseBlockCallback.EVENT.register((pl, world, hand, hit) -> {
            if (pl instanceof ServerPlayer p && hand == InteractionHand.MAIN_HAND && inCamp(p) && !(p instanceof net.fabricmc.fabric.api.entity.FakePlayer) && !(p.getItemInHand(hand).getItem() instanceof BlockItem) && !p.isCreative()) {
                handled.remove(p.getUUID());
                pending.put(p.getUUID(), BuiltInRegistries.BLOCK.getKey(world.getBlockState(hit.getBlockPos()).getBlock()).getPath() + " at " + hit.getBlockPos().toShortString()
                        + String.format(" eye-dist %.1f nearest %s", p.getEyePosition().distanceTo(hit.getLocation()), near(hit.getLocation())));
            }
            return InteractionResult.PASS;
        });
        UseEntityCallback.EVENT.register((pl, world, hand, e, hit) -> {
            if (pl instanceof ServerPlayer p && hand == InteractionHand.MAIN_HAND && inCamp(p) && !(p instanceof net.fabricmc.fabric.api.entity.FakePlayer) && !p.isCreative()) {
                handled.remove(p.getUUID());
                pending.put(p.getUUID(), BuiltInRegistries.ENTITY_TYPE.getKey(e.getType()).getPath() + e.entityTags() + " at " + e.blockPosition().toShortString()
                        + String.format(" eye-dist %.1f nearest %s", p.getEyePosition().distanceTo(e.position()), near(e.position())));
            }
            return InteractionResult.PASS;
        });
        ServerTickEvents.END_SERVER_TICK.register(server -> {
            if (pending.isEmpty()) return;
            for (var en : pending.entrySet()) {
                if (handled.contains(en.getKey())) continue;
                ServerPlayer p = server.getPlayerList().getPlayer(en.getKey());
                // the deploy pad is a datapack advancement: a deploy that tick shows up as the helipad milestone instead
                if (p != null) LOG.info("[ez-flow] miss {} {}", p.getGameProfile().name(), en.getValue());
            }
            pending.clear(); handled.clear();
        });
    }
}

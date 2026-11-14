package crispy.ez;

import net.fabricmc.fabric.api.event.lifecycle.v1.ServerEntityEvents;
import net.fabricmc.fabric.api.event.lifecycle.v1.ServerTickEvents;
import net.minecraft.core.BlockPos;
import net.minecraft.server.MinecraftServer;
import net.minecraft.server.level.ServerLevel;
import net.minecraft.server.level.ServerPlayer;
import net.minecraft.world.entity.Entity;
import net.minecraft.world.entity.Marker;
import net.minecraft.world.level.block.entity.RandomizableContainerBlockEntity;
import net.minecraft.world.phys.AABB;

import java.util.*;

/**
 * Crate restock countdowns (1.8.31). A crate restocks CRATE_TICKS after its last fill (the datapack's crate/second:
 * marker score ez.ct = the game time it was filled), players nearby or not. Once a crate has been
 * opened, a small floating label above it shows how long is left ("⟳ Restocks in 7:32"). Unopened crates (still holding their loot table) show nothing: no label means it's full.
 * Labels exist only near players (within RANGE blocks), update once a second, and are removed when nobody's near;
 * labels left over from a restart are removed when they load.
 */
final class CrateTimer {
    private CrateTimer() {}

    static final int CRATE_TICKS = 600 * 20;   // build.py CRATE_EVERY
    static final double RANGE = 12;
    static final Map<UUID, UUID> LABELS = new HashMap<>();   // crate marker -> its label
    static final Map<UUID, String> SHOWN = new HashMap<>();   // label -> text it shows

    static void init() {
        ServerTickEvents.END_SERVER_TICK.register(server -> {
            if (server.getTickCount() % 20 != 7) return;
            try { tick(server); } catch (Exception e) { System.err.println("[crispy-extraction] crate timers: " + e); }
        });
        ServerEntityEvents.ENTITY_LOAD.register((e, lvl) -> {   // a label from before a restart: it isn't tracked any more
            if (e.entityTags().contains("ez.cratetimer") && !LABELS.containsValue(e.getUUID())) e.discard();
        });
    }

    static String label(long left, boolean playerNear) {
        if (left > 0) { long s = (left + 19) / 20; return "⟳ Restocks in " + s / 60 + ":" + String.format("%02d", s % 60); }
        return "⟳ Restocking...";   // due: the datapack refills it within a second
    }

    static void tick(MinecraftServer server) {
        ServerLevel lvl = server.getLevel(Zone.CITY);
        if (lvl == null) return;
        var sb = server.getScoreboard(); var ct = sb.getObjective("ez.ct");
        if (ct == null) return;
        long now = lvl.getGameTime();
        Set<UUID> keep = new HashSet<>();
        for (ServerPlayer p : lvl.players()) {
            if (p.isSpectator()) continue;
            for (Marker m : lvl.getEntitiesOfClass(Marker.class, p.getBoundingBox().inflate(RANGE), x -> x.entityTags().contains("ez.crate"))) {
                if (!keep.add(m.getUUID())) continue;
                BlockPos b = m.blockPosition();
                boolean full = !(lvl.getBlockEntity(b) instanceof RandomizableContainerBlockEntity be) || be.getLootTable() != null;
                if (full) { keep.remove(m.getUUID()); continue; }   // unopened: its loot is still waiting
                var info = sb.getPlayerScoreInfo(m, ct);
                long left = info == null ? 0 : CRATE_TICKS - (now - info.value());
                show(lvl, m, b, label(left, true), "yellow");
            }
        }
        // labels for crates nobody is near any more (or that restocked): gone
        for (Iterator<Map.Entry<UUID, UUID>> it = LABELS.entrySet().iterator(); it.hasNext(); ) {
            var e = it.next();
            if (keep.contains(e.getKey())) continue;
            Entity d = lvl.getEntity(e.getValue());
            if (d != null) d.discard();
            SHOWN.remove(e.getValue()); it.remove();
        }
    }

    static void show(ServerLevel lvl, Marker m, BlockPos b, String text, String color) {
        UUID id = LABELS.get(m.getUUID());
        Entity d = id == null ? null : lvl.getEntity(id);
        String json = "{text:\"" + text + "\",color:\"" + color + "\"}";
        if (d == null) {
            String tag = "ez.ct_" + m.getUUID().toString().substring(0, 8);
            Plots.run(lvl.getServer(), String.format(Locale.ROOT,
                    "execute in lostcities:lostcity run summon minecraft:text_display %.1f %.2f %.1f {Tags:[\"ez.cratetimer\",\"%s\"],billboard:\"center\",text:%s,"
                            + "transformation:{left_rotation:[0f,0f,0f,1f],right_rotation:[0f,0f,0f,1f],translation:[0f,0f,0f],scale:[0.6f,0.6f,0.6f]}}",
                    b.getX() + 0.5, b.getY() + 1.15, b.getZ() + 0.5, tag, json));
            d = lvl.getEntitiesOfClass(net.minecraft.world.entity.Display.TextDisplay.class, new AABB(b).inflate(1.5),
                    x -> x.entityTags().contains(tag)).stream().findFirst().orElse(null);
            if (d == null) return;
            LABELS.put(m.getUUID(), d.getUUID()); SHOWN.put(d.getUUID(), text);
            return;
        }
        if (text.equals(SHOWN.get(d.getUUID()))) return;
        Plots.run(lvl.getServer(), "data modify entity " + d.getUUID() + " text set value " + json);
        SHOWN.put(d.getUUID(), text);
    }
}

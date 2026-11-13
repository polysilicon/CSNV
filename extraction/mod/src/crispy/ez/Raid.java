package crispy.ez;

import net.fabricmc.fabric.api.command.v2.CommandRegistrationCallback;
import net.fabricmc.fabric.api.entity.event.v1.ServerLivingEntityEvents;
import net.fabricmc.fabric.api.event.lifecycle.v1.ServerTickEvents;
import net.minecraft.ChatFormatting;
import net.minecraft.commands.Commands;
import net.minecraft.network.chat.Component;
import net.minecraft.network.chat.MutableComponent;
import net.minecraft.server.MinecraftServer;
import net.minecraft.server.level.ServerPlayer;
import net.minecraft.world.entity.Entity;
import net.minecraft.world.entity.LivingEntity;
import net.minecraft.world.entity.player.Inventory;
import net.minecraft.world.entity.player.Player;
import net.minecraft.world.item.ItemStack;
import net.minecraft.world.phys.Vec3;
import org.slf4j.Logger;
import org.slf4j.LoggerFactory;

import java.util.HashMap;
import java.util.Map;
import java.util.UUID;

import static crispy.ez.Ui.t;

/**
 * One raid per player, from deploying to extracting or dying (1.1.0). The datapack calls /ezhook deploy|extract|died
 * as the player. Tracks distance and kills, works out loot value (valuables at the Broker's price plus coins carried),
 * pays the hot-extract bonus and contract rewards, and ends with a recap in chat. Standout runs are announced in game
 * and logged as "<name> has completed the challenge [...]", which the Discord bot posts like an advancement.
 */
final class Raid {
    private Raid() {}

    static final Logger LOG = LoggerFactory.getLogger("crispy-extraction");
    static final String[] TYPES = {"infected", "bandit", "raider", "rifleman", "boss"};
    static final Map<String, String> TYPE_NAME = Map.of("infected", "Infected", "bandit", "Bandit Gunners", "raider", "Raiders",
            "rifleman", "Riflemen", "boss", "the Commander", "player", "players");

    static final class State {
        long start = System.currentTimeMillis();
        double dist; Vec3 last;
        final Map<String, Integer> kills = new HashMap<>();
        boolean bossPresent;        // within 48 blocks when the Commander died
        boolean radioUsed;          // Field Radio: one exact event location per raid
        boolean warnedEdge;
        int kills() { return kills.values().stream().mapToInt(Integer::intValue).sum(); }
    }
    static final Map<UUID, State> RAIDS = new HashMap<>();
    static State of(Player p) { return RAIDS.get(p.getUUID()); }
    static boolean raiding(Player p) { return p.entityTags().contains("ez.raid"); }

    static void init() {
        CommandRegistrationCallback.EVENT.register((d, ctx, env) -> d.register(Commands.literal("ezhook")
                .requires(Commands.hasPermission(Commands.LEVEL_GAMEMASTERS))
                .then(Commands.literal("deploy").executes(c -> { if (c.getSource().getEntity() instanceof ServerPlayer p) deploy(p); return 1; }))
                .then(Commands.literal("extract").executes(c -> { if (c.getSource().getEntity() instanceof ServerPlayer p) extract(p); return 1; }))
                .then(Commands.literal("died").executes(c -> { if (c.getSource().getEntity() instanceof ServerPlayer p) died(p); return 1; }))
                .then(Commands.literal("wave").executes(c -> { if (c.getSource().getEntity() instanceof ServerPlayer p) Revive.wave(p, true); return 1; }))
                .then(Commands.literal("wavetest").executes(c -> { if (Revive.testPlayer != null) Revive.wave(Revive.testPlayer, true); return 1; }))
                .then(Commands.literal("wave2").executes(c -> { if (c.getSource().getEntity() instanceof ServerPlayer p) Revive.wave(p, false); return 1; }))));
        ServerLivingEntityEvents.AFTER_DEATH.register(Raid::onDeath);
        ServerTickEvents.END_SERVER_TICK.register(server -> {
            if (server.getTickCount() % 20 != 0) return;
            for (ServerPlayer p : server.getPlayerList().getPlayers()) {
                State st = of(p);
                if (st == null || !raiding(p)) continue;
                Vec3 now = p.position();
                if (st.last != null) {
                    double dx = now.x - st.last.x, dz = now.z - st.last.z, h = Math.sqrt(dx * dx + dz * dz);
                    if (h < 40) st.dist += h;   // teleports don't count
                }
                st.last = now;
            }
        });
    }

    static void deploy(ServerPlayer p) {
        Flow.mark(p, "helipad");
        State st = new State();
        st.last = p.position();
        RAIDS.put(p.getUUID(), st);
        Contracts.onDeploy(p);
    }

    static void onDeath(LivingEntity dead, net.minecraft.world.damagesource.DamageSource src) {
        if (!dead.level().dimension().equals(Zone.CITY)) return;
        Entity k = src.getEntity();
        ServerPlayer killer = k instanceof ServerPlayer sp ? sp : dead.getKillCredit() instanceof ServerPlayer sp2 ? sp2 : null;
        String type = null;
        if (dead instanceof Player) type = "player";
        else for (String tag : dead.entityTags()) if (tag.startsWith("ez.t_")) type = tag.substring(5);
        if (dead.entityTags().contains("ez.boss")) Boss.onDeath(dead, killer);
        if (killer == null || type == null || killer == dead) return;
        State st = of(killer);
        if (st != null) st.kills.merge(type, 1, Integer::sum);
        Contracts.onKill(killer, type);
    }

    /** Broker value of the valuables carried, and coins carried. */
    static int[] loot(ServerPlayer p) {
        Map<String, Integer> price = new HashMap<>();
        Shops.load(p.level().getServer());
        Shops.Shop fence = Shops.SHOPS.get("fence");
        if (fence != null) for (Shops.Sell s : fence.sell()) price.put(s.key(), s.price());
        int val = 0;
        Inventory inv = p.getInventory();
        for (int i = 0; i < inv.getContainerSize(); i++) {
            ItemStack s = inv.getItem(i);
            Integer pr = price.get(Shops.ezKey(s));
            if (pr != null) val += pr * s.getCount();
        }
        return new int[]{val, Coins.count(p)};
    }

    static Entity nearest(ServerPlayer p, String tag, double r) {
        return p.level().getEntitiesOfClass(net.minecraft.world.entity.Marker.class, p.getBoundingBox().inflate(r), e -> e.entityTags().contains(tag))
                .stream().findFirst().orElse(null);
    }

    static void extract(ServerPlayer p) {
        State st = RAIDS.remove(p.getUUID());
        if (st == null) st = new State();
        Entity ex = nearest(p, "ez.exfil", 6);
        String where = ex != null && ex.hasCustomName() ? ex.getCustomName().getString() : "an extraction point";
        int[] loot = loot(p);
        int bonus = 0;
        if (ex != null && ex.entityTags().contains("ez.hot")) bonus = loot[0];   // hot extract: valuables pay double
        Contracts.Result cr = Contracts.onExtract(p, where, st);
        if (bonus > 0) Coins.give(p, bonus);
        if (cr != null && cr.reward() > 0) Coins.give(p, cr.reward());
        int total = loot[0] + loot[1] + bonus + (cr != null ? cr.reward() : 0);
        recap(p, st, true, where, loot, bonus, cr, total);
        boolean standout = total >= 250 || st.kills() >= 8 || st.kills.containsKey("boss") || bonus >= 60;
        if (standout) announce(p, st, total, where);
    }

    static void died(ServerPlayer p) {
        State st = RAIDS.remove(p.getUUID());
        if (st == null) return;
        Contracts.Result cr = Contracts.onDied(p);
        recap(p, st, false, null, null, 0, cr, 0);
    }

    static String time(long ms) { long s = ms / 1000; return (s / 60) + ":" + String.format("%02d", s % 60); }
    static String dist(double m) { return m >= 1000 ? String.format("%.1f km", m / 1000) : Math.round(m) + " m"; }
    static String killLine(State st) {
        if (st.kills.isEmpty()) return "none";
        StringBuilder b = new StringBuilder().append(st.kills()).append(" (");
        boolean first = true;
        for (String k : new String[]{"player", "boss", "rifleman", "raider", "bandit", "infected"}) {
            Integer n = st.kills.get(k);
            if (n == null) continue;
            b.append(first ? "" : ", ").append(n).append(" ").append(k.equals("boss") ? "Commander" : TYPE_NAME.get(k));
            first = false;
        }
        return b.append(")").toString();
    }

    static void recap(ServerPlayer p, State st, boolean out, String where, int[] loot, int bonus, Contracts.Result cr, int total) {
        p.sendSystemMessage(t("━━━━━━━━ RAID RECAP ━━━━━━━━", out ? ChatFormatting.GREEN : ChatFormatting.RED, ChatFormatting.BOLD));
        p.sendSystemMessage(t(out ? "✈ Extracted from " + where : "✖ Killed in action", out ? ChatFormatting.GREEN : ChatFormatting.RED)
                .append(t("   ⏱ " + time(System.currentTimeMillis() - st.start) + "   ⇄ " + dist(st.dist), ChatFormatting.GRAY)));
        p.sendSystemMessage(t("⚔ Kills: ", ChatFormatting.GRAY).append(t(killLine(st), ChatFormatting.WHITE)));
        if (out) {
            MutableComponent l = t("💰 Loot: ", ChatFormatting.GRAY).append(t(Coins.fmt(loot[0] + loot[1]), ChatFormatting.GOLD, ChatFormatting.BOLD))
                    .append(t("  (valuables " + loot[0] + " + coins " + loot[1] + ")", ChatFormatting.DARK_GRAY));
            p.sendSystemMessage(l);
            if (bonus > 0) p.sendSystemMessage(t("🔥 Hot extract bonus: +" + Coins.fmt(bonus) + " (paid now)", ChatFormatting.GOLD));
        }
        if (cr != null) p.sendSystemMessage(t("📋 Contract: " + cr.text(), cr.reward() > 0 ? ChatFormatting.GREEN : ChatFormatting.RED));
        if (out) p.sendSystemMessage(t("Raid total: " + Coins.fmt(total), ChatFormatting.YELLOW, ChatFormatting.BOLD));
        p.sendSystemMessage(t("━━━━━━━━━━━━━━━━━━━━━━━━━━", out ? ChatFormatting.GREEN : ChatFormatting.RED));
    }

    static void announce(ServerPlayer p, State st, int total, String where) {
        String name = p.getGameProfile().name();
        String what = Coins.fmt(total) + " of loot" + (st.kills() > 0 ? ", " + st.kills() + " kills" : "")
                + (st.kills.containsKey("boss") ? ", killed the Commander" : "");
        MinecraftServer server = p.level().getServer();
        server.getPlayerList().broadcastSystemMessage(t("★ ", ChatFormatting.GOLD).append(t(name, ChatFormatting.WHITE, ChatFormatting.BOLD))
                .append(t(" extracted from " + where + " with " + what + "!", ChatFormatting.GOLD)), false);
        // the Discord bot posts "<player> has completed the challenge [...]" lines like an advancement
        LOG.info("{} has completed the challenge [Standout raid: {} from {}]", name, what, where);
    }

    static Component compass(int dx, int dz) {
        String[] d = {"east", "south-east", "south", "south-west", "west", "north-west", "north", "north-east"};
        int i = (int) Math.round(Math.atan2(dz, dx) / (Math.PI / 4));
        return Component.literal(d[(i + 8) % 8]);
    }
}

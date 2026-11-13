package crispy.ez;

import net.fabricmc.fabric.api.entity.event.v1.ServerLivingEntityEvents;
import net.fabricmc.fabric.api.event.lifecycle.v1.ServerTickEvents;
import net.fabricmc.fabric.api.event.player.AttackEntityCallback;
import net.fabricmc.fabric.api.event.player.UseBlockCallback;
import net.fabricmc.fabric.api.event.player.UseEntityCallback;
import net.fabricmc.fabric.api.event.player.UseItemCallback;
import net.fabricmc.fabric.api.networking.v1.ServerPlayConnectionEvents;
import net.minecraft.ChatFormatting;
import net.minecraft.core.BlockPos;
import net.minecraft.core.particles.DustParticleOptions;
import net.minecraft.resources.Identifier;
import net.minecraft.server.MinecraftServer;
import net.minecraft.server.level.ServerLevel;
import net.minecraft.server.level.ServerPlayer;
import net.minecraft.tags.DamageTypeTags;
import net.minecraft.world.InteractionResult;
import net.minecraft.world.damagesource.DamageSource;
import net.minecraft.world.effect.MobEffectInstance;
import net.minecraft.world.effect.MobEffects;
import net.minecraft.world.entity.Entity;
import net.minecraft.world.entity.LivingEntity;
import net.minecraft.world.entity.Mob;
import net.minecraft.world.entity.ai.attributes.AttributeModifier;
import net.minecraft.world.entity.ai.attributes.Attributes;
import net.minecraft.world.entity.item.ItemEntity;
import net.minecraft.world.entity.player.Inventory;
import net.minecraft.world.item.ItemStack;

import java.util.*;

import static crispy.ez.Ui.t;

/**
 * Downed, revived or finished off (1.8.17). In the zone a raiding player who takes a fatal hit goes down instead of
 * dying: on the ground (barely moving, no shooting, no items, can't extract), ignored by raiders, bleeding out over
 * BLEED seconds. Then:
 *  - another player crouches next to them for REVIVE seconds: back up with a few hearts;
 *  - they carry a Self-Revive Injector (ez:selfrevive) and hold crouch for SELF seconds: it's used up, back up;
 *  - another player hits them: executed on the spot, everything they carried drops for the taking;
 *  - the timer runs out (or they log out): they die as before.
 * Going down again within GRACE seconds of getting up is fatal. The blowout and /kill still kill outright.
 * You can carry one Self-Revive Injector; extras are dropped.
 * Extraction waves: when someone starts extracting, the flare draws raiders from that ring (datapack exfil/hold calls
 * /ezhook wave, and wave2 at the halfway mark).
 */
final class Revive {
    private Revive() {}

    static final int BLEED = 45, REVIVE = 5, SELF = 3, GRACE = 20;
    static final double REACH = 2.2;
    static final Identifier MOD_ID = Identifier.fromNamespaceAndPath("crispy", "downed");

    static final class Down {
        long until;              // bleed-out, server tick
        int help, self;          // ticks of reviving / self-reviving so far
        UUID helper;
    }
    static final Map<UUID, Down> DOWN = new HashMap<>();
    static final Map<UUID, Long> UP_AT = new HashMap<>();      // server tick they last got up
    static final int GETUP = 4;                                 // 1.8.19: seconds after getting up that raiders still leave you alone (tag ez.getup)
    static final double SCATTER = 14, CALM = 32;                // raiders closer than SCATTER walk off; none within CALM keeps you as a target
    static final Map<UUID, ServerPlayer> FINISH_BY = new HashMap<>();   // to finish off at the end of this tick (null value: bled out)
    static final Set<UUID> FINISHING = new HashSet<>();
    static int waves;

    static boolean downed(ServerPlayer p) { return DOWN.containsKey(p.getUUID()); }
    static boolean inZoneRaid(ServerPlayer p) { return p.level().dimension().equals(Zone.CITY) && Raid.raiding(p); }

    static void init() {
        ServerLivingEntityEvents.ALLOW_DEATH.register((e, src, amt) -> {
            if (!(e instanceof ServerPlayer p) || FINISHING.contains(p.getUUID())) return true;
            if (!inZoneRaid(p) || src.is(DamageTypeTags.BYPASSES_INVULNERABILITY) || downed(p)) return true;
            long now = p.level().getServer().getTickCount();
            Long up = UP_AT.get(p.getUUID());
            if (up != null && now - up < GRACE * 20L) return true;
            goDown(p, src);
            return false;
        });
        ServerLivingEntityEvents.ALLOW_DAMAGE.register((e, src, amt) -> {
            if (!(e instanceof ServerPlayer p) || !downed(p) || FINISHING.contains(p.getUUID())) return true;
            if (src.is(DamageTypeTags.BYPASSES_INVULNERABILITY)) return true;
            if (src.getEntity() instanceof ServerPlayer k && k != p && !downed(k)) FINISH_BY.put(p.getUUID(), k);   // executed
            return false;   // raiders, falls, radiation: nothing more happens to someone on the ground
        });
        UseItemCallback.EVENT.register((pl, w, hand) -> pl instanceof ServerPlayer p && downed(p) ? InteractionResult.FAIL : InteractionResult.PASS);
        UseBlockCallback.EVENT.register((pl, w, hand, hit) -> pl instanceof ServerPlayer p && downed(p) ? InteractionResult.FAIL : InteractionResult.PASS);
        UseEntityCallback.EVENT.register((pl, w, hand, en, hit) -> pl instanceof ServerPlayer p && downed(p) ? InteractionResult.FAIL : InteractionResult.PASS);
        AttackEntityCallback.EVENT.register((pl, w, hand, en, hit) -> pl instanceof ServerPlayer p && downed(p) ? InteractionResult.FAIL : InteractionResult.PASS);
        ServerPlayConnectionEvents.DISCONNECT.register((h, server) -> {
            ServerPlayer p = h.getPlayer();
            if (downed(p)) { p.sendSystemMessage(t("You logged out while downed.", ChatFormatting.RED)); finish(p, null); }
        });
        ServerPlayConnectionEvents.JOIN.register((h, sender, server) -> clear(h.getPlayer()));   // after a restart nobody is still down
        ServerTickEvents.END_SERVER_TICK.register(server -> {
            try { tick(server); } catch (Exception ex) { System.err.println("[crispy-extraction] revive tick failed: " + ex); }
        });
    }

    // ---------------------------------------------------------------- down, up, finished
    static void goDown(ServerPlayer p, DamageSource src) {
        MinecraftServer server = p.level().getServer();
        p.setHealth(1f);
        p.clearFire();
        Down d = new Down();
        d.until = server.getTickCount() + BLEED * 20L;
        DOWN.put(p.getUUID(), d);
        p.addTag("ez.downed");
        p.addEffect(new MobEffectInstance(MobEffects.SLOWNESS, BLEED * 20 + 40, 5, false, false, true));
        p.addEffect(new MobEffectInstance(MobEffects.WEAKNESS, BLEED * 20 + 40, 4, false, false, true));
        var sp = p.getAttribute(Attributes.JUMP_STRENGTH);
        if (sp != null) sp.addOrUpdateTransientModifier(new AttributeModifier(MOD_ID, -1.0, AttributeModifier.Operation.ADD_MULTIPLIED_TOTAL));
        Plots.run(server, "scoreboard players set " + p.getScoreboardName() + " ez.ex 0");   // extracting stops
        p.connection.send(new net.minecraft.network.protocol.game.ClientboundSetTitleTextPacket(t("DOWNED", ChatFormatting.DARK_RED, ChatFormatting.BOLD)));
        p.connection.send(new net.minecraft.network.protocol.game.ClientboundSetSubtitleTextPacket(t(
                has(p) ? "Hold crouch 3 s to use your Self-Revive" : "Wait for another player to revive you", ChatFormatting.GRAY)));
        Ui.sound(p, net.minecraft.sounds.SoundEvents.PLAYER_HURT, 1f, 0.6f);
        for (ServerPlayer o : server.getPlayerList().getPlayers()) {
            if (o == p || !inZoneRaid(o) || o.distanceTo(p) > 64) continue;
            o.sendSystemMessage(t("✚ " + p.getScoreboardName() + " is down " + (int) o.distanceTo(p) + " blocks away! Crouch next to them for "
                    + REVIVE + " s to revive them... or hit them to finish them off.", ChatFormatting.GOLD));
        }
        Trace.d(p, "downed by " + src.getMsgId());
    }
    static void up(ServerPlayer p, String how) {
        clear(p);
        p.setHealth(6f);
        p.addEffect(new MobEffectInstance(MobEffects.RESISTANCE, 60, 2, false, false, true));
        UP_AT.put(p.getUUID(), (long) p.level().getServer().getTickCount());
        p.addTag("ez.getup");
        calm(p, true);
        p.sendSystemMessage(t("You're back on your feet (" + how + "). Go down again within " + GRACE + " s and it's over.", ChatFormatting.GREEN));
        Ui.sound(p, net.minecraft.sounds.SoundEvents.PLAYER_LEVELUP, 0.7f, 1.4f);
        Trace.d(p, "revived: " + how);
    }
    static void clear(ServerPlayer p) {
        if (!UP_AT.containsKey(p.getUUID())) p.removeTag("ez.getup");
        DOWN.remove(p.getUUID());
        p.removeTag("ez.downed");
        var sp = p.getAttribute(Attributes.JUMP_STRENGTH);
        if (sp != null) sp.removeModifier(MOD_ID);
        MobEffectInstance s = p.getEffect(MobEffects.SLOWNESS);
        if (s != null && s.getAmplifier() == 5) p.removeEffect(MobEffects.SLOWNESS);
        MobEffectInstance w = p.getEffect(MobEffects.WEAKNESS);
        if (w != null && w.getAmplifier() == 4) p.removeEffect(MobEffects.WEAKNESS);
    }
    /** Dies for real: executed by killer, or (killer null) bled out. */
    static void finish(ServerPlayer p, ServerPlayer killer) {
        clear(p);
        FINISHING.add(p.getUUID());
        try {
            p.invulnerableTime = 0;
            DamageSource src = killer != null ? p.damageSources().playerAttack(killer) : p.damageSources().genericKill();
            if (killer != null) {
                killer.sendSystemMessage(t("You finished off " + p.getScoreboardName() + ". Their gear is on the ground.", ChatFormatting.RED));
                p.sendSystemMessage(t(killer.getScoreboardName() + " finished you off.", ChatFormatting.DARK_RED));
            } else p.sendSystemMessage(t("You bled out.", ChatFormatting.DARK_RED));
            p.hurtServer((ServerLevel) p.level(), src, Float.MAX_VALUE);
            if (p.isAlive()) { p.setHealth(0f); p.die(src); }   // armour or a mod soaked it: make sure
        } finally { FINISHING.remove(p.getUUID()); }
        Trace.d(p, killer != null ? "executed by " + killer.getScoreboardName() : "bled out");
    }

    // ---------------------------------------------------------------- every tick
    static void tick(MinecraftServer server) {
        long now = server.getTickCount();
        if (!FINISH_BY.isEmpty()) {
            var todo = new HashMap<>(FINISH_BY); FINISH_BY.clear();
            todo.forEach((id, k) -> { ServerPlayer p = server.getPlayerList().getPlayer(id); if (p != null && downed(p)) finish(p, k); });
        }
        for (UUID id : new ArrayList<>(DOWN.keySet())) {
            ServerPlayer p = server.getPlayerList().getPlayer(id);
            Down d = DOWN.get(id);
            if (p == null || !p.isAlive()) { DOWN.remove(id); continue; }
            if (!inZoneRaid(p)) { clear(p); continue; }   // extracted / moved out somehow
            if (now >= d.until) { finish(p, null); continue; }
            ServerLevel lvl = (ServerLevel) p.level();
            // revived by someone crouching next to them
            ServerPlayer helper = null;
            for (ServerPlayer o : lvl.players())
                if (o != p && o.isAlive() && !downed(o) && o.isShiftKeyDown() && !o.isSpectator() && o.distanceTo(p) <= REACH) { helper = o; break; }
            if (helper != null && helper.getUUID().equals(d.helper)) d.help++;
            else { d.help = helper != null ? 1 : 0; d.helper = helper != null ? helper.getUUID() : null; }
            // or by their own injector
            if (p.isShiftKeyDown() && has(p)) d.self++; else d.self = 0;
            if (d.help >= REVIVE * 20) {
                ServerPlayer h = helper;
                up(p, "revived by " + h.getScoreboardName());
                h.sendSystemMessage(t("You revived " + p.getScoreboardName() + ".", ChatFormatting.GREEN));
                continue;
            }
            if (d.self >= SELF * 20) {
                Shops.take(p, s -> "selfrevive".equals(Shops.ezKey(s)), 1);
                up(p, "Self-Revive Injector");
                continue;
            }
            if (now % 5 == 0) {
                long left = (d.until - now) / 20;
                String msg = d.help > 0 ? "✚ Being revived... " + bar(d.help, REVIVE * 20)
                        : d.self > 0 ? "✚ Injecting... " + bar(d.self, SELF * 20)
                        : "DOWNED: bleeding out in " + left + " s" + (has(p) ? "  (hold crouch: Self-Revive)" : "");
                p.sendSystemMessage(t(msg, d.help > 0 || d.self > 0 ? ChatFormatting.GREEN : ChatFormatting.RED), true);
                if (helper != null) helper.sendSystemMessage(t("✚ Reviving " + p.getScoreboardName() + "... " + bar(d.help, REVIVE * 20), ChatFormatting.GREEN), true);
                lvl.sendParticles(new DustParticleOptions(0xB01010, 1.2f), p.getX(), p.getY() + 0.3, p.getZ(), 4, 0.3, 0.1, 0.3, 0);
            }
        }
        // 1.8.19: raiders don't crowd someone on the ground, or jump them the moment they're up
        for (ServerPlayer p : server.getPlayerList().getPlayers()) {
            if (p.entityTags().contains("ez.getup")) {
                Long up = UP_AT.get(p.getUUID());
                if (up == null || now - up >= GETUP * 20L) { p.removeTag("ez.getup"); continue; }
            } else if (!downed(p)) continue;
            calm(p, now % 10 == 0);
        }
        if (now % 20 == 0) for (ServerPlayer p : server.getPlayerList().getPlayers()) limit(p);
        if (now % 1200 == 0) UP_AT.values().removeIf(t0 -> now - t0 > GRACE * 20L);
    }
    /** Raiders around p forget them; with scatter, the ones closer than SCATTER walk off to SCATTER+6 blocks away. */
    static void calm(ServerPlayer p, boolean scatter) {
        ServerLevel lvl = (ServerLevel) p.level();
        for (Mob m : lvl.getEntitiesOfClass(Mob.class, p.getBoundingBox().inflate(CALM), e -> e.entityTags().contains("ez.ai") || e.entityTags().contains("ez.wave"))) {
            if (m.getTarget() == p) m.setTarget(null);
            if (!scatter || m.distanceTo(p) >= SCATTER) continue;
            backOff(lvl, m, p);
        }
    }
    /** Walk m off to open ground SCATTER+6 blocks from p (straight away first, then wider angles); no path: a shove away. */
    static boolean backOff(ServerLevel lvl, Mob m, ServerPlayer p) {
        if (m.getNavigation().isInProgress() && m.getNavigation().getTargetPos() != null
                && m.getNavigation().getTargetPos().distSqr(p.blockPosition()) >= SCATTER * SCATTER) return true;   // already leaving
        double base = Math.atan2(m.getZ() - p.getZ(), m.getX() - p.getX());
        for (double off : new double[]{0, 0.6, -0.6, 1.2, -1.2, 1.8, -1.8})
            for (double go : new double[]{SCATTER + 6, SCATTER + 2}) {
                BlockPos b = ground(lvl, (int) Math.floor(p.getX() + Math.cos(base + off) * go), m.getBlockY(), (int) Math.floor(p.getZ() + Math.sin(base + off) * go));
                if (b == null) continue;
                var path = m.getNavigation().createPath(b, 1);
                if (path != null && path.canReach() && m.getNavigation().moveTo(path, 1.2)) return true;
            }
        double dx = m.getX() - p.getX(), dz = m.getZ() - p.getZ(), len = Math.max(0.3, Math.hypot(dx, dz));
        m.setDeltaMovement(dx / len * 0.8, 0.25, dz / len * 0.8);
        m.hurtMarked = true;
        return false;
    }
    static String bar(int n, int of) { int k = Math.min(10, n * 10 / of); return "█".repeat(k) + "░".repeat(10 - k); }

    // ---------------------------------------------------------------- the injector: one at a time
    static boolean has(ServerPlayer p) { return Shops.count(p, s -> "selfrevive".equals(Shops.ezKey(s))) > 0; }
    static void limit(ServerPlayer p) {
        Inventory inv = p.getInventory();
        boolean kept = false; int dropped = 0;
        for (int i = 0; i < inv.getContainerSize(); i++) {
            ItemStack s = inv.getItem(i);
            if (s.isEmpty() || !"selfrevive".equals(Shops.ezKey(s))) continue;
            int keep = kept ? 0 : 1; kept = true;
            if (s.getCount() <= keep) continue;
            ItemStack extra = s.split(s.getCount() - keep);
            dropped += extra.getCount();
            ItemEntity ie = p.drop(extra, false);
            if (ie != null) ie.setPickUpDelay(100);
        }
        if (dropped > 0) { inv.setChanged(); p.sendSystemMessage(t("You can carry only one Self-Revive Injector: the extra is on the ground.", ChatFormatting.GOLD)); }
    }

    // ---------------------------------------------------------------- extraction waves
    /** Raiders from the extracting player's ring, 10-18 blocks out on open ground near their height, coming for them. */
    static int wave(ServerPlayer p, boolean big) {
        if (!p.level().dimension().equals(Zone.CITY)) return 0;
        ServerLevel lvl = (ServerLevel) p.level();
        MinecraftServer server = lvl.getServer();
        int tier = Math.max(1, Zone.tier(p.getBlockX(), p.getBlockZ()));
        int n = big ? 2 + tier * 2 : 1 + tier;
        String at = String.format(Locale.ROOT, "execute in lostcities:lostcity positioned %d %d %d run ", p.getBlockX(), p.getBlockY(), p.getBlockZ());
        for (int i = 0; i < n; i++) Plots.run(server, at + "function ez:spawner/ring" + tier);
        List<Entity> fresh = lvl.getEntities((Entity) null, p.getBoundingBox().inflate(4), e -> e.entityTags().contains("ez.newai"));
        Random r = new Random();
        int placed = 0;
        for (Entity m : fresh) {
            m.removeTag("ez.newai"); m.addTag("ez.wave");
            BlockPos spot = null;
            // 1.8.19: 26-38 blocks out (they were on top of you at 10-18), out of sight of the player if possible
            for (int tries = 0; tries < 60 && spot == null; tries++) {
                double a = r.nextDouble() * Math.PI * 2, dist = WAVE_MIN + r.nextDouble() * (WAVE_MAX - WAVE_MIN);
                BlockPos b = ground(lvl, (int) Math.floor(p.getX() + Math.cos(a) * dist), p.getBlockY(), (int) Math.floor(p.getZ() + Math.sin(a) * dist));
                if (b != null && (tries >= 40 || !sees(lvl, b, p))) spot = b;
            }
            if (spot == null) { m.discard(); continue; }   // nowhere to stand: better none than one inside the player
            m.teleportTo(spot.getX() + 0.5, spot.getY(), spot.getZ() + 0.5);
            if (m instanceof Mob mob) mob.setTarget(p);
            placed++;
        }
        waves++;
        for (ServerPlayer o : lvl.players()) {
            if (!Raid.raiding(o) || o.distanceTo(p) > 48) continue;
            o.connection.send(new net.minecraft.network.protocol.game.ClientboundSetTitleTextPacket(t(big ? "INCOMING" : "MORE INCOMING", ChatFormatting.RED, ChatFormatting.BOLD)));
            o.connection.send(new net.minecraft.network.protocol.game.ClientboundSetSubtitleTextPacket(t("The flare drew " + placed + " raiders: hold the extraction point", ChatFormatting.GRAY)));
            Ui.sound(o, net.minecraft.sounds.SoundEvents.RAID_HORN.value(), 0.6f, 1.2f);
        }
        Trace.d(p, "extraction wave " + (big ? "1" : "2") + ": " + placed + " raiders (ring " + tier + ")");
        return placed;
    }
    static final double WAVE_MIN = 26, WAVE_MAX = 38;
    static boolean sees(ServerLevel lvl, BlockPos b, ServerPlayer p) {
        var from = new net.minecraft.world.phys.Vec3(b.getX() + 0.5, b.getY() + 1.6, b.getZ() + 0.5);
        return lvl.clip(new net.minecraft.world.level.ClipContext(from, p.getEyePosition(), net.minecraft.world.level.ClipContext.Block.COLLIDER,
                net.minecraft.world.level.ClipContext.Fluid.NONE, p)).getType() == net.minecraft.world.phys.HitResult.Type.MISS;
    }
    /** Open ground near height y (two clear blocks over a solid one), or null. */
    static BlockPos ground(ServerLevel lvl, int x, int y, int z) {
        if (!lvl.hasChunk(x >> 4, z >> 4)) return null;
        for (int dy : new int[]{0, 1, -1, 2, -2, 3, -3, 4, -4, 5, 6}) {
            BlockPos b = new BlockPos(x, y + dy, z);
            if (lvl.getBlockState(b.below()).isSolidRender() && lvl.getBlockState(b).getCollisionShape(lvl, b).isEmpty()
                    && lvl.getBlockState(b.above()).getCollisionShape(lvl, b.above()).isEmpty()) return b;
        }
        return null;
    }
}

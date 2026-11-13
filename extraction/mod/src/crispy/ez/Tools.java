package crispy.ez;

import net.fabricmc.fabric.api.event.lifecycle.v1.ServerTickEvents;
import net.fabricmc.fabric.api.event.player.UseItemCallback;
import net.minecraft.ChatFormatting;
import net.minecraft.core.particles.ParticleTypes;
import net.minecraft.network.protocol.game.ClientboundSetEntityMotionPacket;
import net.minecraft.server.level.ServerLevel;
import net.minecraft.server.level.ServerPlayer;
import net.minecraft.world.InteractionResult;
import net.minecraft.world.effect.MobEffectInstance;
import net.minecraft.world.effect.MobEffects;
import net.minecraft.world.entity.Entity;
import net.minecraft.world.entity.EntityType;
import net.minecraft.world.entity.EquipmentSlot;
import net.minecraft.world.entity.projectile.throwableitemprojectile.Snowball;
import net.minecraft.world.item.ItemStack;
import net.minecraft.world.level.ClipContext;
import net.minecraft.world.phys.BlockHitResult;
import net.minecraft.world.phys.HitResult;
import net.minecraft.world.phys.Vec3;

import java.util.*;

import static crispy.ez.Ui.t;

/**
 * Zone tools (1.8.0), made at the Tool Bench / Reloading Bench:
 *  - Grappling Hook: right-click a block up to 28 away (in the zone) and you're pulled to it; a moment of slow
 *    falling so a short landing doesn't hurt. 2 s cooldown, 40 uses.
 *  - Repair Kit: right-click to mend every armour piece you wear by half its durability.
 *  - Smoke Grenade (a thrown snowball with custom_data ez:smoke): where it lands, 15 s of thick smoke and a marker
 *    tagged ez.smoke that raider gunfire can't pass (datapack ai/ray).
 * The Parachute (a consumable: slow falling), Rope Ladder (ladders) and Breaching Hammer (a tool component) need no code.
 */
final class Tools {
    private Tools() {}

    static final double REACH = 28;
    static final Map<UUID, Vec3> FLYING = new HashMap<>();   // smoke grenades in the air: last position
    record Smoke(ServerLevel lvl, Vec3 at, long until, UUID marker) {}
    static final List<Smoke> SMOKES = new ArrayList<>();

    static void init() {
        UseItemCallback.EVENT.register((pl, world, hand) -> {
            if (!(pl instanceof ServerPlayer p)) return InteractionResult.PASS;
            ItemStack st = p.getItemInHand(hand);
            String k = Shops.ezKey(st);
            if ("grapple".equals(k)) return grapple(p, st, hand);
            if ("repairkit".equals(k)) return repair(p, st);
            return InteractionResult.PASS;
        });
        ServerTickEvents.END_SERVER_TICK.register(server -> {
            try { smokeTick(server); }
            catch (Exception ex) { System.err.println("[crispy-extraction] tools tick failed: " + ex); }
        });
    }

    static void smokeTick(net.minecraft.server.MinecraftServer server) {
            ServerLevel city = server.getLevel(Zone.CITY);
            if (city == null) return;
            // smoke grenades: follow them while they fly, puff where they stop
            Set<UUID> seen = new HashSet<>();
            for (Entity e : city.getEntities(net.minecraft.world.level.entity.EntityTypeTest.forClass(Snowball.class), s -> "smoke".equals(Shops.ezKey(s.getItem())))) {
                FLYING.put(e.getUUID(), e.position()); seen.add(e.getUUID());
            }
            for (Iterator<Map.Entry<UUID, Vec3>> it = FLYING.entrySet().iterator(); it.hasNext(); ) {
                var en = it.next();
                if (seen.contains(en.getKey())) continue;
                it.remove();
                Vec3 at = en.getValue();
                Plots.run(server, String.format(Locale.ROOT, "execute in lostcities:lostcity run summon minecraft:marker %.2f %.2f %.2f {Tags:[\"ez.smoke\"]}", at.x, at.y, at.z));
                UUID id = city.getEntitiesOfClass(net.minecraft.world.entity.Marker.class, new net.minecraft.world.phys.AABB(at, at).inflate(1),
                        m -> m.entityTags().contains("ez.smoke")).stream().findFirst().map(Entity::getUUID).orElse(null);
                SMOKES.add(new Smoke(city, at, server.getTickCount() + 300, id));
                city.playSound(null, at.x, at.y, at.z, net.minecraft.sounds.SoundEvents.FIRE_EXTINGUISH, net.minecraft.sounds.SoundSource.PLAYERS, 1f, 0.6f);
            }
            for (Iterator<Smoke> it = SMOKES.iterator(); it.hasNext(); ) {
                Smoke s = it.next();
                if (server.getTickCount() >= s.until()) {
                    if (s.marker() != null) { Entity m = s.lvl().getEntity(s.marker()); if (m != null) m.discard(); }
                    it.remove(); continue;
                }
                if (server.getTickCount() % 4 == 0)
                    s.lvl().sendParticles(ParticleTypes.CAMPFIRE_COSY_SMOKE, s.at().x, s.at().y + 1, s.at().z, 14, 1.8, 1.2, 1.8, 0.01);
            }
    }

    static InteractionResult grapple(ServerPlayer p, ItemStack st, net.minecraft.world.InteractionHand hand) {
        if (!p.level().dimension().equals(Zone.CITY)) { p.sendSystemMessage(t("The grappling hook is for the zone.", ChatFormatting.RED), true); return InteractionResult.FAIL; }
        if (p.getCooldowns().isOnCooldown(st)) return InteractionResult.FAIL;
        Vec3 eye = p.getEyePosition(), end = eye.add(p.getLookAngle().scale(REACH));
        BlockHitResult hit = p.level().clip(new ClipContext(eye, end, ClipContext.Block.COLLIDER, ClipContext.Fluid.NONE, p));
        if (hit.getType() == HitResult.Type.MISS) { p.sendSystemMessage(t("Nothing to hook onto within " + (int) REACH + " blocks.", ChatFormatting.GRAY), true); return InteractionResult.FAIL; }
        Vec3 to = hit.getLocation().subtract(p.position());
        double dist = to.length();
        Vec3 v = to.normalize().scale(Math.min(2.6, 0.7 + dist * 0.085)).add(0, 0.35, 0);
        p.setDeltaMovement(v);
        p.connection.send(new ClientboundSetEntityMotionPacket(p));
        p.resetFallDistance();
        p.addEffect(new MobEffectInstance(MobEffects.SLOW_FALLING, 30, 0, true, false, false));
        ServerLevel lvl = (ServerLevel) p.level();
        for (double d = 1; d < dist; d += 0.8) { Vec3 pt = eye.add(to.normalize().scale(d)); lvl.sendParticles(ParticleTypes.CRIT, pt.x, pt.y, pt.z, 1, 0, 0, 0, 0); }
        lvl.playSound(null, p.getX(), p.getY(), p.getZ(), net.minecraft.sounds.SoundEvents.CROSSBOW_SHOOT, net.minecraft.sounds.SoundSource.PLAYERS, 1f, 0.7f);
        p.getCooldowns().addCooldown(st, 40);
        st.hurtAndBreak(1, p, hand == net.minecraft.world.InteractionHand.MAIN_HAND ? EquipmentSlot.MAINHAND : EquipmentSlot.OFFHAND);
        Trace.d(p, String.format("grapple %.1f blocks", dist));
        return InteractionResult.SUCCESS;
    }

    static InteractionResult repair(ServerPlayer p, ItemStack kit) {
        int fixed = 0;
        for (EquipmentSlot sl : Armor.WORN) {
            ItemStack a = p.getItemBySlot(sl);
            if (a.isEmpty() || !a.isDamageableItem() || a.getDamageValue() == 0) continue;
            a.setDamageValue(Math.max(0, a.getDamageValue() - a.getMaxDamage() / 2));
            fixed++;
        }
        if (fixed == 0) { p.sendSystemMessage(t("Nothing you're wearing needs mending.", ChatFormatting.GRAY), true); return InteractionResult.FAIL; }
        kit.shrink(1);
        Shops.ok(p, "Mended " + fixed + " armour piece" + (fixed == 1 ? "" : "s") + ".");
        Ui.sound(p, net.minecraft.sounds.SoundEvents.ANVIL_USE, 0.6f, 1.4f);
        return InteractionResult.SUCCESS;
    }
}

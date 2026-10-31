package crispy.falling;

import net.minecraft.ChatFormatting;
import net.minecraft.core.component.DataComponents;
import net.minecraft.nbt.CompoundTag;
import net.minecraft.nbt.ListTag;
import net.minecraft.nbt.NbtOps;
import net.minecraft.nbt.Tag;
import net.minecraft.network.chat.Component;
import net.minecraft.network.chat.MutableComponent;
import net.minecraft.resources.Identifier;
import net.minecraft.resources.RegistryOps;
import net.minecraft.server.MinecraftServer;
import net.minecraft.server.level.ServerLevel;
import net.minecraft.server.level.ServerPlayer;
import net.minecraft.world.damagesource.DamageSource;
import net.minecraft.world.entity.LivingEntity;
import net.minecraft.world.entity.Mob;
import net.minecraft.world.entity.ai.attributes.AttributeInstance;
import net.minecraft.world.entity.ai.attributes.AttributeModifier;
import net.minecraft.world.entity.ai.attributes.Attributes;
import net.minecraft.world.entity.item.ItemEntity;
import net.minecraft.world.entity.player.Player;
import net.minecraft.world.item.ItemStack;
import net.minecraft.world.item.component.CustomData;
import net.minecraft.world.item.component.ItemLore;
import net.minecraft.world.phys.AABB;

import java.util.*;

import static crispy.falling.Ui.t;

/**
 * What makes the resource zones an RPG area:
 * - Zone mobs (tag cs_zone_mob, spawned by the datapack) get a level when first seen: deeper in the Deep Mines is
 *   harder, the Whispering Woods are gentler. Level scales health and damage, shows above the mob with a health bar,
 *   and pays 2 coins per level to the killer. They don't burn in daylight (MobMixin).
 * - Items that drop in a zone (from mined blocks or mobs, not ones a player threw) are marked "gathered"
 *   (custom_data cs_gathered + a lore line). The mark comes off once you leave the zone, so they stack normally again.
 * - Dying in a zone drops only gathered items: everything else, and your XP, is put aside (storage
 *   crispy_skyblock:stash, so it survives a restart) and handed back when you respawn.
 */
public final class ZoneRules {
    private ZoneRules() {}

    static final Identifier HP = Identifier.fromNamespaceAndPath("crispy_skyblock", "zone_level_health");
    static final Identifier DMG = Identifier.fromNamespaceAndPath("crispy_skyblock", "zone_level_damage");
    static final Identifier STASH = Identifier.fromNamespaceAndPath("crispy_skyblock", "stash");
    static final String MARK = "cs_gathered";
    static final double HP_PER_LV = 0.12, DMG_PER_LV = 0.04;   // +12% health and +4% damage per level
    private static long tick;

    public static boolean isZoneMob(net.minecraft.world.entity.Entity e) { return e.entityTags().contains("cs_zone_mob"); }

    static AABB box(Zones.Zone z) { return new AABB(z.x1(), z.y1(), z.z1(), z.x2() + 1, z.y2() + 1, z.z2() + 1); }

    // ------------------------------------------------------------------ every tick
    private static final List<Mob> outsiders = new ArrayList<>();

    /** Only the zone's own levelled mobs live in a zone: anything else (natural spawns, zombie reinforcements, ...)
     *  is removed as soon as it appears. Tamed pets that followed a player in are left alone. */
    static boolean outsider(net.minecraft.world.entity.Entity e) {
        return e instanceof Mob m && !isZoneMob(m) && !(m instanceof net.minecraft.world.entity.TamableAnimal ta && ta.isTame())
                && !m.isPassenger() && Zones.at(m.level(), m.blockPosition()) != null;
    }
    /** ServerEntityEvents.ENTITY_LOAD: queue it (removing an entity while it's being added isn't safe). */
    static void onEntityLoad(net.minecraft.world.entity.Entity e, ServerLevel level) {
        if (level.dimension() == net.minecraft.world.level.Level.OVERWORLD && outsider(e)) outsiders.add((Mob) e);
    }

    static void onTick(MinecraftServer server) {
        tick++;
        for (Mob m : outsiders) if (!m.isRemoved()) m.discard();
        outsiders.clear();
        ServerLevel ow = server.overworld();
        for (Zones.Zone z : Zones.zones(server)) {
            AABB box = box(z);
            List<ServerPlayer> here = new ArrayList<>();
            for (ServerPlayer p : server.getPlayerList().getPlayers()) if (p.level() == ow && z.contains(p.blockPosition())) here.add(p);
            if (here.isEmpty()) continue;
            // mark fresh drops (block drops can't be picked up for 10 ticks, so every tick is in time)
            for (ItemEntity ie : ow.getEntitiesOfClass(ItemEntity.class, box, ie -> !(ie.getOwner() instanceof Player) && !gathered(ie.getItem())))
                ie.setItem(mark(ie.getItem().copy()));
            if (tick % 5 == 0) {
                for (Mob m : ow.getEntitiesOfClass(Mob.class, box, ZoneRules::isZoneMob)) levelUp(m, z);
                for (Mob m : ow.getEntitiesOfClass(Mob.class, box, ZoneRules::outsider)) m.discard();   // anything that slipped in
            }
        }
        if (tick % 20 == 0)   // out of every zone: drop the gathered marks
            for (ServerPlayer p : server.getPlayerList().getPlayers()) if (Zones.at(p.level(), p.blockPosition()) == null) unmarkAll(p);
    }

    // ------------------------------------------------------------------ levels and health bars
    static int level(Mob m) {
        for (String s : m.entityTags()) if (s.startsWith("cs_lv_")) try { return Integer.parseInt(s.substring(6)); } catch (NumberFormatException ignored) {}
        return 0;
    }

    static void levelUp(Mob m, Zones.Zone z) {
        int lv = level(m);
        if (lv == 0) {
            int roll = m.getRandom().nextInt(5) - 2;
            lv = z.key().equals("mines")
                    ? 2 + (int) Math.round(0.75 * (z.y2() - 12 - m.getBlockY())) + roll   // the rim is 12 below the box top: deeper = harder
                    : 3 + m.getRandom().nextInt(6);
            lv = Math.max(1, Math.min(30, lv));
            m.addTag("cs_lv_" + lv);
            AttributeInstance hp = m.getAttribute(Attributes.MAX_HEALTH), dmg = m.getAttribute(Attributes.ATTACK_DAMAGE);
            if (hp != null) { hp.removeModifier(HP); hp.addPermanentModifier(new AttributeModifier(HP, HP_PER_LV * lv, AttributeModifier.Operation.ADD_MULTIPLIED_BASE)); }
            if (dmg != null) { dmg.removeModifier(DMG); dmg.addPermanentModifier(new AttributeModifier(DMG, DMG_PER_LV * lv, AttributeModifier.Operation.ADD_MULTIPLIED_BASE)); }
            m.setHealth(m.getMaxHealth());
            m.setCustomNameVisible(true);
        }
        Component name = nameplate(m, lv);
        if (!name.equals(m.getCustomName())) m.setCustomName(name);   // only resend it when the health changed
    }

    static Component nameplate(Mob m, int lv) {
        float hp = Math.max(0, m.getHealth()), max = m.getMaxHealth();
        int bars = 10, full = (int) Math.ceil(bars * hp / Math.max(1, max));
        ChatFormatting col = hp > max * 0.5 ? ChatFormatting.GREEN : hp > max * 0.25 ? ChatFormatting.YELLOW : ChatFormatting.RED;
        ChatFormatting lvCol = lv >= 20 ? ChatFormatting.DARK_RED : lv >= 12 ? ChatFormatting.GOLD : lv >= 6 ? ChatFormatting.YELLOW : ChatFormatting.GREEN;
        MutableComponent c = t("[Lv " + lv + "] ", lvCol).append(m.getType().getDescription().copy().withStyle(ChatFormatting.WHITE)).append(t(" ", ChatFormatting.WHITE));
        c.append(t("|".repeat(full), col)).append(t("|".repeat(bars - full), ChatFormatting.DARK_GRAY));
        c.append(t(" " + (int) Math.ceil(hp) + "/" + (int) max + "❤", ChatFormatting.RED));
        return c;
    }

    /** LivingEntityMixin: a levelled zone mob died; pay the killer 2 coins per level. */
    public static void onMobDeath(LivingEntity dead, DamageSource source) {
        if (!(dead instanceof Mob m) || !isZoneMob(m)) return;
        int lv = level(m);
        if (lv <= 0) return;
        ServerPlayer killer = source.getEntity() instanceof ServerPlayer sp ? sp : dead.getKillCredit() instanceof ServerPlayer sp2 ? sp2 : null;
        if (killer == null) return;
        Economy.add(killer.level().getServer(), killer, 2L * lv);
        killer.sendOverlayMessage(t("+" + 2 * lv + " coins", ChatFormatting.GOLD).append(t("  (Lv " + lv + " " + m.getType().getDescription().getString() + ")", ChatFormatting.GRAY)));
    }

    // ------------------------------------------------------------------ gathered marks
    static boolean gathered(ItemStack s) {
        CustomData cd = s.get(DataComponents.CUSTOM_DATA);
        return cd != null && cd.copyTag().getBooleanOr(MARK, false);
    }
    static ItemStack mark(ItemStack s) {
        if (s.isEmpty()) return s;
        CompoundTag tag = s.has(DataComponents.CUSTOM_DATA) ? s.get(DataComponents.CUSTOM_DATA).copyTag() : new CompoundTag();
        tag.putBoolean(MARK, true);
        s.set(DataComponents.CUSTOM_DATA, CustomData.of(tag));
        List<Component> lore = new ArrayList<>(s.getOrDefault(DataComponents.LORE, ItemLore.EMPTY).lines());
        lore.add(t("Gathered here: dropped if you die in this zone", ChatFormatting.DARK_GRAY));
        s.set(DataComponents.LORE, new ItemLore(lore.stream().map(c -> (Component) c.copy().withStyle(st -> st.withItalic(false))).toList()));
        return s;
    }
    static ItemStack unmark(ItemStack s) {
        CompoundTag tag = s.get(DataComponents.CUSTOM_DATA).copyTag();
        tag.remove(MARK);
        if (tag.isEmpty()) s.remove(DataComponents.CUSTOM_DATA); else s.set(DataComponents.CUSTOM_DATA, CustomData.of(tag));
        List<Component> lore = new ArrayList<>(s.getOrDefault(DataComponents.LORE, ItemLore.EMPTY).lines());
        if (!lore.isEmpty()) lore.remove(lore.size() - 1);
        if (lore.isEmpty()) s.remove(DataComponents.LORE); else s.set(DataComponents.LORE, new ItemLore(lore));
        return s;
    }
    static void unmarkAll(ServerPlayer p) {
        var inv = p.getInventory();
        List<ItemStack> moved = new ArrayList<>();
        for (int i = 0; i < inv.getContainerSize(); i++) {
            ItemStack s = inv.getItem(i);
            if (!s.isEmpty() && gathered(s)) { inv.setItem(i, ItemStack.EMPTY); moved.add(unmark(s)); }
        }
        for (ItemStack s : moved) inv.placeItemBackInInventory(s);   // merges with the unmarked stacks again
    }

    // ------------------------------------------------------------------ dying in a zone
    /** ServerPlayerMixin, before the death drops: keep everything that wasn't gathered here. */
    public static void onPlayerDeath(ServerPlayer p) {
        if (Zones.at(p.level(), p.blockPosition()) == null || ((ServerLevel) p.level()).getGameRules().get(net.minecraft.world.level.gamerules.GameRules.KEEP_INVENTORY)) return;
        MinecraftServer server = p.level().getServer();
        RegistryOps<Tag> ops = server.registryAccess().createSerializationContext(NbtOps.INSTANCE);
        CompoundTag all = server.getCommandStorage().get(STASH);
        CompoundTag mine = all.getCompoundOrEmpty(p.getStringUUID());
        ListTag items = mine.getListOrEmpty("items");
        var inv = p.getInventory();
        for (int i = 0; i < inv.getContainerSize(); i++) {
            ItemStack s = inv.getItem(i);
            if (s.isEmpty() || gathered(s)) continue;
            Tag enc = ItemStack.CODEC.encodeStart(ops, s).result().orElse(null);
            if (enc == null) continue;      // can't save it: let it drop rather than lose it
            CompoundTag e = new CompoundTag();
            e.putInt("slot", i);
            e.put("item", enc);
            items.add(e);
            inv.setItem(i, ItemStack.EMPTY);
        }
        mine.put("items", items);
        mine.putInt("lvl", mine.getIntOr("lvl", 0) + p.experienceLevel);
        mine.putFloat("prog", p.experienceProgress);
        p.experienceLevel = 0; p.experienceProgress = 0; p.totalExperience = 0;
        all.put(p.getStringUUID(), mine);
        server.getCommandStorage().set(STASH, all);
    }

    /** After respawning (or joining alive with a stash left from before a restart): hand it all back. */
    static void restore(ServerPlayer p) {
        if (!p.isAlive()) return;
        MinecraftServer server = p.level().getServer();
        CompoundTag all = server.getCommandStorage().get(STASH);
        if (!all.contains(p.getStringUUID())) return;
        CompoundTag mine = all.getCompoundOrEmpty(p.getStringUUID());
        RegistryOps<Tag> ops = server.registryAccess().createSerializationContext(NbtOps.INSTANCE);
        ListTag items = mine.getListOrEmpty("items");
        var inv = p.getInventory();
        int n = 0;
        for (int i = 0; i < items.size(); i++) {
            CompoundTag e = items.getCompoundOrEmpty(i);
            ItemStack s = e.get("item") == null ? ItemStack.EMPTY : ItemStack.CODEC.parse(ops, e.get("item")).result().orElse(ItemStack.EMPTY);
            if (s.isEmpty()) continue;
            int slot = e.getIntOr("slot", -1);
            if (slot >= 0 && slot < inv.getContainerSize() && inv.getItem(slot).isEmpty()) inv.setItem(slot, s);
            else inv.placeItemBackInInventory(s);
            n++;
        }
        p.setExperienceLevels(p.experienceLevel + mine.getIntOr("lvl", 0));
        p.experienceProgress = mine.getFloatOr("prog", 0);
        all.remove(p.getStringUUID());
        server.getCommandStorage().set(STASH, all);
        if (n > 0) p.sendSystemMessage(t("You died in a resource zone: you kept your gear (" + n + " stacks) and XP, and dropped only what you gathered there.", ChatFormatting.YELLOW));
    }
}

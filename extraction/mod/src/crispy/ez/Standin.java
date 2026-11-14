package crispy.ez;

import com.google.gson.*;
import com.mojang.serialization.JsonOps;
import net.fabricmc.fabric.api.entity.event.v1.ServerLivingEntityEvents;
import net.fabricmc.fabric.api.event.lifecycle.v1.ServerEntityEvents;
import net.fabricmc.fabric.api.event.lifecycle.v1.ServerTickEvents;
import net.fabricmc.fabric.api.networking.v1.ServerPlayConnectionEvents;
import net.minecraft.ChatFormatting;
import net.minecraft.server.MinecraftServer;
import net.minecraft.server.level.ServerLevel;
import net.minecraft.server.level.ServerPlayer;
import net.minecraft.tags.DamageTypeTags;
import net.minecraft.world.entity.Entity;
import net.minecraft.world.entity.EquipmentSlot;
import net.minecraft.world.entity.LivingEntity;
import net.minecraft.world.entity.ai.attributes.Attributes;
import net.minecraft.world.entity.item.ItemEntity;
import net.minecraft.world.item.ItemStack;

import java.nio.file.Files;
import java.nio.file.Path;
import java.util.*;

import static crispy.ez.Ui.t;

/**
 * Logging out mid-raid (1.8.21). A raiding player who disconnects in the zone (not downed: that's death, see Revive)
 * leaves a stand-in where they stood: a mannequin with their skin, name, worn gear, held gun and health, carrying a
 * copy of their inventory. Their raid timer keeps running in real time.
 *  - Raiders and the zone can't hurt it; players can. Killed: everything they carried drops there, and when they log
 *    back in their inventory is cleared and they die (killed in action, as usual).
 *  - The timer runs out first: the stand-in goes, and they're caught by the blowout when they log back in.
 *  - They log back in first: the stand-in goes, they carry on with its health and the time that's left.
 * Records survive restarts (config/crispy_extraction/standins.json); a server shutting down leaves no stand-ins
 * (the raid timer pauses as before). A stand-in entity without a live record is removed when it loads.
 */
final class Standin {
    private Standin() {}

    static final Path FILE = Path.of("config", "crispy_extraction", "standins.json");
    static final class Rec {
        String name, entity, state = "out", killer;   // state: out | killed | timeout
        double x, y, z; long deadline; float health;
        List<JsonElement> items = new ArrayList<>();
    }
    static final Map<String, Rec> RECS = new HashMap<>();
    static final Gson GSON = new GsonBuilder().create();
    static boolean loaded;

    static void load() {
        if (loaded) return; loaded = true;
        try {
            if (!Files.exists(FILE)) return;
            JsonObject o = JsonParser.parseString(Files.readString(FILE)).getAsJsonObject();
            for (var e : o.entrySet()) RECS.put(e.getKey(), GSON.fromJson(e.getValue(), Rec.class));
        } catch (Exception ex) { System.err.println("[crispy-extraction] stand-ins: " + ex); }
    }
    static void save() {
        try { Files.createDirectories(FILE.getParent()); Files.writeString(FILE, GSON.toJson(RECS)); }
        catch (Exception ex) { System.err.println("[crispy-extraction] can't save stand-ins: " + ex); }
    }
    static String owner(Entity e) {
        for (String tag : e.entityTags()) if (tag.startsWith("ez.so.")) return tag.substring(6);
        return null;
    }
    static boolean isStandin(Entity e) { return e.entityTags().contains("ez.standin"); }

    static void init() {
        ServerPlayConnectionEvents.DISCONNECT.register((h, server) -> {
            try { leave(server, h.getPlayer()); } catch (Exception ex) { System.err.println("[crispy-extraction] stand-in failed: " + ex); }
        });
        ServerPlayConnectionEvents.JOIN.register((h, sender, server) -> server.execute(() -> {
            try { back(server, h.getPlayer()); } catch (Exception ex) { System.err.println("[crispy-extraction] stand-in return failed: " + ex); }
        }));
        ServerLivingEntityEvents.ALLOW_DAMAGE.register((e, src, amt) -> {
            if (!isStandin(e)) return true;
            return src.getEntity() instanceof ServerPlayer || src.is(DamageTypeTags.BYPASSES_INVULNERABILITY);   // players only: raiders, falls, radiation do nothing
        });
        ServerLivingEntityEvents.AFTER_DEATH.register((e, src) -> { if (isStandin(e)) killed((ServerLevel) e.level(), e, src.getEntity()); });
        ServerEntityEvents.ENTITY_LOAD.register((e, lvl) -> {
            if (!isStandin(e)) return;
            load();
            Rec r = RECS.get(owner(e));
            if (r == null || !"out".equals(r.state) || !e.getUUID().toString().equals(r.entity)) e.discard();   // left over: its player is back, dead or timed out
        });
        ServerTickEvents.END_SERVER_TICK.register(server -> {
            if (server.getTickCount() % 20 != 0 || RECS.isEmpty()) return;
            try { tick(server); } catch (Exception ex) { System.err.println("[crispy-extraction] stand-in tick failed: " + ex); }
        });
    }

    static int timeLeft(MinecraftServer server, ServerPlayer p) {
        var sb = server.getScoreboard(); var o = sb.getObjective("ez.time");
        if (o == null) return 0;
        var i = sb.getPlayerScoreInfo(p, o);
        return i == null ? 0 : i.value();
    }

    static void leave(MinecraftServer server, ServerPlayer p) {
        if (!server.isRunning() || !p.isAlive() || p.isSpectator() || !Raid.raiding(p) || Revive.downed(p) || !p.level().dimension().equals(Zone.CITY)) return;
        int left = timeLeft(server, p);
        if (left <= 0) return;
        load();
        ServerLevel lvl = (ServerLevel) p.level();
        String id = p.getUUID().toString(), tag = "ez.so." + id;
        StringBuilder prof = new StringBuilder();
        for (var pr : p.getGameProfile().properties().get("textures")) {
            prof.append("{name:\"textures\",value:\"").append(pr.value()).append("\"");
            if (pr.signature() != null) prof.append(",signature:\"").append(pr.signature()).append("\"");
            prof.append("}");
            break;
        }
        String name = p.getScoreboardName();
        Plots.run(server, String.format(Locale.ROOT, "execute in lostcities:lostcity run summon minecraft:mannequin %.3f %.3f %.3f {Tags:[\"ez.standin\",\"%s\",\"ez.t_player\"],"
                        + "immovable:1b,hide_description:1b,CustomNameVisible:1b,Rotation:[%.1ff,0f],CustomName:{text:\"%s (offline)\",color:\"gray\"}%s}",
                p.getX(), p.getY(), p.getZ(), tag, p.getYRot(), name, prof.length() > 0 ? ",profile:{properties:[" + prof + "]}" : ""));
        LivingEntity m = lvl.getEntitiesOfClass(LivingEntity.class, p.getBoundingBox().inflate(1), e -> e.entityTags().contains(tag)).stream().findFirst().orElse(null);
        if (m == null) { System.err.println("[crispy-extraction] stand-in for " + name + " didn't spawn"); return; }
        for (EquipmentSlot sl : new EquipmentSlot[]{EquipmentSlot.HEAD, EquipmentSlot.CHEST, EquipmentSlot.LEGS, EquipmentSlot.FEET, EquipmentSlot.MAINHAND, EquipmentSlot.OFFHAND})
            m.setItemSlot(sl, p.getItemBySlot(sl).copy());
        var mh = m.getAttribute(Attributes.MAX_HEALTH);
        if (mh != null) mh.setBaseValue(p.getMaxHealth());
        m.setHealth(p.getHealth());
        Rec r = new Rec();
        r.name = name; r.entity = m.getUUID().toString(); r.x = p.getX(); r.y = p.getY(); r.z = p.getZ(); r.health = p.getHealth();
        r.deadline = System.currentTimeMillis() + left * 1000L;
        var ops = server.registryAccess().createSerializationContext(JsonOps.INSTANCE);
        var inv = p.getInventory();
        for (int i = 0; i < inv.getContainerSize(); i++) {
            ItemStack s = inv.getItem(i);
            if (!s.isEmpty()) r.items.add(ItemStack.CODEC.encodeStart(ops, s).getOrThrow());
        }
        RECS.put(id, r); save();
        for (ServerPlayer o : lvl.players())
            if (o != p && Raid.raiding(o) && o.distanceTo(p) < 64) o.sendSystemMessage(t("📴 " + name + " logged out: their stand-in (and gear) is still out there.", ChatFormatting.GRAY));
        System.out.println("[crispy-extraction] stand-in for " + name + " at " + p.blockPosition().toShortString() + ", " + left + " s left");
    }

    static void killed(ServerLevel lvl, LivingEntity m, Entity by) {
        load();
        String id = owner(m);
        Rec r = id == null ? null : RECS.get(id);
        if (r == null || !"out".equals(r.state)) return;
        r.state = "killed"; r.entity = null;
        r.killer = by instanceof ServerPlayer k ? k.getScoreboardName() : null;
        save();   // first: the gear drops below, and the player's own copy is cleared when they log in
        var ops = lvl.getServer().registryAccess().createSerializationContext(JsonOps.INSTANCE);
        List<ItemStack> gear = new ArrayList<>();
        for (JsonElement j : r.items) {
            try { gear.add(ItemStack.CODEC.parse(ops, j).getOrThrow()); }
            catch (Exception ex) { System.err.println("[crispy-extraction] stand-in item: " + ex); }
        }
        if (!DeathBox.box(lvl, m.blockPosition(), r.name, gear))   // 1.8.28: into a death box, like a real death
            for (ItemStack s : gear) {
                ItemEntity ie = new ItemEntity(lvl, m.getX(), m.getY() + 0.5, m.getZ(), s);
                ie.setDefaultPickUpDelay();
                lvl.addFreshEntity(ie);
            }
        if (by instanceof ServerPlayer k) k.sendSystemMessage(t("You killed " + r.name + "'s stand-in: their gear is in a box where they stood.", ChatFormatting.RED));
        System.out.println("[crispy-extraction] stand-in for " + r.name + " killed by " + r.killer);
    }

    static void tick(MinecraftServer server) {
        long now = System.currentTimeMillis();
        ServerLevel city = server.getLevel(Zone.CITY);
        boolean dirty = false;
        for (Rec r : RECS.values()) {
            if (!"out".equals(r.state) || now < r.deadline) continue;
            r.state = "timeout"; dirty = true;
            if (city != null && r.entity != null) { Entity e = city.getEntity(UUID.fromString(r.entity)); if (e != null) e.discard(); }
            r.entity = null;
            System.out.println("[crispy-extraction] stand-in for " + r.name + ": raid time ran out");
        }
        if (dirty) save();
    }

    static void back(MinecraftServer server, ServerPlayer p) {
        load();
        Rec r = RECS.remove(p.getUUID().toString());
        if (r == null) return;
        save();
        ServerLevel city = server.getLevel(Zone.CITY);
        Entity m = city != null && r.entity != null ? city.getEntity(UUID.fromString(r.entity)) : null;
        float health = m instanceof LivingEntity le ? le.getHealth() : r.health;
        if (m != null) m.discard();
        String name = p.getScoreboardName();
        long left = (r.deadline - System.currentTimeMillis()) / 1000;
        if ("killed".equals(r.state)) {
            p.getInventory().clearContent();
            p.sendSystemMessage(t("While you were offline, " + (r.killer != null ? r.killer : "someone") + " killed your stand-in and took your gear.", ChatFormatting.DARK_RED));
            Plots.run(server, "kill " + name);
        } else if ("timeout".equals(r.state) || left <= 0 || !Raid.raiding(p)) {
            p.sendSystemMessage(t("Your raid timer ran out while you were offline.", ChatFormatting.DARK_RED));
            Plots.run(server, "scoreboard players set " + name + " ez.time 0");
        } else {
            p.setHealth(Math.max(1f, Math.min(p.getMaxHealth(), health)));
            Plots.run(server, "scoreboard players set " + name + " ez.time " + left);
            p.sendSystemMessage(t("Welcome back: your raid kept going. " + left / 60 + ":" + String.format("%02d", left % 60) + " left.", ChatFormatting.GOLD));
        }
        System.out.println("[crispy-extraction] " + name + " back from a stand-in (" + r.state + ")");
    }
}

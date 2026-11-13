package crispy.ez;

import com.google.gson.JsonObject;
import com.google.gson.JsonParser;
import net.fabricmc.fabric.api.event.lifecycle.v1.ServerTickEvents;
import net.fabricmc.fabric.api.event.player.UseBlockCallback;
import net.minecraft.ChatFormatting;
import net.minecraft.core.component.DataComponents;
import net.minecraft.core.registries.BuiltInRegistries;
import net.minecraft.server.MinecraftServer;
import net.minecraft.server.level.ServerPlayer;
import net.minecraft.world.Container;
import net.minecraft.world.InteractionResult;
import net.minecraft.world.effect.MobEffectInstance;
import net.minecraft.world.effect.MobEffects;
import net.minecraft.world.entity.Entity;
import net.minecraft.world.entity.EquipmentSlot;
import net.minecraft.world.item.ItemStack;
import net.minecraft.world.item.component.CustomData;

import java.nio.file.Files;
import java.nio.file.Path;
import java.util.HashMap;
import java.util.Map;
import java.util.regex.Matcher;
import java.util.regex.Pattern;

import static crispy.ez.Ui.t;

/**
 * Milsim armour (1.7.0). The sets are defined by the datapack build (shops.json "armor": set -> slot -> item SNBT);
 * every piece carries custom_data {ezarmor:<set>, ezslot:<slot>}. This class:
 *  - gives the set bonuses: hazmat (each piece blocks 25% of a crash site's contamination, see Events), ghillie (crouching with
 *    no raider gunner within 8 blocks: tag ez.hidden, which the gunners' target selector leaves out), tactical helmet
 *    (night vision while worn);
 *  - swaps any vanilla armour for the nearest set's piece (in a player's inventory, and in a container when opened):
 *    leather / chainmail / gold / copper / turtle -> Scav, iron -> Woodland Patrol, diamond -> Tactical, netherite ->
 *    Juggernaut;
 *  - stops armour helmets being placed as blocks (a placed head loses its stats).
 */
final class Armor {
    private Armor() {}

    static final Path FILE = Path.of("config", "crispy_extraction", "shops.json");
    static final Map<String, Map<String, ItemStack>> SETS = new HashMap<>();
    static final Pattern VANILLA = Pattern.compile("(leather|chainmail|iron|golden|diamond|netherite|copper)_(helmet|chestplate|leggings|boots)|turtle_helmet");
    static final Map<String, String> TO_SET = Map.of("leather", "scav", "chainmail", "scav", "golden", "scav", "copper", "scav", "turtle", "scav",
            "iron", "patrol", "diamond", "tactical", "netherite", "juggernaut");
    static final Map<String, String> TO_SLOT = Map.of("helmet", "head", "chestplate", "chest", "leggings", "legs", "boots", "feet");
    static final EquipmentSlot[] WORN = {EquipmentSlot.HEAD, EquipmentSlot.CHEST, EquipmentSlot.LEGS, EquipmentSlot.FEET};

    static void load(MinecraftServer server) {
        if (!SETS.isEmpty()) return;
        try {
            JsonObject root = JsonParser.parseString(Files.readString(FILE)).getAsJsonObject();
            if (!root.has("armor")) return;
            for (var set : root.getAsJsonObject("armor").entrySet()) {
                Map<String, ItemStack> m = new HashMap<>();
                for (var sl : set.getValue().getAsJsonObject().entrySet()) m.put(sl.getKey(), Shops.parse(server, sl.getValue().getAsString()));
                SETS.put(set.getKey(), m);
            }
        } catch (Exception e) { System.err.println("[crispy-extraction] armour sets: " + e); SETS.clear(); }
    }

    static String set(ItemStack s) {
        if (s.isEmpty()) return null;
        CustomData cd = s.get(DataComponents.CUSTOM_DATA);
        return cd == null ? null : cd.copyTag().getString("ezarmor").orElse(null);
    }
    static int pieces(ServerPlayer p, String set) {
        int n = 0;
        for (EquipmentSlot sl : WORN) if (set.equals(set(p.getItemBySlot(sl)))) n++;
        return n;
    }

    /** The set piece a vanilla armour item becomes, or null if it isn't vanilla armour. */
    static ItemStack convert(MinecraftServer server, ItemStack s) {
        if (s.isEmpty() || set(s) != null) return null;
        Matcher m = VANILLA.matcher(BuiltInRegistries.ITEM.getKey(s.getItem()).getPath());
        if (!m.matches()) return null;
        String mat = m.group(1) == null ? "turtle" : m.group(1), slot = m.group(2) == null ? "head" : TO_SLOT.get(m.group(2));
        load(server);
        Map<String, ItemStack> set = SETS.get(TO_SET.get(mat));
        return set == null || !set.containsKey(slot) ? null : set.get(slot).copy();
    }
    static int convertAll(MinecraftServer server, Container c, ServerPlayer tell) {
        int n = 0;
        for (int i = 0; i < c.getContainerSize(); i++) {
            ItemStack s = c.getItem(i), to = convert(server, s);
            if (to == null) continue;
            if (tell != null) tell.sendSystemMessage(t("Vanilla armour isn't used here: your " + s.getHoverName().getString() + " is now " + to.getHoverName().getString() + ".", ChatFormatting.GOLD));
            c.setItem(i, to); n++;
        }
        if (n > 0) c.setChanged();
        return n;
    }

    static void tick(ServerPlayer p) {
        MinecraftServer server = p.level().getServer();
        convertAll(server, p.getInventory(), p);
        p.removeTag("ez.radproof");   // 1.7.0's edge immunity, gone: hazmat is for contaminated crash sites (Events)
        // ghillie: crouching, no gunner within 8 blocks -> raiders further out lose sight of you
        boolean hide = pieces(p, "ghillie") == 4 && p.isShiftKeyDown()
                && p.level().getEntities((Entity) null, p.getBoundingBox().inflate(8), e -> e.entityTags().contains("ez.gunner")).isEmpty();
        if (hide) { if (p.addTag("ez.hidden")) p.sendSystemMessage(t("Hidden: raiders further than 8 blocks out can't see you.", ChatFormatting.DARK_GREEN), true); }
        else p.removeTag("ez.hidden");
        // tactical helmet: night vision while worn
        MobEffectInstance nv = p.getEffect(MobEffects.NIGHT_VISION);
        if ("tactical".equals(set(p.getItemBySlot(EquipmentSlot.HEAD)))) {
            if (nv == null || nv.getDuration() < 300) p.addEffect(new MobEffectInstance(MobEffects.NIGHT_VISION, 400, 0, true, false, true));
        } else if (nv != null && nv.isAmbient() && nv.getDuration() <= 400) p.removeEffect(MobEffects.NIGHT_VISION);
    }

    static void init() {
        ServerTickEvents.END_SERVER_TICK.register(server -> {
            if (server.getTickCount() % 10 != 0) return;
            for (ServerPlayer p : server.getPlayerList().getPlayers())
                try { tick(p); } catch (Exception ex) { System.err.println("[crispy-extraction] armour tick failed: " + ex); }
        });
        UseBlockCallback.EVENT.register((pl, world, hand, hit) -> {
            if (!(pl instanceof ServerPlayer p)) return InteractionResult.PASS;
            // an armour helmet is a player head: don't let it be placed
            if (set(p.getItemInHand(hand)) != null && p.getItemInHand(hand).is(net.minecraft.world.item.Items.PLAYER_HEAD)) {
                p.sendSystemMessage(t("Armour can't be placed: wear it (it goes in your helmet slot).", ChatFormatting.RED), true);
                return InteractionResult.FAIL;
            }
            // anything stored before 1.7.0: vanilla armour in a container becomes set armour when it's opened
            if (world.getBlockEntity(hit.getBlockPos()) instanceof Container c) convertAll(p.level().getServer(), c, null);
            return InteractionResult.PASS;
        });
    }
}

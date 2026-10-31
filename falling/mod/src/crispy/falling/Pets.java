package crispy.falling;

import com.mojang.brigadier.CommandDispatcher;
import com.mojang.brigadier.arguments.StringArgumentType;
import net.minecraft.ChatFormatting;
import net.minecraft.commands.CommandSourceStack;
import net.minecraft.commands.Commands;
import net.minecraft.commands.arguments.EntityArgument;
import net.minecraft.core.component.DataComponents;
import net.minecraft.nbt.CompoundTag;
import net.minecraft.nbt.ListTag;
import net.minecraft.network.chat.Component;
import net.minecraft.resources.Identifier;
import net.minecraft.server.MinecraftServer;
import net.minecraft.server.level.ServerLevel;
import net.minecraft.server.level.ServerPlayer;
import net.minecraft.server.permissions.LevelBasedPermissionSet;
import net.minecraft.sounds.SoundEvents;
import net.minecraft.world.entity.Display;
import net.minecraft.world.entity.Entity;
import net.minecraft.world.entity.ai.attributes.Attribute;
import net.minecraft.world.entity.ai.attributes.AttributeModifier;
import net.minecraft.world.entity.ai.attributes.Attributes;
import net.minecraft.world.item.ItemStack;
import net.minecraft.world.item.Items;

import java.util.*;

import static crispy.falling.Ui.t;

/**
 * Pets: one at a time floats beside you (a head on an item display) and boosts a skill's XP, plus a small stat.
 * The kinds (key, name, skill, price, stat, head texture) come from storage crispy_skyblock:eco cfg.pets (expansion.py).
 * - Owned pets and the active one are kept in storage crispy_skyblock:pets, per player UUID: {owned:[{t,xp}], act}.
 * - A pet levels up from the XP of the skill it boosts (level = sqrt(xp / 40), up to 30). Its XP boost is
 *   10% + 1% per level; the Phoenix boosts every skill at half that.
 * - /pets: pick a pet to follow you, or buy one. The Phoenix is only a rare End boss drop (/pets grant, from the datapack).
 */
final class Pets {
    private Pets() {}

    static final Identifier STORE = Identifier.fromNamespaceAndPath(SkyblockMod.NS, "pets");
    static final Identifier MOD = Identifier.fromNamespaceAndPath(SkyblockMod.NS, "pet");
    static final int MAX_LEVEL = 30;

    static ListTag kinds(MinecraftServer server) { return Economy.cfg(server).getListOrEmpty("pets"); }
    static CompoundTag kind(MinecraftServer server, String key) {
        ListTag k = kinds(server);
        for (int i = 0; i < k.size(); i++) if (k.getCompoundOrEmpty(i).getStringOr("key", "").equals(key)) return k.getCompoundOrEmpty(i);
        return null;
    }

    static CompoundTag data(MinecraftServer server, ServerPlayer p) {
        return server.getCommandStorage().get(STORE).getCompoundOrEmpty(p.getStringUUID());
    }
    static void save(MinecraftServer server, ServerPlayer p, CompoundTag d) {
        CompoundTag root = server.getCommandStorage().get(STORE).copy();
        root.put(p.getStringUUID(), d);
        server.getCommandStorage().set(STORE, root);
    }
    static int level(long xp) { return (int) Math.min(MAX_LEVEL, Math.sqrt(xp / 40.0)); }
    static double boost(int level) { return 0.10 + 0.01 * level; }

    /** The active pet's record ({t, xp}), or null. */
    static CompoundTag active(MinecraftServer server, ServerPlayer p) {
        CompoundTag d = data(server, p);
        int a = d.getIntOr("act", -1);
        ListTag owned = d.getListOrEmpty("owned");
        return a >= 0 && a < owned.size() ? owned.getCompoundOrEmpty(a) : null;
    }

    /** From Skills.gain: the XP after the active pet's boost; the pet itself also learns from it. */
    static int onSkillXp(ServerPlayer p, Skills.Skill skill, int amount) {
        MinecraftServer server = p.level().getServer();
        CompoundTag d = data(server, p);
        int a = d.getIntOr("act", -1);
        ListTag owned = d.getListOrEmpty("owned");
        if (a < 0 || a >= owned.size()) return amount;
        CompoundTag pet = owned.getCompoundOrEmpty(a);
        CompoundTag k = kind(server, pet.getStringOr("t", ""));
        if (k == null) return amount;
        boolean all = k.getStringOr("skill", "").equals("ALL");
        if (!all && !k.getStringOr("skill", "").equals(skill.name())) return amount;
        long xp = pet.getLongOr("xp", 0);
        int before = level(xp);
        double b = boost(before) * (all ? 0.5 : 1);
        pet.putLong("xp", xp + amount);
        int after = level(xp + amount);
        save(server, p, d);
        if (after > before) {
            p.sendSystemMessage(t("🐾 Your " + k.getStringOr("name", "pet") + " reached level " + after + "!", ChatFormatting.LIGHT_PURPLE));
            p.playSound(SoundEvents.AMETHYST_BLOCK_CHIME, 0.8f, 1.4f);
            applyStats(p);
        }
        return (int) Math.round(amount * (1 + b));
    }

    /** The active pet's stat bonus as an attribute modifier (crispy_skyblock:pet), scaled by its level. */
    static void applyStats(ServerPlayer p) {
        MinecraftServer server = p.level().getServer();
        for (var attr : List.of(Attributes.MOVEMENT_SPEED, Attributes.MINING_EFFICIENCY, Attributes.ATTACK_DAMAGE, Attributes.LUCK, Attributes.MAX_HEALTH)) {
            var inst = p.getAttribute(attr);
            if (inst != null) inst.removeModifier(MOD);
        }
        CompoundTag pet = active(server, p);
        if (pet == null) return;
        String key = pet.getStringOr("t", "");
        double f = 1 + level(pet.getLongOr("xp", 0)) / 15.0;   // x1 at level 0, x3 at level 30
        switch (key) {
            case "pig", "fox" -> add(p, Attributes.MOVEMENT_SPEED, 0.03 * f, AttributeModifier.Operation.ADD_MULTIPLIED_BASE);
            case "silverfish" -> add(p, Attributes.MINING_EFFICIENCY, 2 * f, AttributeModifier.Operation.ADD_VALUE);
            case "wolf" -> add(p, Attributes.ATTACK_DAMAGE, 0.02 * f, AttributeModifier.Operation.ADD_MULTIPLIED_TOTAL);
            case "squid" -> add(p, Attributes.LUCK, 0.5 * f, AttributeModifier.Operation.ADD_VALUE);
            case "phoenix" -> add(p, Attributes.MAX_HEALTH, 4, AttributeModifier.Operation.ADD_VALUE);
            default -> {}
        }
    }
    static void add(ServerPlayer p, net.minecraft.core.Holder<Attribute> attr, double v, AttributeModifier.Operation op) {
        var inst = p.getAttribute(attr);
        if (inst != null) inst.addTransientModifier(new AttributeModifier(MOD, v, op));
    }

    // ------------------------------------------------------------------ the floating pet
    private static final Map<UUID, UUID> shown = new HashMap<>();   // player -> item display
    private static int tick;
    private static boolean cleaned;

    static void onTick(MinecraftServer server) {
        tick++;
        if (!cleaned) { cleaned = true; Upgrades.run(server, "kill @e[type=minecraft:item_display,tag=cs_pet]"); }   // leftovers from before a restart
        Set<UUID> online = new HashSet<>();
        for (ServerPlayer p : server.getPlayerList().getPlayers()) {
            online.add(p.getUUID());
            CompoundTag pet = active(server, p);
            Entity e = display(server, p);
            if (pet == null || p.isSpectator()) { if (e != null) e.discard(); shown.remove(p.getUUID()); continue; }
            if (e == null || e.level() != p.level() || !e.entityTags().contains("cs_pet_" + pet.getStringOr("t", ""))) {
                if (e != null) e.discard();
                e = spawn(server, p, pet.getStringOr("t", ""));
                if (e == null) continue;
            }
            double yaw = Math.toRadians(p.getYRot());
            double bob = Math.sin((tick + p.getId()) / 10.0) * 0.12;
            // over the right shoulder, a little behind
            e.teleportTo(p.getX() - Math.cos(yaw) * 0.9 + Math.sin(yaw) * 0.5, p.getY() + 1.6 + bob, p.getZ() - Math.sin(yaw) * 0.9 - Math.cos(yaw) * 0.5);
            e.setYRot(p.getYRot());
            if (tick % 100 == 0) applyStats(p);
        }
        shown.entrySet().removeIf(en -> {
            if (online.contains(en.getKey())) return false;
            for (ServerLevel l : server.getAllLevels()) { Entity e = l.getEntity(en.getValue()); if (e != null) e.discard(); }
            return true;
        });
    }

    static Entity display(MinecraftServer server, ServerPlayer p) {
        UUID id = shown.get(p.getUUID());
        if (id == null) return null;
        for (ServerLevel l : server.getAllLevels()) { Entity e = l.getEntity(id); if (e != null) return e; }
        return null;
    }

    static Entity spawn(MinecraftServer server, ServerPlayer p, String key) {
        CompoundTag k = kind(server, key);
        if (k == null) return null;
        String tag = "cs_pet_" + key, own = "cs_pet_of_" + p.getStringUUID();
        // just after a teleport the player's chunk may not be entity-ticking yet: a display summoned there can't be
        // found again straight away, so a new one was summoned every tick (a pile of pets at the arrival spot). Wait.
        if (!((ServerLevel) p.level()).isPositionEntityTicking(p.blockPosition())) return null;
        Upgrades.run(server, "kill @e[type=minecraft:item_display,tag=" + own + "]");   // any stray copies of this player's pet
        String cmd = "summon minecraft:item_display " + p.getX() + " " + (p.getY() + 1.6) + " " + p.getZ()
                + " {Tags:[\"cs_pet\",\"" + tag + "\",\"" + own + "\"],teleport_duration:2,billboard:\"vertical\","
                + "transformation:{left_rotation:[0f,0f,0f,1f],right_rotation:[0f,0f,0f,1f],translation:[0f,0f,0f],scale:[0.5f,0.5f,0.5f]},"
                + "item:{id:\"minecraft:player_head\",count:1,components:{\"minecraft:profile\":{properties:[{name:\"textures\",value:\"" + k.getStringOr("tex", "") + "\"}]}}}}";
        server.getCommands().performPrefixedCommand(p.createCommandSourceStack().withSuppressedOutput().withPermission(LevelBasedPermissionSet.GAMEMASTER), cmd);
        List<Display.ItemDisplay> found = ((ServerLevel) p.level()).getEntitiesOfClass(Display.ItemDisplay.class, p.getBoundingBox().inflate(4),
                e -> e.entityTags().contains(own) && e.entityTags().contains(tag));
        if (found.isEmpty()) return null;
        Entity e = found.get(0);
        shown.put(p.getUUID(), e.getUUID());
        return e;
    }

    // ------------------------------------------------------------------ /pets
    static ItemStack head(String tex) {
        ItemStack s = new ItemStack(Items.PLAYER_HEAD);
        CompoundTag props = new CompoundTag();
        // the profile component via a command-style parse is simplest: set through the codec
        try {
            var profile = net.minecraft.world.item.component.ResolvableProfile.CODEC.parse(net.minecraft.nbt.NbtOps.INSTANCE,
                    net.minecraft.nbt.TagParser.parseCompoundFully("{properties:[{name:\"textures\",value:\"" + tex + "\"}]}")).result();
            profile.ifPresent(pr -> s.set(DataComponents.PROFILE, pr));
        } catch (Exception ignored) {}
        return s;
    }

    static void open(ServerPlayer p) {
        MinecraftServer server = p.level().getServer();
        Ui.open(p, t("Pets", ChatFormatting.DARK_GRAY), 6, m -> {
            CompoundTag d = data(server, p);
            ListTag owned = d.getListOrEmpty("owned");
            int act = d.getIntOr("act", -1);
            m.put(4, Ui.item(Items.BONE, t("Your pets", ChatFormatting.LIGHT_PURPLE, ChatFormatting.BOLD), List.of(
                    t("One pet follows you and boosts a skill's XP", ChatFormatting.GRAY),
                    t("(10% + 1% per pet level) and gives a small stat.", ChatFormatting.GRAY),
                    t("Pets level up from the XP they boost.", ChatFormatting.DARK_GRAY)), false), null);
            int[] slots = {10, 11, 12, 13, 14, 15, 16, 19, 20, 21, 22, 23, 24, 25};
            for (int i = 0; i < owned.size() && i < slots.length; i++) {
                CompoundTag pet = owned.getCompoundOrEmpty(i);
                CompoundTag k = kind(server, pet.getStringOr("t", ""));
                if (k == null) continue;
                long xp = pet.getLongOr("xp", 0);
                int lvl = level(xp);
                boolean on = i == act;
                boolean all = k.getStringOr("skill", "").equals("ALL");
                List<Component> lore = new ArrayList<>(List.of(
                        t("Level " + lvl + "/" + MAX_LEVEL + (lvl < MAX_LEVEL ? " · " + Economy.fmt(xp) + "/" + Economy.fmt((long) Math.pow(lvl + 1, 2) * 40) + " XP" : ""), ChatFormatting.GRAY),
                        t("+" + Math.round(boost(lvl) * 100 * (all ? 0.5 : 1)) + "% " + (all ? "all skill" : cap(k.getStringOr("skill", ""))) + " XP", ChatFormatting.GREEN),
                        t(k.getStringOr("stat", ""), ChatFormatting.AQUA), Component.empty(),
                        t(on ? "Following you · click to put away" : "Click to take out", ChatFormatting.YELLOW)));
                int idx = i;
                m.put(slots[i], Ui.item(head(k.getStringOr("tex", "")), t(k.getStringOr("name", "?"), on ? ChatFormatting.GREEN : ChatFormatting.WHITE, ChatFormatting.BOLD), lore, on),
                        (pl, c) -> { CompoundTag dd = data(server, pl); dd.putInt("act", dd.getIntOr("act", -1) == idx ? -1 : idx); save(server, pl, dd); applyStats(pl);
                                     pl.playSound(SoundEvents.ITEM_PICKUP, 0.6f, 1.2f); });
            }
            if (owned.isEmpty()) m.put(22, Ui.item(Economy.item("minecraft:gray_dye"), t("No pets yet: buy one below", ChatFormatting.GRAY), List.of(), false), null);
            // the pet shop
            ListTag ks = kinds(server);
            int s = 37;
            for (int i = 0; i < ks.size() && s <= 43; i++) {
                CompoundTag k = ks.getCompoundOrEmpty(i);
                if (!k.getBooleanOr("shop", true)) continue;
                String key = k.getStringOr("key", "");
                boolean have = false;
                for (int j = 0; j < owned.size(); j++) if (owned.getCompoundOrEmpty(j).getStringOr("t", "").equals(key)) have = true;
                long price = k.getIntOr("price", 0);
                boolean owns = have;
                m.put(s++, Ui.item(head(k.getStringOr("tex", "")), t("Buy: " + k.getStringOr("name", "?"), owns ? ChatFormatting.DARK_GRAY : ChatFormatting.GOLD), List.of(
                        t("Boosts " + cap(k.getStringOr("skill", "")) + " XP · " + k.getStringOr("stat", ""), ChatFormatting.GRAY),
                        owns ? t("You have this pet", ChatFormatting.DARK_GRAY) : t("Price: " + Economy.fmt(price) + " coins", ChatFormatting.GOLD)), false),
                        owns ? null : (pl, c) -> {
                            if (!Economy.add(server, pl, -price)) { pl.sendSystemMessage(t("You need " + Economy.fmt(price) + " coins.", ChatFormatting.RED)); return; }
                            grant(pl, key);
                        });
            }
            m.put(46, Ui.item(Items.NETHER_STAR, t("Phoenix", ChatFormatting.GOLD), List.of(t("A rare drop from End bosses", ChatFormatting.GRAY)), false), null);
            m.put(49, Ui.item(Items.BARRIER, t("Close", ChatFormatting.RED), List.of(), false), (pl, c) -> pl.closeContainer());
        });
    }
    static String cap(String s) { return s.isEmpty() ? s : s.charAt(0) + s.substring(1).toLowerCase(Locale.ROOT); }

    /** Give a pet (a new one at level 0); the first one is taken out straight away. */
    static boolean grant(ServerPlayer p, String key) {
        MinecraftServer server = p.level().getServer();
        CompoundTag k = kind(server, key);
        if (k == null) return false;
        CompoundTag d = data(server, p);
        ListTag owned = d.getListOrEmpty("owned").copy();
        for (int j = 0; j < owned.size(); j++) if (owned.getCompoundOrEmpty(j).getStringOr("t", "").equals(key)) {
            p.sendSystemMessage(t("You already have a " + k.getStringOr("name", "pet") + ".", ChatFormatting.GRAY));
            return false;
        }
        CompoundTag pet = new CompoundTag();
        pet.putString("t", key); pet.putLong("xp", 0);
        owned.add(pet);
        d.put("owned", owned);
        if (d.getIntOr("act", -1) < 0) d.putInt("act", owned.size() - 1);
        save(server, p, d);
        applyStats(p);
        p.sendSystemMessage(t("🐾 New pet: " + k.getStringOr("name", "?") + "! Manage your pets with /pets.", ChatFormatting.LIGHT_PURPLE));
        p.playSound(SoundEvents.PLAYER_LEVELUP, 0.8f, 1.6f);
        return true;
    }

    static void register(CommandDispatcher<CommandSourceStack> d) {
        d.register(Commands.literal("pets").executes(c -> { open(c.getSource().getPlayerOrException()); return 1; })
                .then(Commands.literal("grant").requires(Commands.hasPermission(Commands.LEVEL_GAMEMASTERS))
                        .then(Commands.argument("player", EntityArgument.player()).then(Commands.argument("pet", StringArgumentType.word())
                                .executes(c -> grant(EntityArgument.getPlayer(c, "player"), StringArgumentType.getString(c, "pet")) ? 1 : 0)))));
    }
}

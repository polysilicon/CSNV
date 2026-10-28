package crispy.falling;

import net.minecraft.ChatFormatting;
import net.minecraft.commands.Commands;
import net.minecraft.core.BlockPos;
import net.minecraft.core.Rotations;
import net.minecraft.core.component.DataComponents;
import net.minecraft.core.particles.ParticleTypes;
import net.minecraft.nbt.CompoundTag;
import net.minecraft.nbt.ListTag;
import net.minecraft.network.chat.Component;
import net.minecraft.resources.Identifier;
import net.minecraft.server.MinecraftServer;
import net.minecraft.server.level.ServerLevel;
import net.minecraft.server.level.ServerPlayer;
import net.minecraft.sounds.SoundEvents;
import net.minecraft.sounds.SoundSource;
import net.minecraft.world.InteractionHand;
import net.minecraft.world.InteractionResult;
import net.minecraft.world.SimpleContainer;
import net.minecraft.world.SimpleMenuProvider;
import net.minecraft.world.entity.Entity;
import net.minecraft.world.entity.decoration.ArmorStand;
import net.minecraft.world.entity.player.Inventory;
import net.minecraft.world.entity.player.Player;
import net.minecraft.world.inventory.ChestMenu;
import net.minecraft.world.inventory.ContainerInput;
import net.minecraft.world.inventory.MenuType;
import net.minecraft.world.item.Item;
import net.minecraft.world.item.ItemStack;
import net.minecraft.world.item.Items;
import net.minecraft.world.item.component.CustomData;
import net.minecraft.world.item.component.ItemLore;
import net.minecraft.world.level.Level;
import net.minecraft.world.phys.AABB;
import net.minecraft.world.phys.BlockHitResult;

import java.util.*;

/**
 * Minions: crafted (datapack recipes) as an armor stand item with custom_data {cs_minion:{type,tier}}; placed on your
 * own island they become a small armor stand with the resource on its head. Every tier has a time per action and a
 * storage size; a minion gathers on real time, so it keeps working while the island is unloaded or you're offline,
 * until its storage is full. Records live in storage crispy_skyblock:minions (list: uuid -> {type, tier, plot, last,
 * items, x, y, z}). Right-click a minion (island members only) to collect, upgrade or pick it up.
 */
public final class Minions {
    private Minions() {}

    static final Identifier STORE = Identifier.fromNamespaceAndPath(SkyblockMod.NS, "minions");
    static final String[] ROMAN = {"", "I", "II", "III", "IV", "V"};
    static final int EVERY_TICKS = 100;
    private static int tick;
    private static boolean swing;

    // ------------------------------------------------------------------ config and records
    static CompoundTag type(MinecraftServer server, String key) {
        ListTag l = Economy.cfg(server).getListOrEmpty("minions");
        for (int i = 0; i < l.size(); i++) if (l.getCompoundOrEmpty(i).getStringOr("key", "").equals(key)) return l.getCompoundOrEmpty(i);
        return new CompoundTag();
    }
    static CompoundTag tier(MinecraftServer server, int tier) {
        ListTag l = Economy.cfg(server).getListOrEmpty("tiers");
        return l.getCompoundOrEmpty(Math.max(0, Math.min(l.size() - 1, tier - 1)));
    }
    static int maxTier(MinecraftServer server) { return Math.max(1, Economy.cfg(server).getListOrEmpty("tiers").size()); }

    static CompoundTag all(MinecraftServer server) { return server.getCommandStorage().get(STORE).getCompoundOrEmpty("list"); }
    static void save(MinecraftServer server, CompoundTag list) {
        CompoundTag root = server.getCommandStorage().get(STORE);
        root.put("list", list);
        server.getCommandStorage().set(STORE, root);
    }

    static int limit(MinecraftServer server, int plot) {
        CompoundTag l = Economy.cfg(server).getCompoundOrEmpty("limit");
        int lvl = 0;
        var obj = server.getScoreboard().getObjective("cs_lvl");
        if (obj != null) {
            var info = server.getScoreboard().getPlayerScoreInfo(Economy.holder("#p" + plot), obj);
            if (info != null) lvl = info.value();
        }
        return Math.min(l.getIntOr("max", 15), l.getIntOr("base", 5) + lvl / Math.max(1, l.getIntOr("per_levels", 20)));
    }
    static int count(MinecraftServer server, int plot) {
        CompoundTag list = all(server);
        int n = 0;
        for (String k : list.keySet()) if (list.getCompoundOrEmpty(k).getIntOr("plot", 0) == plot) n++;
        return n;
    }

    static int stored(CompoundTag rec) {
        CompoundTag items = rec.getCompoundOrEmpty("items");
        int n = 0;
        for (String k : items.keySet()) n += items.getIntOr(k, 0);
        return n;
    }

    /** Add what the minion gathered since `last`; returns the number of actions done. */
    static int advance(MinecraftServer server, CompoundTag rec, long now) {
        CompoundTag t = tier(server, rec.getIntOr("tier", 1));
        long interval = Math.max(1, t.getIntOr("secs", 30)) * 1000L;
        int cap = t.getIntOr("cap", 64);
        long last = rec.getLongOr("last", now);
        long acts = (now - last) / interval;
        if (acts <= 0) return 0;
        ListTag drops = type(server, rec.getStringOr("type", "")).getListOrEmpty("drops");
        CompoundTag items = rec.getCompoundOrEmpty("items");
        int stored = stored(rec), done = 0;
        while (done < acts && stored < cap) {
            for (int i = 0; i < drops.size() && stored < cap; i++) {
                CompoundTag d = drops.getCompoundOrEmpty(i);
                int n = Math.min(d.getIntOr("n", 1), cap - stored);
                String id = d.getStringOr("id", "");
                items.putInt(id, items.getIntOr(id, 0) + n);
                stored += n;
            }
            done++;
        }
        rec.put("items", items);
        rec.putLong("last", stored >= cap ? now : last + done * interval);
        return done;
    }

    // ------------------------------------------------------------------ items
    static ItemStack item(MinecraftServer server, String key, int tier) {
        CompoundTag ty = type(server, key), t = tier(server, tier);
        String name = ty.getStringOr("name", key);
        ItemStack s = new ItemStack(Items.ARMOR_STAND);
        s.set(DataComponents.CUSTOM_NAME, Component.literal(name + " Minion " + ROMAN[tier]).withStyle(st -> st.withItalic(false).withColor(ChatFormatting.AQUA).withBold(true)));
        List<Component> lore = new ArrayList<>();
        for (String l : new String[]{"Place it on your island. It gathers", name.toLowerCase(Locale.ROOT) + " on its own, even while", "you're offline, until its storage is full.", ""})
            lore.add(Component.literal(l).withStyle(st -> st.withItalic(false).withColor(ChatFormatting.GRAY)));
        lore.add(Component.literal("Tier " + ROMAN[tier] + ": one action every " + t.getIntOr("secs", 30) + "s, holds " + t.getIntOr("cap", 64))
                .withStyle(st -> st.withItalic(false).withColor(ChatFormatting.DARK_AQUA)));
        lore.add(Component.literal("Right-click it to collect or upgrade.").withStyle(st -> st.withItalic(false).withColor(ChatFormatting.YELLOW)));
        s.set(DataComponents.LORE, new ItemLore(lore));
        s.set(DataComponents.ITEM_MODEL, Identifier.parse(ty.getStringOr("head", "minecraft:cobblestone")));
        s.set(DataComponents.ENCHANTMENT_GLINT_OVERRIDE, true);
        s.set(DataComponents.MAX_STACK_SIZE, 1);
        CompoundTag data = new CompoundTag(), m = new CompoundTag();
        m.putString("type", key);
        m.putInt("tier", tier);
        data.put("cs_minion", m);
        s.set(DataComponents.CUSTOM_DATA, CustomData.of(data));
        return s;
    }

    static Component name(MinecraftServer server, CompoundTag rec) {
        int cap = tier(server, rec.getIntOr("tier", 1)).getIntOr("cap", 64), st = stored(rec);
        return Component.literal(type(server, rec.getStringOr("type", "")).getStringOr("name", "?") + " Minion " + ROMAN[rec.getIntOr("tier", 1)])
                .withStyle(ChatFormatting.AQUA)
                .append(Component.literal(" [" + st + "/" + cap + "]").withStyle(st >= cap ? ChatFormatting.RED : ChatFormatting.GRAY));
    }

    // ------------------------------------------------------------------ placing
    static InteractionResult onUseBlock(Player player, Level world, InteractionHand hand, BlockHitResult hit) {
        if (!(player instanceof ServerPlayer p) || !(world instanceof ServerLevel level)) return InteractionResult.PASS;
        ItemStack held = p.getItemInHand(hand);
        CustomData cd = held.get(DataComponents.CUSTOM_DATA);
        if (cd == null || !cd.copyTag().contains("cs_minion")) return InteractionResult.PASS;
        MinecraftServer server = level.getServer();
        CompoundTag m = cd.copyTag().getCompoundOrEmpty("cs_minion");
        String key = m.getStringOr("type", "");
        int tier = Math.max(1, Math.min(maxTier(server), m.getIntOr("tier", 1)));
        int plot = SkyblockMod.plot(server, p);
        BlockPos pos = hit.getBlockPos().relative(hit.getDirection());
        if (level != server.overworld() || plot <= 0 || !inPlot(server, plot, pos)) {
            p.sendSystemMessage(Component.literal("Minions can only be placed on your own island.").withStyle(ChatFormatting.RED));
            return InteractionResult.FAIL;
        }
        if (!level.getBlockState(pos).canBeReplaced() || !level.getBlockState(pos.above()).isAir()) {
            p.sendSystemMessage(Component.literal("There's no room for a minion there.").withStyle(ChatFormatting.RED));
            return InteractionResult.FAIL;
        }
        int lim = limit(server, plot), have = count(server, plot);
        if (have >= lim) {
            p.sendSystemMessage(Component.literal("Your island already has " + have + "/" + lim + " minions. Raise your island level for more slots.").withStyle(ChatFormatting.RED));
            return InteractionResult.FAIL;
        }
        CompoundTag ty = type(server, key);
        if (ty.isEmpty()) return InteractionResult.FAIL;
        float yaw = p.getYRot() + 180f;
        String color = String.valueOf(ty.getIntOr("color", 0x888888));
        String armor = ",{id:\"minecraft:leather_%s\",components:{\"minecraft:dyed_color\":" + color + "}}";
        String snbt = "{Small:1b,ShowArms:1b,NoBasePlate:1b,Invulnerable:1b,DisabledSlots:4144959,Tags:[\"cs_minion\",\"cs_m_new\"],"
                + "Rotation:[" + yaw + "f,0f],Pose:{RightArm:[-30f,0f,0f],LeftArm:[-15f,0f,10f],Head:[5f,0f,0f]},CustomNameVisible:1b,"
                + "equipment:{head:{id:\"" + ty.getStringOr("head", "minecraft:cobblestone") + "\"},mainhand:{id:\"" + ty.getStringOr("tool", "minecraft:wooden_pickaxe") + "\"}"
                + ",chest:" + String.format(armor, "chestplate").substring(1) + ",legs:" + String.format(armor, "leggings").substring(1)
                + ",feet:" + String.format(armor, "boots").substring(1) + "}}";
        server.getCommands().performPrefixedCommand(server.createCommandSourceStack().withLevel(level).withSuppressedOutput(),
                "summon minecraft:armor_stand " + (pos.getX() + 0.5) + " " + pos.getY() + " " + (pos.getZ() + 0.5) + " " + snbt);
        ArmorStand stand = level.getEntitiesOfClass(ArmorStand.class, new AABB(pos).inflate(1), e -> e.entityTags().contains("cs_m_new")).stream().findFirst().orElse(null);
        if (stand == null) { p.sendSystemMessage(Component.literal("The minion couldn't be placed.").withStyle(ChatFormatting.RED)); return InteractionResult.FAIL; }
        stand.removeTag("cs_m_new");
        CompoundTag rec = new CompoundTag();
        rec.putString("type", key);
        rec.putInt("tier", tier);
        rec.putInt("plot", plot);
        rec.putLong("last", System.currentTimeMillis());
        rec.put("items", new CompoundTag());
        rec.putInt("x", pos.getX()); rec.putInt("y", pos.getY()); rec.putInt("z", pos.getZ());
        CompoundTag list = all(server);
        list.put(stand.getStringUUID(), rec);
        save(server, list);
        stand.setCustomName(name(server, rec));
        if (!p.isCreative()) held.shrink(1);
        p.sendSystemMessage(Component.literal("Placed your " + ty.getStringOr("name", key) + " Minion (" + (have + 1) + "/" + lim + " on this island).").withStyle(ChatFormatting.GREEN));
        level.playSound(null, pos, SoundEvents.ARMOR_EQUIP_GENERIC.value(), SoundSource.BLOCKS, 1f, 1.2f);
        return InteractionResult.SUCCESS;
    }

    static boolean inPlot(MinecraftServer server, int id, BlockPos pos) {
        ListTag plots = server.getCommandStorage().get(IslandLevels.DATA).getListOrEmpty("plots");
        if (id <= 0 || id >= plots.size()) return false;
        CompoundTag pl = plots.getCompoundOrEmpty(id);
        return pos.getX() >= pl.getIntOr("x", 0) && pos.getX() <= pl.getIntOr("x1", -1)
                && pos.getZ() >= pl.getIntOr("z", 0) && pos.getZ() <= pl.getIntOr("z1", -1);
    }

    // ------------------------------------------------------------------ working
    static void onTick(MinecraftServer server) {
        if (++tick % EVERY_TICKS != 0) return;
        swing = !swing;
        ServerLevel level = server.overworld();
        CompoundTag list = all(server);
        if (list.isEmpty()) return;
        long now = System.currentTimeMillis();
        List<String> gone = new ArrayList<>();
        for (String k : list.keySet()) {
            CompoundTag rec = list.getCompoundOrEmpty(k);
            BlockPos pos = new BlockPos(rec.getIntOr("x", 0), rec.getIntOr("y", 0), rec.getIntOr("z", 0));
            if (!level.hasChunkAt(pos)) continue;   // unloaded: catches up when next looked at
            Entity e = level.getEntity(UUID.fromString(k));
            if (!(e instanceof ArmorStand stand)) {
                // chunk loaded but no minion for 3 checks in a row: it was removed some other way
                int miss = rec.getIntOr("miss", 0) + 1;
                if (miss >= 3) gone.add(k); else rec.putInt("miss", miss);
                continue;
            }
            rec.remove("miss");
            int did = advance(server, rec, now);
            stand.setCustomName(name(server, rec));
            if (did > 0) {
                stand.setRightArmPose(swing ? new Rotations(-80f, 0f, 0f) : new Rotations(-30f, 0f, 0f));
                level.sendParticles(ParticleTypes.HAPPY_VILLAGER, stand.getX(), stand.getY() + 0.6, stand.getZ(), 4, 0.3, 0.2, 0.3, 0);
            }
        }
        for (String k : gone) list.remove(k);
        save(server, list);
    }

    // ------------------------------------------------------------------ menu
    static InteractionResult onUseEntity(Player player, Level world, InteractionHand hand, Entity entity) {
        if (!(player instanceof ServerPlayer p) || !(world instanceof ServerLevel level) || !entity.entityTags().contains("cs_minion")) return InteractionResult.PASS;
        if (hand != InteractionHand.MAIN_HAND) return InteractionResult.SUCCESS;
        MinecraftServer server = level.getServer();
        CompoundTag rec = all(server).getCompoundOrEmpty(entity.getStringUUID());
        if (rec.isEmpty()) { p.sendSystemMessage(Component.literal("This minion has no record.").withStyle(ChatFormatting.RED)); return InteractionResult.SUCCESS; }
        boolean staff = Commands.hasPermission(Commands.LEVEL_GAMEMASTERS).test(p.createCommandSourceStack());
        if (rec.getIntOr("plot", -1) != SkyblockMod.plot(server, p) && !staff) {
            p.sendSystemMessage(Component.literal("That's not your minion.").withStyle(ChatFormatting.RED));
            return InteractionResult.SUCCESS;
        }
        open(server, p, entity.getStringUUID());
        return InteractionResult.SUCCESS;
    }

    static void open(MinecraftServer server, ServerPlayer p, String uuid) {
        SimpleContainer box = new SimpleContainer(45);
        p.openMenu(new SimpleMenuProvider((id, inv, pl) -> new Menu(id, inv, box, server, uuid), Component.literal("Minion")));
    }

    static final int INFO = 4, UPGRADE = 38, COLLECT = 40, PICKUP = 42, CLOSE = 44;
    static final int[] STORE_SLOTS = {19, 20, 21, 22, 23, 24, 25, 28, 29, 30, 31, 32, 33, 34};

    static final class Menu extends ChestMenu {
        final SimpleContainer box;
        final MinecraftServer server;
        final String uuid;

        Menu(int id, Inventory inv, SimpleContainer box, MinecraftServer server, String uuid) {
            super(MenuType.GENERIC_9x5, id, inv, box, 5);
            this.box = box; this.server = server; this.uuid = uuid;
            fill();
        }

        CompoundTag rec() { return all(server).getCompoundOrEmpty(uuid); }
        void put(CompoundTag rec) { CompoundTag l = all(server); l.put(uuid, rec); save(server, l); rename(rec); }
        void rename(CompoundTag rec) { if (server.overworld().getEntity(UUID.fromString(uuid)) instanceof ArmorStand a) a.setCustomName(name(server, rec)); }

        void fill() {
            CompoundTag rec = rec();
            advance(server, rec, System.currentTimeMillis());
            put(rec);
            CompoundTag ty = type(server, rec.getStringOr("type", ""));
            int tier = rec.getIntOr("tier", 1), max = maxTier(server);
            CompoundTag t = tier(server, tier);
            int cap = t.getIntOr("cap", 64), st = stored(rec);
            ItemStack pane = Shop.named(Economy.item("minecraft:black_stained_glass_pane"), Component.literal(""), List.of(), false);
            for (int i = 0; i < 45; i++) box.setItem(i, pane.copy());
            for (int s : STORE_SLOTS) box.setItem(s, ItemStack.EMPTY);
            box.setItem(INFO, Shop.named(Economy.item(ty.getStringOr("head", "minecraft:cobblestone")),
                    Shop.t(ty.getStringOr("name", "?") + " Minion " + ROMAN[tier], ChatFormatting.AQUA, ChatFormatting.BOLD),
                    List.of(Shop.t("One action every " + t.getIntOr("secs", 30) + " seconds", ChatFormatting.GRAY),
                            Shop.t("Storage: " + st + "/" + cap, st >= cap ? ChatFormatting.RED : ChatFormatting.GRAY),
                            Shop.t(st >= cap ? "Full! Collect to keep it working." : "Works while you're offline, too.", st >= cap ? ChatFormatting.RED : ChatFormatting.DARK_GRAY)), true));
            int slot = 0;
            CompoundTag items = rec.getCompoundOrEmpty("items");
            for (String id : items.keySet()) {
                Item it = Economy.item(id);
                int n = items.getIntOr(id, 0);
                while (n > 0 && slot < STORE_SLOTS.length) {
                    int k = Math.min(n, it.getDefaultMaxStackSize());
                    box.setItem(STORE_SLOTS[slot++], new ItemStack(it, k));
                    n -= k;
                }
            }
            if (tier < max) {
                CompoundTag nt = tier(server, tier + 1);
                Item mat = Economy.item(ty.getStringOr("recipe", "minecraft:cobblestone"));
                box.setItem(UPGRADE, Shop.named(Items.EXPERIENCE_BOTTLE, Shop.t("Upgrade to tier " + ROMAN[tier + 1], ChatFormatting.GREEN, ChatFormatting.BOLD),
                        List.of(Shop.t("One action every " + nt.getIntOr("secs", 30) + "s, holds " + nt.getIntOr("cap", 64), ChatFormatting.GRAY), Shop.t("", ChatFormatting.GRAY),
                                Shop.t("Cost:", ChatFormatting.GRAY),
                                Shop.t("• " + Economy.fmt(nt.getIntOr("coins", 0)) + " coins", ChatFormatting.GOLD),
                                Shop.t("• " + nt.getIntOr("items", 0) + " ", ChatFormatting.WHITE).append(new ItemStack(mat).getHoverName())), false));
            } else box.setItem(UPGRADE, Shop.named(Items.NETHER_STAR, Shop.t("Max tier", ChatFormatting.LIGHT_PURPLE, ChatFormatting.BOLD), List.of(), true));
            box.setItem(COLLECT, Shop.named(Items.CHEST, Shop.t("Collect all", ChatFormatting.YELLOW, ChatFormatting.BOLD),
                    List.of(Shop.t(st + " items waiting", ChatFormatting.GRAY)), st > 0));
            box.setItem(PICKUP, Shop.named(Items.ARMOR_STAND, Shop.t("Pick up minion", ChatFormatting.RED),
                    List.of(Shop.t("Collects everything, then gives you", ChatFormatting.GRAY), Shop.t("the minion back as an item.", ChatFormatting.GRAY)), false));
            box.setItem(CLOSE, Shop.named(Items.BARRIER, Shop.t("Close", ChatFormatting.RED), List.of(), false));
        }

        /** Move stored items into the player's inventory; returns how many didn't fit. */
        int collect(ServerPlayer p, CompoundTag rec) {
            CompoundTag items = rec.getCompoundOrEmpty("items");
            int left = 0, got = 0;
            for (String id : new ArrayList<>(items.keySet())) {
                Item it = Economy.item(id);
                int n = items.getIntOr(id, 0);
                while (n > 0) {
                    ItemStack s = new ItemStack(it, Math.min(n, it.getDefaultMaxStackSize()));
                    int before = s.getCount();
                    p.getInventory().add(s);
                    int added = before - s.getCount();
                    n -= added; got += added;
                    if (added == 0 || !s.isEmpty()) break;
                }
                if (n > 0) items.putInt(id, n); else items.remove(id);
                left += n;
            }
            rec.put("items", items);
            if (got > 0) p.playSound(SoundEvents.ITEM_PICKUP, 0.6f, 1f);
            if (left > 0) p.sendSystemMessage(Component.literal("Your inventory is full; " + left + " items stayed in the minion.").withStyle(ChatFormatting.YELLOW));
            return left;
        }

        @Override
        public void clicked(int slot, int button, ContainerInput input, Player player) {
            if (!(player instanceof ServerPlayer p) || slot < 0 || slot >= 45) { sendAllDataToRemote(); return; }
            CompoundTag rec = rec();
            if (rec.isEmpty()) { p.closeContainer(); return; }
            advance(server, rec, System.currentTimeMillis());
            if (slot == CLOSE) { p.closeContainer(); return; }
            if (slot == COLLECT || Arrays.stream(STORE_SLOTS).anyMatch(s -> s == slot)) { collect(p, rec); put(rec); }
            else if (slot == UPGRADE) upgrade(p, rec);
            else if (slot == PICKUP) { pickup(p, rec); return; }
            fill();
            sendAllDataToRemote();
        }

        void upgrade(ServerPlayer p, CompoundTag rec) {
            int tier = rec.getIntOr("tier", 1);
            if (tier >= maxTier(server)) return;
            CompoundTag nt = tier(server, tier + 1), ty = type(server, rec.getStringOr("type", ""));
            Item mat = Economy.item(ty.getStringOr("recipe", "minecraft:cobblestone"));
            int coins = nt.getIntOr("coins", 0), need = nt.getIntOr("items", 0), have = Economy.count(p, mat);
            if (have < need || Economy.coins(server, p) < coins) {
                p.sendSystemMessage(Component.literal("You need " + Economy.fmt(coins) + " coins and " + need + " ").withStyle(ChatFormatting.RED)
                        .append(new ItemStack(mat).getHoverName()).append(Component.literal(" (you have " + have + ").").withStyle(ChatFormatting.RED)));
                p.playSound(SoundEvents.VILLAGER_NO, 0.7f, 1f);
                return;
            }
            Economy.take(p, mat, need);
            Economy.add(server, p, -coins);
            rec.putInt("tier", tier + 1);
            put(rec);
            p.sendSystemMessage(Component.literal("Upgraded to tier " + ROMAN[tier + 1] + "!").withStyle(ChatFormatting.GREEN));
            p.playSound(SoundEvents.PLAYER_LEVELUP, 0.6f, 1.2f);
        }

        void pickup(ServerPlayer p, CompoundTag rec) {
            if (collect(p, rec) > 0) { put(rec); fill(); sendAllDataToRemote(); return; }
            CompoundTag l = all(server);
            l.remove(uuid);
            save(server, l);
            if (server.overworld().getEntity(UUID.fromString(uuid)) instanceof ArmorStand a) a.discard();
            ItemStack it = item(server, rec.getStringOr("type", ""), rec.getIntOr("tier", 1));
            if (!p.getInventory().add(it)) p.drop(it, false);
            p.closeContainer();
            p.sendSystemMessage(Component.literal("Picked up your minion.").withStyle(ChatFormatting.GREEN));
        }

        @Override
        public ItemStack quickMoveStack(Player player, int slot) { return ItemStack.EMPTY; }

        @Override
        public boolean stillValid(Player player) { return true; }
    }
}

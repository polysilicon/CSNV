package crispy.falling;

import net.minecraft.ChatFormatting;
import net.minecraft.core.BlockPos;
import net.minecraft.core.registries.BuiltInRegistries;
import net.minecraft.network.chat.Component;
import net.minecraft.resources.Identifier;
import net.minecraft.resources.ResourceKey;
import net.minecraft.server.MinecraftServer;
import net.minecraft.server.level.ServerLevel;
import net.minecraft.server.level.ServerPlayer;
import net.minecraft.sounds.SoundEvents;
import net.minecraft.stats.Stats;
import net.minecraft.tags.BlockTags;
import net.minecraft.world.SimpleContainer;
import net.minecraft.world.SimpleMenuProvider;
import net.minecraft.world.entity.LivingEntity;
import net.minecraft.world.entity.ai.attributes.AttributeModifier;
import net.minecraft.world.entity.ai.attributes.Attributes;
import net.minecraft.world.entity.monster.Enemy;
import net.minecraft.world.entity.player.Inventory;
import net.minecraft.world.entity.player.Player;
import net.minecraft.world.inventory.ChestMenu;
import net.minecraft.world.inventory.ContainerInput;
import net.minecraft.world.inventory.MenuType;
import net.minecraft.world.item.ItemStack;
import net.minecraft.world.item.Items;
import net.minecraft.world.level.Level;
import net.minecraft.world.level.block.Block;
import net.minecraft.world.level.block.Blocks;
import net.minecraft.world.level.block.CocoaBlock;
import net.minecraft.world.level.block.CropBlock;
import net.minecraft.world.level.block.NetherWartBlock;
import net.minecraft.world.level.block.entity.BlockEntity;
import net.minecraft.world.level.block.state.BlockState;
import net.minecraft.world.scores.Objective;
import net.minecraft.world.scores.ScoreHolder;

import java.util.*;

/**
 * Skills, Hypixel style: Farming (fully grown crops, melons, pumpkins, cane, cactus), Mining (ores and stone),
 * Foraging (logs), Combat (hostile mobs, bosses) and Fishing (catches) earn XP into scoreboard objectives sk_*.
 * Level L needs 100 x L^2 XP in total, up to MAX. A level-up pays 100 x L coins.
 * Perks: Farming, Mining (ores) and Foraging have a 2% per level chance of double drops; Combat gives +1% damage per
 * level; Fishing +0.2 Luck per level (better catches). Blocks a player placed give nothing (Placed), so placing and
 * breaking can't farm XP; cobblestone from a generator still counts. /skills shows them.
 */
public final class Skills {
    private Skills() {}

    enum Skill {
        FARMING("Farming", "sk_farm", ChatFormatting.YELLOW, Items.GOLDEN_HOE, "% chance of double crops"),
        MINING("Mining", "sk_mine", ChatFormatting.GRAY, Items.IRON_PICKAXE, "% chance of double ore drops"),
        FORAGING("Foraging", "sk_forage", ChatFormatting.DARK_GREEN, Items.IRON_AXE, "% chance of double logs"),
        COMBAT("Combat", "sk_combat", ChatFormatting.RED, Items.IRON_SWORD, "% more damage"),
        FISHING("Fishing", "sk_fish", ChatFormatting.AQUA, Items.FISHING_ROD, " Luck (better catches)");
        final String title, obj, perk; final ChatFormatting color; final net.minecraft.world.item.Item icon;
        Skill(String title, String obj, ChatFormatting color, net.minecraft.world.item.Item icon, String perk) {
            this.title = title; this.obj = obj; this.color = color; this.icon = icon; this.perk = perk;
        }
        /** The perk at this level, as shown: "24", "+2.4" ... */
        String perkValue(int level) {
            return switch (this) {
                case FARMING, MINING, FORAGING -> String.valueOf(2 * level);
                case COMBAT -> String.valueOf(level);
                case FISHING -> "+" + String.format(Locale.US, "%.1f", 0.2 * level);
            };
        }
    }
    static final int MAX = 25;
    static final Identifier COMBAT_MOD = Identifier.fromNamespaceAndPath(SkyblockMod.NS, "skill_combat");
    static final Identifier FISHING_MOD = Identifier.fromNamespaceAndPath(SkyblockMod.NS, "skill_fishing");

    static long xpFor(int level) { return 100L * level * level; }
    static int level(long xp) { int l = 0; while (l < MAX && xp >= xpFor(l + 1)) l++; return l; }

    // ------------------------------------------------------------------ XP values
    static final Map<Block, Integer> MINING_XP = new HashMap<>();
    static {
        Object[][] m = {{Blocks.COAL_ORE, 5}, {Blocks.DEEPSLATE_COAL_ORE, 5}, {Blocks.COPPER_ORE, 4}, {Blocks.DEEPSLATE_COPPER_ORE, 4},
                {Blocks.IRON_ORE, 8}, {Blocks.DEEPSLATE_IRON_ORE, 8}, {Blocks.GOLD_ORE, 10}, {Blocks.DEEPSLATE_GOLD_ORE, 10},
                {Blocks.NETHER_GOLD_ORE, 6}, {Blocks.LAPIS_ORE, 8}, {Blocks.DEEPSLATE_LAPIS_ORE, 8}, {Blocks.REDSTONE_ORE, 8},
                {Blocks.DEEPSLATE_REDSTONE_ORE, 8}, {Blocks.DIAMOND_ORE, 25}, {Blocks.DEEPSLATE_DIAMOND_ORE, 25},
                {Blocks.EMERALD_ORE, 30}, {Blocks.DEEPSLATE_EMERALD_ORE, 30}, {Blocks.NETHER_QUARTZ_ORE, 5}, {Blocks.ANCIENT_DEBRIS, 50},
                {Blocks.STONE, 1}, {Blocks.COBBLESTONE, 1}, {Blocks.DEEPSLATE, 1}, {Blocks.COBBLED_DEEPSLATE, 1}, {Blocks.NETHERRACK, 1},
                {Blocks.END_STONE, 2}, {Blocks.OBSIDIAN, 5}, {Blocks.BASALT, 1}, {Blocks.BLACKSTONE, 1}};
        for (Object[] e : m) MINING_XP.put((Block) e[0], (Integer) e[1]);
    }
    static boolean isOre(Block b) { return MINING_XP.getOrDefault(b, 0) >= 4 && b != Blocks.OBSIDIAN; }

    /** Farming XP for breaking this (only when it's fully grown), or 0. */
    static int farmingXp(BlockState st) {
        Block b = st.getBlock();
        if (b instanceof CropBlock crop) return crop.isMaxAge(st) ? 2 : 0;
        if (b instanceof NetherWartBlock) return st.getValue(NetherWartBlock.AGE) >= 3 ? 3 : 0;
        if (b instanceof CocoaBlock) return st.getValue(CocoaBlock.AGE) >= 2 ? 3 : 0;
        if (b == Blocks.MELON || b == Blocks.PUMPKIN) return 4;
        if (b == Blocks.SUGAR_CANE || b == Blocks.CACTUS) return 1;
        return 0;
    }

    // ------------------------------------------------------------------ scores
    static Objective objective(MinecraftServer server, Skill s) { return server.getScoreboard().getObjective(s.obj); }
    static long xp(MinecraftServer server, ServerPlayer p, Skill s) { return SkyblockMod.score(server, p, s.obj); }

    static void gain(ServerPlayer p, Skill s, int amount) {
        if (amount <= 0) return;
        amount = Pets.onSkillXp(p, s, amount);   // the active pet's boost (and the pet learns from it)
        MinecraftServer server = p.level().getServer();
        Objective o = objective(server, s);
        if (o == null) return;
        long before = xp(server, p, s);
        server.getScoreboard().getOrCreatePlayerScore(ScoreHolder.forNameOnly(p.getScoreboardName()), o).add(amount);
        int was = level(before), now = level(before + amount);
        p.sendOverlayMessage(Component.literal("+" + amount + " " + s.title + " XP").withStyle(s.color));
        if (now > was) {
            long coins = 0;
            for (int l = was + 1; l <= now; l++) coins += 100L * l;
            Economy.add(server, p, coins);
            p.sendSystemMessage(Component.literal("✦ " + s.title + " " + now + "! ").withStyle(s.color, ChatFormatting.BOLD)
                    .append(Component.literal(s.perkValue(now) + s.perk + " · +" + Economy.fmt(coins) + " coins").withStyle(ChatFormatting.GRAY)));
            p.playSound(SoundEvents.PLAYER_LEVELUP, 0.8f, 1.2f);
            applyPerks(p);
        }
    }

    /** Combat damage and Fishing luck, from the player's levels (run on level-up and every few seconds). */
    static void applyPerks(ServerPlayer p) {
        MinecraftServer server = p.level().getServer();
        int combat = level(xp(server, p, Skill.COMBAT)), fishing = level(xp(server, p, Skill.FISHING));
        var dmg = p.getAttribute(Attributes.ATTACK_DAMAGE);
        if (dmg != null) {
            dmg.removeModifier(COMBAT_MOD);
            if (combat > 0) dmg.addTransientModifier(new AttributeModifier(COMBAT_MOD, 0.01 * combat, AttributeModifier.Operation.ADD_MULTIPLIED_TOTAL));
        }
        var luck = p.getAttribute(Attributes.LUCK);
        if (luck != null) {
            luck.removeModifier(FISHING_MOD);
            if (fishing > 0) luck.addTransientModifier(new AttributeModifier(FISHING_MOD, 0.2 * fishing, AttributeModifier.Operation.ADD_VALUE));
        }
    }

    // ------------------------------------------------------------------ hooks
    /** PlayerBlockBreakEvents.AFTER */
    static void onBreak(Level world, Player player, BlockPos pos, BlockState state, BlockEntity be) {
        if (!(player instanceof ServerPlayer p) || !(world instanceof ServerLevel level) || p.isCreative()) return;
        Block b = state.getBlock();
        int farm = farmingXp(state);
        boolean placed = farm == 0 || b == Blocks.MELON || b == Blocks.PUMPKIN ? Placed.take(level, pos) : false;   // grown crops can't be placed
        if (placed) return;
        Skill skill; int amount;
        if (farm > 0) { skill = Skill.FARMING; amount = farm; }
        else if (state.is(BlockTags.LOGS)) { skill = Skill.FORAGING; amount = 5; }
        else if (MINING_XP.containsKey(b)) { skill = Skill.MINING; amount = MINING_XP.get(b); }
        else return;
        gain(p, skill, amount);
        // double drops
        boolean doubles = skill != Skill.MINING || isOre(b);
        if (doubles && p.getRandom().nextInt(100) < 2 * level(xp(level.getServer(), p, skill)))
            for (ItemStack drop : Block.getDrops(state, level, pos, be, p, p.getMainHandItem())) Block.popResource(level, pos, drop);
    }

    /** From LivingEntityMixin: a living entity died. Hostile mobs and bosses give the killer Combat XP. */
    public static void onDeath(LivingEntity dead, net.minecraft.world.damagesource.DamageSource source) {
        if (!(dead instanceof Enemy) || dead instanceof Player) return;
        ServerPlayer killer = source.getEntity() instanceof ServerPlayer sp ? sp : dead.getKillCredit() instanceof ServerPlayer sp2 ? sp2 : null;
        if (killer == null) return;
        int amount = dead.entityTags().contains("cs_boss") ? 300 : Math.max(1, (int) (dead.getMaxHealth() / 2));
        gain(killer, Skill.COMBAT, amount);
    }

    private static final Map<UUID, Integer> fishSeen = new HashMap<>();
    private static int tick;
    /** Every second: Fishing XP for new catches (the fish_caught stat), and perks kept applied. */
    static void onTick(MinecraftServer server) {
        if (++tick % 20 != 0) return;
        for (ServerPlayer p : server.getPlayerList().getPlayers()) {
            int caught = p.getStats().getValue(Stats.CUSTOM.get(Stats.FISH_CAUGHT));
            Integer was = fishSeen.put(p.getUUID(), caught);
            if (was != null && caught > was) gain(p, Skill.FISHING, 30 * (caught - was));
            if (tick % 100 == 0) applyPerks(p);
        }
    }

    /** The skill average for the sidebar, one decimal. */
    static String average(MinecraftServer server, ServerPlayer p) {
        int sum = 0;
        for (Skill s : Skill.values()) sum += level(xp(server, p, s));
        return String.format(Locale.US, "%.1f", sum / (double) Skill.values().length);
    }

    // ------------------------------------------------------------------ /skills
    static int command(net.minecraft.commands.CommandSourceStack src) throws com.mojang.brigadier.exceptions.CommandSyntaxException {
        ServerPlayer p = src.getPlayerOrException();
        MinecraftServer server = src.getServer();
        SimpleContainer box = new SimpleContainer(27);
        ItemStack pane = new ItemStack(Economy.item("minecraft:black_stained_glass_pane"));
        pane.set(net.minecraft.core.component.DataComponents.CUSTOM_NAME, Component.literal(" "));
        for (int i = 0; i < 27; i++) box.setItem(i, pane.copy());
        int[] slots = {11, 12, 13, 14, 15};
        Skill[] all = Skill.values();
        for (int i = 0; i < all.length; i++) {
            Skill s = all[i];
            long x = xp(server, p, s);
            int l = level(x);
            ItemStack it = new ItemStack(s.icon);
            it.set(net.minecraft.core.component.DataComponents.CUSTOM_NAME, Component.literal(s.title + " " + l).withStyle(s.color, ChatFormatting.BOLD)
                    .withStyle(st -> st.withItalic(false)));
            List<Component> lore = new ArrayList<>();
            if (l < MAX) {
                long from = xpFor(l), to = xpFor(l + 1);
                int filled = (int) Math.round(20.0 * (x - from) / (to - from));
                lore.add(line("Progress to " + (l + 1) + ": ", ChatFormatting.GRAY).append(line(Economy.fmt(x - from) + "/" + Economy.fmt(to - from), ChatFormatting.YELLOW)));
                lore.add(line("■".repeat(filled), ChatFormatting.GREEN).append(line("■".repeat(20 - filled), ChatFormatting.DARK_GRAY)));
            } else lore.add(line("MAXED", ChatFormatting.GOLD));
            lore.add(Component.empty());
            lore.add(line("Perk: ", ChatFormatting.GRAY).append(line(s.perkValue(l) + s.perk, ChatFormatting.WHITE)));
            lore.add(line("Total XP: " + Economy.fmt(x), ChatFormatting.DARK_GRAY));
            it.set(net.minecraft.core.component.DataComponents.LORE, new net.minecraft.world.item.component.ItemLore(lore));
            box.setItem(slots[i], it);
        }
        ItemStack info = new ItemStack(Items.BOOK);
        info.set(net.minecraft.core.component.DataComponents.CUSTOM_NAME, line("Skill average: " + average(server, p), ChatFormatting.GOLD));
        info.set(net.minecraft.core.component.DataComponents.LORE, new net.minecraft.world.item.component.ItemLore(List.of(
                line("Farm, mine, chop, fight and fish to level up.", ChatFormatting.GRAY),
                line("Every level pays coins (100 x the level).", ChatFormatting.GRAY),
                line("Blocks you placed yourself give no XP.", ChatFormatting.DARK_GRAY))));
        box.setItem(4, info);
        p.openMenu(new SimpleMenuProvider((id, inv, pl) -> new ReadOnly(id, inv, box), Component.literal("Your Skills")));
        return 1;
    }
    static net.minecraft.network.chat.MutableComponent line(String t, ChatFormatting c) { return Component.literal(t).withStyle(st -> st.withColor(c).withItalic(false)); }

    /** A chest view nobody can take anything out of. */
    static final class ReadOnly extends ChestMenu {
        ReadOnly(int id, Inventory inv, SimpleContainer box) { super(MenuType.GENERIC_9x3, id, inv, box, 3); }
        @Override public void clicked(int slot, int button, ContainerInput input, Player player) {}
        @Override public ItemStack quickMoveStack(Player player, int slot) { return ItemStack.EMPTY; }
    }

    // ------------------------------------------------------------------ player-placed blocks
    /** Positions where players placed blocks (from BlockItemMixin), so breaking them gives no XP. In memory only,
     *  the oldest forgotten past CAP per dimension. */
    public static final class Placed {
        private Placed() {}
        static final int CAP = 200_000;
        private static final Map<ResourceKey<Level>, LinkedHashSet<Long>> BY_LEVEL = new HashMap<>();
        public static void add(Level level, BlockPos pos) {
            LinkedHashSet<Long> set = BY_LEVEL.computeIfAbsent(level.dimension(), k -> new LinkedHashSet<>());
            set.add(pos.asLong());
            if (set.size() > CAP) { Iterator<Long> it = set.iterator(); it.next(); it.remove(); }
        }
        static boolean take(Level level, BlockPos pos) {
            LinkedHashSet<Long> set = BY_LEVEL.get(level.dimension());
            return set != null && set.remove(pos.asLong());
        }
    }
}

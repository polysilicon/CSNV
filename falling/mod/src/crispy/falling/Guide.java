package crispy.falling;

import com.mojang.brigadier.CommandDispatcher;
import net.minecraft.ChatFormatting;
import net.minecraft.commands.CommandSourceStack;
import net.minecraft.commands.Commands;
import net.minecraft.core.component.DataComponents;
import net.minecraft.nbt.CompoundTag;
import net.minecraft.network.chat.Component;
import net.minecraft.network.chat.MutableComponent;
import net.minecraft.server.MinecraftServer;
import net.minecraft.server.level.ServerPlayer;
import net.minecraft.server.permissions.LevelBasedPermissionSet;
import net.minecraft.sounds.SoundEvents;
import net.minecraft.world.InteractionHand;
import net.minecraft.world.InteractionResult;
import net.minecraft.world.entity.player.Player;
import net.minecraft.world.item.Item;
import net.minecraft.world.item.ItemStack;
import net.minecraft.world.item.Items;
import net.minecraft.world.item.component.CustomData;
import net.minecraft.world.item.crafting.CraftingInput;
import net.minecraft.world.item.crafting.Ingredient;
import net.minecraft.world.item.crafting.Recipe;
import net.minecraft.world.item.crafting.RecipeHolder;
import net.minecraft.world.item.crafting.ShapedRecipe;
import net.minecraft.world.level.Level;

import java.util.*;

import static crispy.falling.Ui.t;

/**
 * The Skyblock Guide: a knowledge book every player gets on joining (and again with /guide book). Right-clicking it, or
 * /guide, opens a chest menu with how-to topics (each a page of notes), a recipe viewer for every crispy_skyblock
 * recipe (minions and gear, shown in a 3x3 grid), a progression page (the crispy_skyblock advancements, done or not),
 * and shortcuts to the other menus (skills, challenges, upgrades, pets, gear, Bazaar, warps, plots).
 */
final class Guide {
    private Guide() {}

    static final String MARK = "cs_guide";

    // ------------------------------------------------------------------ the book
    static ItemStack book() {
        ItemStack s = Ui.item(Items.KNOWLEDGE_BOOK, t("Skyblock Guide", ChatFormatting.GOLD, ChatFormatting.BOLD), List.of(
                t("Right-click to open", ChatFormatting.YELLOW),
                t("Recipes, skills, guides and your progress", ChatFormatting.GRAY),
                t("Lost it? /guide book", ChatFormatting.DARK_GRAY)), true);
        CompoundTag tag = new CompoundTag();
        tag.putBoolean(MARK, true);
        s.set(DataComponents.CUSTOM_DATA, CustomData.of(tag));
        s.set(DataComponents.MAX_STACK_SIZE, 1);
        return s;
    }
    static boolean isGuide(ItemStack s) {
        CustomData cd = s.get(DataComponents.CUSTOM_DATA);
        return cd != null && cd.copyTag().getBooleanOr(MARK, false);
    }
    static boolean has(ServerPlayer p) {
        var inv = p.getInventory();
        for (int i = 0; i < inv.getContainerSize(); i++) if (isGuide(inv.getItem(i))) return true;
        return false;
    }
    static void give(ServerPlayer p) {
        if (has(p)) return;
        ItemStack b = book();
        if (!p.getInventory().add(b)) p.drop(b, false);
    }

    /** Join: everyone gets one the first time (tag cs_guide on the player). */
    static void onJoin(ServerPlayer p) {
        if (p.entityTags().contains(MARK)) return;
        p.addTag(MARK);
        give(p);
        p.sendSystemMessage(t("📖 You've got a Skyblock Guide: right-click it any time for recipes, skills and tips.", ChatFormatting.GOLD));
    }

    /** UseItemCallback: right-clicking the guide opens it instead of the knowledge book's own use. */
    static InteractionResult onUseItem(Player player, Level world, InteractionHand hand) {
        if (!(player instanceof ServerPlayer p) || !isGuide(p.getItemInHand(hand))) return InteractionResult.PASS;
        p.playSound(SoundEvents.BOOK_PAGE_TURN, 1f, 1f);
        open(p);
        return InteractionResult.SUCCESS;
    }

    // ------------------------------------------------------------------ main page
    static void open(ServerPlayer p) {
        Ui.open(p, t("Skyblock Guide", ChatFormatting.DARK_GRAY), 6, m -> {
            m.put(4, Ui.item(Items.KNOWLEDGE_BOOK, t("Skyblock Guide", ChatFormatting.GOLD, ChatFormatting.BOLD), List.of(
                    t("Pick a topic to read about it,", ChatFormatting.GRAY), t("or jump straight to a menu below.", ChatFormatting.GRAY)), true), null);
            int[] slots = {19, 20, 21, 22, 23, 24, 25, 28, 29, 30, 31, 32, 33, 34};
            for (int i = 0; i < TOPICS.size() && i < slots.length; i++) {
                Topic tp = TOPICS.get(i);
                m.put(slots[i], Ui.item(tp.icon(), t(tp.title(), ChatFormatting.YELLOW, ChatFormatting.BOLD), List.of(t(tp.blurb(), ChatFormatting.GRAY),
                        Component.empty(), t("Click to read", ChatFormatting.DARK_GRAY)), false), (pl, c) -> topic(pl, tp));
            }
            m.put(46, Ui.item(Items.CRAFTING_TABLE, t("Recipes", ChatFormatting.GREEN, ChatFormatting.BOLD), List.of(
                    t("Every custom recipe: minions and gear", ChatFormatting.GRAY)), false), (pl, c) -> recipeCats(pl));
            m.put(47, Ui.item(Items.NETHER_STAR, t("Progression", ChatFormatting.LIGHT_PURPLE, ChatFormatting.BOLD), List.of(
                    t("Your Skyblock milestones, done and to do", ChatFormatting.GRAY)), false), (pl, c) -> progression(pl, 0));
            menuButton(m, 48, Items.IRON_SWORD, "Your skills", "Levels, XP and perks", "skills");
            menuButton(m, 49, Items.WRITABLE_BOOK, "Challenges", "One-time hand-ins for rewards", "island challenges");
            menuButton(m, 50, Items.GRASS_BLOCK, "Island upgrades", "Size, minion slots, co-op, ore generator", "island upgrades");
            menuButton(m, 51, Items.BONE, "Pets", "Buy and choose a pet", "pets");
            menuButton(m, 52, Items.DIAMOND_CHESTPLATE, "Armor & weapons", "Every set and weapon with its recipe", "gear");
            menuButton(m, 45, Items.EMERALD, "Bazaar", "Buy and sell with other players", "bazaar");
            menuButton(m, 53, Items.COMPASS, "Warps", "Hub, home, mines, woods, plots", "warp");
        });
    }

    static void menuButton(Ui.Menu m, int slot, Item icon, String name, String line, String command) {
        m.put(slot, Ui.item(icon, t(name, ChatFormatting.AQUA, ChatFormatting.BOLD), List.of(t(line, ChatFormatting.GRAY), Component.empty(),
                t("/" + command, ChatFormatting.DARK_GRAY)), false), (pl, c) -> run(pl, command));
    }
    static void run(ServerPlayer p, String command) {
        p.closeContainer();
        p.level().getServer().getCommands().performPrefixedCommand(p.createCommandSourceStack(), command);
    }
    static ItemStack back() { return Ui.item(Items.ARROW, t("Back", ChatFormatting.YELLOW), List.of(), false); }

    // ------------------------------------------------------------------ topics
    record Page(String head, String text) {}
    record Topic(String title, Item icon, String blurb, List<Page> pages) {}

    static List<Component> wrap(String text, ChatFormatting col) {
        List<Component> out = new ArrayList<>();
        for (String para : text.split("\n")) {
            StringBuilder line = new StringBuilder();
            for (String w : para.split(" ")) {
                if (line.length() + w.length() + 1 > 38 && line.length() > 0) { out.add(t(line.toString(), col)); line.setLength(0); }
                if (line.length() > 0) line.append(' ');
                line.append(w);
            }
            if (line.length() > 0) out.add(t(line.toString(), col));
        }
        return out;
    }

    static void topic(ServerPlayer p, Topic tp) {
        int rows = tp.pages().size() > 7 ? 4 : 3;
        Ui.open(p, t("Guide: " + tp.title(), ChatFormatting.DARK_GRAY), rows, m -> {
            int[] slots = {10, 11, 12, 13, 14, 15, 16, 19, 20, 21, 22, 23, 24, 25};
            for (int i = 0; i < tp.pages().size() && i < slots.length; i++) {
                Page pg = tp.pages().get(i);
                m.put(slots[i], Ui.item(i == 0 ? tp.icon() : Items.PAPER, t(pg.head(), ChatFormatting.GOLD, ChatFormatting.BOLD), wrap(pg.text(), ChatFormatting.GRAY), false), null);
            }
            m.put(rows * 9 - 9, back(), (pl, c) -> open(pl));
        });
    }

    static Page pg(String head, String text) { return new Page(head, text); }
    static final List<Topic> TOPICS = List.of(
            new Topic("Getting started", Items.OAK_SAPLING, "Your first hour on Skyblock", List.of(
                    pg("Your island", "Press Esc and open the Island Menu, or type /island. The first time, pick one of seven starter islands. Each has a chest of supplies and its own biome."),
                    pg("Gifts from the sky", "While you play, the sky drops things near your island: an animal every 15 min, a supply crate every 25, a meteor full of ore every 45, dungeons at 30, 90 and 180 min, and an End portal at 150 min."),
                    pg("Coins", "Sell crops, ores, wood and mob drops to the merchants in the hub, or to other players on the Bazaar. Coins buy upgrades, pets, plots and supplies."),
                    pg("Don't fall!", "The void is below every island. Build carefully and keep a few blocks spare. If you fall in the hub you're caught and sent back to spawn."),
                    pg("Next steps", "Hand in challenges for rewards, craft minions to gather while you're away, level up your skills and climb the island leaderboard with /island level."))),
            new Topic("Islands & portals", Items.CRYING_OBSIDIAN, "Your island, its portals and its realms", List.of(
                    pg("Hub portal", "Every island has a portal 14 blocks north of its centre, out over the void. Build a bridge to it and walk through to reach the hub. The hub's purple portal takes you home."),
                    pg("Island level", "/island level counts the blocks on your island: 100 points make a level. Valuable blocks like diamond or netherite blocks count for more. /island top shows the best islands."),
                    pg("Co-op", "/invite <player> lets a friend join your island. Upgrade co-op slots for up to 8 members."),
                    pg("Your Nether", "Build a Nether portal to reach your island's own Nether. Fortress wrecks with blaze spawners and bastion chunks crash in over time."),
                    pg("Your End", "The End portal appears east of your island after 150 min of play. Fill it with 12 Eyes of Ender to reach your island's own End, with a boss altar in the middle."))),
            new Topic("Minions", Items.ARMOR_STAND, "Helpers that gather while you're offline", List.of(
                    pg("Crafting", "Put 8 of a resource around a wooden pickaxe at a crafting table. There are minions for crops, wood, ores, sand, clay and mobs. See Recipes."),
                    pg("Using them", "Place a minion on your island. It gathers on its own, even while you're offline. Right-click it to collect, upgrade it (I to V) or pick it up."),
                    pg("Slots", "Islands have a limited number of minion slots. Island upgrades add 2 more per tier."))),
            new Topic("Merchants & Bazaar", Items.EMERALD, "Earning and spending coins", List.of(
                    pg("Merchants", "Five merchants stand in market stalls round the hub's plaza: Farming, Mining, Foraging, Combat and Supplies. Click one to buy or sell."),
                    pg("The Bazaar", "/bz or the Bazaar NPC. Place sell offers or buy orders at your own price; they fill against other players' orders. Sellers pay a 1% tax. Claim your coins and items under My orders."))),
            new Topic("Skills", Items.EXPERIENCE_BOTTLE, "Five skills that level as you play", List.of(
                    pg("Farming", "XP from fully grown crops. Perk: a chance of double crops."),
                    pg("Mining", "XP from ores and stone. Perk: a chance of double ore drops."),
                    pg("Foraging", "XP from logs. Perk: a chance of double logs."),
                    pg("Combat", "XP from hostile mobs and bosses. Perk: extra damage."),
                    pg("Fishing", "XP for every catch. Perk: extra luck, so better catches."),
                    pg("Levelling", "Each skill goes to level 25 and every level pays coins. Blocks you placed yourself give no XP. /skills shows your progress."))),
            new Topic("Pets", Items.BONE, "Companions that boost a skill", List.of(
                    pg("Buying", "Open /pets to buy a pet and choose which one follows you. It floats beside you."),
                    pg("Boosts", "Each pet boosts one skill's XP by 10%, plus 1% per pet level, and gives a small bonus. Pets level up from the XP they boost, up to level 30."),
                    pg("The Phoenix", "Can't be bought. Every End boss kill gives each island member a 3% chance of one. It boosts every skill and gives extra hearts."))),
            new Topic("Gear & bosses", Items.NETHERITE_SWORD, "Armor sets, weapons and boss fights", List.of(
                    pg("Armor sets", "Craft armor from farmable blocks. Wearing all four pieces gives a set bonus. /gear shows every set and its recipe."),
                    pg("Weapons", "Some weapons and tools have right-click abilities with a cooldown."),
                    pg("Bosses", "Your End and Nether each have an altar. Right-click the lodestone twice to summon a boss. Beat it for coins and loot; the next one in line is tougher."))),
            new Topic("Resource zones", Items.IRON_PICKAXE, "Shared mines and woods", List.of(
                    pg("Getting there", "Use the orange and green portals in the hub, /warp mines or /warp woods. Each zone has a portal back to the hub."),
                    pg("Regrowth", "Only the zone's resources can be mined, and they grow back: ores after 45 s, logs after 30 s. You can't build there."),
                    pg("Mobs", "Monsters have levels shown over their heads: deeper in the mines means tougher. Kills pay coins. They don't burn in daylight."),
                    pg("Dying there", "You only drop what you gathered in the zone. Your gear and XP come back when you respawn."))),
            new Topic("Hub plots", Items.OAK_SIGN, "Buy a plot for a shop or house", List.of(
                    pg("Buying", "16 plots sit in a ring round the hub's hills. Click the Realtor, a plot's sign, or use /plots. One plot each."),
                    pg("Building", "You, players you trust (/plots trust <player>) and your island co-op can build in your plot. Chests in it are yours."),
                    pg("Abandoning", "From /plots you can give your plot up: it's cleared and you get half the price back."))),
            new Topic("Commands", Items.COMMAND_BLOCK, "Every command in one place", List.of(
                    pg("Island", "/island (/is), /island challenges, /island level, /island top, /invite <player>, /island upgrades"),
                    pg("Progress", "/skills, /pets, /gear, /guide"),
                    pg("Trading", "/bazaar (/bz), /plots"),
                    pg("Travel", "/warp hub, /warp home, /warp mines, /warp woods, /warp plots"))));

    // ------------------------------------------------------------------ recipes
    static List<RecipeHolder<?>> recipes(MinecraftServer server, String prefix) {
        List<RecipeHolder<?>> out = new ArrayList<>();
        for (RecipeHolder<?> h : server.getRecipeManager().getRecipes()) {
            var id = h.id().identifier();
            if (id.getNamespace().equals(SkyblockMod.NS) && id.getPath().startsWith(prefix)) out.add(h);
        }
        out.sort(Comparator.comparing(h -> h.id().identifier().getPath()));
        return out;
    }
    static ItemStack result(Recipe<?> r) {
        try {
            if (r instanceof ShapedRecipe s) return s.assemble(CraftingInput.EMPTY);
            if (r instanceof net.minecraft.world.item.crafting.ShapelessRecipe s) return s.assemble(CraftingInput.EMPTY);
        } catch (RuntimeException ignored) {}
        return new ItemStack(Items.BARRIER);
    }

    static void recipeCats(ServerPlayer p) {
        MinecraftServer server = p.level().getServer();
        Ui.open(p, t("Guide: Recipes", ChatFormatting.DARK_GRAY), 3, m -> {
            m.put(11, Ui.item(Items.ARMOR_STAND, t("Minions", ChatFormatting.GREEN, ChatFormatting.BOLD), List.of(
                    t(recipes(server, "minion_").size() + " recipes", ChatFormatting.GRAY)), false), (pl, c) -> recipeList(pl, "minion_", "Minions", 0));
            m.put(15, Ui.item(Items.DIAMOND_CHESTPLATE, t("Armor, weapons & tools", ChatFormatting.AQUA, ChatFormatting.BOLD), List.of(
                    t(recipes(server, "gear/").size() + " recipes", ChatFormatting.GRAY)), false), (pl, c) -> recipeList(pl, "gear/", "Gear", 0));
            m.put(18, back(), (pl, c) -> open(pl));
        });
    }

    static void recipeList(ServerPlayer p, String prefix, String title, int page) {
        MinecraftServer server = p.level().getServer();
        List<RecipeHolder<?>> all = recipes(server, prefix);
        int pages = Math.max(1, (all.size() + 44) / 45);
        Ui.open(p, t("Recipes: " + title + (pages > 1 ? " (" + (page + 1) + "/" + pages + ")" : ""), ChatFormatting.DARK_GRAY), 6, m -> {
            for (int i = 0; i < 45 && page * 45 + i < all.size(); i++) {
                RecipeHolder<?> h = all.get(page * 45 + i);
                ItemStack icon = result(h.value()).copy();
                List<Component> lore = new ArrayList<>(icon.getOrDefault(DataComponents.LORE, net.minecraft.world.item.component.ItemLore.EMPTY).lines());
                lore.add(Component.empty());
                lore.add(t("Click to see the recipe", ChatFormatting.YELLOW));
                icon.set(DataComponents.LORE, new net.minecraft.world.item.component.ItemLore(lore));
                m.put(i, icon, (pl, c) -> recipe(pl, h, prefix, title, page));
            }
            m.put(45, back(), (pl, c) -> recipeCats(pl));
            if (page > 0) m.put(48, Ui.item(Items.ARROW, t("Previous page", ChatFormatting.YELLOW), List.of(), false), (pl, c) -> recipeList(pl, prefix, title, page - 1));
            if (page + 1 < pages) m.put(50, Ui.item(Items.ARROW, t("Next page", ChatFormatting.YELLOW), List.of(), false), (pl, c) -> recipeList(pl, prefix, title, page + 1));
        });
    }

    static ItemStack ingredient(Optional<Ingredient> ing) {
        if (ing.isEmpty() || ing.get().isEmpty()) return ItemStack.EMPTY;
        List<net.minecraft.core.Holder<Item>> items = ing.get().items().toList();
        if (items.isEmpty()) return ItemStack.EMPTY;
        ItemStack s = new ItemStack(items.get(0));
        if (items.size() > 1) {
            List<Component> lore = new ArrayList<>();
            lore.add(t("Any of:", ChatFormatting.GRAY));
            for (int i = 0; i < items.size() && i < 8; i++) lore.add(t("• " + new ItemStack(items.get(i)).getHoverName().getString(), ChatFormatting.DARK_GRAY));
            if (items.size() > 8) lore.add(t("…and " + (items.size() - 8) + " more", ChatFormatting.DARK_GRAY));
            s.set(DataComponents.LORE, new net.minecraft.world.item.component.ItemLore(lore));
        }
        return s;
    }

    static void recipe(ServerPlayer p, RecipeHolder<?> h, String prefix, String title, int page) {
        Recipe<?> r = h.value();
        ItemStack out = result(r);
        Ui.open(p, t("Recipe: " + out.getHoverName().getString(), ChatFormatting.DARK_GRAY), 5, m -> {
            int[] grid = {10, 11, 12, 19, 20, 21, 28, 29, 30};
            if (r instanceof ShapedRecipe s) {
                List<Optional<Ingredient>> ings = s.getIngredients();
                for (int y = 0; y < s.getHeight(); y++)
                    for (int x = 0; x < s.getWidth(); x++) {
                        ItemStack st = ingredient(ings.get(y * s.getWidth() + x));
                        if (!st.isEmpty()) m.put(grid[y * 3 + x], st, null);
                    }
            } else {
                List<Ingredient> ings = r.placementInfo().ingredients();
                for (int i = 0; i < ings.size() && i < 9; i++) {
                    ItemStack st = ingredient(Optional.of(ings.get(i)));
                    if (!st.isEmpty()) m.put(grid[i], st, null);
                }
                m.put(4, Ui.item(Items.PAPER, t("Shapeless: any arrangement", ChatFormatting.GRAY), List.of(), false), null);
            }
            m.put(23, Ui.item(Items.CRAFTING_TABLE, t("Craft at a crafting table →", ChatFormatting.YELLOW), List.of(), false), null);
            m.put(25, out, null);
            m.put(36, back(), (pl, c) -> recipeList(pl, prefix, title, page));
        });
    }

    // ------------------------------------------------------------------ progression
    static void progression(ServerPlayer p, int page) {
        MinecraftServer server = p.level().getServer();
        List<net.minecraft.advancements.AdvancementHolder> all = new ArrayList<>();
        for (var h : server.getAdvancements().getAllAdvancements())
            if (h.id().getNamespace().equals(SkyblockMod.NS) && h.value().display().isPresent()) all.add(h);
        Map<net.minecraft.resources.Identifier, Integer> depth = new HashMap<>();
        for (var h : all) {
            int d = 0;
            var par = h.value().parent();
            while (par.isPresent() && d < 20) { d++; var ph = server.getAdvancements().get(par.get()); par = ph == null ? Optional.empty() : ph.value().parent(); }
            depth.put(h.id(), d);
        }
        all.sort(Comparator.comparing((net.minecraft.advancements.AdvancementHolder h) -> depth.get(h.id())).thenComparing(h -> h.id().getPath()));
        int done = 0;
        for (var h : all) if (p.getAdvancements().getOrStartProgress(h).isDone()) done++;
        final int doneN = done;
        Ui.open(p, t("Guide: Progression (" + done + "/" + all.size() + ")", ChatFormatting.DARK_GRAY), 6, m -> {
            for (int i = 0; i < all.size() && i < 45; i++) {
                var h = all.get(i);
                var d = h.value().display().get();
                boolean got = p.getAdvancements().getOrStartProgress(h).isDone();
                ItemStack icon = got ? d.getIcon().create() : new ItemStack(Economy.item("minecraft:gray_dye"));
                MutableComponent name = d.getTitle().copy().withStyle(got ? ChatFormatting.GREEN : ChatFormatting.GRAY);
                List<Component> lore = new ArrayList<>(wrap(d.getDescription().getString(), ChatFormatting.GRAY));
                lore.add(Component.empty());
                lore.add(got ? t("✔ Done", ChatFormatting.GREEN) : t("✘ Not yet", ChatFormatting.RED));
                m.put(i, Ui.item(icon, name, lore, got), null);
            }
            m.put(49, Ui.item(Items.NETHER_STAR, t(doneN + " of " + all.size() + " milestones", ChatFormatting.LIGHT_PURPLE, ChatFormatting.BOLD), List.of(
                    t("Island level: " + SkyblockMod.score(server, p, "cs_lvl"), ChatFormatting.GRAY),
                    t("Skill average: " + Skills.average(server, p), ChatFormatting.GRAY),
                    t("Coins: " + Economy.fmt(Economy.coins(server, p)), ChatFormatting.GOLD)), false), null);
            m.put(45, back(), (pl, c) -> open(pl));
        });
    }

    // ------------------------------------------------------------------ command
    static void register(CommandDispatcher<CommandSourceStack> d) {
        d.register(Commands.literal("guide").executes(c -> { open(c.getSource().getPlayerOrException()); return 1; })
                .then(Commands.literal("book").executes(c -> {
                    ServerPlayer p = c.getSource().getPlayerOrException();
                    if (has(p)) { c.getSource().sendFailure(Component.literal("You already have a Skyblock Guide.")); return 0; }
                    give(p);
                    p.sendSystemMessage(t("Here's a new Skyblock Guide.", ChatFormatting.GOLD));
                    return 1;
                })));
    }
}

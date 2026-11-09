package crispy.falling;

import com.mojang.brigadier.CommandDispatcher;
import net.minecraft.ChatFormatting;
import net.minecraft.commands.CommandSourceStack;
import net.minecraft.commands.Commands;
import net.minecraft.core.component.DataComponents;
import net.minecraft.core.registries.BuiltInRegistries;
import net.minecraft.nbt.CompoundTag;
import net.minecraft.nbt.ListTag;
import net.minecraft.network.chat.Component;
import net.minecraft.network.protocol.game.ClientboundContainerSetSlotPacket;
import net.minecraft.server.MinecraftServer;
import net.minecraft.server.level.ServerLevel;
import net.minecraft.server.level.ServerPlayer;
import net.minecraft.world.entity.player.Inventory;
import net.minecraft.world.entity.player.Player;
import net.minecraft.world.inventory.AbstractContainerMenu;
import net.minecraft.world.inventory.CraftingContainer;
import net.minecraft.world.inventory.ResultContainer;
import net.minecraft.world.item.Item;
import net.minecraft.world.item.ItemStack;
import net.minecraft.world.item.Items;
import net.minecraft.world.item.component.CustomData;
import net.minecraft.world.item.component.ItemLore;
import net.minecraft.world.item.crafting.CraftingInput;
import net.minecraft.world.item.crafting.RecipeHolder;
import net.minecraft.world.item.crafting.RecipeType;

import java.util.*;

import static crispy.falling.Ui.t;

/**
 * Enchanted resources (2.16.5), crafted like Hypixel SkyBlock's: the resource in a plus shape at a crafting table with
 * 32 in each of the 5 slots (160 in all) makes one glowing "Enchanted <resource>" (the same item with custom_data
 * cs_ench). The recipes are the datapack's crispy_skyblock:enchanted/<item>; a recipe can't ask for 32 per slot, so
 * CraftingMenuMixin (check) hides the result until every slot has 32, and ResultSlotMixin (consume) takes the other 31. The newer gear recipes (the datapack's eco cfg "ench": recipe id -> the
 * items that must be enchanted) only craft when those slots hold enchanted ones; a recipe can't check custom data, so
 * CraftingMenuMixin calls check() after vanilla works out the result and clears it if the ingredients are wrong. Every
 * other recipe refuses enchanted items, so nobody turns 64 logs into 4 planks by mistake. Crafters can't make the
 * enchanted-gear recipes at all (CrafterBlockMixin).
 */
public final class Compact {
    private Compact() {}

    static final int PER_SLOT = 32, SLOTS = 5, PER = PER_SLOT * SLOTS;
    private static final Map<UUID, Long> told = new HashMap<>();

    public static boolean enchanted(ItemStack s) {
        CustomData cd = s.get(DataComponents.CUSTOM_DATA);
        return cd != null && cd.copyTag().getBooleanOr("cs_ench", false);
    }

    static String nice(Item item) { return new ItemStack(item).getHoverName().getString(); }

    static ItemStack make(Item item, int count) {
        ItemStack s = new ItemStack(item, count);
        s.set(DataComponents.CUSTOM_NAME, Component.literal("Enchanted " + nice(item)).withStyle(st -> st.withItalic(false).withColor(ChatFormatting.GREEN)));
        s.set(DataComponents.LORE, new ItemLore(List.of(
                Component.literal(PER + " " + nice(item) + " crafted into one.").withStyle(st -> st.withItalic(false).withColor(ChatFormatting.GRAY)),
                Component.literal("Used to craft gear (see /guide > Recipes).").withStyle(st -> st.withItalic(false).withColor(ChatFormatting.DARK_GRAY)))));
        s.set(DataComponents.ENCHANTMENT_GLINT_OVERRIDE, true);
        CompoundTag tag = new CompoundTag();
        tag.putBoolean("cs_ench", true);
        s.set(DataComponents.CUSTOM_DATA, CustomData.of(tag));
        return s;
    }

    static List<Item> pressable(MinecraftServer server) {
        List<Item> out = new ArrayList<>();
        ListTag l = Economy.cfg(server).getListOrEmpty("compact");
        for (int i = 0; i < l.size(); i++) {
            Item it = Economy.item(l.getStringOr(i, ""));
            if (it != Items.AIR) out.add(it);
        }
        return out;
    }

    /** Recipe id -> items that must be enchanted in it. */
    static Map<String, Set<Item>> rules(MinecraftServer server) {
        Map<String, Set<Item>> out = new HashMap<>();
        ListTag l = Economy.cfg(server).getListOrEmpty("ench");
        for (int i = 0; i < l.size(); i++) {
            CompoundTag r = l.getCompoundOrEmpty(i);
            Set<Item> items = new HashSet<>();
            ListTag il = r.getListOrEmpty("items");
            for (int j = 0; j < il.size(); j++) items.add(Economy.item(il.getStringOr(j, "")));
            out.put(r.getStringOr("recipe", ""), items);
        }
        return out;
    }
    public static boolean needsEnchanted(MinecraftServer server, RecipeHolder<?> h) {
        return h != null && rules(server).containsKey(h.id().identifier().toString());
    }

    // ------------------------------------------------------------------ crafting checks (mixins)
    /** After vanilla works out a crafting grid's result: clear it when the recipe needs enchanted resources it hasn't
     *  got, or when enchanted items are used in any other recipe. */
    public static void check(AbstractContainerMenu menu, ServerLevel level, Player player, CraftingContainer grid, ResultContainer result) {
        if (result.getItem(0).isEmpty() || !(player instanceof ServerPlayer sp)) return;
        CraftingInput input = grid.asCraftInput();
        Optional<RecipeHolder<net.minecraft.world.item.crafting.CraftingRecipe>> found =
                level.getServer().getRecipeManager().getRecipeFor(RecipeType.CRAFTING, input, level, (RecipeHolder<net.minecraft.world.item.crafting.CraftingRecipe>) null);
        Set<Item> need = found.map(h -> rules(level.getServer()).get(h.id().identifier().toString())).orElse(null);
        String why = null;
        if (found.isPresent() && isEnchantRecipe(found.get())) {   // 32 plain ones in every slot
            for (int i = 0; i < grid.getContainerSize(); i++) {
                ItemStack s = grid.getItem(i);
                if (s.isEmpty()) continue;
                if (enchanted(s) || !Economy.plain(s)) { why = "Use plain " + nice(s.getItem()) + " here."; break; }
                if (s.getCount() < PER_SLOT) { why = "Enchanted " + nice(s.getItem()) + " needs " + PER_SLOT + " in each of the 5 slots (" + PER + " in all)."; break; }
            }
            if (why == null) return;
            need = Set.of();
        }
        else
        for (int i = 0; i < grid.getContainerSize() && why == null; i++) {
            ItemStack s = grid.getItem(i);
            if (s.isEmpty()) continue;
            boolean ench = enchanted(s);
            if (need == null && ench) { why = "Enchanted items only go into the gear that needs them."; break; }
            if (need != null && need.contains(s.getItem()) && !ench) { why = "This needs Enchanted " + nice(s.getItem()) + " (" + PER + " crafted into one: see /guide > Recipes)."; break; }
            if (need != null && !need.contains(s.getItem()) && ench) { why = "Only the " + names(need) + " should be enchanted here."; break; }
        }
        if (why == null) return;
        result.setItem(0, ItemStack.EMPTY);
        menu.setRemoteSlot(0, ItemStack.EMPTY);
        sp.connection.send(new ClientboundContainerSetSlotPacket(menu.containerId, menu.incrementStateId(), 0, ItemStack.EMPTY));
        long now = System.currentTimeMillis();
        if (told.getOrDefault(sp.getUUID(), 0L) + 1500 < now) {
            told.put(sp.getUUID(), now);
            sp.sendOverlayMessage(t(why, ChatFormatting.RED));
        }
    }
    static String names(Set<Item> items) {
        List<String> l = new ArrayList<>();
        for (Item i : items) l.add(nice(i));
        Collections.sort(l);
        return String.join(" and ", l);
    }

    public static boolean isEnchantRecipe(RecipeHolder<?> h) {
        var id = h.id().identifier();
        return id.getNamespace().equals(SkyblockMod.NS) && id.getPath().startsWith("enchanted/");
    }
    /** ResultSlot.onTake, before vanilla takes one from each slot: take the other 31 of an enchanted-resource craft. */
    public static void consume(Player player, CraftingContainer grid) {
        if (!(player.level() instanceof ServerLevel level)) return;
        CraftingInput input = grid.asCraftInput();
        var found = level.getServer().getRecipeManager().getRecipeFor(RecipeType.CRAFTING, input, level,
                (RecipeHolder<net.minecraft.world.item.crafting.CraftingRecipe>) null);
        if (found.isEmpty() || !isEnchantRecipe(found.get())) return;
        for (int i = 0; i < grid.getContainerSize(); i++) {
            ItemStack s = grid.getItem(i);
            if (!s.isEmpty()) s.shrink(Math.min(PER_SLOT - 1, s.getCount() - 1));
        }
    }

    /** The guide's recipe view: the stack to show for an ingredient of recipe h. */
    static ItemStack guideIngredient(MinecraftServer server, RecipeHolder<?> h, ItemStack plain) {
        if (plain.isEmpty()) return plain;
        Set<Item> need = rules(server).get(h.id().identifier().toString());
        return need != null && need.contains(plain.getItem()) ? make(plain.getItem(), 1) : plain;
    }

    static String id(Item i) { return BuiltInRegistries.ITEM.getKey(i).toString(); }
}

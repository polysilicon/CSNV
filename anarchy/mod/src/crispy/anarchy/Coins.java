package crispy.anarchy;

import net.fabricmc.fabric.api.event.lifecycle.v1.ServerTickEvents;
import net.minecraft.core.component.DataComponents;
import net.minecraft.nbt.NbtOps;
import net.minecraft.nbt.TagParser;
import net.minecraft.network.chat.Component;
import net.minecraft.server.MinecraftServer;
import net.minecraft.server.level.ServerPlayer;
import net.minecraft.world.Container;
import net.minecraft.world.item.ItemStack;
import net.minecraft.world.item.Items;
import net.minecraft.world.item.enchantment.ItemEnchantments;

/**
 * Old Gold Coins and Coin Bags (1.1.1). The market's villager trades ask for these items with exact data, but coins
 * and bags saved by older Minecraft versions carry the same name, colour and glint in older formats (names stored
 * as JSON text, every style flag spelled out, enchantments under "levels", a profile name of ""), so the villagers
 * refused them. About once a second every online player's inventory and ender chest is checked, and any old-format
 * coin or bag is rewritten into exactly the form the market uses (the SNBT below is copied from its trades).
 * Coins in chests are fixed as soon as someone takes them out.
 *
 * Only the real items match: a coin is a sunflower that is enchanted (sunflowers can't be enchanted in survival,
 * so an anvil-renamed sunflower doesn't count) and named Gold Coin; a bag is a player head with the Coin Bag skin
 * and name.
 */
final class Coins {
    private Coins() {}

    static final String BAG_TEXTURE = "eyJ0ZXh0dXJlcyI6eyJTS0lOIjp7InVybCI6Imh0dHA6Ly90ZXh0dXJlcy5taW5lY3JhZnQubmV0L3RleHR1cmUvODM4MWM1MjlkNTJlMDNjZDc0YzNiZjM4YmI2YmEzZmRlMTMzN2FlOWJmNTAzMzJmYWE4ODllMGEyOGU4MDgxZiJ9fX0=";
    static final String COIN_SNBT = "{id:\"minecraft:sunflower\",count:1,components:{\"minecraft:custom_name\":{text:\"Gold Coin\",italic:false,color:\"gold\",bold:true},\"minecraft:lore\":[{text:\" -Used for special shop items\",italic:false,color:\"dark_purple\"}],\"minecraft:enchantments\":{\"minecraft:unbreaking\":1}}}";
    static final String BAG_SNBT = "{id:\"minecraft:player_head\",count:1,components:{\"minecraft:custom_name\":{text:\"Coin Bag\",italic:false,color:\"blue\"},\"minecraft:damage\":3,\"minecraft:profile\":{id:[I;67411088,-739686879,-1666252800,-1432091390],properties:[{name:\"textures\",value:\"" + BAG_TEXTURE + "\"}]}}}";

    private static ItemStack coin, bag;
    private static int tick;

    static void init() {
        ServerTickEvents.END_SERVER_TICK.register(server -> {
            if (++tick % 20 != 0) return;
            if (coin == null && !load(server)) return;
            for (ServerPlayer p : server.getPlayerList().getPlayers()) {
                fix(p.getInventory());
                fix(p.getEnderChestInventory());
            }
        });
    }

    private static boolean load(MinecraftServer server) {
        try {
            var ops = server.registryAccess().createSerializationContext(NbtOps.INSTANCE);
            coin = ItemStack.CODEC.parse(ops, TagParser.parseCompoundFully(COIN_SNBT)).getOrThrow();
            bag = ItemStack.CODEC.parse(ops, TagParser.parseCompoundFully(BAG_SNBT)).getOrThrow();
            return true;
        } catch (Exception e) {
            System.err.println("[crispy-anarchy] can't build the market's coin items: " + e);
            coin = ItemStack.EMPTY; bag = ItemStack.EMPTY;   // don't retry every second
            return false;
        }
    }

    static void fix(Container c) {
        if (coin.isEmpty()) return;
        boolean changed = false;
        for (int i = 0; i < c.getContainerSize(); i++) {
            ItemStack s = c.getItem(i);
            if (s.isEmpty()) continue;
            ItemStack want = isCoin(s) ? coin : isBag(s) ? bag : null;
            if (want == null || ItemStack.isSameItemSameComponents(s, want)) continue;
            c.setItem(i, want.copyWithCount(s.getCount()));
            changed = true;
        }
        if (changed) c.setChanged();
    }

    static String name(ItemStack s) {
        Component n = s.get(DataComponents.CUSTOM_NAME);
        return n == null ? "" : n.getString();   // the old JSON-text names read as their raw text, which still contains the name
    }

    static boolean isCoin(ItemStack s) {
        return s.is(Items.SUNFLOWER) && name(s).contains("Gold Coin")
                && !s.getOrDefault(DataComponents.ENCHANTMENTS, ItemEnchantments.EMPTY).isEmpty();
    }

    static boolean isBag(ItemStack s) {
        if (!s.is(Items.PLAYER_HEAD) || !name(s).contains("Coin Bag")) return false;
        var profile = s.get(DataComponents.PROFILE);
        if (profile == null) return false;
        for (var prop : profile.partialProfile().properties().get("textures"))
            if (BAG_TEXTURE.equals(prop.value())) return true;
        return false;
    }
}

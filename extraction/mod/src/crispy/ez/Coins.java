package crispy.ez;

import net.fabricmc.fabric.api.event.lifecycle.v1.ServerTickEvents;
import net.minecraft.core.component.DataComponents;
import net.minecraft.nbt.NbtOps;
import net.minecraft.nbt.TagParser;
import net.minecraft.server.MinecraftServer;
import net.minecraft.server.level.ServerPlayer;
import net.minecraft.world.entity.player.Inventory;
import net.minecraft.world.item.ItemStack;
import net.minecraft.world.item.Items;
import net.minecraft.world.item.component.CustomData;

/**
 * The Zone's money is Anarchy's Gold Coin (same item, same look), and 64 coins condense into a Coin Bag. Everything
 * that costs or pays money goes through here: count() counts coins and bags (a bag is 64), take() spends coins first
 * and breaks a bag for change when it has to, give() pays out in bags and coins.
 * Old Credits (gold nuggets from before 1.1.0) in a player's inventory are swapped for the same number of coins.
 */
final class Coins {
    private Coins() {}

    static final int BAG = 64;
    static final String BAG_TEXTURE = "eyJ0ZXh0dXJlcyI6eyJTS0lOIjp7InVybCI6Imh0dHA6Ly90ZXh0dXJlcy5taW5lY3JhZnQubmV0L3RleHR1cmUvODM4MWM1MjlkNTJlMDNjZDc0YzNiZjM4YmI2YmEzZmRlMTMzN2FlOWJmNTAzMzJmYWE4ODllMGEyOGU4MDgxZiJ9fX0=";
    // exactly Anarchy's market items (anarchy/mod Coins.java)
    static final String COIN_SNBT = "{id:\"minecraft:sunflower\",count:1,components:{\"minecraft:custom_name\":{text:\"Gold Coin\",italic:false,color:\"gold\",bold:true},\"minecraft:lore\":[{text:\" -Used for special shop items\",italic:false,color:\"dark_purple\"}],\"minecraft:enchantments\":{\"minecraft:unbreaking\":1}}}";
    static final String BAG_SNBT = "{id:\"minecraft:player_head\",count:1,components:{\"minecraft:custom_name\":{text:\"Coin Bag\",italic:false,color:\"blue\"},\"minecraft:damage\":3,\"minecraft:profile\":{id:[I;67411088,-739686879,-1666252800,-1432091390],properties:[{name:\"textures\",value:\"" + BAG_TEXTURE + "\"}]}}}";

    static ItemStack coin = ItemStack.EMPTY, bag = ItemStack.EMPTY;
    static int tick;

    static void init() {
        ServerTickEvents.END_SERVER_TICK.register(server -> {
            if (++tick % 40 != 0) return;
            if (!load(server)) return;
            for (ServerPlayer p : server.getPlayerList().getPlayers()) migrate(p);
        });
    }

    static boolean load(MinecraftServer server) {
        if (!coin.isEmpty()) return true;
        try {
            var ops = server.registryAccess().createSerializationContext(NbtOps.INSTANCE);
            coin = ItemStack.CODEC.parse(ops, TagParser.parseCompoundFully(COIN_SNBT)).getOrThrow();
            bag = ItemStack.CODEC.parse(ops, TagParser.parseCompoundFully(BAG_SNBT)).getOrThrow();
            return true;
        } catch (Exception e) { System.err.println("[crispy-extraction] can't build the coin items: " + e); return false; }
    }

    static boolean isCoin(ItemStack s) { return !coin.isEmpty() && ItemStack.isSameItemSameComponents(s, coin); }
    static boolean isBag(ItemStack s) { return !bag.isEmpty() && ItemStack.isSameItemSameComponents(s, bag); }
    /** A coin's worth: 1 for a coin, 64 for a bag, else 0. */
    static int value(ItemStack s) { return isCoin(s) ? s.getCount() : isBag(s) ? s.getCount() * BAG : 0; }

    static int count(ServerPlayer p) {
        load(p.level().getServer());
        Inventory inv = p.getInventory(); int n = 0;
        for (int i = 0; i < inv.getContainerSize(); i++) n += value(inv.getItem(i));
        return n;
    }

    /** Take n coins' worth (coins first, then bags with change back). False, and nothing taken, if they can't afford it. */
    static boolean take(ServerPlayer p, int n) {
        if (n <= 0) return true;
        if (count(p) < n) return false;
        Inventory inv = p.getInventory();
        for (int i = 0; i < inv.getContainerSize() && n > 0; i++) {
            ItemStack s = inv.getItem(i);
            if (isCoin(s)) { int k = Math.min(n, s.getCount()); s.shrink(k); n -= k; }
        }
        for (int i = 0; i < inv.getContainerSize() && n > 0; i++) {
            ItemStack s = inv.getItem(i);
            while (n > 0 && isBag(s) && !s.isEmpty()) {
                s.shrink(1);
                int k = Math.min(n, BAG); n -= k;
                if (BAG - k > 0) Shops.give(p, coin.copyWithCount(BAG - k));   // change
            }
        }
        inv.setChanged();
        return true;
    }

    /** Pay n coins: whole bags first, the rest as coins. */
    static void give(ServerPlayer p, int n) {
        if (n <= 0 || !load(p.level().getServer())) return;
        if (n / BAG > 0) Shops.give(p, bag.copyWithCount(n / BAG));
        if (n % BAG > 0) Shops.give(p, coin.copyWithCount(n % BAG));
    }

    /** Every 64 loose coins in the inventory become a Coin Bag. Returns the number of bags made. */
    static int condense(ServerPlayer p) {
        Inventory inv = p.getInventory(); int loose = 0;
        for (int i = 0; i < inv.getContainerSize(); i++) if (isCoin(inv.getItem(i))) loose += inv.getItem(i).getCount();
        int bags = loose / BAG;
        if (bags == 0) return 0;
        int toTake = bags * BAG;
        for (int i = 0; i < inv.getContainerSize() && toTake > 0; i++) {
            ItemStack s = inv.getItem(i);
            if (isCoin(s)) { int k = Math.min(toTake, s.getCount()); s.shrink(k); toTake -= k; }
        }
        Shops.give(p, bag.copyWithCount(bags));
        inv.setChanged();
        return bags;
    }

    /** Break one Coin Bag into 64 coins. */
    static boolean breakBag(ServerPlayer p) {
        Inventory inv = p.getInventory();
        for (int i = 0; i < inv.getContainerSize(); i++) {
            ItemStack s = inv.getItem(i);
            if (isBag(s)) { s.shrink(1); Shops.give(p, coin.copyWithCount(BAG)); inv.setChanged(); return true; }
        }
        return false;
    }

    /** Old Credits (gold nugget, custom_data ez:"credit") -> the same number of Gold Coins. */
    static void migrate(ServerPlayer p) {
        Inventory inv = p.getInventory();
        for (int i = 0; i < inv.getContainerSize(); i++) {
            ItemStack s = inv.getItem(i);
            if (!s.is(Items.GOLD_NUGGET)) continue;
            CustomData cd = s.get(DataComponents.CUSTOM_DATA);
            if (cd != null && "credit".equals(cd.copyTag().getString("ez").orElse(""))) inv.setItem(i, coin.copyWithCount(s.getCount()));
        }
    }

    static String fmt(int n) { return n + (n == 1 ? " coin" : " coins"); }
}

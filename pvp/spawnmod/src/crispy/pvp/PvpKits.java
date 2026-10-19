package crispy.pvp;

import net.minecraft.ChatFormatting;
import net.minecraft.core.component.DataComponents;
import net.minecraft.nbt.CompoundTag;
import net.minecraft.nbt.ListTag;
import net.minecraft.nbt.NbtOps;
import net.minecraft.nbt.StringTag;
import net.minecraft.nbt.Tag;
import net.minecraft.network.chat.Component;
import net.minecraft.resources.Identifier;
import net.minecraft.resources.RegistryOps;
import net.minecraft.server.MinecraftServer;
import net.minecraft.server.level.ServerPlayer;
import net.minecraft.world.entity.player.Inventory;
import net.minecraft.world.item.ItemStack;
import net.minecraft.world.item.component.ItemLore;
import net.minecraft.world.scores.Objective;
import net.minecraft.world.scores.ReadOnlyScoreInfo;

import java.util.ArrayList;
import java.util.List;

/**
 * Admin-made kits, kept in storage pvp:customkits {kits:[{id,name,by,icon,items:[{slot,item}],implants:["sandy",...]}]}.
 * /pvpkit create copies the admin's whole inventory (armor and offhand included) and installed cyberware.
 * The datapack picks one with "pvpkit give <id>" (ids start at 101); kit menus list them via "custom_kits".
 */
public final class PvpKits {
    private PvpKits() {}

    static final Identifier STORE = Identifier.fromNamespaceAndPath("pvp", "customkits");
    static final int FIRST_ID = 101, MAX_KITS = 10;
    // cyberware implant ids (cy.s1..cy.s9 scores) -> keys, as in anarchy/cyberware/build.py
    private static final String[] IMPLANTS = {null, "kiroshi", "subdermal", "titanium", "lungs", "gorilla", "mantis", "tendons",
            "lynx", "grip", "reflex", "biomon", "heart", "sandy", "berserk"};

    static ListTag all(MinecraftServer server) {
        return server.getCommandStorage().get(STORE).getListOrEmpty("kits");
    }

    private static void store(MinecraftServer server, ListTag kits) {
        CompoundTag root = server.getCommandStorage().get(STORE);
        root.put("kits", kits);
        server.getCommandStorage().set(STORE, root);
    }

    private static RegistryOps<Tag> ops(MinecraftServer server) {
        return server.registryAccess().createSerializationContext(NbtOps.INSTANCE);
    }

    /** Saves (or replaces, by name) a kit from the player's inventory and implants. Returns its id, or -1 if full. */
    static int create(MinecraftServer server, ServerPlayer player, String name) {
        RegistryOps<Tag> ops = ops(server);
        ListTag kits = all(server);
        int id = -1, index = -1, maxId = FIRST_ID - 1;
        for (int i = 0; i < kits.size(); i++) {
            CompoundTag k = kits.getCompoundOrEmpty(i);
            maxId = Math.max(maxId, k.getIntOr("id", 0));
            if (k.getStringOr("name", "").equalsIgnoreCase(name)) { id = k.getIntOr("id", 0); index = i; }
        }
        if (index < 0) {
            if (kits.size() >= MAX_KITS) return -1;
            id = maxId + 1;
        }

        Inventory inv = player.getInventory();
        ListTag items = new ListTag();
        ItemStack first = ItemStack.EMPTY;
        for (int slot = 0; slot < inv.getContainerSize(); slot++) {
            ItemStack stack = inv.getItem(slot);
            if (stack.isEmpty()) continue;
            if (first.isEmpty()) first = stack;
            Tag encoded = ItemStack.CODEC.encodeStart(ops, stack).result().orElse(null);
            if (encoded == null) continue;
            CompoundTag e = new CompoundTag();
            e.putInt("slot", slot);
            e.put("item", encoded);
            items.add(e);
        }

        ListTag implants = new ListTag();
        List<Component> implantNames = new ArrayList<>();
        for (int s = 1; s <= 9; s++) {
            Objective obj = server.getScoreboard().getObjective("cy.s" + s);
            if (obj == null) continue;
            ReadOnlyScoreInfo info = server.getScoreboard().getPlayerScoreInfo(player, obj);
            int v = info == null ? 0 : info.value();
            if (v >= 1 && v < IMPLANTS.length) {
                implants.add(StringTag.valueOf(IMPLANTS[v]));
                implantNames.add(Component.literal(IMPLANTS[v]).withStyle(ChatFormatting.AQUA));
            }
        }

        ItemStack icon = (player.getMainHandItem().isEmpty() ? first : player.getMainHandItem()).copyWithCount(1);
        if (icon.isEmpty()) icon = new ItemStack(net.minecraft.world.item.Items.CHEST);
        icon.set(DataComponents.CUSTOM_NAME, Component.literal(name).withStyle(ChatFormatting.GOLD, ChatFormatting.BOLD).withStyle(s -> s.withItalic(false)));
        List<Component> lore = new ArrayList<>();
        lore.add(Component.literal("Custom kit by " + player.getPlainTextName()).withStyle(s -> s.withColor(ChatFormatting.GRAY).withItalic(false)));
        lore.add(Component.literal(items.size() + " items" + (implants.isEmpty() ? "" : ", cyberware: " + String.join(", ",
                implantNames.stream().map(Component::getString).toList()))).withStyle(s -> s.withColor(ChatFormatting.DARK_GRAY).withItalic(false)));
        icon.set(DataComponents.LORE, new ItemLore(lore));
        icon.set(DataComponents.ENCHANTMENT_GLINT_OVERRIDE, true);

        CompoundTag kit = new CompoundTag();
        kit.putInt("id", id);
        kit.putString("name", name);
        kit.putString("by", player.getPlainTextName());
        ItemStack.CODEC.encodeStart(ops, icon).result().ifPresent(t -> kit.put("icon", t));
        kit.put("items", items);
        kit.put("implants", implants);
        if (index >= 0) kits.set(index, kit); else kits.add(kit);
        store(server, kits);
        return id;
    }

    static boolean delete(MinecraftServer server, int id) {
        ListTag kits = all(server);
        for (int i = 0; i < kits.size(); i++) {
            if (kits.getCompoundOrEmpty(i).getIntOr("id", 0) == id) { kits.remove(i); store(server, kits); return true; }
        }
        return false;
    }

    static CompoundTag find(MinecraftServer server, int id) {
        ListTag kits = all(server);
        for (int i = 0; i < kits.size(); i++) {
            CompoundTag k = kits.getCompoundOrEmpty(i);
            if (k.getIntOr("id", 0) == id) return k;
        }
        return null;
    }

    /** Gives the kit to the player (the datapack has already cleared them). Returns false if there's no such kit. */
    static boolean give(MinecraftServer server, ServerPlayer player, int id) {
        CompoundTag kit = find(server, id);
        if (kit == null) return false;
        RegistryOps<Tag> ops = ops(server);
        Inventory inv = player.getInventory();
        ListTag items = kit.getListOrEmpty("items");
        for (int i = 0; i < items.size(); i++) {
            CompoundTag e = items.getCompoundOrEmpty(i);
            int slot = e.getIntOr("slot", -1);
            Tag t = e.get("item");
            if (slot < 0 || slot >= inv.getContainerSize() || t == null) continue;
            ItemStack.CODEC.parse(ops, t).result().ifPresent(stack -> inv.setItem(slot, stack));
        }
        ListTag implants = kit.getListOrEmpty("implants");
        var source = server.createCommandSourceStack().withEntity(player).withPosition(player.position()).withSuppressedOutput();
        for (int i = 0; i < implants.size(); i++) {
            String key = implants.getStringOr(i, "");
            if (key.matches("[a-z]+")) server.getCommands().performPrefixedCommand(source, "function cyber:implant/" + key + "/kit");
        }
        player.sendSystemMessage(Component.literal("Kit: ").withStyle(ChatFormatting.GRAY)
                .append(Component.literal(kit.getStringOr("name", "?")).withStyle(ChatFormatting.GOLD, ChatFormatting.BOLD))
                .append(Component.literal(implants.isEmpty() ? "" : " (cyberware installed)").withStyle(ChatFormatting.GRAY)));
        return true;
    }
}

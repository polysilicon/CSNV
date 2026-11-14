package crispy.anarchy;

import net.fabricmc.fabric.api.entity.event.v1.ServerLivingEntityEvents;
import net.fabricmc.fabric.api.entity.event.v1.ServerPlayerEvents;
import net.fabricmc.fabric.api.event.lifecycle.v1.ServerLifecycleEvents;
import net.minecraft.core.registries.Registries;
import net.minecraft.nbt.CompoundTag;
import net.minecraft.nbt.ListTag;
import net.minecraft.nbt.NbtAccounter;
import net.minecraft.nbt.NbtIo;
import net.minecraft.nbt.NbtOps;
import net.minecraft.nbt.Tag;
import net.minecraft.network.chat.Component;
import net.minecraft.resources.Identifier;
import net.minecraft.resources.ResourceKey;
import net.minecraft.server.MinecraftServer;
import net.minecraft.server.level.ServerPlayer;
import net.minecraft.tags.DamageTypeTags;
import net.minecraft.world.InteractionHand;
import net.minecraft.world.item.ItemStack;
import net.minecraft.world.item.Items;
import net.minecraft.world.level.Level;

import java.nio.file.Files;
import java.nio.file.Path;
import java.util.*;
import java.util.concurrent.ConcurrentHashMap;

/**
 * 1.3.0: PvP stays on in the market (crispy:market), but a player killed there keeps their items and XP, like
 * keep_inventory for that one dimension (the game rule is server-wide, and YAWP has no keep-inventory flag).
 *
 * Just before a market death goes through (ServerLivingEntityEvents.ALLOW_DEATH) the whole inventory (main, armour,
 * off hand) and XP are set aside and cleared, so nothing drops; on respawn (ServerPlayerEvents.COPY_FROM) they go
 * back into the same slots. Not when a totem of undying is about to save them (it would be set aside too). What's set
 * aside is saved to config/crispy_market_keep.dat until handed back, so a player who quits on the death screen and
 * a server restart in between lose nothing. Implants are the cyberware datapack's: its death handler skips the drop
 * in the market (cyber:death/market).
 */
final class MarketKeep {
    private MarketKeep() {}

    static final ResourceKey<Level> MARKET = ResourceKey.create(Registries.DIMENSION, Identifier.fromNamespaceAndPath("crispy", "market"));
    static final Path FILE = Path.of("config", "crispy_market_keep.dat");

    record Kept(List<ItemStack> items, int level, float progress, int total) {}
    static final Map<UUID, Kept> KEPT = new ConcurrentHashMap<>();
    static MinecraftServer server;

    static void init() {
        ServerLifecycleEvents.SERVER_STARTED.register(s -> { server = s; load(); });
        ServerLivingEntityEvents.ALLOW_DEATH.register((entity, source, amount) -> {
            try {
                if (entity instanceof ServerPlayer p && p.level().dimension().equals(MARKET) && !p.isSpectator()
                        && !(holdsTotem(p) && !source.is(DamageTypeTags.BYPASSES_INVULNERABILITY))) stash(p);
            } catch (Exception e) { System.err.println("[crispy-anarchy] market keep (death): " + e); }
            return true;
        });
        ServerPlayerEvents.COPY_FROM.register((oldP, newP, alive) -> {
            if (alive) return;
            try { restore(newP); } catch (Exception e) { System.err.println("[crispy-anarchy] market keep (respawn): " + e); }
        });
    }

    static boolean holdsTotem(ServerPlayer p) {
        return p.getItemInHand(InteractionHand.MAIN_HAND).is(Items.TOTEM_OF_UNDYING) || p.getItemInHand(InteractionHand.OFF_HAND).is(Items.TOTEM_OF_UNDYING);
    }

    static void stash(ServerPlayer p) {
        var inv = p.getInventory();
        List<ItemStack> items = new ArrayList<>();
        boolean any = false;
        for (int i = 0; i < inv.getContainerSize(); i++) { ItemStack s = inv.getItem(i).copy(); items.add(s); any |= !s.isEmpty(); }
        if (!any && p.experienceLevel == 0 && p.experienceProgress == 0) return;
        KEPT.put(p.getUUID(), new Kept(items, p.experienceLevel, p.experienceProgress, p.totalExperience));
        save();   // on disk before anything is cleared
        inv.clearContent();
        p.experienceLevel = 0; p.experienceProgress = 0; p.totalExperience = 0;
    }

    static void restore(ServerPlayer p) {
        Kept k = KEPT.remove(p.getUUID());
        if (k == null) return;
        var inv = p.getInventory();
        for (int i = 0; i < k.items().size() && i < inv.getContainerSize(); i++) {
            ItemStack s = k.items().get(i);
            if (s.isEmpty()) continue;
            if (inv.getItem(i).isEmpty()) inv.setItem(i, s);
            else if (!inv.add(s)) p.drop(s, false);   // never lose anything: a slot already taken (shouldn't happen) -> any free one
        }
        p.experienceLevel = k.level(); p.experienceProgress = k.progress(); p.totalExperience = k.total();
        save();
        p.sendSystemMessage(Component.literal("You died in the market, so you keep your items and XP.").withStyle(s -> s.withColor(0x55FF55)));
    }

    // ---- saved between death and respawn
    static void save() {
        if (server == null) return;
        try {
            var ops = server.registryAccess().createSerializationContext(NbtOps.INSTANCE);
            CompoundTag root = new CompoundTag();
            for (var e : KEPT.entrySet()) {
                CompoundTag c = new CompoundTag();
                ListTag list = new ListTag();
                for (ItemStack s : e.getValue().items()) list.add(ItemStack.OPTIONAL_CODEC.encodeStart(ops, s).getOrThrow());
                c.put("items", list);
                c.putInt("level", e.getValue().level()); c.putFloat("progress", e.getValue().progress()); c.putInt("total", e.getValue().total());
                root.put(e.getKey().toString(), c);
            }
            Files.createDirectories(FILE.getParent());
            Path tmp = FILE.resolveSibling("crispy_market_keep.dat.tmp");
            NbtIo.writeCompressed(root, tmp);
            Files.move(tmp, FILE, java.nio.file.StandardCopyOption.REPLACE_EXISTING, java.nio.file.StandardCopyOption.ATOMIC_MOVE);
        } catch (Exception e) { System.err.println("[crispy-anarchy] market keep: can't save: " + e); }
    }

    static void load() {
        if (!Files.exists(FILE)) return;
        try {
            var ops = server.registryAccess().createSerializationContext(NbtOps.INSTANCE);
            CompoundTag root = NbtIo.readCompressed(FILE, NbtAccounter.unlimitedHeap());
            for (String k : root.keySet()) {
                CompoundTag c = root.getCompoundOrEmpty(k);
                List<ItemStack> items = new ArrayList<>();
                for (Tag t : c.getListOrEmpty("items")) items.add(ItemStack.OPTIONAL_CODEC.parse(ops, t).result().orElse(ItemStack.EMPTY));
                KEPT.put(UUID.fromString(k), new Kept(items, c.getIntOr("level", 0), c.getFloatOr("progress", 0f), c.getIntOr("total", 0)));
            }
            if (!KEPT.isEmpty()) System.out.println("[crispy-anarchy] market keep: " + KEPT.size() + " player(s) still to get their items back");
        } catch (Exception e) { System.err.println("[crispy-anarchy] market keep: can't load: " + e); }
    }
}

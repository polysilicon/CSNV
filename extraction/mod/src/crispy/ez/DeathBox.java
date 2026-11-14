package crispy.ez;

import com.google.gson.Gson;
import com.google.gson.reflect.TypeToken;
import net.fabricmc.fabric.api.entity.event.v1.ServerLivingEntityEvents;
import net.fabricmc.fabric.api.event.lifecycle.v1.ServerTickEvents;
import net.minecraft.core.BlockPos;
import net.minecraft.core.component.DataComponents;
import net.minecraft.network.chat.Component;
import net.minecraft.server.MinecraftServer;
import net.minecraft.server.level.ServerLevel;
import net.minecraft.server.level.ServerPlayer;
import net.minecraft.world.entity.Display;
import net.minecraft.world.entity.Entity;
import net.minecraft.world.entity.item.ItemEntity;
import net.minecraft.world.item.ItemStack;
import net.minecraft.world.level.block.Blocks;
import net.minecraft.world.level.block.entity.BarrelBlockEntity;
import net.minecraft.world.level.block.state.BlockState;
import net.minecraft.world.phys.AABB;

import java.nio.file.Files;
import java.nio.file.Path;
import java.util.*;

/**
 * Death boxes (1.8.28). When a player dies in the zone, what they dropped goes into a barrel where they fell, named
 * "☠ <name>'s gear" with a floating label, instead of lying scattered. Anyone can open it (the owner can run back for
 * it, anyone else can take it). A full inventory fills a second barrel beside the first. After LIFETIME_MIN minutes
 * the barrels go, with whatever is left, like dropped items despawning.
 *
 * The barrels only take empty space (air, grass, snow layers...): the spot where the player fell, or the nearest such
 * spot with solid ground under it within a few blocks. With nowhere to put one, the items stay on the ground as before.
 * A logged-out player's stand-in, when killed, leaves a box the same way (Standin).
 * Boxes are saved (config/crispy_extraction/deathboxes.json), so a restart doesn't strand one; a box whose chunk isn't
 * loaded when it expires is removed the next time it is.
 */
final class DeathBox {
    private DeathBox() {}

    static final int LIFETIME_MIN = 15;
    static final Path FILE = Path.of("config", "crispy_extraction", "deathboxes.json");
    static final class Box { int x, y, z; int x2 = Integer.MIN_VALUE, y2, z2; long until; String owner; String label; }
    static final List<Box> BOXES = new ArrayList<>();
    static boolean loaded;
    static int made;

    static void load() {
        if (loaded) return; loaded = true;
        try { if (Files.exists(FILE)) BOXES.addAll(new Gson().fromJson(Files.readString(FILE), new TypeToken<List<Box>>() {}.getType())); }
        catch (Exception e) { System.err.println("[crispy-extraction] death boxes: " + e); }
    }
    static void save() {
        try { Files.createDirectories(FILE.getParent()); Files.writeString(FILE, new Gson().toJson(BOXES)); }
        catch (Exception e) { System.err.println("[crispy-extraction] can't save death boxes: " + e); }
    }

    static void init() {
        // drops are already in the world when this fires: gather the ones that appeared this tick around the body
        ServerLivingEntityEvents.AFTER_DEATH.register((e, src) -> {
            if (!(e instanceof ServerPlayer p) || !p.level().dimension().equals(Zone.CITY)) return;
            try {
                ServerLevel lvl = (ServerLevel) p.level();
                List<ItemEntity> drops = lvl.getEntitiesOfClass(ItemEntity.class, p.getBoundingBox().inflate(3),
                        ie -> ie.isAlive() && ie.tickCount == 0);
                if (drops.isEmpty()) return;
                List<ItemStack> items = new ArrayList<>();
                for (ItemEntity ie : drops) items.add(ie.getItem().copy());
                if (box(lvl, p.blockPosition(), p.getScoreboardName(), items)) drops.forEach(Entity::discard);
            } catch (Exception ex) { System.err.println("[crispy-extraction] death box failed: " + ex); }
        });
        ServerTickEvents.END_SERVER_TICK.register(server -> {
            if (server.getTickCount() % 100 != 0) return;
            try { expire(server); } catch (Exception ex) { System.err.println("[crispy-extraction] death box tick failed: " + ex); }
        });
    }

    /** Space a barrel may take: air or a plant/snow layer (never a wall, floor, crate or another container). */
    static boolean free(ServerLevel lvl, BlockPos b) {
        BlockState s = lvl.getBlockState(b);
        return (s.isAir() || s.canBeReplaced()) && lvl.getBlockEntity(b) == null && s.getFluidState().isEmpty();
    }
    static boolean spot(ServerLevel lvl, BlockPos b) { return free(lvl, b) && lvl.getBlockState(b.below()).isSolidRender(); }

    /** The spot nearest `at` (same height first, then a little up or down, out to 3 blocks), or null. */
    static BlockPos find(ServerLevel lvl, BlockPos at, BlockPos not) {
        // fell from a height or died mid-jump: drop to the ground below first (up to 24 blocks)
        BlockPos g = at;
        for (int i = 0; i < 24 && free(lvl, g.below()) && g.getY() > lvl.getMinY(); i++) g = g.below();
        for (int r = 0; r <= 3; r++)
            for (int dy : new int[]{0, 1, -1, 2})
                for (int dx = -r; dx <= r; dx++)
                    for (int dz = -r; dz <= r; dz++) {
                        if (Math.max(Math.abs(dx), Math.abs(dz)) != r) continue;
                        BlockPos b = g.offset(dx, dy, dz);
                        if (!b.equals(not) && spot(lvl, b)) return b;
                    }
        return null;
    }

    /** Put items into one or two barrels near `at`. False (items untouched) if there's nowhere to put them. */
    static boolean box(ServerLevel lvl, BlockPos at, String owner, List<ItemStack> items) {
        load();
        List<ItemStack> stacks = new ArrayList<>();
        for (ItemStack s : items) if (!s.isEmpty()) stacks.add(s);
        if (stacks.isEmpty()) return false;
        BlockPos a = find(lvl, at, null);
        if (a == null) return false;
        BlockPos b = stacks.size() > 27 ? find(lvl, a, a) : null;
        if (stacks.size() > 27 && b == null) return false;   // can't fit it all: leave it on the ground rather than lose some
        String label = "☠ " + owner + "'s gear";
        fill(lvl, a, stacks.subList(0, Math.min(27, stacks.size())), label);
        if (b != null) fill(lvl, b, stacks.subList(27, stacks.size()), label);
        if (held(lvl, a) + (b != null ? held(lvl, b) : 0) != stacks.size()) {   // something went wrong: keep the drops instead
            clear(lvl, a); if (b != null) clear(lvl, b);
            System.err.println("[crispy-extraction] death box for " + owner + " didn't hold the gear; left on the ground");
            return false;
        }
        String safe = owner.replaceAll("[^A-Za-z0-9_]", "");
        Plots.run(lvl.getServer(), String.format(java.util.Locale.ROOT,
                "execute in lostcities:lostcity run summon minecraft:text_display %.1f %.2f %.1f {Tags:[\"ez.deathbox\"],billboard:\"center\","
                        + "text:[{text:\"☠ %s's gear\",color:\"red\"},{text:\"\\nGone in %d min\",color:\"gray\"}]}",
                a.getX() + 0.5, a.getY() + 1.3, a.getZ() + 0.5, safe, LIFETIME_MIN));
        Box box = new Box();
        box.x = a.getX(); box.y = a.getY(); box.z = a.getZ();
        if (b != null) { box.x2 = b.getX(); box.y2 = b.getY(); box.z2 = b.getZ(); }
        box.until = System.currentTimeMillis() + LIFETIME_MIN * 60_000L; box.owner = owner; box.label = label;
        BOXES.add(box); save(); made++;
        lvl.playSound(null, a, net.minecraft.sounds.SoundEvents.BARREL_CLOSE, net.minecraft.sounds.SoundSource.BLOCKS, 1f, 0.7f);
        return true;
    }

    static void fill(ServerLevel lvl, BlockPos p, List<ItemStack> stacks, String label) {
        lvl.setBlock(p, Blocks.BARREL.defaultBlockState(), 3);
        if (lvl.getBlockEntity(p) instanceof BarrelBlockEntity be) {
            // name first: applying components also resets the barrel's contents, so filling must come after
            be.applyComponents(be.components(), net.minecraft.core.component.DataComponentPatch.builder()
                    .set(DataComponents.CUSTOM_NAME, Component.literal(label)).build());
            for (int i = 0; i < stacks.size() && i < 27; i++) be.setItem(i, stacks.get(i));
            be.setChanged();
        }
        // never lose gear: if the barrel didn't take it all, the caller is told and the items stay on the ground
    }

    static int held(ServerLevel lvl, BlockPos p) {
        int n = 0;
        if (lvl.getBlockEntity(p) instanceof BarrelBlockEntity be)
            for (int i = 0; i < be.getContainerSize(); i++) if (!be.getItem(i).isEmpty()) n++;
        return n;
    }

    static void expire(MinecraftServer server) {
        load();
        if (BOXES.isEmpty()) return;
        ServerLevel lvl = server.getLevel(Zone.CITY);
        if (lvl == null) return;
        long now = System.currentTimeMillis();
        boolean dirty = false;
        for (Iterator<Box> it = BOXES.iterator(); it.hasNext(); ) {
            Box b = it.next();
            if (now < b.until) continue;
            BlockPos a = new BlockPos(b.x, b.y, b.z);
            if (!lvl.hasChunk(a.getX() >> 4, a.getZ() >> 4)) continue;   // removed when it's next loaded
            clear(lvl, a);
            if (b.x2 != Integer.MIN_VALUE) clear(lvl, new BlockPos(b.x2, b.y2, b.z2));
            for (Entity e : lvl.getEntitiesOfClass(Display.TextDisplay.class, new AABB(a).inflate(2), d -> d.entityTags().contains("ez.deathbox"))) e.discard();
            it.remove(); dirty = true;
        }
        if (dirty) save();
    }
    static void clear(ServerLevel lvl, BlockPos p) {
        if (!lvl.getBlockState(p).is(Blocks.BARREL)) return;   // someone broke it already
        if (lvl.getBlockEntity(p) instanceof BarrelBlockEntity be) be.clearContent();   // contents go with it, no drop
        lvl.setBlock(p, Blocks.AIR.defaultBlockState(), 3);
    }
}

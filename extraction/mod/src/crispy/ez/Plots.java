package crispy.ez;

import com.google.gson.Gson;
import com.google.gson.GsonBuilder;
import com.google.gson.reflect.TypeToken;
import com.mojang.brigadier.arguments.StringArgumentType;
import net.fabricmc.fabric.api.command.v2.CommandRegistrationCallback;
import net.fabricmc.fabric.api.event.player.AttackBlockCallback;
import net.fabricmc.fabric.api.event.player.AttackEntityCallback;
import net.fabricmc.fabric.api.event.player.PlayerBlockBreakEvents;
import net.fabricmc.fabric.api.event.player.UseBlockCallback;
import net.fabricmc.fabric.api.event.player.UseEntityCallback;
import net.fabricmc.fabric.api.event.player.UseItemCallback;
import net.minecraft.ChatFormatting;
import net.minecraft.commands.Commands;
import net.minecraft.core.BlockPos;
import net.minecraft.core.registries.Registries;
import net.minecraft.resources.Identifier;
import net.minecraft.resources.ResourceKey;
import net.minecraft.server.MinecraftServer;
import net.minecraft.server.level.ServerPlayer;
import net.minecraft.world.InteractionResult;
import net.minecraft.world.entity.Entity;
import net.minecraft.world.entity.LivingEntity;
import net.minecraft.world.entity.player.Player;
import net.minecraft.world.item.ItemStack;
import net.minecraft.world.item.Items;
import net.minecraft.world.level.Level;

import java.nio.file.Files;
import java.nio.file.Path;
import java.util.HashMap;
import java.util.List;
import java.util.Map;
import java.util.Set;
import java.util.UUID;

import static crispy.ez.Ui.t;

/**
 * Plots: every player's own patch of ground in the plot district next to camp (dimension ez:camp). Build anything,
 * store gear in chests, upgrade the size with credits. Only the owner can break, place or open things in a plot;
 * visitors can walk around and look. Outside plots, nobody but creative-mode staff can change the camp.
 *
 * Layout: a grid of CELL x CELL cells from (X0, Z0), PER_ROW per row; a plot sits in the middle of its cell, SIZES[level]
 * blocks square, floor at y FLOOR. Data: config/crispy_extraction/plots.json (uuid -> index, level, name).
 */
final class Plots {
    private Plots() {}

    static final ResourceKey<Level> CAMP = ResourceKey.create(Registries.DIMENSION, Identifier.fromNamespaceAndPath("ez", "camp"));
    static final int X0 = 64, Z0 = -192, CELL = 48, PER_ROW = 6, FLOOR = 63, TOP = 100;
    static final int[] SIZES = {16, 24, 32};
    static final int[] COST = {0, 150, 400};
    static final Set<String> BANNED = Set.of("minecraft:lava_bucket", "minecraft:flint_and_steel", "minecraft:fire_charge", "minecraft:tnt",
            "minecraft:end_crystal", "minecraft:ender_pearl", "minecraft:wither_skeleton_skull", "minecraft:respawn_anchor");

    static final class Plot { int index; int level; String name; }
    static final Path FILE = Path.of("config", "crispy_extraction", "plots.json");
    static final Gson GSON = new GsonBuilder().setPrettyPrinting().create();
    static Map<String, Plot> plots = new HashMap<>();
    static boolean loaded;

    static void load() {
        if (loaded) return;
        loaded = true;
        try {
            if (Files.exists(FILE)) plots = GSON.fromJson(Files.readString(FILE), new TypeToken<Map<String, Plot>>() {}.getType());
            if (plots == null) plots = new HashMap<>();
        } catch (Exception e) { System.err.println("[crispy-extraction] can't read " + FILE + ": " + e); }
    }
    static void save() {
        try { Files.createDirectories(FILE.getParent()); Files.writeString(FILE, GSON.toJson(plots)); }
        catch (Exception e) { System.err.println("[crispy-extraction] can't write " + FILE + ": " + e); }
    }

    static int cx(int i) { return X0 + (i % PER_ROW) * CELL + CELL / 2; }
    static int cz(int i) { return Z0 + (i / PER_ROW) * CELL + CELL / 2; }
    static int half(Plot p) { return SIZES[p.level] / 2; }
    static boolean inside(Plot p, BlockPos b) {
        int h = half(p), x = cx(p.index), z = cz(p.index);
        return b.getX() >= x - h && b.getX() < x + h && b.getZ() >= z - h && b.getZ() < z + h && b.getY() >= FLOOR && b.getY() <= TOP;
    }
    static Plot of(Player pl) { load(); return plots.get(pl.getUUID().toString()); }

    static void run(MinecraftServer s, String cmd) {
        s.getCommands().performPrefixedCommand(s.createCommandSourceStack().withSuppressedOutput(), cmd);
    }
    static String inCamp(String cmd) { return "execute in ez:camp run " + cmd; }

    /** Lay out (or grow) a plot: path around it, grass floor (only where the path was, so builds stay), a border. */
    static void lay(MinecraftServer s, Plot p, boolean fresh) {
        int x = cx(p.index), z = cz(p.index), h = half(p), c = CELL / 2;
        if (fresh) {
            run(s, inCamp(String.format("fill %d %d %d %d %d %d minecraft:coarse_dirt", x - c, FLOOR, z - c, x + c - 1, FLOOR, z + c - 1)));
            run(s, inCamp(String.format("fill %d %d %d %d %d %d minecraft:dirt_path", x - c, FLOOR, z + c - 3, x + c - 1, FLOOR, z + c - 1)));
        }
        run(s, inCamp(String.format("fill %d %d %d %d %d %d minecraft:grass_block replace minecraft:coarse_dirt", x - h, FLOOR, z - h, x + h - 1, FLOOR, z + h - 1)));
        run(s, inCamp(String.format("fill %d %d %d %d %d %d minecraft:grass_block replace minecraft:tuff_bricks", x - h, FLOOR, z - h, x + h - 1, FLOOR, z + h - 1)));
        for (int[] e : new int[][]{{x - h - 1, z - h - 1, x + h, z - h - 1}, {x - h - 1, z + h, x + h, z + h}, {x - h - 1, z - h - 1, x - h - 1, z + h}, {x + h, z - h - 1, x + h, z + h}})
            run(s, inCamp(String.format("fill %d %d %d %d %d %d minecraft:tuff_bricks replace minecraft:coarse_dirt", e[0], FLOOR, e[1], e[2], FLOOR, e[3])));
        if (fresh) run(s, inCamp(String.format("setblock %d %d %d minecraft:chest[facing=south]", x - h + 1, FLOOR + 1, z - h + 1)));
        run(s, inCamp(String.format("kill @e[type=minecraft:text_display,tag=ez.plotname,x=%d,y=%d,z=%d,distance=..3]", x, FLOOR + 3, z + h + 1)));
        run(s, inCamp(String.format("summon minecraft:text_display %d %d %d {Tags:[\"ez.plotname\"],billboard:\"center\",text:{text:\"%s's plot\",color:\"gold\",bold:true}}",
                x, FLOOR + 3, z + h + 1, p.name.replace("\"", ""))));
    }

    static Plot claim(ServerPlayer pl) {
        Plot p = of(pl);
        if (p != null) { p.name = pl.getGameProfile().name(); return p; }
        int idx = 0;
        while (true) { final int i = idx; if (plots.values().stream().noneMatch(q -> q.index == i)) break; idx++; }
        p = new Plot(); p.index = idx; p.level = 0; p.name = pl.getGameProfile().name();
        plots.put(pl.getUUID().toString(), p);
        save();
        lay(pl.level().getServer(), p, true);
        return p;
    }

    static boolean raiding(ServerPlayer pl) { return pl.entityTags().contains("ez.raid"); }
    static void tp(ServerPlayer pl, Plot p) {
        run(pl.level().getServer(), inCamp(String.format("tp %s %d %d %d 180 0", pl.getGameProfile().name(), cx(p.index), FLOOR + 1, cz(p.index) + half(p) + 1)));
    }

    static void menu(ServerPlayer pl) {
        Ui.open(pl, t("Your Plot", ChatFormatting.DARK_GRAY), 3, m -> {
            Plot p = of(pl);
            m.put(4, Shops.balanceIcon(pl), null);
            if (p == null) {
                m.put(13, Ui.item(Items.GRASS_BLOCK, t("Claim your plot (free)", ChatFormatting.GREEN, ChatFormatting.BOLD), List.of(
                        t("Your own " + SIZES[0] + " x " + SIZES[0] + " patch to build on and store gear.", ChatFormatting.GRAY),
                        t("Only you can build or open chests there.", ChatFormatting.GRAY)), true),
                        (q, c) -> { Plot n = claim(q); q.closeContainer(); tp(q, n); Shops.ok(q, "Welcome to your plot! Use /plot to come back, /camp to go to camp."); });
                return;
            }
            m.put(11, Ui.item(Items.ENDER_PEARL, t("Go to my plot", ChatFormatting.AQUA), List.of(t("Or type /plot", ChatFormatting.GRAY)), false),
                    (q, c) -> { q.closeContainer(); tp(q, p); });
            if (p.level + 1 < SIZES.length) {
                int next = p.level + 1;
                m.put(13, Ui.item(Items.GOLDEN_SHOVEL, t("Upgrade to " + SIZES[next] + " x " + SIZES[next], ChatFormatting.GOLD, ChatFormatting.BOLD), List.of(
                        t("Now " + SIZES[p.level] + " x " + SIZES[p.level], ChatFormatting.GRAY), t("Cost: " + COST[next] + " credits", ChatFormatting.GOLD)), true),
                        (q, c) -> {
                            if (!Shops.pay(q, COST[next])) { Shops.no(q, "You need " + COST[next] + " credits (carry them on you)."); return; }
                            p.level = next; save(); lay(q.level().getServer(), p, false);
                            Shops.ok(q, "Your plot is now " + SIZES[next] + " x " + SIZES[next] + ".");
                        });
            } else m.put(13, Ui.item(Items.NETHERITE_SHOVEL, t("Max size: " + SIZES[p.level] + " x " + SIZES[p.level], ChatFormatting.GOLD), List.of(), true), null);
            m.put(15, Ui.item(Items.CHEST, t("Storage", ChatFormatting.YELLOW), List.of(
                    t("Place chests and barrels on your plot:", ChatFormatting.GRAY), t("only you can open them.", ChatFormatting.GRAY),
                    t("Buy more from the Builder.", ChatFormatting.GRAY)), false), null);
        });
    }

    // ---------------------------------------------------------------- protection
    static boolean campAllowed(Player pl, Level world, BlockPos pos) {
        if (!world.dimension().equals(CAMP)) return true;
        if (pl.isCreative()) return true;
        Plot p = of(pl);
        return p != null && inside(p, pos);
    }

    static void init() {
        PlayerBlockBreakEvents.BEFORE.register((world, pl, pos, state, be) -> campAllowed(pl, world, pos));
        AttackBlockCallback.EVENT.register((pl, world, hand, pos, dir) -> campAllowed(pl, world, pos) ? InteractionResult.PASS : InteractionResult.FAIL);
        UseBlockCallback.EVENT.register((pl, world, hand, hit) -> {
            if (!world.dimension().equals(CAMP) || pl.isCreative()) return InteractionResult.PASS;
            ItemStack held = pl.getItemInHand(hand);
            if (BANNED.contains(net.minecraft.core.registries.BuiltInRegistries.ITEM.getKey(held.getItem()).toString())) return InteractionResult.FAIL;
            BlockPos at = hit.getBlockPos(), place = at.relative(hit.getDirection());
            return campAllowed(pl, world, at) && campAllowed(pl, world, place) ? InteractionResult.PASS : InteractionResult.FAIL;
        });
        UseItemCallback.EVENT.register((pl, world, hand) -> {
            if (!world.dimension().equals(CAMP) || pl.isCreative()) return InteractionResult.PASS;
            String id = net.minecraft.core.registries.BuiltInRegistries.ITEM.getKey(pl.getItemInHand(hand).getItem()).toString();
            return BANNED.contains(id) ? InteractionResult.FAIL : InteractionResult.PASS;
        });
        AttackEntityCallback.EVENT.register((pl, world, hand, e, hit) -> decoAllowed(pl, world, e) ? InteractionResult.PASS : InteractionResult.FAIL);
        UseEntityCallback.EVENT.register((pl, world, hand, e, hit) -> {
            for (String tag : e.entityTags()) if (tag.startsWith("ez.shop.")) return InteractionResult.PASS;   // traders: Shops handles them
            return decoAllowed(pl, world, e) ? InteractionResult.PASS : InteractionResult.FAIL;
        });

        CommandRegistrationCallback.EVENT.register((d, ctx, env) -> {
            d.register(Commands.literal("plot")
                    .executes(c -> { ServerPlayer pl = c.getSource().getPlayerOrException();
                        if (raiding(pl)) { Shops.no(pl, "Not during a raid: extract first."); return 0; }
                        tp(pl, claim(pl)); return 1; })
                    .then(Commands.literal("menu").executes(c -> { menu(c.getSource().getPlayerOrException()); return 1; }))
                    .then(Commands.literal("visit").then(Commands.argument("player", StringArgumentType.word()).executes(c -> {
                        ServerPlayer pl = c.getSource().getPlayerOrException();
                        if (raiding(pl)) { Shops.no(pl, "Not during a raid: extract first."); return 0; }
                        load();
                        String who = StringArgumentType.getString(c, "player");
                        for (Plot p : plots.values()) if (p.name != null && p.name.equalsIgnoreCase(who)) { tp(pl, p); return 1; }
                        Shops.no(pl, who + " doesn't have a plot yet."); return 0; }))));
            d.register(Commands.literal("camp").executes(c -> { ServerPlayer pl = c.getSource().getPlayerOrException();
                if (raiding(pl)) { Shops.no(pl, "Not during a raid: extract first."); return 0; }
                run(pl.level().getServer(), inCamp("tp " + pl.getGameProfile().name() + " 0.5 64 6.5 180 0")); return 1; }));
        });
    }

    /** Item frames, armour stands, paintings and the like in camp: only the plot owner (or creative staff). */
    static boolean decoAllowed(Player pl, Level world, Entity e) {
        if (!world.dimension().equals(CAMP) || pl.isCreative() || e instanceof Player) return true;
        if (e instanceof LivingEntity && !(e instanceof net.minecraft.world.entity.decoration.ArmorStand)) return true;
        return campAllowed(pl, world, e.blockPosition());
    }
}

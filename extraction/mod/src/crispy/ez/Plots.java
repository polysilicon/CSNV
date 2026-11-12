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
import net.minecraft.server.level.ServerLevel;
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

    static final class Plot { int index; int level; String name; java.util.List<String> perks = new java.util.ArrayList<>(); }
    /** Stash upgrades with an effect (1.1.0): key, name, icon block placed on the plot, cost, what it does. */
    record Perk(String key, String name, net.minecraft.world.item.Item icon, String block, int cost, List<String> lines) {}
    static final List<Perk> PERKS = List.of(
            new Perk("workbench", "Gun Workbench", Items.SMITHING_TABLE, "minecraft:smithing_table", 300,
                    List.of("Mod your guns: extended magazine (+50%)", "and quick reload (35% faster).", "Right-click it on your plot, or /workbench in camp.")),
            new Perk("med", "Medical Station", Items.BREWING_STAND, "minecraft:brewing_stand", 200,
                    List.of("Bandages and medkits cost 40% less", "at every trader.")),
            new Perk("radio", "Field Radio", Items.JUKEBOX, "minecraft:jukebox", 250,
                    List.of("Each raid, the first zone event", "(supply drop, crash, hot extract)", "comes with its exact location.")));
    static boolean hasPerk(Player pl, String key) { Plot p = of(pl); return p != null && p.perks != null && p.perks.contains(key); }
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
        ServerLevel camp = s.getLevel(CAMP);
        if (camp != null)   // commands need the cell's chunks loaded
            for (int qx = (x - c) >> 4; qx <= (x + c) >> 4; qx++) for (int qz = (z - c) >> 4; qz <= (z + c) >> 4; qz++) camp.getChunk(qx, qz);
        if (fresh) {
            run(s, inCamp(String.format("fill %d %d %d %d %d %d minecraft:coarse_dirt", x - c, FLOOR, z - c, x + c - 1, FLOOR, z + c - 1)));
            run(s, inCamp(String.format("fill %d %d %d %d %d %d minecraft:dirt_path", x - c, FLOOR, z + c - 3, x + c - 1, FLOOR, z + c - 1)));
        }
        run(s, inCamp(String.format("fill %d %d %d %d %d %d minecraft:grass_block replace minecraft:coarse_dirt", x - h, FLOOR, z - h, x + h - 1, FLOOR, z + h - 1)));
        run(s, inCamp(String.format("fill %d %d %d %d %d %d minecraft:grass_block replace minecraft:tuff_bricks", x - h, FLOOR, z - h, x + h - 1, FLOOR, z + h - 1)));
        for (int[] e : new int[][]{{x - h - 1, z - h - 1, x + h, z - h - 1}, {x - h - 1, z + h, x + h, z + h}, {x - h - 1, z - h - 1, x - h - 1, z + h}, {x + h, z - h - 1, x + h, z + h}})
            run(s, inCamp(String.format("fill %d %d %d %d %d %d minecraft:tuff_bricks replace minecraft:coarse_dirt", e[0], FLOOR, e[1], e[2], FLOOR, e[3])));
        if (fresh) run(s, inCamp(String.format("setblock %d %d %d %s", x - h + 1, FLOOR + 1, z - h + 1, Storage.CRATE_BLOCK)));
        if (fresh) surround(s, p);
        run(s, inCamp(String.format("kill @e[type=minecraft:text_display,tag=ez.plotname,x=%d,y=%d,z=%d,distance=..3]", x, FLOOR + 3, z + h + 1)));
        run(s, inCamp(String.format("summon minecraft:text_display %d %d %d {Tags:[\"ez.plotname\"],billboard:\"center\",text:{text:\"%s's plot\",color:\"gold\",bold:true}}",
                x, FLOOR + 3, z + h + 1, p.name.replace("\"", ""))));
    }

    /** 1.2.0: the cell's island: 8 layers of ground down to bedrock (only into empty space, so nothing built is touched),
     *  an invisible wall on the cell edge so nobody walks off, and a ring of trees around the plot with grass and ferns. */
    static void surround(MinecraftServer s, Plot p) {
        int x = cx(p.index), z = cz(p.index), c = CELL / 2, x0 = x - c, x1 = x + c - 1, z0 = z - c, z1 = z + c - 1;
        for (int y = FLOOR - 1; y >= FLOOR - 4; y--) run(s, inCamp(String.format("fill %d %d %d %d %d %d minecraft:dirt keep", x0, y, z0, x1, y, z1)));
        for (int y = FLOOR - 5; y >= FLOOR - 6; y--) run(s, inCamp(String.format("fill %d %d %d %d %d %d minecraft:stone keep", x0, y, z0, x1, y, z1)));
        run(s, inCamp(String.format("fill %d %d %d %d %d %d minecraft:bedrock", x0, FLOOR - 7, z0, x1, FLOOR - 7, z1)));
        for (int[] e : new int[][]{{x0, z0, x1, z0}, {x0, z1, x1, z1}, {x0, z0, x0, z1}, {x1, z0, x1, z1}})
            run(s, inCamp(String.format("fill %d %d %d %d %d %d minecraft:barrier keep", e[0], FLOOR + 1, e[1], e[2], FLOOR + 8, e[3])));
        // the margin outside the biggest plot size becomes grass with trees
        int big = SIZES[SIZES.length - 1] / 2;
        run(s, inCamp(String.format("fill %d %d %d %d %d %d minecraft:grass_block replace minecraft:coarse_dirt", x0 + 1, FLOOR, z0 + 1, x1 - 1, FLOOR, z1 - 1)));
        java.util.Random r = new java.util.Random(p.index * 7919L);
        String[] trees = {"minecraft:oak", "minecraft:birch", "minecraft:spruce", "minecraft:fancy_oak", "minecraft:pine", "minecraft:oak"};
        int planted = 0;
        for (int tries = 0; tries < 200 && planted < 14; tries++) {
            int tx = x0 + 2 + r.nextInt(CELL - 4), tz = z0 + 2 + r.nextInt(CELL - 6);
            if (Math.abs(tx - x) < big + 2 && Math.abs(tz - z) < big + 2) continue;   // keep clear of the plot at its largest
            run(s, inCamp(String.format("setblock %d %d %d minecraft:grass_block", tx, FLOOR, tz)));
            run(s, inCamp(String.format("place feature %s %d %d %d", trees[r.nextInt(trees.length)], tx, FLOOR + 1, tz)));
            planted++;
        }
        for (int i = 0; i < 60; i++) {
            int gx = x0 + 1 + r.nextInt(CELL - 2), gz = z0 + 1 + r.nextInt(CELL - 4);
            if (Math.abs(gx - x) < big + 1 && Math.abs(gz - z) < big + 1) continue;
            run(s, inCamp(String.format("setblock %d %d %d %s keep", gx, FLOOR + 1, gz, r.nextBoolean() ? "minecraft:short_grass" : "minecraft:fern")));
        }
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
        Ui.open(pl, t("Your Plot", ChatFormatting.DARK_GRAY), 4, m -> {
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
                        t("Now " + SIZES[p.level] + " x " + SIZES[p.level], ChatFormatting.GRAY), t("Cost: " + Coins.fmt(COST[next]), ChatFormatting.GOLD)), true),
                        (q, c) -> {
                            if (!Shops.pay(q, COST[next])) { Shops.no(q, "You need " + Coins.fmt(COST[next]) + " (carry them on you)."); return; }
                            p.level = next; save(); lay(q.level().getServer(), p, false);
                            Shops.ok(q, "Your plot is now " + SIZES[next] + " x " + SIZES[next] + ".");
                        });
            } else m.put(13, Ui.item(Items.NETHERITE_SHOVEL, t("Max size: " + SIZES[p.level] + " x " + SIZES[p.level], ChatFormatting.GOLD), List.of(), true), null);
            int used = Storage.count(pl.level().getServer(), p), max = Storage.limit(p);
            m.put(15, Ui.item(Items.BARREL, t("Storage: " + used + " / " + max + " Stash Crates", ChatFormatting.YELLOW), List.of(
                    t("Storage on plots is Stash Crates only", ChatFormatting.GRAY), t("(Builder, " + Coins.fmt(25) + "). Only you can open them.", ChatFormatting.GRAY),
                    t("Size 16: 4 crates · 24: 7 · 32: 10.", ChatFormatting.GRAY)), false), null);
            if (p.perks == null) p.perks = new java.util.ArrayList<>();
            int[] slots = {29, 31, 33};
            for (int i = 0; i < PERKS.size(); i++) {
                Perk k = PERKS.get(i);
                boolean own = p.perks.contains(k.key());
                List<net.minecraft.network.chat.Component> lore = new java.util.ArrayList<>();
                for (String l : k.lines()) lore.add(t(l, ChatFormatting.GRAY));
                lore.add(t(own ? "Installed on your plot" : "Cost: " + Coins.fmt(k.cost()), own ? ChatFormatting.GREEN : ChatFormatting.GOLD));
                m.put(slots[i], Ui.item(k.icon(), t((own ? "✔ " : "") + k.name(), own ? ChatFormatting.GREEN : ChatFormatting.YELLOW, ChatFormatting.BOLD), lore, own),
                        own ? (k.key().equals("workbench") ? (q, c) -> Workbench.open(q) : null) : (q, c) -> {
                            if (!Shops.pay(q, k.cost())) { Shops.no(q, "You need " + Coins.fmt(k.cost()) + " (carry them on you)."); return; }
                            p.perks.add(k.key()); save();
                            placePerk(q.level().getServer(), p, k);
                            Shops.ok(q, k.name() + " installed on your plot.");
                        });
            }
        });
    }

    /** The upgrade's block, in a row along the plot's north edge next to the starter chest (decor and a click target). */
    static void placePerk(MinecraftServer s, Plot p, Perk k) {
        int x = cx(p.index) - half(p) + 3 + 2 * PERKS.indexOf(k), z = cz(p.index) - half(p) + 1;
        run(s, inCamp(String.format("setblock %d %d %d %s", x, FLOOR + 1, z, k.block())));
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
            d.register(Commands.literal("ezadmin").requires(Commands.hasPermission(Commands.LEVEL_GAMEMASTERS))
                    .then(Commands.literal("plotdecor").executes(c -> {   // 1.2.0: ground, edge wall and trees for plots made before
                        load(); MinecraftServer srv = c.getSource().getServer();
                        for (Plot p : plots.values()) { lay(srv, p, false); surround(srv, p); }
                        c.getSource().sendSuccess(() -> net.minecraft.network.chat.Component.literal("Decorated " + plots.size() + " plots."), true); return 1; })));
            d.register(Commands.literal("camp").executes(c -> { ServerPlayer pl = c.getSource().getPlayerOrException();
                if (raiding(pl)) { Shops.no(pl, "Not during a raid: extract first."); return 0; }
                run(pl.level().getServer(), inCamp("tp " + pl.getGameProfile().name() + " 0.5 64 6.5 180 0")); return 1; }));
        });
    }

    /** Item frames, armour stands, paintings and the like in camp: only the plot owner (or creative staff). */
    static boolean decoAllowed(Player pl, Level world, Entity e) {
        if (!world.dimension().equals(CAMP) || pl.isCreative() || e instanceof Player) return true;
        // the camp's own click boxes (deploy pad) and NPCs/decor are always usable
        if (e instanceof net.minecraft.world.entity.Interaction) return true;
        for (String tag : e.entityTags()) if (tag.startsWith("ez.")) return true;
        if (e instanceof LivingEntity && !(e instanceof net.minecraft.world.entity.decoration.ArmorStand)) return true;
        return campAllowed(pl, world, e.blockPosition());
    }
}

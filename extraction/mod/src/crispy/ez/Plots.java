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
    // 1.3.0: plots are underground bunkers deep under camp (y 20): FLOOR is the floor layer, TOP the highest buildable block
    static final int X0 = 64, Z0 = -192, CELL = 48, PER_ROW = 6, FLOOR = 20, TOP = FLOOR + 6;
    static final String FLOOR_BLOCK = "minecraft:polished_tuff", OLD_SHELL = "minecraft:reinforced_deepslate";
    static final String BAND = "minecraft:tuff_bricks", AISLE = "minecraft:smooth_stone", BAY = "minecraft:polished_andesite";   // 1.6.0 palette (design/palette.json)
    /** 1.4.0: wall finishes the Bunker Manager offers (block, name, icon); the first is the default. */
    record Finish(String block, String name, net.minecraft.world.item.Item icon) {}
    static final List<Finish> FINISHES = List.of(
            new Finish("minecraft:white_concrete", "White Concrete", Items.QUARTZ), new Finish("minecraft:light_gray_concrete", "Light Gray Concrete", Items.CLAY_BALL),
            new Finish("minecraft:gray_concrete", "Gray Concrete", Items.FLINT), new Finish("minecraft:smooth_stone", "Smooth Stone", Items.SMOOTH_STONE),
            new Finish("minecraft:stone_bricks", "Stone Bricks", Items.STONE_BRICKS), new Finish("minecraft:tuff_bricks", "Tuff Bricks", Items.TUFF_BRICKS),
            new Finish("minecraft:polished_deepslate", "Polished Deepslate", Items.POLISHED_DEEPSLATE), new Finish("minecraft:spruce_planks", "Spruce Panelling", Items.SPRUCE_PLANKS));
    static final int FINISH_COST = 50;
    static String shell(Plot p) { return p.style == null ? FINISHES.get(0).block() : p.style; }
    // the camp's bunker entrance (datapack camp: an interaction tagged ez.bunkerdoor at the bottom of its steps);
    // coming up from a bunker puts you outside it
    static final double[] CAMP_EXIT = {12.5, 64, 10.5, 180};   // outside the camp's bunker blockhouse, facing camp
    static final double[] CAMP_SPAWN = {0.5, 64, 6.5, 180};
    static final int DOOR_X = 12, DOOR_Z = 16;                  // the blockhouse's iron door (lower half at y 62)

    /** Move a player within camp (bunkers are in the camp dimension too): a direct teleport, no command. */
    static void move(ServerPlayer pl, double x, double y, double z, float yaw) {
        ServerLevel camp = pl.level().getServer().getLevel(CAMP);
        if (camp != null) pl.teleportTo(camp, x, y, z, java.util.Set.of(), yaw, 0f, true);
    }
    /** The exit hatch at the top of every bunker's stairwell (iron trapdoor at FLOOR + 9 in the camp dimension). */
    static boolean isHatch(Level w, BlockPos pos, net.minecraft.world.level.block.state.BlockState st) {
        return w.dimension().equals(CAMP) && pos.getY() == FLOOR + 9 && st.is(net.minecraft.world.level.block.Blocks.IRON_TRAPDOOR);
    }
    /** The camp blockhouse's heavy door. */
    static boolean isCampDoor(Level w, BlockPos pos, net.minecraft.world.level.block.state.BlockState st) {
        return w.dimension().equals(CAMP) && pos.getX() == DOOR_X && pos.getZ() == DOOR_Z && (pos.getY() == 62 || pos.getY() == 63)
                && st.is(net.minecraft.world.level.block.Blocks.IRON_DOOR);
    }
    static void exitToCamp(ServerPlayer sp) {
        move(sp, CAMP_EXIT[0], CAMP_EXIT[1], CAMP_EXIT[2], (float) CAMP_EXIT[3]);
        Ui.sound(sp, net.minecraft.sounds.SoundEvents.IRON_TRAPDOOR_OPEN, 1f, 0.8f);
    }
    static void enterBunker(ServerPlayer sp) {
        Plot p = of(sp);
        if (p == null) { Trace.d(sp, "no bunker yet: claim menu"); menu(sp); return; }
        tp(sp, p);
        Flow.mark(sp, "bunker");
        Ui.sound(sp, net.minecraft.sounds.SoundEvents.IRON_DOOR_CLOSE, 1f, 0.8f);
    }
    static final int OLD_FLOOR = 63;   // where plots were before 1.3.0
    static final int[] SIZES = {16, 24, 32};
    static final int[] COST = {0, 150, 400};
    static final Set<String> BANNED = Set.of("minecraft:lava_bucket", "minecraft:flint_and_steel", "minecraft:fire_charge", "minecraft:tnt",
            "minecraft:end_crystal", "minecraft:ender_pearl", "minecraft:wither_skeleton_skull", "minecraft:respawn_anchor");

    static final class Plot { int index; int level; String name; java.util.List<String> perks = new java.util.ArrayList<>(); String style; }
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
        var src = s.createCommandSourceStack().withSuppressedOutput();
        // 1.6.0: a command that doesn't parse (a bad block ID, a typo) used to fail in silence; now it's kept for the self-test
        var parse = s.getCommands().getDispatcher().parse(cmd, src);
        if (parse.getReader().canRead() || !parse.getExceptions().isEmpty()) {
            String why = parse.getExceptions().isEmpty() ? "unparsed: " + parse.getReader().getRemaining() : parse.getExceptions().values().iterator().next().getMessage();
            if (BAD_COMMANDS.size() < 50) BAD_COMMANDS.add(cmd + "  <- " + why);
            System.err.println("[crispy-extraction] command didn't parse: " + cmd + " (" + why + ")");
        }
        var m = BLOCK_ID.matcher(cmd);
        while (m.find()) USED_IDS.add(m.group(1));
        s.getCommands().performPrefixedCommand(src, cmd);
    }
    static final java.util.List<String> BAD_COMMANDS = new java.util.ArrayList<>();
    static final java.util.Set<String> USED_IDS = new java.util.TreeSet<>();
    static final java.util.regex.Pattern BLOCK_ID = java.util.regex.Pattern.compile("(minecraft:[a-z0-9_]+)");
    static String inCamp(String cmd) { return "execute in ez:camp run " + cmd; }

    /** Load the chunks a box of commands is about to touch. */
    static void loadArea(MinecraftServer s, int x0, int z0, int x1, int z1) {
        ServerLevel camp = s.getLevel(CAMP);
        if (camp != null) for (int qx = x0 >> 4; qx <= x1 >> 4; qx++) for (int qz = z0 >> 4; qz <= z1 >> 4; qz++) camp.getChunk(qx, qz);
    }

    /**
     * Build (or grow) a plot's bunker: a sealed room SIZE x SIZE inside, 6 high. The shell (walls, ceiling) is
     * reinforced deepslate, which can't be mined; under the breakable tuff floor is bedrock. Ceiling lights, hazard
     * stripes along the base of the walls, vent grates, and a blast door on the north wall. Growing it moves the walls
     * out: the old shell inside the bigger room is cleared, nothing else is touched.
     */
    static void lay(MinecraftServer s, Plot p, boolean fresh) { lay(s, p, fresh, -1); }
    static void lay(MinecraftServer s, Plot p, boolean fresh, int oldLevel) {
        int x = cx(p.index), z = cz(p.index), h = half(p);
        int x0 = x - h, x1 = x + h - 1, z0 = z - h, z1 = z + h - 1;
        loadArea(s, x0 - 2, z0 - 2, x1 + 2, z1 + 2);
        String f = "fill %d %d %d %d %d %d %s";
        run(s, inCamp(String.format(f, x0 - 1, FLOOR - 1, z0 - 1, x1 + 1, FLOOR - 1, z1 + 1, "minecraft:bedrock")));
        run(s, inCamp(String.format(f, x0, FLOOR, z0, x1, FLOOR, z1, FLOOR_BLOCK + " keep")));
        String shell = shell(p);
        run(s, inCamp(String.format(f, x0 - 1, FLOOR + 7, z0 - 1, x1 + 1, FLOOR + 7, z1 + 1, shell + " keep")));
        for (int[] e : new int[][]{{x0 - 1, z0 - 1, x1 + 1, z0 - 1}, {x0 - 1, z1 + 1, x1 + 1, z1 + 1}, {x0 - 1, z0 - 1, x0 - 1, z1 + 1}, {x1 + 1, z0 - 1, x1 + 1, z1 + 1}})
            run(s, inCamp(String.format(f, e[0], FLOOR, e[1], e[2], FLOOR + 7, e[3], shell)));
        if (oldLevel >= 0 && oldLevel < p.level) {   // grown: the old walls are inside the room now
            int oh = SIZES[oldLevel] / 2, ox0 = x - oh - 1, ox1 = x + oh, oz0 = z - oh - 1, oz1 = z + oh;
            for (int[] e : new int[][]{{ox0, oz0, ox1, oz0}, {ox0, oz1, ox1, oz1}, {ox0, oz0, ox0, oz1}, {ox1, oz0, ox1, oz1}}) {
                run(s, inCamp(String.format(f, e[0], FLOOR + 1, e[1], e[2], FLOOR + 6, e[3], "minecraft:air")));
                run(s, inCamp(String.format(f, e[0], FLOOR, e[1], e[2], FLOOR, e[3], FLOOR_BLOCK)));
            }
            // the old stairwell, now partly inside the bigger room: clear what's inside, drop its exit
            run(s, inCamp(String.format(f, x - 2, FLOOR + 1, z0, x + 2, FLOOR + 6, oz0 - 1, "minecraft:air")));
            run(s, inCamp(String.format(f, x - 2, FLOOR, z0, x + 2, FLOOR, oz0 - 1, FLOOR_BLOCK)));
            run(s, inCamp(String.format("kill @e[tag=ez.bunkerexit,x=%d,y=%d,z=%d,distance=..%d]", x, FLOOR + 6, z, h + 12)));
        }
        for (int lx = x0 + 2; lx <= x1 - 1; lx += 6)   // ceiling lights, into the shell
            for (int lz = z0 + 2; lz <= z1 - 1; lz += 6) run(s, inCamp(String.format("setblock %d %d %d minecraft:ochre_froglight", lx, FLOOR + 7, lz)));   // 1.6.0 warm, like the reference bunkers
        // 1.6.3 no hanging lights: flush ceiling lights on a 3-block grid (and one at each far edge), so no floor cell is
        // more than 1 block across from one: light 15 - 6 (down) - 2 = 7 at worst. The 1.6.1 pendants come out, matching
        // only their own blocks so nothing a player built moves.
        java.util.List<Integer> gx = new java.util.ArrayList<>(), gz = new java.util.ArrayList<>();
        for (int k = x0 + 1; k <= x1 - 1; k += 3) gx.add(k);
        if (gx.get(gx.size() - 1) < x1 - 1) gx.add(x1 - 1);
        for (int k = z0 + 1; k <= z1 - 1; k += 3) gz.add(k);
        if (gz.get(gz.size() - 1) < z1 - 1) gz.add(z1 - 1);
        for (int lx : gx) for (int lz : gz) run(s, inCamp(String.format("setblock %d %d %d minecraft:ochre_froglight", lx, FLOOR + 7, lz)));
        for (int lx = x0 + 1; lx <= x1; lx += 4)
            for (int lz = z0 + 1; lz <= z1; lz += 4) {
                run(s, inCamp(String.format("fill %d %d %d %d %d %d minecraft:air replace minecraft:iron_chain", lx, FLOOR + 5, lz, lx, FLOOR + 6, lz)));
                run(s, inCamp(String.format("fill %d %d %d %d %d %d minecraft:air replace minecraft:ochre_froglight", lx, FLOOR + 4, lz, lx, FLOOR + 4, lz)));
            }
        // 1.6.0 a grey skirting band (two blocks) round the room, vent grates high up; hazard marks only at the door
        for (int[] e : new int[][]{{x0 - 1, z0 - 1, x1 + 1, z0 - 1}, {x0 - 1, z1 + 1, x1 + 1, z1 + 1}, {x0 - 1, z0 - 1, x0 - 1, z1 + 1}, {x1 + 1, z0 - 1, x1 + 1, z1 + 1}})
            run(s, inCamp(String.format(f, e[0], FLOOR + 1, e[1], e[2], FLOOR + 2, e[3], BAND)));
        for (int k = x0 - 1; k <= x1 + 1; k++)
            if (Math.floorMod(k, 7) == 0) {
                run(s, inCamp(String.format("setblock %d %d %d minecraft:iron_bars", k, FLOOR + 5, z0 - 1)));
                run(s, inCamp(String.format("setblock %d %d %d minecraft:iron_bars", k, FLOOR + 5, z1 + 1)));
            }
        for (int k = z0 - 1; k <= z1 + 1; k++)
            if (Math.floorMod(k, 7) == 0) {
                run(s, inCamp(String.format("setblock %d %d %d minecraft:iron_bars", x0 - 1, FLOOR + 5, k)));
                run(s, inCamp(String.format("setblock %d %d %d minecraft:iron_bars", x1 + 1, FLOOR + 5, k)));
            }
        // 1.4.0 the way out: an open blast-door frame in the north wall onto a stairwell that climbs to the exit hatch
        // (right-click it: up into camp, at the bunker entrance)
        int sz0 = z0 - 9, sz1 = z0 - 1;
        run(s, inCamp(String.format(f, x - 2, FLOOR - 1, sz0, x + 2, FLOOR + 10, sz1, shell)));                 // a solid block...
        run(s, inCamp(String.format(f, x - 1, FLOOR + 1, sz0 + 1, x + 1, FLOOR + 9, sz1, "minecraft:air")));     // ...hollowed out
        for (int st = 0; st < 5; st++) {   // five steps up to the north, solid underneath
            int zz = z0 - 3 - st;
            run(s, inCamp(String.format(f, x - 1, FLOOR, zz, x + 1, FLOOR + st, zz, shell)));
            run(s, inCamp(String.format(f, x - 1, FLOOR + 1 + st, zz, x + 1, FLOOR + 1 + st, zz, "minecraft:polished_andesite_stairs[facing=north]")));
        }
        run(s, inCamp(String.format(f, x - 1, FLOOR, sz0 + 1, x + 1, FLOOR + 5, sz0 + 2, shell)));               // top landing
        run(s, inCamp(String.format(f, x - 1, FLOOR, z0 - 2, x + 1, FLOOR, z0 - 2, FLOOR_BLOCK)));              // bottom landing
        run(s, inCamp(String.format(f, x - 2, FLOOR + 1, z0 - 1, x + 2, FLOOR + 4, z0 - 1, "minecraft:dark_prismarine")));   // the blast-door frame (green)
        for (int y = FLOOR + 1; y <= FLOOR + 3; y++)   // hazard marks on the jambs, inside face
            for (int jx : new int[]{x - 2, x + 2})
                run(s, inCamp(String.format("setblock %d %d %d %s", jx, y, z0, (y - FLOOR) % 2 == 1 ? "minecraft:yellow_concrete" : "minecraft:black_concrete")));
        run(s, inCamp(String.format(f, x - 1, FLOOR + 1, z0 - 1, x + 1, FLOOR + 3, z0 - 1, "minecraft:air")));        // 3 wide x 3 high
        run(s, inCamp(String.format(f, x - 1, FLOOR + 5, z0 - 1, x + 1, FLOOR + 7, z0 - 1, shell)));   // 1.6.3 the wall above the door, up to the ceiling (the stairwell cut left it open)
        run(s, inCamp(String.format("setblock %d %d %d minecraft:ochre_froglight", x, FLOOR + 5, z0 - 1)));
        run(s, inCamp(String.format("setblock %d %d %d minecraft:ochre_froglight", x, FLOOR + 9, z0 - 5)));
        run(s, inCamp(String.format("setblock %d %d %d minecraft:ochre_froglight", x - 2, FLOOR + 3, z0 - 3)));   // stairwell: bottom
        run(s, inCamp(String.format("setblock %d %d %d minecraft:ochre_froglight", x + 2, FLOOR + 7, z0 - 7)));   // stairwell: top landing
        run(s, inCamp(String.format(f, x - 1, FLOOR + 9, sz0 + 1, x + 1, FLOOR + 9, sz0 + 2, "minecraft:iron_trapdoor[half=top,open=false]")));  // the hatch
        run(s, inCamp(String.format("kill @e[tag=ez.bunkerexit,x=%d,y=%d,z=%d,distance=..3]", x, FLOOR + 6, sz0 + 2)));
        run(s, inCamp(String.format("summon minecraft:interaction %d.5 %d %d.0 {Tags:[\"ez.bunkerexit\",\"ez.deco\"],width:3.0f,height:4.2f,response:true}", x, FLOOR + 6, sz0 + 2)));
        run(s, inCamp(String.format("summon minecraft:text_display %d.5 %d.5 %d.5 {Tags:[\"ez.bunkerexit\",\"ez.deco\"],billboard:\"center\",text:{text:\"▲ UP TO CAMP\\n\",color:\"green\",bold:true,extra:[{text:\"Right-click the hatch\",color:\"gray\",bold:false}]}}", x, FLOOR + 8, sz0 + 2)));
        // the owner's name over the door; the starter crate
        run(s, inCamp(String.format("kill @e[type=minecraft:text_display,tag=ez.plotname,x=%d,y=%d,z=%d,distance=..%d]", x, FLOOR + 5, z, h + 4)));
        run(s, inCamp(String.format("summon minecraft:text_display %d.5 %d %d.6 {Tags:[\"ez.plotname\"],billboard:\"center\",text:{text:\"%s's bunker\",color:\"gold\",bold:true}}",
                x, FLOOR + 5, z0, p.name.replace("\"", ""))));
        // 1.6.0 the room's plan: arrival at the south end looking up a clear 3-wide aisle to the lit door; the storage
        // wall on the west (crate bays, the starter crate first), upgrade bays on the east (one per upgrade)
        run(s, inCamp(String.format("fill %d %d %d %d %d %d %s replace %s", x - 1, FLOOR, z0, x + 1, FLOOR, z1, AISLE, FLOOR_BLOCK)));
        // 1.6.3 no fixed spots: upgrades and crates go anywhere. The 1.6.0 bay markings and labels come out.
        run(s, inCamp(String.format("fill %d %d %d %d %d %d %s replace %s", x0, FLOOR, z0 + 2, x0 + 1, FLOOR, z1 - 2, FLOOR_BLOCK, BAY)));
        for (int i = 0; i < PERKS.size(); i++) {
            int[] b = perkSpot(p, i);
            run(s, inCamp(String.format("fill %d %d %d %d %d %d %s replace %s", b[0] - 1, FLOOR, b[2] - 1, b[0], FLOOR, b[2] + 1, FLOOR_BLOCK, BAY)));
        }
        run(s, inCamp(String.format("kill @e[type=minecraft:text_display,tag=ez.bunkerlabel,x=%d,y=%d,z=%d,distance=..%d]", x, FLOOR + 3, z, h + 4)));
        // the old upgrade row (along the north wall, in front of the door before 1.6.0) moves to the bays
        for (Perk k : PERKS) {
            int ox = x0 + 3 + 2 * PERKS.indexOf(k);
            run(s, inCamp(String.format("fill %d %d %d %d %d %d minecraft:air replace %s", ox, FLOOR + 1, z0 + 1, ox, FLOOR + 1, z0 + 1, k.block())));
        }
        if (fresh) run(s, inCamp(String.format("setblock %d %d %d %s", x0, FLOOR + 1, z0 + 2, Storage.CRATE_BLOCK)));
    }

    /** 1.3.0: clear a plot's old open-air cell (around OLD_FLOOR) before it moves underground. */
    static void clearOld(MinecraftServer s, Plot p) {
        int x = cx(p.index), z = cz(p.index), c = CELL / 2;
        loadArea(s, x - c, z - c, x + c, z + c);
        for (int y = OLD_FLOOR - 8; y <= OLD_FLOOR + 17; y++)
            run(s, inCamp(String.format("fill %d %d %d %d %d %d minecraft:air", x - c, y, z - c, x + c - 1, y, z + c - 1)));
        run(s, inCamp(String.format("kill @e[type=minecraft:text_display,tag=ez.plotname,x=%d,y=%d,z=%d,distance=..40]", x, OLD_FLOOR, z)));
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
        move(pl, cx(p.index) + 0.5, FLOOR + 1, cz(p.index) + half(p) - 2.5, 180f);
    }

    static void menu(ServerPlayer pl) {
        Ui.open(pl, t("Your Bunker", ChatFormatting.DARK_GRAY), 4, m -> {
            Plot p = of(pl);
            m.put(4, Shops.balanceIcon(pl), null);
            if (p == null) {
                m.put(13, Ui.item(Items.GRASS_BLOCK, t("Claim your bunker (free)", ChatFormatting.GREEN, ChatFormatting.BOLD), List.of(
                        t("Your own " + SIZES[0] + " x " + SIZES[0] + " underground bunker to build in and store gear.", ChatFormatting.GRAY),
                        t("Only you can build or open chests there.", ChatFormatting.GRAY)), true),
                        (q, c) -> { Plot n = claim(q); q.closeContainer(); tp(q, n); Shops.ok(q, "Welcome to your bunker! Use /bunker (or /plot) to come back, /camp to go to camp."); });
                return;
            }
            m.put(11, Ui.item(Items.ENDER_PEARL, t("Go to my bunker", ChatFormatting.AQUA), List.of(t("Or type /bunker", ChatFormatting.GRAY)), false),
                    (q, c) -> { q.closeContainer(); tp(q, p); });
            if (p.level + 1 < SIZES.length) {
                int next = p.level + 1;
                m.put(13, Ui.item(Items.GOLDEN_SHOVEL, t("Upgrade to " + SIZES[next] + " x " + SIZES[next], ChatFormatting.GOLD, ChatFormatting.BOLD), List.of(
                        t("Now " + SIZES[p.level] + " x " + SIZES[p.level], ChatFormatting.GRAY), t("Cost: " + Coins.fmt(COST[next]), ChatFormatting.GOLD)), true),
                        (q, c) -> {
                            if (!Shops.pay(q, COST[next])) { Shops.no(q, "You need " + Coins.fmt(COST[next]) + " (carry them on you)."); return; }
                            p.level = next; save(); lay(q.level().getServer(), p, false, next - 1);
                            Shops.ok(q, "Your bunker is now " + SIZES[next] + " x " + SIZES[next] + ".");
                        });
            } else m.put(13, Ui.item(Items.NETHERITE_SHOVEL, t("Max size: " + SIZES[p.level] + " x " + SIZES[p.level], ChatFormatting.GOLD), List.of(), true), null);
            int used = Storage.count(pl.level().getServer(), p), max = Storage.limit(p);
            Finish cur = FINISHES.stream().filter(fz -> fz.block().equals(shell(p))).findFirst().orElse(FINISHES.get(0));
            m.put(22, Ui.item(cur.icon(), t("Wall finish: " + cur.name(), ChatFormatting.LIGHT_PURPLE, ChatFormatting.BOLD), List.of(
                    t("Change what your bunker's walls", ChatFormatting.GRAY), t("and ceiling are made of.", ChatFormatting.GRAY),
                    t(Coins.fmt(FINISH_COST) + " a change", ChatFormatting.GOLD)), false), (q, c) -> finishes(q, p));
            m.put(15, Ui.item(Items.BARREL, t("Storage: " + used + " / " + max + " Stash Crates", ChatFormatting.YELLOW), List.of(
                    t("Bunker storage is Stash Crates only", ChatFormatting.GRAY), t("(Builder, " + Coins.fmt(25) + "). Only you can open them.", ChatFormatting.GRAY),
                    t("Size 16: 4 crates · 24: 7 · 32: 10.", ChatFormatting.GRAY)), false), null);
            if (p.perks == null) p.perks = new java.util.ArrayList<>();
            int[] slots = {29, 31, 33};
            for (int i = 0; i < PERKS.size(); i++) {
                Perk k = PERKS.get(i);
                boolean own = p.perks.contains(k.key());
                List<net.minecraft.network.chat.Component> lore = new java.util.ArrayList<>();
                for (String l : k.lines()) lore.add(t(l, ChatFormatting.GRAY));
                lore.add(t(own ? "Owned: place it anywhere in your bunker" : "Cost: " + Coins.fmt(k.cost()) + " · you get the block to place", own ? ChatFormatting.GREEN : ChatFormatting.GOLD));
                m.put(slots[i], Ui.item(k.icon(), t((own ? "✔ " : "") + k.name(), own ? ChatFormatting.GREEN : ChatFormatting.YELLOW, ChatFormatting.BOLD), lore, own),
                        own ? (k.key().equals("workbench") ? (q, c) -> Workbench.open(q) : null) : (q, c) -> {
                            if (!Shops.pay(q, k.cost())) { Shops.no(q, "You need " + Coins.fmt(k.cost()) + " (carry them on you)."); return; }
                            p.perks.add(k.key()); save();
                            Shops.give(q, perkItem(k));
                            Shops.ok(q, k.name() + " installed in your bunker.");
                        });
            }
        });
    }

    /** The wall finishes: pick one, pay, and every wall and ceiling block (and the stairwell) is swapped. */
    static void finishes(ServerPlayer pl, Plot p) {
        Ui.open(pl, t("Bunker wall finish", ChatFormatting.DARK_GRAY), 3, m -> {
            for (int i = 0; i < FINISHES.size(); i++) {
                Finish fz = FINISHES.get(i);
                boolean now = fz.block().equals(shell(p));
                m.put(9 + i + (i >= 4 ? 1 : 0), Ui.item(fz.icon(), t((now ? "✔ " : "") + fz.name(), now ? ChatFormatting.GREEN : ChatFormatting.YELLOW, ChatFormatting.BOLD),
                        List.of(t(now ? "Your walls now" : "Cost: " + Coins.fmt(FINISH_COST), now ? ChatFormatting.GREEN : ChatFormatting.GOLD)), now),
                        now ? null : (q, c) -> {
                            if (!Shops.pay(q, FINISH_COST)) { Shops.no(q, "You need " + Coins.fmt(FINISH_COST) + "."); return; }
                            String old = shell(p);
                            p.style = fz.block(); save();
                            restyle(q.level().getServer(), p, old, fz.block());
                            Shops.ok(q, "Your bunker's walls are now " + fz.name() + ".");
                        });
            }
            m.put(22, Ui.item(Items.ARROW, t("Back", ChatFormatting.YELLOW), List.of(), false), (q, c) -> menu(q));
        });
    }

    /** Swap the shell blocks (walls, ceiling, stairwell) from one finish to another; nothing inside the room changes. */
    static void restyle(MinecraftServer s, Plot p, String from, String to) {
        int x = cx(p.index), z = cz(p.index), h = half(p), x0 = x - h, x1 = x + h - 1, z0 = z - h, z1 = z + h - 1;
        loadArea(s, x0 - 2, z0 - 10, x1 + 2, z1 + 2);
        String f = "fill %d %d %d %d %d %d " + to + " replace " + from;
        for (int[] e : new int[][]{{x0 - 1, z0 - 1, x1 + 1, z0 - 1}, {x0 - 1, z1 + 1, x1 + 1, z1 + 1}, {x0 - 1, z0 - 1, x0 - 1, z1 + 1}, {x1 + 1, z0 - 1, x1 + 1, z1 + 1}})
            run(s, inCamp(String.format(f, e[0], FLOOR, e[1], e[2], FLOOR + 7, e[3])));
        run(s, inCamp(String.format(f, x0 - 1, FLOOR + 7, z0 - 1, x1 + 1, FLOOR + 7, z1 + 1)));
        run(s, inCamp(String.format(f, x - 2, FLOOR - 1, z0 - 9, x + 2, FLOOR + 10, z0 - 1)));
    }

    /** The upgrade's block, in a row along the plot's north edge next to the starter chest (decor and a click target). */
    /** 1.6.3: the upgrade's block, named, for the owner to place anywhere in their bunker (breaking it gives it back). */
    static net.minecraft.world.item.ItemStack perkItem(Perk k) {
        var st = new net.minecraft.world.item.ItemStack(k.icon());
        st.set(net.minecraft.core.component.DataComponents.CUSTOM_NAME, t(k.name(), ChatFormatting.AQUA).copy().withStyle(s -> s.withItalic(false)));
        st.set(net.minecraft.core.component.DataComponents.LORE, new net.minecraft.world.item.component.ItemLore(List.of(t("Place it anywhere in your bunker.", ChatFormatting.GRAY))));
        return st;
    }
    /** Where 1.6.0 marked upgrade i's bay (east wall); kept only to clear the old markings. */
    static int[] perkSpot(Plot p, int i) {
        int x1 = cx(p.index) + half(p) - 1, z0 = cz(p.index) - half(p);
        return new int[]{x1, FLOOR + 1, z0 + 3 + 3 * i};
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
            // 1.5.0: the hatch and the blockhouse door are the triggers themselves (the boxes around them are a backup)
            if (pl instanceof ServerPlayer sp && world.dimension().equals(CAMP)) {
                var st = world.getBlockState(hit.getBlockPos());
                boolean hatch = isHatch(world, hit.getBlockPos(), st), door = isCampDoor(world, hit.getBlockPos(), st);
                if (hatch || door) {
                    if (hand != net.minecraft.world.InteractionHand.MAIN_HAND) return InteractionResult.SUCCESS;
                    if (hatch) { Trace.d(sp, "exit hatch block -> camp"); exitToCamp(sp); }
                    else { Trace.d(sp, "blockhouse door block -> bunker"); enterBunker(sp); }
                    return InteractionResult.SUCCESS;
                }
            }
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
            if (pl instanceof ServerPlayer sp && (e.entityTags().contains("ez.bunkerexit") || e.entityTags().contains("ez.bunkerdoor"))) {
                if (hand != net.minecraft.world.InteractionHand.MAIN_HAND) return InteractionResult.SUCCESS;
                if (e.entityTags().contains("ez.bunkerexit")) { Trace.d(sp, "exit hatch box -> camp"); exitToCamp(sp); }
                else { Trace.d(sp, "blockhouse door box -> bunker"); enterBunker(sp); }
                return InteractionResult.SUCCESS;
            }
            return decoAllowed(pl, world, e) ? InteractionResult.PASS : InteractionResult.FAIL;
        });

        CommandRegistrationCallback.EVENT.register((d, ctx, env) -> {
            var plotNode = d.register(Commands.literal("plot")
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
            d.register(Commands.literal("bunker").executes(plotNode.getCommand()).redirect(plotNode));   // 1.3.0
            d.register(Commands.literal("ezadmin").requires(Commands.hasPermission(Commands.LEVEL_GAMEMASTERS))
                    .then(Commands.literal("bunkerfix").executes(c -> {   // 1.4.0: white walls (from reinforced deepslate), the stairwell up
                        load(); MinecraftServer srv = c.getSource().getServer();
                        for (Plot p : plots.values()) { restyle(srv, p, OLD_SHELL, shell(p)); lay(srv, p, false); }   // re-lays the room (crates, builds and placed upgrades stay)
                        c.getSource().sendSuccess(() -> net.minecraft.network.chat.Component.literal("Updated " + plots.size() + " bunkers."), true); return 1; }))
                    .then(Commands.literal("bunkers").executes(c -> {   // 1.3.0: move plots made before underground (old contents cleared)
                        load(); MinecraftServer srv = c.getSource().getServer();
                        for (Plot p : plots.values()) { clearOld(srv, p); lay(srv, p, true); }
                        c.getSource().sendSuccess(() -> net.minecraft.network.chat.Component.literal("Moved " + plots.size() + " plots into bunkers."), true); return 1; })));
            d.register(Commands.literal("camp").executes(c -> { ServerPlayer pl = c.getSource().getPlayerOrException();
                if (raiding(pl)) { Shops.no(pl, "Not during a raid: extract first."); return 0; }
                move(pl, CAMP_SPAWN[0], CAMP_SPAWN[1], CAMP_SPAWN[2], (float) CAMP_SPAWN[3]); return 1; }));
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

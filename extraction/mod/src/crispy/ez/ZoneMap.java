package crispy.ez;

import com.google.gson.Gson;
import com.google.gson.GsonBuilder;
import net.fabricmc.fabric.api.command.v2.CommandRegistrationCallback;
import net.fabricmc.fabric.api.event.lifecycle.v1.ServerTickEvents;
import net.minecraft.commands.Commands;
import net.minecraft.core.BlockPos;
import net.minecraft.server.MinecraftServer;
import net.minecraft.server.level.ServerLevel;
import net.minecraft.server.level.ServerPlayer;
import net.minecraft.world.item.ItemStack;
import net.minecraft.world.item.MapItem;
import net.minecraft.world.level.levelgen.Heightmap;
import net.minecraft.world.level.material.MapColor;
import net.minecraft.world.level.saveddata.maps.MapItemSavedData;

import java.nio.file.Files;
import java.nio.file.Path;
import java.util.ArrayList;
import java.util.List;

/**
 * The zone map: a scale-3 filled map (8 blocks a pixel, centre 448 448, covering 64..960) of the city dimension,
 * drawn by /ezadmin map a little each tick (it generates the terrain as it goes), shaded by height like vanilla maps.
 * Players get a copy with markers for the extraction points and the zone traders: /zonemap in camp, and on every
 * deploy if they don't carry one (the datapack runs /ezmapgive as them).
 */
final class ZoneMap {
    private ZoneMap() {}

    static final Path FILE = Path.of("config", "crispy_extraction", "map.json");
    static final Gson GSON = new GsonBuilder().setPrettyPrinting().create();
    record Pt(String kind, String name, int x, int z) {}
    static final class Data { int id = -1; List<Pt> points = new ArrayList<>(); }
    static Data data;
    static int row = -1;            // next map row to draw while rendering
    static ItemStack rendering;     // the map being drawn

    static Data d() {
        if (data == null) {
            try { data = Files.exists(FILE) ? GSON.fromJson(Files.readString(FILE), Data.class) : new Data(); }
            catch (Exception e) { data = new Data(); }
            if (data.points == null) data.points = new ArrayList<>();
        }
        return data;
    }
    static void save() {
        try { Files.createDirectories(FILE.getParent()); Files.writeString(FILE, GSON.toJson(d())); }
        catch (Exception e) { System.err.println("[crispy-extraction] can't write " + FILE + ": " + e); }
    }
    static void clearPoints() { d().points.clear(); }
    static void point(String kind, String name, BlockPos b) { d().points.add(new Pt(kind, name, b.getX(), b.getZ())); }

    static void render(MinecraftServer server) {
        ServerLevel lvl = server.getLevel(Zone.CITY);
        if (lvl == null) return;
        rendering = MapItem.create(lvl, Zone.CX, Zone.CZ, (byte) 3, true, false);
        row = 0;
        System.out.println("[crispy-extraction] drawing the zone map...");
    }

    static int height(ServerLevel lvl, int x, int z) {
        lvl.getChunk(x >> 4, z >> 4);
        return lvl.getHeight(Heightmap.Types.WORLD_SURFACE, x, z);
    }

    static void tick(MinecraftServer server) {
        if (rendering == null || row < 0) return;
        ServerLevel lvl = server.getLevel(Zone.CITY);
        MapItemSavedData m = MapItem.getSavedData(rendering, lvl);
        if (m == null) { rendering = null; return; }
        // Drawing loads (and the first time generates) ~4,000 city chunks. Going flat out filled the heap faster than
        // the chunk system could save and unload them (OutOfMemoryError, 2026-11-12), so: one map row every 10 ticks,
        // and wait while the heap is more than 60% used so unloads can catch up.
        Runtime rt = Runtime.getRuntime();
        if (server.getTickCount() % 10 != 0 || rt.totalMemory() - rt.freeMemory() > rt.maxMemory() * 0.6) return;
        if (row % 16 == 0) System.out.println("[crispy-extraction] zone map row " + row + "/128");
        int scale = 8, left = m.centerX - 512, top = m.centerZ - 512;
        for (int once = 0; once < 1 && row < 128; once++) {
            int z = top + row * scale + scale / 2;
            int prev = Integer.MIN_VALUE;
            for (int px = 0; px < 128; px++) {
                int x = left + px * scale + scale / 2;
                int y = height(lvl, x, z);
                int north = height(lvl, x, z - scale);
                BlockPos pos = new BlockPos(x, y - 1, z);
                MapColor c = lvl.getBlockState(pos).getMapColor(lvl, pos);
                MapColor.Brightness br = y > north ? MapColor.Brightness.HIGH : y < north ? MapColor.Brightness.LOW : MapColor.Brightness.NORMAL;
                // 1.1.0: the radiation border as a red line
                int zx0 = Zone.CX - Zone.HALF, zx1 = Zone.CX + Zone.HALF, zz0 = Zone.CZ - Zone.HALF, zz1 = Zone.CZ + Zone.HALF;
                int wx = left + px * scale, wz = top + row * scale;
                boolean onX = (wx <= zx0 && zx0 < wx + scale) || (wx <= zx1 && zx1 < wx + scale), onZ = (wz <= zz0 && zz0 < wz + scale) || (wz <= zz1 && zz1 < wz + scale);
                boolean inX = wx + scale > zx0 && wx <= zx1, inZ = wz + scale > zz0 && wz <= zz1;
                if ((onX && inZ) || (onZ && inX)) { m.updateColor(px, row, MapColor.COLOR_RED.getPackedId(MapColor.Brightness.HIGH)); continue; }
                m.updateColor(px, row, c == MapColor.NONE ? MapColor.COLOR_BLACK.getPackedId(MapColor.Brightness.LOW) : c.getPackedId(br));
            }
            row++;
        }
        if (row >= 128) {
            d().id = rendering.get(net.minecraft.core.component.DataComponents.MAP_ID).id();
            save(); row = -1; rendering = null;
            System.out.println("[crispy-extraction] zone map drawn: map id " + d().id);
        }
    }

    static void give(MinecraftServer server, ServerPlayer p) {
        if (d().id < 0) return;
        StringBuilder deco = new StringBuilder();
        int n = 0;
        for (Pt pt : d().points) {
            String type = pt.kind.equals("exfil") ? "minecraft:banner_lime" : "minecraft:banner_yellow";
            if (n++ > 0) deco.append(',');
            deco.append(String.format("p%d:{type:\"%s\",x:%d.0d,z:%d.0d,rotation:180.0f}", n, type, pt.x, pt.z));
        }
        Plots.run(server, String.format("give %s minecraft:filled_map[minecraft:map_id=%d,minecraft:map_decorations={%s},"
                        + "minecraft:custom_name={text:\"Zone Map\",color:\"aqua\",italic:false,bold:true},"
                        + "minecraft:lore=[{text:\"Green flags: extraction points\",color:\"green\",italic:false},{text:\"Yellow flags: traders\",color:\"yellow\",italic:false}]]",
                p.getGameProfile().name(), d().id, deco));
    }

    static boolean carries(ServerPlayer p) {
        var inv = p.getInventory();
        for (int i = 0; i < inv.getContainerSize(); i++) {
            var id = inv.getItem(i).get(net.minecraft.core.component.DataComponents.MAP_ID);
            if (id != null && id.id() == d().id) return true;
        }
        return false;
    }

    static void init() {
        ServerTickEvents.END_SERVER_TICK.register(ZoneMap::tick);
        CommandRegistrationCallback.EVENT.register((dsp, ctx, env) -> {
            dsp.register(Commands.literal("zonemap").executes(c -> {
                ServerPlayer p = c.getSource().getPlayerOrException();
                if (Plots.raiding(p)) { Shops.no(p, "Maps are handed out in camp (and on deploy)."); return 0; }
                if (d().id < 0) { Shops.no(p, "The zone map isn't ready yet."); return 0; }
                if (carries(p)) { Shops.no(p, "You already have a zone map."); return 0; }
                give(c.getSource().getServer(), p); return 1;
            }));
            dsp.register(Commands.literal("ezmapgive").requires(Commands.hasPermission(Commands.LEVEL_GAMEMASTERS)).executes(c -> {
                ServerPlayer p = c.getSource().getPlayerOrException();
                if (d().id >= 0 && !carries(p)) give(c.getSource().getServer(), p);
                return 1;
            }));
        });
    }
}

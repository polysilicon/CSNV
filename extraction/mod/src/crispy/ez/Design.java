package crispy.ez;

import com.google.gson.Gson;
import com.google.gson.GsonBuilder;
import com.google.gson.JsonArray;
import com.google.gson.JsonElement;
import com.google.gson.JsonObject;
import com.google.gson.JsonParser;
import net.minecraft.core.BlockPos;
import net.minecraft.core.Direction;
import net.minecraft.core.registries.BuiltInRegistries;
import net.minecraft.resources.Identifier;
import net.minecraft.server.MinecraftServer;
import net.minecraft.server.level.ServerLevel;
import net.minecraft.world.entity.Entity;
import net.minecraft.world.level.LightLayer;
import net.minecraft.world.phys.AABB;
import net.minecraft.world.phys.Vec3;
import net.minecraft.world.phys.shapes.VoxelShape;

import java.nio.file.Files;
import java.nio.file.Path;
import java.util.*;

/**
 * Design checks (1.6.0), run by /ezadmin selftest and after every camp rebuild. They test the plan the way a player
 * meets it, on the live world:
 *  - Walkability: a breadth-first search over every place a player fits (0.6 x 1.8 box on the real collision shapes),
 *    moving to a side neighbour by stepping (<= 0.6 up), jumping (<= 1.25 up, with headroom) or dropping (<= 3 down).
 *    From the camp spawn (and from a bunker's arrival point) every destination must be reached, with a step count:
 *    traders within entity reach (3.0 from the eyes), blocks within block reach (4.5).
 *  - Clearance: every doorway in the plan has its width and headroom (3 high for main entries, 2 for doors); every
 *    path cell is standable with 3 blocks of headroom; every trader stands within 4.5 blocks of a path.
 *  - Lighting: block light at the feet of every walkable place. Below 7 is dark: a fail on a path, an aisle or next to
 *    a destination, a warning elsewhere.
 *  - Block IDs: every block the camp and bunker builders use is looked up in the running game's registries; every camp
 *    function exists (a bad ID stops a function loading); no bunker command failed to parse.
 * The plan (paths, doorways, destinations, IDs, functions) comes from config/crispy_extraction/layout.json, written by
 * the datapack build from the same numbers the camp is built from. Everything also goes to selftest_report.json.
 */
final class Design {
    private Design() {}

    static final double REACH_BLOCK = 4.5, REACH_ENTITY = 3.0, STEP = 0.6, JUMP = 1.25, DROP = 3.0;
    static final int DARK = 7;
    static final Path LAYOUT = Path.of("config", "crispy_extraction", "layout.json");
    static final Path REPORT = Path.of("config", "crispy_extraction", "selftest_report.json");
    static JsonObject report = new JsonObject();

    static JsonObject layout() {
        try { return JsonParser.parseString(Files.readString(LAYOUT)).getAsJsonObject(); }
        catch (Exception e) { return null; }
    }

    // ---------------------------------------------------------------- the walkable graph
    record Node(int x, int z, double h) {
        Vec3 eye() { return new Vec3(x + 0.5, h + 1.62, z + 0.5); }
        BlockPos feet() { return BlockPos.containing(x + 0.5, h + 0.01, z + 0.5); }
        String key() { return x + "," + z + "," + Math.round(h * 16); }
        String at() { return String.format("%d %.1f %d", x, h, z); }
    }

    static final class Graph {
        final ServerLevel lvl; final int x0, y0, z0, x1, y1, z1;
        final Map<Long, List<Double>> cols = new HashMap<>();
        final Map<String, Integer> steps = new HashMap<>();
        final List<Node> order = new ArrayList<>();
        Graph(ServerLevel lvl, int x0, int y0, int z0, int x1, int y1, int z1) { this.lvl = lvl; this.x0 = x0; this.y0 = y0; this.z0 = z0; this.x1 = x1; this.y1 = y1; this.z1 = z1; }

        boolean clear(int x, int z, double lo, double hi) {
            return lvl.noCollision(new AABB(x + 0.2, lo + 0.01, z + 0.2, x + 0.8, hi, z + 0.8));
        }
        List<Double> heights(int x, int z) {
            return cols.computeIfAbsent(((long) x << 32) ^ (z & 0xffffffffL), k -> {
                List<Double> out = new ArrayList<>();
                if (x < x0 || x > x1 || z < z0 || z > z1) return out;
                for (int y = y0; y <= y1; y++) {
                    BlockPos p = new BlockPos(x, y, z);
                    VoxelShape sh = lvl.getBlockState(p).getCollisionShape(lvl, p);
                    if (sh.isEmpty()) continue;
                    double top = y + sh.max(Direction.Axis.Y);
                    if (clear(x, z, top, top + 1.8)) out.add(top);
                }
                return out;
            });
        }
        Node near(double x, double y, double z) {
            int bx = (int) Math.floor(x), bz = (int) Math.floor(z);
            Node best = null;
            for (double h : heights(bx, bz)) if (Math.abs(h - y) <= 0.6 && (best == null || Math.abs(h - y) < Math.abs(best.h - y))) best = new Node(bx, bz, h);
            return best;
        }
        void bfs(Node start) {
            ArrayDeque<Node> q = new ArrayDeque<>();
            steps.put(start.key(), 0); order.add(start); q.add(start);
            int[][] dirs = {{1, 0}, {-1, 0}, {0, 1}, {0, -1}};
            while (!q.isEmpty()) {
                Node a = q.poll(); int d = steps.get(a.key());
                for (int[] dv : dirs) {
                    int nx = a.x + dv[0], nz = a.z + dv[1];
                    for (double h : heights(nx, nz)) {
                        double dh = h - a.h;
                        if (dh > JUMP || dh < -DROP) continue;
                        double hi = Math.max(a.h, h) + 1.8;
                        if (dh > STEP) hi = a.h + JUMP + 1.8;   // a jump needs headroom above where you jump from
                        // the cell you leave: free from your feet up; the cell you enter: free from its floor up to
                        // where your head passes (on a drop, the height you walk off at)
                        if (!clear(a.x, a.z, a.h, hi) || !clear(nx, nz, h, Math.max(h + 1.8, a.h + 1.8))) continue;
                        Node b = new Node(nx, nz, h);
                        if (steps.putIfAbsent(b.key(), d + 1) == null) { order.add(b); q.add(b); }
                    }
                }
            }
        }
        /** Fewest steps to a place a player can click target from (eye within reach of the box). */
        Object[] reach(AABB target, double reach) {
            Node best = null; int bs = Integer.MAX_VALUE;
            for (Node n : order) {
                Vec3 e = n.eye();
                double dx = Math.max(Math.max(target.minX - e.x, 0), e.x - target.maxX), dy = Math.max(Math.max(target.minY - e.y, 0), e.y - target.maxY),
                        dz = Math.max(Math.max(target.minZ - e.z, 0), e.z - target.maxZ);
                if (Math.sqrt(dx * dx + dy * dy + dz * dz) <= reach) { int s = steps.get(n.key()); if (s < bs) { bs = s; best = n; } }
            }
            return new Object[]{best, bs};
        }
        int light(Node n) { return lvl.getBrightness(LightLayer.BLOCK, n.feet()); }
    }

    static int headroom(ServerLevel lvl, BlockPos feet) {
        int n = 0;
        for (int k = 0; k < 6; k++) { BlockPos q = feet.above(k); if (lvl.getBlockState(q).getCollisionShape(lvl, q).isEmpty()) n++; else break; }
        return n;
    }
    static boolean solidBelow(ServerLevel lvl, BlockPos feet) { BlockPos b = feet.below(); return !lvl.getBlockState(b).getCollisionShape(lvl, b).isEmpty(); }

    static JsonArray arr(int... v) { JsonArray a = new JsonArray(); for (int i : v) a.add(i); return a; }

    // ---------------------------------------------------------------- camp
    static void camp(MinecraftServer server, ServerLevel camp) {
        JsonObject L = layout();
        if (L == null) { SelfTest.check("design: layout.json present", false, LAYOUT.toString()); return; }
        JsonObject out = new JsonObject(); report.add("camp", out);
        JsonArray rg = L.getAsJsonArray("region");
        Graph g = new Graph(camp, rg.get(0).getAsInt(), rg.get(1).getAsInt(), rg.get(2).getAsInt(), rg.get(3).getAsInt(), rg.get(4).getAsInt(), rg.get(5).getAsInt());
        JsonArray sp = L.getAsJsonArray("spawn");
        Node start = g.near(sp.get(0).getAsDouble(), sp.get(1).getAsDouble(), sp.get(2).getAsDouble());
        SelfTest.check("walk: spawn is a place a player fits", start != null, "");
        if (start == null) return;
        g.bfs(start);
        out.addProperty("walkable_places", g.order.size());
        // destinations
        JsonArray dests = new JsonArray(); out.add("destinations", dests);
        List<AABB> destBoxes = new ArrayList<>();
        for (JsonElement de : L.getAsJsonArray("destinations")) {
            JsonObject d = de.getAsJsonObject(); String name = d.get("name").getAsString(), kind = d.get("kind").getAsString();
            JsonArray pos = d.getAsJsonArray("pos"); Vec3 p = new Vec3(pos.get(0).getAsDouble(), pos.get(1).getAsDouble(), pos.get(2).getAsDouble());
            AABB box; double r;
            if (kind.equals("npc")) {
                Entity npc = camp.getEntities((Entity) null, new AABB(p, p).inflate(1.5, 3, 1.5), e -> e.entityTags().stream().anyMatch(t -> t.startsWith("ez.shop."))).stream().findFirst().orElse(null);
                box = npc != null ? npc.getBoundingBox() : new AABB(p.x - 0.3, p.y, p.z - 0.3, p.x + 0.3, p.y + 1.8, p.z + 0.3); r = REACH_ENTITY;
            } else if (kind.equals("pad")) { box = new AABB(p, p).inflate(3.5, 0, 3.5).expandTowards(0, 2.5, 0); r = REACH_ENTITY; }
            else if (kind.equals("door")) { box = new AABB(Math.floor(p.x), p.y, Math.floor(p.z) + 0.8, Math.floor(p.x) + 1, p.y + 2, Math.floor(p.z) + 1); r = REACH_BLOCK; }
            else { box = new AABB(p, p).inflate(0.5, 0, 0.5).expandTowards(0, 0.1, 0); r = 0.9; }
            destBoxes.add(box.inflate(r));
            Object[] res = g.reach(box, kind.equals("point") ? 2.0 : r);
            Node n = (Node) res[0];
            JsonObject j = new JsonObject(); j.addProperty("name", name); j.addProperty("reached", n != null);
            if (n != null) { j.addProperty("steps", (int) res[1]); j.addProperty("from", n.at()); }
            dests.add(j);
            SelfTest.check("walk: spawn -> " + name, n != null, n == null ? "not reachable" : res[1] + " steps, click from " + n.at());
        }
        // clearance: doorways
        JsonArray doors = new JsonArray(); out.add("doorways", doors);
        for (JsonElement de : L.getAsJsonArray("doorways")) {
            JsonObject d = de.getAsJsonObject(); int needW = d.get("width").getAsInt(), needH = d.get("height").getAsInt();
            int width = 0, minH = 99;
            for (JsonElement ce : d.getAsJsonArray("cells")) {
                JsonArray c = ce.getAsJsonArray(); BlockPos f = new BlockPos(c.get(0).getAsInt(), c.get(1).getAsInt(), c.get(2).getAsInt());
                int hr = solidBelow(camp, f) ? headroom(camp, f) : 0;
                if (hr >= 2) width++;
                minH = Math.min(minH, hr);
            }
            boolean ok = width >= needW && minH >= needH;
            JsonObject j = new JsonObject(); j.addProperty("name", d.get("name").getAsString()); j.addProperty("width", width); j.addProperty("headroom", minH);
            j.addProperty("need_width", needW); j.addProperty("need_headroom", needH); j.addProperty("ok", ok); doors.add(j);
            SelfTest.check("clearance: " + d.get("name").getAsString(), ok, "width " + width + "/" + needW + ", headroom " + minH + "/" + needH);
        }
        // clearance: paths
        JsonArray paths = new JsonArray(); out.add("paths", paths);
        int pathHead = L.get("path_headroom").getAsInt();
        Set<Long> pathCells = new HashSet<>();
        for (JsonElement pe : L.getAsJsonArray("paths")) {
            JsonObject pth = pe.getAsJsonObject(); JsonArray b = pth.getAsJsonArray("box");
            int bx0 = b.get(0).getAsInt(), bz0 = b.get(1).getAsInt(), bx1 = b.get(2).getAsInt(), bz1 = b.get(3).getAsInt();
            int cells = 0, minH = 99; List<String> bad = new ArrayList<>();
            for (int x = bx0; x <= bx1; x++) for (int z = bz0; z <= bz1; z++) {
                cells++; pathCells.add(((long) x << 32) ^ (z & 0xffffffffL));
                BlockPos f = new BlockPos(x, 64, z);
                int hr = solidBelow(camp, f) ? headroom(camp, f) : 0;
                minH = Math.min(minH, hr);
                if (hr < pathHead && bad.size() < 6) bad.add(x + " " + z + " (" + hr + ")");
            }
            int w = Math.min(bx1 - bx0, bz1 - bz0) + 1;
            boolean ok = bad.isEmpty() && w >= L.get("path_width").getAsInt();
            JsonObject j = new JsonObject(); j.addProperty("name", pth.get("name").getAsString()); j.addProperty("cells", cells); j.addProperty("width", w);
            j.addProperty("min_headroom", minH); j.addProperty("ok", ok); paths.add(j);
            SelfTest.check("clearance: path " + pth.get("name").getAsString(), ok, cells + " cells, " + w + " wide, headroom >= " + minH + (bad.isEmpty() ? "" : "; short at " + bad));
        }
        // every trader within 4.5 blocks of a path
        double maxD = L.get("npc_path_max").getAsDouble();
        for (JsonElement de : L.getAsJsonArray("destinations")) {
            JsonObject d = de.getAsJsonObject(); if (!d.get("kind").getAsString().equals("npc")) continue;
            JsonArray pos = d.getAsJsonArray("pos"); double px = pos.get(0).getAsDouble(), pz = pos.get(2).getAsDouble(), best = 99;
            for (long k : pathCells) { int x = (int) (k >> 32), z = (int) k; best = Math.min(best, Math.hypot(x + 0.5 - px, z + 0.5 - pz)); }
            final double bb = best;
            SelfTest.check("layout: " + d.get("name").getAsString() + " within " + maxD + " of a path", best <= maxD, String.format("%.1f blocks", bb));
        }
        lighting(out, g, (n) -> pathCells.contains(((long) n.x << 32) ^ (n.z & 0xffffffffL)) || destBoxes.stream().anyMatch(b -> b.contains(n.eye())), "camp");
    }

    interface Key { boolean test(Node n); }
    static void lighting(JsonObject out, Graph g, Key key, String where) {
        int dark = 0, keyDark = 0; JsonArray spots = new JsonArray(); int[] hist = new int[16];
        for (Node n : g.order) {
            int l = g.light(n); hist[l]++;
            if (l < DARK) {
                dark++;
                boolean k = key.test(n);
                if (k) keyDark++;
                if (k ? keyDark <= 150 : dark - keyDark <= 50) { JsonObject j = new JsonObject(); j.addProperty("at", n.at()); j.addProperty("light", l); j.addProperty("on_route", k); spots.add(j); }
            }
        }
        JsonObject j = new JsonObject(); j.addProperty("walkable", g.order.size()); j.addProperty("dark", dark); j.addProperty("dark_on_routes", keyDark);
        j.add("histogram", arr(hist)); j.add("dark_spots", spots); out.add("lighting", j);
        SelfTest.check("lighting: no dark spot on a route (" + where + ")", keyDark == 0, g.order.size() + " walkable places, " + dark + " below light " + DARK + ", " + keyDark + " of them on a route");
    }

    // ---------------------------------------------------------------- a bunker (the self-test's own)
    static void bunker(MinecraftServer server, ServerLevel camp, Plots.Plot p, String tag) {
        JsonObject out = new JsonObject(); report.add("bunker" + tag.trim(), out);
        int x = Plots.cx(p.index), z = Plots.cz(p.index), h = Plots.half(p), F = Plots.FLOOR, x0 = x - h, x1 = x + h - 1, z0 = z - h, z1 = z + h - 1;
        Graph g = new Graph(camp, x0 - 2, F - 1, z0 - 11, x1 + 2, F + 10, z1 + 2);
        Node start = g.near(x + 0.5, F + 1, z + h - 2.5);
        SelfTest.check("walk: bunker arrival is a place a player fits" + tag, start != null, "");
        if (start == null) return;
        g.bfs(start);
        out.addProperty("walkable_places", g.order.size());
        record D(String name, AABB box, double r) {}
        List<D> ds = new ArrayList<>();
        // 1.6.3: no fixed spots (crates and upgrades go anywhere), so every floor place in the room must be reachable
        int floor = 0, reached = 0, far = 0;
        for (int bx = x0; bx <= x1; bx++) for (int bz = z0; bz <= z1; bz++) {
            if (!g.heights(bx, bz).contains((double) (F + 1))) continue;   // a crate or a build stands there
            floor++;
            Integer st = g.steps.get(new Node(bx, bz, F + 1).key());
            if (st != null) { reached++; far = Math.max(far, st); }
        }
        out.addProperty("room_floor_places", floor); out.addProperty("room_floor_reached", reached); out.addProperty("room_farthest_steps", far);
        SelfTest.check("walk: every floor place in the room reachable" + tag, reached == floor, reached + " / " + floor + ", farthest " + far + " steps");
        ds.add(new D("blast door (through it)", new AABB(x - 1, F + 1, z0 - 1, x + 2, F + 3, z0), 0.9));
        ds.add(new D("stairwell top (the hatch)", new AABB(x - 1, F + 9, z0 - 8, x + 2, F + 10, z0 - 6), REACH_BLOCK));
        JsonArray dests = new JsonArray(); out.add("destinations", dests);
        for (D d : ds) {
            Object[] res = g.reach(d.box, d.r); Node n = (Node) res[0];
            JsonObject j = new JsonObject(); j.addProperty("name", d.name); j.addProperty("reached", n != null);
            if (n != null) { j.addProperty("steps", (int) res[1]); j.addProperty("from", n.at()); }
            dests.add(j);
            SelfTest.check("walk: arrival -> " + d.name + tag, n != null, n == null ? "not reachable" : res[1] + " steps, from " + n.at());
        }
        BlockPos leak = leak(camp, p);
        out.addProperty("sealed", leak == null);
        SelfTest.check("sealed: no opening in the bunker's shell" + tag, leak == null, leak == null ? "" : "air reaches outside from " + leak.toShortString());
        // clearance: the blast door (main entry), the stairwell (3 wide, 2 of headroom over every step), the aisle
        JsonArray doors = new JsonArray(); out.add("doorways", doors);
        int dw = 0, dh = 99;
        for (int k = x - 1; k <= x + 1; k++) { BlockPos f = new BlockPos(k, F + 1, z0 - 1); int hr = solidBelow(camp, f) ? headroom(camp, f) : 0; if (hr >= 2) dw++; dh = Math.min(dh, hr); }
        door(doors, "blast door (main)" + tag, dw, dh, 3, 3);
        int sw = 3, sh = 99;
        for (int st = 0; st < 5; st++) for (int k = x - 1; k <= x + 1; k++) { BlockPos f = new BlockPos(k, F + 2 + st, z0 - 3 - st); int hr = headroom(camp, f); if (hr < 2) sw = Math.min(sw, 2); sh = Math.min(sh, hr); }
        door(doors, "stairwell" + tag, sw, sh, 3, 2);
        int aisleMin = 99;
        for (int k = x - 1; k <= x + 1; k++) for (int zz = z0; zz <= z1; zz++) { BlockPos f = new BlockPos(k, F + 1, zz); aisleMin = Math.min(aisleMin, solidBelow(camp, f) ? headroom(camp, f) : 0); }
        door(doors, "aisle, arrival to door" + tag, 3, aisleMin, 3, 3);
        lighting(out, g, n -> (n.x >= x - 1 && n.x <= x + 1) || ds.stream().anyMatch(d -> d.box.inflate(d.r).contains(n.eye())), "bunker" + tag);
    }
    /** 1.6.4: air flooded from a bunker's arrival point (through the room, the door, the stairwell) must never reach the
     *  edge of a box round the bunker; returns the last inside cell before the first leak, or null when it's sealed. */
    static BlockPos leak(ServerLevel camp, Plots.Plot p) {
        int x = Plots.cx(p.index), z = Plots.cz(p.index), h = Plots.half(p), F = Plots.FLOOR, x0 = x - h, x1 = x + h - 1, z0 = z - h, z1 = z + h - 1;
        int bx0 = x0 - 3, bx1 = x1 + 3, by0 = F - 2, by1 = F + 12, bz0 = z0 - 12, bz1 = z1 + 3;
        ArrayDeque<BlockPos> q = new ArrayDeque<>(); Set<BlockPos> seen = new HashSet<>();
        BlockPos s0 = BlockPos.containing(x + 0.5, F + 1, z + h - 2.5); q.add(s0); seen.add(s0);
        int cells = 0;
        while (!q.isEmpty() && cells < 200000) {
            BlockPos c = q.poll(); cells++;
            for (Direction d : Direction.values()) {
                BlockPos n = c.relative(d);
                if (seen.contains(n) || !camp.getBlockState(n).isAir()) continue;
                if (n.getX() <= bx0 || n.getX() >= bx1 || n.getY() <= by0 || n.getY() >= by1 || n.getZ() <= bz0 || n.getZ() >= bz1) return c;
                seen.add(n); q.add(n);
            }
        }
        return null;
    }
    /** Every player's bunker, as it stands. */
    static void realBunkers(MinecraftServer server, ServerLevel camp) {
        JsonArray arr = new JsonArray(); report.add("player_bunkers", arr);
        for (Plots.Plot p : Plots.plots.values()) {
            if (p.name == null || p.name.equals(SelfTest.PROFILE.name())) continue;
            Plots.loadArea(server, Plots.cx(p.index) - 30, Plots.cz(p.index) - 40, Plots.cx(p.index) + 30, Plots.cz(p.index) + 30);
            BlockPos l = leak(camp, p);
            JsonObject j = new JsonObject(); j.addProperty("index", p.index); j.addProperty("sealed", l == null); arr.add(j);
            SelfTest.check("sealed: player bunker #" + p.index, l == null, l == null ? "" : "air reaches outside from " + l.toShortString());
        }
    }

    static void door(JsonArray doors, String name, int w, int h, int needW, int needH) {
        boolean ok = w >= needW && h >= needH;
        JsonObject j = new JsonObject(); j.addProperty("name", name); j.addProperty("width", w); j.addProperty("headroom", h);
        j.addProperty("need_width", needW); j.addProperty("need_headroom", needH); j.addProperty("ok", ok); doors.add(j);
        SelfTest.check("clearance: " + name, ok, "width " + w + "/" + needW + ", headroom " + h + "/" + needH);
    }

    // ---------------------------------------------------------------- block IDs
    static void ids(MinecraftServer server) {
        JsonObject out = new JsonObject(); report.add("block_ids", out);
        JsonObject L = layout();
        List<String> badCamp = new ArrayList<>(); int nCamp = 0;
        if (L != null && L.has("block_ids")) for (JsonElement e : L.getAsJsonArray("block_ids")) {
            nCamp++; String id = e.getAsString();
            if (!BuiltInRegistries.BLOCK.containsKey(Identifier.parse(id))) badCamp.add(id);
        }
        out.addProperty("camp_checked", nCamp); out.add("camp_unknown", new Gson().toJsonTree(badCamp));
        SelfTest.check("block IDs: camp and palette, against the 26.2 registry", nCamp > 0 && badCamp.isEmpty(), nCamp + " checked" + (badCamp.isEmpty() ? "" : ", unknown " + badCamp));
        List<String> badFn = new ArrayList<>(); int nFn = 0;
        if (L != null && L.has("functions")) for (JsonElement e : L.getAsJsonArray("functions")) {
            nFn++; if (server.getFunctions().get(Identifier.parse(e.getAsString())).isEmpty()) badFn.add(e.getAsString());
        }
        out.addProperty("functions_checked", nFn); out.add("functions_missing", new Gson().toJsonTree(badFn));
        SelfTest.check("camp functions all loaded (a bad ID would stop one loading)", nFn > 0 && badFn.isEmpty(), nFn + " checked" + (badFn.isEmpty() ? "" : ", missing " + badFn));
        List<String> badUsed = new ArrayList<>();
        for (String id : Plots.USED_IDS) {
            Identifier k = Identifier.parse(id);
            if (!BuiltInRegistries.BLOCK.containsKey(k) && !BuiltInRegistries.ENTITY_TYPE.containsKey(k) && !BuiltInRegistries.ITEM.containsKey(k)) badUsed.add(id);
        }
        out.addProperty("bunker_ids_checked", Plots.USED_IDS.size()); out.add("bunker_unknown", new Gson().toJsonTree(badUsed));
        out.add("bunker_bad_commands", new Gson().toJsonTree(Plots.BAD_COMMANDS));
        SelfTest.check("block IDs: bunker builder, against the 26.2 registry", badUsed.isEmpty(), Plots.USED_IDS.size() + " checked" + (badUsed.isEmpty() ? "" : ", unknown " + badUsed));
        SelfTest.check("bunker builder: every command parsed", Plots.BAD_COMMANDS.isEmpty(), Plots.BAD_COMMANDS.isEmpty() ? "" : Plots.BAD_COMMANDS.get(0));
    }

    /** 1.7.0: the armour sets load; vanilla armour converts; no vanilla recipe is loaded. */
    static void armor(MinecraftServer server) {
        JsonObject out = new JsonObject(); report.add("armor", out);
        Armor.SETS.clear(); Armor.load(server);
        int pieces = Armor.SETS.values().stream().mapToInt(Map::size).sum();
        out.addProperty("sets", Armor.SETS.size()); out.addProperty("pieces", pieces);
        SelfTest.check("armour: 6 sets of 4 pieces load", Armor.SETS.size() == 6 && pieces == 24, Armor.SETS.size() + " sets, " + pieces + " pieces");
        String[][] conv = {{"iron_chestplate", "patrol"}, {"diamond_helmet", "tactical"}, {"netherite_boots", "juggernaut"}, {"leather_leggings", "scav"}, {"turtle_helmet", "scav"}};
        int okc = 0;
        for (String[] c : conv) {
            var to = Armor.convert(server, new net.minecraft.world.item.ItemStack(BuiltInRegistries.ITEM.getValue(Identifier.withDefaultNamespace(c[0]))));
            if (to != null && c[1].equals(Armor.set(to))) okc++;
        }
        SelfTest.check("armour: vanilla pieces swap for set pieces", okc == conv.length, okc + " / " + conv.length);
        var head = Armor.SETS.getOrDefault("tactical", Map.of()).get("head");
        boolean armoured = head != null && head.get(net.minecraft.core.component.DataComponents.ATTRIBUTE_MODIFIERS) != null && head.is(net.minecraft.world.item.Items.PLAYER_HEAD);
        SelfTest.check("armour: helmets are player heads with armour", armoured, "");
        long vanilla = server.getRecipeManager().getRecipes().stream().filter(r -> r.id().toString().contains("/ minecraft:")).count();
        long all = server.getRecipeManager().getRecipes().size();
        out.addProperty("vanilla_recipes", vanilla); out.addProperty("recipes", all);
        SelfTest.check("recipes: no vanilla recipe loaded", vanilla == 0, vanilla + " vanilla of " + all);
    }

    /** 1.8.0: stations, recipes, rings, spawners, building recipes. */
    static void crafting(MinecraftServer server) {
        JsonObject out = new JsonObject(); report.add("crafting", out);
        Stations.BY_BLOCK.clear(); Stations.load(server);
        int recipes = Stations.BY_BLOCK.values().stream().mapToInt(s -> s.recipes().size()).sum();
        out.addProperty("stations", Stations.BY_BLOCK.size()); out.addProperty("station_recipes", recipes);
        SelfTest.check("crafting: 6 stations load", Stations.BY_BLOCK.size() == 6, Stations.BY_BLOCK.size() + " stations, " + recipes + " recipes");
        // every input is something that exists: one of our items (made somewhere, sold, or a valuable) or a vanilla item
        java.util.Set<String> ezKeys = new java.util.HashSet<>(List.of("bandage", "pills", "scrap", "wire", "medkit", "ammo"));
        for (var s : Stations.BY_BLOCK.values()) for (var r : s.recipes()) { String k = Shops.ezKey(r.out()); if (k != null) ezKeys.add(k); }
        Shops.load(server);
        for (Shops.Shop sh : Shops.SHOPS.values()) for (Shops.Sell se : sh.sell()) ezKeys.add(se.key());
        List<String> bad = new ArrayList<>();
        for (var s : Stations.BY_BLOCK.values()) for (var r : s.recipes()) {
            if (r.out().isEmpty()) bad.add(s.key() + "/" + r.key() + " makes nothing");
            for (var in : r.in()) {
                boolean ok = in.match().startsWith("ez:") ? ezKeys.contains(in.match().substring(3)) : BuiltInRegistries.ITEM.containsKey(Identifier.parse(in.match()));
                if (!ok) bad.add(s.key() + "/" + r.key() + " needs unknown " + in.match());
            }
        }
        SelfTest.check("crafting: every recipe input exists", bad.isEmpty(), bad.isEmpty() ? "" : String.join("; ", bad.subList(0, Math.min(4, bad.size()))));
        long ezRecipes = server.getRecipeManager().getRecipes().stream().filter(r -> r.id().toString().contains("/ ez:")).count();
        out.addProperty("building_recipes", ezRecipes);
        SelfTest.check("crafting: building recipes loaded", ezRecipes >= 20, ezRecipes + " recipes");
        boolean rings = Zone.tier(Zone.CX, Zone.CZ) == 4 && Zone.tier(Zone.CX + 120, Zone.CZ) == 3 && Zone.tier(Zone.CX + 200, Zone.CZ) == 2 && Zone.tier(Zone.CX + 350, Zone.CZ) == 1;
        SelfTest.check("zone: four rings from the centre out", rings, "");
        List<String> missing = new ArrayList<>();
        for (String f : List.of("ez:spawner/ring1", "ez:spawner/ring2", "ez:spawner/ring3", "ez:spawner/ring4", "ez:spawner/scav", "ez:spawner/sniper", "ez:spawner/heavy", "ez:crate/fill4", "ez:ai/gunner_long"))
            if (server.getFunctions().get(Identifier.parse(f)).isEmpty()) missing.add(f);
        SelfTest.check("zone: ring spawners, new raiders and Core crates loaded", missing.isEmpty(), missing.isEmpty() ? "" : "missing " + missing);
    }

    static void write(int passed, List<String> fails) {
        report.addProperty("passed", passed); report.add("failed", new Gson().toJsonTree(fails));
        report.addProperty("at", java.time.Instant.now().toString());
        try { Files.createDirectories(REPORT.getParent()); Files.writeString(REPORT, new GsonBuilder().setPrettyPrinting().create().toJson(report)); }
        catch (Exception e) { SelfTest.LOG.error("[ez-selftest] can't write the report", e); }
    }
}

package crispy.lobby;

import com.google.gson.JsonArray;
import com.google.gson.JsonObject;
import com.google.gson.JsonParser;
import com.sun.net.httpserver.HttpExchange;
import com.sun.net.httpserver.HttpServer;
import net.kyori.adventure.text.Component;
import net.kyori.adventure.text.serializer.gson.GsonComponentSerializer;
import org.bukkit.Bukkit;
import org.bukkit.Sound;
import org.bukkit.inventory.Inventory;
import org.bukkit.inventory.ItemStack;

import java.io.IOException;
import java.io.OutputStream;
import java.net.InetSocketAddress;
import java.net.URLDecoder;
import java.nio.charset.StandardCharsets;
import java.util.HashMap;
import java.util.Map;
import java.util.UUID;
import java.util.concurrent.ConcurrentHashMap;
import java.util.concurrent.Executors;
import java.util.concurrent.TimeUnit;

/**
 * /vote and /cosmetics on every server, without a trip to the lobby. The other servers (crispy_chattags on Fabric,
 * CrispyChatTags on Paper) call this localhost-only HTTP API and draw the chest menu themselves:
 *   GET /open?uuid=..&name=..&cmd=vote|cosmetics|links|top   GET /click?uuid=..&slot=..&shift=0|1   GET /close?uuid=..
 * The same Votes menu code runs as for a lobby player, through a Viewer.Remote that records what it shows. Reply:
 *   {"open":{"title":<text json>,"rows":n,"items":[{"slot":i,"item":<item json>}]} | absent,
 *    "close":true|false, "messages":[<text json>], "sounds":[{"id":"minecraft:..","volume":v,"pitch":p}], "connect":"server"|absent}
 * Items are Paper's serializeItemAsJson (the game's own item codec, read natively by the Fabric servers), plus a
 * "simple" copy (material, name, lore, glint, head) for older Paper servers (Factions) that can't read a newer item.
 */
final class RemoteMenus {
    private final CrispyLobby plugin;
    private final Map<UUID, Votes.Menu> open = new ConcurrentHashMap<>();   // each remote player's current menu
    private HttpServer http;

    RemoteMenus(CrispyLobby plugin) { this.plugin = plugin; }

    void start() {
        int port = plugin.getConfig().getInt("remote-menus.port", 25599);
        try {
            http = HttpServer.create(new InetSocketAddress("127.0.0.1", port), 0);
            http.setExecutor(Executors.newFixedThreadPool(2));
            http.createContext("/open", x -> handle(x, true));
            http.createContext("/click", x -> handle(x, false));
            http.createContext("/close", x -> {   // the player closed the menu over there
                try { forget(UUID.fromString(query(x).get("uuid"))); } catch (Exception ignored) {}
                x.sendResponseHeaders(204, -1); x.close();
            });
            http.start();
            plugin.getLogger().info("Remote /vote and /cosmetics menus on 127.0.0.1:" + port);
        } catch (IOException e) { plugin.getLogger().warning("Remote menus off: can't listen on port " + port + ": " + e); }
    }

    void stop() { if (http != null) http.stop(0); }

    private static Map<String, String> query(HttpExchange x) {
        Map<String, String> q = new HashMap<>();
        String raw = x.getRequestURI().getRawQuery();
        if (raw != null) for (String kv : raw.split("&")) {
            int i = kv.indexOf('=');
            if (i > 0) q.put(URLDecoder.decode(kv.substring(0, i), StandardCharsets.UTF_8), URLDecoder.decode(kv.substring(i + 1), StandardCharsets.UTF_8));
        }
        return q;
    }

    private void handle(HttpExchange x, boolean isOpen) throws IOException {
        JsonObject out;
        int code = 200;
        try {
            Map<String, String> q = query(x);
            UUID uuid = UUID.fromString(q.get("uuid"));
            String name = q.getOrDefault("name", "");
            out = Bukkit.getScheduler().callSyncMethod(plugin, () -> run(uuid, name, isOpen, q)).get(5, TimeUnit.SECONDS);
        } catch (Exception e) {
            code = 400; out = new JsonObject(); out.addProperty("error", String.valueOf(e));
        }
        byte[] body = out.toString().getBytes(StandardCharsets.UTF_8);
        x.getResponseHeaders().set("Content-Type", "application/json");
        x.sendResponseHeaders(code, body.length);
        try (OutputStream os = x.getResponseBody()) { os.write(body); }
    }

    /** Main thread: run the menu code for this remote player and describe the result. */
    private JsonObject run(UUID uuid, String name, boolean isOpen, Map<String, String> q) {
        Votes v = plugin.votes;
        Viewer.Remote r = new Viewer.Remote(name, uuid);
        if (!name.isEmpty()) { Votes.PD pd = v.pd(name); pd.name = name; }
        if (isOpen) {
            switch (q.getOrDefault("cmd", "vote")) {
                case "cosmetics" -> v.openCosmetics(r);
                case "links" -> { v.links(r); r.closed = true; }
                case "top" -> { v.top(r); r.closed = true; }
                default -> v.open(r);
            }
        } else {
            Votes.Menu m = open.get(uuid);
            if (m == null) { r.closed = true; }
            else {
                Inventory before = m.inv;
                v.click(r, m, Integer.parseInt(q.getOrDefault("slot", "-1")), "1".equals(q.get("shift")));
                if (r.opened == null && !r.closed) r.opened = before;   // nothing new: keep showing the same menu
            }
        }
        JsonObject out = new JsonObject();
        if (r.opened != null && r.opened.getHolder() instanceof Votes.Menu m) {
            open.put(uuid, m);
            JsonObject o = new JsonObject();
            o.add("title", JsonParser.parseString(GsonComponentSerializer.gson().serialize(m.title == null ? Component.empty() : m.title)));
            o.addProperty("rows", m.inv.getSize() / 9);
            JsonArray items = new JsonArray();
            for (int i = 0; i < m.inv.getSize(); i++) {
                ItemStack it = m.inv.getItem(i);
                if (it == null || it.getType().isAir()) continue;
                JsonObject e = new JsonObject();
                e.addProperty("slot", i);
                e.add("item", Bukkit.getUnsafe().serializeItemAsJson(it));
                e.add("simple", simple(it));   // for older servers (Factions, 1.21.11), which can't read a newer item
                items.add(e);
            }
            o.add("items", items);
            out.add("open", o);
        } else open.remove(uuid);
        out.addProperty("close", r.opened == null);
        JsonArray msgs = new JsonArray();
        for (Component c : r.messages) msgs.add(JsonParser.parseString(GsonComponentSerializer.gson().serialize(c)));
        out.add("messages", msgs);
        JsonArray sounds = new JsonArray();
        for (Object[] s : r.sounds) {
            JsonObject so = new JsonObject();
            so.addProperty("id", ((Sound) s[0]).getKey().toString());
            so.addProperty("volume", (Float) s[1]);
            so.addProperty("pitch", (Float) s[2]);
            sounds.add(so);
        }
        out.add("sounds", sounds);
        if (r.connect != null) out.addProperty("connect", r.connect);
        return out;
    }

    /** Material, name, lore, glint and head texture: enough to rebuild a menu icon on any version. */
    static JsonObject simple(ItemStack it) {
        JsonObject o = new JsonObject();
        o.addProperty("id", it.getType().getKey().toString());
        var meta = it.getItemMeta();
        if (meta == null) return o;
        if (meta.hasDisplayName()) o.add("name", JsonParser.parseString(GsonComponentSerializer.gson().serialize(meta.displayName())));
        JsonArray lore = new JsonArray();
        if (meta.lore() != null) for (Component l : meta.lore()) lore.add(JsonParser.parseString(GsonComponentSerializer.gson().serialize(l)));
        o.add("lore", lore);
        if (meta.hasEnchantmentGlintOverride() && meta.getEnchantmentGlintOverride()) o.addProperty("glint", true);
        if (meta instanceof org.bukkit.inventory.meta.SkullMeta sm && sm.getPlayerProfile() != null)
            for (var prop : sm.getPlayerProfile().getProperties()) if (prop.getName().equals("textures")) o.addProperty("head", prop.getValue());
        return o;
    }

    /** The remote player closed the menu (or left their server). */
    void forget(UUID uuid) { open.remove(uuid); }
}

package crispy.chattags;

import com.google.gson.JsonElement;
import com.google.gson.JsonObject;
import com.google.gson.JsonParser;
import net.kyori.adventure.text.Component;
import net.kyori.adventure.text.format.NamedTextColor;
import net.kyori.adventure.text.serializer.gson.GsonComponentSerializer;
import org.bukkit.Bukkit;
import org.bukkit.entity.Player;
import org.bukkit.event.EventHandler;
import org.bukkit.event.EventPriority;
import org.bukkit.event.Listener;
import org.bukkit.event.inventory.InventoryClickEvent;
import org.bukkit.event.inventory.InventoryCloseEvent;
import org.bukkit.event.inventory.InventoryDragEvent;
import org.bukkit.event.player.PlayerCommandPreprocessEvent;
import org.bukkit.inventory.Inventory;
import org.bukkit.inventory.InventoryHolder;
import org.bukkit.inventory.ItemStack;
import org.bukkit.plugin.java.JavaPlugin;

import java.net.URI;
import java.net.URLEncoder;
import java.net.http.HttpClient;
import java.net.http.HttpRequest;
import java.net.http.HttpResponse;
import java.nio.charset.StandardCharsets;
import java.nio.file.Files;
import java.nio.file.Path;
import java.time.Duration;
import java.util.Locale;

/**
 * /vote and /cosmetics right here (Factions): the lobby's CrispyLobby builds the menu (RemoteMenus, localhost HTTP)
 * and this draws it as a chest (from the reply's "simple" items: this server is older than the lobby), sends clicks
 * back and shows what comes back. Takes the commands over before other
 * plugins (CrispyFactions has its own /vote), like the proxy used to. Off where CrispyLobby itself runs (the lobby).
 * Not while combat-tagged (crispy_combat.json, written by CrispyFactions). Port: config remote-menus-port (25599).
 */
final class RemoteMenu implements Listener {
    private final JavaPlugin plugin;
    private final String base;
    private final HttpClient http = HttpClient.newBuilder().connectTimeout(Duration.ofSeconds(2)).build();

    static final class Holder implements InventoryHolder {
        final int rows; final Component title; Inventory inv;
        Holder(int rows, Component title) { this.rows = rows; this.title = title; }
        @Override public Inventory getInventory() { return inv; }
    }

    RemoteMenu(JavaPlugin plugin) {
        this.plugin = plugin;
        base = "http://127.0.0.1:" + plugin.getConfig().getInt("remote-menus-port", 25599);
    }

    @EventHandler(priority = EventPriority.LOWEST)
    public void onCommand(PlayerCommandPreprocessEvent e) {
        String[] a = e.getMessage().substring(1).trim().toLowerCase(Locale.ROOT).split("\\s+");
        String cmd;
        if (a[0].equals("cosmetics")) cmd = "cosmetics";
        else if (a[0].equals("vote") || a[0].equals("votes")) cmd = a.length > 1 && (a[1].equals("links") || a[1].equals("top")) ? a[1] : "vote";
        else return;
        e.setCancelled(true);
        Player p = e.getPlayer();
        if (inCombat(p.getName())) { p.sendMessage(Component.text("You can't use /" + a[0] + " in combat.", NamedTextColor.RED)); return; }
        request(p, "/open?cmd=" + cmd);
    }

    private boolean inCombat(String name) {
        try {
            JsonObject o = JsonParser.parseString(Files.readString(Path.of("crispy_combat.json"))).getAsJsonObject();
            JsonElement u = o.get(name.toLowerCase(Locale.ROOT));
            return u != null && u.getAsLong() > System.currentTimeMillis();
        } catch (Exception ignored) { return false; }
    }

    void request(Player p, String pathAndQuery) {
        String sep = pathAndQuery.contains("?") ? "&" : "?";
        String url = base + pathAndQuery + sep + "uuid=" + p.getUniqueId() + "&name=" + URLEncoder.encode(p.getName(), StandardCharsets.UTF_8);
        http.sendAsync(HttpRequest.newBuilder(URI.create(url)).timeout(Duration.ofSeconds(6)).GET().build(), HttpResponse.BodyHandlers.ofString())
                .whenComplete((res, err) -> Bukkit.getScheduler().runTask(plugin, () -> {
                    if (!p.isOnline()) return;
                    if (err != null || res.statusCode() != 200) {
                        p.sendMessage(Component.text("Vote and cosmetics menus are unavailable right now (the lobby isn't answering). Try again soon.", NamedTextColor.RED));
                        if (p.getOpenInventory().getTopInventory().getHolder() instanceof Holder) p.closeInventory();
                        return;
                    }
                    apply(p, JsonParser.parseString(res.body()).getAsJsonObject());
                }));
    }

    private void apply(Player p, JsonObject r) {
        for (JsonElement m : r.getAsJsonArray("messages")) p.sendMessage(GsonComponentSerializer.gson().deserializeFromTree(m));
        for (JsonElement s : r.getAsJsonArray("sounds")) {
            JsonObject so = s.getAsJsonObject();
            p.playSound(p.getLocation(), so.get("id").getAsString(), so.get("volume").getAsFloat(), so.get("pitch").getAsFloat());
        }
        Inventory top = p.getOpenInventory().getTopInventory();
        if (!r.has("open")) { if (top.getHolder() instanceof Holder) p.closeInventory(); return; }
        JsonObject o = r.getAsJsonObject("open");
        int rows = Math.max(1, Math.min(6, o.get("rows").getAsInt()));
        Component title = GsonComponentSerializer.gson().deserializeFromTree(o.get("title"));
        ItemStack[] items = new ItemStack[rows * 9];
        for (JsonElement e : o.getAsJsonArray("items")) {
            JsonObject eo = e.getAsJsonObject();
            int slot = eo.get("slot").getAsInt();
            if (slot < 0 || slot >= items.length) continue;
            items[slot] = build(eo.getAsJsonObject("simple"));
        }
        // same size and title: refresh in place (keeps the cursor still); otherwise open the new menu
        if (top.getHolder() instanceof Holder h && h.rows == rows && h.title.equals(title)) { top.setContents(items); return; }
        Holder h = new Holder(rows, title);
        h.inv = Bukkit.createInventory(h, rows * 9, title);
        h.inv.setContents(items);
        p.openInventory(h.inv);
    }

    /** The lobby's "simple" item (material, name, lore, glint, head texture): this server may be an older version. */
    static ItemStack build(JsonObject o) {
        if (o == null) return null;
        org.bukkit.Material m = org.bukkit.Material.matchMaterial(o.get("id").getAsString());
        ItemStack it = new ItemStack(m == null || !m.isItem() ? org.bukkit.Material.PAPER : m);
        var meta = it.getItemMeta();
        if (meta == null) return it;
        if (o.has("name")) meta.displayName(GsonComponentSerializer.gson().deserializeFromTree(o.get("name")));
        if (o.has("lore")) {
            java.util.List<Component> lore = new java.util.ArrayList<>();
            for (JsonElement l : o.getAsJsonArray("lore")) lore.add(GsonComponentSerializer.gson().deserializeFromTree(l));
            meta.lore(lore);
        }
        if (o.has("glint")) meta.setEnchantmentGlintOverride(true);
        meta.addItemFlags(org.bukkit.inventory.ItemFlag.values());
        if (o.has("head") && meta instanceof org.bukkit.inventory.meta.SkullMeta sm) {
            var prof = Bukkit.createProfile(java.util.UUID.nameUUIDFromBytes(o.get("head").getAsString().getBytes()), "crispy");
            prof.setProperty(new com.destroystokyo.paper.profile.ProfileProperty("textures", o.get("head").getAsString()));
            sm.setPlayerProfile(prof);
        }
        it.setItemMeta(meta);
        return it;
    }

    @EventHandler public void onClick(InventoryClickEvent e) {
        if (!(e.getView().getTopInventory().getHolder() instanceof Holder h) || !(e.getWhoClicked() instanceof Player p)) return;
        e.setCancelled(true);
        if (e.getClickedInventory() != e.getView().getTopInventory() || e.getRawSlot() >= h.rows * 9) return;
        request(p, "/click?slot=" + e.getRawSlot() + "&shift=" + (e.isShiftClick() ? 1 : 0));
    }

    @EventHandler public void onDrag(InventoryDragEvent e) { if (e.getView().getTopInventory().getHolder() instanceof Holder) e.setCancelled(true); }

    @EventHandler public void onClose(InventoryCloseEvent e) {
        if (!(e.getInventory().getHolder() instanceof Holder) || !(e.getPlayer() instanceof Player p)) return;
        Bukkit.getScheduler().runTask(plugin, () -> {   // not when it was just replaced by the next menu
            if (p.isOnline() && p.getOpenInventory().getTopInventory().getHolder() instanceof Holder) return;
            http.sendAsync(HttpRequest.newBuilder(URI.create(base + "/close?uuid=" + p.getUniqueId())).timeout(Duration.ofSeconds(3)).GET().build(),
                    HttpResponse.BodyHandlers.discarding());
        });
    }
}

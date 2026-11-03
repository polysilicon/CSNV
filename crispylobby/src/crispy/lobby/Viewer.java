package crispy.lobby;

import net.kyori.adventure.text.Component;
import org.bukkit.Sound;
import org.bukkit.command.CommandSender;
import org.bukkit.entity.Player;
import org.bukkit.inventory.Inventory;

import java.util.ArrayList;
import java.util.List;
import java.util.UUID;

/**
 * Whoever a /vote or /cosmetics menu is for. Local: a player (or the console) here on the lobby, served as before.
 * Remote: a player on another server (RemoteMenus); what the menu code "shows" them is collected and sent back to that
 * server, which draws the chest menu itself and sends clicks back here.
 */
interface Viewer {
    String getName();
    UUID getUniqueId();
    boolean hasPermission(String perm);
    void sendMessage(Component c);
    void playSound(Sound s, float volume, float pitch);
    void openInventory(Inventory inv);
    void closeInventory();

    record Local(CommandSender sender) implements Viewer {
        Player player() { return sender instanceof Player p ? p : null; }
        public String getName() { return sender.getName(); }
        public UUID getUniqueId() { return sender instanceof Player p ? p.getUniqueId() : new UUID(0, 0); }
        public boolean hasPermission(String perm) { return sender.hasPermission(perm); }
        public void sendMessage(Component c) { sender.sendMessage(c); }
        public void playSound(Sound s, float v, float p) { if (sender instanceof Player pl) pl.playSound(pl.getLocation(), s, v, p); }
        public void openInventory(Inventory inv) { if (sender instanceof Player pl) pl.openInventory(inv); }
        public void closeInventory() { if (sender instanceof Player pl) pl.closeInventory(); }
    }

    /** A player on another server: everything is recorded for the response. */
    final class Remote implements Viewer {
        final String name; final UUID uuid;
        final List<Component> messages = new ArrayList<>();
        final List<Object[]> sounds = new ArrayList<>();   // {Sound, volume, pitch}
        Inventory opened; boolean closed; String connect;
        Remote(String name, UUID uuid) { this.name = name; this.uuid = uuid; }
        public String getName() { return name; }
        public UUID getUniqueId() { return uuid; }
        public boolean hasPermission(String perm) { return false; }   // staff tools stay in the lobby
        public void sendMessage(Component c) { messages.add(c); }
        public void playSound(Sound s, float v, float p) { sounds.add(new Object[]{s, v, p}); }
        public void openInventory(Inventory inv) { opened = inv; closed = false; }
        public void closeInventory() { opened = null; closed = true; }
    }
}

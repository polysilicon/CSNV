package crispy.lobby;

import net.kyori.adventure.text.Component;
import org.bukkit.Bukkit;
import org.bukkit.GameMode;
import org.bukkit.Location;
import org.bukkit.Color;
import org.bukkit.entity.Display;
import org.bukkit.entity.Player;
import org.bukkit.entity.TextDisplay;
import org.bukkit.event.EventHandler;
import org.bukkit.event.Listener;
import org.bukkit.event.player.PlayerJoinEvent;
import org.bukkit.event.player.PlayerQuitEvent;
import org.bukkit.potion.PotionEffectType;
import org.bukkit.util.Transformation;
import org.joml.AxisAngle4f;
import org.joml.Vector3f;

import java.io.IOException;
import java.nio.file.Files;
import java.nio.file.Path;
import java.util.HashMap;
import java.util.HashSet;
import java.util.Locale;
import java.util.Map;
import java.util.Objects;
import java.util.Set;
import java.util.UUID;

/**
 * Your own name tag, so you can see it in third person (the game never draws your own).
 * Each player gets a text display with their name (in their cosmetic name colour) and their cosmetic tag, shown to
 * them only (everyone else sees the normal name tag). It follows them every tick instead of riding them: a player
 * with a passenger can't be teleported by plugins (spawn, portals, launch pads). Teleport interpolation smooths it.
 * /owntag turns it off or on (saved in owntag-off.txt). Hidden while invisible or in spectator.
 */
final class OwnTag implements Listener {
    static final double HEIGHT = 2.1;   // above the feet: where the game puts a player's name tag
    private final CrispyLobby plugin;
    private final Map<UUID, TextDisplay> tags = new HashMap<>();
    private final Map<UUID, String> shown = new HashMap<>();
    private final Set<String> off = new HashSet<>();
    private final Path offFile;
    private int tick;

    OwnTag(CrispyLobby plugin) {
        this.plugin = plugin;
        offFile = plugin.getDataFolder().toPath().resolve("owntag-off.txt");
        try {
            if (Files.exists(offFile)) for (String l : Files.readAllLines(offFile)) if (!l.isBlank()) off.add(l.trim().toLowerCase(Locale.ROOT));
        } catch (IOException e) { plugin.getLogger().warning("owntag-off.txt read failed: " + e); }
    }

    void start() {
        Bukkit.getScheduler().runTaskTimer(plugin, this::tick, 20L, 1L);
    }

    void stop() {
        tags.values().forEach(d -> { if (d.isValid()) d.remove(); });
        tags.clear(); shown.clear();
    }

    private boolean wants(Player p) {
        return !off.contains(p.getName().toLowerCase(Locale.ROOT)) && p.getGameMode() != GameMode.SPECTATOR
                && !p.hasPotionEffect(PotionEffectType.INVISIBILITY) && !p.isDead();
    }

    private void tick() {
        tick++;
        for (Player p : Bukkit.getOnlinePlayers()) {
            TextDisplay d = tags.get(p.getUniqueId());
            if (!wants(p)) { remove(p.getUniqueId()); continue; }
            Location at = p.getLocation().add(0, HEIGHT, 0);
            if (d == null || !d.isValid() || d.getWorld() != p.getWorld()) {
                remove(p.getUniqueId());
                d = spawn(p, at);
                continue;
            }
            d.teleport(at);
            if (tick % 40 == 0) text(p, d);   // pick up a new name colour or tag
        }
        tags.keySet().removeIf(u -> {   // anyone who left without a quit event
            if (Bukkit.getPlayer(u) != null) return false;
            TextDisplay d = tags.get(u); if (d != null && d.isValid()) d.remove();
            shown.remove(u); return true;
        });
    }

    private TextDisplay spawn(Player p, Location at) {
        TextDisplay d = p.getWorld().spawn(at, TextDisplay.class, e -> {
            e.setPersistent(false);
            e.setVisibleByDefault(false);   // only its owner sees it
            e.setBillboard(Display.Billboard.CENTER);
            e.setBackgroundColor(Color.fromARGB(64, 0, 0, 0));   // like the game's name tag
            e.setShadowed(false);
            e.setSeeThrough(false);
            e.setTeleportDuration(2);
            e.setTransformation(new Transformation(new Vector3f(), new AxisAngle4f(), new Vector3f(1, 1, 1), new AxisAngle4f()));
        });
        p.showEntity(plugin, d);
        tags.put(p.getUniqueId(), d);
        shown.remove(p.getUniqueId());
        text(p, d);
        return d;
    }

    private void text(Player p, TextDisplay d) {
        String key = p.getName().toLowerCase(Locale.ROOT);
        Votes v = plugin.votes;
        String name = p.getName(), tag = null;
        Votes.PD pd = v == null ? null : v.players.get(key);
        if (pd != null) {
            Votes.NameColor c = pd.color == null ? null : v.colors.get(pd.color);
            if (c != null) name = Votes.colored(p.getName(), c.code());
            Votes.Tag t = pd.tag == null ? null : v.tags.get(pd.tag);
            if (t != null) tag = t.display();
        }
        String line = (pd != null && pd.color != null && v.colors.get(pd.color) != null ? name : "&f" + name) + (tag == null ? "" : " &r" + tag);
        if (Objects.equals(shown.get(p.getUniqueId()), line)) return;
        shown.put(p.getUniqueId(), line);
        d.text(CrispyLobby.AMP.deserialize(line));
    }

    private void remove(UUID u) {
        TextDisplay d = tags.remove(u);
        shown.remove(u);
        if (d != null && d.isValid()) d.remove();
    }

    @EventHandler public void onQuit(PlayerQuitEvent e) { remove(e.getPlayer().getUniqueId()); }

    @EventHandler public void onJoin(PlayerJoinEvent e) { remove(e.getPlayer().getUniqueId()); }   // spawned on the next tick

    /** /owntag: turn your own floating name tag off or on. */
    boolean command(org.bukkit.command.CommandSender s) {
        if (!(s instanceof Player p)) { s.sendMessage("Run /owntag in game."); return true; }
        String key = p.getName().toLowerCase(Locale.ROOT);
        boolean nowOff = off.add(key);
        if (!nowOff) off.remove(key);
        if (nowOff) remove(p.getUniqueId());
        try { Files.write(offFile, off); } catch (IOException e) { plugin.getLogger().warning("owntag-off.txt write failed: " + e); }
        p.sendMessage(CrispyLobby.AMP.deserialize(nowOff ? "&7Your own name tag is now &chidden&7. /owntag to show it again."
                : "&7Your own name tag is now &ashown&7 (third person, F5). /owntag to hide it."));
        return true;
    }
}

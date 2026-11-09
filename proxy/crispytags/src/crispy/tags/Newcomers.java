package crispy.tags;

import com.velocitypowered.api.event.Subscribe;
import com.velocitypowered.api.event.connection.PostLoginEvent;
import com.velocitypowered.api.event.player.ServerPostConnectEvent;
import com.velocitypowered.api.proxy.Player;
import net.kyori.adventure.text.Component;
import net.kyori.adventure.text.event.ClickEvent;
import net.kyori.adventure.text.event.HoverEvent;
import net.kyori.adventure.text.format.NamedTextColor;
import net.kyori.adventure.text.format.TextDecoration;

import java.nio.file.Files;
import java.nio.file.Path;
import java.util.Map;
import java.util.Set;
import java.util.UUID;
import java.util.concurrent.ConcurrentHashMap;
import java.util.concurrent.TimeUnit;

/**
 * First join to the network, wherever it lands (1.10.0). With per-mode addresses (skyblock.crispyanarchy.net etc.,
 * velocity.toml forced-hosts) new players can skip the lobby and its welcome, so the proxy greets them instead:
 * a short welcome with the other modes, Discord and vote links, and a line to everyone else online so they say hi.
 * Players who land in the lobby are left to the lobby's own welcome (CrispyLobby Welcome), so nobody gets two.
 *
 * "New" = no saved player file for their UUID on any server (the same files the backends write), checked at login,
 * before any backend has saved them.
 */
final class Newcomers {
    static final String[] INSTANCES = {"CrispyLobby01", "CrispyAnarchy01", "Vanilla01", "CrispyPvP01", "Factions01", "Falling01"};
    static final String[] DATA = {"Minecraft/world/players/data", "Minecraft/world/playerdata"};
    static final Map<String, String> MODE = Map.of("anarchy", "Anarchy", "skyblock", "Skyblock", "multiverse", "the Multiverse",
            "factions", "Factions", "vanilla", "Vanilla");
    static final String DISCORD = "https://discord.gg/hF2bQgU";

    final CrispyTags plugin;
    final Set<UUID> pending = ConcurrentHashMap.newKeySet();   // new this login, not greeted yet
    final Set<UUID> greeted = ConcurrentHashMap.newKeySet();   // greeted since the proxy started (no repeat before their file is saved)

    Newcomers(CrispyTags plugin) { this.plugin = plugin; }

    static boolean known(UUID u) {
        for (String inst : INSTANCES)
            for (String d : DATA)
                if (Files.exists(CrispyTags.INSTANCES.resolve(inst).resolve(d).resolve(u + ".dat"))) return true;
        return false;
    }

    @Subscribe public void onLogin(PostLoginEvent e) {
        UUID u = e.getPlayer().getUniqueId();
        if (greeted.contains(u)) return;
        try { if (!known(u)) pending.add(u); }
        catch (Exception ex) { /* can't tell: treat as known, never greet a regular by mistake */ }
    }

    @Subscribe public void onPostConnect(ServerPostConnectEvent e) {
        if (e.getPreviousServer() != null) return;
        Player p = e.getPlayer();
        if (!pending.remove(p.getUniqueId())) return;
        greeted.add(p.getUniqueId());
        String server = p.getCurrentServer().map(c -> c.getServerInfo().getName()).orElse("");
        if (server.equalsIgnoreCase(CrispyTags.LOBBY)) return;   // the lobby welcomes its own
        String mode = MODE.getOrDefault(server.toLowerCase(), server);
        plugin.proxy.getScheduler().buildTask(plugin, () -> {
            if (!p.isActive()) return;
            p.sendMessage(Component.text()
                    .append(Component.text("✦ Welcome to Crispy, ", NamedTextColor.GOLD, TextDecoration.BOLD))
                    .append(Component.text(p.getUsername() + "!", NamedTextColor.YELLOW, TextDecoration.BOLD))
                    .append(Component.text(" You're on " + mode + ".", NamedTextColor.GRAY))
                    .build());
            p.sendMessage(Component.text()
                    .append(Component.text("  We also have Anarchy, Skyblock, the Multiverse, Factions and Vanilla. ", NamedTextColor.GRAY))
                    .append(link("[Other modes]", NamedTextColor.AQUA, ClickEvent.runCommand("/lobby"), "Go to the lobby to pick another mode"))
                    .append(Component.text("  "))
                    .append(link("[Discord]", NamedTextColor.BLUE, ClickEvent.openUrl(DISCORD), "Join the Discord"))
                    .append(Component.text("  "))
                    .append(link("[Vote rewards]", NamedTextColor.LIGHT_PURPLE, ClickEvent.runCommand("/vote"), "Free rewards for voting"))
                    .build());
            Component hi = Component.text()
                    .append(Component.text("✦ ", NamedTextColor.GOLD))
                    .append(Component.text(p.getUsername(), NamedTextColor.YELLOW))
                    .append(Component.text(" just joined Crispy for the first time, on " + mode + ". Say hi!", NamedTextColor.GOLD))
                    .build();
            for (Player o : plugin.proxy.getAllPlayers()) if (!o.equals(p)) o.sendMessage(hi);
            plugin.proxy.getConsoleCommandSource().sendMessage(hi);
        }).delay(3, TimeUnit.SECONDS).schedule();
    }

    static Component link(String label, NamedTextColor color, ClickEvent click, String hover) {
        return Component.text(label, color, TextDecoration.UNDERLINED).clickEvent(click)
                .hoverEvent(HoverEvent.showText(Component.text(hover, NamedTextColor.GRAY)));
    }
}

package crispy.tags;

import com.velocitypowered.api.event.PostOrder;
import com.velocitypowered.api.event.Subscribe;
import com.velocitypowered.api.event.player.PlayerChooseInitialServerEvent;
import com.velocitypowered.api.event.player.ServerPostConnectEvent;
import com.velocitypowered.api.event.player.ServerPreConnectEvent;
import com.velocitypowered.api.proxy.Player;
import com.velocitypowered.api.proxy.server.RegisteredServer;
import com.velocitypowered.proxy.connection.client.ConnectedPlayer;
import io.netty.channel.Channel;
import net.kyori.adventure.text.Component;
import net.kyori.adventure.text.format.NamedTextColor;

import java.util.Optional;
import java.util.concurrent.TimeUnit;

/**
 * 1.13.0: Crispymon (the Cobblemon modpack server) behind the proxy. A modpack client changes vanilla blocks' IDs, so
 * on the network's vanilla servers it sees garbled blocks; a vanilla client can't join Crispymon at all (missing mods).
 * So: a modpack client (ChannelCap spots Cobblemon's channels) is sent to crispymon whichever address it used (via
 * crispymon.org it lands there directly, via crispyanarchy.net it's moved there as soon as it's recognised), and can't
 * /server to the vanilla servers; a vanilla client can't go to crispymon. Server name: -Dcrispytags.modpackServer.
 */
final class Modpack {
    static final String MARKER = "cobblemon:";
    static final String SERVER = System.getProperty("crispytags.modpackServer", "crispymon");
    final CrispyTags plugin;
    Modpack(CrispyTags plugin) { this.plugin = plugin; }

    static boolean is(Player p) {
        if (confirmed.contains(p.getUniqueId()) || candidate.contains(p.getUniqueId())) return true;
        if (!(p instanceof ConnectedPlayer cp)) return false;
        return cp.getConnection().getChannel().pipeline().get("crispy-channel-cap") instanceof ChannelCap.Cap c && c.modpack;
    }

    Optional<RegisteredServer> target() { return plugin.proxy.getServer(SERVER); }

    /** Called from the netty thread as soon as the client registers Cobblemon's channels: if it's already on another
     *  server (it joined through crispyanarchy.net and is in the lobby), move it now. */
    static void detected(CrispyTags plugin, Channel ch) {
        plugin.proxy.getScheduler().buildTask(plugin, () -> {
            for (Player p : plugin.proxy.getAllPlayers())
                if (p instanceof ConnectedPlayer cp && cp.getConnection().getChannel() == ch) { plugin.modpack.reroute(p); return; }
        }).delay(1, TimeUnit.SECONDS).schedule();
    }

    void reroute(Player p) {
        String on = p.getCurrentServer().map(c -> c.getServerInfo().getName()).orElse(null);
        if (on == null || on.equalsIgnoreCase(SERVER)) return;
        target().ifPresentOrElse(t -> {
            p.sendMessage(Component.text("You're on the Crispymon modpack: taking you to Crispymon...", NamedTextColor.GREEN));
            p.createConnectionRequest(t).fireAndForget();
        }, () -> plugin.log.warn("[modpack] no server named {} to send {} to", SERVER, p.getUsername()));
    }

    // 1.13.5: against a vanilla server (the lobby) the modpack client sends no plugin channels at all (2026-11-21 test:
    // 83 s in the lobby, none), so the only thing to go on there is brand "fabric" + protocol 1.21(.1), the pack's
    // version. Such a client is a *candidate* and is moved to crispymon. If it gets in, it's a confirmed modpack client.
    // A Fabric 1.21.1 player WITHOUT the pack is dropped by Crispymon's registry check (missing mods): if a candidate
    // disconnects without ever reaching crispymon, it's remembered as not-the-pack and never moved again (no loop).
    static final java.util.Set<java.util.UUID> candidate = java.util.concurrent.ConcurrentHashMap.newKeySet();
    static final java.util.Set<java.util.UUID> confirmed = java.util.concurrent.ConcurrentHashMap.newKeySet();
    static final java.util.Set<java.util.UUID> notPack = java.util.concurrent.ConcurrentHashMap.newKeySet();

    @Subscribe public void onBrand(com.velocitypowered.api.event.player.PlayerClientBrandEvent e) {
        Player p = e.getPlayer();
        String brand = e.getBrand() == null ? "" : e.getBrand().toLowerCase(java.util.Locale.ROOT);
        if (!brand.contains("fabric") || p.getProtocolVersion() != com.velocitypowered.api.network.ProtocolVersion.MINECRAFT_1_21) return;
        if (notPack.contains(p.getUniqueId()) || is(p)) return;
        candidate.add(p.getUniqueId());
        plugin.log.info("[modpack] {} looks like the Crispymon modpack (Fabric, 1.21.x): moving to {}", p.getUsername(), SERVER);
        plugin.proxy.getScheduler().buildTask(plugin, () -> { if (p.isActive()) reroute(p); }).delay(1, TimeUnit.SECONDS).schedule();
    }

    @Subscribe public void onDisconnect(com.velocitypowered.api.event.connection.DisconnectEvent e) {
        java.util.UUID id = e.getPlayer().getUniqueId();
        if (candidate.remove(id) && !confirmed.contains(id)) {
            notPack.add(id);
            plugin.log.info("[modpack] {} never got into {}: not the modpack, won't move them again", e.getPlayer().getUsername(), SERVER);
        }
    }

    /** A modpack client whose channels arrived before the first server was picked goes straight to crispymon. */
    @Subscribe(order = PostOrder.LATE) public void onChoose(PlayerChooseInitialServerEvent e) {
        if (is(e.getPlayer())) target().ifPresent(e::setInitialServer);
    }

    /** Otherwise as soon as it lands anywhere else. */
    @Subscribe public void onPostConnect(ServerPostConnectEvent e) {
        Player p = e.getPlayer();
        if (p.getCurrentServer().map(c -> c.getServerInfo().getName().equalsIgnoreCase(SERVER)).orElse(false)) {
            confirmed.add(p.getUniqueId()); notPack.remove(p.getUniqueId()); return;   // it's on crispymon: a modpack client
        }
        if (is(p)) plugin.proxy.getScheduler().buildTask(plugin, () -> { if (p.isActive()) reroute(p); }).delay(500, TimeUnit.MILLISECONDS).schedule();
    }

    /** Keep each kind of client where it works when they switch servers. */
    @Subscribe(order = PostOrder.EARLY) public void onPreConnect(ServerPreConnectEvent e) {
        Player p = e.getPlayer();
        String to = e.getOriginalServer().getServerInfo().getName();
        boolean toModpack = to.equalsIgnoreCase(SERVER);
        // Only switches are checked. The first connection is always let through: the client's channels (how a modpack is
        // recognised) arrive after the first server is picked, so a modpack player joining crispymon.org would look
        // vanilla here and be stuck with no server (2026-11-21 first test). A vanilla client joining crispymon.org is
        // turned away by Crispymon itself (missing mods); a modpack client landing in the lobby is moved by onPostConnect.
        if (e.getPreviousServer() == null) return;
        if (toModpack && !is(p)) {
            e.setResult(ServerPreConnectEvent.ServerResult.denied());
            p.sendMessage(Component.text("Crispymon needs the Crispymon modpack (search \"Crispymon\" on CurseForge), then join crispymon.org.", NamedTextColor.RED));
        } else if (!toModpack && is(p)) {
            e.setResult(ServerPreConnectEvent.ServerResult.denied());
            p.sendMessage(Component.text("The other Crispy servers are vanilla: blocks show up wrong with the modpack. Use a vanilla profile to play them.", NamedTextColor.RED));
        }
    }
}

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

    /** A modpack client whose channels arrived before the first server was picked goes straight to crispymon. */
    @Subscribe(order = PostOrder.LATE) public void onChoose(PlayerChooseInitialServerEvent e) {
        if (is(e.getPlayer())) target().ifPresent(e::setInitialServer);
    }

    /** Otherwise as soon as it lands anywhere else. */
    @Subscribe public void onPostConnect(ServerPostConnectEvent e) {
        Player p = e.getPlayer();
        if (is(p)) plugin.proxy.getScheduler().buildTask(plugin, () -> { if (p.isActive()) reroute(p); }).delay(500, TimeUnit.MILLISECONDS).schedule();
    }

    /** Keep each kind of client where it works. The first connection is let through (the modpack isn't recognised yet
     *  for a moment; it's moved right after). */
    @Subscribe(order = PostOrder.EARLY) public void onPreConnect(ServerPreConnectEvent e) {
        Player p = e.getPlayer();
        String to = e.getOriginalServer().getServerInfo().getName();
        boolean toModpack = to.equalsIgnoreCase(SERVER);
        if (toModpack && !is(p)) {
            e.setResult(ServerPreConnectEvent.ServerResult.denied());
            p.sendMessage(Component.text("Crispymon needs the Crispymon modpack (search \"Crispymon\" on CurseForge), then join crispymon.org.", NamedTextColor.RED));
        } else if (!toModpack && is(p) && e.getPreviousServer() != null) {
            e.setResult(ServerPreConnectEvent.ServerResult.denied());
            p.sendMessage(Component.text("The other Crispy servers are vanilla: blocks show up wrong with the modpack. Use a vanilla profile to play them.", NamedTextColor.RED));
        }
    }
}

package crispy.tags;

import com.velocitypowered.api.event.PostOrder;
import com.velocitypowered.api.event.Subscribe;
import com.velocitypowered.api.event.proxy.ProxyPingEvent;
import com.velocitypowered.api.util.Favicon;

import java.nio.file.Files;
import java.nio.file.Path;
import java.util.Locale;

/**
 * 1.13.2: the server-list icon for crispymon.org. MiniMOTD (extra-configs/crispymon.conf) sets that address's text and
 * player count, but it picks icons from one shared folder (its "random" would mix Crispymon's into the network's), so
 * its icon is off for Crispymon and this sets plugins/crispytags/crispymon-icon.png instead, after MiniMOTD has run.
 */
final class HostIcon {
    final CrispyTags plugin;
    Favicon icon;
    HostIcon(CrispyTags plugin) {
        this.plugin = plugin;
        Path p = Path.of(System.getProperty("crispytags.hostIcon", "plugins/crispytags/crispymon-icon.png"));   // relative to the proxy
        try { if (Files.exists(p)) icon = Favicon.create(p); else plugin.log.warn("[icon] no {}", p); }
        catch (Exception e) { plugin.log.warn("[icon] couldn't load {}: {}", p, e.toString()); }
    }

    @Subscribe(order = PostOrder.LAST) public void onPing(ProxyPingEvent e) {
        if (icon == null) return;
        String host = e.getConnection().getVirtualHost().map(a -> a.getHostString().toLowerCase(Locale.ROOT)).orElse("");
        if (host.equals("crispymon.org") || host.equals("www.crispymon.org"))
            e.setPing(e.getPing().asBuilder().favicon(icon).build());
    }
}

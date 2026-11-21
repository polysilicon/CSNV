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
    final Path path = Path.of(System.getProperty("crispytags.hostIcon", "plugins/crispytags/crispymon-icon.png"));   // relative to the proxy
    Favicon icon;
    long mtime = -1;
    HostIcon(CrispyTags plugin) { this.plugin = plugin; load(); }

    /** (Re)load the icon when the file changes (1.13.3), so swapping it needs no proxy restart. */
    void load() {
        try {
            long m = Files.exists(path) ? Files.getLastModifiedTime(path).toMillis() : -1;
            if (m == mtime) return;
            mtime = m;
            icon = m < 0 ? null : Favicon.create(path);
            if (m < 0) plugin.log.warn("[icon] no {}", path);
        } catch (Exception e) { plugin.log.warn("[icon] couldn't load {}: {}", path, e.toString()); }
    }

    @Subscribe(order = PostOrder.LAST) public void onPing(ProxyPingEvent e) {
        load();
        if (icon == null) return;
        String host = e.getConnection().getVirtualHost().map(a -> a.getHostString().toLowerCase(Locale.ROOT)).orElse("");
        if (host.equals("crispymon.org") || host.equals("www.crispymon.org"))
            e.setPing(e.getPing().asBuilder().favicon(icon).build());
    }
}

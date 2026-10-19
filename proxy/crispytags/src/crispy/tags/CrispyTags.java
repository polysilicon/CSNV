package crispy.tags;

import com.google.gson.Gson;
import com.google.gson.reflect.TypeToken;
import com.google.inject.Inject;
import com.velocitypowered.api.event.Subscribe;
import com.velocitypowered.api.event.proxy.ProxyInitializeEvent;
import com.velocitypowered.api.proxy.ProxyServer;
import me.neznamy.tab.api.TabAPI;
import me.neznamy.tab.api.TabPlayer;
import me.neznamy.tab.api.nametag.NameTagManager;
import me.neznamy.tab.api.tablist.TabListFormatManager;

import java.nio.file.Files;
import java.nio.file.Path;
import java.util.*;
import java.util.concurrent.TimeUnit;

/** Shows the vote-cosmetic tags bought in the lobby (/cosmetics) after each player's name in the tab list and on
 *  name tags, on every server, through TAB's API. The lobby's CrispyLobby plugin writes name -> tag to tags.json;
 *  this re-reads it every few seconds and keeps TAB's custom suffix in step (TAB placeholders keep working). */
public class CrispyTags {
    static final Path FILE = Path.of(System.getProperty("crispytags.file",
            "/AMPStorage/.ampdata/instances/CrispyLobby01/Minecraft/plugins/CrispyLobby/tags.json"));
    final ProxyServer proxy;
    Map<String, String> tags = Map.of();
    long mtime = -1;

    @Inject public CrispyTags(ProxyServer proxy) { this.proxy = proxy; }

    @Subscribe public void onInit(ProxyInitializeEvent e) {
        proxy.getScheduler().buildTask(this, this::tick).delay(10, TimeUnit.SECONDS).repeat(3, TimeUnit.SECONDS).schedule();
    }

    void tick() {
        try {
            long m = Files.getLastModifiedTime(FILE).toMillis();
            if (m != mtime) {
                Map<String, String> t = new Gson().fromJson(Files.readString(FILE), new TypeToken<Map<String, String>>() {}.getType());
                tags = t == null ? Map.of() : t;
                mtime = m;
            }
        } catch (Exception ignored) {}
        TabAPI api = TabAPI.getInstance();
        if (api == null) return;
        NameTagManager tagMgr = api.getNameTagManager();
        TabListFormatManager listMgr = api.getTabListFormatManager();
        for (TabPlayer p : api.getOnlinePlayers()) {
            if (!p.isLoaded()) continue;
            String tag = tags.get(p.getName().toLowerCase(Locale.ROOT));
            if (listMgr != null) {
                String want = tag == null ? null : join(listMgr.getOriginalRawSuffix(p), tag);
                if (!Objects.equals(listMgr.getCustomSuffix(p), want)) listMgr.setSuffix(p, want);
            }
            if (tagMgr != null) {
                String want = tag == null ? null : join(tagMgr.getOriginalRawSuffix(p), tag);
                if (!Objects.equals(tagMgr.getCustomSuffix(p), want)) tagMgr.setSuffix(p, want);
            }
        }
    }
    static String join(String original, String tag) { return (original == null ? "" : original) + " " + tag; }
}

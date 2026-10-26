package crispy.tags;

import com.google.gson.Gson;
import com.google.gson.reflect.TypeToken;
import com.google.inject.Inject;
import com.velocitypowered.api.event.Subscribe;
import com.velocitypowered.api.event.command.CommandExecuteEvent;
import com.velocitypowered.api.command.SimpleCommand;
import com.velocitypowered.api.event.proxy.ProxyInitializeEvent;
import com.velocitypowered.api.proxy.Player;
import com.velocitypowered.api.proxy.ProxyServer;
import com.velocitypowered.api.proxy.ServerConnection;
import com.velocitypowered.api.proxy.messages.MinecraftChannelIdentifier;
import com.velocitypowered.api.proxy.server.RegisteredServer;
import net.kyori.adventure.text.Component;
import net.kyori.adventure.text.format.NamedTextColor;
import me.neznamy.tab.api.TabAPI;
import me.neznamy.tab.api.TabPlayer;
import me.neznamy.tab.api.nametag.NameTagManager;
import me.neznamy.tab.api.tablist.TabListFormatManager;

import java.nio.charset.StandardCharsets;
import java.nio.file.Files;
import java.nio.file.Path;
import java.util.*;
import java.util.concurrent.TimeUnit;

/** Shows the vote-cosmetic tags bought in the lobby (/cosmetics) after each player's name in the tab list and on
 *  name tags, on every server, through TAB's API. The lobby's CrispyLobby plugin writes name -> tag to tags.json;
 *  this re-reads it every few seconds and keeps TAB's custom suffix in step (TAB placeholders keep working). Bought
 *  name colours (namecolors.json) colour the name in the tab list the same way.
 *  It also owns /vote and /cosmetics on every server: the menus live on the lobby, so the player is sent there
 *  (if not already on it) and the command line is handed to the lobby's CrispyLobby on the crispy:vote channel.
 *  /lobby sends you to the lobby from any server (like /server lobby, but not in combat), and /server <name> is
 *  refused in combat too. */
public class CrispyTags {
    static final Path FILE = Path.of(System.getProperty("crispytags.file",
            "/AMPStorage/.ampdata/instances/CrispyLobby01/Minecraft/plugins/CrispyLobby/tags.json"));
    static final String LOBBY = System.getProperty("crispytags.lobby", "lobby");
    static final Path INSTANCES = Path.of(System.getProperty("crispytags.instances", "/AMPStorage/.ampdata/instances"));
    /** Velocity server name -> AMP instance; each writes Minecraft/crispy_combat.json (name -> epoch ms when out of
     *  combat): the crispy_chattags mod on the Fabric servers, CrispyFactions' combat tag on Factions. */
    static final Map<String, String> INSTANCE = Map.of("og", "CrispyAnarchy01", "vanilla", "Vanilla01", "pvp", "CrispyPvP01",
            "factions", "Factions01", "falling", "Falling01");
    static final MinecraftChannelIdentifier CHANNEL = MinecraftChannelIdentifier.from("crispy:vote");
    final ProxyServer proxy;
    Map<String, String> tags = Map.of();
    long mtime = -1;
    // name colours bought in /cosmetics (the lobby writes namecolors.json next to tags.json): shown in the tab list too
    static final Path COLORS = FILE.resolveSibling("namecolors.json");
    Map<String, String> colors = Map.of();
    long cmtime = -1;

    @Inject public CrispyTags(ProxyServer proxy) { this.proxy = proxy; }

    @Subscribe public void onInit(ProxyInitializeEvent e) {
        proxy.getChannelRegistrar().register(CHANNEL);
        var cm = proxy.getCommandManager();
        cm.register(cm.metaBuilder("vote").plugin(this).build(), new Lobby("vote", List.of("links", "top")));
        cm.register(cm.metaBuilder("cosmetics").plugin(this).build(), new Lobby("cosmetics", List.of()));
        cm.register(cm.metaBuilder("lobby").plugin(this).build(), new ToLobby());
        proxy.getScheduler().buildTask(this, this::tick).delay(10, TimeUnit.SECONDS).repeat(3, TimeUnit.SECONDS).schedule();
    }

    /** Velocity's own /server would be a way out of a fight: refuse it while combat-tagged, like /lobby and /vote. */
    @Subscribe public void onCommand(CommandExecuteEvent e) {
        if (!(e.getCommandSource() instanceof Player p) || !e.getResult().isAllowed()) return;
        String[] a = e.getCommand().trim().split("\\s+");
        if (a.length < 2 || !a[0].equalsIgnoreCase("server")) return;   // bare /server only lists the servers
        long left = p.getCurrentServer().map(c -> combatLeft(c.getServerInfo().getName(), p.getUsername())).orElse(0L);
        if (left <= 0) return;
        e.setResult(CommandExecuteEvent.CommandResult.denied());
        p.sendMessage(Component.text("You can't switch servers in combat (" + (left + 999) / 1000 + "s left).", NamedTextColor.RED));
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
        try {
            long m = Files.getLastModifiedTime(COLORS).toMillis();
            if (m != cmtime) {
                Map<String, String> c = new Gson().fromJson(Files.readString(COLORS), new TypeToken<Map<String, String>>() {}.getType());
                colors = c == null ? Map.of() : c;
                cmtime = m;
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
                String code = colors.get(p.getName().toLowerCase(Locale.ROOT));
                String name = code == null ? null : colored(p.getName(), code);
                if (!Objects.equals(listMgr.getCustomName(p), name)) listMgr.setName(p, name);
            }
            if (tagMgr != null) {
                String want = tag == null ? null : join(tagMgr.getOriginalRawSuffix(p), tag);
                if (!Objects.equals(tagMgr.getCustomSuffix(p), want)) tagMgr.setSuffix(p, want);
            }
        }
    }
    /** /vote or /cosmetics: hand the command line to the lobby, moving the player there first if needed. */
    final class Lobby implements SimpleCommand {
        final String name; final List<String> subs;
        Lobby(String name, List<String> subs) { this.name = name; this.subs = subs; }
        @Override public void execute(Invocation inv) {
            if (!(inv.source() instanceof Player p)) { inv.source().sendMessage(Component.text("Run /" + name + " in game.")); return; }
            byte[] line = (name + (inv.arguments().length > 0 ? " " + String.join(" ", inv.arguments()) : "")).getBytes(StandardCharsets.UTF_8);
            Optional<ServerConnection> cur = p.getCurrentServer();
            if (cur.isPresent() && cur.get().getServerInfo().getName().equalsIgnoreCase(LOBBY)) { cur.get().sendPluginMessage(CHANNEL, line); return; }
            long left = cur.map(c -> combatLeft(c.getServerInfo().getName(), p.getUsername())).orElse(0L);
            if (left > 0) {
                p.sendMessage(Component.text("You can't use /" + name + " in combat (" + (left + 999) / 1000 + "s left).", NamedTextColor.RED));
                return;
            }
            Optional<RegisteredServer> lobby = proxy.getServer(LOBBY);
            if (lobby.isEmpty()) { p.sendMessage(Component.text("The lobby isn't available right now.", NamedTextColor.RED)); return; }
            p.sendMessage(Component.text("Taking you to the lobby for /" + name + "...", NamedTextColor.LIGHT_PURPLE));
            p.createConnectionRequest(lobby.get()).connect().thenAccept(r -> {
                if (!r.isSuccessful()) { p.sendMessage(Component.text("Couldn't reach the lobby, try again in a moment.", NamedTextColor.RED)); return; }
                // give the lobby a moment to finish the join (spawn teleport, hotbar) before the menu opens
                proxy.getScheduler().buildTask(CrispyTags.this, () -> p.getCurrentServer()
                        .filter(s -> s.getServerInfo().getName().equalsIgnoreCase(LOBBY))
                        .ifPresent(s -> s.sendPluginMessage(CHANNEL, line))).delay(1500, TimeUnit.MILLISECONDS).schedule();
            });
        }
        @Override public List<String> suggest(Invocation inv) {
            String a = inv.arguments().length == 0 ? "" : inv.arguments()[0].toLowerCase(Locale.ROOT);
            return inv.arguments().length <= 1 ? subs.stream().filter(x -> x.startsWith(a)).toList() : List.of();
        }
    }
    /** /lobby on every server: the same as /server lobby, but not while combat-tagged (it would be a way out of a fight). */
    final class ToLobby implements SimpleCommand {
        @Override public void execute(Invocation inv) {
            if (!(inv.source() instanceof Player p)) { inv.source().sendMessage(Component.text("Run /lobby in game.")); return; }
            Optional<ServerConnection> cur = p.getCurrentServer();
            if (cur.isPresent() && cur.get().getServerInfo().getName().equalsIgnoreCase(LOBBY)) {
                p.sendMessage(Component.text("You are already in the lobby.", NamedTextColor.GRAY)); return;
            }
            long left = cur.map(c -> combatLeft(c.getServerInfo().getName(), p.getUsername())).orElse(0L);
            if (left > 0) {
                p.sendMessage(Component.text("You can't go to the lobby in combat (" + (left + 999) / 1000 + "s left).", NamedTextColor.RED));
                return;
            }
            Optional<RegisteredServer> lobby = proxy.getServer(LOBBY);
            if (lobby.isEmpty()) { p.sendMessage(Component.text("The lobby isn't available right now.", NamedTextColor.RED)); return; }
            p.createConnectionRequest(lobby.get()).fireAndForget();
        }
    }
    /** Milliseconds until this player is out of combat on that server, 0 if not in combat (or the server has no file). */
    static long combatLeft(String server, String player) {
        String inst = INSTANCE.get(server.toLowerCase(Locale.ROOT));
        if (inst == null) return 0;
        try {
            Map<String, Long> m = new Gson().fromJson(Files.readString(INSTANCES.resolve(inst).resolve("Minecraft/crispy_combat.json")),
                    new TypeToken<Map<String, Long>>() {}.getType());
            Long u = m == null ? null : m.get(player.toLowerCase(Locale.ROOT));
            return u == null ? 0 : Math.max(0, u - System.currentTimeMillis());
        } catch (Exception e) { return 0; }
    }
    /** Same rules as the lobby and chat: a colour code ("&b", "&6&l"), a per-letter sequence ("&c|&6|&e") or "rainbow". */
    static String colored(String name, String code) {
        if ("rainbow".equalsIgnoreCase(code)) code = "&c|&6|&e|&a|&b|&9|&d";
        if (!code.contains("|")) return code + name;
        String[] cyc = code.split("\\|");
        StringBuilder b = new StringBuilder();
        for (int i = 0; i < name.length(); i++) b.append(cyc[i % cyc.length]).append(name.charAt(i));
        return b.toString();
    }
    static String join(String original, String tag) { return (original == null ? "" : original) + " " + tag; }
}

package crispy.tags;

import com.google.gson.Gson;
import com.google.gson.GsonBuilder;
import com.google.gson.reflect.TypeToken;
import com.velocitypowered.api.command.SimpleCommand;
import com.velocitypowered.api.proxy.Player;
import net.kyori.adventure.text.Component;
import net.kyori.adventure.text.event.ClickEvent;
import net.kyori.adventure.text.format.NamedTextColor;
import net.kyori.adventure.text.format.TextDecoration;

import java.io.*;
import java.net.Socket;
import java.nio.charset.StandardCharsets;
import java.nio.file.Files;
import java.nio.file.Path;
import java.nio.file.StandardCopyOption;
import java.util.*;
import java.util.concurrent.TimeUnit;

/**
 * Invite a friend (1.12.0). A new player can name who invited them with /invitedby <name> during their first
 * WINDOW_H hours on the network. Once they've played NEED_MIN minutes in total (counted here, on any server; slow to
 * farm with alt accounts, and every player reaches us from the same tunnel address, so an IP check can't work), the
 * lobby's vote vault pays out: the new player gets NEW_POINTS vote points and NEW_REWARDS vote reward(s), the inviter
 * INVITER_POINTS points, and an inviter's RECRUITER_AT-th paid invite unlocks the [Recruiter] tag. Payment goes to the
 * lobby over RCON (`vote bonus`, `vote grant`); if the lobby is down it's retried every minute.
 * /invite explains it. New players are told about /invitedby a minute after their first login.
 * Data: plugins/crispytags/invites.json (new players' first-login times, invites, inviters' paid counts).
 */
final class Invites {
    static final long WINDOW_H = 48;
    static final int NEED_MIN = 60, NEW_POINTS = 5, NEW_REWARDS = 1, INVITER_POINTS = 10, RECRUITER_AT = 3;
    static final Path FILE = Path.of("plugins", "crispytags", "invites.json");
    static final Path LOBBY_PROPS = CrispyTags.INSTANCES.resolve("CrispyLobby01/Minecraft/server.properties");
    static final String[] CACHES = {"CrispyLobby01", "CrispyAnarchy01", "Vanilla01", "CrispyPvP01", "Falling01", "Extraction01"};
    static final Gson GSON = new GsonBuilder().setPrettyPrinting().create();

    static final class Invite { String name, inviter; long at; int minutes; boolean paid; }
    static final class Data {
        Map<String, Long> firstSeen = new HashMap<>();     // uuid -> first login (ms), new players only
        Map<String, Invite> invites = new HashMap<>();     // invited player's uuid -> invite
        Map<String, Integer> recruited = new HashMap<>();  // inviter (lower case) -> paid invites
    }

    final CrispyTags plugin;
    Data data = new Data();

    Invites(CrispyTags plugin) {
        this.plugin = plugin;
        try (Reader r = Files.newBufferedReader(FILE)) { Data d = GSON.fromJson(r, Data.class); if (d != null) data = d; }
        catch (IOException ignored) {}
        if (data.firstSeen == null) data.firstSeen = new HashMap<>();
        if (data.invites == null) data.invites = new HashMap<>();
        if (data.recruited == null) data.recruited = new HashMap<>();
    }

    synchronized void save() {
        try {
            Files.createDirectories(FILE.getParent());
            Path tmp = FILE.resolveSibling("invites.json.tmp");
            Files.writeString(tmp, GSON.toJson(data));
            Files.move(tmp, FILE, StandardCopyOption.REPLACE_EXISTING, StandardCopyOption.ATOMIC_MOVE);
        } catch (IOException e) { plugin.log.warn("invites: can't save: {}", e.toString()); }
    }

    void start() {
        var cm = plugin.proxy.getCommandManager();
        cm.register(cm.metaBuilder("invitedby").aliases("referredby").plugin(plugin).build(), new InvitedBy());
        cm.register(cm.metaBuilder("invite").aliases("invites", "refer").plugin(plugin).build(), new Info());
        plugin.proxy.getScheduler().buildTask(plugin, this::minute).delay(1, TimeUnit.MINUTES).repeat(1, TimeUnit.MINUTES).schedule();
    }

    /** Newcomers: a player with no save file anywhere just logged in for the first time. */
    void newPlayer(Player p) {
        synchronized (this) { data.firstSeen.putIfAbsent(p.getUniqueId().toString(), System.currentTimeMillis()); }
        save();
        plugin.proxy.getScheduler().buildTask(plugin, () -> {
            if (!p.isActive()) return;
            p.sendMessage(Component.text()
                    .append(Component.text("✦ Did a friend invite you? ", NamedTextColor.GOLD, TextDecoration.BOLD))
                    .append(Component.text("Type ", NamedTextColor.GRAY))
                    .append(Component.text("/invitedby <their name>", NamedTextColor.YELLOW)
                            .clickEvent(ClickEvent.suggestCommand("/invitedby ")))
                    .append(Component.text(" in your first 2 days: after an hour of play you both get rewards.", NamedTextColor.GRAY))
                    .build());
        }).delay(75, TimeUnit.SECONDS).schedule();
    }

    static Component pre() { return Component.text("Invite » ", NamedTextColor.GREEN, TextDecoration.BOLD); }
    static void say(Player p, String text, NamedTextColor c) { p.sendMessage(pre().append(Component.text(text, c).decoration(TextDecoration.BOLD, false))); }

    /** The exact name of a player who has played here before (from the servers' user caches), or null. */
    static String knownName(String name) {
        for (String inst : CACHES) {
            try {
                List<Map<String, Object>> l = new Gson().fromJson(Files.readString(CrispyTags.INSTANCES.resolve(inst).resolve("Minecraft/usercache.json")),
                        new TypeToken<List<Map<String, Object>>>() {}.getType());
                if (l != null) for (Map<String, Object> e : l) if (name.equalsIgnoreCase(String.valueOf(e.get("name")))) return String.valueOf(e.get("name"));
            } catch (Exception ignored) {}
        }
        return null;
    }

    final class InvitedBy implements SimpleCommand {
        @Override public void execute(Invocation inv) {
            if (!(inv.source() instanceof Player p)) return;
            String[] a = inv.arguments();
            if (a.length != 1 || !a[0].matches("[A-Za-z0-9_.*]{2,16}")) { say(p, "Use /invitedby <the name of the friend who invited you>", NamedTextColor.GRAY); return; }
            String me = p.getUniqueId().toString();
            Long first;
            synchronized (Invites.this) {
                if (data.invites.containsKey(me)) { say(p, "You've already said " + data.invites.get(me).inviter + " invited you.", NamedTextColor.GRAY); return; }
                first = data.firstSeen.get(me);
            }
            if (first == null || System.currentTimeMillis() - first > WINDOW_H * 3_600_000L) {
                say(p, "This is only for new players, in their first 2 days. Invite your own friends with /invite!", NamedTextColor.RED); return;
            }
            if (a[0].equalsIgnoreCase(p.getUsername())) { say(p, "You can't invite yourself.", NamedTextColor.RED); return; }
            String inviter = plugin.proxy.getPlayer(a[0]).map(Player::getUsername).orElseGet(() -> knownName(a[0]));
            if (inviter == null) { say(p, "Nobody called " + a[0] + " has played here yet. Check the spelling.", NamedTextColor.RED); return; }
            synchronized (Invites.this) {   // no swapping: someone you invited can't name you back
                Invite theirs = plugin.proxy.getPlayer(inviter).map(o -> data.invites.get(o.getUniqueId().toString())).orElse(null);
                if (theirs != null && theirs.inviter.equalsIgnoreCase(p.getUsername())) { say(p, "You invited " + inviter + ", so they can't have invited you.", NamedTextColor.RED); return; }
                if (data.invites.values().stream().anyMatch(i -> i.name.equalsIgnoreCase(inviter) && i.inviter.equalsIgnoreCase(p.getUsername()))) {
                    say(p, "You invited " + inviter + ", so they can't have invited you.", NamedTextColor.RED); return;
                }
                Invite i = new Invite();
                i.name = p.getUsername(); i.inviter = inviter; i.at = System.currentTimeMillis();
                data.invites.put(me, i);
            }
            save();
            plugin.log.info("[invite] {} was invited by {}", p.getUsername(), inviter);
            say(p, "Thanks! Play for an hour (on any server) and you'll get " + NEW_POINTS + " vote points and a free vote reward; "
                    + inviter + " gets " + INVITER_POINTS + " points.", NamedTextColor.GREEN);
            plugin.proxy.getPlayer(inviter).ifPresent(o -> say(o, p.getUsername() + " says you invited them! You'll get " + INVITER_POINTS
                    + " vote points once they've played an hour.", NamedTextColor.GREEN));
        }
        @Override public List<String> suggest(Invocation inv) {
            String start = inv.arguments().length > 0 ? inv.arguments()[0].toLowerCase(Locale.ROOT) : "";
            return plugin.proxy.getAllPlayers().stream().map(Player::getUsername)
                    .filter(n -> n.toLowerCase(Locale.ROOT).startsWith(start) && !(inv.source() instanceof Player p && p.getUsername().equals(n))).toList();
        }
    }

    final class Info implements SimpleCommand {
        @Override public void execute(Invocation inv) {
            if (!(inv.source() instanceof Player p)) return;
            int n;
            long waiting;
            synchronized (Invites.this) {
                n = data.recruited.getOrDefault(p.getUsername().toLowerCase(Locale.ROOT), 0);
                waiting = data.invites.values().stream().filter(i -> !i.paid && i.inviter.equalsIgnoreCase(p.getUsername())).count();
            }
            p.sendMessage(Component.text()
                    .append(pre()).append(Component.text("Bring your friends to Crispy!", NamedTextColor.YELLOW).decoration(TextDecoration.BOLD, false)).build());
            p.sendMessage(Component.text("  1. They join ", NamedTextColor.GRAY).append(Component.text("crispyanarchy.net", NamedTextColor.WHITE))
                    .append(Component.text(" (Java, or Bedrock port 19100).", NamedTextColor.GRAY)));
            p.sendMessage(Component.text("  2. In their first 2 days they type ", NamedTextColor.GRAY)
                    .append(Component.text("/invitedby " + p.getUsername(), NamedTextColor.YELLOW)).append(Component.text(".", NamedTextColor.GRAY)));
            p.sendMessage(Component.text("  3. After they've played an hour: you get ", NamedTextColor.GRAY)
                    .append(Component.text(INVITER_POINTS + " vote points", NamedTextColor.LIGHT_PURPLE))
                    .append(Component.text(", they get " + NEW_POINTS + " points and a free vote reward.", NamedTextColor.GRAY)));
            p.sendMessage(Component.text("  Bring " + RECRUITER_AT + " friends for the ", NamedTextColor.GRAY)
                    .append(Component.text("[Recruiter]", NamedTextColor.GREEN, TextDecoration.BOLD)).append(Component.text(" tag.", NamedTextColor.GRAY)));
            p.sendMessage(Component.text("  You've brought " + n + (waiting > 0 ? " (" + waiting + " still playing their first hour)" : "") + ".", NamedTextColor.DARK_GRAY));
        }
    }

    /** Every minute: count online time for unpaid invites and pay out the ones that reached NEED_MIN. */
    void minute() {
        List<Invite> due = new ArrayList<>();
        boolean dirty = false;
        synchronized (this) {
            for (Player p : plugin.proxy.getAllPlayers()) {
                Invite i = data.invites.get(p.getUniqueId().toString());
                if (i == null || i.paid) continue;
                if (i.minutes < NEED_MIN) { i.minutes++; dirty = true; }
                if (i.minutes >= NEED_MIN) due.add(i);
            }
            long cut = System.currentTimeMillis() - 30L * 24 * 3_600_000L;   // first-login times only matter for 2 days
            dirty |= data.firstSeen.values().removeIf(t -> t < cut);
        }
        if (dirty) save();
        for (Invite i : due) pay(i);
    }

    void pay(Invite i) {
        try {
            rcon("vote bonus " + i.name + " " + NEW_POINTS + " " + NEW_REWARDS + " playing your first hour (invited by " + i.inviter + ")");
            rcon("vote bonus " + i.inviter + " " + INVITER_POINTS + " 0 inviting " + i.name);
        } catch (IOException e) { plugin.log.warn("invites: lobby RCON failed, retrying next minute: {}", e.toString()); return; }
        int n;
        synchronized (this) {
            i.paid = true;
            n = data.recruited.merge(i.inviter.toLowerCase(Locale.ROOT), 1, Integer::sum);
        }
        save();
        plugin.log.info("[invite] paid: {} (invited by {}, their #{})", i.name, i.inviter, n);
        if (n == RECRUITER_AT) try { rcon("vote grant " + i.inviter + " tag:recruiter"); } catch (IOException e) { plugin.log.warn("invites: couldn't grant [Recruiter] to {}: {}", i.inviter, e.toString()); }
        plugin.proxy.getPlayer(i.name).ifPresent(p -> say(p, "You've played an hour: +" + NEW_POINTS + " vote points and a free vote reward (claim it in /vote). Welcome to Crispy!", NamedTextColor.GREEN));
        plugin.proxy.getPlayer(i.inviter).ifPresent(p -> say(p, i.name + " has played an hour: +" + INVITER_POINTS + " vote points! (" + n + " friend" + (n == 1 ? "" : "s") + " brought"
                + (n == RECRUITER_AT ? ": you've earned the [Recruiter] tag, wear it in /cosmetics" : "") + ")", NamedTextColor.GREEN));
    }

    /** One command on the lobby's console (RCON port and password from its server.properties). */
    static String rcon(String cmd) throws IOException {
        Properties pr = new Properties();
        try (Reader r = Files.newBufferedReader(LOBBY_PROPS)) { pr.load(r); }
        try (Socket s = new Socket("127.0.0.1", Integer.parseInt(pr.getProperty("rcon.port", "25575")))) {
            s.setSoTimeout(5000);
            DataOutputStream out = new DataOutputStream(s.getOutputStream());
            DataInputStream in = new DataInputStream(s.getInputStream());
            send(out, 1, 3, pr.getProperty("rcon.password", ""));
            if ((int) read(in)[0] == -1) throw new IOException("RCON login refused");
            send(out, 2, 2, cmd);
            return new String((byte[]) read(in)[1], StandardCharsets.UTF_8);
        }
    }
    static void send(DataOutputStream out, int id, int type, String body) throws IOException {
        byte[] b = body.getBytes(StandardCharsets.UTF_8);
        java.nio.ByteBuffer buf = java.nio.ByteBuffer.allocate(14 + b.length).order(java.nio.ByteOrder.LITTLE_ENDIAN);
        buf.putInt(10 + b.length).putInt(id).putInt(type).put(b).put((byte) 0).put((byte) 0);
        out.write(buf.array()); out.flush();
    }
    static Object[] read(DataInputStream in) throws IOException {
        byte[] h = new byte[12]; in.readFully(h);
        java.nio.ByteBuffer hb = java.nio.ByteBuffer.wrap(h).order(java.nio.ByteOrder.LITTLE_ENDIAN);
        int len = hb.getInt(), id = hb.getInt();
        byte[] body = new byte[len - 8]; in.readFully(body);
        return new Object[]{id, Arrays.copyOf(body, Math.max(0, body.length - 2))};
    }
}

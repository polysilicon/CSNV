package crispy.anarchy;

import com.google.gson.Gson;
import com.google.gson.GsonBuilder;
import com.mojang.brigadier.CommandDispatcher;
import com.mojang.brigadier.arguments.StringArgumentType;
import com.mojang.brigadier.context.CommandContext;
import net.fabricmc.fabric.api.command.v2.CommandRegistrationCallback;
import net.fabricmc.fabric.api.entity.event.v1.ServerLivingEntityEvents;
import net.fabricmc.fabric.api.event.lifecycle.v1.ServerLifecycleEvents;
import net.fabricmc.fabric.api.message.v1.ServerMessageEvents;
import net.fabricmc.fabric.api.networking.v1.ServerPlayConnectionEvents;
import net.fabricmc.loader.api.FabricLoader;
import net.minecraft.ChatFormatting;
import net.minecraft.commands.CommandSourceStack;
import net.minecraft.commands.Commands;
import net.minecraft.commands.SharedSuggestionProvider;
import net.minecraft.network.chat.ClickEvent;
import net.minecraft.network.chat.Component;
import net.minecraft.network.chat.HoverEvent;
import net.minecraft.network.chat.MutableComponent;
import net.minecraft.server.MinecraftServer;
import net.minecraft.server.level.ServerPlayer;

import java.nio.file.Files;
import java.nio.file.Path;
import java.util.*;

/**
 * Clans on Anarchy (the old Bukkit "Clans" plugin's idea, rebuilt for Fabric): a name shown as a tag in chat, a private
 * clan chat, kill stats and a top list. No land claiming, no bases.
 * - Data: config/crispy_clans.json (the old plugin's 24 clans were imported into it once, see anarchy/mod/README.md).
 * - The tag reaches chat through the Placeholder API placeholder %crispy:clan% ("[Name] " or nothing), used in
 *   config/styled-chat.json: "<%crispy:clan%%crispy:tag%%crispy:name%> ${message}".
 * - Clan chat (/cc <message>, or /clan chat to send everything there) is stopped before the server logs or broadcasts
 *   the message, so it never reaches the console, the log or the Discord bridge. Ops can listen in with /clan spy.
 * - Ranks: owner, officers (invite, kick, clan colour, friendly fire), members. Friendly fire is off unless the owner
 *   or an officer turns it on. A kill of a player outside the clan counts towards the clan's kills.
 */
public final class Clans {
    private Clans() {}

    static final Path FILE = Path.of("config", "crispy_clans.json");
    static final Gson GSON = new GsonBuilder().setPrettyPrinting().create();
    static final int NAME_MIN = 2, NAME_MAX = 10;
    static final long INVITE_MS = 5 * 60_000;
    static final List<String> COLORS = List.of("white", "gray", "dark_gray", "black", "red", "dark_red", "gold", "yellow",
            "green", "dark_green", "aqua", "dark_aqua", "blue", "dark_blue", "light_purple", "dark_purple");
    static final List<String> BLOCKED = List.of("admin", "staff", "owner", "mod", "server", "crispy", "console");

    static final class Clan {
        String name;                       // as typed (shown as the tag); the map key is its lower case
        String color = "gray";
        String owner;                      // UUID
        List<String> officers = new ArrayList<>();
        Map<String, String> members = new LinkedHashMap<>();   // UUID -> last known name (owner included)
        int kills;
        boolean friendlyFire;
        long created;
    }
    static final class Data { Map<String, Clan> clans = new TreeMap<>(); }

    static Data data = new Data();
    static final Map<UUID, String> byPlayer = new HashMap<>();              // player -> clan key
    static final Map<UUID, Map<String, Long>> invites = new HashMap<>();    // player -> clan key -> expiry
    static final Set<UUID> chatMode = new HashSet<>(), spies = new HashSet<>();
    static MinecraftServer server;

    // ------------------------------------------------------------------ setup
    static void init() {
        ServerLifecycleEvents.SERVER_STARTED.register(s -> { server = s; load(); });
        ServerPlayConnectionEvents.JOIN.register((handler, sender, s) -> rename(handler.player));
        ServerPlayConnectionEvents.DISCONNECT.register((handler, s) -> spies.remove(handler.player.getUUID()));
        CommandRegistrationCallback.EVENT.register((d, reg, env) -> register(d));
        // clan chat mode: the message goes to the clan and never into public chat (or the log)
        ServerMessageEvents.ALLOW_CHAT_MESSAGE.register((msg, sender, params) -> {
            if (!chatMode.contains(sender.getUUID())) return true;
            Clan c = clanOf(sender);
            if (c == null) { chatMode.remove(sender.getUUID()); return true; }
            clanChat(sender, c, msg.signedContent());
            return false;
        });
        // friendly fire
        ServerLivingEntityEvents.ALLOW_DAMAGE.register((victim, source, amount) -> {
            if (!(victim instanceof ServerPlayer v) || !(source.getEntity() instanceof ServerPlayer a) || a == v) return true;
            Clan c = clanOf(v);
            return c == null || c != clanOf(a) || c.friendlyFire;
        });
        // kills of players outside the clan
        ServerLivingEntityEvents.AFTER_DEATH.register((victim, source) -> {
            if (!(victim instanceof ServerPlayer v) || !(source.getEntity() instanceof ServerPlayer k) || k == v) return;
            Clan c = clanOf(k);
            if (c != null && c != clanOf(v)) { c.kills++; save(); }
        });
        if (FabricLoader.getInstance().isModLoaded("placeholder-api")) ClanPlaceholder.register();
    }

    static void load() {
        try {
            if (Files.exists(FILE)) {
                Data d = GSON.fromJson(Files.readString(FILE), Data.class);
                if (d != null && d.clans != null) data = d;
            }
        } catch (Exception e) { System.err.println("[crispy_anarchy] couldn't read " + FILE + ": " + e); }
        byPlayer.clear();
        for (var e : data.clans.entrySet()) for (String u : e.getValue().members.keySet()) {
            try { byPlayer.putIfAbsent(UUID.fromString(u), e.getKey()); } catch (IllegalArgumentException ignored) {}
        }
    }

    static void save() {
        try {
            Files.createDirectories(FILE.getParent());
            Path tmp = FILE.resolveSibling("crispy_clans.json.tmp");
            Files.writeString(tmp, GSON.toJson(data));
            Files.move(tmp, FILE, java.nio.file.StandardCopyOption.REPLACE_EXISTING, java.nio.file.StandardCopyOption.ATOMIC_MOVE);
        } catch (Exception e) { System.err.println("[crispy_anarchy] couldn't save " + FILE + ": " + e); }
    }

    static void rename(ServerPlayer p) {
        Clan c = clanOf(p);
        if (c == null) return;
        String n = p.getGameProfile().name();
        if (!n.equals(c.members.get(p.getUUID().toString()))) { c.members.put(p.getUUID().toString(), n); save(); }
    }

    static Clan clanOf(ServerPlayer p) { String k = byPlayer.get(p.getUUID()); return k == null ? null : data.clans.get(k); }
    static boolean isOwner(Clan c, ServerPlayer p) { return c.owner.equals(p.getUUID().toString()); }
    static boolean canManage(Clan c, ServerPlayer p) { return isOwner(c, p) || c.officers.contains(p.getUUID().toString()); }
    static ChatFormatting color(Clan c) {
        try { return ChatFormatting.valueOf(c.color.toUpperCase(Locale.ROOT)); } catch (RuntimeException e) { return ChatFormatting.GRAY; }
    }

    /** "[Name]" in the clan's colour, with its info on hover. */
    static MutableComponent tag(Clan c) {
        return Component.literal("[" + c.name + "]").withStyle(color(c))
                .withStyle(s -> s.withHoverEvent(new HoverEvent.ShowText(Component.literal("Clan " + c.name + " · " + c.members.size()
                        + " member" + (c.members.size() == 1 ? "" : "s") + " · " + c.kills + " kills").withStyle(ChatFormatting.GRAY)))
                        .withClickEvent(new ClickEvent.RunCommand("/clan info " + c.name)));
    }

    // ------------------------------------------------------------------ messages
    static MutableComponent t(String s, ChatFormatting f) { return Component.literal(s).withStyle(f); }
    static MutableComponent prefix() { return t("[Clans] ", ChatFormatting.DARK_AQUA); }
    static void ok(ServerPlayer p, String s) { p.sendSystemMessage(prefix().append(t(s, ChatFormatting.GRAY))); }
    static void err(ServerPlayer p, String s) { p.sendSystemMessage(prefix().append(t(s, ChatFormatting.RED))); }
    static MutableComponent button(String label, String cmd, String hover, ChatFormatting col) {
        return Component.literal(label).withStyle(col, ChatFormatting.BOLD)
                .withStyle(s -> s.withClickEvent(new ClickEvent.RunCommand(cmd)).withHoverEvent(new HoverEvent.ShowText(t(hover, ChatFormatting.GRAY))));
    }

    static void toClan(Clan c, Component msg) {
        if (server == null) return;
        for (String u : c.members.keySet()) {
            ServerPlayer m = server.getPlayerList().getPlayer(UUID.fromString(u));
            if (m != null) m.sendSystemMessage(msg);
        }
    }

    static void clanChat(ServerPlayer from, Clan c, String text) {
        text = text.strip();
        if (text.isEmpty()) return;
        Component line = t("[CC] ", ChatFormatting.DARK_AQUA).append(tag(c)).append(t(" " + from.getGameProfile().name() + ": ", ChatFormatting.AQUA))
                .append(t(text, ChatFormatting.WHITE));
        toClan(c, line);
        Component spy = t("[spy] ", ChatFormatting.DARK_GRAY).append(line);
        for (ServerPlayer p : server.getPlayerList().getPlayers())
            if (spies.contains(p.getUUID()) && !c.members.containsKey(p.getUUID().toString())) p.sendSystemMessage(spy);
    }

    // ------------------------------------------------------------------ commands
    static ServerPlayer player(CommandContext<CommandSourceStack> ctx) { return ctx.getSource().getPlayer(); }

    interface Act { int run(ServerPlayer p, CommandContext<CommandSourceStack> c); }
    static com.mojang.brigadier.Command<CommandSourceStack> as(Act a) {
        return ctx -> { ServerPlayer p = player(ctx); if (p == null) { ctx.getSource().sendFailure(Component.literal("Players only.")); return 0; } return a.run(p, ctx); };
    }
    static String arg(CommandContext<CommandSourceStack> c, String n) { return StringArgumentType.getString(c, n); }

    static void register(CommandDispatcher<CommandSourceStack> d) {
        var online = (com.mojang.brigadier.suggestion.SuggestionProvider<CommandSourceStack>) (c, b) ->
                SharedSuggestionProvider.suggest(c.getSource().getServer().getPlayerList().getPlayerNamesArray(), b);
        var clans = (com.mojang.brigadier.suggestion.SuggestionProvider<CommandSourceStack>) (c, b) ->
                SharedSuggestionProvider.suggest(data.clans.values().stream().map(x -> x.name), b);
        var members = (com.mojang.brigadier.suggestion.SuggestionProvider<CommandSourceStack>) (c, b) -> {
            ServerPlayer p = c.getSource().getPlayer();
            Clan cl = p == null ? null : clanOf(p);
            return SharedSuggestionProvider.suggest(cl == null ? List.<String>of() : cl.members.values(), b);
        };
        d.register(Commands.literal("clan").executes(as((p, c) -> help(p)))
                .then(Commands.literal("help").executes(as((p, c) -> help(p))))
                .then(Commands.literal("create").then(Commands.argument("name", StringArgumentType.word()).executes(as((p, c) -> create(p, arg(c, "name"))))))
                .then(Commands.literal("invite").then(Commands.argument("player", StringArgumentType.word()).suggests(online).executes(as((p, c) -> invite(p, arg(c, "player"))))))
                .then(Commands.literal("accept").executes(as((p, c) -> accept(p, null)))
                        .then(Commands.argument("clan", StringArgumentType.word()).suggests(clans).executes(as((p, c) -> accept(p, arg(c, "clan"))))))
                .then(Commands.literal("deny").executes(as((p, c) -> deny(p, null)))
                        .then(Commands.argument("clan", StringArgumentType.word()).suggests(clans).executes(as((p, c) -> deny(p, arg(c, "clan"))))))
                .then(Commands.literal("leave").executes(as((p, c) -> leave(p))))
                .then(Commands.literal("kick").then(Commands.argument("player", StringArgumentType.word()).suggests(members).executes(as((p, c) -> kick(p, arg(c, "player"))))))
                .then(Commands.literal("promote").then(Commands.argument("player", StringArgumentType.word()).suggests(members).executes(as((p, c) -> rank(p, arg(c, "player"), true)))))
                .then(Commands.literal("demote").then(Commands.argument("player", StringArgumentType.word()).suggests(members).executes(as((p, c) -> rank(p, arg(c, "player"), false)))))
                .then(Commands.literal("transfer").then(Commands.argument("player", StringArgumentType.word()).suggests(members).executes(as((p, c) -> transfer(p, arg(c, "player"))))))
                .then(Commands.literal("disband").executes(as((p, c) -> disband(p, false)))
                        .then(Commands.literal("confirm").executes(as((p, c) -> disband(p, true)))))
                .then(Commands.literal("info").executes(as((p, c) -> info(p, null)))
                        .then(Commands.argument("clan", StringArgumentType.word()).suggests(clans).executes(as((p, c) -> info(p, arg(c, "clan"))))))
                .then(Commands.literal("list").executes(as((p, c) -> list(p))))
                .then(Commands.literal("top").executes(as((p, c) -> top(p))))
                .then(Commands.literal("chat").executes(as((p, c) -> toggleChat(p))))
                .then(Commands.literal("color").then(Commands.argument("color", StringArgumentType.word())
                        .suggests((c, b) -> SharedSuggestionProvider.suggest(COLORS, b)).executes(as((p, c) -> color(p, arg(c, "color"))))))
                .then(Commands.literal("pvp").then(Commands.literal("on").executes(as((p, c) -> pvp(p, true))))
                        .then(Commands.literal("off").executes(as((p, c) -> pvp(p, false)))))
                .then(Commands.literal("spy").requires(Commands.hasPermission(Commands.LEVEL_GAMEMASTERS)).executes(as((p, c) -> spy(p)))));
        d.register(Commands.literal("cc").executes(as((p, c) -> toggleChat(p)))
                .then(Commands.argument("message", StringArgumentType.greedyString()).executes(as((p, c) -> {
                    Clan cl = clanOf(p);
                    if (cl == null) { err(p, "You're not in a clan."); return 0; }
                    clanChat(p, cl, arg(c, "message"));
                    return 1;
                }))));
    }

    static int help(ServerPlayer p) {
        p.sendSystemMessage(t("Clans", ChatFormatting.DARK_AQUA).withStyle(ChatFormatting.BOLD).append(t("  (no land claiming)", ChatFormatting.DARK_GRAY)));
        String[][] lines = {
                {"/clan create <name>", "start a clan (2-10 letters or numbers)"}, {"/clan invite <player>", "invite someone (owner/officers)"},
                {"/clan accept [clan]", "join a clan that invited you"}, {"/cc <message>", "talk to your clan only (/clan chat: toggle)"},
                {"/clan info [clan]", "members, kills and ranks"}, {"/clan list", "every clan"}, {"/clan top", "most kills"},
                {"/clan leave", "leave your clan"}, {"/clan kick <player>", "remove a member (owner/officers)"},
                {"/clan promote|demote <player>", "officers (owner)"}, {"/clan transfer <player>", "give the clan away (owner)"},
                {"/clan color <colour>", "your tag's colour (owner/officers)"}, {"/clan pvp on|off", "friendly fire (owner/officers)"},
                {"/clan disband", "delete the clan (owner)"}};
        for (String[] l : lines) p.sendSystemMessage(Component.literal(l[0]).withStyle(ChatFormatting.AQUA)
                .withStyle(s -> s.withClickEvent(new ClickEvent.SuggestCommand(l[0].replaceAll(" [<\\[].*", " ")))).append(t(" " + l[1], ChatFormatting.GRAY)));
        return 1;
    }

    static int create(ServerPlayer p, String name) {
        if (clanOf(p) != null) { err(p, "You're already in a clan. Leave it first."); return 0; }
        if (name.length() < NAME_MIN || name.length() > NAME_MAX || !name.matches("[A-Za-z0-9]+")) {
            err(p, "Clan names are " + NAME_MIN + "-" + NAME_MAX + " letters or numbers."); return 0;
        }
        String key = name.toLowerCase(Locale.ROOT);
        if (BLOCKED.contains(key)) { err(p, "That name isn't allowed."); return 0; }
        if (data.clans.containsKey(key)) { err(p, "There's already a clan called " + data.clans.get(key).name + "."); return 0; }
        Clan c = new Clan();
        c.name = name; c.owner = p.getUUID().toString(); c.created = System.currentTimeMillis();
        c.members.put(c.owner, p.getGameProfile().name());
        data.clans.put(key, c); byPlayer.put(p.getUUID(), key); save();
        p.sendSystemMessage(prefix().append(t("You founded ", ChatFormatting.GREEN)).append(tag(c)).append(t("! Invite people with /clan invite <player>.", ChatFormatting.GREEN)));
        return 1;
    }

    static int invite(ServerPlayer p, String who) {
        Clan c = clanOf(p);
        if (c == null) { err(p, "You're not in a clan."); return 0; }
        if (!canManage(c, p)) { err(p, "Only the owner and officers can invite."); return 0; }
        ServerPlayer t = server.getPlayerList().getPlayerByName(who);
        if (t == null) { err(p, who + " isn't online."); return 0; }
        if (t == p) { err(p, "You're already in your clan."); return 0; }
        if (clanOf(t) != null) { err(p, t.getGameProfile().name() + " is already in a clan."); return 0; }
        String key = c.name.toLowerCase(Locale.ROOT);
        invites.computeIfAbsent(t.getUUID(), k -> new HashMap<>()).put(key, System.currentTimeMillis() + INVITE_MS);
        ok(p, "Invited " + t.getGameProfile().name() + ". The invite lasts 5 minutes.");
        t.sendSystemMessage(prefix().append(t(p.getGameProfile().name() + " invited you to ", ChatFormatting.GRAY)).append(tag(c)).append(t("  ", ChatFormatting.GRAY))
                .append(button("[Join]", "/clan accept " + c.name, "Join " + c.name, ChatFormatting.GREEN)).append(t(" ", ChatFormatting.GRAY))
                .append(button("[No thanks]", "/clan deny " + c.name, "Turn the invite down", ChatFormatting.RED)));
        return 1;
    }

    static String pending(ServerPlayer p, String clan) {
        Map<String, Long> m = invites.getOrDefault(p.getUUID(), Map.of());
        long now = System.currentTimeMillis();
        List<String> live = m.entrySet().stream().filter(e -> e.getValue() > now && data.clans.containsKey(e.getKey())).map(Map.Entry::getKey).toList();
        if (clan != null) { String k = clan.toLowerCase(Locale.ROOT); return live.contains(k) ? k : null; }
        return live.size() == 1 ? live.get(0) : null;
    }

    static int accept(ServerPlayer p, String clan) {
        if (clanOf(p) != null) { err(p, "You're already in a clan. Leave it first."); return 0; }
        String key = pending(p, clan);
        if (key == null) { err(p, clan == null ? "You have no invite to accept (or several: /clan accept <clan>)." : "You have no invite from " + clan + "."); return 0; }
        Clan c = data.clans.get(key);
        invites.remove(p.getUUID());
        c.members.put(p.getUUID().toString(), p.getGameProfile().name());
        byPlayer.put(p.getUUID(), key); save();
        toClan(c, prefix().append(t(p.getGameProfile().name() + " joined ", ChatFormatting.GREEN)).append(tag(c)).append(t("!", ChatFormatting.GREEN)));
        return 1;
    }

    static int deny(ServerPlayer p, String clan) {
        String key = pending(p, clan);
        if (key == null) { err(p, "You have no invite to turn down."); return 0; }
        invites.getOrDefault(p.getUUID(), new HashMap<>()).remove(key);
        ok(p, "Invite turned down.");
        return 1;
    }

    static void removeMember(Clan c, String uuid) {
        c.members.remove(uuid); c.officers.remove(uuid);
        try { UUID u = UUID.fromString(uuid); byPlayer.remove(u); chatMode.remove(u); } catch (IllegalArgumentException ignored) {}
    }

    static int leave(ServerPlayer p) {
        Clan c = clanOf(p);
        if (c == null) { err(p, "You're not in a clan."); return 0; }
        if (isOwner(c, p) && c.members.size() > 1) { err(p, "You own the clan: /clan transfer <player> first, or /clan disband."); return 0; }
        if (isOwner(c, p)) return disband(p, true);
        removeMember(c, p.getUUID().toString()); save();
        ok(p, "You left " + c.name + ".");
        toClan(c, prefix().append(t(p.getGameProfile().name() + " left the clan.", ChatFormatting.YELLOW)));
        return 1;
    }

    static String memberUuid(Clan c, String name) {
        return c.members.entrySet().stream().filter(e -> e.getValue().equalsIgnoreCase(name)).map(Map.Entry::getKey).findFirst().orElse(null);
    }

    static int kick(ServerPlayer p, String who) {
        Clan c = clanOf(p);
        if (c == null || !canManage(c, p)) { err(p, "Only the owner and officers can kick."); return 0; }
        String u = memberUuid(c, who);
        if (u == null) { err(p, who + " isn't in your clan."); return 0; }
        if (u.equals(c.owner) || c.officers.contains(u) && !isOwner(c, p)) { err(p, "You can't kick them."); return 0; }
        String name = c.members.get(u);
        removeMember(c, u); save();
        toClan(c, prefix().append(t(name + " was kicked by " + p.getGameProfile().name() + ".", ChatFormatting.YELLOW)));
        ServerPlayer t = server.getPlayerList().getPlayer(UUID.fromString(u));
        if (t != null) err(t, "You were kicked from " + c.name + ".");
        return 1;
    }

    static int rank(ServerPlayer p, String who, boolean up) {
        Clan c = clanOf(p);
        if (c == null || !isOwner(c, p)) { err(p, "Only the owner can promote or demote."); return 0; }
        String u = memberUuid(c, who);
        if (u == null || u.equals(c.owner)) { err(p, who + " isn't a member you can change."); return 0; }
        if (up == c.officers.contains(u)) { err(p, c.members.get(u) + (up ? " is already an officer." : " isn't an officer.")); return 0; }
        if (up) c.officers.add(u); else c.officers.remove(u);
        save();
        toClan(c, prefix().append(t(c.members.get(u) + (up ? " is now an officer." : " is no longer an officer."), ChatFormatting.GREEN)));
        return 1;
    }

    static int transfer(ServerPlayer p, String who) {
        Clan c = clanOf(p);
        if (c == null || !isOwner(c, p)) { err(p, "Only the owner can hand the clan over."); return 0; }
        String u = memberUuid(c, who);
        if (u == null || u.equals(c.owner)) { err(p, who + " isn't another member of your clan."); return 0; }
        c.officers.remove(u);
        if (!c.officers.contains(c.owner)) c.officers.add(c.owner);   // the old owner stays on as an officer
        c.owner = u; save();
        toClan(c, prefix().append(t(c.members.get(u) + " now owns the clan.", ChatFormatting.GOLD)));
        return 1;
    }

    static int disband(ServerPlayer p, boolean confirm) {
        Clan c = clanOf(p);
        if (c == null || !isOwner(c, p)) { err(p, "Only the owner can disband the clan."); return 0; }
        if (!confirm) {
            p.sendSystemMessage(prefix().append(t("Delete " + c.name + " for good? Its kills go too. ", ChatFormatting.RED))
                    .append(button("[Yes, disband]", "/clan disband confirm", "Delete the clan", ChatFormatting.DARK_RED)));
            return 1;
        }
        toClan(c, prefix().append(t(c.name + " was disbanded.", ChatFormatting.RED)));
        for (String u : List.copyOf(c.members.keySet())) removeMember(c, u);
        data.clans.remove(c.name.toLowerCase(Locale.ROOT)); save();
        return 1;
    }

    static int info(ServerPlayer p, String name) {
        Clan c = name == null ? clanOf(p) : data.clans.get(name.toLowerCase(Locale.ROOT));
        if (c == null) { err(p, name == null ? "You're not in a clan. /clan info <clan> shows another one." : "There's no clan called " + name + "."); return 0; }
        p.sendSystemMessage(t("— ", ChatFormatting.DARK_GRAY).append(tag(c)).append(t(" —  " + c.kills + " kills · friendly fire " + (c.friendlyFire ? "on" : "off"), ChatFormatting.GRAY)));
        MutableComponent line = t("Members (" + c.members.size() + "): ", ChatFormatting.GRAY);
        boolean first = true;
        for (var e : c.members.entrySet()) {
            boolean on = server.getPlayerList().getPlayer(UUID.fromString(e.getKey())) != null;
            String rank = e.getKey().equals(c.owner) ? "★" : c.officers.contains(e.getKey()) ? "+" : "";
            if (!first) line.append(t(", ", ChatFormatting.DARK_GRAY));
            line.append(t(rank + e.getValue(), on ? ChatFormatting.GREEN : ChatFormatting.WHITE));
            first = false;
        }
        p.sendSystemMessage(line);
        p.sendSystemMessage(t("★ owner · + officer · green = online", ChatFormatting.DARK_GRAY));
        return 1;
    }

    static int list(ServerPlayer p) {
        if (data.clans.isEmpty()) { ok(p, "No clans yet. /clan create <name>"); return 1; }
        List<Clan> all = new ArrayList<>(data.clans.values());
        all.sort(Comparator.comparingInt((Clan c) -> -c.members.size()).thenComparing(c -> c.name.toLowerCase(Locale.ROOT)));
        p.sendSystemMessage(t("Clans (" + all.size() + "), click one for its members:", ChatFormatting.DARK_AQUA));
        MutableComponent line = Component.empty();
        for (int i = 0; i < all.size(); i++) {
            if (i > 0) line.append(t("  ", ChatFormatting.GRAY));
            line.append(tag(all.get(i))).append(t(" " + all.get(i).members.size(), ChatFormatting.DARK_GRAY));
        }
        p.sendSystemMessage(line);
        return 1;
    }

    static int top(ServerPlayer p) {
        List<Clan> all = new ArrayList<>(data.clans.values());
        all.sort(Comparator.comparingInt((Clan c) -> -c.kills).thenComparing(c -> c.name.toLowerCase(Locale.ROOT)));
        p.sendSystemMessage(t("Top clans by kills", ChatFormatting.GOLD).withStyle(ChatFormatting.BOLD));
        for (int i = 0; i < Math.min(10, all.size()); i++)
            p.sendSystemMessage(t((i + 1) + ". ", ChatFormatting.YELLOW).append(tag(all.get(i))).append(t("  " + all.get(i).kills + " kills", ChatFormatting.GRAY)));
        return 1;
    }

    static int toggleChat(ServerPlayer p) {
        if (clanOf(p) == null) { err(p, "You're not in a clan."); return 0; }
        if (chatMode.remove(p.getUUID())) ok(p, "Clan chat off: your messages go to public chat again.");
        else { chatMode.add(p.getUUID()); ok(p, "Clan chat on: everything you type goes to your clan only. /clan chat again to switch back."); }
        return 1;
    }

    static int color(ServerPlayer p, String col) {
        Clan c = clanOf(p);
        if (c == null || !canManage(c, p)) { err(p, "Only the owner and officers can change the colour."); return 0; }
        col = col.toLowerCase(Locale.ROOT);
        if (!COLORS.contains(col)) { err(p, "Colours: " + String.join(", ", COLORS)); return 0; }
        c.color = col; save();
        toClan(c, prefix().append(t("The clan tag is now ", ChatFormatting.GRAY)).append(tag(c)));
        return 1;
    }

    static int pvp(ServerPlayer p, boolean on) {
        Clan c = clanOf(p);
        if (c == null || !canManage(c, p)) { err(p, "Only the owner and officers can change friendly fire."); return 0; }
        c.friendlyFire = on; save();
        toClan(c, prefix().append(t("Friendly fire is now " + (on ? "ON: clanmates can hurt each other." : "OFF."), on ? ChatFormatting.RED : ChatFormatting.GREEN)));
        return 1;
    }

    static int spy(ServerPlayer p) {
        if (spies.remove(p.getUUID())) ok(p, "Clan spy off.");
        else { spies.add(p.getUUID()); ok(p, "Clan spy on: you see every clan's chat (until you log out or turn it off)."); }
        return 1;
    }

    /** %crispy:clan%: "[Name] " in the clan's colour, or nothing. Separate class: only loaded with Placeholder API. */
    static final class ClanPlaceholder {
        static void register() {
            eu.pb4.placeholders.api.Placeholders.registerServer(net.minecraft.resources.Identifier.fromNamespaceAndPath("crispy", "clan"), (ctx, arg) -> {
                if (!ctx.hasServerPlayer()) return eu.pb4.placeholders.api.PlaceholderResult.value("");
                Clan c = clanOf(ctx.serverPlayer());
                return c == null ? eu.pb4.placeholders.api.PlaceholderResult.value("")
                        : eu.pb4.placeholders.api.PlaceholderResult.value(tag(c).append(Component.literal(" ")));
            });
        }
    }
}

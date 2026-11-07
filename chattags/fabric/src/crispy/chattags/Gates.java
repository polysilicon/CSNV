package crispy.chattags;

import com.google.gson.Gson;
import com.google.gson.JsonElement;
import com.google.gson.JsonObject;
import com.google.gson.JsonParser;
import com.google.gson.reflect.TypeToken;
import com.mojang.brigadier.CommandDispatcher;
import com.mojang.brigadier.arguments.StringArgumentType;
import com.mojang.serialization.JsonOps;
import net.minecraft.commands.CommandSourceStack;
import net.minecraft.commands.Commands;
import net.minecraft.network.chat.ClickEvent;
import net.minecraft.network.chat.Component;
import net.minecraft.network.chat.ComponentSerialization;
import net.minecraft.network.chat.HoverEvent;
import net.minecraft.network.chat.MutableComponent;
import net.minecraft.resources.RegistryOps;
import net.minecraft.server.MinecraftServer;
import net.minecraft.server.level.ServerPlayer;
import net.minecraft.world.entity.Entity;

import java.net.URI;
import java.net.URLEncoder;
import java.net.http.HttpRequest;
import java.net.http.HttpResponse;
import java.nio.charset.StandardCharsets;
import java.nio.file.Files;
import java.time.Duration;
import java.util.*;

/**
 * Tag-gated places: things only players wearing a certain cosmetic tag can use.
 * - The lobby writes equipped.json (name -> tag id). Every second each online player gets the entity tag ctag.<id> for
 *   the tag they're wearing (and loses old ones), so any mod or datapack can check @s[tag=ctag.og].
 * - An entity tagged needtag.<id> (a shop villager, say) only lets players wearing that tag interact with it.
 * - /crispytag gate <id> <what>: the "you need this tag" message, with a click to equip it when the player can already
 *   wear it (owned, earned, or affordable). Mods run it as the player when they turn someone away.
 * - /crispytag equip <id>: the click. The lobby equips it (claiming or buying it if needed) and the marker updates now.
 */
public final class Gates {
    private Gates() {}

    static final String PREFIX = "ctag.", NEED = "needtag.";
    private static final Map<UUID, Long> lastMsg = new HashMap<>();
    private static volatile Map<String, String> equipped = Map.of();
    private static long mtime = -1;

    // ------------------------------------------------------------------ markers
    /** Once a second (CombatTickMixin): re-read equipped.json if it changed and sync everyone's ctag.<id> marker. */
    public static void tick(MinecraftServer server) {
        try {
            var f = Tags.DIR.resolve("equipped.json");
            long m = Files.getLastModifiedTime(f).toMillis();
            if (m != mtime) {
                Map<String, String> t = new Gson().fromJson(Files.readString(f), new TypeToken<Map<String, String>>() {}.getType());
                equipped = t == null ? Map.of() : t;
                mtime = m;
            }
        } catch (Exception ignored) {}
        for (ServerPlayer p : server.getPlayerList().getPlayers()) sync(p, equipped.get(p.getGameProfile().name().toLowerCase(Locale.ROOT)));
    }

    static void sync(ServerPlayer p, String id) {
        String want = id == null ? null : PREFIX + id;
        for (String t : List.copyOf(p.entityTags())) if (t.startsWith(PREFIX) && !t.equals(want)) p.removeTag(t);
        if (want != null && !p.entityTags().contains(want)) p.addTag(want);
    }

    public static boolean wearing(ServerPlayer p, String id) { return p.entityTags().contains(PREFIX + id); }

    // ------------------------------------------------------------------ gated entities (Player.interactOn mixin)
    /** True when the player may use this entity; otherwise tells them why and returns false. */
    public static boolean mayInteract(ServerPlayer p, Entity e) {
        for (String t : e.entityTags()) {
            if (!t.startsWith(NEED)) continue;
            String id = t.substring(NEED.length());
            if (wearing(p, id)) continue;
            deny(p, id, "This " + (e.hasCustomName() ? e.getCustomName().getString() : "merchant"));
            return false;
        }
        return true;
    }

    // ------------------------------------------------------------------ the message and the click
    /** "<what> needs <tag> equipped" plus, when the player can wear it now, a click to equip it. */
    public static void deny(ServerPlayer p, String id, String what) {
        long now = System.currentTimeMillis();
        Long last = lastMsg.get(p.getUUID());
        if (last != null && now - last < 6000) return;   // walking into a portal or clicking again: one message, not a pile
        lastMsg.put(p.getUUID(), now);
        lobby(p, id, "check", o -> {
            if (o == null) { p.sendSystemMessage(red("🔒 " + what + " needs a special tag equipped.")); return; }
            MutableComponent tag = Tags.legacy(o.get("display").getAsString());
            // one line: 🔒 <what> needs <tag> equipped. [Equip] (or, when they can't yet, what it takes on a hover)
            MutableComponent msg = Component.literal("🔒 ").withStyle(s -> s.withColor(0xFFAA00))
                    .append(Component.literal(what + " needs ").withStyle(s -> s.withColor(0xAAAAAA))).append(tag)
                    .append(Component.literal(" equipped. ").withStyle(s -> s.withColor(0xAAAAAA)));
            if (o.get("can").getAsBoolean()) {
                int cost = o.get("cost").getAsInt();
                String label = cost > 0 ? "[Buy & equip · " + cost + " pt" + (cost == 1 ? "" : "s") + "]" : "[Equip]";
                msg.append(Component.literal(label).withStyle(s -> s.withColor(0x55FF55).withBold(true)
                        .withClickEvent(new ClickEvent.RunCommand("/crispytag equip " + id))
                        .withHoverEvent(new HoverEvent.ShowText(Component.literal("Click to wear ").append(Tags.legacy(o.get("display").getAsString()))))));
            } else {
                msg.append(Component.literal("[How to get it]").withStyle(s -> s.withColor(0xFF5555)
                        .withHoverEvent(new HoverEvent.ShowText(Tags.legacy(o.get("need").getAsString())))));
            }
            p.sendSystemMessage(msg);
        });
    }

    static void award(ServerPlayer p, String id) {
        lobby(p, id, "award", o -> {
            if (o == null || !o.get("equipped").getAsBoolean()) { p.sendSystemMessage(red("Couldn't reach the lobby to unlock your tag: claim it in /cosmetics in a few minutes.")); return; }
            sync(p, id);
            p.sendSystemMessage(Component.literal("✔ ").withStyle(s -> s.withColor(0x55FF55)).append(Tags.legacy(o.get("display").getAsString()))
                    .append(Component.literal(" unlocked and equipped!").withStyle(s -> s.withColor(0x55FF55))));
        });
    }

    static void equip(ServerPlayer p, String id) {
        lobby(p, id, "equip", o -> {
            if (o == null) { p.sendSystemMessage(red("The lobby isn't answering, so tags can't be changed right now. Try again soon.")); return; }
            if (o.get("equipped").getAsBoolean()) {
                sync(p, id);   // right away, not at the next equipped.json read
                lastMsg.remove(p.getUUID());
                p.sendSystemMessage(Component.literal("✔ ").withStyle(s -> s.withColor(0x55FF55)).append(Tags.legacy(o.get("display").getAsString()))
                        .append(Component.literal(" equipped. You can go in now.").withStyle(s -> s.withColor(0x55FF55))));
            } else {
                show(p, o);
                if (!o.get("can").getAsBoolean()) p.sendSystemMessage(Component.literal("✖ ").withStyle(s -> s.withColor(0xFF5555)).append(Tags.legacy(o.get("need").getAsString())));
            }
        });
    }

    private static void show(ServerPlayer p, JsonObject o) {
        MinecraftServer server = p.level().getServer();
        if (!o.has("messages")) return;
        RegistryOps<JsonElement> ops = server.registryAccess().createSerializationContext(JsonOps.INSTANCE);
        for (JsonElement m : o.getAsJsonArray("messages"))
            p.sendSystemMessage(ComponentSerialization.CODEC.parse(ops, m).result().orElse(Component.empty()));
    }

    private static MutableComponent red(String s) { return Component.literal(s).withStyle(st -> st.withColor(0xFF5555)); }

    /** GET the lobby's /tag and hand the reply (or null if it isn't answering) to done, on the server thread. */
    private static void lobby(ServerPlayer p, String id, String act, java.util.function.Consumer<JsonObject> done) {
        MinecraftServer server = p.level().getServer();
        String url = RemoteMenu.BASE + "/tag?do=" + act + "&tag=" + URLEncoder.encode(id, StandardCharsets.UTF_8) + "&uuid=" + p.getUUID()
                + "&name=" + URLEncoder.encode(p.getGameProfile().name(), StandardCharsets.UTF_8);
        RemoteMenu.HTTP.sendAsync(HttpRequest.newBuilder(URI.create(url)).timeout(Duration.ofSeconds(6)).GET().build(), HttpResponse.BodyHandlers.ofString())
                .whenComplete((res, err) -> server.execute(() -> {
                    if (p.hasDisconnected()) return;
                    JsonObject o = null;
                    if (err == null && res.statusCode() == 200) {
                        try { o = JsonParser.parseString(res.body()).getAsJsonObject(); if (o.has("error")) o = null; } catch (Exception ignored) {}
                    }
                    done.accept(o);
                }));
    }

    // ------------------------------------------------------------------ commands
    public static void register(CommandDispatcher<CommandSourceStack> d) {
        d.register(Commands.literal("crispytag")
                .then(Commands.literal("equip").then(Commands.argument("id", StringArgumentType.word()).executes(c -> {
                    ServerPlayer p = c.getSource().getPlayer();
                    if (p == null) return 0;
                    equip(p, StringArgumentType.getString(c, "id"));
                    return 1;
                })))
                // run by datapacks/mods (as the player, with permission) the moment someone earns a tag: unlock + wear it now
                .then(Commands.literal("award").requires(Commands.hasPermission(Commands.LEVEL_GAMEMASTERS))
                        .then(Commands.argument("id", StringArgumentType.word()).executes(c -> {
                            ServerPlayer p = c.getSource().getPlayer();
                            if (p == null) return 0;
                            award(p, StringArgumentType.getString(c, "id"));
                            return 1;
                        })))
                // run by other mods (as the player, with permission) when they turn someone away
                .then(Commands.literal("gate").requires(Commands.hasPermission(Commands.LEVEL_GAMEMASTERS))
                        .then(Commands.argument("id", StringArgumentType.word()).then(Commands.argument("what", StringArgumentType.greedyString()).executes(c -> {
                            ServerPlayer p = c.getSource().getPlayer();
                            if (p == null) return 0;
                            deny(p, StringArgumentType.getString(c, "id"), StringArgumentType.getString(c, "what"));
                            return 1;
                        })))));
    }
}

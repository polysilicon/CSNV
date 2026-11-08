package crispy.falling;

import com.google.gson.Gson;
import com.google.gson.GsonBuilder;
import com.google.gson.reflect.TypeToken;
import com.mojang.brigadier.CommandDispatcher;
import com.mojang.brigadier.arguments.StringArgumentType;
import com.mojang.brigadier.builder.LiteralArgumentBuilder;
import net.minecraft.ChatFormatting;
import net.minecraft.commands.CommandSourceStack;
import net.minecraft.commands.Commands;
import net.minecraft.commands.SharedSuggestionProvider;
import net.minecraft.nbt.CompoundTag;
import net.minecraft.resources.Identifier;
import net.minecraft.resources.ResourceKey;
import net.minecraft.server.MinecraftServer;
import net.minecraft.server.level.ServerLevel;
import net.minecraft.server.level.ServerPlayer;
import net.minecraft.world.level.Level;
import net.minecraft.world.scores.ScoreHolder;

import java.nio.file.Files;
import java.nio.file.Path;
import java.util.*;

import static crispy.falling.Ui.t;

/**
 * Homes and open visits (2.15.3, from Stuckinchair's feedback).
 * - /island home: back to your island (the same as the menu's Go home).
 * - /island sethome: any island member moves the island's spawn spot (plots[id].home) to where they stand. /island home,
 *   respawns and visitors all land there (p/home2 in the datapack).
 * - /sethome [name], /home [name], /delhome <name>, /homes: up to MAX personal homes, only on your own island (its
 *   overworld, its Nether or its End). /home waits 3 s like /tpa (cancelled if you move).
 * - /island visit <player>: go to anyone's island, online or not, unless its members made it private with
 *   /island public off (then ask with /visit while they're online). Visitors get a visitor's pass (Visits.pass) and
 *   can't touch anything, as before. Islands are public unless plots[id].private is set.
 */
final class IslandHomes {
    private IslandHomes() {}

    static final int MAX = 3;
    static final Path FILE = Path.of("config", "crispy_skyblock_homes.json");
    static final Gson GSON = new GsonBuilder().setPrettyPrinting().create();
    static final ResourceKey<Level> END = ResourceKey.create(net.minecraft.core.registries.Registries.DIMENSION,
            Identifier.fromNamespaceAndPath(SkyblockMod.NS, "end"));

    record Home(String dim, double x, double y, double z, float yaw, float pitch) {}
    static Map<String, Map<String, Home>> homes;   // player UUID -> name -> home

    static Map<String, Map<String, Home>> homes() {
        if (homes == null) {
            homes = new HashMap<>();
            try {
                if (Files.exists(FILE)) {
                    Map<String, Map<String, Home>> m = GSON.fromJson(Files.readString(FILE), new TypeToken<Map<String, Map<String, Home>>>() {}.getType());
                    if (m != null) homes.putAll(m);
                }
            } catch (Exception e) { System.err.println("[crispy_skyblock] couldn't read " + FILE + ": " + e); }
        }
        return homes;
    }

    static void save() {
        try {
            Files.createDirectories(FILE.getParent());
            Path tmp = FILE.resolveSibling(FILE.getFileName() + ".tmp");
            Files.writeString(tmp, GSON.toJson(homes()));
            Files.move(tmp, FILE, java.nio.file.StandardCopyOption.REPLACE_EXISTING, java.nio.file.StandardCopyOption.ATOMIC_MOVE);
        } catch (Exception e) { System.err.println("[crispy_skyblock] couldn't save " + FILE + ": " + e); }
    }

    // ------------------------------------------------------------------ commands
    /** The /island (and /is) sub-commands: home, sethome, visit, public. */
    static void island(LiteralArgumentBuilder<CommandSourceStack> root) {
        root.then(Commands.literal("home").executes(c -> islandHome(c.getSource())))
            .then(Commands.literal("sethome").executes(c -> setIslandHome(c.getSource())))
            .then(Commands.literal("visit").then(Commands.argument("player", StringArgumentType.word()).suggests(Visits::suggestIslanders)
                    .executes(c -> visit(c.getSource(), StringArgumentType.getString(c, "player")))))
            .then(Commands.literal("public").executes(c -> setPublic(c.getSource(), null))
                    .then(Commands.literal("on").executes(c -> setPublic(c.getSource(), true)))
                    .then(Commands.literal("off").executes(c -> setPublic(c.getSource(), false))));
    }

    static void register(CommandDispatcher<CommandSourceStack> d) {
        com.mojang.brigadier.suggestion.SuggestionProvider<CommandSourceStack> mine = (c, b) -> {
            ServerPlayer p = c.getSource().getPlayer();
            return SharedSuggestionProvider.suggest(p == null ? List.of() : homes().getOrDefault(p.getUUID().toString(), Map.of()).keySet(), b);
        };
        d.register(Commands.literal("sethome").executes(c -> setHome(c.getSource(), "home"))
                .then(Commands.argument("name", StringArgumentType.word()).executes(c -> setHome(c.getSource(), StringArgumentType.getString(c, "name")))));
        d.register(Commands.literal("home").executes(c -> home(c.getSource(), null))
                .then(Commands.argument("name", StringArgumentType.word()).suggests(mine).executes(c -> home(c.getSource(), StringArgumentType.getString(c, "name")))));
        d.register(Commands.literal("delhome").then(Commands.argument("name", StringArgumentType.word()).suggests(mine)
                .executes(c -> delHome(c.getSource(), StringArgumentType.getString(c, "name")))));
        d.register(Commands.literal("homes").executes(c -> list(c.getSource())));
    }

    // ------------------------------------------------------------------ the island's spawn spot
    static int islandHome(CommandSourceStack s) throws com.mojang.brigadier.exceptions.CommandSyntaxException {
        ServerPlayer p = s.getPlayerOrException();
        Visits.run(s.getServer(), "execute as " + p.getScoreboardName() + " at @s run function " + SkyblockMod.NS + ":act/home");
        return 1;
    }

    static int setIslandHome(CommandSourceStack s) throws com.mojang.brigadier.exceptions.CommandSyntaxException {
        ServerPlayer p = s.getPlayerOrException();
        MinecraftServer server = s.getServer();
        int id = SkyblockMod.plot(server, p);
        if (id <= 0) { s.sendFailure(t("You don't have an island yet.", ChatFormatting.RED)); return 0; }
        if (!inside(server, id, p.level(), p.getX(), p.getZ()) || p.level().dimension() != Level.OVERWORLD) {
            s.sendFailure(t("Stand on your island (not its Nether or End) to set its spawn spot.", ChatFormatting.RED)); return 0;
        }
        if (!p.onGround()) { s.sendFailure(t("Stand on solid ground first.", ChatFormatting.RED)); return 0; }
        Visits.run(server, String.format(Locale.ROOT, "data modify storage %s:d plots[%d].home set value {x:%.2fd,y:%.2fd,z:%.2fd,yaw:%.1ff}",
                SkyblockMod.NS, id, p.getX(), p.getY(), p.getZ(), p.getYRot()));
        p.sendSystemMessage(t("Island spawn set here. /island home, respawns and visitors now land on this spot.", ChatFormatting.GREEN));
        return 1;
    }

    // ------------------------------------------------------------------ personal homes
    /** Is (x, z) in dimension `level` part of island id: its overworld square, its Nether square, or its End square. */
    static boolean inside(MinecraftServer server, int id, Level level, double x, double z) {
        CompoundTag r = Upgrades.rec(server, id);
        if (r.isEmpty()) return false;
        var dim = level.dimension();
        if (dim == Level.OVERWORLD || dim == END)
            return x >= r.getIntOr("x", 0) && x < r.getIntOr("x1", 0) + 1 && z >= r.getIntOr("z", 0) && z < r.getIntOr("z1", 0) + 1;
        if (dim == Level.NETHER)
            return x >= r.getIntOr("nx", 0) && x < r.getIntOr("nx1", 0) + 1 && z >= r.getIntOr("nz", 0) && z < r.getIntOr("nz1", 0) + 1;
        return false;
    }

    static int setHome(CommandSourceStack s, String name) throws com.mojang.brigadier.exceptions.CommandSyntaxException {
        ServerPlayer p = s.getPlayerOrException();
        MinecraftServer server = s.getServer();
        int id = SkyblockMod.plot(server, p);
        if (id <= 0 || !inside(server, id, p.level(), p.getX(), p.getZ())) {
            s.sendFailure(t("Homes can only be set on your own island (or its Nether or End).", ChatFormatting.RED)); return 0;
        }
        name = name.toLowerCase(Locale.ROOT);
        if (!name.matches("[a-z0-9_-]{1,16}")) { s.sendFailure(t("Home names are 1-16 letters, numbers, - or _.", ChatFormatting.RED)); return 0; }
        Map<String, Home> mine = homes().computeIfAbsent(p.getUUID().toString(), k -> new LinkedHashMap<>());
        if (!mine.containsKey(name) && mine.size() >= MAX) {
            s.sendFailure(t("You already have " + MAX + " homes (" + String.join(", ", mine.keySet()) + "). /delhome one first.", ChatFormatting.RED)); return 0;
        }
        mine.put(name, new Home(p.level().dimension().identifier().toString(), p.getX(), p.getY(), p.getZ(), p.getYRot(), p.getXRot()));
        save();
        p.sendSystemMessage(t("Home \"" + name + "\" set. /home " + (name.equals("home") ? "" : name) + "takes you back.", ChatFormatting.GREEN));
        return 1;
    }

    static int home(CommandSourceStack s, String name) throws com.mojang.brigadier.exceptions.CommandSyntaxException {
        ServerPlayer p = s.getPlayerOrException();
        MinecraftServer server = s.getServer();
        Map<String, Home> mine = homes().getOrDefault(p.getUUID().toString(), Map.of());
        if (mine.isEmpty()) { s.sendFailure(t("You have no homes yet. Stand on your island and /sethome [name].", ChatFormatting.RED)); return 0; }
        if (name == null) name = mine.containsKey("home") ? "home" : mine.size() == 1 ? mine.keySet().iterator().next() : null;
        if (name == null) { s.sendFailure(t("Which one? " + String.join(", ", mine.keySet()), ChatFormatting.RED)); return 0; }
        Home h = mine.get(name.toLowerCase(Locale.ROOT));
        if (h == null) { s.sendFailure(t("No home called " + name + ". Yours: " + String.join(", ", mine.keySet()), ChatFormatting.RED)); return 0; }
        ServerLevel level = server.getLevel(ResourceKey.create(net.minecraft.core.registries.Registries.DIMENSION, Identifier.parse(h.dim())));
        int id = SkyblockMod.plot(server, p);
        if (level == null || id <= 0 || !inside(server, id, level, h.x(), h.z())) {
            s.sendFailure(t("That home isn't on your island any more.", ChatFormatting.RED)); return 0;
        }
        String n = name;
        Visits.travel(p, () -> {
            Visits.pass(server, p, 0);
            p.teleportTo(level, h.x(), h.y(), h.z(), Set.of(), h.yaw(), h.pitch(), true);
        }, "home (" + n + ")");
        return 1;
    }

    static int delHome(CommandSourceStack s, String name) throws com.mojang.brigadier.exceptions.CommandSyntaxException {
        ServerPlayer p = s.getPlayerOrException();
        Map<String, Home> mine = homes().getOrDefault(p.getUUID().toString(), new HashMap<>());
        if (mine.remove(name.toLowerCase(Locale.ROOT)) == null) { s.sendFailure(t("No home called " + name + ".", ChatFormatting.RED)); return 0; }
        save();
        p.sendSystemMessage(t("Home \"" + name + "\" deleted.", ChatFormatting.GRAY));
        return 1;
    }

    static int list(CommandSourceStack s) throws com.mojang.brigadier.exceptions.CommandSyntaxException {
        ServerPlayer p = s.getPlayerOrException();
        Map<String, Home> mine = homes().getOrDefault(p.getUUID().toString(), Map.of());
        p.sendSystemMessage(t("Homes (" + mine.size() + "/" + MAX + "): " + (mine.isEmpty() ? "none yet, /sethome [name] on your island" : String.join(", ", mine.keySet())), ChatFormatting.AQUA));
        return 1;
    }

    // ------------------------------------------------------------------ open visits
    static boolean isPrivate(MinecraftServer server, int id) { return Upgrades.rec(server, id).getBooleanOr("private", false); }

    static int setPublic(CommandSourceStack s, Boolean on) throws com.mojang.brigadier.exceptions.CommandSyntaxException {
        ServerPlayer p = s.getPlayerOrException();
        MinecraftServer server = s.getServer();
        int id = SkyblockMod.plot(server, p);
        if (id <= 0) { s.sendFailure(t("You don't have an island yet.", ChatFormatting.RED)); return 0; }
        if (on == null) {
            p.sendSystemMessage(t("Your island is " + (isPrivate(server, id) ? "private: only people you allow with /visit can come."
                    : "public: anyone can /island visit it (they can look, not touch).") + " /island public on|off", ChatFormatting.AQUA));
            return 1;
        }
        Visits.run(server, on ? "data remove storage " + SkyblockMod.NS + ":d plots[" + id + "].private"
                : "data modify storage " + SkyblockMod.NS + ":d plots[" + id + "].private set value 1b");
        p.sendSystemMessage(t(on ? "Your island is public: anyone can /island visit it (they can look around but not touch anything)."
                : "Your island is private: people can only visit when you allow their /visit request.", ChatFormatting.GREEN));
        return 1;
    }

    /** The island a player name belongs to, online or not (their cs_plot score). */
    static int islandOf(MinecraftServer server, String name) {
        ServerPlayer online = server.getPlayerList().getPlayerByName(name);
        if (online != null) return SkyblockMod.plot(server, online);
        var obj = server.getScoreboard().getObjective("cs_plot");
        if (obj == null) return 0;
        for (var e : server.getScoreboard().listPlayerScores(obj))
            if (e.owner().equalsIgnoreCase(name)) return e.value();
        return 0;
    }

    static int visit(CommandSourceStack s, String name) throws com.mojang.brigadier.exceptions.CommandSyntaxException {
        ServerPlayer me = s.getPlayerOrException();
        MinecraftServer server = s.getServer();
        int id = islandOf(server, name);
        if (id <= 0) { s.sendFailure(t(name + " doesn't have an island.", ChatFormatting.RED)); return 0; }
        if (id == SkyblockMod.plot(server, me)) return islandHome(s);
        if (isPrivate(server, id)) {
            s.sendFailure(t(name + "'s island is private. Ask with /visit " + name + " while they're online.", ChatFormatting.RED)); return 0;
        }
        Visits.travel(me, () -> {
            Visits.pass(server, me, id);
            Visits.run(server, "execute as " + me.getScoreboardName() + " run function " + SkyblockMod.NS + ":p/home2 with storage " + SkyblockMod.NS + ":d plots[" + id + "]");
            me.sendSystemMessage(t("Welcome to " + name + "'s island! You can look around, but not build or open anything. /island home takes you back.", ChatFormatting.AQUA));
            for (ServerPlayer m : server.getPlayerList().getPlayers())
                if (m != me && SkyblockMod.plot(server, m) == id) m.sendSystemMessage(t(me.getScoreboardName() + " is visiting your island.", ChatFormatting.GRAY));
        }, "to " + name + "'s island");
        return 1;
    }
}

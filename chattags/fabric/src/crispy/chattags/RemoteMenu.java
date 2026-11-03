package crispy.chattags;

import com.google.gson.JsonArray;
import com.google.gson.JsonElement;
import com.google.gson.JsonObject;
import com.google.gson.JsonParser;
import com.mojang.brigadier.CommandDispatcher;
import com.mojang.serialization.JsonOps;
import net.minecraft.commands.CommandSourceStack;
import net.minecraft.commands.Commands;
import net.minecraft.core.Holder;
import net.minecraft.core.registries.BuiltInRegistries;
import net.minecraft.network.chat.Component;
import net.minecraft.network.chat.ComponentSerialization;
import net.minecraft.network.protocol.game.ClientboundSoundPacket;
import net.minecraft.resources.Identifier;
import net.minecraft.resources.RegistryOps;
import net.minecraft.server.MinecraftServer;
import net.minecraft.server.level.ServerPlayer;
import net.minecraft.sounds.SoundEvent;
import net.minecraft.sounds.SoundSource;
import net.minecraft.world.SimpleContainer;
import net.minecraft.world.SimpleMenuProvider;
import net.minecraft.world.entity.player.Inventory;
import net.minecraft.world.entity.player.Player;
import net.minecraft.world.inventory.ChestMenu;
import net.minecraft.world.inventory.ContainerInput;
import net.minecraft.world.inventory.MenuType;
import net.minecraft.world.item.ItemStack;

import java.net.URI;
import java.net.URLEncoder;
import java.net.http.HttpClient;
import java.net.http.HttpRequest;
import java.net.http.HttpResponse;
import java.nio.charset.StandardCharsets;
import java.time.Duration;
import java.util.Locale;

/**
 * /vote and /cosmetics right here: the lobby's CrispyLobby builds the menu (RemoteMenus, localhost HTTP) and this
 * draws it as a chest, sends clicks back and shows whatever comes back (the next menu, chat lines, sounds). The
 * menus and all the data stay in the lobby. Not while in combat (Combat). Port: -Dcrispy.lobbyapi=25599.
 */
public final class RemoteMenu {
    private RemoteMenu() {}

    static final String BASE = "http://127.0.0.1:" + Integer.getInteger("crispy.lobbyapi", 25599);
    static final HttpClient HTTP = HttpClient.newBuilder().connectTimeout(Duration.ofSeconds(2)).build();
    @SuppressWarnings("unchecked")
    private static final MenuType<ChestMenu>[] TYPES = new MenuType[]{MenuType.GENERIC_9x1, MenuType.GENERIC_9x2,
            MenuType.GENERIC_9x3, MenuType.GENERIC_9x4, MenuType.GENERIC_9x5, MenuType.GENERIC_9x6};

    public static void register(CommandDispatcher<CommandSourceStack> d) {
        d.register(Commands.literal("vote").executes(c -> run(c.getSource(), "vote"))
                .then(Commands.literal("links").executes(c -> run(c.getSource(), "links")))
                .then(Commands.literal("top").executes(c -> run(c.getSource(), "top"))));
        d.register(Commands.literal("cosmetics").executes(c -> run(c.getSource(), "cosmetics")));
    }

    private static int run(CommandSourceStack src, String cmd) {
        ServerPlayer p = src.getPlayer();
        if (p == null) { src.sendSystemMessage(Component.literal("Run this in game.")); return 0; }
        Long until = Combat.until.get(p.getGameProfile().name().toLowerCase(Locale.ROOT));
        if (until != null && until > System.currentTimeMillis() || p.entityTags().stream().anyMatch(Combat.FIGHT_TAGS::contains)) {
            p.sendSystemMessage(Component.literal("You can't use /" + (cmd.equals("cosmetics") ? "cosmetics" : "vote") + " in combat.").withStyle(s -> s.withColor(0xFF5555)));
            return 0;
        }
        request(p, "/open?cmd=" + cmd);
        return 1;
    }

    static void request(ServerPlayer p, String pathAndQuery) {
        MinecraftServer server = p.level().getServer();
        String sep = pathAndQuery.contains("?") ? "&" : "?";
        String url = BASE + pathAndQuery + sep + "uuid=" + p.getUUID() + "&name=" + URLEncoder.encode(p.getGameProfile().name(), StandardCharsets.UTF_8);
        HTTP.sendAsync(HttpRequest.newBuilder(URI.create(url)).timeout(Duration.ofSeconds(6)).GET().build(), HttpResponse.BodyHandlers.ofString())
                .whenComplete((res, err) -> server.execute(() -> {
                    if (p.hasDisconnected()) return;
                    if (err != null || res.statusCode() != 200) {
                        p.sendSystemMessage(Component.literal("Vote and cosmetics menus are unavailable right now (the lobby isn't answering). Try again soon.")
                                .withStyle(s -> s.withColor(0xFF5555)));
                        if (p.containerMenu instanceof Chest) p.closeContainer();
                        return;
                    }
                    apply(server, p, JsonParser.parseString(res.body()).getAsJsonObject());
                }));
    }

    private static void apply(MinecraftServer server, ServerPlayer p, JsonObject r) {
        RegistryOps<JsonElement> ops = server.registryAccess().createSerializationContext(JsonOps.INSTANCE);
        for (JsonElement m : r.getAsJsonArray("messages"))
            p.sendSystemMessage(ComponentSerialization.CODEC.parse(ops, m).result().orElse(Component.empty()));
        for (JsonElement s : r.getAsJsonArray("sounds")) {
            JsonObject so = s.getAsJsonObject();
            Identifier id = Identifier.tryParse(so.get("id").getAsString());
            if (id == null) continue;
            BuiltInRegistries.SOUND_EVENT.get(id).ifPresent(h -> p.connection.send(new ClientboundSoundPacket((Holder<SoundEvent>) h, SoundSource.MASTER,
                    p.getX(), p.getY(), p.getZ(), so.get("volume").getAsFloat(), so.get("pitch").getAsFloat(), p.getRandom().nextLong())));
        }
        if (!r.has("open")) { if (p.containerMenu instanceof Chest) p.closeContainer(); return; }
        JsonObject o = r.getAsJsonObject("open");
        int rows = Math.max(1, Math.min(6, o.get("rows").getAsInt()));
        Component title = ComponentSerialization.CODEC.parse(ops, o.get("title")).result().orElse(Component.literal("Menu"));
        ItemStack[] items = new ItemStack[rows * 9];
        JsonArray arr = o.getAsJsonArray("items");
        for (JsonElement e : arr) {
            JsonObject eo = e.getAsJsonObject();
            int slot = eo.get("slot").getAsInt();
            if (slot >= 0 && slot < items.length) items[slot] = ItemStack.CODEC.parse(ops, eo.get("item")).result().orElse(ItemStack.EMPTY);
        }
        // same menu size and title: refresh it in place (keeps the cursor where it is); otherwise open the new one
        if (p.containerMenu instanceof Chest c && c.rows == rows && c.title.equals(title)) {
            for (int i = 0; i < items.length; i++) c.box.setItem(i, items[i] == null ? ItemStack.EMPTY : items[i]);
            c.broadcastChanges();
            return;
        }
        SimpleContainer box = new SimpleContainer(rows * 9);
        for (int i = 0; i < items.length; i++) if (items[i] != null) box.setItem(i, items[i]);
        MenuType<ChestMenu> type = TYPES[rows - 1];
        p.openMenu(new SimpleMenuProvider((id, inv, pl) -> new Chest(type, id, inv, box, rows, title, server), title));
    }

    static final class Chest extends ChestMenu {
        final SimpleContainer box; final int rows; final Component title; final MinecraftServer server;
        Chest(MenuType<ChestMenu> type, int id, Inventory inv, SimpleContainer box, int rows, Component title, MinecraftServer server) {
            super(type, id, inv, box, rows);
            this.box = box; this.rows = rows; this.title = title; this.server = server;
        }

        @Override
        public void clicked(int slot, int button, ContainerInput input, Player player) {
            if (player instanceof ServerPlayer sp && slot >= 0 && slot < rows * 9 && (input == ContainerInput.PICKUP || input == ContainerInput.QUICK_MOVE))
                request(sp, "/click?slot=" + slot + "&shift=" + (input == ContainerInput.QUICK_MOVE ? 1 : 0));
            sendAllDataToRemote();   // undo whatever the client predicted
        }

        @Override
        public void removed(Player player) {
            super.removed(player);
            if (player instanceof ServerPlayer sp) server.execute(() -> {   // not when it was just replaced by the next menu
                if (!(sp.containerMenu instanceof Chest) && !sp.hasDisconnected())
                    HTTP.sendAsync(HttpRequest.newBuilder(URI.create(BASE + "/close?uuid=" + sp.getUUID())).timeout(Duration.ofSeconds(3)).GET().build(),
                            HttpResponse.BodyHandlers.discarding());
            });
        }

        @Override
        public ItemStack quickMoveStack(Player player, int slot) { return ItemStack.EMPTY; }

        @Override
        public boolean stillValid(Player player) { return true; }
    }
}

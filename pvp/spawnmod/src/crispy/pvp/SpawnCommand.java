package crispy.pvp;

import com.mojang.brigadier.arguments.IntegerArgumentType;
import com.mojang.brigadier.arguments.StringArgumentType;
import net.fabricmc.api.ModInitializer;
import net.fabricmc.fabric.api.command.v2.CommandRegistrationCallback;
import net.fabricmc.fabric.api.event.lifecycle.v1.ServerTickEvents;
import net.minecraft.commands.CommandSourceStack;
import net.minecraft.commands.Commands;
import net.minecraft.ChatFormatting;
import net.minecraft.nbt.CompoundTag;
import net.minecraft.nbt.ListTag;
import net.minecraft.network.chat.Component;

/**
 * /spawn and /lobby run the datapack's "/trigger pvp.spawn" (which keeps its 10 s combat lock).
 * /pvpmenu <name> opens a chest menu from storage pvp:menus (see PvpMenus).
 * Lobby leaderboards are refreshed by Leaderboards (top kills, best streak, best Outbreak wave).
 * /pvpkit create|delete|list (ops) manages admin-made kits; "pvpkit give <id>" is used by the datapack (see PvpKits).
 */
public class SpawnCommand implements ModInitializer {
    @Override
    public void onInitialize() {
        ServerTickEvents.END_SERVER_TICK.register(Leaderboards::onTick);
        CommandRegistrationCallback.EVENT.register((dispatcher, context, selection) -> {
            for (String name : new String[]{"spawn", "lobby"}) {
                dispatcher.register(Commands.literal(name).requires(CommandSourceStack::isPlayer).executes(c -> {
                    CommandSourceStack s = c.getSource();
                    s.getServer().getCommands().performPrefixedCommand(s.withSuppressedOutput(), "trigger pvp.spawn");
                    return 1;
                }));
            }
            // no requires(isPlayer) here: datapack functions use it, and they're parsed with a non-player source
            dispatcher.register(Commands.literal("pvpmenu")
                    .then(Commands.argument("name", StringArgumentType.word()).executes(c -> {
                        CommandSourceStack s = c.getSource();
                        String key = StringArgumentType.getString(c, "name");
                        if (!PvpMenus.open(s.getServer(), s.getPlayerOrException(), key))
                            s.sendFailure(Component.literal("No menu called " + key));
                        return 1;
                    })));
            dispatcher.register(Commands.literal("pvpkit").requires(Commands.hasPermission(Commands.LEVEL_GAMEMASTERS))
                    .then(Commands.literal("create").then(Commands.argument("name", StringArgumentType.greedyString()).executes(c -> {
                        CommandSourceStack s = c.getSource();
                        String name = StringArgumentType.getString(c, "name").trim();
                        if (name.isEmpty() || name.length() > 32) { s.sendFailure(Component.literal("Kit names are 1-32 characters.")); return 0; }
                        int id = PvpKits.create(s.getServer(), s.getPlayerOrException(), name);
                        if (id < 0) { s.sendFailure(Component.literal("There are already " + PvpKits.MAX_KITS + " custom kits; delete one first (/pvpkit list).")); return 0; }
                        CompoundTag saved = PvpKits.find(s.getServer(), id);
                        ListTag implants = saved == null ? new ListTag() : saved.getListOrEmpty("implants");
                        int items = saved == null ? 0 : saved.getListOrEmpty("items").size();
                        StringBuilder names = new StringBuilder();
                        for (int i = 0; i < implants.size(); i++) names.append(i == 0 ? "" : ", ").append(implants.getStringOr(i, "?"));
                        s.sendSuccess(() -> Component.literal("Saved kit \"" + name + "\" (id " + id + "): " + items + " items, "
                                + (implants.isEmpty() ? "no cyberware" : "cyberware: " + names) + ". It's in the Kit Dealer and Outbreak menus.")
                                .withStyle(ChatFormatting.GREEN), true);
                        if (implants.isEmpty())
                            s.sendSuccess(() -> Component.literal("No implants were installed on you. To add cyberware: /function cyber:admin/give, hold right-click "
                                    + "on each implant to install it (/trigger cyber to check), then run /pvpkit create " + name + " again.").withStyle(ChatFormatting.YELLOW), false);
                        return id;
                    })))
                    .then(Commands.literal("delete").then(Commands.argument("id", IntegerArgumentType.integer()).executes(c -> {
                        CommandSourceStack s = c.getSource();
                        int id = IntegerArgumentType.getInteger(c, "id");
                        if (!PvpKits.delete(s.getServer(), id)) { s.sendFailure(Component.literal("No custom kit with id " + id)); return 0; }
                        s.sendSuccess(() -> Component.literal("Deleted custom kit " + id).withStyle(ChatFormatting.YELLOW), true);
                        return 1;
                    })))
                    .then(Commands.literal("list").executes(c -> {
                        CommandSourceStack s = c.getSource();
                        ListTag kits = PvpKits.all(s.getServer());
                        if (kits.isEmpty()) { s.sendSuccess(() -> Component.literal("No custom kits yet. Set up your inventory and run /pvpkit create <name>."), false); return 0; }
                        for (int i = 0; i < kits.size(); i++) {
                            CompoundTag k = kits.getCompoundOrEmpty(i);
                            String line = k.getIntOr("id", 0) + ": " + k.getStringOr("name", "?") + " (by " + k.getStringOr("by", "?") + ", "
                                    + k.getListOrEmpty("items").size() + " items, " + k.getListOrEmpty("implants").size() + " implants)";
                            s.sendSuccess(() -> Component.literal(line).withStyle(ChatFormatting.GOLD), false);
                        }
                        return kits.size();
                    }))
                    .then(Commands.literal("give").then(Commands.argument("id", IntegerArgumentType.integer()).executes(c -> {
                        CommandSourceStack s = c.getSource();
                        return PvpKits.give(s.getServer(), s.getPlayerOrException(), IntegerArgumentType.getInteger(c, "id")) ? 1 : 0;
                    }))));
        });
    }
}

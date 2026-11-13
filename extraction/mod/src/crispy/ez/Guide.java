package crispy.ez;

import net.fabricmc.fabric.api.command.v2.CommandRegistrationCallback;
import net.fabricmc.fabric.api.networking.v1.ServerPlayConnectionEvents;
import net.minecraft.ChatFormatting;
import net.minecraft.commands.Commands;
import net.minecraft.core.component.DataComponents;
import net.minecraft.nbt.CompoundTag;
import net.minecraft.network.chat.Component;
import net.minecraft.network.chat.MutableComponent;
import net.minecraft.server.level.ServerPlayer;
import net.minecraft.server.network.Filterable;
import net.minecraft.world.item.ItemStack;
import net.minecraft.world.item.Items;
import net.minecraft.world.item.component.CustomData;
import net.minecraft.world.item.component.WrittenBookContent;

import java.util.ArrayList;
import java.util.List;

import static crispy.ez.Ui.t;

/**
 * The Field Guide (1.8.21): a written book explaining every system, given once on a player's first visit and any time
 * with /guide (custom_data ez:guide; /guide doesn't hand out a second copy while you carry one).
 */
final class Guide {
    private Guide() {}

    static final String[][] PAGES = {
            {"FIELD GUIDE", "Extraction Zone\n\nDeploy, loot, and get out alive.\n\nLost this book? Type /guide."},
            {"RAIDS", "Right-click the helipad in camp to deploy. You have 25:00 to reach an extraction point (the flare columns, marked on your map) and hold it for 30 s.\n\nDie and you drop everything you carried."},
            {"THE RINGS", "Outskirts, middle ring, inner ring, the Core. The closer to the centre, the tougher the raiders and the better the loot. The Commander holds the Core.\n\nCrates refill every 10 minutes."},
            {"EXTRACTING", "Starting an extraction fires a flare: a wave of raiders comes for you, and a second one at the halfway mark.\n\nStep off the point and the count starts again."},
            {"DOWNED", "A fatal hit in the zone puts you down for 45 s.\n\nAnother player crouching beside you for 5 s gets you up. Any player can hit you instead to finish you off and take your gear."},
            {"SELF-REVIVE", "A Self-Revive Injector gets you up on your own: hold crouch for 3 s while downed.\n\nRare in inner ring and Core crates, or made at a Med Bench. You can carry one."},
            {"SQUADS", "Stand next to another raider and type /trigger truce. If they do the same within 30 s you're a squad.\n\nBetrayal is always possible."},
            {"LOGGING OUT", "Log out mid-raid and a stand-in of you stays where you stood, carrying your gear, and your timer keeps running.\n\nRaiders leave it alone. Players can kill it and take everything."},
            {"YOUR BUNKER", "/bunker, or the steps in camp. Store gear in Stash Crates.\n\nThe Builder sells stations: Sewing Table, Med Bench, Kiln, Reloading Bench, Still, Tool Bench and Salvage Bench."},
            {"SALVAGE", "At a Salvage Bench, break spare armour and guns into Cloth, Scrap, Wire, Gun Parts and Armour Plate.\n\nSell them to the Broker or craft with them."},
            {"TRADERS", "Quartermaster: guns, ammo, meds, armour.\nBuilder: blocks and stations.\nThe Broker: buys valuables.\nBunker Manager: your bunker.\nThe Fixer: contracts that pay extra."},
            {"TOOLS", "Grappling Hook: pulls you to a block.\nParachute: slow fall.\nSmoke Grenade: blocks raider gunfire.\nRope Ladder: climb out.\nRepair Kit: mends worn armour.\n\nCraft them at your stations."},
    };

    static ItemStack book() {
        List<Filterable<Component>> pages = new ArrayList<>();
        for (String[] pg : PAGES) {
            MutableComponent c = Component.literal(pg[0] + "\n\n").withStyle(ChatFormatting.DARK_RED, ChatFormatting.BOLD);
            c.append(Component.literal(pg[1]).withStyle(s -> s.withBold(false).withColor(ChatFormatting.BLACK)));
            pages.add(Filterable.passThrough(c));
        }
        ItemStack b = new ItemStack(Items.WRITTEN_BOOK);
        b.set(DataComponents.WRITTEN_BOOK_CONTENT, new WrittenBookContent(Filterable.passThrough("Field Guide"), "The Fixer", 0, pages, true));
        CompoundTag tag = new CompoundTag(); tag.putString("ez", "guide");
        b.set(DataComponents.CUSTOM_DATA, CustomData.of(tag));
        return b;
    }
    static boolean carries(ServerPlayer p) { return Shops.count(p, s -> "guide".equals(Shops.ezKey(s))) > 0; }
    static void give(ServerPlayer p, boolean tell) {
        if (carries(p)) { if (tell) p.sendSystemMessage(t("You already carry the Field Guide: right-click it to read.", ChatFormatting.GRAY)); return; }
        Shops.give(p, book());
        if (tell) p.sendSystemMessage(t("📖 Field Guide added to your inventory: right-click it to read.", ChatFormatting.GREEN));
    }

    static void init() {
        CommandRegistrationCallback.EVENT.register((d, ctx, env) -> d.register(Commands.literal("guide").executes(c -> {
            if (c.getSource().getEntity() instanceof ServerPlayer p) give(p, true);
            return 1;
        })));
        ServerPlayConnectionEvents.JOIN.register((h, sender, server) -> server.execute(() -> {
            ServerPlayer p = h.getPlayer();
            if (p.entityTags().contains("ez.guided")) return;
            p.addTag("ez.guided");
            give(p, false);
            p.sendSystemMessage(t("📖 Here's your Field Guide: it explains raids, revives, your bunker and more. /guide for a new copy.", ChatFormatting.GOLD));
        }));
    }
}

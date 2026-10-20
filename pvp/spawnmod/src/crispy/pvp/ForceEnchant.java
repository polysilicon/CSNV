package crispy.pvp;

import com.mojang.brigadier.CommandDispatcher;
import com.mojang.brigadier.arguments.IntegerArgumentType;
import net.minecraft.ChatFormatting;
import net.minecraft.commands.CommandBuildContext;
import net.minecraft.commands.CommandSourceStack;
import net.minecraft.commands.Commands;
import net.minecraft.commands.arguments.ResourceArgument;
import net.minecraft.core.Holder;
import net.minecraft.core.registries.Registries;
import net.minecraft.network.chat.Component;
import net.minecraft.server.level.ServerPlayer;
import net.minecraft.world.item.ItemStack;
import net.minecraft.world.item.enchantment.Enchantment;
import net.minecraft.world.item.enchantment.EnchantmentHelper;

/**
 * /forceenchant <enchantment> [level] (ops): puts any enchantment, vanilla or crispy_enchants, on the held item at
 * any level 1-255, ignoring which items it normally goes on, its max level and conflicts with other enchantments.
 * Level 0 removes it; "/forceenchant clear" strips all. Books get stored enchantments. Unlike /enchant it sets the
 * level exactly (can lower it). Alias /fe.
 */
final class ForceEnchant {
    static void register(CommandDispatcher<CommandSourceStack> d, CommandBuildContext ctx) {
        for (String name : new String[]{"forceenchant", "fe"}) {
            d.register(Commands.literal(name).requires(Commands.hasPermission(Commands.LEVEL_GAMEMASTERS))
                    .then(Commands.literal("clear").executes(c -> {
                        ItemStack it = held(c.getSource());
                        if (it == null) return 0;
                        EnchantmentHelper.updateEnchantments(it, m -> m.removeIf(h -> true));
                        c.getSource().sendSuccess(() -> Component.literal("Removed all enchantments from your item.").withStyle(ChatFormatting.YELLOW), false);
                        return 1;
                    }))
                    .then(Commands.argument("enchantment", ResourceArgument.resource(ctx, Registries.ENCHANTMENT))
                            .executes(c -> apply(c.getSource(), ResourceArgument.getEnchantment(c, "enchantment"), -1))
                            .then(Commands.argument("level", IntegerArgumentType.integer(0, 255))
                                    .executes(c -> apply(c.getSource(), ResourceArgument.getEnchantment(c, "enchantment"), IntegerArgumentType.getInteger(c, "level"))))));
        }
    }

    static ItemStack held(CommandSourceStack s) {
        ServerPlayer p = s.getPlayer();
        if (p == null) { s.sendFailure(Component.literal("Run this as a player, holding the item.")); return null; }
        ItemStack it = p.getMainHandItem();
        if (it.isEmpty()) { s.sendFailure(Component.literal("Hold the item you want to enchant.")); return null; }
        return it;
    }

    static int apply(CommandSourceStack s, Holder<Enchantment> e, int level) {
        ItemStack it = held(s);
        if (it == null) return 0;
        int lvl = level < 0 ? e.value().getMaxLevel() : level;     // no level given = the enchant's normal max
        EnchantmentHelper.updateEnchantments(it, m -> m.set(e, lvl));
        if (lvl == 0) s.sendSuccess(() -> Component.literal("Removed ").append(Enchantment.getFullname(e, 1)).withStyle(ChatFormatting.YELLOW), false);
        else s.sendSuccess(() -> Component.literal("Applied ").append(e.value().description().copy()).append(" " + lvl + " to your item.").withStyle(ChatFormatting.GREEN), false);
        return lvl;
    }
}

package crispy.chattags.mixin;

import com.mojang.brigadier.ParseResults;
import crispy.chattags.Combat;
import net.minecraft.commands.CommandSourceStack;
import net.minecraft.commands.Commands;
import net.minecraft.server.level.ServerPlayer;
import org.spongepowered.asm.mixin.Mixin;
import org.spongepowered.asm.mixin.injection.At;
import org.spongepowered.asm.mixin.injection.Inject;
import org.spongepowered.asm.mixin.injection.callback.CallbackInfo;

/** 1.10.0: commands listed in config/crispy_combat_block.txt are refused while the player is in combat. */
@Mixin(Commands.class)
public abstract class CombatCommandMixin {
    @Inject(method = "performCommand", at = @At("HEAD"), cancellable = true)
    private void crispy$combatBlock(ParseResults<CommandSourceStack> parse, String command, CallbackInfo ci) {
        if (parse.getContext().getSource().getEntity() instanceof ServerPlayer p && Combat.refuse(p, command)) ci.cancel();
    }
}

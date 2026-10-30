package crispy.anarchy;

import net.fabricmc.api.ModInitializer;
import net.fabricmc.fabric.api.event.player.UseEntityCallback;
import net.minecraft.server.level.ServerPlayer;
import net.minecraft.world.InteractionHand;
import net.minecraft.world.InteractionResult;
import net.minecraft.world.entity.Interaction;

/**
 * Crispy Anarchy: chest-menu shops for the market's Ripperdoc (crispy_cyberware) and Enchanter (crispy_enchants).
 * Right-clicking a vendor's interaction box (tag cy.doc / ce.enchanter) opens its menu instead of the datapack's
 * dialog; buying runs the datapack's own buy function, which checks you're near the vendor and takes the price.
 */
public final class AnarchyMod implements ModInitializer {
    @Override
    public void onInitialize() {
        UseEntityCallback.EVENT.register((player, world, hand, entity, hit) -> {
            if (!(entity instanceof Interaction) || !(player instanceof ServerPlayer p)) return InteractionResult.PASS;
            boolean doc = entity.entityTags().contains("cy.doc"), ench = entity.entityTags().contains("ce.enchanter");
            if (!doc && !ench) return InteractionResult.PASS;
            if (hand == InteractionHand.MAIN_HAND) { if (doc) Shops.ripperdoc(p); else Shops.enchanter(p); }
            return InteractionResult.SUCCESS;
        });
    }
}

package crispy.ez;

import net.fabricmc.api.ModInitializer;

/** Crispy Extraction Zone: chest-menu traders (Shops), player plots (Plots), the Lost Cities zone and game modes (Zone). */
public final class EzMod implements ModInitializer {
    @Override public void onInitialize() {
        Coins.init();
        Shops.init();
        Plots.init();
        Zone.init();
        Relief.init();
        Workbench.init();   // after Plots: its use-block hook runs after the plot protection's
        Raid.init();
        Contracts.init();
        Boss.init();
        Events.init();
        Reset.init();
    }
}

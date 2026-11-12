package crispy.ez;

import net.fabricmc.api.ModInitializer;

/** Crispy Extraction Zone: chest-menu traders (Shops), player plots (Plots), the Lost Cities zone and game modes (Zone). */
public final class EzMod implements ModInitializer {
    @Override public void onInitialize() {
        Shops.init();
        Plots.init();
        Zone.init();
    }
}

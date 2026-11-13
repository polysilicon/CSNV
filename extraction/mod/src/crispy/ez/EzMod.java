package crispy.ez;

import net.fabricmc.api.ModInitializer;

/** Crispy Extraction Zone: chest-menu traders (Shops), player plots (Plots), the Lost Cities zone and game modes (Zone). */
public final class EzMod implements ModInitializer {
    @Override public void onInitialize() {
        Trace.init();        // first: it logs every click before any handler acts on it
        Flow.init();         // 1.6.0: right after the tracer, so a click is noted before a handler marks it handled
        Armor.init();         // 1.7.0 milsim armour: set bonuses, vanilla armour swapped
        Stations.init();      // 1.8.0 bunker crafting stations
        Tools.init();         // 1.8.0 grappling hook, repair kit, smoke
        Coins.init();
        Shops.init();
        Plots.init();
        Zone.init();
        Relief.init();
        Workbench.init();
        Storage.init();   // after Plots: its use-block hook runs after the plot protection's
        Raid.init();
        Contracts.init();
        Boss.init();
        Events.init();
        Reset.init();
        SelfTest.init();
    }
}

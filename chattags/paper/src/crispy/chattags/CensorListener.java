package crispy.chattags;

import io.papermc.paper.event.player.AsyncChatEvent;
import net.kyori.adventure.text.Component;
import net.kyori.adventure.text.serializer.plain.PlainTextComponentSerializer;
import org.bukkit.event.EventHandler;
import org.bukkit.event.EventPriority;
import org.bukkit.event.Listener;
import org.bukkit.event.block.SignChangeEvent;
import org.bukkit.event.inventory.PrepareAnvilEvent;
import org.bukkit.event.player.PlayerCommandPreprocessEvent;
import org.bukkit.event.player.PlayerEditBookEvent;
import org.bukkit.inventory.ItemStack;
import org.bukkit.inventory.meta.BookMeta;
import org.bukkit.inventory.meta.ItemMeta;

import java.util.ArrayList;
import java.util.List;
import java.util.Set;

/** Slur filter (1.7.0): listed words are starred (Censor, the same list and matching as the Discord bot and the
 *  Fabric mod) in chat, private-message commands, signs, books and anvil names. Chat is starred first (LOWEST), so
 *  the colour and tag passes work on the clean text. */
final class CensorListener implements Listener {
    static final PlainTextComponentSerializer PLAIN = PlainTextComponentSerializer.plainText();
    /** Commands whose arguments are a message to other players (Essentials and vanilla names). */
    static final Set<String> MSG = Set.of("msg", "tell", "w", "whisper", "m", "pm", "dm", "t", "r", "reply", "me", "say",
            "mail", "emsg", "etell", "ewhisper", "er", "ereply", "eme", "broadcast", "bc", "helpop", "ac", "f", "fac", "factions");

    @SuppressWarnings("deprecation")
    @EventHandler(priority = EventPriority.LOWEST)
    public void legacyChat(org.bukkit.event.player.AsyncPlayerChatEvent e) {
        String c = Censor.apply(e.getMessage());
        if (c != e.getMessage()) e.setMessage(c);
    }

    @EventHandler(priority = EventPriority.LOWEST)
    public void chat(AsyncChatEvent e) {
        String text = PLAIN.serialize(e.message()), c = Censor.apply(text);
        if (c != text) e.message(Component.text(c));
    }

    @EventHandler(priority = EventPriority.LOWEST)
    public void command(PlayerCommandPreprocessEvent e) {
        String m = e.getMessage();
        int sp = m.indexOf(' ');
        if (sp < 0) return;
        String cmd = m.substring(1, sp).toLowerCase();
        int colon = cmd.indexOf(':');
        if (colon >= 0) cmd = cmd.substring(colon + 1);
        if (!MSG.contains(cmd)) return;
        String args = m.substring(sp), c = Censor.apply(args);
        if (c != args) e.setMessage(m.substring(0, sp) + c);
    }

    @EventHandler(priority = EventPriority.LOWEST)
    public void sign(SignChangeEvent e) {
        for (int i = 0; i < e.lines().size(); i++) {
            Component line = e.line(i);
            if (line == null) continue;
            String t = PLAIN.serialize(line), c = Censor.apply(t);
            if (c != t) e.line(i, Component.text(c));
        }
    }

    @EventHandler(priority = EventPriority.LOWEST)
    public void book(PlayerEditBookEvent e) {
        BookMeta meta = e.getNewBookMeta();
        boolean changed = false;
        List<Component> pages = new ArrayList<>();
        for (Component p : meta.pages()) {
            String t = PLAIN.serialize(p), c = Censor.apply(t);
            if (c != t) { changed = true; pages.add(Component.text(c)); } else pages.add(p);
        }
        if (changed) meta.pages(pages);
        if (meta.hasTitle()) {
            String t = meta.getTitle(), c = Censor.apply(t);
            if (c != t) { meta.setTitle(c); changed = true; }
        }
        if (changed) e.setNewBookMeta(meta);
    }

    @EventHandler(priority = EventPriority.HIGHEST)
    public void anvil(PrepareAnvilEvent e) {
        String name = e.getView().getRenameText();
        if (name == null || name.isEmpty()) return;
        String c = Censor.apply(name);
        ItemStack result = e.getResult();
        if (c == name || result == null || result.isEmpty()) return;
        result = result.clone();
        ItemMeta m = result.getItemMeta();
        m.displayName(Component.text(c));
        result.setItemMeta(m);
        e.setResult(result);
    }
}

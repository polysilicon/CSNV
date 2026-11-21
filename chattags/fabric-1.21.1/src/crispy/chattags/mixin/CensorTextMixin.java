package crispy.chattags.mixin;

import crispy.chattags.Censor;
import net.minecraft.server.network.FilteredText;
import net.minecraft.server.network.ServerGamePacketListenerImpl;
import org.spongepowered.asm.mixin.Mixin;
import org.spongepowered.asm.mixin.injection.At;
import org.spongepowered.asm.mixin.injection.ModifyVariable;

import java.util.ArrayList;
import java.util.List;

/** Signs and books: listed slurs are starred before the text is stored, so it never ends up in the world. */
@Mixin(ServerGamePacketListenerImpl.class)
public abstract class CensorTextMixin {
    @ModifyVariable(method = "updateSignText", at = @At("HEAD"), argsOnly = true)
    private List<FilteredText> crispy$sign(List<FilteredText> lines) { return clean(lines); }

    @ModifyVariable(method = "updateBookContents", at = @At("HEAD"), argsOnly = true)
    private List<FilteredText> crispy$bookPages(List<FilteredText> pages) { return clean(pages); }

    @ModifyVariable(method = "signBook", at = @At("HEAD"), argsOnly = true)
    private List<FilteredText> crispy$signedPages(List<FilteredText> pages) { return clean(pages); }

    @ModifyVariable(method = "signBook", at = @At("HEAD"), argsOnly = true)
    private FilteredText crispy$title(FilteredText title) { return clean(title); }

    private static FilteredText clean(FilteredText t) {
        if (t == null) return null;
        String c = Censor.apply(t.raw());
        return c == t.raw() ? t : FilteredText.passThrough(c);
    }

    private static List<FilteredText> clean(List<FilteredText> list) {
        if (list == null) return null;
        List<FilteredText> out = null;
        for (int i = 0; i < list.size(); i++) {
            FilteredText t = list.get(i), c = clean(t);
            if (c != t && out == null) out = new ArrayList<>(list);
            if (out != null) out.set(i, c);
        }
        return out == null ? list : out;
    }
}

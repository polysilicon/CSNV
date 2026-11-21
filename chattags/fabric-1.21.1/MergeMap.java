import net.fabricmc.mappingio.*;
import net.fabricmc.mappingio.adapter.*;
import net.fabricmc.mappingio.format.MappingFormat;
import net.fabricmc.mappingio.tree.MemoryMappingTree;
import java.nio.file.*;
import java.util.Map;
/** intermediary (official->intermediary) + Mojang ProGuard (named->official) => one tiny v2 with official, intermediary, named. */
public class MergeMap {
    public static void main(String[] a) throws Exception {
        MemoryMappingTree tree = new MemoryMappingTree();
        MappingReader.read(Path.of(a[0]), MappingFormat.TINY_2_FILE, tree);
        MappingReader.read(Path.of(a[1]), MappingFormat.PROGUARD_FILE,
                new MappingNsRenamer(new MappingSourceNsSwitch(tree, "official"), Map.of("source", "named", "target", "official")));
        try (MappingWriter w = MappingWriter.create(Path.of(a[2]), MappingFormat.TINY_2_FILE)) { tree.accept(w); }
        System.out.println("namespaces: " + tree.getSrcNamespace() + " " + tree.getDstNamespaces() + ", classes " + tree.getClasses().size());
    }
}

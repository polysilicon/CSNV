package crispy.ez;

import com.google.gson.Gson;
import com.google.gson.reflect.TypeToken;
import net.minecraft.server.level.ServerPlayer;

import java.nio.file.Files;
import java.nio.file.Path;
import java.time.LocalDate;
import java.time.temporal.IsoFields;
import java.util.HashMap;
import java.util.Map;

/** Weekly sell limits (1.8.0): how many of a capped item (farm produce) each player sold this ISO week. */
final class Market {
    private Market() {}
    static final Path FILE = Path.of("config", "crispy_extraction", "market.json");
    static final class Data { String week; Map<String, Map<String, Integer>> sold = new HashMap<>(); }
    static Data data;

    static String week() { LocalDate d = LocalDate.now(); return d.get(IsoFields.WEEK_BASED_YEAR) + "-W" + d.get(IsoFields.WEEK_OF_WEEK_BASED_YEAR); }
    static Data data() {
        if (data == null) {
            try { if (Files.exists(FILE)) data = new Gson().fromJson(Files.readString(FILE), new TypeToken<Data>() {}.getType()); } catch (Exception ignored) {}
            if (data == null) data = new Data();
        }
        if (!week().equals(data.week)) { data.week = week(); data.sold.clear(); }
        return data;
    }
    static int sold(ServerPlayer p, String key) { return data().sold.getOrDefault(p.getUUID().toString(), Map.of()).getOrDefault(key, 0); }
    static void add(ServerPlayer p, String key, int n) {
        data().sold.computeIfAbsent(p.getUUID().toString(), k -> new HashMap<>()).merge(key, n, Integer::sum);
        try { Files.createDirectories(FILE.getParent()); Files.writeString(FILE, new Gson().toJson(data)); } catch (Exception ignored) {}
    }
}

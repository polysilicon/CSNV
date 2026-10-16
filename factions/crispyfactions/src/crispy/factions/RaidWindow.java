package crispy.factions;

import org.bukkit.configuration.ConfigurationSection;

import java.time.*;
import java.util.*;

/** Prime-time raid schedule. Windows are per weekday, in the configured time zone; "24:00" means end of day. */
public class RaidWindow {
    record Slot(LocalTime start, LocalTime end, boolean toMidnight) {}

    final ZoneId zone;
    final Map<DayOfWeek, List<Slot>> slots = new EnumMap<>(DayOfWeek.class);
    String force = "auto"; // auto | open | closed

    RaidWindow(ConfigurationSection c) {
        zone = ZoneId.of(c.getString("timezone", "America/New_York"));
        ConfigurationSection days = c.getConfigurationSection("windows");
        for (DayOfWeek d : DayOfWeek.values()) {
            List<Slot> list = new ArrayList<>();
            if (days != null) for (String s : days.getStringList(d.name().toLowerCase(Locale.ROOT))) {
                String[] p = s.split("-");
                boolean mid = p[1].trim().equals("24:00");
                list.add(new Slot(LocalTime.parse(p[0].trim()), mid ? LocalTime.MAX : LocalTime.parse(p[1].trim()), mid));
            }
            slots.put(d, list);
        }
    }

    ZonedDateTime now() { return ZonedDateTime.now(zone); }

    boolean scheduledOpen(ZonedDateTime t) {
        for (Slot s : slots.get(t.getDayOfWeek())) {
            LocalTime lt = t.toLocalTime();
            if (!lt.isBefore(s.start) && (s.toMidnight || lt.isBefore(s.end))) return true;
        }
        return false;
    }

    boolean isOpen() {
        if (force.equals("open")) return true;
        if (force.equals("closed")) return false;
        return scheduledOpen(now());
    }

    /** Next scheduled opening strictly after t (ignores the force override). */
    ZonedDateTime nextOpen(ZonedDateTime t) {
        ZonedDateTime best = null;
        for (int d = 0; d <= 8; d++) {
            LocalDate day = t.toLocalDate().plusDays(d);
            for (Slot s : slots.get(day.getDayOfWeek())) {
                ZonedDateTime st = day.atTime(s.start).atZone(zone);
                // a slot that runs on from yesterday's midnight-ending slot is the same window, not a new opening
                if (st.isAfter(t) && (best == null || st.isBefore(best)) && !scheduledOpen(st.minusMinutes(1))) best = st;
            }
        }
        return best;
    }

    /** When the current scheduled window closes (only meaningful while open). */
    ZonedDateTime closesAt(ZonedDateTime t) {
        ZonedDateTime x = t.withSecond(0).withNano(0);
        for (int i = 0; i < 60 * 48 && scheduledOpen(x); i++) x = x.plusMinutes(1);
        return x;
    }
}

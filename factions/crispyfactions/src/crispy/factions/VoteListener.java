package crispy.factions;

import com.vexsoftware.votifier.model.Vote;
import com.vexsoftware.votifier.model.VotifierEvent;
import org.bukkit.Bukkit;
import org.bukkit.event.EventHandler;
import org.bukkit.event.Listener;

/** Kept separate so CrispyFactions still loads when NuVotifier isn't installed. */
public class VoteListener implements Listener {
    final Votes votes;
    VoteListener(Votes votes) { this.votes = votes; }

    @EventHandler
    public void onVote(VotifierEvent e) {
        Vote v = e.getVote();
        String user = v.getUsername(), service = v.getServiceName();
        if (user == null || user.isBlank()) return;
        if (Bukkit.isPrimaryThread()) votes.receive(user.trim(), service);
        else Bukkit.getScheduler().runTask(votes.plugin, () -> votes.receive(user.trim(), service));
    }
}

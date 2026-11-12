package crispy.tags;

import com.velocitypowered.api.event.Subscribe;
import com.velocitypowered.api.event.connection.ConnectionHandshakeEvent;
import com.velocitypowered.proxy.connection.client.InitialInboundConnection;
import com.velocitypowered.proxy.network.Connections;
import com.velocitypowered.proxy.protocol.packet.PluginMessagePacket;
import io.netty.buffer.ByteBuf;
import io.netty.buffer.Unpooled;
import io.netty.channel.Channel;
import io.netty.channel.ChannelHandlerContext;
import io.netty.channel.ChannelInboundHandlerAdapter;

import java.nio.charset.StandardCharsets;
import java.util.ArrayList;
import java.util.HashSet;
import java.util.List;
import java.util.Set;

/**
 * 1.11.0: clients with big mod packs register more plugin-message channels than Paper allows (128 per player): the
 * lobby throws "Too many channels registered!" and kicks them with "Invalid custom payload payload!", so they can never
 * get in. This sits in every client connection, before Velocity's own handler, and passes on at most MAX channel
 * registrations per connection (vanilla, proxy and our own namespaces first); the rest are dropped. Nothing else
 * changes: the Fabric servers don't need the extra mod channels either (they only matter for client mods' own servers).
 */
final class ChannelCap {
    static final int MAX = 100;
    static final String[] FIRST = {"minecraft:", "velocity:", "bungeecord", "crispy", "fabric", "c:", "geyser", "floodgate", "voicechat"};

    final CrispyTags plugin;
    ChannelCap(CrispyTags plugin) { this.plugin = plugin; }

    @Subscribe public void onHandshake(ConnectionHandshakeEvent e) {
        if (!(e.getConnection() instanceof InitialInboundConnection ic)) return;
        Channel ch = ic.getConnection().getChannel();
        ch.eventLoop().execute(() -> {
            try {
                if (ch.pipeline().get(Connections.HANDLER) != null && ch.pipeline().get("crispy-channel-cap") == null)
                    ch.pipeline().addBefore(Connections.HANDLER, "crispy-channel-cap", new Cap());
            } catch (Exception ex) { plugin.log.warn("channel cap: couldn't add to the pipeline: {}", ex.toString()); }
        });
    }

    static int rank(String c) {
        for (int i = 0; i < FIRST.length; i++) if (c.startsWith(FIRST[i])) return i;
        return FIRST.length;
    }

    final class Cap extends ChannelInboundHandlerAdapter {
        final Set<String> kept = new HashSet<>();
        int dropped;
        boolean logged;

        @Override public void channelRead(ChannelHandlerContext ctx, Object msg) throws Exception {
            if (msg instanceof PluginMessagePacket p && ("minecraft:register".equals(p.getChannel()) || "REGISTER".equals(p.getChannel()))) {
                ByteBuf buf = p.content();
                String all = buf.toString(buf.readerIndex(), buf.readableBytes(), StandardCharsets.UTF_8);
                List<String> chans = new ArrayList<>();
                for (String c : all.split("\0")) if (!c.isEmpty()) chans.add(c);
                chans.sort((a, b) -> Integer.compare(rank(a), rank(b)));   // stable: keeps the client's order within a rank
                List<String> pass = new ArrayList<>();
                for (String c : chans) {
                    if (kept.contains(c)) { pass.add(c); continue; }
                    if (kept.size() < MAX) { kept.add(c); pass.add(c); } else dropped++;
                }
                if (pass.size() < chans.size()) {
                    if (!logged) {
                        logged = true;
                        plugin.log.info("[channels] {} registers more than {} plugin channels (a big mod pack); passing {} on, dropping the rest so the lobby doesn't kick it",
                                ctx.channel().remoteAddress(), MAX, MAX);
                    }
                    if (pass.isEmpty()) { p.release(); return; }
                    PluginMessagePacket trimmed = p.replace(Unpooled.copiedBuffer(String.join("\0", pass), StandardCharsets.UTF_8));
                    p.release();
                    ctx.fireChannelRead(trimmed);
                    return;
                }
            }
            super.channelRead(ctx, msg);
        }
    }
}

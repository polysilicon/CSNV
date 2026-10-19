package crispy.lobby;

import java.io.*;
import java.net.InetSocketAddress;
import java.net.Socket;
import java.nio.ByteBuffer;
import java.nio.ByteOrder;
import java.nio.charset.StandardCharsets;
import java.nio.file.Files;
import java.nio.file.Path;
import java.util.Properties;

/** Minimal Source-RCON client: one connection per backend, reconnects after a failure. Used from a single thread.
 *  The port and password are read from the backend's own server.properties and never logged. */
final class Rcon implements Closeable {
    final String label; final Path props;
    private Socket sock; private DataInputStream in; private OutputStream out; private int id;

    Rcon(String label, Path props) { this.label = label; this.props = props; }

    synchronized String cmd(String command) throws IOException {
        if (sock == null || sock.isClosed()) connect();
        try { return send(2, command); } catch (IOException e) { close(); throw e; }
    }

    private void connect() throws IOException {
        Properties p = new Properties();
        try (Reader r = Files.newBufferedReader(props)) { p.load(r); }
        if (!"true".equalsIgnoreCase(p.getProperty("enable-rcon", "false").trim())) throw new IOException(label + ": RCON is disabled");
        int port = Integer.parseInt(p.getProperty("rcon.port", "25575").trim());
        sock = new Socket();
        sock.connect(new InetSocketAddress("127.0.0.1", port), 3000);
        sock.setSoTimeout(5000);
        in = new DataInputStream(new BufferedInputStream(sock.getInputStream()));
        out = sock.getOutputStream();
        try { send(3, p.getProperty("rcon.password", "")); } catch (IOException e) { close(); throw e; }
    }

    private String send(int type, String body) throws IOException {
        byte[] b = body.getBytes(StandardCharsets.UTF_8);
        int rid = ++id;
        ByteBuffer bb = ByteBuffer.allocate(14 + b.length).order(ByteOrder.LITTLE_ENDIAN);
        bb.putInt(10 + b.length).putInt(rid).putInt(type).put(b).put((byte) 0).put((byte) 0);
        out.write(bb.array()); out.flush();
        int len = Integer.reverseBytes(in.readInt());
        if (len < 10 || len > 1 << 20) throw new IOException(label + ": bad RCON packet");
        byte[] pk = new byte[len]; in.readFully(pk);
        int got = ByteBuffer.wrap(pk).order(ByteOrder.LITTLE_ENDIAN).getInt();
        if (got == -1) throw new IOException(label + ": RCON login refused");
        return new String(pk, 8, len - 10, StandardCharsets.UTF_8);
    }

    @Override public synchronized void close() {
        try { if (sock != null) sock.close(); } catch (IOException ignored) {}
        sock = null;
    }
}

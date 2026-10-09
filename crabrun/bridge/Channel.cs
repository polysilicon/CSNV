// The live link with the CET mod while Cyberpunk runs (CET only lets Lua use files in its own mod folder):
//   io/events.txt  mod -> bridge  run events; each plays its Crab Champions sound
//   io/keys.txt    bridge -> mod  "<seq> <action> [char]" for sheet keys pressed while Cyberpunk is in front
//   io/alive.txt   bridge -> mod  heartbeat (unix seconds)
using System.Diagnostics;
using System.Runtime.InteropServices;
using System.Text.Json;
using NAudio.Wave;
using NAudio.Wave.SampleProviders;

namespace CrabRun;

public sealed class Channel : IDisposable
{
    readonly string io;
    readonly Sounds sounds;
    long eventsPos;
    int seq;
    readonly Dictionary<int, bool> down = new();

    public Channel(string modDir, string crabDir)
    {
        io = Path.Combine(modDir, "io");
        Directory.CreateDirectory(io);
        sounds = new Sounds(Path.Combine(crabDir, "crab_data.json"));
        var keys = Path.Combine(io, "keys.txt");
        // keep counting from the file so the mod never mistakes new presses for old ones
        if (File.Exists(keys))
            foreach (var l in File.ReadAllLines(keys))
                if (int.TryParse(l.Split(' ')[0], out var n)) seq = Math.Max(seq, n);
    }

    public void RunWhileGameAlive(TimeSpan startWait)
    {
        var start = DateTime.UtcNow;
        var lastBeat = DateTime.MinValue;
        var seen = false;
        while (true)
        {
            var alive = GameProcessIds().Count > 0 || File.Exists(Path.Combine(io, "fake_game_running"));  // test hook
            if (alive) seen = true;
            if (!alive && (seen || DateTime.UtcNow - start > startWait)) break;
            if (DateTime.UtcNow - lastBeat > TimeSpan.FromSeconds(1))
            {
                lastBeat = DateTime.UtcNow;
                TryWrite(Path.Combine(io, "alive.txt"), DateTimeOffset.UtcNow.ToUnixTimeSeconds().ToString());
            }
            PollEvents();
            PollKeys();
            Thread.Sleep(15);
        }
        sounds.StopMusic();
    }

    static HashSet<int> GameProcessIds() =>
        Process.GetProcessesByName("Cyberpunk2077").Select(p => p.Id).ToHashSet();

    void PollEvents()
    {
        var path = Path.Combine(io, "events.txt");
        try
        {
            using var fs = new FileStream(path, FileMode.OpenOrCreate, FileAccess.Read, FileShare.ReadWrite | FileShare.Delete);
            if (fs.Length < eventsPos) eventsPos = 0;      // the mod truncates it at start
            if (fs.Length == eventsPos) return;
            fs.Position = eventsPos;
            using var r = new StreamReader(fs);
            var text = r.ReadToEnd();
            var end = text.LastIndexOf('\n');
            if (end < 0) return;
            eventsPos += System.Text.Encoding.UTF8.GetByteCount(text[..(end + 1)]);
            foreach (var ev in text[..end].Split('\n', StringSplitOptions.RemoveEmptyEntries | StringSplitOptions.TrimEntries))
                sounds.Play(ev);
        }
        catch (IOException) { }
    }

    [DllImport("user32.dll")] static extern short GetAsyncKeyState(int vk);
    [DllImport("user32.dll")] static extern IntPtr GetForegroundWindow();
    [DllImport("user32.dll")] static extern uint GetWindowThreadProcessId(IntPtr hWnd, out uint pid);

    static bool GameInFront()
    {
        var h = GetForegroundWindow();
        if (h == IntPtr.Zero) return false;
        GetWindowThreadProcessId(h, out var pid);
        try { return Process.GetProcessById((int)pid).ProcessName.Equals("Cyberpunk2077", StringComparison.OrdinalIgnoreCase); }
        catch { return false; }
    }

    DateTime frontChecked = DateTime.MinValue;
    bool front;

    void PollKeys()
    {
        if (!OperatingSystem.IsWindows()) return;
        if (DateTime.UtcNow - frontChecked > TimeSpan.FromMilliseconds(250)) { front = GameInFront(); frontChecked = DateTime.UtcNow; }
        var lines = new List<string>();
        foreach (var vk in SheetData.Keys.Select(k => k.Vk).Distinct())
        {
            var isDown = front && (GetAsyncKeyState(vk) & 0x8000) != 0;
            down.TryGetValue(vk, out var was);
            down[vk] = isDown;
            if (!isDown || was) continue;
            foreach (var k in SheetData.Keys.Where(k => k.Vk == vk))
                lines.Add(k.Action == "seed_char" ? $"{++seq} {k.Action} {k.Key}" : $"{++seq} {k.Action}");
        }
        if (lines.Count > 0) TryAppend(Path.Combine(io, "keys.txt"), string.Join("\n", lines) + "\n");
    }

    static void TryWrite(string p, string s) { try { File.WriteAllText(p, s); } catch (IOException) { } }
    static void TryAppend(string p, string s)
    {
        for (var i = 0; i < 5; i++)
        {
            try { File.AppendAllText(p, s); return; } catch (IOException) { Thread.Sleep(5); }
        }
    }

    public void Dispose() => sounds.Dispose();
}

// Plays the Crab Champions sounds extracted from the player's paks through one mixer.
public sealed class Sounds : IDisposable
{
    readonly Dictionary<string, (float[] data, float volume, bool loop)> clips = new();
    readonly MixingSampleProvider mixer;
    readonly WaveOutEvent output;
    ISampleProvider music;
    static readonly WaveFormat Fmt = WaveFormat.CreateIeeeFloatWaveFormat(44100, 2);

    public Sounds(string dataJson)
    {
        mixer = new MixingSampleProvider(Fmt) { ReadFully = true };
        try
        {
            output = new WaveOutEvent { DesiredLatency = 120 };
            output.Init(mixer);
            output.Play();
        }
        catch (Exception e) { Log.Info("no audio output: " + e.Message); output = null; }
        if (!File.Exists(dataJson)) return;
        try
        {
            using var doc = JsonDocument.Parse(File.ReadAllText(dataJson));
            if (!doc.RootElement.TryGetProperty("sounds", out var snd)) return;
            foreach (var p in snd.EnumerateObject())
            {
                var file = p.Value.GetProperty("file").GetString();
                try { clips[p.Name] = (Load(file), p.Value.GetProperty("volume").GetSingle(), p.Value.GetProperty("loop").GetBoolean()); }
                catch (Exception e) { Log.Info($"sound {p.Name}: can't load {file}: {e.Message}"); }
            }
            Log.Info($"{clips.Count} Crab Champions sounds ready");
        }
        catch (Exception e) { Log.Info("crab_data.json unreadable: " + e.Message); }
    }

    public static float[] Load(string file)
    {
        ISampleProvider src;
        IDisposable owner;
        if (file.EndsWith(".ogg", StringComparison.OrdinalIgnoreCase))
        {
            var v = new NVorbis.VorbisReader(file);
            owner = v;
            src = new VorbisSampleProvider(v);
        }
        else
        {
            var r = new WaveFileReader(file);
            owner = r;
            src = r.WaveFormat.Encoding == WaveFormatEncoding.Pcm || r.WaveFormat.Encoding == WaveFormatEncoding.IeeeFloat
                ? r.ToSampleProvider()
                : WaveFormatConversionStream.CreatePcmStream(r).ToSampleProvider();
        }
        using (owner)
        {
            if (src.WaveFormat.Channels == 1) src = new MonoToStereoSampleProvider(src);
            if (src.WaveFormat.SampleRate != Fmt.SampleRate) src = new WdlResamplingSampleProvider(src, Fmt.SampleRate);
            var all = new List<float>();
            var buf = new float[Fmt.SampleRate * 2];
            int n;
            while ((n = src.Read(buf, 0, buf.Length)) > 0) all.AddRange(buf.AsSpan(0, n).ToArray());
            return all.ToArray();
        }
    }

    public void Play(string ev)
    {
        if (output == null) return;
        if (ev == "music_stop") { StopMusic(); return; }
        if (!clips.TryGetValue(ev, out var c)) return;
        if (c.loop)
        {
            StopMusic();
            music = new VolumeSampleProvider(new LoopingClip(c.data)) { Volume = c.volume };
            mixer.AddMixerInput(music);
        }
        else mixer.AddMixerInput(new VolumeSampleProvider(new Clip(c.data)) { Volume = c.volume });
    }

    public void StopMusic()
    {
        if (music != null) { mixer.RemoveMixerInput(music); music = null; }
    }

    public void Dispose() { output?.Dispose(); }

    sealed class Clip(float[] d) : ISampleProvider
    {
        int pos;
        public WaveFormat WaveFormat => Fmt;
        public int Read(float[] buffer, int offset, int count)
        {
            var n = Math.Min(count, d.Length - pos);
            if (n <= 0) return 0;
            Array.Copy(d, pos, buffer, offset, n);
            pos += n;
            return n;
        }
    }

    sealed class LoopingClip(float[] d) : ISampleProvider
    {
        int pos;
        public WaveFormat WaveFormat => Fmt;
        public int Read(float[] buffer, int offset, int count)
        {
            if (d.Length == 0) return 0;
            for (var i = 0; i < count; i++) { buffer[offset + i] = d[pos]; pos = (pos + 1) % d.Length; }
            return count;
        }
    }

    sealed class VorbisSampleProvider(NVorbis.VorbisReader r) : ISampleProvider
    {
        public WaveFormat WaveFormat { get; } = WaveFormat.CreateIeeeFloatWaveFormat(r.SampleRate, r.Channels);
        public int Read(float[] buffer, int offset, int count) => r.ReadSamples(buffer, offset, count);
    }
}

// CrabRunBridge: Melty starts this instead of the game.
//  1. reads Crab Champions' own perks, icons and sounds out of the player's installed paks (CrabExtract),
//  2. starts Cyberpunk 2077,
//  3. while it runs: plays the Crab sounds the CET mod asks for and relays the shop keys (Channel).
using System.Diagnostics;

namespace CrabRun;

public static class Program
{
    public static int Main(string[] args)
    {
        string game = Arg(args, "--game"), crab = Arg(args, "--crab");
        bool launch = !args.Contains("--no-launch"), extractOnly = args.Contains("--extract-only");
        if (game == null) { Console.Error.WriteLine("usage: CrabRunBridge --game <Cyberpunk 2077 folder> --crab <Crab Champions folder>"); return 2; }
        var modDir = Path.Combine(game, "bin", "x64", "plugins", "cyber_engine_tweaks", "mods", "CrabRun");
        Directory.CreateDirectory(Path.Combine(modDir, "io"));
        Log.Open(Path.Combine(modDir, "bridge.log"));
        Log.Info($"Crab Run bridge {SheetData.Version}; game={game}; crab={crab}");

        try
        {
            if (crab != null) CrabExtract.Run(crab, Path.Combine(modDir, "crab"));
            else Log.Info("no Crab Champions folder given (--crab); the mod falls back to sheet names");
        }
        catch (Exception e) { Log.Info("Crab Champions extraction failed: " + e); }
        if (extractOnly) return 0;

        Process proc = null;
        if (launch)
        {
            var exe = Path.Combine(game, "bin", "x64", "Cyberpunk2077.exe");
            if (!File.Exists(exe)) { Log.Info("Cyberpunk2077.exe not found at " + exe); return 3; }
            Log.Info("starting " + exe);
            proc = Process.Start(new ProcessStartInfo(exe, "-skipStartScreen") { WorkingDirectory = Path.GetDirectoryName(exe), UseShellExecute = false });
        }
        using var channel = new Channel(modDir, Path.Combine(modDir, "crab"));
        channel.RunWhileGameAlive(TimeSpan.FromSeconds(launch ? 90 : 5));
        Log.Info("Cyberpunk 2077 closed; bridge exiting");
        return 0;
    }

    static string Arg(string[] a, string name)
    {
        var i = Array.IndexOf(a, name);
        return i >= 0 && i + 1 < a.Length ? a[i + 1].TrimEnd('\\', '/', '"') : null;
    }
}

public static class Log
{
    static StreamWriter w;
    public static void Open(string path)
    {
        try { w = new StreamWriter(path, false) { AutoFlush = true }; } catch { }
    }
    public static void Info(string s)
    {
        var line = $"{DateTime.Now:HH:mm:ss} {s}";
        Console.WriteLine(line);
        try { w?.WriteLine(line); } catch { }
    }
}

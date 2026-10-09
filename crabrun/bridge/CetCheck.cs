// What we can tell about Cyber Engine Tweaks from outside the game, written to bridge.log so one file shows
// why the CET mod did or didn't run: is CET installed, which game version, and what CET itself logged.
using System.Diagnostics;

namespace CrabRun;

public sealed class CetCheck
{
    readonly string game, x64, cetDir, modLog;
    DateTime started;

    public CetCheck(string game)
    {
        this.game = game;
        x64 = Path.Combine(game, "bin", "x64");
        cetDir = Path.Combine(x64, "plugins", "cyber_engine_tweaks");
        modLog = Path.Combine(cetDir, "mods", "CrabRun", "CrabRun.log");
    }

    public void BeforeLaunch()
    {
        started = DateTime.Now;
        try
        {
            var exe = Path.Combine(x64, "Cyberpunk2077.exe");
            if (File.Exists(exe)) Log.Info($"Cyberpunk 2077 version {FileVersionInfo.GetVersionInfo(exe).FileVersion}");
        }
        catch { }
        foreach (var f in new[] { "version.dll", "global.ini", Path.Combine("plugins", "cyber_engine_tweaks.asi") })
            Log.Info($"CET file {f}: {(File.Exists(Path.Combine(x64, f)) ? "present" : "MISSING")}");
        Log.Info($"CrabRun init.lua: {(File.Exists(Path.Combine(cetDir, "mods", "CrabRun", "init.lua")) ? "present" : "MISSING")}");
    }

    public void AfterGame()
    {
        var ran = File.Exists(modLog) && File.GetLastWriteTime(modLog) >= started;
        Log.Info(ran ? "CET loaded Crab Run this session" : "CET did NOT load Crab Run this session (no fresh CrabRun.log)");
        Tail(Path.Combine(cetDir, "cyber_engine_tweaks.log"), 30);
        Tail(Path.Combine(cetDir, "scripting.log"), 30);
        Tail(modLog, 60);
    }

    static void Tail(string path, int n)
    {
        try
        {
            if (!File.Exists(path)) { Log.Info($"--- {Path.GetFileName(path)}: not found"); return; }
            using var fs = new FileStream(path, FileMode.Open, FileAccess.Read, FileShare.ReadWrite | FileShare.Delete);
            var lines = new StreamReader(fs).ReadToEnd().Split('\n');
            Log.Info($"--- last lines of {Path.GetFileName(path)} ({File.GetLastWriteTime(path):yyyy-MM-dd HH:mm}):");
            foreach (var l in lines.Skip(Math.Max(0, lines.Length - n))) if (l.Trim().Length > 0) Log.Info("    " + l.TrimEnd());
        }
        catch (Exception e) { Log.Info($"--- {Path.GetFileName(path)}: {e.Message}"); }
    }
}

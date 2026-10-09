// Bridge checks that run without the games: pak discovery and mounting, asset matching, sound decoding,
// and the event/key file channel. Real Crab Champions assets are checked on a PC that has the game.
using System.Diagnostics;
using CrabRun;

int pass = 0, fail = 0;
void Check(string n, bool c, string m = "") { if (c) pass++; else { fail++; Console.WriteLine($"FAIL {n} {m}"); } }
var root = Path.Combine(Path.GetTempPath(), "crabrun-bridge-test-" + Environment.ProcessId);
Directory.CreateDirectory(root);
var fixtures = args.Length > 0 ? args[0] : ".";

// --- asset matching
var paths = new List<string> {
    "crabchampions/content/ui/textures/t_crystal_icon.uasset", "crabchampions/content/fx/crystal_shard.uasset",
    "crabchampions/content/audio/sfx/sw_crystal_pickup.uasset", "crabchampions/content/audio/music/sw_music_island.uasset" };
var c1 = CrabExtract.Candidates(paths, new[] { "crystal", "icon" }, new[] { "crystal" }).ToList();
Check("art candidates prefer all keywords", c1[0].EndsWith("t_crystal_icon.uasset"), string.Join(",", c1));
Check("fallback keywords follow", c1.Count == 3);
Check("sound candidates", CrabExtract.Candidates(paths, new[] { "crystal", "pickup" }, new[] { "crystal" }).First().Contains("sw_crystal_pickup"));
Check("objpath", CrabExtract.ObjPath("a/b/da_perk_vitality.uasset") == "a/b/da_perk_vitality.da_perk_vitality");
Check("norm", CrabExtract.Norm("Speed Demon") == CrabExtract.Norm("speed_demon") && CrabExtract.Norm("SpeedDemon") == "speeddemon");

// --- perk text fields, as CrabPerkDA has them (bridge.log from the real game, 2026-10-09)
var pf = new CrabExtract.PerkFields();
foreach (var (k, v) in new (string, object)[] { ("PerkType", null), ("LevelDescription", "+10% max health"), ("BaseBuff", 0.1f),
         ("Name", "Vitality"), ("Description", "Increases max health."), ("Icon", null) })
    pf.Add(k, v);
Check("perk name from string Name", pf.Name == "Vitality", pf.Name ?? "null");
Check("perk description prefers Description over LevelDescription", pf.Desc == "Increases max health.", pf.Desc ?? "null");

// --- pak discovery + mount + resilience against unreadable assets (pak built by tools/make_test_pak.py)
var crab = Path.Combine(root, "Crab Champions");
var paks = Path.Combine(crab, "CrabChampions", "Content", "Paks");
Directory.CreateDirectory(paks);
File.Copy(Path.Combine(fixtures, "test.pak"), Path.Combine(paks, "CrabChampions-WindowsNoEditor.pak"));
Check("find paks", CrabExtract.FindPaks(crab) == paks, CrabExtract.FindPaks(crab));
Check("no paks", CrabExtract.FindPaks(Path.Combine(root, "nothing")) == null);
var mod = Path.Combine(root, "mod");
Log.Open(Path.Combine(root, "log.txt"));
CrabExtract.Run(crab, Path.Combine(mod, "crab"));
var log = File.ReadAllText(Path.Combine(root, "log.txt"));
Check("mounted", log.Contains("mounted 1 pak(s)"), log);
Check("found perk assets", log.Contains("2 DA_Perk assets"), log);
Check("bad asset noted, no crash", log.Contains("perk Vitality:") || log.Contains("note: perk Vitality"), log);
// the fixture is zlib-compressed: its garbage bytes must come back intact for the magic check to report them
Check("zlib entries decompressed (managed)", log.Contains("Invalid uasset magic"), log);
Check("data written", File.Exists(Path.Combine(mod, "crab", "crab_data.json")));
Check("asset list written", File.ReadAllText(Path.Combine(mod, "crab", "assets.txt")).Contains("da_perk_vitality"));

// --- sounds decode (files made with ffmpeg by the test script)
var ogg = Sounds.Load(Path.Combine(fixtures, "beep.ogg"));
var wav = Sounds.Load(Path.Combine(fixtures, "beep_mono_22k.wav"));
Check("ogg decoded to 44.1k stereo", Math.Abs(ogg.Length - 44100 * 2 * 0.5) < 44100 * 0.1, ogg.Length.ToString());
Check("mono 22k wav resampled", Math.Abs(wav.Length - 44100 * 2 * 0.5) < 44100 * 0.1, wav.Length.ToString());
Check("audio not silent", ogg.Max() > 0.05f && wav.Max() > 0.05f, $"{ogg.Max()} {wav.Max()}");

// --- channel: reads the mod's events while the "game" runs, stops when it closes
var io = Path.Combine(mod, "io");
Directory.CreateDirectory(io);
File.WriteAllText(Path.Combine(io, "fake_game_running"), "");
File.WriteAllText(Path.Combine(io, "keys.txt"), "41 buy1\n");
using (var ch = new Channel(mod, Path.Combine(mod, "crab")))
{
    var t = new Thread(() => ch.RunWhileGameAlive(TimeSpan.FromSeconds(1)));
    t.Start();
    File.AppendAllText(Path.Combine(io, "events.txt"), "crystal\nbuy\n");
    Thread.Sleep(1500);
    Check("heartbeat", File.Exists(Path.Combine(io, "alive.txt")) &&
        Math.Abs(long.Parse(File.ReadAllText(Path.Combine(io, "alive.txt"))) - DateTimeOffset.UtcNow.ToUnixTimeSeconds()) < 3);
    File.Delete(Path.Combine(io, "fake_game_running"));
    Check("exits when game closes", t.Join(3000));
}
Directory.Delete(root, true);
Console.WriteLine($"{pass} passed, {fail} failed");
return fail == 0 ? 0 : 1;

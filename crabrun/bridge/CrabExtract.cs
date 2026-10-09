// Reads Crab Champions' real content from the player's own install (Unreal Engine 4.27 .pak files):
// each perk's name, description and icon (DA_Perk_<key> data assets), the crystal icon and the sounds the
// run uses. Writes them next to the CET mod as crab/crab_data.json, crab/icons/*.png and crab/sounds/*.
// Nothing from Crab Champions ships with Crab Run; this runs on the player's PC from their copy.
using System.Text.Json;
using CUE4Parse.Compression;
using CUE4Parse.FileProvider;
using CUE4Parse.UE4.Assets.Exports;
using CUE4Parse.UE4.Assets.Exports.Sound;
using CUE4Parse.UE4.Assets.Exports.Texture;
using CUE4Parse.UE4.Assets.Objects;
using CUE4Parse.UE4.Objects.Core.i18N;
using CUE4Parse.UE4.Objects.UObject;
using CUE4Parse.UE4.Versions;
using CUE4Parse_Conversion.Sounds;
using CUE4Parse_Conversion.Textures;
using CUE4Parse_Conversion.Options;

namespace CrabRun;

public static class CrabExtract
{
    public const int FormatVersion = 1;

    public static string FindPaks(string crabDir)
    {
        if (!Directory.Exists(crabDir)) return null;
        var paks = Directory.EnumerateFiles(crabDir, "*.pak", new EnumerationOptions { RecurseSubdirectories = true, MaxRecursionDepth = 5, IgnoreInaccessible = true })
            .Where(p => !Path.GetFileName(p).StartsWith("CrabRun", StringComparison.OrdinalIgnoreCase)).ToList();
        // the game's own Content/Paks folder (mods sit in Paks/~mods and are mounted too, which is fine)
        return paks.Select(Path.GetDirectoryName).Where(d => d.EndsWith("Paks", StringComparison.OrdinalIgnoreCase))
                   .OrderBy(d => d.Length).FirstOrDefault() ?? paks.Select(Path.GetDirectoryName).FirstOrDefault();
    }

    static string Fingerprint(string paksDir)
    {
        var parts = Directory.EnumerateFiles(paksDir, "*.*", SearchOption.AllDirectories)
            .Where(f => f.EndsWith(".pak") || f.EndsWith(".utoc") || f.EndsWith(".ucas"))
            .OrderBy(f => f).Select(f => { var i = new FileInfo(f); return $"{i.Name}:{i.Length}:{i.LastWriteTimeUtc.Ticks}"; });
        return $"v{FormatVersion}|{SheetData.Version}|" + string.Join("|", parts);
    }

    public static void Run(string crabDir, string outDir)
    {
        var paksDir = FindPaks(crabDir);
        if (paksDir == null) { Log.Info($"no .pak files under {crabDir}"); return; }
        Directory.CreateDirectory(outDir);
        var fpPath = Path.Combine(outDir, "fingerprint.txt");
        var fp = Fingerprint(paksDir);
        if (File.Exists(fpPath) && File.ReadAllText(fpPath) == fp && File.Exists(Path.Combine(outDir, "crab_data.json")))
        {
            Log.Info("Crab Champions content already extracted for this game version");
            return;
        }
        Log.Info("reading Crab Champions paks in " + paksDir);
        var sw = System.Diagnostics.Stopwatch.StartNew();
        var result = Extract(paksDir, outDir);
        File.WriteAllText(Path.Combine(outDir, "crab_data.json"), JsonSerializer.Serialize(result, new JsonSerializerOptions { WriteIndented = true }));
        if (result.ok) File.WriteAllText(fpPath, fp);
        Log.Info($"extraction done in {sw.Elapsed.TotalSeconds:F1}s: {result.perks.Count} perks, {result.sounds.Count} sounds, ok={result.ok}");
    }

    public class Result
    {
        public bool ok { get; set; }
        public string source { get; set; }
        public Dictionary<string, PerkOut> perks { get; set; } = new();
        public Dictionary<string, string> art { get; set; } = new();
        public Dictionary<string, SoundOut> sounds { get; set; } = new();
        public List<string> notes { get; set; } = new();
    }
    public class PerkOut { public string name { get; set; } public string desc { get; set; } public string icon { get; set; } public string asset { get; set; } [System.Text.Json.Serialization.JsonIgnore] public string seen; }
    public class SoundOut { public string file { get; set; } public string asset { get; set; } public float volume { get; set; } public bool loop { get; set; } }

    public static string Norm(string s) => new string(s.ToLowerInvariant().Where(char.IsLetterOrDigit).ToArray());

    static Result Extract(string paksDir, string outDir)
    {
        var res = new Result { source = paksDir };
        var provider = new DefaultFileProvider(paksDir, SearchOption.AllDirectories, new VersionContainer(EGame.GAME_UE4_27), StringComparer.OrdinalIgnoreCase);
        provider.Initialize();
        var mounted = provider.Mount();
        Log.Info($"mounted {mounted} pak(s), {provider.Files.Count} files; {provider.RequiredKeys.Count} need an AES key");
        if (provider.Files.Count == 0) { res.notes.Add("paks could not be read (encrypted?)"); return res; }

        var files = provider.Files.Keys.Select(k => k.ToLowerInvariant()).ToList();   // match on lower case; the provider is case-insensitive
        var uassets = files.Where(f => f.EndsWith(".uasset")).ToList();
        File.WriteAllLines(Path.Combine(outDir, "assets.txt"), uassets.Where(f =>
            f.Contains("/da_perk") || f.Contains("sound") || f.Contains("audio") || f.Contains("music") || f.Contains("crystal")).OrderBy(f => f));

        // ---- perks
        var iconDir = Path.Combine(outDir, "icons");
        Directory.CreateDirectory(iconDir);
        var perkAssets = uassets.Where(f => Path.GetFileNameWithoutExtension(f).StartsWith("da_perk_")).ToList();
        Log.Info($"{perkAssets.Count} DA_Perk assets in the paks");
        foreach (var row in SheetData.Perks)
        {
            var want = Norm(row.Key);
            var path = perkAssets.FirstOrDefault(f => Norm(Path.GetFileNameWithoutExtension(f)["da_perk_".Length..]) == want)
                    ?? perkAssets.FirstOrDefault(f => Norm(Path.GetFileNameWithoutExtension(f)).Contains(want));
            if (path == null) { res.notes.Add($"perk {row.Key}: no DA_Perk asset"); continue; }
            try
            {
                var p = ReadPerk(provider, path, iconDir, row.Key);
                if (p.name != null) { res.perks[row.Key] = p; Log.Info($"perk {row.Key}: '{p.name}' icon={p.icon != null} ({path})"); }
                else res.notes.Add($"perk {row.Key}: no name text in {path}; properties seen: {p.seen}");
            }
            catch (Exception e) { res.notes.Add($"perk {row.Key}: {e.Message}"); }
        }

        // ---- art
        var artDir = Path.Combine(outDir, "art");
        Directory.CreateDirectory(artDir);
        foreach (var a in SheetData.Art)
        {
            foreach (var path in Candidates(uassets, a.Keywords, a.FallbackKeywords).Take(12))
            {
                try
                {
                    if (provider.TryLoadPackageObject<UTexture2D>(ObjPath(path), out var tex) && tex != null)
                    {
                        var png = SavePng(tex, Path.Combine(artDir, a.Id + ".png"));
                        if (png) { res.art[a.Id] = $"crab/art/{a.Id}.png"; Log.Info($"art {a.Id}: {path}"); break; }
                    }
                }
                catch { }
            }
        }

        // ---- sounds
        var sndDir = Path.Combine(outDir, "sounds");
        Directory.CreateDirectory(sndDir);
        var usedSounds = new HashSet<string>();
        foreach (var s in SheetData.Sounds)
        {
            foreach (var path in Candidates(uassets, s.Keywords, s.FallbackKeywords).Where(p => !usedSounds.Contains(p)).Take(25))
            {
                try
                {
                    if (!provider.TryLoadPackageObject<USoundWave>(ObjPath(path), out var wave) || wave == null) continue;
                    wave.Decode(true, out var fmt, out var data);
                    if (data == null) continue;
                    var ext = fmt.ToUpperInvariant() switch { "OGG" => "ogg", "WAV" => "wav", "ADPCM" => "wav", _ => null };
                    if (ext == null) { res.notes.Add($"sound {s.Event}: {path} is {fmt}, not playable"); continue; }
                    var file = Path.Combine(sndDir, s.Event + "." + ext);
                    File.WriteAllBytes(file, data);
                    usedSounds.Add(path);
                    res.sounds[s.Event] = new SoundOut { file = file, asset = path, volume = s.Volume, loop = s.Loop };
                    Log.Info($"sound {s.Event}: {path} ({fmt})");
                    break;
                }
                catch (Exception e) { res.notes.Add($"sound {s.Event}: {path}: {e.Message}"); }
            }
            if (!res.sounds.ContainsKey(s.Event)) res.notes.Add($"sound {s.Event}: no match");
        }
        if (res.sounds.Count == 0 && files.Any(f => f.EndsWith(".wem") || f.EndsWith(".bnk")))
            res.notes.Add("this build keeps its audio in Wwise banks, which Crab Run can't play yet");

        foreach (var n in res.notes) Log.Info("note: " + n);
        res.ok = res.perks.Count > 0;
        return res;
    }

    // asset paths whose words contain every keyword (else every fallback keyword), shortest first
    public static IEnumerable<string> Candidates(List<string> paths, string[] kw, string[] fallback)
    {
        static bool All(string p, string[] k) => k.Length > 0 && k.All(x => p.Contains(x.ToLowerInvariant()));
        var a = paths.Where(p => All(p, kw)).OrderBy(p => p.Length);
        var b = paths.Where(p => !All(p, kw) && All(p, fallback)).OrderBy(p => p.Length);
        return a.Concat(b);
    }

    // "crabchampions/content/x/y.uasset" -> "crabchampions/content/x/y.y"
    public static string ObjPath(string file)
    {
        var noExt = file[..file.LastIndexOf('.')];
        return noExt + "." + Path.GetFileName(noExt);
    }

    static PerkOut ReadPerk(IFileProvider provider, string path, string iconDir, string key)
    {
        var exports = provider.LoadPackage(path).GetExports().ToList();
        var main = Path.GetFileNameWithoutExtension(path);
        var obj = exports.FirstOrDefault(e => e.Name.Equals(main, StringComparison.OrdinalIgnoreCase)) ?? exports.FirstOrDefault();
        if (obj == null) return new PerkOut { seen = "no exports" };
        var p = new PerkOut { asset = path };
        UTexture2D icon = null;
        string name = null, nameLoose = null, desc = null, descLoose = null;
        var seen = new List<string>();
        Walk(obj.Properties, 0, (name, value) =>
        {
            var n = name.ToLowerInvariant();
            if (seen.Count < 30) seen.Add($"{name}:{value?.GetType().Name}");
            // Crab Champions keeps Name/Description as plain strings (CrabPerkDA), other builds may use FText
            var text = value switch { FText t => t.Text, string str => str, _ => null };
            if (!string.IsNullOrWhiteSpace(text))
            {
                if (n == "description") desc = text;
                else if (n.Contains("desc")) descLoose ??= text;
                else if (n == "name" || n == "displayname") name = text;
                else if (n.Contains("name") || n.Contains("title")) nameLoose ??= text;
                return;
            }
            switch (value)
            {
                case FPackageIndex idx when icon == null && !idx.IsNull:
                    if (idx.TryLoad<UTexture2D>(out var tex)) icon = tex;
                    break;
                case FSoftObjectPath sp when icon == null && !sp.AssetPathName.IsNone:
                    if (sp.TryLoad<UTexture2D>(out var stex)) icon = stex;
                    break;
            }
        });
        p.seen = $"{obj.ExportType} [" + string.Join(", ", seen) + "]";
        p.name = name ?? nameLoose;
        p.desc = desc ?? descLoose;
        if (p.name == null) return p;
        if (icon != null && SavePng(icon, Path.Combine(iconDir, key + ".png"))) p.icon = $"crab/icons/{key}.png";
        return p;
    }

    // visit every (property name, value) pair, descending into structs and arrays
    static void Walk(IEnumerable<FPropertyTag> props, int depth, Action<string, object> visit)
    {
        if (props == null || depth > 4) return;
        foreach (var prop in props)
        {
            var name = prop.Name.Text;
            Visit(name, prop.Tag?.GenericValue, depth, visit);
        }
    }

    static void Visit(string name, object v, int depth, Action<string, object> visit)
    {
        switch (v)
        {
            case null: return;
            case FScriptStruct ss when ss.StructType is FStructFallback fb:
                Walk(fb.Properties, depth + 1, visit); return;
            case UScriptArray arr:
                foreach (var e in arr.Properties) Visit(name, e.GenericValue, depth + 1, visit);
                return;
            default:
                visit(name, v); return;
        }
    }

    static bool SavePng(UTexture2D tex, string file)
    {
        var bmp = tex.Decode(256);
        if (bmp == null) return false;
        File.WriteAllBytes(file, bmp.Encode(ETextureFormat.Png, false, out _));
        return true;
    }
}

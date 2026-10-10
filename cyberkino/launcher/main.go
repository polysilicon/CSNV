// Command cyberkino-launch builds Cyberpunk Kino on the player's PC and starts Black Ops with it.
//
// Melty runs it on every Play with the two games' folders:
//
//	cyberkino-launch.exe --bo <Black Ops folder> --cp <Cyberpunk 2077 folder>
//
// It reads Kino from the player's own Black Ops (OpenAssetTools' Unlinker), exports the Cyberpunk guns,
// Mantis Blades and a shard from the player's own Cyberpunk (WolvenKit), fits each Cyberpunk model into
// the Black Ops gun it replaces, builds <Black Ops>/mods/cyberkino/mod.ff and cyberkino.iwd (OpenAssetTools'
// Linker) and starts BlackOps.exe with that mod. Nothing from either game is shipped with the mod; the
// build is cached and only redone when a game, or the mod, changes.
package main

import (
	"archive/zip"
	"crypto/sha256"
	"encoding/hex"
	"encoding/json"
	"errors"
	"flag"
	"fmt"
	"io"
	"net/url"
	"os"
	"os/exec"
	"path/filepath"
	"regexp"
	"runtime"
	"sort"
	"strings"
	"time"
)

type weaponRow struct {
	ID, Name, Base, BaseUp string
	Meshes                 []string
	DamageMult             float64
	Clip, MaxAmmo          int
	FireTimeMult           float64
	PapDamageMult          float64
	PapClip, PapMaxAmmo    int
	FitScale               float64
}

type modelRow struct {
	ID     string
	Meshes []string
	Kind   string
	FitTo  string
	Scale  float64
}

type mantisSpec struct {
	Model       string
	Base        string
	MeleeDamage int
}

type hookRow struct {
	ID, File, Anchor, Action, Text string
	Required                       bool
}

type zoneRow struct {
	ID, Dir, Use string
	Required     bool
}

type launcher struct {
	exeDir   string
	boDir    string
	cpDir    string
	work     string
	logFile  *os.File
	noLaunch bool
}

func (l *launcher) logf(format string, args ...any) {
	line := fmt.Sprintf("%s %s", time.Now().Format("15:04:05"), fmt.Sprintf(format, args...))
	fmt.Println(line)
	if l.logFile != nil {
		fmt.Fprintln(l.logFile, line)
	}
}

func main() {
	l := &launcher{}
	exe, _ := os.Executable()
	l.exeDir = filepath.Dir(exe)
	flag.StringVar(&l.boDir, "bo", "", "Call of Duty: Black Ops folder")
	flag.StringVar(&l.cpDir, "cp", "", "Cyberpunk 2077 folder")
	flag.BoolVar(&l.noLaunch, "no-launch", false, "build the mod but don't start Black Ops")
	rebuild := flag.Bool("rebuild", false, "ignore the cache")
	flag.Parse()

	logPath := filepath.Join(l.exeDir, "cyberkino-launch.log")
	if f, err := os.Create(logPath); err == nil {
		l.logFile = f
		defer f.Close()
	}
	l.logf("Cyberpunk Kino %s", modVersion)
	if err := l.run(*rebuild); err != nil {
		l.logf("CyberKino error: %v", err)
		showError("Cyberpunk Kino could not start.\n\n" + err.Error() + "\n\nDetails: " + logPath)
		os.Exit(1)
	}
}

func (l *launcher) run(rebuild bool) error {
	if l.boDir == "" || l.cpDir == "" {
		return errors.New("start it from Melty (it needs --bo and --cp)")
	}
	l.boDir, l.cpDir = filepath.Clean(l.boDir), filepath.Clean(l.cpDir)
	boExe := filepath.Join(l.boDir, "BlackOps.exe")
	if _, err := os.Stat(boExe); err != nil {
		return fmt.Errorf("BlackOps.exe not found in %s", l.boDir)
	}
	cpContent := filepath.Join(l.cpDir, "archive", "pc", "content")
	if _, err := os.Stat(cpContent); err != nil {
		return fmt.Errorf("Cyberpunk 2077's archive\\pc\\content folder not found in %s", l.cpDir)
	}
	l.logf("Black Ops: %s", l.boDir)
	l.previousConsole()
	l.logf("Cyberpunk 2077: %s", l.cpDir)

	cacheRoot := os.Getenv("LOCALAPPDATA")
	if cacheRoot == "" {
		cacheRoot = l.exeDir
	}
	l.work = filepath.Join(cacheRoot, "CyberKino")
	modDir := filepath.Join(l.boDir, "mods", "cyberkino")
	stamp, err := l.stamp()
	if err != nil {
		return err
	}
	stampFile := filepath.Join(modDir, "cyberkino.stamp")
	if old, err := os.ReadFile(stampFile); err == nil && string(old) == stamp && !rebuild {
		if _, err := os.Stat(filepath.Join(modDir, "mod.ff")); err == nil {
			l.logf("Mod is up to date (games unchanged since the last build).")
			return l.launch(boExe)
		}
	}
	start := time.Now()
	if err := l.build(modDir); err != nil {
		return err
	}
	if err := os.WriteFile(stampFile, []byte(stamp), 0o644); err != nil {
		return err
	}
	l.logf("Built the mod in %s.", time.Since(start).Round(time.Second))
	return l.launch(boExe)
}

// stamp changes whenever the mod or anything it reads from the games changes.
func (l *launcher) stamp() (string, error) {
	h := sha256.New()
	fmt.Fprintln(h, modVersion)
	gen, _ := json.Marshal([]any{weaponRows, modelRows, mantisRow, hookRows, zoneRows})
	h.Write(gen)
	for _, rel := range []string{"gsc/maps/cyberkino.gsc", "gsc/clientscripts/cyberkino.csc", "gsc/english/localizedstrings/cyberkino.str"} {
		b, err := os.ReadFile(filepath.Join(l.exeDir, filepath.FromSlash(rel)))
		if err != nil {
			return "", fmt.Errorf("the mod's %s is missing: reinstall it from Melty", rel)
		}
		h.Write(b)
	}
	files := []string{}
	for _, z := range zoneRows {
		files = append(files, l.zonePath(z))
	}
	archives, _ := filepath.Glob(filepath.Join(l.cpDir, "archive", "pc", "content", "*.archive"))
	sort.Strings(archives)
	files = append(files, archives...)
	for _, f := range files {
		if st, err := os.Stat(f); err == nil {
			fmt.Fprintf(h, "%s %d %d\n", filepath.Base(f), st.Size(), st.ModTime().Unix())
		}
	}
	return hex.EncodeToString(h.Sum(nil)), nil
}

func (l *launcher) zonePath(z zoneRow) string {
	return filepath.Join(l.boDir, "zone", z.Dir, z.ID)
}

func (l *launcher) tool(parts ...string) string {
	return filepath.Join(append([]string{l.exeDir, "tools"}, parts...)...)
}

func (l *launcher) exec(name string, dir string, args ...string) error {
	l.logf("> %s %s", filepath.Base(name), strings.Join(args, " "))
	cmd := exec.Command(name, args...)
	cmd.Dir = dir
	hideWindow(cmd)
	out, err := cmd.CombinedOutput()
	lines := strings.Split(strings.TrimSpace(stripANSI(string(out))), "\n")
	for _, line := range lines {
		if line = strings.TrimSpace(line); line != "" && l.logFile != nil {
			fmt.Fprintln(l.logFile, "    "+line)
		}
	}
	if err != nil {
		tail := lines
		if len(tail) > 6 {
			tail = tail[len(tail)-6:]
		}
		return fmt.Errorf("%s failed (%v): %s", filepath.Base(name), err, strings.Join(tail, " | "))
	}
	return nil
}

var ansi = regexp.MustCompile(`\x1b\[[0-9;]*m`)

func stripANSI(s string) string { return ansi.ReplaceAllString(s, "") }

func exeName(n string) string {
	if runtime.GOOS == "windows" {
		return n + ".exe"
	}
	return n
}

// ---------------------------------------------------------------- build

func (l *launcher) build(modDir string) error {
	if err := os.RemoveAll(l.work); err != nil {
		return err
	}
	dumpRoot := filepath.Join(l.work, "bo_dump")
	cpOut := filepath.Join(l.work, "cp")
	cpRepo := filepath.Join(l.work, "cp_repo")
	oatBase := filepath.Join(l.work, "oat")
	raw := filepath.Join(oatBase, "zone_raw", "mod")
	imgDir := filepath.Join(l.work, "img")
	for _, d := range []string{dumpRoot, cpOut, cpRepo, raw, imgDir, filepath.Join(oatBase, "zone_source")} {
		if err := os.MkdirAll(d, 0o755); err != nil {
			return err
		}
	}

	// 1. Kino from the player's Black Ops. Kino's weapons, models and materials are spread over the shared
	// Zombies zone and Kino's own, so each "unlink" zone is dumped, loading the zones before it first.
	var loads []string
	dump := boDump{}
	for _, z := range zoneRows {
		p := l.zonePath(z)
		if _, err := os.Stat(p); err != nil {
			if z.Required {
				return fmt.Errorf("Black Ops file zone\\%s\\%s is missing: verify the game's files in Steam", z.Dir, z.ID)
			}
			l.logf("Optional zone %s not found; going on without it.", z.ID)
			continue
		}
		if z.Use == "unlink" || z.Use == "both" {
			args := []string{}
			for _, lp := range loads {
				args = append(args, "-l", lp)
			}
			args = append(args, "--model-format", "GLB", "--include-assets", "weapon,xmodel,material,rawfile", "-o", filepath.Join(dumpRoot, "?zone?"), p)
			l.logf("Reading %s from Black Ops...", z.ID)
			if err := l.exec(l.tool("oat", exeName("Unlinker")), l.work, args...); err != nil {
				return err
			}
			root := filepath.Join(dumpRoot, strings.TrimSuffix(z.ID, ".ff"))
			// later zones (Kino's own) win over earlier ones (shared Zombies)
			dump.Roots = append([]string{root}, dump.Roots...)
			l.logf("  %s", dump.inventory(root))
		}
		if z.Use == "load" || z.Use == "both" {
			loads = append(loads, p)
		}
	}
	if len(dump.Roots) == 0 {
		return errors.New("no Black Ops zone was read (zones sheet)")
	}

	// 2. The Cyberpunk meshes from the player's Cyberpunk
	var depot []string
	for _, w := range weaponRows {
		depot = append(depot, w.Meshes...)
	}
	for _, m := range modelRows {
		depot = append(depot, m.Meshes...)
	}
	var quoted []string
	for _, p := range depot {
		quoted = append(quoted, regexp.QuoteMeta(p))
	}
	l.logf("Exporting %d Cyberpunk meshes with WolvenKit (a minute or two the first time)...", len(depot))
	wk := []string{l.tool("wolvenkit", "WolvenKit.CLI.dll"), "uncook", filepath.Join(l.cpDir, "archive", "pc", "content"),
		"-gp", l.cpDir, "-o", cpOut, "--mesh-export-material-repo", cpRepo, "--uext", "png", "--mesh-export-lod-filter",
		"-r", "^(" + strings.Join(quoted, "|") + ")$"}
	if err := l.exec(l.tool("dotnet", exeName("dotnet")), l.work, wk...); err != nil {
		return err
	}
	glbs := 0
	filepath.Walk(cpOut, func(p string, info os.FileInfo, err error) error {
		if err == nil && !info.IsDir() && strings.EqualFold(filepath.Ext(p), ".glb") {
			glbs++
		}
		return nil
	})
	l.logf("  WolvenKit exported %d of %d meshes.", glbs, len(depot))
	if glbs == 0 {
		return errors.New("WolvenKit exported none of the Cyberpunk meshes (its output is in the log)")
	}
	tex := texResolver{Repo: cpRepo, Log: l.logf}

	z := &zoneFile{}
	b := &modBuilder{l: l, dump: dump, raw: raw, imgDir: imgDir, cpOut: cpOut, tex: tex, zone: z}

	// 3. Guns
	built := 0
	var reasons []string
	for _, w := range weaponRows {
		if err := b.weapon(w); err != nil {
			l.logf("CyberKino warning: %s skipped: %v", w.Name, err)
			if len(reasons) < 3 {
				reasons = append(reasons, w.Name+": "+err.Error())
			}
			continue
		}
		built++
	}
	if built == 0 {
		return fmt.Errorf("none of the Cyberpunk guns could be built. First reasons:\n%s", strings.Join(reasons, "\n"))
	}
	l.logf("%d of %d guns built.", built, len(weaponRows))

	// 4. Models that are not guns
	for _, m := range modelRows {
		if err := b.model(m); err != nil {
			return fmt.Errorf("model %s: %w", m.ID, err)
		}
	}
	if err := b.mantis(); err != nil {
		return fmt.Errorf("Mantis Blades: %w", err)
	}

	// 5. Scripts and strings
	if err := b.scripts(); err != nil {
		return err
	}

	// 6. Link mod.ff and pack the textures
	if err := os.WriteFile(filepath.Join(oatBase, "zone_source", "mod.zone"), []byte(z.String()), 0o644); err != nil {
		return err
	}
	largs := []string{"-b", oatBase}
	for _, p := range loads {
		largs = append(largs, "--load", p)
	}
	largs = append(largs, "mod")
	l.logf("Linking mod.ff...")
	if err := l.exec(l.tool("oat", exeName("Linker")), oatBase, largs...); err != nil {
		return err
	}
	if err := os.MkdirAll(modDir, 0o755); err != nil {
		return err
	}
	if err := copyFile(filepath.Join(oatBase, "zone_out", "mod", "mod.ff"), filepath.Join(modDir, "mod.ff")); err != nil {
		return err
	}
	if err := writeIWD(filepath.Join(modDir, "cyberkino.iwd"), filepath.Join(raw, "images")); err != nil {
		return err
	}
	l.logf("Wrote %s", modDir)
	return nil
}

// ---------------------------------------------------------------- launch

// launch starts Black Ops with the mod. Steam's copy of Black Ops hands itself over to Steam when
// started directly, dropping its command line (test 5: it exited at once, steam_appid.txt or not), so
// Steam is asked to start it with the mod's options: steam.exe -applaunch, or, if steam.exe can't be
// found, Steam's run link with the options URL-encoded.
func (l *launcher) launch(boExe string) error {
	if l.noLaunch {
		l.logf("Not starting Black Ops (--no-launch).")
		return nil
	}
	l.logf("Starting Black Ops with the mod. In the menu: Zombies > Solo > Kino der Toten.")
	// logfile 2: Black Ops writes its console to mods/cyberkino/console.log, read back on the next Play
	args := []string{"+set", "fs_game", "mods/cyberkino", "+set", "logfile", "2"}
	if steam := findSteamExe(); steam != "" {
		cmd := exec.Command(steam, append([]string{"-applaunch", steamAppID}, args...)...)
		if err := cmd.Start(); err == nil {
			l.logf("Asked Steam (%s) to start Black Ops with: %s", steam, strings.Join(args, " "))
			return nil
		} else {
			l.logf("CyberKino warning: could not run %s (%v)", steam, err)
		}
	}
	link := "steam://run/" + steamAppID + "//" + url.PathEscape(strings.Join(args, " ")) + "/"
	if err := openURL(link); err != nil {
		return fmt.Errorf("could not start Black Ops through Steam: %w", err)
	}
	l.logf("Asked Steam to run %s (Steam may ask once to allow the launch options).", link)
	return nil
}

// findSteamExe reads Steam's install from the registry (the games may be in another library folder).
func findSteamExe() string {
	queries := [][]string{
		{`HKCU\Software\Valve\Steam`, "SteamExe"},
		{`HKLM\SOFTWARE\WOW6432Node\Valve\Steam`, "InstallPath"},
		{`HKLM\SOFTWARE\Valve\Steam`, "InstallPath"},
	}
	for _, q := range queries {
		v := regQuery(q[0], q[1])
		if v == "" {
			continue
		}
		v = filepath.FromSlash(v)
		if !strings.EqualFold(filepath.Ext(v), ".exe") {
			v = filepath.Join(v, "steam.exe")
		}
		if _, err := os.Stat(v); err == nil {
			return v
		}
	}
	for _, p := range []string{`C:\Program Files (x86)\Steam\steam.exe`, `C:\Program Files\Steam\steam.exe`} {
		if _, err := os.Stat(p); err == nil {
			return p
		}
	}
	return ""
}

// regQuery returns one registry value through reg.exe ("" when missing or not on Windows).
func regQuery(key, value string) string {
	if runtime.GOOS != "windows" {
		return ""
	}
	cmd := exec.Command("reg", "query", key, "/v", value)
	hideWindow(cmd)
	out, err := cmd.Output()
	if err != nil {
		return ""
	}
	return parseRegValue(string(out), value)
}

func parseRegValue(out, value string) string {
	for _, line := range strings.Split(out, "\n") {
		f := strings.Fields(line)
		if len(f) >= 3 && strings.EqualFold(f[0], value) && strings.HasPrefix(f[1], "REG_") {
			i := strings.Index(line, f[1]) + len(f[1])
			return strings.TrimSpace(line[i:])
		}
	}
	return ""
}

const steamAppID = "42700" // Call of Duty: Black Ops on Steam

// ---------------------------------------------------------------- files

func copyFile(src, dst string) error {
	in, err := os.Open(src)
	if err != nil {
		return err
	}
	defer in.Close()
	if err := os.MkdirAll(filepath.Dir(dst), 0o755); err != nil {
		return err
	}
	out, err := os.Create(dst)
	if err != nil {
		return err
	}
	if _, err := io.Copy(out, in); err != nil {
		out.Close()
		return err
	}
	return out.Close()
}

// writeIWD packs images/*.iwi into an .iwd (a zip Black Ops reads textures from).
func writeIWD(path, imagesDir string) error {
	files, _ := filepath.Glob(filepath.Join(imagesDir, "*.iwi"))
	sort.Strings(files)
	f, err := os.Create(path)
	if err != nil {
		return err
	}
	zw := zip.NewWriter(f)
	for _, src := range files {
		w, err := zw.CreateHeader(&zip.FileHeader{Name: "images/" + filepath.Base(src), Method: zip.Store})
		if err != nil {
			f.Close()
			return err
		}
		in, err := os.Open(src)
		if err != nil {
			f.Close()
			return err
		}
		_, err = io.Copy(w, in)
		in.Close()
		if err != nil {
			f.Close()
			return err
		}
	}
	if err := zw.Close(); err != nil {
		f.Close()
		return err
	}
	return f.Close()
}

var consoleInteresting = regexp.MustCompile(`(?i)cyberkino|fs_game|mod\.ff|error|script|could not|unknown function|failed`)

// previousConsole copies the telling lines of Black Ops' console log from the last game into this log.
func (l *launcher) previousConsole() {
	for _, p := range []string{
		filepath.Join(l.boDir, "mods", "cyberkino", "console.log"),
		filepath.Join(l.boDir, "main", "console.log"),
	} {
		data, err := os.ReadFile(p)
		if err != nil {
			continue
		}
		lines := strings.Split(strings.ReplaceAll(string(data), "\r", ""), "\n")
		l.logf("Black Ops console from the last game (%s, %d lines), telling lines:", p, len(lines))
		shown := 0
		for _, line := range lines {
			if consoleInteresting.MatchString(line) && shown < 200 {
				l.logf("  | %s", strings.TrimSpace(line))
				shown++
			}
		}
		if shown == 0 {
			l.logf("  | (none)")
		}
	}
}

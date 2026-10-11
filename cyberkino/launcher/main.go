// Command cyberkino-launch prepares Cyberpunk Kino on the player's PC and starts Cyberpunk 2077.
//
// Melty runs it on every Play with the two games' folders:
//
//	cyberkino-launch.exe --cp <Cyberpunk 2077 folder> --bo <Call of Duty: Black Ops folder>
//
// It reads Black Ops' Ray Gun from the player's own Black Ops (OpenAssetTools' Unlinker), builds it onto
// Cyberpunk's Militech Omaha meshes exported from the player's own Cyberpunk (WolvenKit), packs that into
// archive\pc\mod\zz_cyberkino_raygun.archive, presets the mod's CET keys (F7 start, F buy, Z Sandevistan)
// and starts Cyberpunk. Nothing from either game is shipped; the Ray Gun is rebuilt only when a game or
// the mod changes.
package main

import (
	"crypto/sha256"
	"encoding/hex"
	"encoding/json"
	"errors"
	"flag"
	"fmt"
	"io"
	"os"
	"os/exec"
	"path/filepath"
	"regexp"
	"runtime"
	"sort"
	"strings"
	"time"
)

type rayGunSpec struct {
	Zone, Weapon, DonorMesh, HidePrefix, Archive string
	FitScale                                     float64
}

type keySpec struct {
	ID string
	VK uint64
}

type launcher struct {
	exeDir, cpDir, boDir, work string
	logFile                    *os.File
	noLaunch                   bool
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
	flag.StringVar(&l.cpDir, "cp", "", "Cyberpunk 2077 folder")
	flag.StringVar(&l.boDir, "bo", "", "Call of Duty: Black Ops folder")
	flag.BoolVar(&l.noLaunch, "no-launch", false, "prepare the mod but don't start Cyberpunk")
	rebuild := flag.Bool("rebuild", false, "rebuild the Ray Gun even if nothing changed")
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
	if l.cpDir == "" || l.boDir == "" {
		return errors.New("start it from Melty (it needs --cp and --bo)")
	}
	l.cpDir, l.boDir = filepath.Clean(l.cpDir), filepath.Clean(l.boDir)
	cpExe := filepath.Join(l.cpDir, "bin", "x64", "Cyberpunk2077.exe")
	if !fileExists(cpExe) {
		return fmt.Errorf("Cyberpunk2077.exe not found in %s", l.cpDir)
	}
	l.logf("Cyberpunk 2077: %s", l.cpDir)
	l.logf("Black Ops: %s", l.boDir)
	root := os.Getenv("LOCALAPPDATA")
	if root == "" {
		root = l.exeDir
	}
	l.work = filepath.Join(root, "CyberKino")

	if err := l.rayGun(rebuild); err != nil {
		// a match still works without the Ray Gun's model (it is then a plain Omaha)
		l.logf("CyberKino warning: the Ray Gun could not be built, so it will look like an Omaha: %v", err)
	}
	if err := l.presetKeys(); err != nil {
		l.logf("CyberKino warning: could not preset the CET keys (%v); bind them in CET's Bindings tab", err)
	}
	return l.launch(cpExe)
}

// ---------------------------------------------------------------- the Ray Gun

func (l *launcher) archivePath() string {
	return filepath.Join(l.cpDir, "archive", "pc", "mod", rayGun.Archive)
}

func (l *launcher) stamp() string {
	h := sha256.New()
	fmt.Fprintln(h, modVersion)
	spec, _ := json.Marshal(rayGun)
	h.Write(spec)
	common := filepath.Join(l.boDir, "zone", "Common")
	files := []string{filepath.Join(common, rayGun.Zone), filepath.Join(common, "code_post_gfx.ff"), filepath.Join(common, "common.ff")}
	archives, _ := filepath.Glob(filepath.Join(l.cpDir, "archive", "pc", "content", "*.archive"))
	sort.Strings(archives)
	for _, f := range append(files, archives...) {
		if st, err := os.Stat(f); err == nil {
			fmt.Fprintf(h, "%s %d %d\n", filepath.Base(f), st.Size(), st.ModTime().Unix())
		}
	}
	return hex.EncodeToString(h.Sum(nil))
}

func (l *launcher) rayGun(rebuild bool) error {
	stamp := l.stamp()
	stampFile := filepath.Join(l.work, "raygun.stamp")
	if old, err := os.ReadFile(stampFile); err == nil && string(old) == stamp && !rebuild && fileExists(l.archivePath()) {
		l.logf("Ray Gun is up to date.")
		return nil
	}
	start := time.Now()
	if err := os.RemoveAll(l.work); err != nil {
		return err
	}
	dump := filepath.Join(l.work, "bo_dump")
	depotRoot := filepath.Join(l.work, strings.TrimSuffix(rayGun.Archive, ".archive"))
	raw := filepath.Join(l.work, "raw")
	for _, d := range []string{dump, depotRoot, raw} {
		if err := os.MkdirAll(d, 0o755); err != nil {
			return err
		}
	}

	// 1. the Ray Gun from the player's Black Ops
	common := filepath.Join(l.boDir, "zone", "Common")
	zone := filepath.Join(common, rayGun.Zone)
	if !fileExists(zone) {
		return fmt.Errorf("Black Ops file zone\\Common\\%s is missing", rayGun.Zone)
	}
	args := []string{}
	for _, z := range []string{"code_post_gfx.ff", "common.ff"} {
		if p := filepath.Join(common, z); fileExists(p) {
			args = append(args, "-l", p)
		}
	}
	args = append(args, "--model-format", "GLB", "--include-assets", "weapon,xmodel", "-o", filepath.Join(dump, "?zone?"), zone)
	l.logf("Reading the Ray Gun from Black Ops...")
	if err := l.exec(l.tool("oat", exeName("Unlinker")), l.work, args...); err != nil {
		return err
	}
	zoneDump := filepath.Join(dump, strings.TrimSuffix(rayGun.Zone, ".ff"))
	wf, err := os.ReadFile(filepath.Join(zoneDump, "weapons", rayGun.Weapon))
	if err != nil {
		return fmt.Errorf("Black Ops weapon %s not found in %s", rayGun.Weapon, rayGun.Zone)
	}
	ws, err := parseInfoString(string(wf))
	if err != nil {
		return err
	}
	model := ws.Values["worldModel"]
	bog, err := readGLB(filepath.Join(zoneDump, "model_export", model+"_lod0.glb"))
	if err != nil {
		return fmt.Errorf("Ray Gun model %s not dumped: %w", model, err)
	}
	bo, err := loadBaseModel(model, bog)
	if err != nil {
		return err
	}
	boParts, err := loadParts(bog)
	if err != nil {
		return err
	}
	l.logf("  Ray Gun model %s: %d parts, muzzle %v", model, len(boParts), bo.Forward)

	// 2. the Omaha's meshes from the player's Cyberpunk, unbundled and exported to glTF
	l.logf("Exporting the Omaha's meshes with WolvenKit...")
	wk := []string{l.tool("wolvenkit", "WolvenKit.CLI.dll"), "uncook", filepath.Join(l.cpDir, "archive", "pc", "content"),
		"-gp", l.cpDir, "-o", depotRoot, "-or", raw, "-u", "--uext", "png", "--mesh-export-lod-filter",
		"-r", "^" + regexp.QuoteMeta(rayGun.HidePrefix) + `.*\.mesh$`}
	if err := l.exec(l.tool("dotnet", exeName("dotnet")), l.work, wk...); err != nil {
		return err
	}
	meshes, err := depotMeshes(depotRoot, rayGun.HidePrefix)
	if err != nil {
		return err
	}
	l.logf("  %d Omaha meshes exported", len(meshes))
	donorRel := depotRel(rayGun.DonorMesh)
	if !contains(meshes, donorRel) {
		return fmt.Errorf("WolvenKit did not export %s", rayGun.DonorMesh)
	}

	// 3. a glb per mesh: the donor gets the Ray Gun, every other part is emptied
	for _, rel := range meshes {
		glbPath := filepath.Join(raw, strings.TrimSuffix(rel, filepath.Ext(rel))+".glb")
		dg, err := readGLB(glbPath)
		if err != nil {
			return fmt.Errorf("%s was not exported to glTF: %w", filepath.Base(rel), err)
		}
		base, err := loadBaseModel(filepath.Base(rel), dg)
		if err != nil {
			return err
		}
		names := meshNames(dg)
		if len(names) == 0 {
			return fmt.Errorf("%s has no meshes", filepath.Base(rel))
		}
		if strings.EqualFold(rel, donorRel) {
			base.Forward = vec3{0, 0, -1} // Cyberpunk's guns point along -Z in WolvenKit's glTF
			parts, _ := simplify(boParts, maxModelVerts)
			fitted, info, err := fitPartsFrom(parts, bo.Forward, base, rayGun.FitScale)
			if err != nil {
				return fmt.Errorf("fitting the Ray Gun: %w", err)
			}
			l.logf("  Ray Gun fitted onto %s (scale %.4f, %d submeshes kept)", filepath.Base(rel), info.Scale, len(names))
			names[0].Parts = fitted
		}
		data, err := writeNamedMeshesGLB(base, names)
		if err != nil {
			return err
		}
		if err := os.WriteFile(glbPath, data, 0o644); err != nil {
			return err
		}
	}

	// 4. import into the meshes, pack, install
	l.logf("Importing the Ray Gun into the meshes...")
	wkcli := l.tool("wolvenkit", "WolvenKit.CLI.dll")
	if err := l.exec(l.tool("dotnet", exeName("dotnet")), l.work, wkcli, "import", raw, "-o", depotRoot, "-k"); err != nil {
		return err
	}
	if err := pruneDepot(depotRoot, meshes); err != nil {
		return err
	}
	if err := l.exec(l.tool("dotnet", exeName("dotnet")), l.work, wkcli, "pack", depotRoot, "-o", l.work); err != nil {
		return err
	}
	packed := filepath.Join(l.work, rayGun.Archive)
	if !fileExists(packed) {
		return errors.New("WolvenKit wrote no archive")
	}
	if err := copyFile(packed, l.archivePath()); err != nil {
		return err
	}
	if err := os.WriteFile(stampFile, []byte(stamp), 0o644); err != nil {
		return err
	}
	l.logf("Ray Gun built in %s: %s", time.Since(start).Round(time.Second), l.archivePath())
	return nil
}

func depotRel(depot string) string {
	return filepath.FromSlash(strings.ReplaceAll(depot, "\\", "/"))
}

// depotMeshes lists the exported .mesh files under root whose depot path starts with prefix.
func depotMeshes(root, prefix string) ([]string, error) {
	var out []string
	pre := strings.ToLower(depotRel(prefix))
	filepath.Walk(root, func(p string, info os.FileInfo, err error) error {
		if err != nil || info.IsDir() || !strings.EqualFold(filepath.Ext(p), ".mesh") {
			return nil
		}
		rel, _ := filepath.Rel(root, p)
		if strings.HasPrefix(strings.ToLower(rel), pre) {
			out = append(out, rel)
		}
		return nil
	})
	sort.Strings(out)
	if len(out) == 0 {
		return nil, errors.New("WolvenKit exported none of the Omaha's meshes")
	}
	return out, nil
}

// pruneDepot removes every unbundled file but the meshes, so the archive holds only them.
func pruneDepot(root string, keep []string) error {
	keepSet := map[string]bool{}
	for _, k := range keep {
		keepSet[strings.ToLower(k)] = true
	}
	return filepath.Walk(root, func(p string, info os.FileInfo, err error) error {
		if err != nil || info.IsDir() {
			return nil
		}
		rel, _ := filepath.Rel(root, p)
		if !keepSet[strings.ToLower(rel)] {
			return os.Remove(p)
		}
		return nil
	})
}

func contains(list []string, s string) bool {
	for _, x := range list {
		if strings.EqualFold(x, s) {
			return true
		}
	}
	return false
}

func fileExists(p string) bool {
	_, err := os.Stat(p)
	return err == nil
}

// ---------------------------------------------------------------- CET keys

// presetKeys adds the mod's default keys to CET's bindings.json once: a key the player has bound (or
// changed) in CET's Bindings tab is left alone. CET stores a single key as its virtual-key code << 48.
func (l *launcher) presetKeys() error {
	path := filepath.Join(l.cpDir, "bin", "x64", "plugins", "cyber_engine_tweaks", "bindings.json")
	cfg := map[string]map[string]uint64{}
	if data, err := os.ReadFile(path); err == nil && len(strings.TrimSpace(string(data))) > 0 {
		var raw map[string]json.RawMessage
		if err := json.Unmarshal(data, &raw); err != nil {
			return fmt.Errorf("bindings.json is not readable: %w", err)
		}
		for mod, v := range raw {
			m := map[string]uint64{}
			if err := json.Unmarshal(v, &m); err != nil {
				return fmt.Errorf("bindings.json has an entry in an older format (%s); left as it is", mod)
			}
			cfg[mod] = m
		}
	}
	mod := cfg[cetModName]
	if mod == nil {
		mod = map[string]uint64{}
	}
	added := 0
	for _, k := range keyRows {
		if _, ok := mod[k.ID]; !ok {
			mod[k.ID] = k.VK << 48
			added++
		}
	}
	if added == 0 {
		return nil
	}
	cfg[cetModName] = mod
	out, err := json.MarshalIndent(cfg, "", "    ")
	if err != nil {
		return err
	}
	if err := os.MkdirAll(filepath.Dir(path), 0o755); err != nil {
		return err
	}
	if err := os.WriteFile(path, append(out, '\n'), 0o644); err != nil {
		return err
	}
	l.logf("Preset %d CET keys (F7 start, F buy, Z Sandevistan).", added)
	return nil
}

// ---------------------------------------------------------------- launch

const cyberpunkSteamID = "1091500"

// launch starts Cyberpunk: through Steam for Steam's copy, else its exe (GOG, or Steam not found).
func (l *launcher) launch(cpExe string) error {
	if l.noLaunch {
		l.logf("Not starting Cyberpunk (--no-launch).")
		return nil
	}
	hint := "In game, go to V's floor in Megabuilding H10 and press F7."
	if strings.Contains(strings.ToLower(l.cpDir), "steamapps") {
		if steam := findSteamExe(); steam != "" {
			if err := exec.Command(steam, "-applaunch", cyberpunkSteamID).Start(); err == nil {
				l.logf("Asked Steam to start Cyberpunk 2077. %s", hint)
				return nil
			}
		}
	}
	cmd := exec.Command(cpExe)
	cmd.Dir = filepath.Dir(cpExe)
	if err := cmd.Start(); err != nil {
		return fmt.Errorf("could not start Cyberpunk2077.exe: %w", err)
	}
	l.logf("Started Cyberpunk 2077. %s", hint)
	return nil
}

// findSteamExe reads Steam's install from the registry (the games may be in another library folder).
func findSteamExe() string {
	for _, q := range [][]string{
		{`HKCU\Software\Valve\Steam`, "SteamExe"},
		{`HKLM\SOFTWARE\WOW6432Node\Valve\Steam`, "InstallPath"},
		{`HKLM\SOFTWARE\Valve\Steam`, "InstallPath"},
	} {
		v := regQuery(q[0], q[1])
		if v == "" {
			continue
		}
		v = filepath.FromSlash(v)
		if !strings.EqualFold(filepath.Ext(v), ".exe") {
			v = filepath.Join(v, "steam.exe")
		}
		if fileExists(v) {
			return v
		}
	}
	for _, p := range []string{`C:\Program Files (x86)\Steam\steam.exe`, `C:\Program Files\Steam\steam.exe`} {
		if fileExists(p) {
			return p
		}
	}
	return ""
}

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

// ---------------------------------------------------------------- helpers

func (l *launcher) tool(parts ...string) string {
	return filepath.Join(append([]string{l.exeDir, "tools"}, parts...)...)
}

func (l *launcher) exec(name, dir string, args ...string) error {
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

// ---------------------------------------------------------------- Black Ops weapon files

type infoString struct {
	Prefix string
	Keys   []string
	Values map[string]string
}

// parseInfoString reads a Black Ops weapon file (WEAPONFILE\key\value\...).
func parseInfoString(text string) (*infoString, error) {
	text = strings.TrimRight(text, "\r\n\x00 ")
	parts := strings.Split(text, "\\")
	if len(parts) < 1 || parts[0] == "" {
		return nil, errors.New("empty weapon file")
	}
	s := &infoString{Prefix: parts[0], Values: map[string]string{}}
	for i := 1; i+1 < len(parts); i += 2 {
		if _, seen := s.Values[parts[i]]; !seen {
			s.Keys = append(s.Keys, parts[i])
		}
		s.Values[parts[i]] = parts[i+1]
	}
	return s, nil
}

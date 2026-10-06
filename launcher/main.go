// csnv-launch: Melty's Play button for CS2 in the Mojave.
//
// Before every Play it (hooks rows marked provider=launcher in sheets/hooks.json):
//   - write_settings: reads the player's CS2 buy key and crosshair (files only; CS2 is never started) and writes
//     Data/config/csnv_cs2.ini and Data/textures/interface/csnv/xhair.dds
//   - build_plugin: copies the sheet's weapons out of the player's own FalloutNV.esm into Data/CSNV.esp
//   - activate_plugin: makes sure CSNV.esp is listed in plugins.txt
//
// then starts New Vegas through xNVSE (nvse_loader.exe). A failed step is logged and the game still starts.
//
// Usage: csnv-launch.exe --fnv <Fallout New Vegas folder> [--cs2 <Counter-Strike 2 folder>] [--no-launch] [-- game args]
package main

import (
	"bufio"
	"flag"
	"fmt"
	"os"
	"os/exec"
	"path/filepath"
	"strings"
	"time"
)

const pluginName = "CSNV.esp"

var dlcMasters = []string{"DeadMoney.esm", "HonestHearts.esm", "OldWorldBlues.esm", "LonesomeRoad.esm",
	"GunRunnersArsenal.esm", "ClassicPack.esm", "MercenaryPack.esm", "TribalPack.esm", "CaravanPack.esm"}

// activatePlugin adds CSNV.esp to plugins.txt (creating it with the masters present if it does not exist).
func activatePlugin(pluginsTxt, dataDir string) (bool, error) {
	var lines []string
	if b, err := os.ReadFile(pluginsTxt); err == nil {
		sc := bufio.NewScanner(strings.NewReader(string(b)))
		for sc.Scan() {
			line := strings.TrimRight(sc.Text(), "\r")
			if strings.EqualFold(strings.TrimSpace(line), pluginName) {
				return false, nil
			}
			lines = append(lines, line)
		}
	} else if os.IsNotExist(err) {
		lines = append(lines, "FalloutNV.esm")
		for _, m := range dlcMasters {
			if _, err := os.Stat(filepath.Join(dataDir, m)); err == nil {
				lines = append(lines, m)
			}
		}
	} else {
		return false, err
	}
	for len(lines) > 0 && strings.TrimSpace(lines[len(lines)-1]) == "" {
		lines = lines[:len(lines)-1]
	}
	lines = append(lines, pluginName)
	if err := os.MkdirAll(filepath.Dir(pluginsTxt), 0o755); err != nil {
		return false, err
	}
	return true, os.WriteFile(pluginsTxt, []byte(strings.Join(lines, "\r\n")+"\r\n"), 0o644)
}

func main() {
	fnv := flag.String("fnv", "", "Fallout: New Vegas folder (Melty passes {game})")
	cs2 := flag.String("cs2", "", "Counter-Strike 2 folder (Melty passes {game:counter-strike-2}); optional")
	noLaunch := flag.Bool("no-launch", false, "prepare everything but do not start the game")
	flag.Parse()

	exe, _ := os.Executable()
	logPath := filepath.Join(filepath.Dir(exe), "csnv-launch.log")
	logFile, _ := os.Create(logPath)
	logf := func(format string, args ...any) {
		line := time.Now().Format("15:04:05 ") + fmt.Sprintf(format, args...)
		fmt.Println(line)
		if logFile != nil {
			fmt.Fprintln(logFile, line)
		}
	}
	defer func() {
		if logFile != nil {
			logFile.Close()
		}
	}()

	if *fnv == "" {
		logf("error: --fnv <Fallout New Vegas folder> is required")
		os.Exit(2)
	}
	data := filepath.Join(*fnv, "Data")
	logf("CS2 in the Mojave launcher: New Vegas at %s, CS2 at %q", *fnv, *cs2)

	// write_settings
	s := readCS2(*cs2, logf)
	if err := os.MkdirAll(filepath.Join(data, "config"), 0o755); err == nil {
		if err := os.WriteFile(filepath.Join(data, "config", "csnv_cs2.ini"), []byte(s.ini()), 0o644); err != nil {
			logf("error: writing csnv_cs2.ini: %v", err)
		}
	}
	texDir := filepath.Join(data, "textures", "interface", "csnv")
	if err := os.MkdirAll(texDir, 0o755); err == nil {
		if err := os.WriteFile(filepath.Join(texDir, "xhair.dds"), solidDDS(s.R, s.G, s.B, s.A), 0o644); err != nil {
			logf("error: writing xhair.dds: %v", err)
		}
	}

	// build_plugin
	written, errs := buildPlugin(filepath.Join(data, "FalloutNV.esm"), filepath.Join(data, pluginName), sheetWeapons)
	for _, err := range errs {
		logf("error: %v", err)
	}
	logf("%s: wrote %d of %d weapons %v", pluginName, len(written), len(sheetWeapons), written)

	// activate_plugin
	if local := os.Getenv("LOCALAPPDATA"); local != "" {
		pluginsTxt := filepath.Join(local, "FalloutNV", "plugins.txt")
		if added, err := activatePlugin(pluginsTxt, data); err != nil {
			logf("error: plugins.txt: %v", err)
		} else if added {
			logf("added %s to %s", pluginName, pluginsTxt)
		}
	} else {
		logf("error: LOCALAPPDATA is not set; cannot find plugins.txt")
	}

	if *noLaunch {
		logf("--no-launch: not starting the game")
		return
	}
	loader := filepath.Join(*fnv, "nvse_loader.exe")
	cmd := exec.Command(loader, flag.Args()...)
	cmd.Dir = *fnv
	cmd.Stdout, cmd.Stderr = os.Stdout, os.Stderr
	logf("starting %s", loader)
	if err := cmd.Run(); err != nil {
		logf("error: starting the game through xNVSE: %v", err)
		os.Exit(1)
	}
}

package main

// Reads the player's Counter-Strike 2 key binds and crosshair from the plain-text .vcfg files CS2 keeps on
// disk. CS2 is never started or touched while it runs. The rows of sheets/cs2_settings.json say what is
// read and how it converts; sheetCS2Defaults (generated from that sheet) fills anything missing.

import (
	"fmt"
	"math"
	"os"
	"os/exec"
	"path/filepath"
	"regexp"
	"runtime"
	"sort"
	"strconv"
	"strings"
)

// parseVCFG returns every "key" "value" pair in a KeyValues text file, flattened, plus the bindings block.
func parseVCFG(text string) (values map[string]string, bindings map[string]string) {
	values, bindings = map[string]string{}, map[string]string{}
	var stack []string
	var pending []string
	tok := regexp.MustCompile(`"((?:[^"\\]|\\.)*)"|[{}]|//[^\n]*`)
	for _, m := range tok.FindAllStringSubmatch(text, -1) {
		switch {
		case strings.HasPrefix(m[0], "//"):
		case m[0] == "{":
			if len(pending) > 0 {
				stack = append(stack, strings.ToLower(pending[len(pending)-1]))
			} else {
				stack = append(stack, "")
			}
			pending = nil
		case m[0] == "}":
			if len(stack) > 0 {
				stack = stack[:len(stack)-1]
			}
			pending = nil
		default:
			pending = append(pending, m[1])
			if len(pending) == 2 {
				k, v := strings.ToLower(pending[0]), pending[1]
				if len(stack) > 0 && stack[len(stack)-1] == "bindings" {
					bindings[k] = strings.ToLower(v)
				} else {
					values[k] = v
				}
				pending = nil
			}
		}
	}
	return values, bindings
}

// steamRoots lists folders that may hold Steam's userdata, most likely first.
func steamRoots(cs2Dir string) []string {
	var roots []string
	if runtime.GOOS == "windows" {
		if out, err := exec.Command("reg", "query", `HKCU\Software\Valve\Steam`, "/v", "SteamPath").Output(); err == nil {
			for _, line := range strings.Split(string(out), "\n") {
				if i := strings.Index(line, "REG_SZ"); i >= 0 {
					roots = append(roots, filepath.Clean(strings.TrimSpace(line[i+len("REG_SZ"):])))
				}
			}
		}
	}
	// <library>/steamapps/common/Counter-Strike Global Offensive -> <library>
	if cs2Dir != "" {
		roots = append(roots, filepath.Clean(filepath.Join(cs2Dir, "..", "..", "..")))
	}
	roots = append(roots, `C:\Program Files (x86)\Steam`, `C:\Program Files\Steam`)
	return roots
}

// newestCS2File finds the newest file matching pattern in any account's CS2 (app 730) cfg folder.
func newestCS2File(roots []string, pattern string) string {
	type hit struct {
		path string
		mod  int64
	}
	var hits []hit
	for _, root := range roots {
		matches, _ := filepath.Glob(filepath.Join(root, "userdata", "*", "730", "local", "cfg", pattern))
		for _, m := range matches {
			if st, err := os.Stat(m); err == nil {
				hits = append(hits, hit{m, st.ModTime().UnixNano()})
			}
		}
	}
	sort.Slice(hits, func(i, j int) bool { return hits[i].mod > hits[j].mod })
	if len(hits) == 0 {
		return ""
	}
	return hits[0].path
}

type cs2Settings struct {
	BuyKeyName string
	BuyKey     int
	R, G, B, A int
	Length     float64
	Gap        float64
	Thickness  float64
	Dot        int
	Source     string
}

var crosshairPresets = map[int][3]int{0: {250, 50, 50}, 1: {50, 250, 50}, 2: {250, 250, 50}, 3: {50, 50, 250}, 4: {50, 250, 250}}

func clamp(v, lo, hi float64) float64 { return math.Max(lo, math.Min(hi, v)) }

// resolveCS2 turns the raw CS2 values into what the mod uses (see the convert column of cs2_settings).
func resolveCS2(convars, bindings map[string]string, source string) cs2Settings {
	get := func(k string) float64 {
		if v, ok := convars[k]; ok {
			v = strings.ToLower(strings.TrimSpace(v))
			if v == "true" { // CS2 stores switches as true/false
				return 1
			}
			if v == "false" {
				return 0
			}
			if f, err := strconv.ParseFloat(v, 64); err == nil {
				return f
			}
		}
		f, _ := strconv.ParseFloat(sheetCS2Defaults[k], 64)
		return f
	}
	s := cs2Settings{Source: source}
	s.BuyKeyName = sheetCS2Defaults["buymenu"]
	var bound []string
	for key, cmd := range bindings {
		if _, ok := dikCodes[key]; ok && cmd == "buymenu" {
			bound = append(bound, key)
		}
	}
	if len(bound) > 0 {
		sort.Strings(bound) // deterministic pick when several keyboard keys are bound
		s.BuyKeyName = bound[0]
	}
	s.BuyKey = dikCodes[s.BuyKeyName]
	if s.BuyKey == 0 {
		s.BuyKeyName, s.BuyKey = "b", 48
	}
	preset := int(get("cl_crosshaircolor"))
	if rgb, ok := crosshairPresets[preset]; ok {
		s.R, s.G, s.B = rgb[0], rgb[1], rgb[2]
	} else {
		s.R = int(clamp(get("cl_crosshaircolor_r"), 0, 255))
		s.G = int(clamp(get("cl_crosshaircolor_g"), 0, 255))
		s.B = int(clamp(get("cl_crosshaircolor_b"), 0, 255))
	}
	s.A = 255
	if _, ok := convars["cl_crosshairusealpha"]; ok && get("cl_crosshairusealpha") != 0 {
		s.A = int(clamp(get("cl_crosshairalpha"), 0, 255))
	}
	s.Length = clamp(get("cl_crosshairsize")*2, 1, 60)
	s.Gap = clamp(4+get("cl_crosshairgap"), 0, 40)
	s.Thickness = math.Max(1, math.Round(get("cl_crosshairthickness")*2))
	if get("cl_crosshairdot") >= 1 {
		s.Dot = 1
	}
	return s
}

// readCS2 finds the player's CS2 files and resolves them; it never fails, falling back to CS2's defaults.
func readCS2(cs2Dir string, logf func(string, ...any)) cs2Settings {
	roots := steamRoots(cs2Dir)
	convars, bindings := map[string]string{}, map[string]string{}
	var sources []string
	if cs2Dir != "" {
		def := filepath.Join(cs2Dir, "game", "csgo", "cfg", "user_keys_default.vcfg")
		if b, err := os.ReadFile(def); err == nil {
			_, bindings = parseVCFG(string(b))
			sources = append(sources, "CS2 default keys")
		}
	}
	if p := newestCS2File(roots, "cs2_user_keys_*.vcfg"); p != "" {
		if b, err := os.ReadFile(p); err == nil {
			_, user := parseVCFG(string(b))
			if len(user) > 0 {
				userHasBuy := false
				for _, v := range user {
					userHasBuy = userHasBuy || v == "buymenu"
				}
				if userHasBuy { // the player's own buy key wins over every default bind
					bindings = user
				} else {
					for k, v := range user { // otherwise their binds override CS2's defaults key by key
						bindings[k] = v
					}
				}
				sources = append(sources, "your CS2 keys ("+filepath.Base(p)+")")
			}
		}
	}
	if p := newestCS2File(roots, "cs2_user_convars_*.vcfg"); p != "" {
		if b, err := os.ReadFile(p); err == nil {
			convars, _ = parseVCFG(string(b))
			sources = append(sources, "your CS2 crosshair ("+filepath.Base(p)+")")
		}
	}
	if len(sources) == 0 {
		sources = []string{"CS2 defaults (no CS2 files found)"}
	}
	s := resolveCS2(convars, bindings, strings.Join(sources, "; "))
	logf("CS2 settings from %s: buy key %q (scancode %d), crosshair rgba %d,%d,%d,%d length %g gap %g thickness %g dot %d",
		s.Source, s.BuyKeyName, s.BuyKey, s.R, s.G, s.B, s.A, s.Length, s.Gap, s.Thickness, s.Dot)
	return s
}

func (s cs2Settings) ini() string {
	return fmt.Sprintf("; CS2 in the Mojave: written by csnv-launch.exe before this Play from %s.\r\n"+
		"[Keys]\r\nBuyKey=%d\r\nBuyKeyName=%s\r\n[Crosshair]\r\nR=%d\r\nG=%d\r\nB=%d\r\nAlpha=%d\r\nLength=%g\r\nGap=%g\r\nThickness=%g\r\nDot=%d\r\n",
		s.Source, s.BuyKey, s.BuyKeyName, s.R, s.G, s.B, s.A, s.Length, s.Gap, s.Thickness, s.Dot)
}

// solidDDS is an uncompressed 8x8 A8R8G8B8 texture of one colour (same format tools/img.py writes).
func solidDDS(r, g, b, a int) []byte {
	const w, h = 8, 8
	buf := make([]byte, 0, 128+w*h*4)
	le := func(v uint32) { buf = append(buf, byte(v), byte(v>>8), byte(v>>16), byte(v>>24)) }
	buf = append(buf, "DDS "...)
	le(124)
	le(0x1 | 0x2 | 0x4 | 0x1000 | 0x8)
	le(h)
	le(w)
	le(w * 4)
	le(0)
	le(0)
	buf = append(buf, make([]byte, 44)...)
	le(32)
	le(0x41)
	le(0)
	le(32)
	le(0x00FF0000)
	le(0x0000FF00)
	le(0x000000FF)
	le(0xFF000000)
	le(0x1000)
	le(0)
	le(0)
	le(0)
	le(0)
	for i := 0; i < w*h; i++ {
		buf = append(buf, byte(b), byte(g), byte(r), byte(a))
	}
	return buf
}

// dikCodes maps CS2 key names to DirectInput scan codes (what JIP's key events use).
var dikCodes = map[string]int{
	"escape": 1, "1": 2, "2": 3, "3": 4, "4": 5, "5": 6, "6": 7, "7": 8, "8": 9, "9": 10, "0": 11, "-": 12, "=": 13,
	"backspace": 14, "tab": 15, "q": 16, "w": 17, "e": 18, "r": 19, "t": 20, "y": 21, "u": 22, "i": 23, "o": 24,
	"p": 25, "[": 26, "]": 27, "enter": 28, "ctrl": 29, "a": 30, "s": 31, "d": 32, "f": 33, "g": 34, "h": 35,
	"j": 36, "k": 37, "l": 38, "semicolon": 39, "'": 40, "`": 41, "shift": 42, "\\": 43, "z": 44, "x": 45,
	"c": 46, "v": 47, "b": 48, "n": 49, "m": 50, ",": 51, ".": 52, "/": 53, "rshift": 54, "kp_multiply": 55,
	"alt": 56, "space": 57, "capslock": 58, "f1": 59, "f2": 60, "f3": 61, "f4": 62, "f5": 63, "f6": 64,
	"f7": 65, "f8": 66, "f9": 67, "f10": 68, "numlock": 69, "scrolllock": 70, "kp_home": 71, "kp_uparrow": 72,
	"kp_pgup": 73, "kp_minus": 74, "kp_leftarrow": 75, "kp_5": 76, "kp_rightarrow": 77, "kp_plus": 78,
	"kp_end": 79, "kp_downarrow": 80, "kp_pgdn": 81, "kp_ins": 82, "kp_del": 83, "f11": 87, "f12": 88,
	"kp_enter": 156, "rctrl": 157, "kp_slash": 181, "ralt": 184, "pause": 197, "home": 199, "uparrow": 200,
	"pgup": 201, "leftarrow": 203, "rightarrow": 205, "end": 207, "downarrow": 208, "pgdn": 209, "ins": 210,
	"del": 211,
}

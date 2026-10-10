package main

// The Black Ops side: reading Kino from the player's zombie_theater.ff with OpenAssetTools' Unlinker,
// editing its weapon files, materials and scripts, and building mods/cyberkino/mod.ff with its Linker.

import (
	"encoding/json"
	"errors"
	"fmt"
	"math"
	"os"
	"path/filepath"
	"regexp"
	"sort"
	"strconv"
	"strings"
)

// ---------------------------------------------------------------- weapon files (WEAPONFILE\key\value\...)

type infoString struct {
	Prefix string
	Keys   []string
	Values map[string]string
}

func parseInfoString(text string) (*infoString, error) {
	text = strings.TrimRight(text, "\r\n\x00 ")
	parts := strings.Split(text, "\\")
	if len(parts) < 1 || parts[0] == "" {
		return nil, errors.New("empty weapon file")
	}
	s := &infoString{Prefix: parts[0], Values: map[string]string{}}
	for i := 1; i+1 < len(parts); i += 2 {
		k := parts[i]
		if _, seen := s.Values[k]; !seen {
			s.Keys = append(s.Keys, k)
		}
		s.Values[k] = parts[i+1]
	}
	return s, nil
}

func (s *infoString) Set(k, v string) {
	if _, ok := s.Values[k]; !ok {
		s.Keys = append(s.Keys, k)
	}
	s.Values[k] = v
}

func (s *infoString) scale(k string, mult float64, asInt bool) {
	v, ok := s.Values[k]
	if !ok || v == "" {
		return
	}
	f, err := strconv.ParseFloat(v, 64)
	if err != nil {
		return
	}
	f *= mult
	if asInt {
		s.Values[k] = strconv.Itoa(int(math.Round(f)))
	} else {
		s.Values[k] = strconv.FormatFloat(f, 'f', -1, 64)
	}
}

func (s *infoString) String() string {
	var b strings.Builder
	b.WriteString(s.Prefix)
	for _, k := range s.Keys {
		b.WriteString("\\" + k + "\\" + s.Values[k])
	}
	return b.String()
}

var attachmentModelKey = regexp.MustCompile(`^(gunModel|worldModel)[0-9]+$`)

type weaponEdit struct {
	DisplayName  string
	ViewModel    string
	WorldModel   string
	DamageMult   float64
	Clip         int
	MaxAmmo      int
	FireTimeMult float64
	AmmoName     string
	MeleeDamage  int
}

func editWeapon(base string, e weaponEdit) (string, error) {
	s, err := parseInfoString(base)
	if err != nil {
		return "", err
	}
	s.Set("displayName", e.DisplayName)
	if e.ViewModel != "" {
		s.Set("gunModel", e.ViewModel)
	}
	if e.WorldModel != "" {
		s.Set("worldModel", e.WorldModel)
	}
	// attachment models of the Black Ops gun (scopes, launchers) would float on the Cyberpunk one
	for _, k := range s.Keys {
		if attachmentModelKey.MatchString(k) {
			s.Values[k] = ""
		}
	}
	if e.DamageMult > 0 {
		for _, k := range []string{"damage", "minDamage", "playerDamage", "explosionInnerDamage", "explosionOuterDamage"} {
			s.scale(k, e.DamageMult, true)
		}
	}
	if e.FireTimeMult > 0 {
		s.scale("fireTime", e.FireTimeMult, false)
	}
	if e.Clip > 0 {
		s.Set("clipSize", strconv.Itoa(e.Clip))
	}
	if e.MaxAmmo > 0 {
		s.Set("maxAmmo", strconv.Itoa(e.MaxAmmo))
		s.Set("startAmmo", strconv.Itoa(e.MaxAmmo))
	}
	if e.AmmoName != "" {
		// own ammo pool, so the gun doesn't share reserve ammo with the Black Ops gun it is built from
		s.Set("ammoName", e.AmmoName)
		s.Set("clipName", e.AmmoName)
	}
	if e.MeleeDamage > 0 {
		s.Set("meleeDamage", strconv.Itoa(e.MeleeDamage))
	}
	return s.String(), nil
}

// ---------------------------------------------------------------- materials

// cloneMaterial copies a dumped Black Ops material JSON with its colour map replaced by image and
// its normal map by the engine's flat normal map (the Black Ops gun's would not match the UVs).
func cloneMaterial(baseJSON []byte, image string) ([]byte, error) {
	var m map[string]any
	if err := json.Unmarshal(baseJSON, &m); err != nil {
		return nil, err
	}
	textures, _ := m["textures"].([]any)
	replaced := false
	for _, t := range textures {
		tm, ok := t.(map[string]any)
		if !ok {
			continue
		}
		sem, _ := tm["semantic"].(string)
		name, _ := tm["name"].(string)
		switch {
		case sem == "colorMap" || strings.EqualFold(name, "colorMap"):
			tm["image"] = image
			replaced = true
		case sem == "normalMap" || strings.EqualFold(name, "normalMap"):
			tm["image"] = "$identitynormalmap"
		}
	}
	if !replaced {
		return nil, errors.New("the Black Ops material has no colour map to replace")
	}
	return json.MarshalIndent(m, "", "  ")
}

func materialFileName(asset string) string {
	return strings.NewReplacer("*", "_", "<", "_", ">", "_", ":", "_", "\"", "_", "|", "_", "?", "_").Replace(asset)
}

// ---------------------------------------------------------------- scripts

func applyHooks(file string, text string, hooks []hookRow) (string, []string, error) {
	var notes []string
	for _, h := range hooks {
		if h.File != file {
			continue
		}
		re, err := regexp.Compile(h.Anchor)
		if err != nil {
			return "", nil, fmt.Errorf("hook %s: %w", h.ID, err)
		}
		locs := re.FindAllStringIndex(text, -1)
		if len(locs) != 1 {
			msg := fmt.Sprintf("hook %s: anchor matched %d times in %s (expected once)", h.ID, len(locs), file)
			if h.Required {
				return "", nil, errors.New(msg)
			}
			notes = append(notes, msg+"; skipped")
			continue
		}
		at := locs[0][0]
		insert := h.Text + "\n"
		if h.Action == "insert_after" {
			at = locs[0][1]
			insert = "\n" + h.Text
		}
		text = text[:at] + insert + text[at:]
		notes = append(notes, "hook "+h.ID+" applied")
	}
	return text, notes, nil
}

// ---------------------------------------------------------------- zone

type zoneFile struct {
	entries []string
	seen    map[string]bool
}

func (z *zoneFile) add(kind, name string) {
	if z.seen == nil {
		z.seen = map[string]bool{}
	}
	k := kind + "," + name
	if !z.seen[k] {
		z.seen[k] = true
		z.entries = append(z.entries, k)
	}
}

func (z *zoneFile) String() string {
	order := map[string]int{"localize": 0, "rawfile": 1, "material": 2, "xmodel": 3, "weapon": 4}
	e := append([]string{}, z.entries...)
	sort.SliceStable(e, func(i, j int) bool {
		return order[strings.SplitN(e[i], ",", 2)[0]] < order[strings.SplitN(e[j], ",", 2)[0]]
	})
	return ">game,T5\n>name,mod\n" + strings.Join(e, "\n") + "\n"
}

// ---------------------------------------------------------------- dump lookups

type boDump struct {
	Root string
}

func (d boDump) weaponFile(name string) (string, error) {
	for _, rel := range []string{filepath.Join("weapons", name), filepath.Join("weapons", "sp", name)} {
		if b, err := os.ReadFile(filepath.Join(d.Root, rel)); err == nil {
			return string(b), nil
		}
	}
	return "", fmt.Errorf("weapon %s is not in zombie_theater.ff", name)
}

func (d boDump) modelGLB(name string) string {
	return filepath.Join(d.Root, "model_export", name+"_lod0.glb")
}

func (d boDump) material(name string) ([]byte, error) {
	return os.ReadFile(filepath.Join(d.Root, "materials", materialFileName(name)+".json"))
}

func (d boDump) rawfile(rel string) (string, error) {
	b, err := os.ReadFile(filepath.Join(d.Root, filepath.FromSlash(rel)))
	return string(b), err
}

package main

import (
	"errors"
	"fmt"
	"os"
	"path/filepath"
	"strings"
)

// modBuilder writes the assets of mod.ff into OpenAssetTools' zone_raw/mod folder.
type modBuilder struct {
	l      *launcher
	dump   boDump
	raw    string // zone_raw/mod
	imgDir string
	cpOut  string
	tex    texResolver
	zone   *zoneFile
	// built once each: colour maps per gun and Cyberpunk material, materials per colour map and Black Ops material
	images    map[string]string
	imgCount  map[string]int
	materials map[string]string
}

func (b *modBuilder) write(rel string, data []byte) error {
	p := filepath.Join(b.raw, filepath.FromSlash(rel))
	if err := os.MkdirAll(filepath.Dir(p), 0o755); err != nil {
		return err
	}
	return os.WriteFile(p, data, 0o644)
}

// cpParts loads and merges the exported Cyberpunk meshes (each depot path's .glb).
func (b *modBuilder) cpParts(depot []string) ([]part, map[string]cpMaterial, error) {
	var parts []part
	mats := map[string]cpMaterial{}
	for _, d := range depot {
		rel := filepath.FromSlash(strings.ReplaceAll(d, "\\", "/"))
		noExt := strings.TrimSuffix(rel, filepath.Ext(rel))
		var found string
		for _, cand := range []string{noExt + ".glb", rel + ".glb"} {
			if _, err := os.Stat(filepath.Join(b.cpOut, cand)); err == nil {
				found = filepath.Join(b.cpOut, cand)
				break
			}
		}
		if found == "" {
			if len(parts) == 0 {
				return nil, nil, fmt.Errorf("WolvenKit did not export %s", d)
			}
			b.l.logf("  %s not exported; left out", filepath.Base(d))
			continue
		}
		g, err := readGLB(found)
		if err != nil {
			return nil, nil, fmt.Errorf("%s: %w", filepath.Base(found), err)
		}
		p, err := loadParts(g)
		if err != nil {
			return nil, nil, fmt.Errorf("%s: %w", filepath.Base(found), err)
		}
		parts = append(parts, p...)
		for k, v := range readMaterials(strings.TrimSuffix(found, ".glb") + ".Material.json") {
			mats[k] = v
		}
	}
	return parts, mats, nil
}

// image returns the colour map built for a Cyberpunk material (once per gun and material).
func (b *modBuilder) image(prefix string, cp cpMaterial) (string, error) {
	if b.images == nil {
		b.images, b.imgCount = map[string]string{}, map[string]int{}
	}
	key := prefix + "|" + cp.Name
	if name, ok := b.images[key]; ok {
		return name, nil
	}
	n := b.imgCount[prefix]
	b.imgCount[prefix] = n + 1
	image := fmt.Sprintf("cpk_%s_%d", prefix, n)
	albedo, how := b.tex.albedo(cp)
	b.l.logf("  %s: colour from %s (%s)", cp.Name, how, image)
	dds := filepath.Join(b.imgDir, image+".dds")
	if err := os.WriteFile(dds, ddsBytes(albedo), 0o644); err != nil {
		return "", err
	}
	if err := b.l.exec(b.l.tool("oat", exeName("ImageConverter")), b.imgDir, "--t5", dds); err != nil {
		return "", err
	}
	iwi, err := os.ReadFile(strings.TrimSuffix(dds, ".dds") + ".iwi")
	if err != nil {
		return "", fmt.Errorf("ImageConverter wrote no .iwi for %s", image)
	}
	if err := b.write("images/"+image+".iwi", iwi); err != nil {
		return "", err
	}
	b.images[key] = image
	return image, nil
}

// material returns our material: a copy of a Black Ops material with a Cyberpunk colour map.
func (b *modBuilder) material(prefix, boMaterial string, cp cpMaterial) (string, error) {
	if b.materials == nil {
		b.materials = map[string]string{}
	}
	image, err := b.image(prefix, cp)
	if err != nil {
		return "", err
	}
	key := boMaterial + "|" + image
	if name, ok := b.materials[key]; ok {
		return name, nil
	}
	base, err := b.dump.material(boMaterial)
	if err != nil {
		return "", fmt.Errorf("Black Ops material %s not dumped", boMaterial)
	}
	name := fmt.Sprintf("mc_%s_%d", image, len(b.materials))
	js, err := cloneMaterial(base, image)
	if err != nil {
		return "", fmt.Errorf("material %s: %w", boMaterial, err)
	}
	if err := b.write("materials/"+materialFileName(name)+".json", js); err != nil {
		return "", err
	}
	b.zone.add("material", name)
	b.materials[key] = name
	return name, nil
}

// fittedModel builds xmodel `name` from Cyberpunk meshes fitted into Black Ops model `boModel`.
func (b *modBuilder) fittedModel(name, boModel string, depot []string, fitScale float64) error {
	g, err := readGLB(b.dump.modelGLB(boModel))
	if err != nil {
		return fmt.Errorf("Black Ops model %s not dumped: %w", boModel, err)
	}
	base, err := loadBaseModel(name, g)
	if err != nil {
		return fmt.Errorf("Black Ops model %s: %w", boModel, err)
	}
	parts, mats, err := b.cpParts(depot)
	if err != nil {
		return err
	}
	fitted, info, err := fitParts(parts, base, fitScale)
	if err != nil {
		return err
	}
	b.l.logf("  %s: fitted into %s (scale %.1f, muzzle %v -> %v, %d parts)", name, boModel, info.Scale, info.CPForward, base.Forward, len(fitted))
	for _, d := range info.Dropped {
		b.l.logf("  %s: part %s lies outside the gun; left out", name, d)
	}
	return b.writeModel(name, base, fitted, mats)
}

func (b *modBuilder) writeModel(name string, base *baseModel, parts []part, mats map[string]cpMaterial) error {
	var ferr error
	data, err := writeModelGLB(base, parts, func(cpName string) string {
		cp, ok := mats[cpName]
		if !ok {
			cp = cpMaterial{Name: cpName}
		}
		m, err := b.material(imagePrefix(name), base.Material, cp)
		if err != nil && ferr == nil {
			ferr = err
		}
		return m
	})
	if ferr != nil {
		return ferr
	}
	if err != nil {
		return err
	}
	if err := b.write("model_export/"+name+".glb", data); err != nil {
		return err
	}
	js := fmt.Sprintf(`{"_type": "xmodel", "_version": 2, "type": "animated", "lods": [{"file": "model_export/%s.glb", "distance": 1000000.0}], "flags": 0}`, name)
	if err := b.write("xmodel/"+name+".json", []byte(js)); err != nil {
		return err
	}
	b.zone.add("xmodel", name)
	return nil
}

func (b *modBuilder) weapon(w weaponRow) error {
	b.l.logf("%s (from %s)", w.Name, w.Base)
	baseFile, err := b.dump.weaponFile(w.Base)
	if err != nil {
		return err
	}
	bs, err := parseInfoString(baseFile)
	if err != nil {
		return err
	}
	view, world := "cpk_"+w.ID+"_view", "cpk_"+w.ID+"_world"
	if err := b.fittedModel(view, bs.Values["gunModel"], w.Meshes, w.FitScale); err != nil {
		return fmt.Errorf("view model: %w", err)
	}
	if wm := bs.Values["worldModel"]; wm != "" {
		if err := b.fittedModel(world, wm, w.Meshes, w.FitScale); err != nil {
			b.l.logf("  world model: %v; using the view model", err)
			world = view
		}
	} else {
		world = view
	}
	edits := []struct {
		weapon, base, display string
		dmg                   float64
		clip, ammo            int
	}{
		{"cpk_" + w.ID + "_zm", w.Base, "CYBERKINO_W_" + strings.ToUpper(w.ID), w.DamageMult, w.Clip, w.MaxAmmo},
		{"cpk_" + w.ID + "_upgraded_zm", w.BaseUp, "CYBERKINO_W_" + strings.ToUpper(w.ID) + "_UP", w.PapDamageMult, w.PapClip, w.PapMaxAmmo},
	}
	for _, e := range edits {
		src, err := b.dump.weaponFile(e.base)
		if err != nil {
			return err
		}
		out, err := editWeapon(src, weaponEdit{
			DisplayName: e.display, ViewModel: view, WorldModel: world, DamageMult: e.dmg,
			Clip: e.clip, MaxAmmo: e.ammo, FireTimeMult: w.FireTimeMult, AmmoName: e.weapon,
		})
		if err != nil {
			return fmt.Errorf("%s: %w", e.base, err)
		}
		if err := b.write("weapons/"+e.weapon, []byte(out)); err != nil {
			return err
		}
		b.zone.add("weapon", e.weapon)
	}
	return nil
}

func (b *modBuilder) model(m modelRow) error {
	name := "cpk_" + m.ID
	if m.Kind == "view" {
		baseFile, err := b.dump.weaponFile(m.FitTo)
		if err != nil {
			return err
		}
		bs, err := parseInfoString(baseFile)
		if err != nil {
			return err
		}
		return b.fittedModel(name, bs.Values["gunModel"], m.Meshes, m.Scale)
	}
	parts, mats, err := b.cpParts(m.Meshes)
	if err != nil {
		return err
	}
	// rigid models take their material from the first gun built (any lit model material works)
	boMat := ""
	for _, w := range weaponRows {
		if f, err := b.dump.weaponFile(w.Base); err == nil {
			if bs, err := parseInfoString(f); err == nil {
				if g, err := readGLB(b.dump.modelGLB(bs.Values["gunModel"])); err == nil {
					if bm, err := loadBaseModel("", g); err == nil {
						boMat = bm.Material
						break
					}
				}
			}
		}
	}
	if boMat == "" {
		return errors.New("no Black Ops material to build it on")
	}
	base := &baseModel{Name: name, Nodes: []gltfNode{{Name: "tag_origin"}}, Roots: []int{0}, IBM: [][]float64{identitySlice()}, Material: boMat}
	return b.writeModel(name, base, scaleParts(parts, m.Scale), mats)
}

func (b *modBuilder) mantis() error {
	src, err := b.dump.weaponFile(mantisRow.Base)
	if err != nil {
		return err
	}
	out, err := editWeapon(src, weaponEdit{DisplayName: "CYBERKINO_W_MANTIS", ViewModel: "cpk_" + mantisRow.Model, MeleeDamage: mantisRow.MeleeDamage})
	if err != nil {
		return err
	}
	if err := b.write("weapons/cpk_mantis_zm", []byte(out)); err != nil {
		return err
	}
	b.zone.add("weapon", "cpk_mantis_zm")
	return nil
}

func (b *modBuilder) scripts() error {
	// our own scripts and strings, shipped with the mod
	for _, rel := range []string{"maps/cyberkino.gsc", "clientscripts/cyberkino.csc"} {
		data, err := os.ReadFile(filepath.Join(b.l.exeDir, "gsc", filepath.FromSlash(rel)))
		if err != nil {
			return err
		}
		if err := b.write(rel, data); err != nil {
			return err
		}
		b.zone.add("rawfile", rel)
	}
	str, err := os.ReadFile(filepath.Join(b.l.exeDir, "gsc", "english", "localizedstrings", "cyberkino.str"))
	if err != nil {
		return err
	}
	if err := b.write("english/localizedstrings/cyberkino.str", str); err != nil {
		return err
	}
	b.zone.add("localize", "cyberkino")

	// Kino's own scripts, with the hook lines added
	files := []string{}
	seen := map[string]bool{}
	for _, h := range hookRows {
		if !seen[h.File] {
			seen[h.File] = true
			files = append(files, h.File)
		}
	}
	for _, f := range files {
		text, err := b.dump.rawfile(f)
		if err != nil {
			required := false
			for _, h := range hookRows {
				required = required || (h.File == f && h.Required)
			}
			if required {
				return fmt.Errorf("Kino's %s was not found in zombie_theater.ff", f)
			}
			b.l.logf("CyberKino warning: %s not found; its hooks are skipped", f)
			continue
		}
		patched, notes, err := applyHooks(f, text, hookRows)
		if err != nil {
			return err
		}
		for _, n := range notes {
			b.l.logf("  %s", n)
		}
		if err := b.write(f, []byte(patched)); err != nil {
			return err
		}
		b.zone.add("rawfile", f)
	}
	return nil
}

// imagePrefix shares colour maps between a gun's view and world models: cpk_ajax_view -> ajax.
func imagePrefix(model string) string {
	p := strings.TrimPrefix(model, "cpk_")
	p = strings.TrimSuffix(p, "_view")
	return strings.TrimSuffix(p, "_world")
}

package main

import (
	"encoding/json"
	"math"
	"os"
	"path/filepath"
	"strings"
	"testing"
)

// boxPart is an axis-aligned box from lo to hi as a part.
func boxPart(material string, lo, hi vec3) part {
	p := part{Material: material}
	for i := 0; i < 8; i++ {
		v := lo
		if i&1 != 0 {
			v[0] = hi[0]
		}
		if i&2 != 0 {
			v[1] = hi[1]
		}
		if i&4 != 0 {
			v[2] = hi[2]
		}
		p.Pos = append(p.Pos, v)
		p.Nrm = append(p.Nrm, vec3{0, 1, 0})
		p.UV = append(p.UV, [2]float64{float64(i & 1), float64((i >> 1) & 1)})
	}
	p.Idx = []int{0, 1, 3, 0, 3, 2, 4, 6, 7, 4, 7, 5, 0, 4, 5, 0, 5, 1, 2, 3, 7, 2, 7, 6, 0, 2, 6, 0, 6, 4, 1, 5, 7, 1, 7, 3}
	return p
}

// donorGLB is shaped like WolvenKit's export of a Cyberpunk pistol: metres, muzzle at -Z, a small rig,
// two submeshes named the way WolvenKit names them.
func donorGLB(t *testing.T) *glb {
	base := &baseModel{Name: "donor", Nodes: []gltfNode{{Name: "Root", Children: []int{1}}, {Name: "Base", Translation: []float64{0, 0.05, 0}}}, Roots: []int{0}, BodyJoint: 1}
	g := &glb{Doc: gltfDoc{Nodes: base.Nodes}}
	for _, m := range g.globalMatrices() {
		base.IBM = append(base.IBM, invertAffine(m))
	}
	data, err := writeNamedMeshesGLB(base, []namedMesh{
		{Name: "0_submesh_00_LOD_1", Material: "omaha_body", Parts: []part{boxPart("x", vec3{-0.02, 0, -0.12}, vec3{0.02, 0.06, 0.1})}},
		{Name: "1_submesh_01_LOD_1", Material: "omaha_glass", Parts: []part{boxPart("y", vec3{-0.01, 0.06, -0.05}, vec3{0.01, 0.07, 0.0})}},
	})
	if err != nil {
		t.Fatal(err)
	}
	out, err := parseGLB(data)
	if err != nil {
		t.Fatal(err)
	}
	return out
}

func TestRayGunOntoDonor(t *testing.T) {
	g := donorGLB(t)
	base, err := loadBaseModel("donor", g)
	if err != nil {
		t.Fatal(err)
	}
	base.Forward = vec3{0, 0, -1}
	names := meshNames(g)
	if len(names) != 2 || names[0].Name != "0_submesh_00_LOD_1" || names[1].Material != "omaha_glass" {
		t.Fatalf("mesh names %+v", names)
	}
	// a Black Ops-like ray gun: inches, muzzle at +X, a tall grip at the back
	ray := []part{
		boxPart("body", vec3{-4, 2, -1}, vec3{8, 5, 1}),
		boxPart("grip", vec3{-4, -3, -0.8}, vec3{-1, 2, 0.8}),
	}
	fitted, info, err := fitPartsFrom(ray, vec3{1, 0, 0}, base, 1)
	if err != nil {
		t.Fatal(err)
	}
	b := partsBBox(fitted)
	if math.Abs(b.extent()[2]-0.22) > 1e-6 {
		t.Errorf("Ray Gun length %.4f m, want the donor's 0.22", b.extent()[2])
	}
	grip := partsBBox(fitted[1:])
	if grip.center()[2] <= b.center()[2] {
		t.Errorf("the grip should be at the back (+Z), got %v vs %v", grip.center(), b.center())
	}
	if math.Abs(info.Scale-0.22/12) > 1e-9 {
		t.Errorf("scale %v", info.Scale)
	}
	names[0].Parts = fitted
	data, err := writeNamedMeshesGLB(base, names)
	if err != nil {
		t.Fatal(err)
	}
	back, err := parseGLB(data)
	if err != nil {
		t.Fatal(err)
	}
	if len(back.Doc.Meshes) != 2 || back.Doc.Meshes[0].Name != "0_submesh_00_LOD_1" || back.Doc.Meshes[1].Name != "1_submesh_01_LOD_1" {
		t.Fatalf("submesh names not kept: %+v", back.Doc.Meshes)
	}
	parts, _ := loadParts(back)
	if len(parts[1].Pos) != 3 || partsBBox(parts[1:2]).extent()[0] > 0.001 {
		t.Errorf("the second submesh should be emptied to a tiny triangle")
	}
	if len(back.Doc.Skins) != 1 || len(back.Doc.Skins[0].Joints) != 2 {
		t.Errorf("donor rig not kept")
	}
}

func TestSimplify(t *testing.T) {
	p := part{Material: "m"}
	n := 300
	for i := 0; i < n; i++ {
		for j := 0; j < n; j++ {
			a := float64(j) / float64(n) * 2 * math.Pi
			p.Pos = append(p.Pos, vec3{0.02 * math.Cos(a), 0.03 * math.Sin(a), -0.15 + 0.3*float64(i)/float64(n-1)})
			p.Nrm = append(p.Nrm, vec3{math.Cos(a), math.Sin(a), 0})
			p.UV = append(p.UV, [2]float64{0, 0})
		}
	}
	for i := 0; i+1 < n; i++ {
		for j := 0; j < n; j++ {
			a, b, c, d := i*n+j, i*n+(j+1)%n, (i+1)*n+j, (i+1)*n+(j+1)%n
			p.Idx = append(p.Idx, a, c, b, b, c, d)
		}
	}
	out, count := simplify([]part{p}, maxModelVerts)
	if count > maxModelVerts || count < maxModelVerts/4 || len(out[0].Idx) == 0 {
		t.Fatalf("simplified to %d vertices", count)
	}
}

func TestPresetKeys(t *testing.T) {
	dir := t.TempDir()
	cetDir := filepath.Join(dir, "bin", "x64", "plugins", "cyber_engine_tweaks")
	os.MkdirAll(cetDir, 0o755)
	path := filepath.Join(cetDir, "bindings.json")
	os.WriteFile(path, []byte(`{"cet": {"overlay_key": 13510798882111488}, "cyberkino": {"use": 19140298416324608}}`), 0o644)
	l := &launcher{cpDir: dir}
	if err := l.presetKeys(); err != nil {
		t.Fatal(err)
	}
	var cfg map[string]map[string]uint64
	data, _ := os.ReadFile(path)
	if err := json.Unmarshal(data, &cfg); err != nil {
		t.Fatal(err)
	}
	if cfg["cet"]["overlay_key"] != 13510798882111488 {
		t.Error("CET's own binding was changed")
	}
	if cfg["cyberkino"]["use"] != 19140298416324608 {
		t.Error("a key the player already set was overwritten")
	}
	if cfg["cyberkino"]["start"] != 118<<48 || cfg["cyberkino"]["sandevistan"] != 90<<48 {
		t.Errorf("defaults not added: %v", cfg["cyberkino"])
	}
	// a second run changes nothing
	before, _ := os.ReadFile(path)
	l.presetKeys()
	after, _ := os.ReadFile(path)
	if string(before) != string(after) {
		t.Error("second run rewrote bindings.json")
	}
}

func TestParseHelpers(t *testing.T) {
	out := "\r\nHKEY_CURRENT_USER\\Software\\Valve\\Steam\r\n    SteamExe    REG_SZ    c:/program files (x86)/steam/steam.exe\r\n"
	if got := parseRegValue(out, "SteamExe"); got != "c:/program files (x86)/steam/steam.exe" {
		t.Fatalf("got %q", got)
	}
	s, err := parseInfoString(`WEAPONFILE\displayName\ZOMBIE_RAYGUN\worldModel\weapon_usa_ray_gun\damage\1000`)
	if err != nil || s.Values["worldModel"] != "weapon_usa_ray_gun" || s.Values["damage"] != "1000" {
		t.Fatalf("weapon file: %v %v", s, err)
	}
	if !strings.HasPrefix(depotRel(rayGun.DonorMesh), "base") {
		t.Error("depot path")
	}
}

package main

import (
	"bytes"
	"encoding/binary"
	"math"
	"os"
	"os/exec"
	"path/filepath"
	"strings"
	"testing"
)

func TestInfoStringEdit(t *testing.T) {
	base := `WEAPONFILE\displayName\ZOMBIE_COMMANDO\gunModel\viewmodel_commando\gunModel2\viewmodel_commando_acog\worldModel\t5_weapon_commando_world\damage\80\minDamage\50\clipSize\30\maxAmmo\270\fireTime\0.08\ammoName\commando\clipName\commando`
	out, err := editWeapon(base, weaponEdit{DisplayName: "CYBERKINO_W_AJAX", ViewModel: "cpk_ajax_view", WorldModel: "cpk_ajax_world",
		DamageMult: 1.1, Clip: 45, MaxAmmo: 360, FireTimeMult: 1.5, AmmoName: "cpk_ajax_zm"})
	if err != nil {
		t.Fatal(err)
	}
	s, _ := parseInfoString(out)
	want := map[string]string{"displayName": "CYBERKINO_W_AJAX", "gunModel": "cpk_ajax_view", "gunModel2": "", "worldModel": "cpk_ajax_world",
		"damage": "88", "minDamage": "55", "clipSize": "45", "maxAmmo": "360", "startAmmo": "360", "fireTime": "0.12", "ammoName": "cpk_ajax_zm", "clipName": "cpk_ajax_zm"}
	for k, v := range want {
		if s.Values[k] != v {
			t.Errorf("%s = %q, want %q", k, s.Values[k], v)
		}
	}
	if !strings.HasPrefix(out, `WEAPONFILE\displayName\CYBERKINO_W_AJAX\gunModel\`) {
		t.Errorf("key order not kept: %s", out[:60])
	}
}

const theaterSample = `main()
{
	level thread maps\_callbackglobal::SetupCallbacks();
	include_weapons();
	maps\_zombiemode::main();
	level thread something();
}
`

func TestHooks(t *testing.T) {
	out, notes, err := applyHooks("maps/zombie_theater.gsc", theaterSample, hookRows)
	if err != nil {
		t.Fatal(err)
	}
	pre := strings.Index(out, `maps\cyberkino::pre_main();`)
	call := strings.Index(out, `maps\_zombiemode::main();`)
	post := strings.Index(out, `maps\cyberkino::post_main();`)
	if pre < 0 || call < 0 || post < 0 || !(pre < call && call < post) {
		t.Fatalf("hooks in the wrong place:\n%s", out)
	}
	if len(notes) != 2 {
		t.Errorf("notes: %v", notes)
	}
	if _, _, err := applyHooks("maps/zombie_theater.gsc", "main()\n{\n}\n", hookRows); err == nil {
		t.Error("a missing required anchor must fail")
	}
	csc := "include_weapons()\n{\n\tinclude_weapon( \"m1911_zm\", false );\n}\n"
	out, _, err = applyHooks("clientscripts/zombie_theater.csc", csc, hookRows)
	if err != nil || !strings.Contains(out, "{\n\tclientscripts\\cyberkino::include_weapons();") {
		t.Fatalf("client hook: %v\n%s", err, out)
	}
}

// boxPart is an axis-aligned box from lo to hi as a part.
func boxPart(material string, lo, hi vec3) part {
	p := part{Material: material}
	for i := 0; i < 8; i++ {
		v := vec3{lo[0], lo[1], lo[2]}
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

// syntheticBase writes a glb shaped like an OpenAssetTools view model dump: tag_origin > j_gun > tag_flash,
// a gun 20 units long along +X (muzzle at +X), every vertex on j_gun.
func syntheticBase(t *testing.T) []byte {
	base := &baseModel{
		Name: "viewmodel_test",
		Nodes: []gltfNode{
			{Name: "tag_origin", Children: []int{1}},
			{Name: "j_gun", Translation: []float64{2, 1, 0}, Children: []int{2}},
			{Name: "tag_flash", Translation: []float64{13, 1, 0}},
		},
		Roots:     []int{0},
		BodyJoint: 1,
	}
	g := &glb{Doc: gltfDoc{Nodes: base.Nodes}}
	for _, m := range g.globalMatrices() {
		base.IBM = append(base.IBM, invertAffine(m))
	}
	data, err := writeModelGLB(base, []part{boxPart("mtl_test", vec3{-5, -2, -1}, vec3{15, 4, 1})}, func(s string) string { return s })
	if err != nil {
		t.Fatal(err)
	}
	return data
}

func TestFitIntoBase(t *testing.T) {
	g, err := parseGLB(syntheticBase(t))
	if err != nil {
		t.Fatal(err)
	}
	base, err := loadBaseModel("cpk_test_view", g)
	if err != nil {
		t.Fatal(err)
	}
	if base.Forward != (vec3{1, 0, 0}) {
		t.Fatalf("base forward %v, want +X (from tag_flash)", base.Forward)
	}
	if base.BodyJoint != 1 || len(base.Nodes) != 3 || base.Nodes[0].Name != "tag_origin" {
		t.Fatalf("skeleton not kept: joint %d, nodes %v", base.BodyJoint, base.Nodes)
	}
	// A Cyberpunk-like gun in metres: 0.3 long along Z, barrel at -Z (thin), grip at +Z (tall).
	cp := []part{
		boxPart("body", vec3{-0.02, 0, -0.15}, vec3{0.02, 0.05, 0.15}),
		boxPart("grip", vec3{-0.015, -0.12, 0.08}, vec3{0.015, 0, 0.14}),
		boxPart("stray", vec3{5, 5, 5}, vec3{5.1, 5.1, 5.1}),
	}
	fitted, info, err := fitParts(cp, base, 1.0)
	if err != nil {
		t.Fatal(err)
	}
	if len(info.Dropped) != 1 || info.Dropped[0] != "stray" {
		t.Errorf("stray part not dropped: %v", info.Dropped)
	}
	if info.CPForward != (vec3{0, 0, -1}) {
		t.Errorf("Cyberpunk muzzle %v, want -Z", info.CPForward)
	}
	b := partsBBox(fitted)
	if l := b.extent()[0]; math.Abs(l-20) > 1e-6 {
		t.Errorf("fitted length %.3f, want 20", l)
	}
	// the grip (was at +Z, the back) must now be at -X, the back of the Black Ops gun
	grip := partsBBox(fitted[1:2])
	if grip.center()[0] >= b.center()[0] {
		t.Errorf("grip ended up at the front: %v vs %v", grip.center(), b.center())
	}
	if math.Abs(b.center()[0]-5) > 1e-6 || math.Abs(b.center()[1]-1) > 1e-6 {
		t.Errorf("not centred on the base: %v", b.center())
	}
	out, err := writeModelGLB(base, fitted, func(s string) string { return "mc_" + s })
	if err != nil {
		t.Fatal(err)
	}
	back, err := parseGLB(out)
	if err != nil {
		t.Fatal(err)
	}
	if len(back.Doc.Skins) != 1 || len(back.Doc.Skins[0].Joints) != 3 || len(back.Doc.Materials) != 2 || back.Doc.Materials[0].Name != "mc_body" {
		t.Fatalf("written model wrong: %+v", back.Doc)
	}
}

func TestDDS(t *testing.T) {
	img := newRGBA(1000, 300, [4]float64{1, 0.5, 0, 1})
	d := ddsBytes(img)
	if string(d[:4]) != "DDS " {
		t.Fatal("no DDS magic")
	}
	h, w := binary.LittleEndian.Uint32(d[12:]), binary.LittleEndian.Uint32(d[16:])
	mips := binary.LittleEndian.Uint32(d[28:])
	if w != 512 || h != 256 || mips != 10 {
		t.Fatalf("got %dx%d with %d mips, want 512x256 with 10", w, h, mips)
	}
	size := 0
	for lw, lh := 512, 256; ; lw, lh = max(1, lw/2), max(1, lh/2) {
		size += lw * lh * 4
		if lw == 1 && lh == 1 {
			break
		}
	}
	if len(d) != 128+size {
		t.Fatalf("DDS is %d bytes, want %d", len(d), 128+size)
	}
	if !bytes.Equal(d[128:132], []byte{0, 127, 255, 255}) {
		t.Errorf("first pixel %v, want BGRA 0,127,255,255", d[128:132])
	}
}

func TestZoneFile(t *testing.T) {
	z := &zoneFile{}
	z.add("weapon", "cpk_ajax_zm")
	z.add("xmodel", "cpk_ajax_view")
	z.add("localize", "cyberkino")
	z.add("xmodel", "cpk_ajax_view")
	want := ">game,T5\n>name,mod\nlocalize,cyberkino\nxmodel,cpk_ajax_view\nweapon,cpk_ajax_zm\n"
	if z.String() != want {
		t.Fatalf("zone:\n%s", z.String())
	}
}

func TestMaterialClone(t *testing.T) {
	base := `{"_type":"material","_version":1,"_game":"t5","techniqueSet":"wc_l_sm_r0c0n0s0","textures":[{"name":"colorMap","semantic":"colorMap","image":"~weapon_col"},{"name":"normalMap","semantic":"normalMap","image":"weapon_nml"},{"name":"specularMap","semantic":"specularMap","image":"weapon_spc"}]}`
	out, err := cloneMaterial([]byte(base), "cpk_ajax_0")
	if err != nil {
		t.Fatal(err)
	}
	s := string(out)
	for _, want := range []string{`"image": "cpk_ajax_0"`, `"image": "$identitynormalmap"`, `"image": "weapon_spc"`, `"techniqueSet": "wc_l_sm_r0c0n0s0"`} {
		if !strings.Contains(s, want) {
			t.Errorf("missing %s in %s", want, s)
		}
	}
}

// TestLinkerReadsFittedModel runs OpenAssetTools' Linker (set OAT_LINKER to it) on a fitted model, to
// prove the glTF and xmodel JSON the launcher writes are accepted. Materials are left to the Linker's
// defaults here; on a player's PC they come from Black Ops' own zones.
func TestLinkerReadsFittedModel(t *testing.T) {
	linker := os.Getenv("OAT_LINKER")
	if linker == "" {
		t.Skip("OAT_LINKER not set")
	}
	dir := t.TempDir()
	raw := filepath.Join(dir, "zone_raw", "mod")
	os.MkdirAll(filepath.Join(raw, "model_export"), 0o755)
	os.MkdirAll(filepath.Join(raw, "xmodel"), 0o755)
	os.MkdirAll(filepath.Join(dir, "zone_source"), 0o755)
	g, _ := parseGLB(syntheticBase(t))
	base, _ := loadBaseModel("cpk_test_view", g)
	dense, _ := simplify([]part{densePart(300)}, maxModelVerts)
	fitted, _, err := fitParts(dense, base, 1)
	if err != nil {
		t.Fatal(err)
	}
	data, _ := writeModelGLB(base, fitted, func(string) string { return "mc_cpk_test_0" })
	os.WriteFile(filepath.Join(raw, "model_export", "cpk_test_view.glb"), data, 0o644)
	os.WriteFile(filepath.Join(raw, "xmodel", "cpk_test_view.json"), []byte(`{"_type": "xmodel", "_version": 2, "type": "animated", "lods": [{"file": "model_export/cpk_test_view.glb", "distance": 1000000.0}], "flags": 0}`), 0o644)
	z := &zoneFile{}
	z.add("material", ",mc_cpk_test_0") // a reference, as a material from Black Ops' own zones would be
	z.add("xmodel", "cpk_test_view")
	// a weapon file edited the way the launcher edits the dumped Black Ops ones
	weapon, err := editWeapon(`WEAPONFILE\displayName\ZOMBIE_TEST\aiVsAiAccuracyGraph\pistol.accu\aiVsPlayerAccuracyGraph\pistol.accu\weaponType\bullet\weaponClass\rifle\inventoryType\primary\fireType\Full Auto\gunModel\viewmodel_test\worldModel\\damage\40\minDamage\20\clipSize\30\maxAmmo\120\fireTime\0.1`,
		weaponEdit{DisplayName: "CYBERKINO_W_TEST", ViewModel: "cpk_test_view", WorldModel: "cpk_test_view", DamageMult: 2, Clip: 12, MaxAmmo: 48, FireTimeMult: 1, AmmoName: "cpk_test_zm"})
	if err != nil {
		t.Fatal(err)
	}
	b := &modBuilder{l: &launcher{}, dump: boDump{Roots: []string{filepath.Join(dir, "nodump")}}, raw: raw, zone: z}
	if err := b.writeWeapon("cpk_test_zm", weapon); err != nil {
		t.Fatal(err)
	}
	os.WriteFile(filepath.Join(dir, "zone_source", "mod.zone"), []byte(z.String()), 0o644)
	out, err := exec.Command(linker, "-b", dir, "-v", "mod").CombinedOutput()
	t.Logf("%s", stripANSI(string(out)))
	if err != nil {
		t.Fatalf("Linker failed: %v", err)
	}
	if st, err := os.Stat(filepath.Join(dir, "zone_out", "mod", "mod.ff")); err != nil || st.Size() < 200 {
		t.Fatalf("no mod.ff with the model: %v", err)
	}
	// read it back: the model must be in the zone with its bones
	unlinker := filepath.Join(filepath.Dir(linker), "Unlinker")
	dump := filepath.Join(dir, "dump")
	out, err = exec.Command(unlinker, "--model-format", "GLB", "-o", dump, filepath.Join(dir, "zone_out", "mod", "mod.ff")).CombinedOutput()
	if err != nil {
		t.Fatalf("Unlinker: %v %s", err, out)
	}
	back, err := readGLB(filepath.Join(dump, "model_export", "cpk_test_view_lod0.glb"))
	if err != nil {
		t.Fatalf("model not dumped back: %v", err)
	}
	names := []string{}
	for _, n := range back.Doc.Nodes {
		names = append(names, n.Name)
	}
	t.Logf("nodes after round trip: %v", names)
	if !strings.Contains(strings.Join(names, ","), "tag_flash") {
		t.Errorf("tag_flash lost in the round trip: %v", names)
	}
	wf, err := os.ReadFile(filepath.Join(dump, "weapons", "cpk_test_zm"))
	if err != nil {
		t.Fatalf("weapon not dumped back: %v", err)
	}
	ws, _ := parseInfoString(string(wf))
	for k, v := range map[string]string{"gunModel": "cpk_test_view", "damage": "80", "clipSize": "12", "displayName": "CYBERKINO_W_TEST"} {
		if ws.Values[k] != v {
			t.Errorf("weapon %s = %q after the round trip, want %q", k, ws.Values[k], v)
		}
	}
	rb, err := loadBaseModel("x", back)
	if err != nil {
		t.Fatal(err)
	}
	t.Logf("round-trip box %v, forward %v", rb.BBox, rb.Forward)
	if math.Abs(rb.BBox.extent()[0]-20) > 0.05 {
		t.Errorf("round trip changed the model: box %v forward %v", rb.BBox, rb.Forward)
	}
}

// densePart is a 0.3 m long tube-ish grid with about n*n vertices, like a Cyberpunk gun's density.
func densePart(n int) part {
	p := part{Material: "Default", Mesh: "0_submesh_00_LOD_1"}
	for i := 0; i < n; i++ {
		for j := 0; j < n; j++ {
			a := float64(j) / float64(n) * 2 * math.Pi
			p.Pos = append(p.Pos, vec3{0.02 * math.Cos(a), 0.03 * math.Sin(a), -0.15 + 0.3*float64(i)/float64(n-1)})
			p.Nrm = append(p.Nrm, vec3{math.Cos(a), math.Sin(a), 0})
			p.UV = append(p.UV, [2]float64{float64(j) / float64(n), float64(i) / float64(n)})
		}
	}
	for i := 0; i+1 < n; i++ {
		for j := 0; j < n; j++ {
			a, b, c, d := i*n+j, i*n+(j+1)%n, (i+1)*n+j, (i+1)*n+(j+1)%n
			p.Idx = append(p.Idx, a, c, b, b, c, d)
		}
	}
	return p
}

func TestSimplify(t *testing.T) {
	parts := []part{densePart(300)} // 90,000 vertices
	out, n := simplify(parts, maxModelVerts)
	if n > maxModelVerts || n < maxModelVerts/4 {
		t.Fatalf("simplified to %d vertices, want at most %d and not far below", n, maxModelVerts)
	}
	got := 0
	for _, p := range out {
		got += len(p.Pos)
		for _, i := range p.Idx {
			if i < 0 || i >= len(p.Pos) {
				t.Fatal("index out of range after simplify")
			}
		}
	}
	if got != n || len(out[0].Idx) == 0 {
		t.Fatalf("count %d vs %d, %d indices", got, n, len(out[0].Idx))
	}
	b0, b1 := partsBBox(parts), partsBBox(out)
	if math.Abs(b0.extent()[2]-b1.extent()[2]) > 0.01 {
		t.Errorf("simplify changed the length: %v vs %v", b0.extent(), b1.extent())
	}
}

func TestSubmeshMaterials(t *testing.T) {
	dir := t.TempDir()
	p := filepath.Join(dir, "w.Material.json")
	os.WriteFile(p, []byte(`{"Header":{},"Data":{"MaterialRepo":"x","Materials":[{"Name":"body","Data":{}}],"Appearances":{"default":["body","mag"],"zz":["a"]}}}`), 0o644)
	names := submeshMaterials(p)
	if strings.Join(names, ",") != "body,mag" {
		t.Fatalf("got %v", names)
	}
	for name, want := range map[string]int{"1_submesh_01_LOD_1": 1, "submesh_03_LOD_1": 3, "0_x": 0, "mesh": 7} {
		if got, _ := submeshIndex(name, 7); got != want {
			t.Errorf("%s -> %d, want %d", name, got, want)
		}
	}
}

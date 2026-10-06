package main

import (
	"bytes"
	"compress/zlib"
	"encoding/binary"
	"math"
	"os"
	"path/filepath"
	"strings"
	"testing"
)

// fakeWeapon builds a WEAP record shaped like a vanilla one: EDID, FULL, DATA (15 bytes), DNAM (204 bytes).
func fakeWeapon(formID uint32, edid string, damage int16, clip byte, fireRate, shots float32, compressed bool) []byte {
	data := make([]byte, 15)
	binary.LittleEndian.PutUint16(data[12:14], uint16(damage))
	data[14] = clip
	dnam := make([]byte, 204)
	dnam[12] = 0x01 // 'Ignores Normal Weapon Resistance' must survive
	binary.LittleEndian.PutUint32(dnam[64:68], math.Float32bits(fireRate))
	binary.LittleEndian.PutUint32(dnam[88:92], math.Float32bits(shots))
	rec := &record{typ: "WEAP", formID: formID, version: 15, subs: []subrecord{
		{"EDID", append([]byte(edid), 0)}, {"FULL", []byte("Vanilla\x00")}, {"MODL", []byte("weapons\\x.nif\x00")},
		{"DATA", data}, {"DNAM", dnam},
	}}
	raw := rec.encode()
	if !compressed {
		return raw
	}
	body := raw[headerSize:]
	var z bytes.Buffer
	zw := zlib.NewWriter(&z)
	zw.Write(body)
	zw.Close()
	var out bytes.Buffer
	out.Write(raw[:4])
	binary.Write(&out, binary.LittleEndian, uint32(4+z.Len()))
	binary.Write(&out, binary.LittleEndian, binary.LittleEndian.Uint32(raw[8:12])|flagCompressed)
	out.Write(raw[12:headerSize])
	binary.Write(&out, binary.LittleEndian, uint32(len(body)))
	out.Write(z.Bytes())
	return out.Bytes()
}

func fakeESM(t *testing.T) string {
	t.Helper()
	var esm bytes.Buffer
	esm.Write(headerRecord(4, 0x800))
	esm.Write(groupBytes("GMST", [][]byte{(&record{typ: "GMST", formID: 0x10, subs: []subrecord{{"EDID", []byte("x\x00")}}}).encode()}))
	esm.Write(groupBytes("WEAP", [][]byte{
		fakeWeapon(0x0E3778, "Weap9mmPistol", 22, 13, 2.0, 2.0, false),
		fakeWeapon(0x0E9C3B, "WeapNVServiceRifle", 20, 24, 3.0, 3.0, true),
		fakeWeapon(0x004353, "WeapNVSniperRifle", 50, 5, 1.0, 1.0, false),
		fakeWeapon(0x000123, "Other", 1, 1, 1, 1, false),
	}))
	esm.Write(groupBytes("AMMO", nil))
	p := filepath.Join(t.TempDir(), "FalloutNV.esm")
	if err := os.WriteFile(p, esm.Bytes(), 0o644); err != nil {
		t.Fatal(err)
	}
	return p
}

func f32(b []byte) float32 { return math.Float32frombits(binary.LittleEndian.Uint32(b)) }

func TestBuildPluginAppliesSheet(t *testing.T) {
	esm := fakeESM(t)
	out := filepath.Join(t.TempDir(), "CSNV.esp")
	written, errs := buildPlugin(esm, out, sheetWeapons)
	if len(errs) > 0 {
		t.Fatalf("errors: %v", errs)
	}
	if len(written) != len(sheetWeapons) {
		t.Fatalf("wrote %v", written)
	}
	f, _ := os.Open(out)
	defer f.Close()
	// the header must name FalloutNV.esm as the only master
	hdr := make([]byte, headerSize)
	f.Read(hdr)
	if string(hdr[:4]) != "TES4" {
		t.Fatalf("first record %q", hdr[:4])
	}
	body := make([]byte, binary.LittleEndian.Uint32(hdr[4:8]))
	f.Read(body)
	if !bytes.Contains(body, []byte("MAST\x0e\x00FalloutNV.esm\x00")) {
		t.Fatal("missing MAST FalloutNV.esm")
	}
	want := map[uint32]bool{}
	for _, w := range sheetWeapons {
		want[0x01000000|w.PluginForm] = true
	}
	f.Seek(0, 0)
	recs, err := findRecords(f, "WEAP", want)
	if err != nil || len(recs) != len(sheetWeapons) {
		t.Fatalf("re-read %d records, err %v", len(recs), err)
	}
	base := map[uint32][3]float32{0x0E3778: {22, 2, 2}, 0x0E9C3B: {20, 3, 3}, 0x004353: {50, 1, 1}}
	for _, w := range sheetWeapons {
		r := recs[0x01000000|w.PluginForm]
		if got := strings.TrimRight(string(r.sub("EDID").data), "\x00"); got != w.ID {
			t.Errorf("EDID %q, want %q", got, w.ID)
		}
		if got := strings.TrimRight(string(r.sub("FULL").data), "\x00"); got != w.Name {
			t.Errorf("FULL %q, want %q", got, w.Name)
		}
		d := r.sub("DATA").data
		if dmg := int16(binary.LittleEndian.Uint16(d[12:14])); float64(dmg) != math.Round(float64(base[w.BaseForm][0])*w.DamageMult) {
			t.Errorf("%s damage %d", w.ID, dmg)
		}
		if int(d[14]) != w.ClipSize {
			t.Errorf("%s clip %d, want %d", w.ID, d[14], w.ClipSize)
		}
		dn := r.sub("DNAM").data
		if auto := dn[12]&0x02 != 0; auto != w.Automatic {
			t.Errorf("%s automatic %v", w.ID, auto)
		}
		if dn[12]&0x01 == 0 {
			t.Errorf("%s lost an unrelated flag", w.ID)
		}
		if got, want := f32(dn[64:68]), base[w.BaseForm][1]*float32(w.FireRateMult); math.Abs(float64(got-want)) > 1e-5 {
			t.Errorf("%s fire rate %v, want %v", w.ID, got, want)
		}
		if got, want := f32(dn[88:92]), base[w.BaseForm][2]*float32(w.FireRateMult); math.Abs(float64(got-want)) > 1e-5 {
			t.Errorf("%s shots/sec %v, want %v", w.ID, got, want)
		}
		if r.sub("MODL") == nil {
			t.Errorf("%s lost its model", w.ID)
		}
	}
}

func TestBuildPluginReportsMissingBase(t *testing.T) {
	esm := fakeESM(t)
	rows := append([]weaponRow(nil), sheetWeapons...)
	rows = append(rows, weaponRow{ID: "Ghost", BaseForm: 0xABCDEF, PluginForm: 0x900, DamageMult: 1, ClipSize: 1, FireRateMult: 1})
	written, errs := buildPlugin(esm, filepath.Join(t.TempDir(), "CSNV.esp"), rows)
	if len(written) != len(sheetWeapons) || len(errs) != 1 || !strings.Contains(errs[0].Error(), "Ghost") {
		t.Fatalf("written %v errs %v", written, errs)
	}
}

const sampleKeys = `"config"
{
	"bindings"
	{
		"b"		"buymenu"
		"w"		"+forward"
		"MOUSE1"		"+attack"
	}
}`

const sampleConvars = `"config"
{
	"convars"
	{
		"cl_crosshaircolor"		"5"
		"cl_crosshaircolor_r"		"255"
		"cl_crosshaircolor_g"		"0"
		"cl_crosshaircolor_b"		"255"
		"cl_crosshairsize"		"2.5"
		"cl_crosshairgap"		"-2"
		"cl_crosshairthickness"		"1"
		"cl_crosshairdot"		"true"
		"cl_crosshairusealpha"		"1"
		"cl_crosshairalpha"		"180"
	}
}`

func TestParseAndResolveCS2(t *testing.T) {
	_, binds := parseVCFG(sampleKeys)
	if binds["b"] != "buymenu" || binds["mouse1"] != "+attack" {
		t.Fatalf("bindings %v", binds)
	}
	conv, _ := parseVCFG(sampleConvars)
	binds["b"] = ""
	binds["n"] = "buymenu" // player moved the buy menu to N
	s := resolveCS2(conv, binds, "test")
	if s.BuyKeyName != "n" || s.BuyKey != 49 {
		t.Errorf("buy key %q %d", s.BuyKeyName, s.BuyKey)
	}
	if s.R != 255 || s.G != 0 || s.B != 255 || s.A != 180 {
		t.Errorf("colour %d,%d,%d,%d", s.R, s.G, s.B, s.A)
	}
	if s.Length != 5 || s.Gap != 2 || s.Thickness != 2 {
		t.Errorf("geometry %g %g %g", s.Length, s.Gap, s.Thickness)
	}
	if s.Dot != 1 {
		t.Errorf("dot %d", s.Dot)
	}
}

func TestResolveDefaultsWithoutCS2Files(t *testing.T) {
	s := resolveCS2(map[string]string{}, map[string]string{}, "none")
	if s.BuyKey != 48 || s.R != 50 || s.G != 250 || s.B != 50 || s.A != 255 || s.Length != 10 || s.Gap != 5 || s.Thickness != 1 {
		t.Errorf("defaults %+v", s)
	}
}

func TestCS2FilesFoundInSteamUserdata(t *testing.T) {
	root := t.TempDir()
	cfg := filepath.Join(root, "userdata", "12345", "730", "local", "cfg")
	os.MkdirAll(cfg, 0o755)
	os.WriteFile(filepath.Join(cfg, "cs2_user_keys_0_slot0.vcfg"), []byte(strings.Replace(sampleKeys, `"b"`, `"x"`, 1)), 0o644)
	os.WriteFile(filepath.Join(cfg, "cs2_user_convars_0_slot0.vcfg"), []byte(sampleConvars), 0o644)
	cs2 := filepath.Join(root, "steamapps", "common", "Counter-Strike Global Offensive")
	os.MkdirAll(filepath.Join(cs2, "game", "csgo", "cfg"), 0o755)
	os.WriteFile(filepath.Join(cs2, "game", "csgo", "cfg", "user_keys_default.vcfg"), []byte(sampleKeys), 0o644)
	s := readCS2(cs2, func(string, ...any) {})
	if s.BuyKeyName != "x" || s.R != 255 {
		t.Errorf("got %+v", s)
	}
}

func TestActivatePlugin(t *testing.T) {
	dir := t.TempDir()
	data := filepath.Join(dir, "Data")
	os.MkdirAll(data, 0o755)
	os.WriteFile(filepath.Join(data, "DeadMoney.esm"), nil, 0o644)
	txt := filepath.Join(dir, "FalloutNV", "plugins.txt")
	added, err := activatePlugin(txt, data)
	if err != nil || !added {
		t.Fatal(added, err)
	}
	b, _ := os.ReadFile(txt)
	if string(b) != "FalloutNV.esm\r\nDeadMoney.esm\r\nCSNV.esp\r\n" {
		t.Fatalf("new plugins.txt %q", b)
	}
	if added, _ := activatePlugin(txt, data); added {
		t.Fatal("added twice")
	}
	os.WriteFile(txt, []byte("FalloutNV.esm\r\nSomeMod.esp\r\n\r\n"), 0o644)
	activatePlugin(txt, data)
	b, _ = os.ReadFile(txt)
	if string(b) != "FalloutNV.esm\r\nSomeMod.esp\r\nCSNV.esp\r\n" {
		t.Fatalf("existing plugins.txt %q", b)
	}
}

func TestSolidDDS(t *testing.T) {
	d := solidDDS(1, 2, 3, 4)
	if len(d) != 128+8*8*4 || string(d[:4]) != "DDS " || !bytes.Equal(d[128:132], []byte{3, 2, 1, 4}) {
		t.Fatalf("dds header/pixel wrong: %d bytes", len(d))
	}
}

func TestFindCS2NextToNewVegas(t *testing.T) {
	common := filepath.Join(t.TempDir(), "steamapps", "common")
	fnv := filepath.Join(common, "Fallout New Vegas")
	cs2 := filepath.Join(common, "Counter-Strike Global Offensive")
	os.MkdirAll(fnv, 0o755)
	if got := findCS2Dir(fnv); got != "" {
		t.Fatalf("found %q with no CS2 installed", got)
	}
	os.MkdirAll(filepath.Join(cs2, "game", "csgo"), 0o755)
	if got := findCS2Dir(fnv); got != cs2 {
		t.Fatalf("got %q, want %q", got, cs2)
	}
}

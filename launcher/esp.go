package main

// Builds Data/CSNV.esp on the player's PC: the vanilla weapon records named in sheets/weapons.json are
// copied out of their own FalloutNV.esm under new form IDs, with the sheet's name and stats applied.
// Record layouts follow xEdit's Fallout: New Vegas definitions (wbDefinitionsFNV.pas):
//   DATA: Value s32, Health s32, Weight f32, Base Damage s16 @12, Clip Size u8 @14
//   DNAM: Flags 1 u8 @12 (0x02 = Is Automatic), Fire Rate f32 @64, Attack Shots/Sec f32 @88

import (
	"bytes"
	"compress/zlib"
	"encoding/binary"
	"errors"
	"fmt"
	"io"
	"math"
	"os"
)

type weaponRow struct {
	ID           string
	Name         string
	BaseForm     uint32
	PluginForm   uint32
	DamageMult   float64
	ClipSize     int
	FireRateMult float64
	Automatic    bool
}

const (
	flagCompressed = 0x00040000
	headerSize     = 24
)

type subrecord struct {
	typ  string
	data []byte
}

type record struct {
	typ     string
	flags   uint32
	formID  uint32
	vcs     uint32
	version uint16
	unknown uint16
	subs    []subrecord
}

// findRecords scans an ESM for records of type typ whose form IDs are in want.
func findRecords(r io.ReadSeeker, typ string, want map[uint32]bool) (map[uint32]*record, error) {
	found := map[uint32]*record{}
	hdr := make([]byte, headerSize)
	for {
		if _, err := io.ReadFull(r, hdr); err != nil {
			if errors.Is(err, io.EOF) {
				return found, nil
			}
			return found, err
		}
		sig := string(hdr[0:4])
		size := binary.LittleEndian.Uint32(hdr[4:8])
		if sig == "GRUP" {
			label := string(hdr[8:12])
			gtype := int32(binary.LittleEndian.Uint32(hdr[12:16]))
			if gtype == 0 && label != typ {
				if _, err := r.Seek(int64(size)-headerSize, io.SeekCurrent); err != nil {
					return found, err
				}
			}
			continue // descend into the wanted top group (and any nested group)
		}
		formID := binary.LittleEndian.Uint32(hdr[12:16])
		if sig != typ || !want[formID] {
			if _, err := r.Seek(int64(size), io.SeekCurrent); err != nil {
				return found, err
			}
			continue
		}
		body := make([]byte, size)
		if _, err := io.ReadFull(r, body); err != nil {
			return found, err
		}
		rec, err := parseRecord(hdr, body)
		if err != nil {
			return found, fmt.Errorf("record %08X: %w", formID, err)
		}
		found[formID] = rec
		if len(found) == len(want) {
			return found, nil
		}
	}
}

func parseRecord(hdr, body []byte) (*record, error) {
	rec := &record{
		typ:     string(hdr[0:4]),
		flags:   binary.LittleEndian.Uint32(hdr[8:12]),
		formID:  binary.LittleEndian.Uint32(hdr[12:16]),
		vcs:     binary.LittleEndian.Uint32(hdr[16:20]),
		version: binary.LittleEndian.Uint16(hdr[20:22]),
		unknown: binary.LittleEndian.Uint16(hdr[22:24]),
	}
	if rec.flags&flagCompressed != 0 {
		if len(body) < 4 {
			return nil, errors.New("compressed record too short")
		}
		want := binary.LittleEndian.Uint32(body[0:4])
		zr, err := zlib.NewReader(bytes.NewReader(body[4:]))
		if err != nil {
			return nil, err
		}
		plain, err := io.ReadAll(zr)
		if err != nil {
			return nil, err
		}
		if uint32(len(plain)) != want {
			return nil, fmt.Errorf("decompressed %d bytes, header says %d", len(plain), want)
		}
		body = plain
		rec.flags &^= flagCompressed
	}
	var bigSize uint32
	for p := 0; p < len(body); {
		if p+6 > len(body) {
			return nil, errors.New("truncated subrecord header")
		}
		typ := string(body[p : p+4])
		n := uint32(binary.LittleEndian.Uint16(body[p+4 : p+6]))
		p += 6
		if typ == "XXXX" {
			bigSize = binary.LittleEndian.Uint32(body[p : p+4])
			p += int(n)
			continue
		}
		if bigSize != 0 {
			n, bigSize = bigSize, 0
		}
		if p+int(n) > len(body) {
			return nil, fmt.Errorf("subrecord %s overruns record", typ)
		}
		rec.subs = append(rec.subs, subrecord{typ, append([]byte(nil), body[p:p+int(n)]...)})
		p += int(n)
	}
	return rec, nil
}

func (r *record) sub(typ string) *subrecord {
	for i := range r.subs {
		if r.subs[i].typ == typ {
			return &r.subs[i]
		}
	}
	return nil
}

func (r *record) setString(typ, s string) {
	data := append([]byte(s), 0)
	if sr := r.sub(typ); sr != nil {
		sr.data = data
		return
	}
	// EDID always comes first; anything else goes after it
	sr := subrecord{typ, data}
	if typ == "EDID" || len(r.subs) == 0 {
		r.subs = append([]subrecord{sr}, r.subs...)
		return
	}
	r.subs = append(r.subs[:1], append([]subrecord{sr}, r.subs[1:]...)...)
}

// applyWeapon turns a copy of the base WEAP into the sheet's weapon.
func applyWeapon(r *record, w weaponRow) error {
	r.formID = 0x01000000 | w.PluginForm
	r.setString("EDID", w.ID)
	r.setString("FULL", w.Name)
	data := r.sub("DATA")
	if data == nil || len(data.data) < 15 {
		return errors.New("WEAP has no 15-byte DATA")
	}
	dmg := float64(int16(binary.LittleEndian.Uint16(data.data[12:14])))
	binary.LittleEndian.PutUint16(data.data[12:14], uint16(int16(math.Round(dmg*w.DamageMult))))
	if w.ClipSize < 0 || w.ClipSize > 255 {
		return fmt.Errorf("clip size %d does not fit in a byte", w.ClipSize)
	}
	data.data[14] = byte(w.ClipSize)
	dnam := r.sub("DNAM")
	if dnam == nil || len(dnam.data) < 68 {
		return errors.New("WEAP has no DNAM with a fire rate")
	}
	if w.Automatic {
		dnam.data[12] |= 0x02
	} else {
		dnam.data[12] &^= 0x02
	}
	scale := func(off int) {
		v := math.Float32frombits(binary.LittleEndian.Uint32(dnam.data[off : off+4]))
		binary.LittleEndian.PutUint32(dnam.data[off:off+4], math.Float32bits(float32(float64(v)*w.FireRateMult)))
	}
	scale(64)
	if len(dnam.data) >= 92 {
		scale(88)
	}
	return nil
}

func (r *record) encode() []byte {
	var body bytes.Buffer
	for _, s := range r.subs {
		if len(s.data) > 0xFFFF {
			body.WriteString("XXXX")
			binary.Write(&body, binary.LittleEndian, uint16(4))
			binary.Write(&body, binary.LittleEndian, uint32(len(s.data)))
			body.WriteString(s.typ)
			binary.Write(&body, binary.LittleEndian, uint16(0))
		} else {
			body.WriteString(s.typ)
			binary.Write(&body, binary.LittleEndian, uint16(len(s.data)))
		}
		body.Write(s.data)
	}
	var out bytes.Buffer
	out.WriteString(r.typ)
	binary.Write(&out, binary.LittleEndian, uint32(body.Len()))
	binary.Write(&out, binary.LittleEndian, r.flags)
	binary.Write(&out, binary.LittleEndian, r.formID)
	binary.Write(&out, binary.LittleEndian, r.vcs)
	binary.Write(&out, binary.LittleEndian, r.version)
	binary.Write(&out, binary.LittleEndian, r.unknown)
	out.Write(body.Bytes())
	return out.Bytes()
}

func groupBytes(label string, records [][]byte) []byte {
	var inner bytes.Buffer
	for _, r := range records {
		inner.Write(r)
	}
	var out bytes.Buffer
	out.WriteString("GRUP")
	binary.Write(&out, binary.LittleEndian, uint32(inner.Len()+headerSize))
	out.WriteString(label)
	binary.Write(&out, binary.LittleEndian, uint32(0)) // top group
	out.Write(make([]byte, 8))
	out.Write(inner.Bytes())
	return out.Bytes()
}

func headerRecord(numRecords int, nextID uint32) []byte {
	hedr := new(bytes.Buffer)
	binary.Write(hedr, binary.LittleEndian, float32(1.34))
	binary.Write(hedr, binary.LittleEndian, int32(numRecords))
	binary.Write(hedr, binary.LittleEndian, nextID)
	tes4 := &record{typ: "TES4", version: 15, subs: []subrecord{
		{"HEDR", hedr.Bytes()},
		{"CNAM", []byte("CS2 in the Mojave launcher\x00")},
		{"SNAM", []byte("Weapons for CS2 in the Mojave, built on this PC from FalloutNV.esm. Rebuilt on every Play.\x00")},
		{"MAST", []byte("FalloutNV.esm\x00")},
		{"DATA", make([]byte, 8)},
	}}
	return tes4.encode()
}

// buildPlugin reads the base weapons from esmPath and writes the plugin to outPath.
// It returns the IDs of the weapons it wrote; a weapon whose base record is missing is skipped and reported.
func buildPlugin(esmPath, outPath string, weapons []weaponRow) ([]string, []error) {
	var errs []error
	f, err := os.Open(esmPath)
	if err != nil {
		return nil, []error{err}
	}
	defer f.Close()
	want := map[uint32]bool{}
	for _, w := range weapons {
		want[w.BaseForm] = true
	}
	found, err := findRecords(f, "WEAP", want)
	if err != nil {
		errs = append(errs, fmt.Errorf("reading %s: %w", esmPath, err))
	}
	var recs [][]byte
	var written []string
	maxID := uint32(0x800)
	for _, w := range weapons {
		base, ok := found[w.BaseForm]
		if !ok {
			errs = append(errs, fmt.Errorf("%s: base weapon %06X is not a WEAP in FalloutNV.esm", w.ID, w.BaseForm))
			continue
		}
		cp := *base
		cp.subs = make([]subrecord, len(base.subs))
		for i, s := range base.subs {
			cp.subs[i] = subrecord{s.typ, append([]byte(nil), s.data...)}
		}
		if err := applyWeapon(&cp, w); err != nil {
			errs = append(errs, fmt.Errorf("%s: %w", w.ID, err))
			continue
		}
		recs = append(recs, cp.encode())
		written = append(written, w.ID)
		if w.PluginForm >= maxID {
			maxID = w.PluginForm + 1
		}
	}
	var out bytes.Buffer
	out.Write(headerRecord(len(recs)+1, maxID))
	if len(recs) > 0 {
		out.Write(groupBytes("WEAP", recs))
	}
	tmp := outPath + ".tmp"
	if err := os.WriteFile(tmp, out.Bytes(), 0o644); err != nil {
		return written, append(errs, err)
	}
	if err := os.Rename(tmp, outPath); err != nil {
		return written, append(errs, err)
	}
	return written, errs
}

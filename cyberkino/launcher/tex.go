package main

// Textures for the fitted models. WolvenKit writes each mesh's materials to <mesh>.Material.json and
// the textures they use into the material repo as PNG. Cyberpunk guns mostly use multilayered
// materials (a mask per layer, a colour per layer), so the colour map is rebuilt from the masks and
// each layer's colour; a plain base-colour texture is used when there is one; a neutral gun-metal
// grey when neither can be read.

import (
	"bytes"
	"encoding/binary"
	"encoding/json"
	"fmt"
	"image"
	"image/color"
	_ "image/png"
	"math"
	"os"
	"path/filepath"
	"strings"
)

const maxTextureSize = 512

type rgba struct {
	W, H int
	Pix  []float64 // r,g,b,a 0..1
}

func newRGBA(w, h int, c [4]float64) *rgba {
	t := &rgba{W: w, H: h, Pix: make([]float64, w*h*4)}
	for i := 0; i < w*h; i++ {
		copy(t.Pix[i*4:], c[:])
	}
	return t
}

func loadImage(path string) (*rgba, error) {
	f, err := os.Open(path)
	if err != nil {
		return nil, err
	}
	defer f.Close()
	img, _, err := image.Decode(f)
	if err != nil {
		return nil, err
	}
	b := img.Bounds()
	t := &rgba{W: b.Dx(), H: b.Dy(), Pix: make([]float64, b.Dx()*b.Dy()*4)}
	for y := 0; y < t.H; y++ {
		for x := 0; x < t.W; x++ {
			c := color.NRGBA64Model.Convert(img.At(b.Min.X+x, b.Min.Y+y)).(color.NRGBA64)
			i := (y*t.W + x) * 4
			t.Pix[i], t.Pix[i+1], t.Pix[i+2], t.Pix[i+3] = float64(c.R)/65535, float64(c.G)/65535, float64(c.B)/65535, float64(c.A)/65535
		}
	}
	return t, nil
}

// sample reads t at normalised coordinates with wrap-around.
func (t *rgba) sample(u, v float64) [4]float64 {
	x := int(math.Floor(u*float64(t.W))) % t.W
	y := int(math.Floor(v*float64(t.H))) % t.H
	if x < 0 {
		x += t.W
	}
	if y < 0 {
		y += t.H
	}
	i := (y*t.W + x) * 4
	return [4]float64{t.Pix[i], t.Pix[i+1], t.Pix[i+2], t.Pix[i+3]}
}

// resized returns t resampled to w x h (box filter when shrinking).
func (t *rgba) resized(w, h int) *rgba {
	out := &rgba{W: w, H: h, Pix: make([]float64, w*h*4)}
	sx, sy := float64(t.W)/float64(w), float64(t.H)/float64(h)
	for y := 0; y < h; y++ {
		for x := 0; x < w; x++ {
			var acc [4]float64
			n := 0.0
			for yy := int(float64(y) * sy); yy < int(math.Max(float64(y+1)*sy, float64(y)*sy+1)) && yy < t.H; yy++ {
				for xx := int(float64(x) * sx); xx < int(math.Max(float64(x+1)*sx, float64(x)*sx+1)) && xx < t.W; xx++ {
					i := (yy*t.W + xx) * 4
					for c := 0; c < 4; c++ {
						acc[c] += t.Pix[i+c]
					}
					n++
				}
			}
			i := (y*w + x) * 4
			for c := 0; c < 4; c++ {
				out.Pix[i+c] = acc[c] / math.Max(n, 1)
			}
		}
	}
	return out
}

func pow2Below(n int) int {
	p := 1
	for p*2 <= n {
		p *= 2
	}
	return p
}

// ddsBytes writes an uncompressed 32-bit BGRA DDS with a full mip chain (power-of-two size, at most maxTextureSize).
func ddsBytes(t *rgba) []byte {
	w := pow2Below(int(math.Min(float64(t.W), maxTextureSize)))
	h := pow2Below(int(math.Min(float64(t.H), maxTextureSize)))
	if w < 4 {
		w = 4
	}
	if h < 4 {
		h = 4
	}
	levels := []*rgba{t.resized(w, h)}
	for lw, lh := w, h; lw > 1 || lh > 1; {
		lw, lh = int(math.Max(1, float64(lw/2))), int(math.Max(1, float64(lh/2)))
		levels = append(levels, levels[len(levels)-1].resized(lw, lh))
	}
	var b bytes.Buffer
	le := binary.LittleEndian
	b.WriteString("DDS ")
	binary.Write(&b, le, uint32(124))
	binary.Write(&b, le, uint32(0x1|0x2|0x4|0x8|0x1000|0x20000)) // caps, height, width, pitch, pixelformat, mipmapcount
	binary.Write(&b, le, uint32(h))
	binary.Write(&b, le, uint32(w))
	binary.Write(&b, le, uint32(w*4))
	binary.Write(&b, le, uint32(0))
	binary.Write(&b, le, uint32(len(levels)))
	b.Write(make([]byte, 44))
	binary.Write(&b, le, uint32(32))
	binary.Write(&b, le, uint32(0x41)) // RGB | ALPHAPIXELS
	binary.Write(&b, le, uint32(0))
	binary.Write(&b, le, uint32(32))
	for _, m := range []uint32{0x00ff0000, 0x0000ff00, 0x000000ff, 0xff000000} {
		binary.Write(&b, le, m)
	}
	binary.Write(&b, le, uint32(0x1000|0x8|0x400000)) // texture | complex | mipmap
	b.Write(make([]byte, 16))
	for _, l := range levels {
		for i := 0; i < l.W*l.H; i++ {
			px := l.Pix[i*4 : i*4+4]
			b.WriteByte(byte(clamp01(px[2]) * 255))
			b.WriteByte(byte(clamp01(px[1]) * 255))
			b.WriteByte(byte(clamp01(px[0]) * 255))
			b.WriteByte(255)
		}
	}
	return b.Bytes()
}

func clamp01(v float64) float64 { return math.Max(0, math.Min(1, v)) }

// ---------------------------------------------------------------- WolvenKit material data

// cpMaterial is one material from a .Material.json: its parameters (texture params hold repo-relative paths).
type cpMaterial struct {
	Name string
	Data map[string]any
}

// unwrap reads RedJsonSerializer's {"$value": x} wrappers (and DepotPath objects) down to a plain value.
func unwrap(v any) any {
	for i := 0; i < 4; i++ {
		m, ok := v.(map[string]any)
		if !ok {
			return v
		}
		switch {
		case m["$value"] != nil:
			v = m["$value"]
		case m["DepotPath"] != nil:
			v = m["DepotPath"]
		case m["value"] != nil:
			v = m["value"]
		default:
			return v
		}
	}
	return v
}

func asString(v any) string {
	s, _ := unwrap(v).(string)
	return s
}

func asFloat(v any, def float64) float64 {
	switch x := unwrap(v).(type) {
	case float64:
		return x
	case json.Number:
		f, err := x.Float64()
		if err == nil {
			return f
		}
	}
	return def
}

// walk calls fn on every JSON object in v.
func walk(v any, fn func(map[string]any)) {
	switch x := v.(type) {
	case map[string]any:
		fn(x)
		for _, c := range x {
			walk(c, fn)
		}
	case []any:
		for _, c := range x {
			walk(c, fn)
		}
	}
}

func readJSON(path string) (any, error) {
	data, err := os.ReadFile(path)
	if err != nil {
		return nil, err
	}
	var v any
	if err := json.Unmarshal(data, &v); err != nil {
		return nil, err
	}
	return v, nil
}

func readMaterials(path string) map[string]cpMaterial {
	out := map[string]cpMaterial{}
	v, err := readJSON(path)
	if err != nil {
		return out
	}
	walk(v, func(m map[string]any) {
		name := asString(m["Name"])
		data, ok := m["Data"].(map[string]any)
		if name != "" && ok {
			out[name] = cpMaterial{Name: name, Data: data}
		}
	})
	return out
}

type texResolver struct {
	Repo string
	Log  func(string, ...any)
}

// repoFile finds a depot path exported into the material repo, trying the given extensions.
func (r texResolver) repoFile(depot string, exts ...string) string {
	depot = strings.ReplaceAll(depot, "\\", string(filepath.Separator))
	base := filepath.Join(r.Repo, depot)
	trimmed := strings.TrimSuffix(base, filepath.Ext(base))
	for _, e := range exts {
		for _, cand := range []string{trimmed + e, base + e} {
			if _, err := os.Stat(cand); err == nil {
				return cand
			}
		}
	}
	return ""
}

var gunMetal = [4]float64{0.23, 0.23, 0.25, 1}

// albedo builds the colour map of one Cyberpunk material.
func (r texResolver) albedo(m cpMaterial) (*rgba, string) {
	for _, key := range []string{"BaseColor", "Albedo", "DiffuseTexture", "Diffuse", "BaseColorTexture", "Color"} {
		for k, v := range m.Data {
			if !strings.EqualFold(k, key) {
				continue
			}
			s := asString(v)
			if !strings.HasSuffix(strings.ToLower(s), ".xbm") {
				continue
			}
			if f := r.repoFile(s, ".png"); f != "" {
				if img, err := loadImage(f); err == nil {
					return img, "texture " + k
				}
			}
		}
	}
	setup, mask := "", ""
	for k, v := range m.Data {
		lk := strings.ToLower(k)
		if strings.Contains(lk, "multilayersetup") {
			setup = asString(v)
		}
		if strings.Contains(lk, "multilayermask") {
			mask = asString(v)
		}
	}
	if setup != "" && mask != "" {
		if img, err := r.multilayer(setup, mask); err == nil {
			return img, "multilayer"
		} else {
			r.Log("  material %s: multilayer colours not readable (%v)", m.Name, err)
		}
	}
	return newRGBA(4, 4, gunMetal), "gun-metal grey"
}

type mlLayer struct {
	Color   [3]float64
	Opacity float64
}

func (r texResolver) multilayer(setupPath, maskPath string) (*rgba, error) {
	sf := r.repoFile(setupPath, ".json", ".mlsetup.json")
	if sf == "" {
		return nil, fmt.Errorf("%s not exported", setupPath)
	}
	sv, err := readJSON(sf)
	if err != nil {
		return nil, err
	}
	var layers []mlLayer
	walk(sv, func(m map[string]any) {
		arr, ok := m["layers"].([]any)
		if !ok || layers != nil {
			return
		}
		for _, l := range arr {
			lm, ok := l.(map[string]any)
			if !ok {
				continue
			}
			layer := mlLayer{Color: [3]float64{0.5, 0.5, 0.5}, Opacity: asFloat(lm["opacity"], 1)}
			scale := asString(lm["colorScale"])
			if tpl := asString(lm["material"]); tpl != "" {
				if c, ok := r.templateColor(tpl, scale); ok {
					layer.Color = c
				}
			}
			layers = append(layers, layer)
		}
	})
	if len(layers) == 0 {
		return nil, fmt.Errorf("no layers in %s", sf)
	}
	maskBase := strings.TrimSuffix(maskPath, filepath.Ext(maskPath))
	name := filepath.Base(strings.ReplaceAll(maskBase, "\\", "/"))
	var out *rgba
	for i, layer := range layers {
		var mimg *rgba
		if i > 0 {
			for _, cand := range []string{fmt.Sprintf("%s_%d", maskBase, i), fmt.Sprintf("%s_layers\\%s_%d", maskBase, name, i)} {
				if f := r.repoFile(cand+".png", ".png"); f != "" {
					mimg, _ = loadImage(f)
					break
				}
			}
		}
		if out == nil {
			w, h := 512, 512
			if mimg != nil {
				w, h = mimg.W, mimg.H
			}
			out = newRGBA(w, h, [4]float64{layer.Color[0], layer.Color[1], layer.Color[2], 1})
			continue
		}
		if mimg == nil {
			continue
		}
		for y := 0; y < out.H; y++ {
			for x := 0; x < out.W; x++ {
				a := mimg.sample((float64(x)+0.5)/float64(out.W), (float64(y)+0.5)/float64(out.H))[0] * layer.Opacity
				p := (y*out.W + x) * 4
				for c := 0; c < 3; c++ {
					out.Pix[p+c] = out.Pix[p+c]*(1-a) + layer.Color[c]*a
				}
			}
		}
	}
	return out, nil
}

// templateColor reads a layer template's named colour (overrides.colorScale).
func (r texResolver) templateColor(tplPath, scale string) ([3]float64, bool) {
	f := r.repoFile(tplPath, ".json", ".mltemplate.json")
	if f == "" {
		return [3]float64{}, false
	}
	v, err := readJSON(f)
	if err != nil {
		return [3]float64{}, false
	}
	var found [3]float64
	ok := false
	walk(v, func(m map[string]any) {
		if ok {
			return
		}
		arr, isArr := m["colorScale"].([]any)
		if !isArr {
			return
		}
		for _, e := range arr {
			em, isMap := e.(map[string]any)
			if !isMap {
				continue
			}
			if scale != "" && asString(em["n"]) != scale {
				continue
			}
			vals, isList := unwrap(em["v"]).([]any)
			if !isList || len(vals) < 3 {
				continue
			}
			found = [3]float64{asFloat(vals[0], 0.5), asFloat(vals[1], 0.5), asFloat(vals[2], 0.5)}
			ok = true
			return
		}
	})
	return found, ok
}

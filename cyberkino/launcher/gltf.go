package main

// Minimal glTF 2.0 binary (.glb) reading and writing: enough to read WolvenKit's mesh exports and
// OpenAssetTools' xmodel dumps, and to write the fitted models OpenAssetTools' Linker reads back.

import (
	"bytes"
	"encoding/binary"
	"encoding/json"
	"errors"
	"fmt"
	"math"
	"os"
)

type gltfDoc struct {
	Asset       map[string]any   `json:"asset"`
	Scene       *int             `json:"scene,omitempty"`
	Scenes      []gltfScene      `json:"scenes,omitempty"`
	Nodes       []gltfNode       `json:"nodes,omitempty"`
	Meshes      []gltfMesh       `json:"meshes,omitempty"`
	Skins       []gltfSkin       `json:"skins,omitempty"`
	Materials   []gltfMaterial   `json:"materials,omitempty"`
	Accessors   []gltfAccessor   `json:"accessors,omitempty"`
	BufferViews []gltfBufferView `json:"bufferViews,omitempty"`
	Buffers     []gltfBuffer     `json:"buffers,omitempty"`
	Textures    []map[string]any `json:"textures,omitempty"`
	Images      []map[string]any `json:"images,omitempty"`
	Samplers    []map[string]any `json:"samplers,omitempty"`
}

type gltfScene struct {
	Nodes []int `json:"nodes"`
}

type gltfNode struct {
	Name        string    `json:"name,omitempty"`
	Children    []int     `json:"children,omitempty"`
	Mesh        *int      `json:"mesh,omitempty"`
	Skin        *int      `json:"skin,omitempty"`
	Translation []float64 `json:"translation,omitempty"`
	Rotation    []float64 `json:"rotation,omitempty"`
	Scale       []float64 `json:"scale,omitempty"`
	Matrix      []float64 `json:"matrix,omitempty"`
}

type gltfMesh struct {
	Name       string          `json:"name,omitempty"`
	Primitives []gltfPrimitive `json:"primitives"`
}

type gltfPrimitive struct {
	Attributes map[string]int `json:"attributes"`
	Indices    *int           `json:"indices,omitempty"`
	Material   *int           `json:"material,omitempty"`
	Mode       *int           `json:"mode,omitempty"`
}

type gltfSkin struct {
	Name                string `json:"name,omitempty"`
	InverseBindMatrices *int   `json:"inverseBindMatrices,omitempty"`
	Joints              []int  `json:"joints"`
	Skeleton            *int   `json:"skeleton,omitempty"`
}

type gltfMaterial struct {
	Name string         `json:"name"`
	PBR  map[string]any `json:"pbrMetallicRoughness,omitempty"`
}

type gltfAccessor struct {
	BufferView    *int      `json:"bufferView,omitempty"`
	ByteOffset    int       `json:"byteOffset,omitempty"`
	ComponentType int       `json:"componentType"`
	Normalized    bool      `json:"normalized,omitempty"`
	Count         int       `json:"count"`
	Type          string    `json:"type"`
	Min           []float64 `json:"min,omitempty"`
	Max           []float64 `json:"max,omitempty"`
}

type gltfBufferView struct {
	Buffer     int `json:"buffer"`
	ByteOffset int `json:"byteOffset,omitempty"`
	ByteLength int `json:"byteLength"`
	ByteStride int `json:"byteStride,omitempty"`
	Target     int `json:"target,omitempty"`
}

type gltfBuffer struct {
	ByteLength int    `json:"byteLength"`
	URI        string `json:"uri,omitempty"`
}

const (
	compByte   = 5120
	compUByte  = 5121
	compShort  = 5122
	compUShort = 5123
	compUInt   = 5125
	compFloat  = 5126
)

type glb struct {
	Doc gltfDoc
	Bin []byte
}

func readGLB(path string) (*glb, error) {
	data, err := os.ReadFile(path)
	if err != nil {
		return nil, err
	}
	return parseGLB(data)
}

func parseGLB(data []byte) (*glb, error) {
	if len(data) < 20 || string(data[0:4]) != "glTF" {
		return nil, errors.New("not a binary glTF file")
	}
	g := &glb{}
	off := 12
	for off+8 <= len(data) {
		n := int(binary.LittleEndian.Uint32(data[off:]))
		kind := string(data[off+4 : off+8])
		if off+8+n > len(data) {
			return nil, errors.New("truncated glTF chunk")
		}
		chunk := data[off+8 : off+8+n]
		switch kind {
		case "JSON":
			if err := json.Unmarshal(bytes.TrimRight(chunk, " \x00"), &g.Doc); err != nil {
				return nil, fmt.Errorf("glTF JSON: %w", err)
			}
		case "BIN\x00":
			g.Bin = chunk
		}
		off += 8 + n
	}
	return g, nil
}

func (g *glb) componentSize(ct int) int {
	switch ct {
	case compByte, compUByte:
		return 1
	case compShort, compUShort:
		return 2
	}
	return 4
}

func typeCount(t string) int {
	switch t {
	case "SCALAR":
		return 1
	case "VEC2":
		return 2
	case "VEC3":
		return 3
	case "VEC4", "MAT2":
		return 4
	case "MAT3":
		return 9
	case "MAT4":
		return 16
	}
	return 0
}

// floats reads an accessor as float64 values, n per element (normalised integers are scaled).
func (g *glb) floats(index int) ([][]float64, error) {
	if index < 0 || index >= len(g.Doc.Accessors) {
		return nil, fmt.Errorf("accessor %d out of range", index)
	}
	a := g.Doc.Accessors[index]
	n := typeCount(a.Type)
	out := make([][]float64, a.Count)
	if a.BufferView == nil {
		for i := range out {
			out[i] = make([]float64, n)
		}
		return out, nil
	}
	bv := g.Doc.BufferViews[*a.BufferView]
	cs := g.componentSize(a.ComponentType)
	stride := bv.ByteStride
	if stride == 0 {
		stride = cs * n
	}
	base := bv.ByteOffset + a.ByteOffset
	for i := 0; i < a.Count; i++ {
		v := make([]float64, n)
		for c := 0; c < n; c++ {
			p := base + i*stride + c*cs
			if p+cs > len(g.Bin) {
				return nil, errors.New("accessor reads past the buffer")
			}
			b := g.Bin[p:]
			switch a.ComponentType {
			case compFloat:
				v[c] = float64(math.Float32frombits(binary.LittleEndian.Uint32(b)))
			case compUByte:
				v[c] = float64(b[0])
				if a.Normalized {
					v[c] /= 255
				}
			case compByte:
				v[c] = float64(int8(b[0]))
				if a.Normalized {
					v[c] = math.Max(v[c]/127, -1)
				}
			case compUShort:
				v[c] = float64(binary.LittleEndian.Uint16(b))
				if a.Normalized {
					v[c] /= 65535
				}
			case compShort:
				v[c] = float64(int16(binary.LittleEndian.Uint16(b)))
				if a.Normalized {
					v[c] = math.Max(v[c]/32767, -1)
				}
			case compUInt:
				v[c] = float64(binary.LittleEndian.Uint32(b))
			default:
				return nil, fmt.Errorf("unsupported component type %d", a.ComponentType)
			}
		}
		out[i] = v
	}
	return out, nil
}

func (g *glb) indices(prim gltfPrimitive, vertexCount int) ([]int, error) {
	if prim.Indices == nil {
		idx := make([]int, vertexCount)
		for i := range idx {
			idx[i] = i
		}
		return idx, nil
	}
	vals, err := g.floats(*prim.Indices)
	if err != nil {
		return nil, err
	}
	idx := make([]int, len(vals))
	for i, v := range vals {
		idx[i] = int(v[0])
	}
	return idx, nil
}

// ---------------------------------------------------------------- node transforms

type mat4 [16]float64 // column-major, as glTF

func identity() mat4 {
	return mat4{1, 0, 0, 0, 0, 1, 0, 0, 0, 0, 1, 0, 0, 0, 0, 1}
}

func (a mat4) mul(b mat4) mat4 {
	var r mat4
	for c := 0; c < 4; c++ {
		for row := 0; row < 4; row++ {
			s := 0.0
			for k := 0; k < 4; k++ {
				s += a[k*4+row] * b[c*4+k]
			}
			r[c*4+row] = s
		}
	}
	return r
}

func (a mat4) point(p vec3) vec3 {
	return vec3{
		a[0]*p[0] + a[4]*p[1] + a[8]*p[2] + a[12],
		a[1]*p[0] + a[5]*p[1] + a[9]*p[2] + a[13],
		a[2]*p[0] + a[6]*p[1] + a[10]*p[2] + a[14],
	}
}

func (a mat4) dir(p vec3) vec3 {
	return vec3{
		a[0]*p[0] + a[4]*p[1] + a[8]*p[2],
		a[1]*p[0] + a[5]*p[1] + a[9]*p[2],
		a[2]*p[0] + a[6]*p[1] + a[10]*p[2],
	}
}

func nodeLocal(n gltfNode) mat4 {
	if len(n.Matrix) == 16 {
		var m mat4
		copy(m[:], n.Matrix)
		return m
	}
	t := vec3{}
	if len(n.Translation) == 3 {
		t = vec3{n.Translation[0], n.Translation[1], n.Translation[2]}
	}
	q := [4]float64{0, 0, 0, 1}
	if len(n.Rotation) == 4 {
		q = [4]float64{n.Rotation[0], n.Rotation[1], n.Rotation[2], n.Rotation[3]}
	}
	s := vec3{1, 1, 1}
	if len(n.Scale) == 3 {
		s = vec3{n.Scale[0], n.Scale[1], n.Scale[2]}
	}
	x, y, z, w := q[0], q[1], q[2], q[3]
	return mat4{
		(1 - 2*(y*y+z*z)) * s[0], (2 * (x*y + z*w)) * s[0], (2 * (x*z - y*w)) * s[0], 0,
		(2 * (x*y - z*w)) * s[1], (1 - 2*(x*x+z*z)) * s[1], (2 * (y*z + x*w)) * s[1], 0,
		(2 * (x*z + y*w)) * s[2], (2 * (y*z - x*w)) * s[2], (1 - 2*(x*x+y*y)) * s[2], 0,
		t[0], t[1], t[2], 1,
	}
}

// globalMatrices returns every node's world matrix.
func (g *glb) globalMatrices() []mat4 {
	n := len(g.Doc.Nodes)
	parent := make([]int, n)
	for i := range parent {
		parent[i] = -1
	}
	for i, node := range g.Doc.Nodes {
		for _, c := range node.Children {
			if c >= 0 && c < n {
				parent[c] = i
			}
		}
	}
	out := make([]mat4, n)
	done := make([]bool, n)
	var resolve func(i, depth int) mat4
	resolve = func(i, depth int) mat4 {
		if done[i] || depth > n {
			return out[i]
		}
		m := nodeLocal(g.Doc.Nodes[i])
		if parent[i] >= 0 {
			m = resolve(parent[i], depth+1).mul(m)
		}
		out[i], done[i] = m, true
		return m
	}
	for i := 0; i < n; i++ {
		resolve(i, 0)
	}
	return out
}

// ---------------------------------------------------------------- writing

type glbWriter struct {
	doc gltfDoc
	bin bytes.Buffer
}

func newGLBWriter() *glbWriter {
	return &glbWriter{doc: gltfDoc{Asset: map[string]any{"version": "2.0", "generator": "Cyberpunk Kino launcher"}}}
}

func (w *glbWriter) align() {
	for w.bin.Len()%4 != 0 {
		w.bin.WriteByte(0)
	}
}

func (w *glbWriter) addFloats(vals [][]float64, typ string, target int, withBounds bool) int {
	w.align()
	off := w.bin.Len()
	n := typeCount(typ)
	for _, v := range vals {
		for c := 0; c < n; c++ {
			binary.Write(&w.bin, binary.LittleEndian, float32(v[c]))
		}
	}
	w.doc.BufferViews = append(w.doc.BufferViews, gltfBufferView{ByteOffset: off, ByteLength: w.bin.Len() - off, Target: target})
	bv := len(w.doc.BufferViews) - 1
	acc := gltfAccessor{BufferView: &bv, ComponentType: compFloat, Count: len(vals), Type: typ}
	if withBounds && len(vals) > 0 {
		acc.Min = make([]float64, n)
		acc.Max = make([]float64, n)
		for c := 0; c < n; c++ {
			acc.Min[c], acc.Max[c] = math.Inf(1), math.Inf(-1)
		}
		for _, v := range vals {
			for c := 0; c < n; c++ {
				acc.Min[c] = math.Min(acc.Min[c], float64(float32(v[c])))
				acc.Max[c] = math.Max(acc.Max[c], float64(float32(v[c])))
			}
		}
	}
	w.doc.Accessors = append(w.doc.Accessors, acc)
	return len(w.doc.Accessors) - 1
}

func (w *glbWriter) addJoints(vals [][4]int) int {
	w.align()
	off := w.bin.Len()
	for _, v := range vals {
		for _, j := range v {
			binary.Write(&w.bin, binary.LittleEndian, uint16(j))
		}
	}
	w.doc.BufferViews = append(w.doc.BufferViews, gltfBufferView{ByteOffset: off, ByteLength: w.bin.Len() - off, Target: 34962})
	bv := len(w.doc.BufferViews) - 1
	w.doc.Accessors = append(w.doc.Accessors, gltfAccessor{BufferView: &bv, ComponentType: compUShort, Count: len(vals), Type: "VEC4"})
	return len(w.doc.Accessors) - 1
}

func (w *glbWriter) addIndices(idx []int) int {
	w.align()
	off := w.bin.Len()
	for _, i := range idx {
		binary.Write(&w.bin, binary.LittleEndian, uint32(i))
	}
	w.doc.BufferViews = append(w.doc.BufferViews, gltfBufferView{ByteOffset: off, ByteLength: w.bin.Len() - off, Target: 34963})
	bv := len(w.doc.BufferViews) - 1
	w.doc.Accessors = append(w.doc.Accessors, gltfAccessor{BufferView: &bv, ComponentType: compUInt, Count: len(idx), Type: "SCALAR"})
	return len(w.doc.Accessors) - 1
}

func (w *glbWriter) bytes() ([]byte, error) {
	w.align()
	w.doc.Buffers = []gltfBuffer{{ByteLength: w.bin.Len()}}
	js, err := json.Marshal(w.doc)
	if err != nil {
		return nil, err
	}
	for len(js)%4 != 0 {
		js = append(js, ' ')
	}
	var out bytes.Buffer
	total := 12 + 8 + len(js) + 8 + w.bin.Len()
	out.WriteString("glTF")
	binary.Write(&out, binary.LittleEndian, uint32(2))
	binary.Write(&out, binary.LittleEndian, uint32(total))
	binary.Write(&out, binary.LittleEndian, uint32(len(js)))
	out.WriteString("JSON")
	out.Write(js)
	binary.Write(&out, binary.LittleEndian, uint32(w.bin.Len()))
	out.WriteString("BIN\x00")
	out.Write(w.bin.Bytes())
	return out.Bytes(), nil
}

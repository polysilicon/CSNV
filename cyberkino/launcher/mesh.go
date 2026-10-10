package main

// Fitting a Cyberpunk mesh into a Black Ops model: the Cyberpunk gun is turned so its muzzle points
// where the Black Ops gun's muzzle (tag_flash) points, scaled to the same length, centred on it and
// bound to the Black Ops gun's own skeleton, so Black Ops' animations move it the same way.

import (
	"errors"
	"fmt"
	"math"
	"sort"
	"strings"
)

type vec3 [3]float64

func (a vec3) sub(b vec3) vec3      { return vec3{a[0] - b[0], a[1] - b[1], a[2] - b[2]} }
func (a vec3) add(b vec3) vec3      { return vec3{a[0] + b[0], a[1] + b[1], a[2] + b[2]} }
func (a vec3) scale(s float64) vec3 { return vec3{a[0] * s, a[1] * s, a[2] * s} }

func (a vec3) normalized() vec3 {
	l := math.Sqrt(a[0]*a[0] + a[1]*a[1] + a[2]*a[2])
	if l == 0 {
		return vec3{0, 0, 1}
	}
	return a.scale(1 / l)
}

type bbox struct{ Min, Max vec3 }

func newBBox() bbox {
	return bbox{vec3{math.Inf(1), math.Inf(1), math.Inf(1)}, vec3{math.Inf(-1), math.Inf(-1), math.Inf(-1)}}
}

func (b *bbox) add(p vec3) {
	for i := 0; i < 3; i++ {
		b.Min[i] = math.Min(b.Min[i], p[i])
		b.Max[i] = math.Max(b.Max[i], p[i])
	}
}

func (b bbox) valid() bool  { return b.Min[0] <= b.Max[0] }
func (b bbox) center() vec3 { return b.Min.add(b.Max).scale(0.5) }
func (b bbox) extent() vec3 { return b.Max.sub(b.Min) }
func (b bbox) contains(p vec3) bool {
	for i := 0; i < 3; i++ {
		if p[i] < b.Min[i] || p[i] > b.Max[i] {
			return false
		}
	}
	return true
}

// grown is the box enlarged on every side by f times its largest extent.
func (b bbox) grown(f float64) bbox {
	e := b.extent()
	m := math.Max(e[0], math.Max(e[1], e[2])) * f
	d := vec3{m, m, m}
	return bbox{b.Min.sub(d), b.Max.add(d)}
}

// part is geometry that uses one material.
type part struct {
	Material string
	Mesh     string // glTF mesh name (WolvenKit: "<submesh index>_<name>")
	Pos      []vec3
	Nrm      []vec3
	UV       [][2]float64
	Idx      []int
}

func partsBBox(parts []part) bbox {
	b := newBBox()
	for _, p := range parts {
		for _, v := range p.Pos {
			b.add(v)
		}
	}
	return b
}

// loadParts reads every mesh primitive of a glb in world space, one part per primitive.
func loadParts(g *glb) ([]part, error) {
	globals := g.globalMatrices()
	var out []part
	for ni, node := range g.Doc.Nodes {
		if node.Mesh == nil || *node.Mesh >= len(g.Doc.Meshes) {
			continue
		}
		m := globals[ni]
		if node.Skin != nil {
			m = identity() // glTF ignores a skinned mesh node's own transform
		}
		for _, prim := range g.Doc.Meshes[*node.Mesh].Primitives {
			if prim.Mode != nil && *prim.Mode != 4 {
				continue
			}
			posIdx, ok := prim.Attributes["POSITION"]
			if !ok {
				continue
			}
			pos, err := g.floats(posIdx)
			if err != nil {
				return nil, err
			}
			p := part{Material: "default", Mesh: g.Doc.Meshes[*node.Mesh].Name}
			if prim.Material != nil && *prim.Material < len(g.Doc.Materials) {
				p.Material = g.Doc.Materials[*prim.Material].Name
			}
			for _, v := range pos {
				p.Pos = append(p.Pos, m.point(vec3{v[0], v[1], v[2]}))
			}
			if ni, ok := prim.Attributes["NORMAL"]; ok {
				nrm, err := g.floats(ni)
				if err != nil {
					return nil, err
				}
				for _, v := range nrm {
					p.Nrm = append(p.Nrm, m.dir(vec3{v[0], v[1], v[2]}).normalized())
				}
			}
			if len(p.Nrm) != len(p.Pos) {
				p.Nrm = make([]vec3, len(p.Pos))
				for i := range p.Nrm {
					p.Nrm[i] = vec3{0, 1, 0}
				}
			}
			if ti, ok := prim.Attributes["TEXCOORD_0"]; ok {
				uv, err := g.floats(ti)
				if err != nil {
					return nil, err
				}
				for _, v := range uv {
					p.UV = append(p.UV, [2]float64{v[0], v[1]})
				}
			}
			if len(p.UV) != len(p.Pos) {
				p.UV = make([][2]float64, len(p.Pos))
			}
			p.Idx, err = g.indices(prim, len(p.Pos))
			if err != nil {
				return nil, err
			}
			p.Idx = p.Idx[:len(p.Idx)/3*3]
			out = append(out, p)
		}
	}
	if len(out) == 0 {
		return nil, errors.New("no triangle meshes in the file")
	}
	return out, nil
}

// baseModel is a Black Ops model dumped by OpenAssetTools' Unlinker.
type baseModel struct {
	Name      string
	Nodes     []gltfNode // the skeleton's nodes only, children re-indexed
	Roots     []int
	IBM       [][]float64
	BodyJoint int // joint index (in Nodes) most of the gun's vertices hang on
	BBox      bbox
	Forward   vec3 // unit vector from the model centre towards the muzzle
	Material  string
}

func loadBaseModel(name string, g *glb) (*baseModel, error) {
	parts, err := loadParts(g)
	if err != nil {
		return nil, err
	}
	bm := &baseModel{Name: name, BBox: partsBBox(parts), Material: parts[0].Material}
	globals := g.globalMatrices()

	if len(g.Doc.Skins) > 0 && len(g.Doc.Skins[0].Joints) > 0 {
		skin := g.Doc.Skins[0]
		remap := map[int]int{}
		for i, j := range skin.Joints {
			remap[j] = i
		}
		isChild := map[int]bool{}
		for i, j := range skin.Joints {
			src := g.Doc.Nodes[j]
			n := gltfNode{Name: src.Name, Translation: src.Translation, Rotation: src.Rotation, Scale: src.Scale, Matrix: src.Matrix}
			for _, c := range src.Children {
				if ci, ok := remap[c]; ok {
					n.Children = append(n.Children, ci)
					isChild[ci] = true
				}
			}
			bm.Nodes = append(bm.Nodes, n)
			_ = i
		}
		for i := range bm.Nodes {
			if !isChild[i] {
				bm.Roots = append(bm.Roots, i)
			}
		}
		if skin.InverseBindMatrices != nil {
			bm.IBM, err = g.floats(*skin.InverseBindMatrices)
			if err != nil {
				return nil, err
			}
		}
		if len(bm.IBM) != len(bm.Nodes) {
			// rebuild inverse bind matrices from the node hierarchy
			bm.IBM = nil
			for _, j := range skin.Joints {
				bm.IBM = append(bm.IBM, invertAffine(globals[j]))
			}
		}
		bm.BodyJoint = dominantJoint(g)
		for i, j := range skin.Joints {
			if strings.EqualFold(g.Doc.Nodes[j].Name, "tag_flash") {
				flash := globals[j].point(vec3{})
				bm.Forward = horizontalAxisTowards(bm.BBox, flash)
				_ = i
			}
		}
	} else {
		bm.Nodes = []gltfNode{{Name: "tag_origin"}}
		bm.Roots = []int{0}
		bm.IBM = [][]float64{identitySlice()}
	}
	if bm.Forward == (vec3{}) {
		bm.Forward = muzzleByShape(parts, bm.BBox)
	}
	return bm, nil
}

func identitySlice() []float64 {
	m := identity()
	return m[:]
}

func invertAffine(m mat4) []float64 {
	// inverse of [R|t] where R may include scale: use the general 3x3 inverse
	a, b, c := m[0], m[4], m[8]
	d, e, f := m[1], m[5], m[9]
	g, h, i := m[2], m[6], m[10]
	det := a*(e*i-f*h) - b*(d*i-f*g) + c*(d*h-e*g)
	if det == 0 {
		return identitySlice()
	}
	inv := [9]float64{
		(e*i - f*h) / det, (c*h - b*i) / det, (b*f - c*e) / det,
		(f*g - d*i) / det, (a*i - c*g) / det, (c*d - a*f) / det,
		(d*h - e*g) / det, (b*g - a*h) / det, (a*e - b*d) / det,
	}
	t := vec3{m[12], m[13], m[14]}
	tx := -(inv[0]*t[0] + inv[1]*t[1] + inv[2]*t[2])
	ty := -(inv[3]*t[0] + inv[4]*t[1] + inv[5]*t[2])
	tz := -(inv[6]*t[0] + inv[7]*t[1] + inv[8]*t[2])
	return []float64{inv[0], inv[3], inv[6], 0, inv[1], inv[4], inv[7], 0, inv[2], inv[5], inv[8], 0, tx, ty, tz, 1}
}

// dominantJoint is the skin joint that carries the most vertex weight in the model.
func dominantJoint(g *glb) int {
	weight := map[int]float64{}
	for _, mesh := range g.Doc.Meshes {
		for _, prim := range mesh.Primitives {
			ji, ok1 := prim.Attributes["JOINTS_0"]
			wi, ok2 := prim.Attributes["WEIGHTS_0"]
			if !ok1 || !ok2 {
				continue
			}
			joints, err1 := g.floats(ji)
			weights, err2 := g.floats(wi)
			if err1 != nil || err2 != nil || len(joints) != len(weights) {
				continue
			}
			for v := range joints {
				for k := 0; k < 4 && k < len(joints[v]); k++ {
					weight[int(joints[v][k])] += weights[v][k]
				}
			}
		}
	}
	best, bestW := 0, -1.0
	keys := make([]int, 0, len(weight))
	for k := range weight {
		keys = append(keys, k)
	}
	sort.Ints(keys)
	for _, k := range keys {
		if weight[k] > bestW {
			best, bestW = k, weight[k]
		}
	}
	return best
}

// horizontalAxisTowards is the horizontal axis (glTF X or Z; Y is up) pointing from the box centre towards p.
func horizontalAxisTowards(b bbox, p vec3) vec3 {
	d := p.sub(b.center())
	if math.Abs(d[0]) >= math.Abs(d[2]) {
		return vec3{math.Copysign(1, d[0]), 0, 0}
	}
	return vec3{0, 0, math.Copysign(1, d[2])}
}

// muzzleByShape guesses the muzzle end of a gun lying along its longest horizontal axis: the end
// whose last 15% is shortest vertically (the barrel), not the end with the grip or stock.
func muzzleByShape(parts []part, b bbox) vec3 {
	axis := 0
	if b.extent()[2] > b.extent()[0] {
		axis = 2
	}
	lo, hi := newBBox(), newBBox()
	cut := b.extent()[axis] * 0.15
	for _, p := range parts {
		for _, v := range p.Pos {
			if v[axis] <= b.Min[axis]+cut {
				lo.add(v)
			}
			if v[axis] >= b.Max[axis]-cut {
				hi.add(v)
			}
		}
	}
	sign := 1.0
	if lo.valid() && hi.valid() && lo.extent()[1] < hi.extent()[1] {
		sign = -1
	}
	f := vec3{}
	f[axis] = sign
	return f
}

// yRotation returns the quarter turn about Y (up) that takes from onto to; both are ±X or ±Z.
func yRotation(from, to vec3) func(vec3) vec3 {
	turns := []func(vec3) vec3{
		func(v vec3) vec3 { return v },
		func(v vec3) vec3 { return vec3{v[2], v[1], -v[0]} },
		func(v vec3) vec3 { return vec3{-v[0], v[1], -v[2]} },
		func(v vec3) vec3 { return vec3{-v[2], v[1], v[0]} },
	}
	for _, t := range turns {
		r := t(from)
		if math.Abs(r[0]-to[0]) < 1e-6 && math.Abs(r[2]-to[2]) < 1e-6 {
			return t
		}
	}
	return turns[0]
}

type fitInfo struct {
	Scale     float64
	CPForward vec3
	Dropped   []string
}

// fitParts turns, scales and moves Cyberpunk parts (glTF metres, Y up) onto a Black Ops model.
// Parts after the first whose centre lies well outside the first part's box are dropped (a part
// exported in its own space instead of the gun's).
func fitParts(parts []part, base *baseModel, fitScale float64) ([]part, fitInfo, error) {
	if len(parts) == 0 {
		return nil, fitInfo{}, errors.New("no parts")
	}
	body := partsBBox(parts[:1])
	var kept []part
	info := fitInfo{}
	for i, p := range parts {
		if i > 0 {
			c := partsBBox([]part{p}).center()
			if !body.grown(0.5).contains(c) {
				info.Dropped = append(info.Dropped, p.Material)
				continue
			}
		}
		kept = append(kept, p)
	}
	cpBox := partsBBox(kept)
	info.CPForward = cyberpunkForward(kept, cpBox)
	rot := yRotation(info.CPForward, base.Forward)
	axisLen := func(b bbox, f vec3) float64 {
		if f[0] != 0 {
			return b.extent()[0]
		}
		return b.extent()[2]
	}
	cpLen := axisLen(cpBox, info.CPForward)
	baseLen := axisLen(base.BBox, base.Forward)
	if cpLen <= 0 || baseLen <= 0 {
		return nil, info, fmt.Errorf("empty model (length %.3f / %.3f)", cpLen, baseLen)
	}
	info.Scale = baseLen / cpLen * fitScale
	cpC, baseC := cpBox.center(), base.BBox.center()
	out := make([]part, len(kept))
	for i, p := range kept {
		q := part{Material: p.Material, UV: p.UV, Idx: p.Idx}
		for _, v := range p.Pos {
			q.Pos = append(q.Pos, rot(v.sub(cpC)).scale(info.Scale).add(baseC))
		}
		for _, n := range p.Nrm {
			q.Nrm = append(q.Nrm, rot(n))
		}
		out[i] = q
	}
	return out, info, nil
}

// scaleParts is the rigid-model path: metres to inches times scale, centred on the origin, resting on Y=0.
func scaleParts(parts []part, scale float64) []part {
	b := partsBBox(parts)
	c := b.center()
	c[1] = b.Min[1]
	s := 39.37 * scale
	out := make([]part, len(parts))
	for i, p := range parts {
		q := part{Material: p.Material, UV: p.UV, Idx: p.Idx, Nrm: p.Nrm}
		for _, v := range p.Pos {
			q.Pos = append(q.Pos, v.sub(c).scale(s))
		}
		out[i] = q
	}
	return out
}

// writeModelGLB writes parts bound to base's skeleton (every vertex on BodyJoint).
// materialFor maps a part's Cyberpunk material name to its Black Ops material name.
func writeModelGLB(base *baseModel, parts []part, materialFor func(string) string) ([]byte, error) {
	w := newGLBWriter()
	w.doc.Nodes = append(w.doc.Nodes, base.Nodes...)
	matIndex := map[string]int{}
	mesh := gltfMesh{Name: base.Name}
	for _, p := range parts {
		if len(p.Pos) == 0 || len(p.Idx) == 0 {
			continue
		}
		name := materialFor(p.Material)
		mi, ok := matIndex[name]
		if !ok {
			w.doc.Materials = append(w.doc.Materials, gltfMaterial{Name: name})
			mi = len(w.doc.Materials) - 1
			matIndex[name] = mi
		}
		pos := make([][]float64, len(p.Pos))
		nrm := make([][]float64, len(p.Pos))
		uv := make([][]float64, len(p.Pos))
		joints := make([][4]int, len(p.Pos))
		weights := make([][]float64, len(p.Pos))
		for i := range p.Pos {
			pos[i] = []float64{p.Pos[i][0], p.Pos[i][1], p.Pos[i][2]}
			n := p.Nrm[i].normalized()
			nrm[i] = []float64{n[0], n[1], n[2]}
			uv[i] = []float64{p.UV[i][0], p.UV[i][1]}
			joints[i] = [4]int{base.BodyJoint, 0, 0, 0}
			weights[i] = []float64{1, 0, 0, 0}
		}
		prim := gltfPrimitive{Attributes: map[string]int{
			"POSITION":   w.addFloats(pos, "VEC3", 34962, true),
			"NORMAL":     w.addFloats(nrm, "VEC3", 34962, false),
			"TEXCOORD_0": w.addFloats(uv, "VEC2", 34962, false),
			"JOINTS_0":   w.addJoints(joints),
			"WEIGHTS_0":  w.addFloats(weights, "VEC4", 34962, false),
		}}
		idx := w.addIndices(p.Idx)
		prim.Indices = &idx
		m := mi
		prim.Material = &m
		mesh.Primitives = append(mesh.Primitives, prim)
	}
	if len(mesh.Primitives) == 0 {
		return nil, errors.New("nothing to write")
	}
	w.doc.Meshes = []gltfMesh{mesh}
	ibm := w.addFloats(base.IBM, "MAT4", 0, false)
	joints := make([]int, len(base.Nodes))
	for i := range joints {
		joints[i] = i
	}
	w.doc.Skins = []gltfSkin{{Name: base.Name, InverseBindMatrices: &ibm, Joints: joints}}
	meshIdx, skinIdx := 0, 0
	w.doc.Nodes = append(w.doc.Nodes, gltfNode{Name: base.Name, Mesh: &meshIdx, Skin: &skinIdx})
	scene := 0
	w.doc.Scene = &scene
	w.doc.Scenes = []gltfScene{{Nodes: append(append([]int{}, base.Roots...), len(w.doc.Nodes)-1)}}
	return w.bytes()
}

// cyberpunkForward: Cyberpunk models its guns with the muzzle along +Y in its Z-up space, which WolvenKit's
// Y-up glTF turns into -Z. The shape guess is only used for a mesh not lying along Z.
func cyberpunkForward(parts []part, b bbox) vec3 {
	if b.extent()[2] >= b.extent()[0] {
		return vec3{0, 0, -1}
	}
	return muzzleByShape(parts, b)
}

// simplify merges vertices on a grid (per material and normal direction) until the parts hold at most
// maxVerts vertices. Cyberpunk's guns are far denser than a Black Ops model may be (65535 at most).
func simplify(parts []part, maxVerts int) ([]part, int) {
	total := 0
	for _, p := range parts {
		total += len(p.Pos)
	}
	if total <= maxVerts {
		return parts, total
	}
	b := partsBBox(parts)
	e := b.extent()
	size := math.Max(e[0], math.Max(e[1], e[2]))
	if size <= 0 {
		return parts, total
	}
	var best []part
	bestN := 0
	lo, hi := 8, 1024
	for lo <= hi {
		n := (lo + hi) / 2
		out, count := clusterParts(parts, b.Min, size/float64(n))
		if count <= maxVerts {
			best, bestN = out, count
			lo = n + 1
		} else {
			hi = n - 1
		}
	}
	if best == nil {
		best, bestN = clusterParts(parts, b.Min, size/8)
	}
	return best, bestN
}

func normalBucket(n vec3) int {
	ax, ay, az := math.Abs(n[0]), math.Abs(n[1]), math.Abs(n[2])
	switch {
	case ax >= ay && ax >= az:
		if n[0] < 0 {
			return 1
		}
		return 0
	case ay >= az:
		if n[1] < 0 {
			return 3
		}
		return 2
	}
	if n[2] < 0 {
		return 5
	}
	return 4
}

func clusterParts(parts []part, origin vec3, cell float64) ([]part, int) {
	type key struct{ x, y, z, nb int }
	out := make([]part, 0, len(parts))
	count := 0
	for _, p := range parts {
		ids := map[key]int{}
		remap := make([]int, len(p.Pos))
		q := part{Material: p.Material, Mesh: p.Mesh}
		var sum []vec3
		var nsum []vec3
		var n []int
		for i, v := range p.Pos {
			d := v.sub(origin)
			k := key{int(d[0] / cell), int(d[1] / cell), int(d[2] / cell), normalBucket(p.Nrm[i])}
			id, ok := ids[k]
			if !ok {
				id = len(q.Pos)
				ids[k] = id
				q.Pos = append(q.Pos, vec3{})
				q.Nrm = append(q.Nrm, vec3{})
				q.UV = append(q.UV, p.UV[i])
				sum = append(sum, vec3{})
				nsum = append(nsum, vec3{})
				n = append(n, 0)
			}
			sum[id] = sum[id].add(v)
			nsum[id] = nsum[id].add(p.Nrm[i])
			n[id]++
			remap[i] = id
		}
		for id := range q.Pos {
			q.Pos[id] = sum[id].scale(1 / float64(n[id]))
			q.Nrm[id] = nsum[id].normalized()
		}
		for t := 0; t+2 < len(p.Idx); t += 3 {
			a, b2, c := remap[p.Idx[t]], remap[p.Idx[t+1]], remap[p.Idx[t+2]]
			if a == b2 || b2 == c || a == c {
				continue
			}
			q.Idx = append(q.Idx, a, b2, c)
		}
		if len(q.Idx) == 0 {
			continue
		}
		count += len(q.Pos)
		out = append(out, q)
	}
	return out, count
}

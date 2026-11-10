from PIL import Image
# 12x12 pixel flame. . = empty, d = dark ember, r = deep orange, o = lava orange, y = hot yellow, w = white-hot core
G = """
.....r......
.....rr.....
....rro.....
....roo..r..
...rroor.rr.
..rrooorroo.
..roooyoooo.
.rroyyyyoor.
.rooyywwyor.
.rooyywwyor.
..rooyyyor..
...drrrrd...
"""
C = {'d': (122, 32, 8), 'r': (214, 72, 18), 'o': (255, 122, 47), 'y': (255, 196, 64), 'w': (255, 244, 214)}
rows = [r for r in G.strip('\n').split('\n')]
def render(size, pad=0, bg=None):
    n = 12; s = (size - 2 * pad) // n; off = (size - s * n) // 2
    im = Image.new('RGBA', (size, size), bg or (0, 0, 0, 0))
    for y, row in enumerate(rows):
        for x, ch in enumerate(row):
            if ch in C:
                for i in range(s):
                    for j in range(s):
                        im.putpixel((off + x * s + i, off + y * s + j), C[ch] + (255,))
    return im
render(64, 4, (13, 16, 22, 255)).save('icon-64.png')
render(512, 40, (13, 16, 22, 255)).save('icon-512.png')
render(96).save('mark-96.png')
# SVG for the header
rects = ''.join(f'<rect x="{x}" y="{y}" width="1" height="1" fill="#%02x%02x%02x"/>' % C[ch] for y, row in enumerate(rows) for x, ch in enumerate(row) if ch in C)
open('mark.svg', 'w').write(f'<svg xmlns="http://www.w3.org/2000/svg" viewBox="0 0 12 12" shape-rendering="crispEdges">{rects}</svg>')
prev = Image.new('RGBA', (600, 160), (13, 16, 22, 255))
prev.paste(render(128), (16, 16), render(128)); prev.paste(render(64, 4, (13,16,22,255)), (180, 48)); prev.paste(render(32, 2, (13,16,22,255)), (270, 64))
prev.save('preview.png')

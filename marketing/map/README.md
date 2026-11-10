# Anarchy spawn map

Top-down map of the 3.5 × 3.5 km around Crispy Anarchy's spawn (287, -207), 1 pixel = 1 block.

1. `extract.py <region dir> <out dir> <rx0> <rx1> <rz0> <rz1>`: run on the AMP host (read-only, low priority:
   `nice -n 19 ionice -c3`) against `CrispyAnarchy01/Minecraft/world/dimensions/minecraft/overworld/region`.
   Writes per region the top block, height and water depth of every column (~110 KB per region; ~6 s per region).
   The 2026-11-10 render used regions -3..3 × -4..2, output in `CrispyAnarchy01/Minecraft/crispy_map_extract`.
2. `render.py <extract dir> <out.png>`: colours and shades it like an in-game map (needs Pillow).
3. Save the PNG as lossless WebP (`spawn.webp`) next to `index.html`, the pan/zoom viewer (pixel (0,0) =
   block -1536, -2048; change ORIGIN_X/Z if the area changes). Published as a claude.ai artifact.

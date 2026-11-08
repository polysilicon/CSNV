"""gif2mp4.py <in.gif> <out.mp4>: exact timing (every frame's duration is a multiple of 90 ms; repeat frames at 100/9 fps)."""
import subprocess, sys
from PIL import Image, ImageSequence
src, out = sys.argv[1:3]
im = Image.open(src); W, H = im.size
p = subprocess.Popen(["ffmpeg", "-v", "error", "-y", "-f", "rawvideo", "-pix_fmt", "rgb24", "-s", f"{W}x{H}", "-r", "100/9", "-i", "-",
                      "-c:v", "libx264", "-pix_fmt", "yuv420p", "-crf", "18", "-preset", "slow", "-movflags", "+faststart", out], stdin=subprocess.PIPE)
total = 0
for fr in ImageSequence.Iterator(im):
    d = fr.info.get("duration", 90); assert d % 90 == 0, d
    rgb = fr.convert("RGB").tobytes()
    for _ in range(d // 90): p.stdin.write(rgb)
    total += d
p.stdin.close(); p.wait(); print(out, total / 1000, "s")

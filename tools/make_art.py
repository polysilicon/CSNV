#!/usr/bin/env python3
"""Draws the project's original art into assets/ (procedural, no external sources):
armor.png - a 64x64 shield icon for the CS-style armor readout; white.png - an 8x8 white square
that the HUD tints for the crosshair arms and the buy-screen panels."""
from pathlib import Path

from img import write_png

ASSETS = Path(__file__).resolve().parent.parent / "assets"


def shield(size=64):
    rows = []
    cx = (size - 1) / 2
    for y in range(size):
        row = []
        for x in range(size):
            t = y / (size - 1)
            # straight top half, then a point at the bottom
            half = (size * 0.42) if t < 0.5 else (size * 0.42) * max(0.0, 1 - ((t - 0.5) / 0.5) ** 1.4)
            inside = 4 <= y <= size - 4 and abs(x - cx) <= half
            border = inside and abs(x - cx) > half - 4.5
            if not inside:
                row.append((0, 0, 0, 0))
            elif border or y < 8:
                row.append((235, 235, 235, 255))
            else:
                row.append((235, 235, 235, 70 if abs(x - cx) > 3 else 255))
        rows.append(row)
    return rows


def main():
    from img import write_png as w
    ASSETS.mkdir(exist_ok=True)
    w(ASSETS / "armor.png", 64, 64, shield())
    w(ASSETS / "white.png", 8, 8, [[(255, 255, 255, 255)] * 8 for _ in range(8)])
    print("wrote", ", ".join(p.name for p in sorted(ASSETS.glob("*.png"))))


if __name__ == "__main__":
    main()

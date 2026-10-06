#!/usr/bin/env python3
"""Preflight for CS2 in the Mojave: lists every unfilled cell, every unverified row and
every cross-sheet reference that does not resolve. Exit code 0 only when all are clean."""
import json
import sys
from pathlib import Path

SHEETS = Path(__file__).resolve().parent.parent / "sheets"

# column -> sheet whose ids it must reference
REFS = {
    ("hud", "source_hook"): "hooks",
    ("buy_menu", "weapon"): "weapons",
    ("buy_menu", "open_hook"): "hooks",
    ("buy_menu", "pay_hook"): "hooks",
    ("buy_menu", "give_hook"): "hooks",
}


def main():
    sheets = {}
    for path in sorted(SHEETS.glob("*.json")):
        data = json.loads(path.read_text())
        sheets[data["sheet"]] = data

    unfilled, unverified, broken, problems = [], [], [], []
    for name, data in sheets.items():
        cols = list(data["columns"])
        ids = [row.get("id") for row in data["rows"]]
        if len(ids) != len(set(ids)):
            problems.append(f"{name}: duplicate ids")
        for row in data["rows"]:
            rid = row.get("id", "?")
            for extra in set(row) - set(cols):
                problems.append(f"{name}.{rid}: column '{extra}' not declared")
            for col in cols:
                if row.get(col) in (None, "", "TODO"):
                    unfilled.append(f"{name}.{rid}.{col}")
            if row.get("verified") is not True:
                unverified.append(f"{name}.{rid}")
            for (sheet, col), target in REFS.items():
                if sheet == name and row.get(col) is not None:
                    target_ids = {r["id"] for r in sheets.get(target, {"rows": []})["rows"]}
                    if row[col] not in target_ids:
                        broken.append(f"{name}.{rid}.{col} -> {target}.{row[col]}")

    total = sum(len(d["rows"]) * len(d["columns"]) for d in sheets.values())
    print(f"Sheets: {', '.join(sheets)}  |  cells: {total}")
    for title, items in (("Unfilled cells", unfilled), ("Broken references", broken),
                         ("Sheet problems", problems), ("Rows not verified in game", unverified)):
        print(f"\n{title} ({len(items)}):")
        for item in items:
            print(f"  - {item}")
    clean = not (unfilled or broken or problems)
    print("\nBuild gate:", "CLEAN" if clean else "BLOCKED (fix unfilled/broken first)")
    print("Release gate:", "READY" if clean and not unverified else "NOT READY (rows untested in game)")
    return 0 if clean else 1


if __name__ == "__main__":
    sys.exit(main())

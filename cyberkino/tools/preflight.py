#!/usr/bin/env python3
"""Preflight for Cyberpunk Kino: lays every sheet's rows and columns over each other and lists
every unfilled cell, every cross-sheet reference that does not resolve and every row not yet
tested in the game. Exit code 0 only when nothing is unfilled or broken (untested rows are listed,
they don't fail the build: they can only be checked in the running game).

If CYBERKINO_PATHS points to a text file with one Cyberpunk depot path per line (WolvenKit's path
list), every Cyberpunk mesh in the sheets is also checked against it."""
import json
import os
import re
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent
SHEETS = ROOT / "sheets"

ENUMS = {
    ("weapons", "role"): {"start", "wall", "box", "rare"},
    ("weapons", "vox"): {"pistol", "smg", "shotgun", "assault", "sniper", "mg", "raygun"},
    ("cyberware", "effect"): {"slowmo", "double_jump", "armor", "mantis"},
    ("models", "kind"): {"view", "rigid"},
    ("hooks", "action"): {"insert_before", "insert_after"},
    ("zones", "use"): {"load", "unlink"},
}
# columns that may legitimately hold an empty list
EMPTY_LIST_OK = {("weapons", "replaces")}
# cyberware params each effect needs
EFFECT_PARAMS = {
    "slowmo": {"timescale", "duration_s", "cooldown_s"},
    "double_jump": {"jump_velocity", "min_air_s"},
    "armor": {"health_bonus"},
    "mantis": {"melee_damage", "base"},
}
REQUIRED_RULES = {"first_round", "specials_per_round", "chip_lifetime_s", "pickup_radius", "lose_on_down"}
NAME = re.compile(r"^[a-z0-9_]+$")


def load():
    sheets = {}
    for path in sorted(SHEETS.glob("*.json")):
        data = json.loads(path.read_text())
        sheets[data["sheet"]] = data
    return sheets


def main():
    sheets = load()
    unfilled, broken, problems, untested = [], [], [], []

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
                value = row.get(col)
                if value is None or value == "" or value == "TODO":
                    unfilled.append(f"{name}.{rid}.{col}")
                elif value == [] and (name, col) not in EMPTY_LIST_OK:
                    unfilled.append(f"{name}.{rid}.{col}")
                if (name, col) in ENUMS and value is not None and value not in ENUMS[(name, col)]:
                    problems.append(f"{name}.{rid}.{col}: '{value}' not one of {sorted(ENUMS[(name, col)])}")
            if "tested_in_game" in cols and row.get("tested_in_game") is not True:
                untested.append(f"{name}.{rid}")

    weapons = sheets["weapons"]["rows"]
    models = {r["id"]: r for r in sheets["models"]["rows"]}
    wall_stock = {}
    for w in weapons:
        rid = w["id"]
        if not NAME.match(rid):
            problems.append(f"weapons.{rid}: id must be lower-case letters, digits and _")
        if w["role"] in ("start", "wall") and not w["replaces"]:
            broken.append(f"weapons.{rid}.replaces: a {w['role']} gun must replace at least one stock weapon")
        if w["role"] in ("box", "rare") and w["replaces"]:
            problems.append(f"weapons.{rid}.replaces: only start and wall guns replace stock weapons")
        if w["role"] == "wall" and not w["cost"] > 0:
            problems.append(f"weapons.{rid}.cost: wall-buys need a price")
        want_weight = {"box": 3, "rare": 1}.get(w["role"], 0)
        if w["box_weight"] != want_weight:
            problems.append(f"weapons.{rid}.box_weight: {w['role']} guns use {want_weight}")
        for stock in w["replaces"]:
            if stock in wall_stock:
                broken.append(f"weapons.{rid}.replaces: {stock} already replaced by {wall_stock[stock]}")
            wall_stock[stock] = rid
        for col in ("damage_mult", "fire_time_mult", "pap_damage_mult", "fit_scale"):
            if not (isinstance(w[col], (int, float)) and 0 < w[col] <= 10):
                problems.append(f"weapons.{rid}.{col}: expected a number between 0 and 10")
        for col in ("clip_size", "max_ammo", "pap_clip_size", "pap_max_ammo"):
            if not (isinstance(w[col], int) and w[col] > 0):
                problems.append(f"weapons.{rid}.{col}: expected a whole number above 0")
        if not all(p.startswith("base\\") and p.endswith(".mesh") for p in w["cp_meshes"]):
            problems.append(f"weapons.{rid}.cp_meshes: expected base\\...\\*.mesh depot paths")
    if not any(w["role"] == "start" for w in weapons):
        broken.append("weapons: no start gun (role start)")

    for c in sheets["cyberware"]["rows"]:
        rid = c["id"]
        need = EFFECT_PARAMS.get(c["effect"], set())
        missing = need - set(c["params"])
        if missing:
            unfilled.extend(f"cyberware.{rid}.params.{m}" for m in sorted(missing))
        if c["model"] != "none" and c["model"] not in models:
            broken.append(f"cyberware.{rid}.model -> models.{c['model']}")
    if {c["id"] for c in sheets["cyberware"]["rows"]} != {"sandevistan", "tendons", "subdermal", "mantis"}:
        problems.append("cyberware: the script expects exactly sandevistan, tendons, subdermal and mantis")
    mantis = [c for c in sheets["cyberware"]["rows"] if c["effect"] == "mantis"]
    if mantis and models.get(mantis[0]["model"], {}).get("fit_to") != mantis[0]["params"].get("base"):
        broken.append("cyberware.mantis: params.base must equal its model's fit_to")

    for m in models.values():
        if m["kind"] == "view" and m["fit_to"] == "none":
            broken.append(f"models.{m['id']}.fit_to: a view model needs a Black Ops weapon to fit to")
        if m["kind"] == "rigid" and m["fit_to"] != "none":
            problems.append(f"models.{m['id']}.fit_to: rigid models are not fitted (use none)")

    rules = {r["id"] for r in sheets["rules"]["rows"]}
    for missing in sorted(REQUIRED_RULES - rules):
        unfilled.append(f"rules.{missing}")

    for h in sheets["hooks"]["rows"]:
        try:
            re.compile(h["anchor"].replace("(?m)", ""), re.M)
        except re.error as e:
            problems.append(f"hooks.{h['id']}.anchor: {e}")
    zones = {z["id"]: z for z in sheets["zones"]["rows"]}
    hook_files = {h["file"] for h in sheets["hooks"]["rows"]}
    if not any(z["use"] == "unlink" for z in zones.values()) and hook_files:
        broken.append("hooks: no zone is unlinked, so the hooked scripts can't be read")

    for t in sheets["tools"]["rows"]:
        if not re.fullmatch(r"[0-9a-f]{64}", t["sha256"]):
            problems.append(f"tools.{t['id']}.sha256: not a SHA-256")
        if not t["url"].startswith("https://"):
            problems.append(f"tools.{t['id']}.url: must be https")

    paths_file = os.environ.get("CYBERKINO_PATHS")
    mesh_note = "Cyberpunk mesh paths: not checked (set CYBERKINO_PATHS to WolvenKit's path list)"
    if paths_file and Path(paths_file).is_file():
        known = set(Path(paths_file).read_text(encoding="utf-8", errors="replace").split("\n"))
        known = {k.strip() for k in known}
        all_meshes = [(f"weapons.{w['id']}", p) for w in weapons for p in w["cp_meshes"]]
        all_meshes += [(f"models.{m['id']}", p) for m in models.values() for p in m["cp_meshes"]]
        for where, p in all_meshes:
            if p not in known:
                broken.append(f"{where}.cp_meshes: {p} is not in the game's path list")
        mesh_note = f"Cyberpunk mesh paths: {len(all_meshes)} checked against {paths_file}"

    rows = sum(len(d["rows"]) for d in sheets.values())
    cells = sum(len(d["rows"]) * len(d["columns"]) for d in sheets.values())
    print(f"Sheets: {len(sheets)}, rows: {rows}, cells: {cells}")
    print(mesh_note)
    for title, items in (("Unfilled", unfilled), ("Broken references", broken), ("Problems", problems)):
        print(f"{title}: {len(items)}")
        for item in items:
            print(f"  {item}")
    print(f"Untested in game: {len(untested)} rows")
    if unfilled or broken or problems:
        return 1
    print("Preflight clean.")
    return 0


if __name__ == "__main__":
    sys.exit(main())

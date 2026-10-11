#!/usr/bin/env python3
"""Preflight for Cyberpunk Kino: lays every sheet's rows and columns over each other and lists every
unfilled cell, every cross-reference that does not resolve and every row not yet tested in the game.
Exit code 0 only when nothing is unfilled or broken (untested rows are listed; only the game can check them).

Optional checks against the games' own name lists:
  CYBERKINO_TDB    text file of Cyberpunk TweakDB record names (WolvenKit's tweakdbstr.kark)
  CYBERKINO_PATHS  text file of Cyberpunk depot paths (WolvenKit's usedhashes.kark)"""
import json
import os
import re
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent
SHEETS = ROOT / "sheets"

ENUMS = {
    ("weapons", "role"): {"start", "wall", "box", "rare"},
    ("cyberware", "effect"): {"stat", "slowmo", "item"},
    ("zombies", "pool"): {"scavenger", "maelstrom", "boss"},
    ("keys", "kind"): {"hotkey", "input"},
    ("layout", "kind"): {"start", "barricade", "wallbuy", "box", "spawn", "stash"},
}
EFFECT_PARAMS = {"stat": {"stat", "value"}, "slowmo": {"key", "timescale", "duration_s", "cooldown_s"}, "item": {"record"}}
REQUIRED_RULES = {
    "start_points", "kill_points", "special_points", "boss_points", "box_cost", "rare_weight", "door_cost_first",
    "door_cost_step", "round_base", "round_step", "max_active", "spawn_interval_s", "boss_every", "round_break_s",
    "end_health_pct", "chip_lifetime_s", "buy_radius_m", "teleport_settle_s", "barricade_hold_m", "box_moves_after",
    "barricade_half_width_m", "floor_height_m",
}
REQUIRED_KEYS = {"start", "use", "sandevistan"}
NAME = re.compile(r"^[a-z0-9_]+$")


def load():
    return {json.loads(p.read_text())["sheet"]: json.loads(p.read_text()) for p in sorted(SHEETS.glob("*.json"))}


def name_list(env):
    p = os.environ.get(env)
    if p and Path(p).is_file():
        return {line.strip() for line in Path(p).read_text(encoding="utf-8", errors="replace").split("\n")}, p
    return None, None


def main():
    sheets = load()
    unfilled, broken, problems, untested = [], [], [], []
    for name, data in sheets.items():
        cols = list(data["columns"])
        ids = [r.get("id") for r in data["rows"]]
        if len(ids) != len(set(ids)):
            problems.append(f"{name}: duplicate ids")
        for row in data["rows"]:
            rid = row.get("id", "?")
            if not NAME.match(str(rid)):
                problems.append(f"{name}.{rid}: id must be lower-case letters, digits and _")
            for extra in set(row) - set(cols):
                problems.append(f"{name}.{rid}: column '{extra}' not declared")
            for col in cols:
                v = row.get(col)
                if v is None or v == "" or v == "TODO" or v == []:
                    unfilled.append(f"{name}.{rid}.{col}")
                if (name, col) in ENUMS and v is not None and v not in ENUMS[(name, col)]:
                    problems.append(f"{name}.{rid}.{col}: '{v}' not one of {sorted(ENUMS[(name, col)])}")
            if "tested_in_game" in cols and row.get("tested_in_game") is not True:
                untested.append(f"{name}.{rid}")

    notes = []
    weapons = sheets["weapons"]["rows"]
    if [w["id"] for w in weapons if w["role"] == "start"] == []:
        broken.append("weapons: no start gun")
    if len([w for w in weapons if w["role"] == "start"]) > 1:
        problems.append("weapons: only one start gun")
    for w in weapons:
        if w["role"] == "wall" and not w["cost"] > 0:
            problems.append(f"weapons.{w['id']}.cost: a wall-buy needs a price")
        if w["role"] != "wall" and w["cost"] != 0:
            problems.append(f"weapons.{w['id']}.cost: only wall-buys have a price")
        if not w["record"].startswith("Items.") or not w["ammo"].startswith("Ammo."):
            problems.append(f"weapons.{w['id']}: record must be Items.*, ammo Ammo.*")
    if not any(w["id"] == "raygun" for w in weapons):
        broken.append("weapons: the Ray Gun row is missing (sheets/raygun.json builds it)")

    for c in sheets["cyberware"]["rows"]:
        missing = EFFECT_PARAMS[c["effect"]] - set(c["params"])
        unfilled += [f"cyberware.{c['id']}.params.{m}" for m in sorted(missing)]
    keys = {k["id"] for k in sheets["keys"]["rows"]}
    for missing in sorted(REQUIRED_KEYS - keys):
        broken.append(f"keys.{missing}: the script uses this binding")
    for c in sheets["cyberware"]["rows"]:
        if c["effect"] == "slowmo" and c["params"].get("key") not in keys:
            broken.append(f"cyberware.{c['id']}.params.key -> keys.{c['params'].get('key')}")
    rules = {r["id"] for r in sheets["rules"]["rows"]}
    unfilled += [f"rules.{m}" for m in sorted(REQUIRED_RULES - rules)]
    pools = {z["pool"] for z in sheets["zombies"]["rows"]}
    for p in ("scavenger", "maelstrom", "boss"):
        if p not in pools:
            broken.append(f"zombies: no {p} row")
    if not any(z["from_round"] == 1 for z in sheets["zombies"]["rows"]):
        broken.append("zombies: nothing can appear in round 1")
    if {p["id"] for p in sheets["props"]["rows"]} != {"barricade", "wallbuy", "box", "chip"}:
        broken.append("props: the script needs barricade, wallbuy, box and chip")
    wall_ids = {w["id"] for w in weapons if w["role"] == "wall"}
    for r in sheets["layout"]["rows"]:
        if r["kind"] == "wallbuy" and r["weapon"] not in wall_ids:
            broken.append(f"layout.{r['id']}.weapon -> weapons (wall) .{r['weapon']}")
        if r["kind"] == "stash" and not str(r["entity"]).endswith("ULL"):
            problems.append(f"layout.{r['id']}.entity: expected a CET uint64 like 123ULL")
    if not sheets["layout"]["rows"]:
        notes.append("layout: no rows yet (record one with the in-game layout editor)")
    if not any(a["id"] == "h10" for a in sheets["arena"]["rows"]):
        broken.append("arena: h10 row missing")
    for t in sheets["tools"]["rows"]:
        if not re.fullmatch(r"[0-9a-f]{64}", t["sha256"]):
            problems.append(f"tools.{t['id']}.sha256: not a SHA-256")

    tdb, tdb_path = name_list("CYBERKINO_TDB")
    if tdb:
        records = [(f"weapons.{w['id']}.record", w["record"]) for w in weapons]
        records += [(f"weapons.{w['id']}.ammo", w["ammo"]) for w in weapons]
        records += [(f"zombies.{z['id']}.record", z["record"]) for z in sheets["zombies"]["rows"]]
        records += [(f"cyberware.{c['id']}.params.record", c["params"]["record"]) for c in sheets["cyberware"]["rows"] if c["effect"] == "item"]
        records += [(f"cyberware.{c['id']}.params.stat", "BaseStats." + c["params"]["stat"]) for c in sheets["cyberware"]["rows"] if c["effect"] == "stat"]
        for where, rec in records:
            if rec not in tdb:
                broken.append(f"{where}: {rec} is not a Cyberpunk TweakDB record")
        notes.append(f"{len(records)} TweakDB records checked against {tdb_path}")
    paths, paths_path = name_list("CYBERKINO_PATHS")
    if paths:
        depot = [(f"props.{p['id']}.entity", p["entity"]) for p in sheets["props"]["rows"]]
        depot += [(f"raygun.{r['id']}.cp_donor_mesh", r["cp_donor_mesh"]) for r in sheets["raygun"]["rows"]]
        for where, p in depot:
            if p not in paths:
                broken.append(f"{where}: {p} is not in Cyberpunk's path list")
        for r in sheets["raygun"]["rows"]:
            hidden = [p for p in paths if p.startswith(r["cp_hide_prefix"]) and p.endswith(".mesh") and p != r["cp_donor_mesh"]]
            if not hidden or not r["cp_donor_mesh"].startswith(r["cp_hide_prefix"]):
                broken.append(f"raygun.{r['id']}.cp_hide_prefix matches {len(hidden)} meshes, or not the donor's folder")
            else:
                notes.append(f"raygun: {len(hidden)} donor part meshes will be emptied")
        notes.append(f"{len(depot)} depot paths checked against {paths_path}")

    rows = sum(len(d["rows"]) for d in sheets.values())
    cells = sum(len(d["rows"]) * len(d["columns"]) for d in sheets.values())
    print(f"Sheets: {len(sheets)}, rows: {rows}, cells: {cells}")
    for n in notes or ["game name lists: not checked (set CYBERKINO_TDB and CYBERKINO_PATHS)"]:
        print(n)
    for title, items in (("Unfilled", unfilled), ("Broken references", broken), ("Problems", problems)):
        print(f"{title}: {len(items)}")
        for i in items:
            print(f"  {i}")
    print(f"Untested in game: {len(untested)} rows")
    if unfilled or broken or problems:
        return 1
    print("Preflight clean.")
    return 0


if __name__ == "__main__":
    sys.exit(main())

#!/usr/bin/env python3
"""Preflight: lay every sheet over each other and list unfilled cells and broken cross-references.
Exit 1 if anything would fail the build. Rows not yet seen working in the game are listed, not fatal."""
import json, glob, os, sys
HERE = os.path.dirname(os.path.abspath(__file__))
SHEETS = os.path.join(HERE, "..", "sheets")

def load():
    out = {}
    for f in sorted(glob.glob(os.path.join(SHEETS, "*.json"))):
        d = json.load(open(f))
        out[d["sheet"]] = d["rows"]
    return out

# columns that may legitimately be empty / zero for some effect kinds
OPTIONAL = {
    "crab_perks": {"stat", "mod", "value", "status", "radius", "interval", "chance", "amount"},
}
PERK_NEEDS = {
    "stat": ["stat", "mod", "value"], "regen": ["amount"], "aura": ["status", "radius", "interval"],
    "on_kill": ["status", "radius", "chance"], "crystals_kill": ["amount"], "crystals_wave": ["amount"],
    "crystals_mult": ["amount"], "discount": ["amount"],
}
STAT_TYPES = {"Health", "MaxSpeed", "CritChance", "CritDamage", "Armor", "AllDamageDonePercentBonus", "JumpHeight"}
MOD_TYPES = {"Additive", "AdditiveMultiplier", "Multiplier"}
AREAS = {"ArmsCW", "SystemReplacementCW", "IntegumentarySystemCW", "MusculoskeletalSystemCW"}

def preflight(s):
    errors, pending, cells = [], [], 0
    for name, rows in s.items():
        cols = set()
        for r in rows: cols |= set(r)
        for i, r in enumerate(rows):
            rid = r.get("id") or r.get("key") or r.get("event") or r.get("slot")
            for c in sorted(cols):
                cells += 1
                v = r.get(c)
                if c not in r:
                    errors.append(f"{name}[{rid}].{c}: missing cell")
                elif v is None or v == "" or v == []:
                    if c not in OPTIONAL.get(name, ()):
                        errors.append(f"{name}[{rid}].{c}: unfilled")
            if r.get("verified") is False:
                pending.append(f"{name}[{rid}]: source not yet checked against real files")
            if r.get("in_game") is False:
                pending.append(f"{name}[{rid}]: not yet seen working in game")
    ids = lambda n, k="id": {r[k] for r in s.get(n, [])}
    sysrow = s["systems"][0]
    # cross references
    if sysrow["starter_weapon"] not in ids("shop_weapons"):
        errors.append(f"systems.starter_weapon -> shop_weapons '{sysrow['starter_weapon']}' does not resolve")
    starters = [r for r in s["shop_weapons"] if r["starter"]]
    if len(starters) != 1 or starters[0]["id"] != sysrow["starter_weapon"]:
        errors.append("shop_weapons: exactly one starter row must match systems.starter_weapon")
    tiers = {r["tier"] for r in s["enemies"]}
    for w in s["waves"]:
        for t in w["tiers"]:
            if t not in tiers: errors.append(f"waves[{w['id']}].tiers: tier {t} has no enemies")
        if w["from_wave"] > w["to_wave"]: errors.append(f"waves[{w['id']}]: from_wave > to_wave")
    # contiguous coverage of waves 1..999
    cover = sorted((w["from_wave"], w["to_wave"]) for w in s["waves"])
    nxt = 1
    for a, b in cover:
        if a != nxt: errors.append(f"waves: gap or overlap at wave {nxt} (next band starts {a})")
        nxt = b + 1
    if not any(e["boss"] for e in s["enemies"]): errors.append("enemies: no boss rows for boss waves")
    pools = {"crab_perks", "shop_cyberware", "shop_weapons"}
    for r in s["shop_layout"]:
        if r["pool"] not in pools: errors.append(f"shop_layout[{r['slot']}].pool '{r['pool']}' does not resolve")
    if sorted(r["slot"] for r in s["shop_layout"]) != list(range(1, len(s["shop_layout"]) + 1)):
        errors.append("shop_layout: slots must be 1..n")
    buy_actions = {r["action"] for r in s["keys"]}
    for r in s["shop_layout"]:
        if f"buy{r['slot']}" not in buy_actions: errors.append(f"keys: no key for buy{r['slot']}")
    for a in ("reroll", "continue", "seed_entry", "new_run", "end_run", "seed_back", "seed_char"):
        if a not in buy_actions: errors.append(f"keys: no key for action {a}")
    alpha = sysrow["seed_alphabet"]
    for c in alpha:
        if not any(k["key"] == c and k["action"] == "seed_char" for k in s["keys"]):
            errors.append(f"keys: seed alphabet char '{c}' has no key")
    for p in s["crab_perks"]:
        need = PERK_NEEDS.get(p["effect"])
        if need is None: errors.append(f"crab_perks[{p['key']}].effect '{p['effect']}' unknown"); continue
        for c in need:
            if p.get(c) in ("", 0, 0.0, None): errors.append(f"crab_perks[{p['key']}].{c}: required for effect {p['effect']}")
        if p["effect"] == "stat":
            if p["stat"] not in STAT_TYPES: errors.append(f"crab_perks[{p['key']}].stat '{p['stat']}' not a checked gamedataStatType")
            if p["mod"] not in MOD_TYPES: errors.append(f"crab_perks[{p['key']}].mod '{p['mod']}' unknown")
    for c in s["shop_cyberware"]:
        if c["area"] not in AREAS: errors.append(f"shop_cyberware[{c['id']}].area '{c['area']}' not handled")
    for n in ("enemies", "shop_weapons", "shop_cyberware"):
        seen = set()
        for r in s[n]:
            if not r["record"].startswith(("Character.", "Items.")): errors.append(f"{n}[{r['id']}].record malformed")
            if r["record"] in seen: errors.append(f"{n}[{r['id']}].record duplicate")
            seen.add(r["record"])
    events = {r["event"] for r in s["crab_sounds"]}
    for ev in ("crystal", "buy", "perk", "wave_start", "wave_clear", "portal", "boss", "death", "countdown", "music"):
        if ev not in events: errors.append(f"crab_sounds: event '{ev}' used by the mod has no row")
    if len(s["stages"]) < 2: errors.append("stages: need at least 2 islands")
    return errors, pending, cells

if __name__ == "__main__":
    s = load()
    errors, pending, cells = preflight(s)
    rows = sum(len(v) for v in s.values())
    print(f"preflight: {len(s)} sheets, {rows} rows, {cells} cells")
    for e in errors: print("  FAIL", e)
    verbose = "-v" in sys.argv
    from collections import Counter
    kinds = Counter(p.split(":")[1].strip() for p in pending)
    for k, n in kinds.items(): print(f"  PENDING {n} rows: {k}")
    if verbose:
        for p in pending: print("   ", p)
    print("preflight:", "CLEAN" if not errors else f"{len(errors)} problem(s)")
    sys.exit(1 if errors else 0)

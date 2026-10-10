#!/usr/bin/env python3
"""Build Cyberpunk Kino from its sheets.

  python3 tools/build.py            generate scripts, strings and launcher tables, build the launcher
  python3 tools/build.py --release  also download the bundled tools (checked by SHA-256) and make
                                    build/CyberKino-<version>.zip

Generated from sheets/*.json:
  gsc/maps/cyberkino.gsc                         server script (tables + gsc/maps/cyberkino.gsc.in)
  gsc/clientscripts/cyberkino.csc                client includes for the Mystery Box display
  gsc/english/localizedstrings/cyberkino.str     every string the mod shows
  launcher/sheets_gen.go                         the launcher's tables
"""
import argparse
import hashlib
import json
import os
import re
import shutil
import subprocess
import sys
import urllib.request
import zipfile
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent
SHEETS = ROOT / "sheets"
BUILD = ROOT / "build"
VERSION_FILE = ROOT / "VERSION"


def sheet(name):
    return json.loads((SHEETS / f"{name}.json").read_text())["rows"]


def gsc_str(s):
    if '"' in s or "\\" in s:
        raise SystemExit(f"string not allowed in a script: {s!r}")
    return f'"{s}"'


def key(*parts):
    return "CYBERKINO_" + "_".join(p.upper() for p in parts)


# ---------------------------------------------------------------- strings

def strings():
    out = {}
    for w in sheet("weapons"):
        out[key("W", w["id"])] = w["name"]
        out[key("W", w["id"], "UP")] = w["pap_name"]
        out[key("BUY", w["id"])] = f"Hold [{{+activate}}] for {w['name']} [Cost: &&1]"
    for c in sheet("cyberware"):
        out[key("CHIP", c["id"])] = f"{c['name']} installed. {c['how_to_use']}"
        out[key("HUD", c["id"])] = c["name"]
    out[key("CHIP_HINT")] = "Hold [{+activate}] to install the cyberware chip"
    out[key("ALL_INSTALLED")] = "All cyberware installed"
    out[key("SANDEVISTAN_ON")] = "SANDEVISTAN"
    out[key("READY")] = "Sandevistan ready"
    out[key("W", "MANTIS")] = "Mantis Blades"
    return out


def str_file(entries):
    lines = ['VERSION             "1"', 'CONFIG              "C:/projects/cod/t5/bin/StringEd.cfg"', 'FILENOTES           ""', ""]
    for k, v in entries.items():
        if '"' in v:
            raise SystemExit(f"string {k} contains a quote")
        lines += [f"REFERENCE           {k}", f'LANG_ENGLISH        "{v}"', ""]
    lines.append("ENDMARKER")
    return "\r\n".join(lines) + "\r\n"


# ---------------------------------------------------------------- scripts

def gsc_tables():
    weapons, cyber = sheet("weapons"), sheet("cyberware")
    rules = {r["id"]: r["value"] for r in sheet("rules")}
    params = {c["id"]: c["params"] for c in cyber}
    lines = ["init_tables()", "{", "\tlevel.cpk_weapons = [];"]
    for w in weapons:
        lines.append(
            f"\tcpk_add_weapon( {gsc_str(w['id'])}, {gsc_str('cpk_' + w['id'] + '_zm')}, {gsc_str('cpk_' + w['id'] + '_upgraded_zm')}, "
            f"{gsc_str(w['role'])}, {w['cost']}, {w['box_weight']}, {gsc_str(w['vox'])}, &{gsc_str(key('BUY', w['id']))} );")
    lines.append("")
    lines.append("\tlevel.cpk_wall = [];")
    lines.append("\tlevel.cpk_start_swap = [];")
    for w in weapons:
        for stock in w["replaces"]:
            table = "cpk_start_swap" if w["role"] == "start" else "cpk_wall"
            lines.append(f"\tlevel.{table}[{gsc_str(stock)}] = {gsc_str('cpk_' + w['id'] + '_zm')};")
            if w["role"] == "start":
                # the Pack-a-Punched starting pistol becomes the Pack-a-Punched start gun
                up = next(x["bo_base_upgraded"] for x in weapons if x["id"] == w["id"])
                lines.append(f"\tlevel.cpk_start_swap[{gsc_str(up)}] = {gsc_str('cpk_' + w['id'] + '_upgraded_zm')};")
    lines.append("")
    lines.append("\tlevel.cpk_box_keep = [];")
    for k in sheet("box_keep"):
        lines.append(f"\tlevel.cpk_box_keep[{gsc_str(k['id'])}] = true;")
    lines.append("")
    lines.append("\tlevel.cpk_cyber = [];")
    for c in cyber:
        lines.append(f"\tcpk_add_cyber( {gsc_str(c['id'])}, {gsc_str(c['effect'])}, &{gsc_str(key('CHIP', c['id']))}, &{gsc_str(key('HUD', c['id']))} );")
    lines.append("")
    lines.append("\tlevel.cpk_rules = [];")
    for k, v in rules.items():
        lines.append(f"\tlevel.cpk_rules[{gsc_str(k)}] = {v};")
    s, t, a, m = params["sandevistan"], params["tendons"], params["subdermal"], params["mantis"]
    lines += [
        "",
        f"\tlevel.cpk_sandevistan_timescale = {gsc_str(str(s['timescale']))};",
        f"\tlevel.cpk_sandevistan_timescale_num = {s['timescale']};",
        f"\tlevel.cpk_sandevistan_duration = {s['duration_s']};",
        f"\tlevel.cpk_sandevistan_cooldown = {s['cooldown_s']};",
        f"\tlevel.cpk_tendons_velocity = {t['jump_velocity']};",
        f"\tlevel.cpk_tendons_min_air = {t['min_air_s']};",
        f"\tlevel.cpk_subdermal_bonus = {a['health_bonus']};",
        f"\tlevel.cpk_mantis_weapon = {gsc_str('cpk_mantis_zm')};",
        "}",
    ]
    return "\n".join(lines)


def csc_includes():
    lines = []
    for w in sheet("weapons"):
        in_box = "true" if w["box_weight"] > 0 else "false"
        lines.append(f"\tinclude_weapon( {gsc_str('cpk_' + w['id'] + '_zm')}, {in_box} );")
        lines.append(f"\tinclude_weapon( {gsc_str('cpk_' + w['id'] + '_upgraded_zm')}, false );")
    lines.append(f"\tinclude_weapon( {gsc_str('cpk_mantis_zm')}, false );")
    return "\n".join(lines)


def check_script(path, text):
    """Cheap checks that catch the mistakes that stop a script compiling in Black Ops."""
    depth = 0
    for ch in re.sub(r'"[^"\n]*"|//[^\n]*', "", text):
        depth += {"{": 1, "}": -1}.get(ch, 0)
        if depth < 0:
            raise SystemExit(f"{path}: unbalanced braces")
    if depth != 0:
        raise SystemExit(f"{path}: unbalanced braces")
    defined = set(re.findall(r"(?m)^([A-Za-z_][A-Za-z0-9_]*)\s*\(", text))
    called = set(re.findall(r"(?:::|thread\s+|\s)(cpk_[A-Za-z0-9_]*)\s*\(", text))
    called |= set(re.findall(r"::(cpk_[A-Za-z0-9_]*)", text))
    missing = sorted(c for c in called if c not in defined)
    if missing:
        raise SystemExit(f"{path}: calls undefined functions {missing}")
    if "@@" in text:
        raise SystemExit(f"{path}: template marker left in")


def generate():
    out = {}
    gsc = (ROOT / "gsc/maps/cyberkino.gsc.in").read_text().replace("//@@TABLES@@", gsc_tables())
    check_script("maps/cyberkino.gsc", gsc)
    out["gsc/maps/cyberkino.gsc"] = gsc
    csc = (ROOT / "gsc/clientscripts/cyberkino.csc.in").read_text().replace("//@@CLIENT_INCLUDES@@", csc_includes())
    check_script("clientscripts/cyberkino.csc", csc)
    out["gsc/clientscripts/cyberkino.csc"] = csc
    out["gsc/english/localizedstrings/cyberkino.str"] = str_file(strings())
    out["launcher/sheets_gen.go"] = go_tables()
    for rel, text in out.items():
        path = ROOT / rel
        path.parent.mkdir(parents=True, exist_ok=True)
        path.write_text(text, newline="")
        print(f"generated {rel}")


# ---------------------------------------------------------------- launcher tables

def go_string(s):
    return json.dumps(s)


def go_tables():
    weapons, models, cyber = sheet("weapons"), sheet("models"), sheet("cyberware")
    lines = ["// Code generated by tools/build.py from sheets/*.json. DO NOT EDIT.", "", "package main", "",
             f"const modVersion = {go_string(VERSION_FILE.read_text().strip())}", "", "var weaponRows = []weaponRow{"]
    for w in weapons:
        lines.append(
            f"\t{{ID: {go_string(w['id'])}, Name: {go_string(w['name'])}, Base: {go_string(w['bo_base'])}, BaseUp: {go_string(w['bo_base_upgraded'])}, "
            f"Meshes: []string{{{', '.join(go_string(p) for p in w['cp_meshes'])}}}, DamageMult: {w['damage_mult']}, Clip: {w['clip_size']}, MaxAmmo: {w['max_ammo']}, "
            f"FireTimeMult: {w['fire_time_mult']}, PapDamageMult: {w['pap_damage_mult']}, PapClip: {w['pap_clip_size']}, PapMaxAmmo: {w['pap_max_ammo']}, FitScale: {w['fit_scale']}}},")
    lines += ["}", "", "var modelRows = []modelRow{"]
    for m in models:
        lines.append(f"\t{{ID: {go_string(m['id'])}, Meshes: []string{{{', '.join(go_string(p) for p in m['cp_meshes'])}}}, Kind: {go_string(m['kind'])}, FitTo: {go_string(m['fit_to'])}, Scale: {m['scale']}}},")
    mantis = next(c for c in cyber if c["effect"] == "mantis")
    lines += ["}", "", f"var mantisRow = mantisSpec{{Model: {go_string(mantis['model'])}, Base: {go_string(mantis['params']['base'])}, MeleeDamage: {mantis['params']['melee_damage']}}}", "", "var hookRows = []hookRow{"]
    for h in sheet("hooks"):
        lines.append(f"\t{{ID: {go_string(h['id'])}, File: {go_string(h['file'])}, Anchor: {go_string(h['anchor'])}, Action: {go_string(h['action'])}, Text: {go_string(h['text'])}, Required: {str(h['required']).lower()}}},")
    lines += ["}", "", "var zoneRows = []zoneRow{"]
    for z in sheet("zones"):
        lines.append(f"\t{{ID: {go_string(z['id'])}, Dir: {go_string(z['dir'])}, Use: {go_string(z['use'])}, Required: {str(z['required']).lower()}}},")
    lines += ["}", ""]
    return "\n".join(lines)


# ---------------------------------------------------------------- launcher and release

def build_launcher(stage):
    env = dict(os.environ, GOOS="windows", GOARCH="amd64", CGO_ENABLED="0")
    out = stage / "cyberkino-launch.exe"
    subprocess.run(["go", "build", "-trimpath", "-ldflags", "-s -w", "-o", str(out), "."], cwd=ROOT / "launcher", env=env, check=True)
    print(f"built {out.relative_to(ROOT)}")


def download(tool, cache):
    cache.mkdir(parents=True, exist_ok=True)
    dest = cache / Path(tool["url"]).name
    if not dest.exists() or hashlib.sha256(dest.read_bytes()).hexdigest() != tool["sha256"]:
        print(f"downloading {tool['url']}")
        with urllib.request.urlopen(tool["url"]) as r, open(dest, "wb") as f:
            shutil.copyfileobj(r, f)
    digest = hashlib.sha256(dest.read_bytes()).hexdigest()
    if digest != tool["sha256"]:
        raise SystemExit(f"{tool['id']}: SHA-256 {digest} does not match the tools sheet")
    return dest


def release(stage, version):
    tools_dir = stage / "tools"
    for tool in sheet("tools"):
        archive = download(tool, BUILD / "dl")
        target = tools_dir / tool["bundle_dir"]
        if target.exists():
            shutil.rmtree(target)
        with zipfile.ZipFile(archive) as z:
            for info in z.infolist():
                name = info.filename.replace("\\", "/")
                if name.endswith("/") or ".." in name.split("/"):
                    continue
                # OAT's raw/ folder holds templates for other games; T5 needs only its own
                if tool["id"] == "oat" and name.startswith("raw/") and not name.startswith("raw/t5/"):
                    continue
                dest = target / name
                dest.parent.mkdir(parents=True, exist_ok=True)
                dest.write_bytes(z.read(info))
    zip_path = BUILD / f"CyberKino-{version}.zip"
    if zip_path.exists():
        zip_path.unlink()
    with zipfile.ZipFile(zip_path, "w", zipfile.ZIP_DEFLATED, compresslevel=9) as z:
        for path in sorted(stage.rglob("*")):
            if path.is_file():
                z.write(path, Path("CyberKino") / path.relative_to(stage))
    digest = hashlib.sha256(zip_path.read_bytes()).hexdigest()
    print(f"release {zip_path.relative_to(ROOT)}: {zip_path.stat().st_size} bytes, sha256 {digest}")


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("--release", action="store_true")
    args = ap.parse_args()
    if subprocess.run([sys.executable, str(ROOT / "tools/preflight.py")]).returncode != 0:
        raise SystemExit("preflight is not clean: fix the sheets first")
    generate()
    version = VERSION_FILE.read_text().strip()
    stage = BUILD / "stage"
    if stage.exists():
        shutil.rmtree(stage)
    stage.mkdir(parents=True)
    build_launcher(stage)
    for rel in ("gsc/maps/cyberkino.gsc", "gsc/clientscripts/cyberkino.csc", "gsc/english/localizedstrings/cyberkino.str"):
        dest = stage / rel
        dest.parent.mkdir(parents=True, exist_ok=True)
        shutil.copy(ROOT / rel, dest)
    for doc in ("README.md", "CREDITS.md", "LICENSE"):
        shutil.copy(ROOT / doc, stage / doc)
    shutil.copytree(ROOT / "licenses", stage / "licenses")
    if args.release:
        release(stage, version)


if __name__ == "__main__":
    main()

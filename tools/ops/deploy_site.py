#!/usr/bin/env python3
"""Build and deploy www.crispyanarchy.net (Cloudflare Pages project crispy-map) in one go.

    python3 tools/ops/deploy_site.py

Builds marketing/site, hashes it (marketing/bluemap/hashes.js, needs `npm install blake3-wasm@2.1.5` in WORK),
merges the BlueMap hashes (marketing/bluemap/map_manifest.json, served under /map/), uploads only the files Cloudflare
doesn't have yet, creates the deployment and pings IndexNow. The asset upload runs on the AMP host (gx.py), because
this session's proxy replaces the Authorization header the upload JWT needs; the upload token is written there to a
root-only file and deleted afterwards, and is never printed.
"""
import base64, gzip, json, os, shutil, subprocess, sys, tempfile, urllib.request

ROOT = os.path.abspath(os.path.join(os.path.dirname(__file__), "..", ".."))
ACCOUNT, PROJECT = "334f2a46b6012a7b2b44a77a4881d06f", "crispy-map"
WORK = os.environ.get("DEPLOY_WORK", os.path.join(tempfile.gettempdir(), "crispy_site_deploy"))
CF = "https://api.cloudflare.com/client/v4"
GX = [sys.executable, os.path.join(ROOT, "tools", "ops", "gx.py")]
CHUNK = 16000   # the Proxmox API refuses a request much over ~64 KB


def gx(script, timeout=120):
    with tempfile.NamedTemporaryFile("w", suffix=".sh", delete=False) as f:
        f.write(script)
    try:
        return subprocess.run(GX + [f.name, str(timeout)], capture_output=True, text=True, timeout=timeout + 30).stdout
    finally:
        os.unlink(f.name)


def cf(path, method="GET", **kw):   # session-side Cloudflare API (the proxy adds the account token)
    cmd = ["curl", "-sS", "-X", method, CF + path, "-H", "Authorization: Bearer dummy"]
    for k, v in kw.get("form", {}).items():
        cmd += ["-F", f"{k}={v}"]
    return json.loads(subprocess.run(cmd, capture_output=True, text=True, check=True).stdout)


def main():
    out = os.path.join(WORK, "out")
    shutil.rmtree(out, ignore_errors=True)
    subprocess.run([sys.executable, os.path.join(ROOT, "marketing", "site", "build.py"), out], check=True)
    headers = os.path.join(WORK, "headers.txt")
    shutil.move(os.path.join(out, "_headers"), headers)
    redirects = os.path.join(WORK, "redirects.txt")   # _headers and _redirects go with the deployment, not as assets
    shutil.move(os.path.join(out, "_redirects"), redirects)
    if not os.path.isdir(os.path.join(WORK, "node_modules", "blake3-wasm")):
        subprocess.run(["npm", "install", "--silent", "--prefix", WORK, "blake3-wasm@2.1.5"], check=True)
    sm, tsv = os.path.join(WORK, "site_manifest.json"), os.path.join(WORK, "site_upload.tsv")
    subprocess.run(["node", os.path.join(ROOT, "marketing", "bluemap", "hashes.js"), out, sm, tsv], check=True,
                   env={**os.environ, "NODE_PATH": os.path.join(WORK, "node_modules")})
    manifest = json.load(open(sm))
    manifest.update({"/map" + k: v for k, v in json.load(open(os.path.join(ROOT, "marketing", "bluemap", "map_manifest.json"))).items()})
    mpath = os.path.join(WORK, "manifest.json")
    json.dump(manifest, open(mpath, "w"))
    rows = [l.rstrip("\n").split("\t") for l in open(tsv) if l.strip()]
    hashes = [r[0] for r in rows]

    jwt = cf(f"/accounts/{ACCOUNT}/pages/projects/{PROJECT}/upload-token")["result"]["jwt"]
    py_post = '''python3 -I - <<'PY'
import json, sys, urllib.request
jwt = open('/root/.cfjwt').read().strip()
def post(p, b):
    r = urllib.request.Request("https://api.cloudflare.com/client/v4" + p, json.dumps(b).encode(), {"Content-Type": "application/json", "Authorization": "Bearer " + jwt})
    return json.load(urllib.request.urlopen(r, timeout=120))
%s
PY'''
    res = gx(f"umask 077; printf '%s' '{jwt}' > /root/.cfjwt\n" + py_post %
             f'print("MISSING", json.dumps(post("/pages/assets/check-missing", {{"hashes": {json.dumps(hashes)}}})["result"]))')
    missing = set(json.loads(res.split("MISSING", 1)[1].splitlines()[0]))
    upload, seen = [], set()
    for h, rel, ct in rows:
        if h in missing and h not in seen:
            seen.add(h)
            upload.append({"key": h, "value": base64.b64encode(open(out + rel, "rb").read()).decode(), "metadata": {"contentType": ct}, "base64": True})
            print("  upload", rel)
    blob = base64.b64encode(gzip.compress(json.dumps({"upload": upload, "hashes": hashes}).encode())).decode()
    for i in range(0, len(blob), CHUNK):
        gx(("umask 077; : > /root/cfpay.b64\n" if i == 0 else "") + f"printf '%s' '{blob[i:i + CHUNK]}' >> /root/cfpay.b64\n", 50)
    print(gx("base64 -d /root/cfpay.b64 | gunzip > /root/cfpay.json\n" + py_post % '''d = json.load(open('/root/cfpay.json'))
if d["upload"]: print("upload:", post("/pages/assets/upload", d["upload"]).get("success"), len(d["upload"]), "files")
print("upsert:", post("/pages/assets/upsert-hashes", {"hashes": d["hashes"]}).get("success"))''' +
             "\nrm -f /root/.cfjwt /root/cfpay.json /root/cfpay.b64\n").strip())

    d = cf(f"/accounts/{ACCOUNT}/pages/projects/{PROJECT}/deployments", "POST",
           form={"manifest": "<" + mpath, "_headers": "@" + headers + ";filename=_headers",
                 "_redirects": "@" + redirects + ";filename=_redirects", "branch": "main"})
    print("deployment:", d.get("success"), d.get("errors"), (d.get("result") or {}).get("url"))


if __name__ == "__main__":
    main()

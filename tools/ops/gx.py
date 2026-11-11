#!/usr/bin/env python3
"""gx.py <script.sh> [timeout_s]   run a bash script on VM 111 (AMP host) via the Proxmox guest agent.
Proxmox at PVE_HOST (default https://lblsmtnguw.loclx.io), token from PVE_TOKEN_ID / PVE_SECRET (never printed)."""
import base64, json, os, sys, time, urllib.parse, urllib.request
BASE = os.environ.get("PVE_HOST", "https://lblsmtnguw.loclx.io").rstrip("/") + "/api2/json"
AUTH = {"Authorization": f"PVEAPIToken={os.environ['PVE_TOKEN_ID']}={os.environ['PVE_SECRET']}"}
VMID = os.environ.get("PVE_VMID", "111")
def api(method, path, data=None):
    body = urllib.parse.urlencode(data, doseq=True).encode() if data else None
    r = urllib.request.Request(BASE + path, body, AUTH, method=method)
    return json.load(urllib.request.urlopen(r, timeout=60))["data"]
node = next(n["node"] for n in api("GET", "/nodes") if any(str(v["vmid"]) == VMID for v in api("GET", f"/nodes/{n['node']}/qemu")))
script = open(sys.argv[1]).read()
b64 = base64.b64encode(script.encode()).decode()
pid = api("POST", f"/nodes/{node}/qemu/{VMID}/agent/exec", {"command": ["bash", "-c", f"echo {b64} | base64 -d | bash"]})["pid"]
deadline = time.time() + int(sys.argv[2] if len(sys.argv) > 2 else 110)
while time.time() < deadline:
    s = api("GET", f"/nodes/{node}/qemu/{VMID}/agent/exec-status?pid={pid}")
    if s.get("exited"):
        sys.stdout.write(s.get("out-data", "")); sys.stderr.write(s.get("err-data", ""))
        print(f"[exit] {s.get('exitcode')}"); sys.exit(0)
    time.sleep(1.5)
print(f"[still running, pid {pid}]")

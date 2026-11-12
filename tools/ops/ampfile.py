#!/usr/bin/env python3
"""ampfile.py put <Instance> <remote path> <local file>   upload (paths relative to the instance's Minecraft folder)
   ampfile.py get <Instance> <remote path> <local file>   download
   ampfile.py unzip <Instance> <remote zip> <remote dir>  extract an uploaded zip on the server
Credentials from AMP_URL / AMP_USER / AMP_PASS (AMP_URL may lack a scheme)."""
import base64, json, os, sys, urllib.request
A = os.environ["AMP_URL"].rstrip("/")
if "://" not in A: A = "https://" + A
H = {"Content-Type": "application/json", "Accept": "application/json"}
def call(path, body):
    r = urllib.request.Request(A + path, json.dumps(body).encode(), H)
    d = json.load(urllib.request.urlopen(r, timeout=300))
    return d if (isinstance(d, dict) and "sessionID" in d) else (d.get("result", d) if isinstance(d, dict) and "result" in d else d)
CRED = {"username": os.environ["AMP_USER"], "password": os.environ["AMP_PASS"], "token": "", "rememberMe": False}
def session(name):
    sid = call("/API/Core/Login", CRED)["sessionID"]
    insts = call("/API/ADSModule/GetInstances", {"SESSIONID": sid})
    iid = [i["InstanceID"] for t in insts for i in t["AvailableInstances"] if i["InstanceName"] == name][0]
    base = f"/API/ADSModule/Servers/{iid}/API/"
    return base, call(base + "Core/Login", CRED)["sessionID"]
def main():
    op, name, remote, local = sys.argv[1:5]
    base, sid = session(name)
    if op == "put":
        # AMP keeps an upload lock on a file name for a while after a write, so upload under a fresh temporary name
        # and rename it into place
        final_name, remote = remote, remote + ".up" + os.urandom(4).hex()
        data = open(local, "rb").read(); step = 512 * 1024; off = 0
        while True:
            chunk = data[off:off + step]; final = off + step >= len(data)
            r = call(base + "FileManagerPlugin/WriteFileChunk", {"SESSIONID": sid, "Filename": remote,
                     "Data": base64.b64encode(chunk).decode(), "Offset": off, "FinalChunk": final})
            if isinstance(r, dict) and r.get("Status") is False: sys.exit(f"write failed: {r.get('Reason')}")
            off += len(chunk)
            if final: break
        call(base + "FileManagerPlugin/ReleaseFileUploadLock", {"SESSIONID": sid, "Filename": remote})
        call(base + "FileManagerPlugin/TrashFile", {"SESSIONID": sid, "Filename": final_name})
        r = call(base + "FileManagerPlugin/RenameFile", {"SESSIONID": sid, "Filename": remote, "NewFilename": os.path.basename(final_name)})
        if isinstance(r, dict) and r.get("Status") is False: sys.exit(f"rename failed: {r.get('Reason')} (data is in {remote})")
        remote = final_name
        print(f"uploaded {len(data)} bytes to {name}:{remote}")
    elif op == "get":
        out = bytearray(); off = 0; step = 1024 * 1024
        while True:
            r = call(base + "FileManagerPlugin/ReadFileChunk", {"SESSIONID": sid, "Filename": remote, "Offset": off, "ChunkSize": step})
            b = base64.b64decode((r.get("Result") or r.get("Base64Data") or "") if isinstance(r, dict) else (r or ""))
            out += b; off += len(b)
            if len(b) < step: break
        open(local, "wb").write(out); print(f"got {len(out)} bytes")
    elif op == "unzip":
        print(call(base + "FileManagerPlugin/ExtractArchive", {"SESSIONID": sid, "ArchivePath": remote, "DestinationPath": local}))
main()

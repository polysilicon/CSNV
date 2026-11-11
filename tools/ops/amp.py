#!/usr/bin/env python3
"""amp.py <Module/Method> [json]        call the ADS controller
   amp.py @<Instance> <Module/Method> [json]   call an instance (credentials from AMP_URL/AMP_USER/AMP_PASS)"""
import json, os, sys, urllib.request
A = os.environ["AMP_URL"].rstrip("/")
if "://" not in A: A = os.environ.get("AMP_SCHEME", "https") + "://" + A
H = {"Content-Type": "application/json", "Accept": "application/json"}
def call(path, body):
    r = urllib.request.Request(A + path, json.dumps(body).encode(), H)
    return json.load(urllib.request.urlopen(r, timeout=120))
cred = {"username": os.environ["AMP_USER"], "password": os.environ["AMP_PASS"], "token": "", "rememberMe": False}
sid = call("/API/Core/Login", cred)["sessionID"]
args = sys.argv[1:]
if args[0].startswith("@"):
    name = args.pop(0)[1:]
    insts = call("/API/ADSModule/GetInstances", {"SESSIONID": sid}); insts = insts.get("result", insts) if isinstance(insts, dict) else insts
    iid = [i["InstanceID"] for t in insts for i in t["AvailableInstances"] if i["InstanceName"] == name][0]
    base = f"/API/ADSModule/Servers/{iid}/API/"
    sid = call(base + "Core/Login", cred)["sessionID"]
else:
    base = "/API/"
body = json.loads(args[1]) if len(args) > 1 else {}
body["SESSIONID"] = sid
print(json.dumps(call(base + args[0], body), indent=1))

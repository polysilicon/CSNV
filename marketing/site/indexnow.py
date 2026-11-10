#!/usr/bin/env python3
"""Tell IndexNow search engines (Bing, Yandex, Seznam, Naver; Bing shares with ChatGPT/Copilot search) that pages changed.

    python3 indexnow.py              # every URL in the live sitemap
    python3 indexnow.py /news/x/ ... # just these paths

Run after each deploy. The key file /<key>.txt is published by build.py.
"""
import json, os, re, sys, urllib.request
SITE = "https://www.crispyanarchy.net"
UA = {"User-Agent": "crispy-indexnow/1.0"}
key = open(os.path.join(os.path.dirname(os.path.abspath(__file__)), "indexnow_key.txt")).read().strip()
if len(sys.argv) > 1:
    urls = [SITE + p for p in sys.argv[1:]]
else:
    urls = re.findall(r"<loc>([^<]+)</loc>", urllib.request.urlopen(urllib.request.Request(SITE + "/sitemap.xml", headers=UA), timeout=30).read().decode())
body = json.dumps({"host": "www.crispyanarchy.net", "key": key, "keyLocation": f"{SITE}/{key}.txt", "urlList": urls}).encode()
req = urllib.request.Request("https://api.indexnow.org/indexnow", body, {"Content-Type": "application/json; charset=utf-8", **UA})
try:
    with urllib.request.urlopen(req, timeout=30) as r:
        print(r.status, "submitted", len(urls), "URLs")
except urllib.error.HTTPError as e:
    print(e.code, e.read().decode()[:300])

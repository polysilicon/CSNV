"""Create the trader's own Solana wallet, on the server, readable only by the crispytrader user.

    sudo -u crispytrader /opt/crispytrader/venv/bin/python /opt/crispytrader/wallet.py

Writes /etc/crispytrader/wallet.json (Solana CLI format, mode 600) unless it exists, and prints ONLY the public
address: send SOL there to fund it. The private key never leaves this file; back it up offline yourself if you want to.
`wallet.py balance` shows the address and its SOL balance.
"""
import json, os, sys, urllib.request
from solders.keypair import Keypair

PATH = os.environ.get("TRADER_WALLET", "/etc/crispytrader/wallet.json")
if len(sys.argv) > 1 and sys.argv[1] == "balance":
    kp = Keypair.from_bytes(bytes(json.load(open(PATH))))
    req = urllib.request.Request(os.environ.get("TRADER_RPC", "https://api.mainnet-beta.solana.com"), method="POST",
                                 data=json.dumps({"jsonrpc": "2.0", "id": 1, "method": "getBalance", "params": [str(kp.pubkey())]}).encode(),
                                 headers={"Content-Type": "application/json"})
    print(kp.pubkey(), json.load(urllib.request.urlopen(req, timeout=15))["result"]["value"] / 1e9, "SOL")
    sys.exit()
if os.path.exists(PATH):
    print("A wallet already exists:", Keypair.from_bytes(bytes(json.load(open(PATH)))).pubkey()); sys.exit()
os.makedirs(os.path.dirname(PATH), mode=0o700, exist_ok=True)
kp = Keypair()
fd = os.open(PATH, os.O_WRONLY | os.O_CREAT | os.O_EXCL, 0o600)
with os.fdopen(fd, "w") as f: json.dump(list(bytes(kp)), f)
print("New trader wallet:", kp.pubkey())

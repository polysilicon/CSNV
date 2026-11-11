# Ops helpers (no secrets in here: everything comes from the session environment)

- `gx.py <script.sh> [timeout]`: runs a bash script as root on VM 111 (the AMP host) through the Proxmox guest
  agent. Needs `PVE_TOKEN_ID`, `PVE_SECRET`; Proxmox address `PVE_HOST` (default the LocalXpose tunnel
  `https://lblsmtnguw.loclx.io`). The Proxmox API rejects a request much over ~64 KB, so send bigger data in chunks.
- `amp.py [@Instance] <Module/Method> [json]`: AMP API (ADS controller, or one instance with `@Name`). Needs
  `AMP_USER`, `AMP_PASS`, `AMP_URL` (set `AMP_URL=https://gkausz1wax.loclx.io` when the configured address is down).

Website deploy (Cloudflare Pages Direct Upload, see `marketing/site/README.md`): the session's proxy rewrites the
Authorization header for api.cloudflare.com, so `/pages/assets/*` calls (which use the project's upload JWT) run on
the AMP host via `gx.py`; the deployment itself (`/deployments`, normal API token) runs from the session. The BlueMap
part of the manifest can be rebuilt without the host: list `/AMPStorage/bluemap/deploy`, download each file from
`https://crispy-map.pages.dev/map/<path>` (`index.html` from `/map/`) and hash with `marketing/bluemap/hashes.js`.

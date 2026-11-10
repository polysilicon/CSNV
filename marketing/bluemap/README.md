# 3D spawn map (BlueMap → Cloudflare Pages)

Live: https://crispy-map.pages.dev (Cloudflare Pages project `crispy-map`). Planned custom domain: map.crispyanarchy.net.

## Render (on the AMP host, VM111)
- BlueMap CLI 5.29 in `/AMPStorage/bluemap` (`bluemap-5.29-cli.jar`, run with Java 25).
- `config/core.conf`: `accept-download: true`, 2 render threads.
- `maps/overworld.conf`: CrispyAnarchy01 world, start-pos 287,-207, render-mask box x -737..1311, z -1231..817 (±1 km around spawn).
  Nether/End maps disabled. `webapp.conf`: `client-decompression: true`.
- Output in `web/` (~4,350 files, ~411 MB). The deploy copy leaves out `sql.php` and `live/` (static hosting only).

## Deploy (Cloudflare Pages Direct Upload)
1. `node hashes.js <deploy dir> manifest.json upload_list.tsv` (needs `blake3-wasm`): hash = blake3(base64(content) + ext), first 32 hex chars.
2. Get an upload JWT from `GET /accounts/<id>/pages/projects/crispy-map/upload-token`.
3. `POST /pages/assets/check-missing` with the hashes, upload the missing ones to `/pages/assets/upload` (base64, batched), then `/pages/assets/upsert-hashes`.
   Uploads use the JWT as the Bearer token, so they were run from the host (this session's proxy replaces the Authorization header for api.cloudflare.com).
4. `POST /accounts/<id>/pages/projects/crispy-map/deployments` with `manifest` (form field, JSON) using the normal API token.

Re-render + redeploy only uploads changed tiles; unchanged hashes are skipped by check-missing.

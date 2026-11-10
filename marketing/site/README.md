# www.crispyanarchy.net

Static site on Cloudflare Pages (project `crispy-map`, custom domain `www.crispyanarchy.net`; the BlueMap 3D map is
deployed with it under `/map/`, see `marketing/bluemap/README.md`). The bare `crispyanarchy.net` must keep pointing
at the Minecraft server, so the site lives on `www`.

- `build.py <out>`: writes every page, `sitemap.xml`, `robots.txt` (AI crawlers allowed), `llms.txt`, `_headers`
  (noindex on `*.pages.dev` and `/map/`) and the IndexNow key file.
- `news.py`: the news posts, newest first. **To post news:** add an entry at the top (slug, date, title, summary,
  body HTML), rebuild, deploy, then `python3 indexnow.py /news/ /news/<slug>/ /`.
- `indexnow.py`: pings IndexNow (Bing, Yandex, ...; Bing feeds ChatGPT/Copilot search). No arguments = whole sitemap.
- `logo.py`: draws the pixel flame (`images/mark.svg`, `icon-64.png`, `icon-512.png`).
- Claims on the site follow `marketing/listings.md`: no player counts, no "biggest/best", no franchise names, never
  publish Black Market spots.

Deploy (Direct Upload): hash the built files (`marketing/bluemap/hashes.js`), merge with the BlueMap manifest under
`/map/`, upload missing assets with the project's upload JWT, then create the deployment with the manifest and
`_headers` as form fields. Only changed files are uploaded.

const fs = require('fs'), path = require('path'), { hash } = require('blake3-wasm');
const root = process.argv[2];
const types = { html: 'text/html', js: 'application/javascript', mjs: 'application/javascript', css: 'text/css', json: 'application/json', png: 'image/png',
  jpg: 'image/jpeg', svg: 'image/svg+xml', webp: 'image/webp', woff: 'font/woff', woff2: 'font/woff2', ttf: 'font/ttf', gz: 'application/gzip', ico: 'image/x-icon',
  txt: 'text/plain', wasm: 'application/wasm', prbm: 'application/octet-stream' };
const manifest = {}, rows = [];
(function walk(d) {
  for (const n of fs.readdirSync(d)) {
    const p = path.join(d, n), st = fs.statSync(p);
    if (st.isDirectory()) { walk(p); continue; }
    const ext = path.extname(p).substring(1);
    const h = hash(fs.readFileSync(p).toString('base64') + ext).toString('hex').slice(0, 32);
    const rel = '/' + path.relative(root, p).split(path.sep).join('/');
    manifest[rel] = h; rows.push([h, rel, types[ext.toLowerCase()] || 'application/octet-stream'].join('\t'));
  }
})(root);
fs.writeFileSync(process.argv[3], JSON.stringify(manifest));
fs.writeFileSync(process.argv[4], rows.join('\n') + '\n');
console.log('files', rows.length, 'unique hashes', new Set(Object.values(manifest)).size);

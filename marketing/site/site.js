// Copy buttons, mobile menu, and the live server status (from the public mcsrvstat.us API).
document.querySelectorAll('.copy').forEach(b => b.addEventListener('click', () => {
  const t = b.dataset.copy, done = () => { b.textContent = 'Copied'; setTimeout(() => b.textContent = 'Copy', 1500); };
  if (navigator.clipboard) navigator.clipboard.writeText(t).then(done, () => {}); 
}));
const mb = document.querySelector('.menu-btn'), nav = document.getElementById('nav');
if (mb) mb.addEventListener('click', () => { const o = nav.classList.toggle('open'); mb.setAttribute('aria-expanded', o); });
const st = document.querySelectorAll('[data-status]');
if (st.length) fetch('https://api.mcsrvstat.us/3/crispyanarchy.net').then(r => r.json()).then(d => {
  st.forEach(s => {
    s.classList.add(d.online ? 'up' : 'down');
    s.querySelector('.txt').textContent = d.online
      ? 'Server is online now' : 'Offline right now. Check Discord for news.';
  });
}).catch(() => st.forEach(s => s.hidden = true));

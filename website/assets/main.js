// ── The app's address: every "Start free" button points here ──
const APP_URL = "https://app.momentum.alakhveer.com";

const STAGES = [
  { id: 'new', name: 'New', color: 'var(--st1)' },
  { id: 'contacted', name: 'Contacted', color: 'var(--st2)' },
  { id: 'qualified', name: 'Qualified', color: 'var(--st3)' },
  { id: 'negotiating', name: 'Negotiating', color: 'var(--st4)' },
  { id: 'won', name: 'Won', color: 'var(--st5)' },
  { id: 'lost', name: 'Lost', color: 'var(--st6)' },
];
// Example leads per board; [name, company, value in ₹, score, stage]
const BOARDS = {
  hero: [
    ['Kavya Rao', 'Rao Interiors', 35000, 42, 'new'], ['Sameer Khan', 'Website form', 12000, 30, 'new'],
    ['Rakesh Gupta', 'Gupta Hardware', 60000, 55, 'contacted'],
    ['Meera Shah', 'Shah Traders', 48000, 68, 'qualified'], ['Neha Joshi', 'Bloom Florist', 22000, 64, 'qualified'],
    ['Priya Nair', 'Nair Textiles', 90000, 81, 'negotiating'],
    ['Arjun Mehta', 'Mehta Motors', 120000, 94, 'won'],
    ['Dev Patel', 'Walk-in', 8000, 18, 'lost'],
  ],
};

const inr = n => '₹' + n.toLocaleString('en-IN');
const short = n => n >= 100000 ? '₹' + (n / 100000).toFixed(n % 100000 ? 1 : 0) + 'L' : n >= 1000 ? '₹' + Math.round(n / 1000) + 'k' : inr(n);
const esc = s => String(s).replace(/[&<>"]/g, c => ({ '&': '&amp;', '<': '&lt;', '>': '&gt;', '"': '&quot;' })[c]);
const reduce = matchMedia('(prefers-reduced-motion: reduce)').matches;

(() => {
  document.documentElement.classList.remove('no-js');
  document.querySelectorAll('[data-app]').forEach(a => { a.href = APP_URL; });

  // theme (shared key with alakhveer.com)
  const root = document.documentElement, tb = document.getElementById('themeBtn');
  const syncTheme = () => tb.setAttribute('aria-label', root.dataset.theme === 'light' ? 'Switch to dark theme' : 'Switch to light theme');
  syncTheme();
  tb.addEventListener('click', () => {
    root.dataset.theme = root.dataset.theme === 'light' ? 'dark' : 'light';
    try { localStorage.setItem('theme', root.dataset.theme); } catch (e) {}
    syncTheme();
  });

  const nav = document.getElementById('nav');
  const onScroll = () => nav.classList.toggle('scrolled', scrollY > 20);
  addEventListener('scroll', onScroll, { passive: true }); onScroll();

  // ── pipeline boards ──
  const live = document.createElement('div');
  live.className = 'sr'; live.setAttribute('aria-live', 'polite'); document.body.append(live);

  document.querySelectorAll('[data-board]').forEach(board => {
    const key = board.dataset.board;
    board.innerHTML = STAGES.map(s => `<div class="col" data-stage="${s.id}">
      <div class="col-h"><span class="d" style="background:${s.color}"></span>${s.name} <span class="n"></span></div>
      <div class="col-v"></div><div class="drop"></div></div>`).join('');
    BOARDS[key].forEach(([name, co, val, score, st]) => {
      const c = document.createElement('div');
      c.className = 'lc'; c.tabIndex = 0; c.dataset.value = val;
      c.innerHTML = `<b>${esc(name)}</b><small>${esc(co)}</small><div class="m"><span>${inr(val)}</span><span class="score" title="Lead score">${score}</span></div>`;
      board.querySelector(`[data-stage="${st}"] .drop`).append(c);
    });
    const totals = () => {
      let open = 0;
      board.querySelectorAll('.col').forEach(col => {
        const cards = [...col.querySelectorAll('.lc')];
        const sum = cards.reduce((t, c) => t + +c.dataset.value, 0);
        col.querySelector('.n').textContent = `(${cards.length})`;
        col.querySelector('.col-v').textContent = inr(sum);
        if (!['won', 'lost'].includes(col.dataset.stage)) open += sum;
      });
      if (key === 'hero') document.getElementById('hero-total').textContent = `${short(open)} open pipeline`;
    };
    totals();

    const place = (card, col, before) => {
      const drop = col.querySelector('.drop');
      before ? drop.insertBefore(card, before) : drop.append(card);
      card.classList.remove('landed'); void card.offsetWidth; card.classList.add('landed');
      totals();
      const st = STAGES.find(s => s.id === col.dataset.stage).name;
      live.textContent = `${card.querySelector('b').textContent} moved to ${st}. ${col.querySelector('.col-v').textContent} in ${st}.`;
    };

    // keyboard: arrows move a focused card between stages
    board.addEventListener('keydown', e => {
      const card = e.target.closest('.lc');
      if (!card || !['ArrowLeft', 'ArrowRight'].includes(e.key)) return;
      e.preventDefault();
      const cols = [...board.querySelectorAll('.col')];
      const i = cols.indexOf(card.closest('.col')) + (e.key === 'ArrowRight' ? 1 : -1);
      if (i < 0 || i >= cols.length) return;
      place(card, cols[i]); card.focus();
      cols[i].scrollIntoView({ block: 'nearest', inline: 'nearest', behavior: reduce ? 'auto' : 'smooth' });
    });

    // pointer drag (mouse + touch): a floating clone follows the pointer
    let drag = null;
    board.addEventListener('pointerdown', e => {
      const card = e.target.closest('.lc');
      if (!card || e.button > 0) return;
      const r = card.getBoundingClientRect();
      drag = { card, dx: e.clientX - r.left, dy: e.clientY - r.top, x0: e.clientX, y0: e.clientY, moved: false, w: r.width };
      card.setPointerCapture(e.pointerId);
    });
    board.addEventListener('pointermove', e => {
      if (!drag) return;
      if (!drag.moved) {
        if (Math.hypot(e.clientX - drag.x0, e.clientY - drag.y0) < 5) return;
        drag.moved = true;
        drag.float = drag.card.cloneNode(true);
        Object.assign(drag.float.style, { position: 'fixed', left: 0, top: 0, width: drag.w + 'px', pointerEvents: 'none', margin: 0 });
        drag.float.classList.add('dragging'); drag.float.removeAttribute('tabindex');
        document.body.append(drag.float);
        drag.card.classList.add('ghost');
      }
      drag.float.style.translate = `${e.clientX - drag.dx}px ${e.clientY - drag.dy}px`;
      const col = document.elementsFromPoint(e.clientX, e.clientY).map(el => el.closest('.col')).find(c => c && board.contains(c));
      board.querySelectorAll('.col.over').forEach(c => c !== col && c.classList.remove('over'));
      if (col) col.classList.add('over');
      drag.col = col;
      // auto-scroll the board near its edges (narrow screens)
      const br = board.getBoundingClientRect();
      if (e.clientX > br.right - 40) board.scrollLeft += 12; else if (e.clientX < br.left + 40) board.scrollLeft -= 12;
    });
    const end = () => {
      if (!drag) return;
      if (drag.moved) {
        drag.float.remove(); drag.card.classList.remove('ghost');
        board.querySelectorAll('.col.over').forEach(c => c.classList.remove('over'));
        if (drag.col && drag.col !== drag.card.closest('.col')) place(drag.card, drag.col);
      }
      drag = null;
    };
    board.addEventListener('pointerup', end);
    board.addEventListener('pointercancel', end);
  });

  // ── reveal on scroll ──
  const io = new IntersectionObserver(es => es.forEach(en => {
    if (!en.isIntersecting) return;
    en.target.classList.add('in'); io.unobserve(en.target);
  }), { threshold: 0.15, rootMargin: '0px 0px -40px 0px' });
  document.querySelectorAll('.rv').forEach(el => io.observe(el));

  // ── feature tabs ──
  const tabs = [...document.querySelectorAll('[role=tab]')];
  const pick = (t, focus) => {
    tabs.forEach(x => {
      const on = x === t;
      x.setAttribute('aria-selected', on); x.tabIndex = on ? 0 : -1;
      document.getElementById(x.getAttribute('aria-controls')).hidden = !on;
    });
    if (focus) t.focus();
    t.scrollIntoView({ block: 'nearest', inline: 'nearest', behavior: reduce ? 'auto' : 'smooth' });
    if (t.id === 't-score') scoreUp();
  };
  tabs.forEach((t, i) => {
    t.addEventListener('click', () => pick(t));
    t.addEventListener('keydown', e => {
      const d = { ArrowDown: 1, ArrowRight: 1, ArrowUp: -1, ArrowLeft: -1 }[e.key];
      if (d) { e.preventDefault(); pick(tabs[(i + d + tabs.length) % tabs.length], true); }
    });
  });
  function scoreUp() {
    const ring = document.getElementById('ring'), num = document.getElementById('ringNum'), target = 86;
    ring.style.setProperty('--v', 0); void ring.offsetWidth;
    requestAnimationFrame(() => ring.style.setProperty('--v', target));
    if (reduce) { num.textContent = target; return; }
    const t0 = performance.now();
    const tick = t => { const p = Math.min(1, (t - t0) / 1400); num.textContent = Math.round(target * (1 - Math.pow(1 - p, 3))); if (p < 1) requestAnimationFrame(tick); };
    requestAnimationFrame(tick);
  }
  document.querySelectorAll('.tasks input').forEach(cb => cb.addEventListener('change', () => cb.closest('li').classList.toggle('done', cb.checked)));

  // email placeholder fills in with a real name, then resets, on a loop
  const phs = document.querySelectorAll('.mail-ill .ph');
  phs.forEach(p => { p.dataset.raw = p.textContent; });
  if (!reduce) {
    let on = false;
    setInterval(() => { on = !on; phs.forEach(p => { p.textContent = on ? p.dataset.ph : p.dataset.raw; p.classList.toggle('on', on); }); }, 2600);
  }
})();

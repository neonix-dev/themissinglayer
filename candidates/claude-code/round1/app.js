/* The Missing Layer — the bench.
   Everything lives in localStorage under one key. No network calls, no dependencies. */
(() => {
  'use strict';

  const KEY = 'themissinglayer.v1';
  const VERDICTS = {
    cold:   { label: 'Made it cold',   hint: 'Blank page to finished. Nothing looked up.' },
    looked: { label: 'Had to look',    hint: 'Got there, but with a reference open.' },
    notyet: { label: 'Not yet',        hint: 'Could not make it. That is information.' },
  };
  const SUGGESTED = ['Guitar', 'Code', 'Woodworking', 'Drawing', 'Writing', 'Electronics', 'Cooking', 'Mathematics'];
  const DEFAULT_RULES = [
    'Blank page. Nothing open to copy from.',
    'If I look, I say so.',
    'A rep counts on the day it happens.',
  ];

  const fresh = () => ({ v: 1, domains: [], pieces: [], reps: [], rules: [...DEFAULT_RULES], hold: 3, active: null, sample: false });

  // ---------- storage ----------
  let storageOK = true;
  function load() {
    try {
      const raw = localStorage.getItem(KEY);
      if (!raw) return fresh();
      const s = JSON.parse(raw);
      return valid(s) ? { ...fresh(), ...s } : fresh();
    } catch { storageOK = false; return fresh(); }
  }
  function save() {
    try { localStorage.setItem(KEY, JSON.stringify(state)); storageOK = true; }
    catch { storageOK = false; }
  }
  function valid(s) {
    return s && s.v === 1 && Array.isArray(s.domains) && Array.isArray(s.pieces) && Array.isArray(s.reps);
  }

  let state = load();
  let armed = null;       // id of a destructive button waiting for its second click
  let draft = { verdict: null, gap: '' };
  let flash = '';
  let tick = null;

  // ---------- helpers ----------
  const $ = (sel, el = document) => el.querySelector(sel);
  const main = $('#main');
  const esc = (s) => String(s).replace(/[&<>"']/g, (c) => ({ '&': '&amp;', '<': '&lt;', '>': '&gt;', '"': '&quot;', "'": '&#39;' }[c]));
  const uid = () => (crypto.randomUUID ? crypto.randomUUID() : Date.now().toString(36) + Math.random().toString(36).slice(2));
  const pad = (n) => String(n).padStart(2, '0');
  const dayKey = (t) => { const d = new Date(t); return `${d.getFullYear()}-${pad(d.getMonth() + 1)}-${pad(d.getDate())}`; };
  const clock = (sec) => { const h = Math.floor(sec / 3600), m = Math.floor((sec % 3600) / 60), s = sec % 60; return (h ? h + ':' + pad(m) : m) + ':' + pad(s); };
  const plural = (n, w) => `${n} ${w}${n === 1 ? '' : 's'}`;
  const startOfDay = (t) => { const d = new Date(t); d.setHours(0, 0, 0, 0); return d.getTime(); };
  function ago(t) {
    const days = Math.round((startOfDay(Date.now()) - startOfDay(t)) / 864e5);
    if (days <= 0) return 'today';
    if (days === 1) return 'yesterday';
    if (days < 14) return `${days} days ago`;
    return new Date(t).toLocaleDateString(undefined, { month: 'short', day: 'numeric' });
  }
  const longDay = (t) => new Date(t).toLocaleDateString(undefined, { weekday: 'long', month: 'long', day: 'numeric' });
  const repsOf = (pieceId) => state.reps.filter((r) => r.pieceId === pieceId).sort((a, b) => a.at - b.at);
  const piecesOf = (domainId) => state.pieces.filter((p) => p.domainId === domainId);
  const isHeld = (reps) => reps.length >= state.hold && reps.slice(-state.hold).every((r) => r.verdict === 'cold');
  const dot = (v) => `<i class="dot ${v}" title="${esc(VERDICTS[v]?.label || '')}"></i>`;
  const armAttr = (id) => (armed === id ? ' data-armed="1"' : '');

  // ---------- views ----------
  function home() {
    const n = state.reps.length;
    return `
    <section class="hero">
      <p class="eyebrow">A practice, not a course</p>
      <h1 class="quote">What I cannot <em>create</em>, I do not understand.</h1>
      <p class="by">— Richard Feynman, left on his blackboard, 1988</p>
      <div class="hero-grid">
        <div>
          <p class="pitch">A self-governed, local-first practice for building muscle across domains. Your reps stay in your browser.</p>
          <div class="row">
            <a class="btn primary" href="#/bench">${n ? 'Back to the bench' : 'Go to the bench'} →</a>
            <a class="btn quiet" href="#/about">What is this?</a>
          </div>
        </div>
        <div>
          <div class="stack" role="img" aria-label="Three layers: knowing about it at the bottom, understanding it at the top, and a missing layer between them: making it yourself.">
            <div class="slab solid"><b>understanding it</b><span>what you wanted</span></div>
            <div class="slab gap"><b>making it yourself</b><span>the missing layer</span></div>
            <div class="slab base"><b>knowing about it</b><span>what you have</span></div>
          </div>
          <p class="stack-cap">Reading, watching and being told all land on the bottom layer. Nothing reaches the top without passing through the middle.</p>
        </div>
      </div>
    </section>

    <section class="steps" aria-label="How a rep works">
      <div class="step"><span class="n">01</span><h3>Name the thing</h3><p>Something you would say you know. A twelve-bar blues. A binary search. A through dovetail. A proof.</p></div>
      <div class="step"><span class="n">02</span><h3>Make it cold</h3><p>Blank page, nothing open to copy from, clock running. Then say honestly how it went.</p></div>
      <div class="step"><span class="n">03</span><h3>Write what was missing</h3><p>One line. It is the first thing you see next time. Repeat until the thing holds.</p></div>
    </section>

    <section class="tenets">
      <div><h3>Self-governed</h3><p>No curriculum, no teacher, no streak to protect. You choose the domains, write the rules, and give the verdicts.</p></div>
      <div><h3>Local-first</h3><p>No account, no server, no analytics. The record lives in this browser and leaves only as a file you export.</p></div>
      <div><h3>Across domains</h3><p>A chord, a joint, a function and an argument are the same shape of work: can you produce it from nothing, again?</p></div>
    </section>`;
  }

  function bench() {
    if (!state.domains.length) {
      return `
      <div class="head"><div><h1 class="h1">The bench</h1><p class="lede">Start with a domain: any field where you want the knowing to turn into doing.</p></div></div>
      <div class="card empty">
        <h2>Nothing on the bench yet.</h2>
        <p>Pick a starting point, or type your own. Domains are only folders. The work is in what you put inside them.</p>
        <div class="chips">${SUGGESTED.map((s) => `<button class="chip" data-act="add-domain" data-name="${esc(s)}">+ ${esc(s)}</button>`).join('')}</div>
        <form class="row add-domain" data-form="domain">
          <input class="field grow" name="name" maxlength="60" placeholder="Your own domain" aria-label="New domain name" required>
          <button class="btn">Add</button>
        </form>
        <p class="small" style="margin-top:22px"><button class="btn quiet sm" data-act="sample">Just looking? Load sample reps</button></p>
      </div>`;
    }
    const domains = state.domains.map((d) => {
      const ps = piecesOf(d.id);
      const reps = ps.reduce((n, p) => n + repsOf(p.id).length, 0);
      const held = ps.filter((p) => isHeld(repsOf(p.id))).length;
      const rows = ps.map((p) => {
        const rs = repsOf(p.id), last = rs[rs.length - 1];
        const status = !rs.length ? '<span class="tag">new</span>' : isHeld(rs) ? '<span class="tag held">held</span>' : '<span class="tag">working</span>';
        const lastGap = last && last.gap ? last : null;
        return `
        <li class="piece">
          <div class="title">${esc(p.title)}</div>
          <div class="acts">
            <button class="btn primary sm" data-act="start" data-id="${p.id}">Start cold</button>
            <button class="x${armed === 'p' + p.id ? ' armed' : ''}" data-act="del-piece" data-id="${p.id}" aria-label="Remove ${esc(p.title)}">${armed === 'p' + p.id ? 'remove + reps?' : '×'}</button>
          </div>
          <div class="sub">
            ${status}
            ${rs.length ? `<span class="dots" aria-label="${plural(rs.length, 'rep')}">${rs.slice(-12).map((r) => dot(r.verdict)).join('')}</span><span>${plural(rs.length, 'rep')} · last ${ago(last.at)}</span>` : '<span>no reps yet</span>'}
          </div>
          ${lastGap ? `<div class="lastgap"><b>Missing last time</b>${esc(lastGap.gap)}</div>` : ''}
        </li>`;
      }).join('');
      return `
      <article class="card domain">
        <header>
          <div><h2>${esc(d.name)}</h2></div>
          <div class="row">
            <span class="meta">${plural(reps, 'rep')} · ${held} of ${ps.length} held</span>
            <button class="x${armed === 'd' + d.id ? ' armed' : ''}" data-act="del-domain" data-id="${d.id}" aria-label="Remove domain ${esc(d.name)}">${armed === 'd' + d.id ? 'remove domain + everything in it?' : '×'}</button>
          </div>
        </header>
        <ul class="pieces">${rows}</ul>
        <form class="row add-piece" data-form="piece" data-id="${d.id}">
          <input class="field grow" name="title" maxlength="140" placeholder="${ps.length ? 'Another thing to make from nothing' : 'A thing you claim to know, small enough to make in one sitting'}" aria-label="New thing to make in ${esc(d.name)}" required>
          <button class="btn">Add</button>
        </form>
      </article>`;
    }).join('');

    return `
    ${state.sample ? `<div class="banner"><span>These are <b>sample reps</b>, loaded so you can look around. They are not yours.</span><button class="btn sm" data-act="clear-sample">Clear and start my own</button></div>` : ''}
    <div class="head">
      <div><h1 class="h1">The bench</h1><p class="lede">Pick one thing. Make it from nothing. Say how it went.</p></div>
      <form class="row" data-form="domain">
        <input class="field" name="name" maxlength="60" placeholder="New domain" aria-label="New domain name" required style="width:180px">
        <button class="btn">Add domain</button>
      </form>
    </div>
    ${domains}
    <div class="legend" aria-label="Legend">
      <span>${dot('cold')} made it cold</span><span>${dot('looked')} had to look</span><span>${dot('notyet')} not yet</span>
      <span><span class="tag held">held</span> last ${state.hold} reps cold</span>
    </div>
    <section class="card rules">
      <h2>Your rules</h2>
      <p class="muted small">Nobody checks these but you. Change them when they stop serving the work.</p>
      <ol>${state.rules.map((r, i) => `<li><div><span>${esc(r)}</span><button class="x" data-act="del-rule" data-i="${i}" aria-label="Remove rule">×</button></div></li>`).join('') || '<li class="muted">No rules. That is also a rule.</li>'}</ol>
      <form class="row" data-form="rule">
        <input class="field grow" name="rule" maxlength="160" placeholder="Add a rule" aria-label="New rule" required>
        <button class="btn">Add</button>
      </form>
      <div class="row hold">
        <label for="hold">A thing is <b>held</b> when the last</label>
        <input class="field" id="hold" type="number" min="1" max="20" value="${state.hold}" data-change="hold">
        <span>reps in a row were made cold.</span>
      </div>
    </section>`;
  }

  function rep() {
    const a = state.active;
    const p = state.pieces.find((x) => x.id === a.pieceId);
    const d = state.domains.find((x) => x.id === p.domainId);
    const prior = repsOf(p.id).filter((r) => r.gap).pop() && repsOf(p.id).slice(-1)[0].gap ? repsOf(p.id).slice(-1)[0] : null;
    if (a.stage === 'running') {
      return `
      <section class="rep">
        <p class="eyebrow">${esc(d.name)} · rep ${repsOf(p.id).length + 1}</p>
        <h1 class="what">${esc(p.title)}</h1>
        <div class="clock" id="clock" role="timer" aria-live="off">${clock(elapsed())}</div>
        <p class="remind">Leave this tab. Go make it — on paper, on the instrument, in an empty file. Come back when you are done or stuck.</p>
        ${prior ? `<p class="prior"><b>Missing last time</b>${esc(prior.gap)}</p>` : ''}
        <div class="row">
          <button class="btn primary" data-act="stop">I'm done</button>
          <button class="btn quiet" data-act="abandon">Abandon, don't count it</button>
        </div>
      </section>`;
    }
    return `
    <section class="rep">
      <p class="eyebrow">${esc(d.name)} · ${clock(a.seconds)} at the bench</p>
      <h1 class="what">${esc(p.title)}</h1>
      <div class="verdicts" role="group" aria-label="How did it go?">
        ${Object.entries(VERDICTS).map(([k, v]) => `
          <button class="verdict" data-act="verdict" data-v="${k}" aria-pressed="${draft.verdict === k}">
            <b>${dot(k)}${v.label}</b><span>${v.hint}</span>
          </button>`).join('')}
      </div>
      <label for="gap">What was missing?</label>
      <textarea class="field" id="gap" maxlength="600" data-input="gap" placeholder="The step you blanked on. The thing you reached for. One line is enough, and it is fine to leave this empty if nothing was.">${esc(draft.gap)}</textarea>
      <div class="row">
        <button class="btn primary" data-act="log" ${draft.verdict ? '' : 'disabled style="opacity:.45;cursor:not-allowed"'}>Log the rep</button>
        <button class="btn quiet" data-act="abandon">Discard</button>
      </div>
    </section>`;
  }

  function ledger() {
    const reps = [...state.reps].sort((a, b) => b.at - a.at);
    if (!reps.length) {
      return `<div class="head"><div><h1 class="h1">The ledger</h1><p class="lede">Every rep you log shows up here, with what was missing.</p></div></div>
      <div class="card empty"><h2>No reps yet.</h2><p>The ledger fills itself. Go make something.</p><p style="margin-top:18px"><a class="btn primary" href="#/bench">Go to the bench →</a></p></div>`;
    }
    const cold = reps.filter((r) => r.verdict === 'cold').length;
    const minutes = Math.round(reps.reduce((n, r) => n + (r.seconds || 0), 0) / 60);
    const byDay = new Map();
    reps.forEach((r) => { const k = dayKey(r.at); byDay.set(k, (byDay.get(k) || []).concat(r)); });

    // 16 weeks, columns are weeks (Mon first), ending this week
    const WEEKS = 16, today = startOfDay(Date.now());
    const dow = (new Date(today).getDay() + 6) % 7;
    const first = new Date(today); first.setDate(first.getDate() - dow - (WEEKS - 1) * 7);
    let cells = '';
    for (let i = 0; i < WEEKS * 7; i++) {
      const d = new Date(first); d.setDate(first.getDate() + i);
      if (d.getTime() > today) { cells += '<i class="cell future"></i>'; continue; }
      const n = (byDay.get(dayKey(d)) || []).length;
      cells += `<i class="cell${n ? ' l' + Math.min(n, 3) : ''}" title="${d.toLocaleDateString(undefined, { month: 'short', day: 'numeric' })}: ${plural(n, 'rep')}"></i>`;
    }

    const days = [...byDay.entries()].map(([, rs]) => `
      <section class="day">
        <h3>${longDay(rs[0].at)}</h3>
        ${rs.map((r) => {
          const p = state.pieces.find((x) => x.id === r.pieceId);
          const d = p && state.domains.find((x) => x.id === p.domainId);
          return `<div class="entry">
            ${dot(r.verdict)}
            <div class="t">${esc(p ? p.title : 'removed')} <span class="muted small" style="font-weight:400">· ${esc(d ? d.name : '')}</span></div>
            <div class="m"><span>${esc(VERDICTS[r.verdict]?.label.toLowerCase() || '')} · ${clock(r.seconds || 0)}</span><button class="x${armed === 'r' + r.id ? ' armed' : ''}" data-act="del-rep" data-id="${r.id}" aria-label="Delete this rep">${armed === 'r' + r.id ? 'delete?' : '×'}</button></div>
            ${r.gap ? `<div class="g">${esc(r.gap)}</div>` : ''}
          </div>`;
        }).join('')}
      </section>`).join('');

    return `
    ${state.sample ? `<div class="banner"><span>These are <b>sample reps</b>, not yours.</span><button class="btn sm" data-act="clear-sample">Clear and start my own</button></div>` : ''}
    <div class="head"><div><h1 class="h1">The ledger</h1><p class="lede">What you actually did. No scores, no streaks to protect.</p></div></div>
    <div class="stats">
      <div class="stat"><b>${reps.length}</b><span>reps</span></div>
      <div class="stat"><b>${Math.round((cold / reps.length) * 100)}%</b><span>made cold</span></div>
      <div class="stat"><b>${byDay.size}</b><span>days at the bench</span></div>
      <div class="stat"><b>${minutes < 120 ? minutes + 'm' : (minutes / 60).toFixed(1) + 'h'}</b><span>time making</span></div>
    </div>
    <p class="eyebrow" style="margin-bottom:10px">Last ${WEEKS} weeks</p>
    <div class="grid-wrap"><div class="grid" role="img" aria-label="Reps per day over the last ${WEEKS} weeks">${cells}</div></div>
    ${days}`;
  }

  function data() {
    const bytes = new Blob([JSON.stringify(state)]).size;
    return `
    <div class="head"><div><h1 class="h1">Your data</h1><p class="lede">It is a single JSON record in this browser's local storage. There is no copy anywhere else, which means there is no backup unless you make one.</p></div></div>
    ${storageOK ? '' : '<div class="banner"><span>This browser is refusing local storage (private window, or storage blocked). You can practice, but nothing will survive closing the tab. Export before you leave.</span></div>'}
    <dl class="kv">
      <dt>domains</dt><dd>${state.domains.length}</dd>
      <dt>things to make</dt><dd>${state.pieces.length}</dd>
      <dt>reps</dt><dd>${state.reps.length}</dd>
      <dt>size</dt><dd>${bytes < 1024 ? bytes + ' bytes' : (bytes / 1024).toFixed(1) + ' KB'}</dd>
      <dt>stored at</dt><dd>localStorage["${KEY}"]</dd>
    </dl>
    <div class="panel-list">
      <div class="card"><div><h3>Export</h3><p>Download everything as one readable JSON file. This is your backup and your way to move browsers.</p></div><button class="btn" data-act="export">Download file</button></div>
      <div class="card"><div><h3>Import</h3><p>Replace what is here with a file you exported earlier.</p></div><label class="btn" tabindex="0">Choose file<input type="file" accept="application/json,.json" data-change="import" hidden></label></div>
      <div class="card"><div><h3>Erase</h3><p>Remove every domain, rep and rule from this browser. There is no undo.</p></div><button class="btn danger" data-act="erase">${armed === 'erase' ? 'Yes, erase everything' : 'Erase'}</button></div>
    </div>
    <p class="note" role="status">${esc(flash)}</p>`;
  }

  function about() {
    return `
    <div class="prose">
      <h1 class="h1">About</h1>
      <p class="lede" style="margin-bottom:22px">What this site is, what it is built from, and what is still a guess.</p>

      <p>There is a layer between hearing how something works and understanding it. It is the part where you produce the thing yourself, from nothing, and find out which pieces you were only nodding along to. It cannot be read, watched or explained into place. This site is a bench for that layer and nothing more.</p>

      <h2>What a rep is</h2>
      <p>You name one thing small enough to make in a sitting. You make it cold. You give your own verdict, and you write down what was missing. The next time you sit down with it, that line is waiting. When the last few reps in a row were made cold, the thing is marked <em>held</em>, and you move on.</p>
      <p>The site does not teach, grade, rank or remind. It keeps the record straight and stays out of the way.</p>

      <h2>What it is built from</h2>
      <p>The project's own stated purpose is one sentence, and the whole site is an attempt to take it literally:</p>
      <blockquote>“What I cannot create, I do not understand.” A self-governed, local-first practice for building muscle across domains. Your reps stay in your browser.</blockquote>
      <ul>
        <li><b>Given:</b> the Feynman line as the bar; practice as the purpose; self-governed; local-first; across domains; reps stored in the browser.</li>
        <li><b>Interpreted by the builder:</b> the reading of “the missing layer” as the making layer between knowing and understanding; the cold start; the three verdicts; the “what was missing” note; the <em>held</em> threshold; the names bench and ledger.</li>
        <li><b>Not established:</b> who beyond its author this practice is meant for, and whether the mechanics here match what the author does by hand. Those are the owner's to say, and this page will change when they do.</li>
      </ul>

      <h2>What it does not do</h2>
      <ul>
        <li>No account, no sign-in, no server holding anything.</li>
        <li>No analytics, cookies, fonts or scripts from anywhere else. After the page loads it makes no requests; your browser's network panel will confirm it.</li>
        <li>No sync. Moving to another browser means exporting a file and importing it there.</li>
      </ul>

      <p style="margin-top:26px"><a class="btn primary" href="#/bench">Go to the bench →</a></p>
    </div>`;
  }

  // ---------- render + routing ----------
  const routes = { '': home, bench, ledger, data, about };
  function route() { return (location.hash.replace(/^#\/?/, '') || '').split('/')[0]; }
  function elapsed() { return Math.max(0, Math.floor((Date.now() - state.active.startedAt) / 1000)); }

  function render(keepFocus) {
    clearInterval(tick);
    const r = route();
    const inRep = state.active && state.pieces.some((p) => p.id === state.active.pieceId);
    if (state.active && !inRep) { state.active = null; save(); }
    main.innerHTML = inRep ? rep() : (routes[r] || home)();
    document.querySelectorAll('nav a').forEach((a) => {
      if (!inRep && a.dataset.nav === r) a.setAttribute('aria-current', 'page'); else a.removeAttribute('aria-current');
    });
    if (inRep && state.active.stage === 'running') {
      const el = $('#clock');
      tick = setInterval(() => { el.textContent = clock(elapsed()); document.title = `${clock(elapsed())} · ${$('.what').textContent}`; }, 1000);
    } else {
      const name = inRep ? '' : { bench: 'Bench', ledger: 'Ledger', data: 'Your data', about: 'About' }[r];
      document.title = name ? `${name} · The Missing Layer` : 'The Missing Layer — practice, by making';
    }
    if (keepFocus) { const f = $(keepFocus); if (f) f.focus(); }
  }
  function commit(keepFocus) { save(); render(keepFocus); }

  // ---------- actions ----------
  function addDomain(name) {
    name = name.trim(); if (!name) return;
    if (state.domains.some((d) => d.name.toLowerCase() === name.toLowerCase())) return;
    state.domains.push({ id: uid(), name, created: Date.now() });
  }
  // A destructive button needs two clicks; the first only arms it.
  function confirmArm(id) { if (armed === id) { armed = null; return true; } armed = id; render(); return false; }

  const actions = {
    'add-domain': (el) => { addDomain(el.dataset.name); commit(); },
    start: (el) => { state.active = { pieceId: el.dataset.id, startedAt: Date.now(), stage: 'running' }; draft = { verdict: null, gap: '' }; commit(); window.scrollTo(0, 0); },
    stop: () => { state.active.seconds = elapsed(); state.active.stage = 'verdict'; commit(); },
    abandon: () => { state.active = null; commit(); },
    verdict: (el) => { draft.verdict = el.dataset.v; render(`[data-v="${draft.verdict}"]`); },
    log: () => {
      if (!draft.verdict) return;
      const a = state.active;
      state.reps.push({ id: uid(), pieceId: a.pieceId, at: Date.now(), seconds: a.seconds, verdict: draft.verdict, gap: draft.gap.trim() });
      state.active = null; draft = { verdict: null, gap: '' };
      if (route() !== 'bench') { save(); location.hash = '#/bench'; } else commit();
    },
    'del-piece': (el) => { if (!confirmArm('p' + el.dataset.id)) return; state.pieces = state.pieces.filter((p) => p.id !== el.dataset.id); state.reps = state.reps.filter((r) => r.pieceId !== el.dataset.id); commit(); },
    'del-domain': (el) => {
      if (!confirmArm('d' + el.dataset.id)) return;
      const gone = new Set(piecesOf(el.dataset.id).map((p) => p.id));
      state.domains = state.domains.filter((d) => d.id !== el.dataset.id);
      state.pieces = state.pieces.filter((p) => !gone.has(p.id));
      state.reps = state.reps.filter((r) => !gone.has(r.pieceId));
      commit();
    },
    'del-rep': (el) => { if (!confirmArm('r' + el.dataset.id)) return; state.reps = state.reps.filter((r) => r.id !== el.dataset.id); commit(); },
    'del-rule': (el) => { state.rules.splice(+el.dataset.i, 1); commit(); },
    sample: () => { state = sample(); commit(); },
    'clear-sample': () => { state = fresh(); commit(); },
    erase: () => { if (!confirmArm('erase')) return; state = fresh(); flash = 'Erased. This browser holds nothing now.'; commit(); },
    export: () => {
      const blob = new Blob([JSON.stringify({ ...state, active: null }, null, 2)], { type: 'application/json' });
      const a = document.createElement('a');
      a.href = URL.createObjectURL(blob); a.download = `themissinglayer-${dayKey(Date.now())}.json`;
      document.body.appendChild(a); a.click(); a.remove(); setTimeout(() => URL.revokeObjectURL(a.href), 1000);
      flash = 'Exported. Keep the file somewhere you trust.'; render();
    },
  };

  main.addEventListener('click', (e) => {
    const el = e.target.closest('[data-act]');
    if (!el) { if (armed) { armed = null; render(); } return; }
    if (armed && !el.dataset.act.startsWith('del-') && el.dataset.act !== 'erase') armed = null;
    flash = '';
    actions[el.dataset.act]?.(el);
  });

  main.addEventListener('submit', (e) => {
    const f = e.target.closest('[data-form]'); if (!f) return;
    e.preventDefault();
    const kind = f.dataset.form;
    if (kind === 'domain') { addDomain(f.name.value); commit(); }
    if (kind === 'piece') {
      const title = f.title.value.trim();
      if (title) state.pieces.push({ id: uid(), domainId: f.dataset.id, title, created: Date.now() });
      commit(`[data-form="piece"][data-id="${f.dataset.id}"] input`);
    }
    if (kind === 'rule') { const r = f.rule.value.trim(); if (r) state.rules.push(r); commit('[data-form="rule"] input'); }
  });

  main.addEventListener('input', (e) => { if (e.target.dataset.input === 'gap') draft.gap = e.target.value; });

  main.addEventListener('change', (e) => {
    const k = e.target.dataset.change;
    if (k === 'hold') { state.hold = Math.min(20, Math.max(1, parseInt(e.target.value, 10) || 3)); commit(); }
    if (k === 'import') {
      const file = e.target.files[0]; if (!file) return;
      file.text().then((t) => {
        let s; try { s = JSON.parse(t); } catch { s = null; }
        if (!valid(s)) { flash = 'That file is not a Missing Layer export. Nothing was changed.'; return render(); }
        const ids = new Set(s.pieces.map((p) => p.id));
        state = { ...fresh(), ...s, active: null, reps: s.reps.filter((r) => ids.has(r.pieceId) && VERDICTS[r.verdict]) };
        flash = `Imported ${plural(state.reps.length, 'rep')} across ${plural(state.domains.length, 'domain')}.`;
        commit();
      });
    }
  });

  // ---------- sample data (clearly marked, never mixed with real reps) ----------
  function sample() {
    const s = fresh(); s.sample = true;
    const now = Date.now(), D = 864e5;
    const mk = (domain, items) => {
      const d = { id: uid(), name: domain, created: now - 40 * D }; s.domains.push(d);
      items.forEach(([title, reps]) => {
        const p = { id: uid(), domainId: d.id, title, created: now - 40 * D }; s.pieces.push(p);
        reps.forEach(([daysAgo, verdict, min, gap]) => s.reps.push({ id: uid(), pieceId: p.id, at: now - daysAgo * D - 3600e3, seconds: min * 60 + (daysAgo * 7) % 50, verdict, gap: gap || '' }));
      });
    };
    mk('Guitar', [
      ['Twelve-bar blues in A, with a turnaround', [[33, 'notyet', 9, 'Lost the form at bar 9. I know the chords, not where I am in them.'], [29, 'looked', 12, 'Had to check the turnaround fingering.'], [22, 'cold', 8], [15, 'cold', 6], [6, 'cold', 5]]],
      ['A minor pentatonic, all five positions, connected', [[20, 'looked', 14, 'Positions 3 and 4 blur together moving up the neck.'], [11, 'looked', 11, 'Position 4 still. The shift on the B string.'], [2, 'cold', 10]]],
    ]);
    mk('Code', [
      ['Binary search, no off-by-one, first try', [[31, 'looked', 7, 'lo <= hi versus lo < hi. I guessed.'], [24, 'cold', 4], [17, 'cold', 3], [9, 'cold', 3]]],
      ['An LRU cache from an empty file', [[13, 'notyet', 25, 'Could describe it perfectly. Could not keep the list and the map in step on eviction.'], [5, 'looked', 21, 'Moving a node to the front: forgot to unlink it first.'], [0, 'cold', 16]]],
      ['Parse a CSV line with quoted commas', [[3, 'notyet', 18, 'Escaped quotes inside quoted fields. Never actually handled them before, only used a library.']]],
    ]);
    mk('Woodworking', [
      ['Through dovetail, hand cut, one corner', [[27, 'notyet', 55, 'Sawed on the wrong side of the line on two tails.'], [14, 'looked', 48, 'Checked the marking sequence: tails first, then transfer.'], [1, 'looked', 41, 'Baseline gaps. Paring past the knife line.']]],
    ]);
    return s;
  }

  // ---------- go ----------
  window.addEventListener('hashchange', () => { armed = null; flash = ''; render(); window.scrollTo(0, 0); main.focus({ preventScroll: true }); });
  window.addEventListener('storage', (e) => { if (e.key === KEY) { state = load(); render(); } });
  render();

  if ('serviceWorker' in navigator && location.protocol.startsWith('http')) {
    navigator.serviceWorker.register('sw.js').catch(() => {});
  }
})();

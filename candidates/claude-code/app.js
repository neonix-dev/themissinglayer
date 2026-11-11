/* The Missing Layer — reader, fit diagnostic, and the layer builder.
   Owner-authored text comes from content.js. Everything the visitor writes stays in localStorage. */
(() => {
  'use strict';

  const DOCS = window.TML_DOCS || [];
  const DIAG = window.TML_DIAG || { parts: [], scoring: {}, honest: [] };
  const KEY = 'themissinglayer.v2';

  // ---------- the eight categories (thesis §2) + where the work lives (§8.2) ----------
  const EXTERNAL = [
    ['practitioner', 'Identity of the practitioner', 'What role you are operating in, what register your work is in.'],
    ['work', 'Identity of the work', 'What this project is, what it is for.'],
    ['state', 'State of the work', 'Where you are. What is done. What is in progress. What is next.'],
    ['decisions', 'Decisions made', 'What is settled. What has been committed to.'],
    ['open', 'Open questions', 'What is not yet decided. What is in motion.'],
    ['conventions', 'Conventions and language', 'How you talk about this work. Your terms. Your shared vocabulary.'],
    ['constraints', 'Constraints', 'What you will not do. The negative space.'],
  ];
  const INTERNAL = [
    ['frames', 'Frames', 'How you look at this work.'],
    ['attention', 'Attention-patterns', 'What you notice first; what you check before anything else.'],
    ['principles', 'Operating principles', 'The rules you actually work by.'],
    ['failures', 'Recognized failure-modes', 'The ways this work, or you, have gone wrong before.'],
    ['questions', 'Characteristic questions', 'The questions you keep asking of the work.'],
  ];
  const MODES = {
    A: { name: 'Mode A: Long Chat', short: 'Long chat', hint: 'Exploration. Accept drift.', mitigation: 'Periodically reload Law mid-chat. Do not assume early instructions are still active.' },
    B: { name: 'Mode B: Memory On', short: 'Memory on', hint: 'Routine. Platform curates part of the signature.', mitigation: 'Treat memory as supplement to operator-controlled Law, never as replacement.' },
    C: { name: 'Mode C: One Prompt, One Output', short: 'One prompt, one output', hint: 'Commits. Every call auditable.', mitigation: 'Build the FP-dump step into the workflow so it does not depend on memory or discipline alone.' },
  };
  const REFLECT = [
    'Where does the signature show internal contradiction?',
    'Where has it accumulated assumptions that are not grounded?',
    'Where has recent updating been over-fit to specific events?',
    'Where does your expressed understanding diverge from your actual operating record?',
    'What is your signature not addressing — the negative space?',
  ];

  const fresh = () => ({ v: 2, fields: {}, mode: 'C', depth: 'light', versions: [], predictions: [], fit: {} });

  // ---------- storage ----------
  let storageOK = true;
  const valid = (s) => s && s.v === 2 && typeof s.fields === 'object' && Array.isArray(s.versions) && Array.isArray(s.predictions);
  function load() {
    try { const raw = localStorage.getItem(KEY); if (!raw) return fresh(); const s = JSON.parse(raw); return valid(s) ? { ...fresh(), ...s } : fresh(); }
    catch { storageOK = false; return fresh(); }
  }
  function save() { try { localStorage.setItem(KEY, JSON.stringify(state)); storageOK = true; } catch { storageOK = false; } }
  let state = load();

  // ---------- helpers ----------
  const $ = (s, el = document) => el.querySelector(s);
  const main = $('#main');
  const esc = (s) => String(s ?? '').replace(/[&<>"']/g, (c) => ({ '&': '&amp;', '<': '&lt;', '>': '&gt;', '"': '&quot;', "'": '&#39;' }[c]));
  const uid = () => (crypto.randomUUID ? crypto.randomUUID() : Date.now().toString(36) + Math.random().toString(36).slice(2));
  const pad = (n) => String(n).padStart(2, '0');
  const isoDay = (t = Date.now()) => { const d = new Date(t); return `${d.getFullYear()}-${pad(d.getMonth() + 1)}-${pad(d.getDate())}`; };
  const when = (t) => new Date(t).toLocaleString(undefined, { month: 'short', day: 'numeric', hour: 'numeric', minute: '2-digit' });
  const plural = (n, w) => `${n} ${w}${n === 1 ? '' : 's'}`;
  let armed = null, flash = '';
  function download(name, text, type) {
    const a = document.createElement('a');
    a.href = URL.createObjectURL(new Blob([text], { type })); a.download = name;
    document.body.appendChild(a); a.click(); a.remove(); setTimeout(() => URL.revokeObjectURL(a.href), 1000);
  }

  // ---------- home + the session boundary ----------
  const sim = { session: 1, z: 0, law: 0, geo: 0, intent: 0, fp: 0, layer: true, reexplained: 0, worked: 0 };
  const dots = (n, cap = 24) => '<i></i>'.repeat(Math.min(n, cap));

  function simView() {
    const lost = !sim.layer;
    const L = (cls, name, desc, n, isLost) => `
      <div class="layer ${cls}${isLost ? ' lost' : ''}" data-layer="${cls}">
        <b>${name}</b><span>${desc}</span><div class="meter" aria-label="${n} items">${dots(n)}</div>
      </div>`;
    const prior = sim.session - 1;
    let read;
    if (sim.layer) {
      read = prior
        ? `Session <b>${sim.session}</b>. Z remembers nothing of ${prior === 1 ? 'session 1' : `sessions 1–${prior}`}. It loads Law, reads the Geometry, picks up the Intent — and continues.`
        : `Session <b>1</b>. Do some work, then end the session.`;
    } else {
      read = prior
        ? `Session <b>${sim.session}</b>. The artifact survived, but nothing says how to read it. Context re-explained so far: <b>${sim.reexplained}</b>.`
        : `Session <b>1</b>. Without the layer. Do some work, then end the session.`;
    }
    return `
      <div class="sim-head">
        <span>A working session</span>
        <span class="switch" role="group" aria-label="Layer">
          <button data-act="layer-on" aria-pressed="${sim.layer}">with the layer</button>
          <button data-act="layer-off" aria-pressed="${!sim.layer}">without</button>
        </span>
      </div>
      <div class="layers">
        ${L('z', 'Z', 'The model. Each session, Z starts from zero.', sim.z)}
        <div class="reset-line" aria-hidden="true"><span>session boundary</span></div>
        ${L('law', 'Law', 'Your instructions. Breakable — Z can drift from it.', sim.law, lost)}
        ${L('geo', 'Geometry', 'The structural substrate of the work. It accumulates.', sim.geo, lost)}
        ${L('intent', 'Intent', 'What you are trying to do, refined as you go.', sim.intent, lost)}
        ${L('fp', 'FP', 'The artifact. Where the work lives between sessions.', sim.fp)}
      </div>
      <div class="sim-foot">
        <p class="readout" aria-live="polite">${read}</p>
        <div class="row">
          <button class="btn sm" data-act="work">Work</button>
          <button class="btn sm primary" data-act="end" ${sim.worked ? '' : 'disabled'}>End session</button>
          <button class="btn sm quiet" data-act="sim-reset">Reset</button>
        </div>
      </div>`;
  }
  function renderSim(flashCls) {
    const el = $('#sim'); if (!el) return;
    el.innerHTML = simView();
    if (flashCls) el.querySelectorAll(flashCls).forEach((n) => n.classList.add('flash'));
  }

  function home() {
    const thesis = DOCS.find((d) => d.id === 'thesis');
    return `
    <section class="hero">
      <p class="epigraph"><i lang="sa">Yogaḥ karmasu kauśalam.</i> <b>Mastery is alignment within action.</b></p>
      <h1>The model is stateless by design. You are <em>not.</em></h1>
      <p class="lede">Continuity is your problem to solve. Each new session, the AI does not remember what you built together, and the gap between what you understand and what it operates with widens. The continuity-architecture you build around it is the missing layer.</p>
      <div class="row">
        <a class="btn primary" href="#/read/thesis">Read the thesis</a>
        <a class="btn" href="#/build">Build your layer</a>
      </div>
      <p class="byline">Rajan Thakurdesai${thesis ? ` · ${thesis.words.toLocaleString()} words` : ''} · developed over two years of practice</p>
    </section>

    <section class="boundary" aria-labelledby="b-h">
      <div>
        <p class="eyebrow">The architecture, in one session</p>
        <h2 id="b-h" style="margin-top:10px">Z resets. Everything else must cross.</h2>
        <p>Five elements operate together. Each session loads Law into Z, reads Geometry, engages with FP, refines Intent. The session ends. FP, Law, Geometry and Intent persist. Z resets. The next session reloads.</p>
        <p>Switch the layer off and end a session: the artifact survives, but the understanding that made it readable does not.</p>
        <p class="quote">Understanding crosses the session boundary through serialized projections, not through direct transmission.</p>
      </div>
      <div class="card sim" id="sim">${simView()}</div>
    </section>

    <section class="three" aria-label="Three ways in">
      <a href="#/read/thesis"><span class="n">01 · READ</span><h3>The publication</h3><p>The thesis, the three modes of practice, and a note for platform engineers who have already built this without calling it that.</p></a>
      <a href="#/fit"><span class="n">02 · FIT</span><h3>Does it fit you?</h3><p>The diagnostic, by domain, practitioner and operating conditions. Not a gate, and not a score.</p></a>
      <a href="#/build"><span class="n">03 · BUILD</span><h3>Your layer</h3><p>Write the eight things that must cross the boundary. Get a Law file with reflection and disclosure built in. Keep score against reality.</p></a>
    </section>

    <section class="warn">
      <h2>The central failure mode</h2>
      <div>
        <p>This architecture can become a delusion-compounding engine if reality-contact mechanisms are weak.</p>
        <p>That sentence is load-bearing. Read it again. Coherence is not strongly correlated with truth — <a href="#/read/thesis#thesis-9-the-central-failure-mode-and-how-to-guard-against-it">section 9</a> says what to do about it.</p>
      </div>
    </section>`;
  }

  // ---------- reader ----------
  function reader(id) {
    const i = Math.max(0, DOCS.findIndex((d) => d.id === id));
    const d = DOCS[i];
    if (!d) return '<p>The documents did not load.</p>';
    const prev = DOCS[i - 1], next = DOCS[i + 1];
    return `
    <div class="reader">
      <aside class="toc" aria-label="Documents">
        <div class="docs">${DOCS.map((x) => `<a href="#/read/${x.id}"${x.id === d.id ? ' aria-current="page"' : ''}><b>${esc(x.kind)}</b>${esc(x.title)}</a>`).join('')}</div>
        <ol>${d.toc.map(([hid, t]) => `<li><a href="#/read/${d.id}#${hid}">${esc(t)}</a></li>`).join('')}</ol>
      </aside>
      <article class="doc">
        <p class="eyebrow">${esc(d.kind)}</p>
        <h1 class="h1" style="margin-top:8px">${esc(d.title)}</h1>
        <p class="meta">${esc(d.author)} · ${d.words.toLocaleString()} words${d.id === 'fit' ? ' · <a href="#/fit">take it interactively →</a>' : ''}</p>
        ${d.html}
        <nav class="doc-next" aria-label="More documents">
          ${prev ? `<a class="btn quiet" href="#/read/${prev.id}">← ${esc(prev.title)}</a>` : '<span></span>'}
          ${next ? `<a class="btn" href="#/read/${next.id}">${esc(next.title)} →</a>` : '<a class="btn" href="#/build">Build your layer →</a>'}
        </nav>
      </article>
    </div>`;
  }

  // ---------- fit ----------
  // Tiers are this site's reading of each answer's own verdict text; the document itself is explicit that it is not a numeric score.
  const tier = (v) => (/poor|do not|will not produce|wait until|establish this/i.test(v) ? 'poor' : /caution|partial|possible|may be|verify/i.test(v) ? 'mixed' : 'fit');
  const TIER_LABEL = { fit: 'fit', mixed: 'caution', poor: 'poor fit' };

  function fitResult() {
    const per = DIAG.parts.map((p) => {
      const ts = p.questions.map((q) => { const a = state.fit[q.n]; return a == null ? null : tier(q.opts[a].v); });
      const answered = ts.filter(Boolean).length;
      const t = answered < ts.length ? null : ts.includes('poor') ? 'poor' : ts.includes('mixed') ? 'mixed' : 'fit';
      return { p, t, answered, total: ts.length };
    });
    const total = per.reduce((n, x) => n + x.total, 0), answered = per.reduce((n, x) => n + x.answered, 0);
    let key = null;
    if (answered === total && total) {
      const [dom, prac] = per;
      const poorParts = per.filter((x) => x.t === 'poor').length;
      if (poorParts >= 2) key = 'Poor fit across multiple parts';
      else if (per.every((x) => x.t === 'fit')) key = 'Strong fit across all three parts';
      else if (dom.t === 'fit' && prac.t !== 'fit') key = 'Strong domain-fit but mixed practitioner-fit';
      else if (prac.t === 'fit' && dom.t !== 'fit') key = 'Strong practitioner-fit but mixed domain-fit';
      else key = 'Mixed everywhere';
    }
    let weakest = '';
    if (key === 'Strong domain-fit but mixed practitioner-fit') {
      const order = { poor: 0, mixed: 1, fit: 2 };
      const q = [...DIAG.parts[1].questions].sort((a, b) => order[tier(a.opts[state.fit[a.n]].v)] - order[tier(b.opts[state.fit[b.n]].v)])[0];
      weakest = `<p class="small muted">Your weakest practitioner answer: <b>${esc(q.n)}</b> — ${esc(q.q)}</p>`;
    }
    const allTop = answered === total && DIAG.parts.every((p) => p.questions.every((q) => state.fit[q.n] === 0));
    return `
      <div class="parts">${per.map((x) => `<span>${esc(x.p.title.replace(' Diagnostic', ''))} <span class="tag ${x.t || ''}">${x.t ? TIER_LABEL[x.t] : `${x.answered}/${x.total}`}</span></span>`).join('')}
        ${answered ? '<button class="x" data-act="fit-clear">clear answers</button>' : ''}</div>
      ${key ? `<h2>${esc(key)}</h2><p>${esc(DIAG.scoring[key] || '')}</p>${weakest}` : `<p class="small muted" style="margin-top:10px">${answered ? `${answered} of ${total} answered.` : 'Answer honestly.'} The guidance appears when every question has an answer. Answers stay in this browser.</p>`}
      ${allTop ? `<p class="small" style="margin-top:10px;color:var(--rust)">You chose the strongest answer to every question. ${esc(DIAG.honest[1] || '')}</p>` : ''}`;
  }

  function fit() {
    return `
    <p class="eyebrow">Self-evaluation</p>
    <h1 class="h1" style="margin-top:8px">Does this architecture fit you?</h1>
    <p class="lede">The architecture amplifies whatever you load. If what you load is mis-fit to amplification, the amplification compounds the mis-fit. This is not a gate.</p>
    ${DIAG.parts.map((p) => `
      <section class="part" aria-labelledby="part-${p.n}">
        <h2 id="part-${p.n}">${p.n}. ${esc(p.title)}</h2>
        <p>${esc(p.intro)}</p>
        ${p.questions.map((q) => `
          <div class="card q">
            <h3><span>${esc(q.n)}</span>${esc(q.q)}</h3>
            <div class="opts" role="radiogroup" aria-label="${esc(q.q)}">
              ${q.opts.map((o, i) => `
                <button class="opt" role="radio" aria-checked="${state.fit[q.n] === i}" data-act="fit" data-q="${esc(q.n)}" data-i="${i}">
                  <i></i><span>${esc(o.a)}<span class="v ${tier(o.v)}">${esc(o.v)}</span></span>
                </button>`).join('')}
            </div>
          </div>`).join('')}
        ${Object.keys(p.lists).length ? `<div class="domains">${Object.entries(p.lists).map(([h, items]) => `<div><h4>${esc(h)}</h4><ul>${items.map((x) => `<li>${esc(x)}</li>`).join('')}</ul></div>`).join('')}</div>` : ''}
      </section>`).join('')}
    <div class="card result" id="fit-result" aria-live="polite">${fitResult()}</div>
    <section class="honest">
      <h2>A note on honest answers</h2>
      ${DIAG.honest.map((p) => `<p>${esc(p)}</p>`).join('')}
    </section>`;
  }

  // ---------- build ----------
  function lawText(f = state.fields, mode = state.mode, depth = state.depth, versionNo = state.versions.length + 1) {
    const val = (k) => (f[k] || '').trim();
    const block = (k, title) => `## ${title}\n${val(k) || '_Not yet written._'}\n`;
    const title = (val('work').split('\n')[0] || 'this work').slice(0, 80);
    const m = MODES[mode];
    return [
      `# Law — ${title}`,
      `Loaded at the start of every session. Version ${versionNo}, ${isoDay()}. ${m.name}.`,
      '',
      '## Before operating: reflect',
      'Before operating inside this signature, interrogate the signature itself:',
      ...REFLECT.map((q) => `- ${q}`),
      depth === 'heavy'
        ? 'Heavy interrogation: this session commits to something the signature should be tested against. Answer each question before starting the work.'
        : 'Light touch: this is routine continuation. Raise only what would change the next step.',
      'The reflection is not a gate. It is a flag. Surface the risk; I evaluate; I decide. When I override a flagged risk, operate inside the override, with no further pushback on the acknowledged risk.',
      '',
      ...EXTERNAL.map(([k, t]) => block(k, t)),
      '## Where the work lives (FP)',
      `${val('fp') || '_Not yet written._'}`,
      'Chat history is ephemeral; the artifact is canonical. Do not modify the artifact without being asked.',
      '',
      '## Understanding (projections)',
      'These projections do not contain the understanding. They produce output that approximates operating with the understanding.',
      '',
      ...INTERNAL.map(([k, t]) => `### ${t}\n${val(k) || '_Not yet written._'}\n`),
      `## Mode`,
      `${m.name}. ${m.mitigation}`,
      '',
      '## Disclosure',
      'Append to every substantive output:',
      `*(\*) Produced with this specific understanding, in ${m.name.split(':')[0]}. If not true, please do risk assessment before accepting advice.*`,
      '',
    ].join('\n');
  }
  function highlight(t) {
    return esc(t).split('\n').map((l) => (/^#{1,3} /.test(l) ? `<span class="hd">${l}</span>` : l === '_Not yet written._' ? `<span class="ph">${l}</span>` : l)).join('\n');
  }
  const filled = (f = state.fields) => [...EXTERNAL, ...INTERNAL, ['fp']].filter(([k]) => (f[k] || '').trim()).length;
  const TOTAL_FIELDS = EXTERNAL.length + INTERNAL.length + 1;

  function fieldHTML([k, t, hint], rows = 2) {
    return `<div class="fld"><label for="f-${k}">${esc(t)}<small>${esc(hint)}</small></label>
      <textarea class="field" id="f-${k}" rows="${rows}" data-field="${k}">${esc(state.fields[k] || '')}</textarea></div>`;
  }

  function build() {
    const held = state.predictions.filter((p) => p.outcome === 'held').length;
    const settled = state.predictions.filter((p) => p.outcome !== 'open').length;
    return `
    <p class="eyebrow">Build</p>
    <h1 class="h1" style="margin-top:8px">Your layer</h1>
    <p class="lede">The first seven can be captured. The eighth — your understanding — cannot be captured directly; it crosses through its projections. Write what you can. Empty sections stay visible in the file as negative space.</p>
    ${storageOK ? '' : '<p class="note">This browser is refusing local storage. Nothing here will survive closing the tab — download before you leave.</p>'}
    <div class="build" style="margin-top:30px">
      <div>
        <section class="group"><h2>External · <b>artifact-able</b></h2>
          ${EXTERNAL.map((f) => fieldHTML(f, f[0] === 'state' ? 3 : 2)).join('')}
          ${fieldHTML(['fp', 'Where the work lives (FP)', 'The actual artifact. Versioned. State-trackable. Distinct from your conversations with the model.'], 2)}
        </section>
        <section class="group"><h2>Internal · <b>through its projections</b></h2>
          ${INTERNAL.map((f) => fieldHTML(f)).join('')}
        </section>
        <section class="group"><h2>Mode of practice</h2>
          <div class="choice" role="group" aria-label="Mode">${Object.entries(MODES).map(([k, m]) => `<button data-act="mode" data-mode="${k}" aria-pressed="${state.mode === k}"><b>${k} · ${esc(m.short)}</b>${esc(m.hint)}</button>`).join('')}</div>
          <div class="fld"><label>Reflection<small>Proportional to the stakes.</small></label>
            <div class="choice" role="group" aria-label="Reflection depth" style="grid-template-columns:1fr 1fr">
              <button data-act="depth" data-depth="light" aria-pressed="${state.depth === 'light'}"><b>Light touch</b>Routine continuation.</button>
              <button data-act="depth" data-depth="heavy" aria-pressed="${state.depth === 'heavy'}"><b>Heavy</b>About to commit to something.</button>
            </div>
          </div>
        </section>
      </div>
      <div class="preview">
        <div class="bar"><span class="mono small muted" id="filled">${filled()} of ${TOTAL_FIELDS} written</span>
          <span class="row"><button class="btn sm" data-act="copy">Copy</button><button class="btn sm" data-act="download-law">Download CLAUDE.md</button></span></div>
        <pre id="law" aria-label="Generated Law file">${highlight(lawText())}</pre>
        <p class="note" id="law-note" role="status">${esc(flash)}</p>
      </div>
    </div>

    <section class="ledger">
      <div>
        <h2>Versions</h2>
        <p>Your Geometry accumulates. Seal a version when the Law changes, so you can read older outputs against current reality — retrospective calibration.</p>
        <div class="row" style="margin-bottom:12px"><input class="field" id="vnote" maxlength="120" placeholder="What changed (optional)" style="flex:1;min-width:0"><button class="btn" data-act="seal">Seal version ${state.versions.length + 1}</button></div>
        <ul class="list">${state.versions.length ? [...state.versions].reverse().map((v, i) => `
          <li><span class="t">v${state.versions.length - i}${v.note ? ' · ' + esc(v.note) : ''}</span>
            <span class="m">${when(v.at)} · ${v.filled}/${TOTAL_FIELDS} written · ${MODES[v.mode]?.short || ''}</span>
            <span class="a"><button class="x" data-act="restore" data-id="${v.id}">${armed === 'r' + v.id ? 'replace current?' : 'restore'}</button><button class="x" data-act="dl-version" data-id="${v.id}">download</button></span></li>`).join('') : '<li><span class="empty">No sealed versions yet.</span></li>'}</ul>
      </div>
      <div>
        <h2>Scorekeeping</h2>
        <p>Track predictions against outcomes. When your Geometry predicts X and reality produces not-X, the Geometry needs revision, not protection.</p>
        <form class="addrow" data-form="prediction">
          <input class="field" name="text" maxlength="240" placeholder="My understanding predicts…" required aria-label="Prediction">
          <input class="field" name="by" type="date" aria-label="Check by" value="${isoDay(Date.now() + 14 * 864e5)}">
          <button class="btn">Add</button>
        </form>
        <p class="mono small muted" style="margin:10px 0">${settled ? `${held} of ${settled} settled predictions held` : 'Nothing settled yet.'}</p>
        <ul class="list">${state.predictions.length ? [...state.predictions].reverse().map((p) => {
          const overdue = p.outcome === 'open' && p.by && p.by < isoDay();
          return `<li><span class="t">${esc(p.text)}</span>
            <span class="m">${p.outcome === 'open' ? (p.by ? `check by ${p.by}${overdue ? ' · due' : ''}` : 'open') : `<span class="tag ${p.outcome === 'held' ? 'fit' : 'poor'}">${p.outcome === 'held' ? 'held' : 'did not hold'}</span> v${p.v}`}</span>
            <span class="a">${p.outcome === 'open' ? `<button class="x" data-act="held" data-id="${p.id}">held</button><button class="x" data-act="missed" data-id="${p.id}">did not hold</button>` : `<button class="x" data-act="reopen" data-id="${p.id}">reopen</button>`}<button class="x${armed === 'p' + p.id ? ' armed' : ''}" data-act="del-pred" data-id="${p.id}" aria-label="Delete prediction">${armed === 'p' + p.id ? 'delete?' : '×'}</button></span></li>`;
        }).join('') : '<li><span class="empty">No predictions yet.</span></li>'}</ul>
      </div>
    </section>

    <div class="card data-strip">
      <span>Everything above lives only in this browser. ${plural(state.versions.length, 'version')}, ${plural(state.predictions.length, 'prediction')}.</span>
      <span class="row">
        <button class="btn sm" data-act="export">Export all</button>
        <label class="btn sm" tabindex="0">Import<input type="file" accept="application/json,.json" data-change="import" hidden></label>
        <button class="btn sm quiet" data-act="erase">${armed === 'erase' ? 'Yes, erase everything' : 'Erase'}</button>
      </span>
    </div>`;
  }

  // ---------- sources ----------
  function sources() {
    return `
    <div class="prose">
      <p class="eyebrow">Sources</p>
      <h1 class="h1" style="margin-top:8px">Where this came from</h1>
      <p class="lede">This site is a reconstruction. The text is the author's; the instruments are built from it. This page says which is which.</p>

      <h2>The author's words</h2>
      <p>The four documents under <a href="#/read/thesis">Read</a> are reproduced from the author's own drafts, each headed with his name and with <code>themissinglayer.org</code> as its source, dated 2026-05-17. Only their full text is used. Notes added later by an AI assistant were left out.</p>
      <div class="prov">
        ${DOCS.map((d) => `<div><span>${esc(d.kind)}</span><span>${esc(d.title)} — ${d.words.toLocaleString()} words</span></div>`).join('')}
        <div><span>Left out</span><span>A fifth draft, “The Missing Layer (GPT version)”, is a re-articulation written by GPT, not the author. It also redefines <i>FP</i> in a way that conflicts with the thesis.</span></div>
      </div>

      <h2>Built from the text</h2>
      <ul>
        <li><b>The session-boundary demonstration</b> on the home page illustrates section 3 of the thesis. The counts are illustrative, not measured.</li>
        <li><b>The fit diagnostic</b> uses the questions and verdicts verbatim. Colouring each answer as fit, caution, or poor fit, and choosing which scoring paragraph applies, is this site's reading of the verdict text. The diagnostic itself says it is not a numeric score.</li>
        <li><b>The Law builder</b> takes its categories from section 2 of the thesis, its reflection questions from section 5, the override from section 6, the disclosure from section 7, and the mode-aware disclosure and mitigations from <i>Modes of Practice</i>. The layout of the generated file, and the wording of the light and heavy reflection lines, are this site's.</li>
        <li><b>Versions and scorekeeping</b> implement two of the reality-contact mechanisms in section 9: retrospective calibration and empirical scorekeeping.</li>
      </ul>

      <h2>Named but not found</h2>
      <p>The thesis lists companion artifacts: a diagram of the six-element architecture; example Claude.md files for a software, a writing and a research project; the over-fit failure case; the trading anti-pattern. None of them turned up in any trace, so none were written here in the author's name.</p>

      <h2>What this site does not do</h2>
      <ul>
        <li>No account, no server, no analytics, no third-party fonts or scripts.</li>
        <li>What you write under Build and Fit stays in this browser's local storage, and leaves only as a file you export.</li>
      </ul>
    </div>`;
  }

  // ---------- routing ----------
  function route() { const [r, a] = location.hash.replace(/^#\/?/, '').split('#')[0].split('/'); return { r: r || '', a }; }
  function render() {
    const { r, a } = route();
    const view = { '': home, read: () => reader(a || 'thesis'), fit, build, sources }[r] || home;
    main.innerHTML = view();
    document.querySelectorAll('nav a').forEach((n) => (n.dataset.nav === r ? n.setAttribute('aria-current', 'page') : n.removeAttribute('aria-current')));
    const titles = { read: (DOCS.find((d) => d.id === (a || 'thesis')) || {}).title, fit: 'Fit', build: 'Your layer', sources: 'Sources' };
    document.title = titles[r] && titles[r] !== 'The Missing Layer' ? `${titles[r]} · The Missing Layer` : 'The Missing Layer';
    const anchor = location.hash.split('#')[2];
    if (anchor) { const el = document.getElementById(anchor); if (el) el.scrollIntoView(); }
  }
  function commit() { save(); render(); }
  function confirmArm(id) { if (armed === id) { armed = null; return true; } armed = id; render(); return false; }

  // ---------- events ----------
  const actions = {
    work: () => { sim.worked++; sim.z++; sim.fp++; sim.intent = Math.min(sim.intent + 1, 12); if (sim.z % 2 === 1) sim.law++; if (sim.z % 3 === 0) sim.geo++; renderSim('[data-layer="z"]'); },
    end: () => {
      if (!sim.worked) return;
      if (!sim.layer) { sim.reexplained += sim.law + sim.geo + sim.intent; sim.law = 0; sim.geo = 0; sim.intent = 0; }
      sim.session++; sim.z = 0; sim.worked = 0;
      renderSim(sim.layer ? '[data-layer="z"]' : '.layer');
    },
    'sim-reset': () => { Object.assign(sim, { session: 1, z: 0, law: 0, geo: 0, intent: 0, fp: 0, reexplained: 0, worked: 0 }); renderSim(); },
    'layer-on': () => { sim.layer = true; actions['sim-reset'](); },
    'layer-off': () => { sim.layer = false; actions['sim-reset'](); },
    fit: (el) => { state.fit[el.dataset.q] = +el.dataset.i; save(); const g = el.closest('.opts'); g.querySelectorAll('.opt').forEach((b) => b.setAttribute('aria-checked', b === el)); $('#fit-result').innerHTML = fitResult(); },
    'fit-clear': () => { state.fit = {}; commit(); },
    mode: (el) => { state.mode = el.dataset.mode; commit(); },
    depth: (el) => { state.depth = el.dataset.depth; commit(); },
    copy: async () => {
      let ok = false; try { await navigator.clipboard.writeText(lawText()); ok = true; } catch {}
      $('#law-note').textContent = ok ? 'Copied. Load it at the start of the next session.' : 'Copy was blocked by the browser. Use Download instead.';
    },
    'download-law': () => { download('CLAUDE.md', lawText(), 'text/markdown'); $('#law-note').textContent = 'Downloaded CLAUDE.md.'; },
    seal: () => {
      const note = ($('#vnote')?.value || '').trim();
      state.versions.push({ id: uid(), at: Date.now(), note, fields: { ...state.fields }, mode: state.mode, depth: state.depth, filled: filled(), text: lawText() });
      flash = `Sealed version ${state.versions.length}.`; commit(); flash = '';
    },
    restore: (el) => {
      if (!confirmArm('r' + el.dataset.id)) return;
      const v = state.versions.find((x) => x.id === el.dataset.id); if (!v) return;
      state.fields = { ...v.fields }; state.mode = v.mode; state.depth = v.depth;
      flash = `Restored version ${state.versions.indexOf(v) + 1} into the editor.`; commit(); flash = '';
    },
    'dl-version': (el) => { const i = state.versions.findIndex((x) => x.id === el.dataset.id); if (i > -1) download(`CLAUDE.v${i + 1}.md`, state.versions[i].text, 'text/markdown'); },
    held: (el) => { const p = state.predictions.find((x) => x.id === el.dataset.id); if (p) { p.outcome = 'held'; p.settled = Date.now(); } commit(); },
    missed: (el) => { const p = state.predictions.find((x) => x.id === el.dataset.id); if (p) { p.outcome = 'missed'; p.settled = Date.now(); } commit(); },
    reopen: (el) => { const p = state.predictions.find((x) => x.id === el.dataset.id); if (p) p.outcome = 'open'; commit(); },
    'del-pred': (el) => { if (!confirmArm('p' + el.dataset.id)) return; state.predictions = state.predictions.filter((x) => x.id !== el.dataset.id); commit(); },
    export: () => download(`themissinglayer-${isoDay()}.json`, JSON.stringify(state, null, 2), 'application/json'),
    erase: () => { if (!confirmArm('erase')) return; state = fresh(); commit(); },
  };

  main.addEventListener('click', (e) => {
    const el = e.target.closest('[data-act]');
    if (!el) { if (armed) { armed = null; render(); } return; }
    const act = el.dataset.act;
    if (armed && !['restore', 'del-pred', 'erase'].includes(act)) armed = null;
    actions[act]?.(el);
  });

  main.addEventListener('input', (e) => {
    const k = e.target.dataset.field; if (!k) return;
    state.fields[k] = e.target.value; save();
    const pre = $('#law'); if (pre) pre.innerHTML = highlight(lawText());
    const f = $('#filled'); if (f) f.textContent = `${filled()} of ${TOTAL_FIELDS} written`;
  });

  main.addEventListener('submit', (e) => {
    const f = e.target.closest('[data-form="prediction"]'); if (!f) return;
    e.preventDefault();
    const text = f.text.value.trim(); if (!text) return;
    state.predictions.push({ id: uid(), at: Date.now(), text, by: f.by.value || '', outcome: 'open', v: state.versions.length || 0 });
    commit(); $('[data-form="prediction"] input[name="text"]')?.focus();
  });

  main.addEventListener('change', (e) => {
    if (e.target.dataset.change !== 'import') return;
    const file = e.target.files[0]; if (!file) return;
    file.text().then((t) => {
      let s; try { s = JSON.parse(t); } catch { s = null; }
      if (!valid(s)) { flash = 'That file is not a Missing Layer export. Nothing changed.'; render(); flash = ''; return; }
      state = { ...fresh(), ...s }; flash = `Imported ${plural(state.versions.length, 'version')} and ${plural(state.predictions.length, 'prediction')}.`; commit(); flash = '';
    });
  });

  window.addEventListener('hashchange', () => {
    armed = null; render();
    if (!location.hash.split('#')[2]) window.scrollTo(0, 0);
    main.focus({ preventScroll: true });
  });
  window.addEventListener('storage', (e) => { if (e.key === KEY) { state = load(); render(); } });
  render();

  if ('serviceWorker' in navigator && location.protocol.startsWith('http')) navigator.serviceWorker.register('sw.js').catch(() => {});
})();

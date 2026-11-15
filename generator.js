// The generator. The one script on the site. It takes shapes in as JSON and turns the
// ones it knows into running code, in this tab. It holds the grammar of a step and how
// to draw a board; which stores and verbs exist, and what each does, is in the contract.
// Text is never run as code here, and the page's policy makes the browser refuse it.
// What the board is and holds can be kept as plain JSON on floppies and rebuilt from them.
(async () => {
  if (document.querySelector("main.board")) return;   // one board to a page
  const el = (kind, text, attrs) => {
    const node = document.createElement(kind);
    if (text != null) node.append(text);
    for (const [k, v] of Object.entries(attrs || {})) node.setAttribute(k, v);
    return node;
  };
  class Refused extends Error {}
  const address = location.pathname.replace(/\.html$/, "").split("/").pop(), asking = address === "deserialize";
  const refuse = (why) => { throw new Refused(why); };
  const word = (v) => (v == null ? "" : typeof v === "string" ? v : JSON.stringify(v));

  // ---- the grammar of a step ----------------------------------------------------------
  const box = el("div", null, { class: "box" });
  const ROOTS = {
    document: () => document, box: () => box, localStorage: () => localStorage, sessionStorage: () => sessionStorage,
    indexedDB: () => indexedDB, cookieStore: () => cookieStore, caches: () => caches, history: () => history, location: () => location,
  };
  const MAKES = { Response: (...a) => new Response(...a), URL: (...a) => new URL(...a) };
  const STEPS = ["from", "use", "as", "new", "gather", "each", "entries", "part", "call", "get", "set"];
  const NEVER = /^(constructor|__proto__|prototype|defaultView|insertAdjacentHTML|write|writeln|setHTMLUnsafe|parseHTMLUnsafe)$/;
  const NEVER_SET = /^(innerHTML|outerHTML|srcdoc)$/;
  const NAMED = /^\$\w+$/;

  // Only shapes the generator knows get through. Parts are written out in place.
  const known = (steps, parts, depth = 0) => {
    if (!Array.isArray(steps)) refuse("steps must be a list");
    if (depth > 8) refuse("parts are nested too deep");
    return steps.flatMap((s) => {
      const kind = s && typeof s === "object" && !Array.isArray(s) && STEPS.find((k) => k in s);
      if (!kind) refuse(`not a step the generator knows: ${JSON.stringify(s)}`);
      if (kind === "part") return s.part in parts ? known(parts[s.part], parts, depth + 1) : refuse(`no part called ${s.part}`);
      if (kind === "from" && !(s.from in ROOTS)) refuse(`the generator does not start from ${s.from}`);
      if (kind === "new" && !(s.new in MAKES)) refuse(`the generator does not make a ${s.new}`);
      if ((kind === "call" || kind === "get" || kind === "set") && (typeof s[kind] !== "string" || NEVER.test(s[kind]))) refuse(`the generator does not touch ${s[kind]}`);
      if (kind === "set" && NEVER_SET.test(s.set)) refuse(`the generator does not write ${s.set}`);
      if (kind === "each") return [{ each: known(s.each, parts, depth + 1) }];
      if (kind === "gather") return [{ gather: Object.fromEntries(Object.entries(s.gather).map(([k, p]) => [k, known(p, parts, depth + 1)])) }];
      return [s.upgrade ? { ...s, upgrade: known(s.upgrade, parts, depth + 1) } : s];
    });
  };

  const fill = (text, env) => text.replace(/\{([A-Za-z]\w*)(?::(uri|before=|after=))?\}/g, (all, key, how) => {
    if (!(key in env.words)) return all;
    const s = word(env.words[key]), at = s.indexOf("=");
    return how === "uri" ? encodeURIComponent(s) : how === "before=" ? (at < 0 ? s : s.slice(0, at)) : how === "after=" ? (at < 0 ? "" : s.slice(at + 1)) : s;
  });
  const given = (a, env) => {
    if (typeof a === "string") {
      if (!NAMED.test(a)) return fill(a, env);
      const thing = env.named[a.slice(1)];
      if (thing == null) env.missing = true;
      return thing;
    }
    if (Array.isArray(a)) return a.map((x) => given(x, env));
    if (a && typeof a === "object") return Object.fromEntries(Object.entries(a).map(([k, v]) => [k, given(v, env)]));
    return a;
  };
  // A database request answers later; wait for it. Anything else is awaited as it is.
  const settle = (x, upgrade, env) => (typeof IDBRequest !== "undefined" && x instanceof IDBRequest ? new Promise((ok, no) => {
    if (upgrade) x.onupgradeneeded = () => { walk(upgrade, env, x.result); };
    x.onsuccess = () => ok(x.result);
    x.onerror = () => no(x.error);
  }) : x);

  // The steps, turned into what the browser does. `it` is the current thing.
  const walk = async (steps, env, it) => {
    for (const s of steps) {
      if ("from" in s) it = ROOTS[s.from]();
      else if ("use" in s) it = env.named[s.use];
      else if ("as" in s) env.named[s.as] = it;
      else if ("new" in s) it = MAKES[s.new](...given(s.with || [], env));
      else if ("gather" in s) { const all = {}; for (const [k, p] of Object.entries(s.gather)) all[k] = await walk(p, env); it = all; }
      else if (it == null) { env.missing = true; return null; }
      else if ("entries" in s) it = Object.entries(it);
      else if ("each" in s) { const all = []; for (const one of it) all.push(await walk(s.each, env, one)); it = all; }
      else if ("call" in s) {
        if (typeof it[s.call] !== "function") refuse(`${s.call} cannot be called there`);
        const passed = given(s.with || [], env);
        if (env.missing) return null;
        it = await settle(it[s.call](...passed), s.upgrade, env);
      }
      else if ("get" in s) it = await settle(it[s.get]);
      else if ("set" in s) { const to = given(s.to, env); if (env.missing) return null; it[s.set] = to; }
    }
    return it;
  };

  // The same steps written out as the code they stand for. Shown, never run.
  const shown = (a, env) => (typeof a === "string" ? (NAMED.test(a) ? a.slice(1) : JSON.stringify(fill(a, env)))
    : Array.isArray(a) ? `[${a.map((x) => shown(x, env)).join(", ")}]`
    : a && typeof a === "object" ? `{${Object.entries(a).map(([k, v]) => `${k}: ${shown(v, env)}`).join(", ")}}` : JSON.stringify(a));
  const passed = (s, env) => (s.with || []).map((x) => shown(x, env)).join(", ");
  const code = (steps, env, start) => {
    const lines = [];
    let cur = start || "", bare = true;
    const flush = () => { if (cur && !bare) lines.push(cur); };
    for (const s of steps) {
      if ("from" in s) { flush(); cur = s.from; bare = true; }
      else if ("use" in s) { flush(); cur = s.use; bare = true; }
      else if ("as" in s) { if (!bare) lines.push(`const ${s.as} = ${cur}`); else if (cur !== s.as) lines.push(`const ${s.as} = ${cur}`); cur = s.as; bare = true; }
      else if ("new" in s) { flush(); cur = `new ${s.new}(${passed(s, env)})`; bare = false; }
      else if ("gather" in s) { flush(); cur = `{${Object.entries(s.gather).map(([k, p]) => `${k}: ${code(p, env)}`).join(", ")}}`; bare = false; }
      else if ("entries" in s) { cur = `Object.entries(${cur})`; bare = false; }
      else if ("each" in s) { cur = `${cur}.map((one) => ${code(s.each, env, "one") || "one"})`; bare = false; }
      else if ("call" in s) { cur = `${cur}.${s.call}(${passed(s, env)})`; bare = false; }
      else if ("get" in s) { cur = `${cur}.${s.get}`; bare = false; }
      else if ("set" in s) { lines.push(`${cur}.${s.set} = ${shown(s.to, env)}`); bare = true; }
    }
    flush();
    return lines.join("; ");
  };

  // What a store holds, as rows of name and value, however the browser hands it over.
  const rowsOf = (x) => (x == null ? [] : Array.isArray(x) ? x.map((r) => (Array.isArray(r) ? [word(r[0]), word(r[1])]
    : r && typeof r === "object" && "name" in r && "value" in r ? [word(r.name), word(r.value)] : [word(r)]))
    : typeof x === "object" ? Object.entries(x).map(([k, v]) => [k, word(v)]) : [[word(x)]]);

  // ---- running a shape ----------------------------------------------------------------
  let contract;
  const envOf = (words) => ({ words, named: {}, missing: false });
  const runVerb = async (shape, undoing) => {
    const store = contract.stores.find((s) => s.store === shape.store) || refuse(`no store is called ${shape.store}`);
    const verb = store.verbs.find((v) => v.verb === shape.verb) || refuse(`${shape.store} has no verb called ${shape.verb}`);
    const words = { Name: word(shape.Name), Value: word(shape.Value) };
    const parts = contract.parts || {};
    let was = null;
    if (verb.was && !undoing) {
      const before = envOf(words);
      try { was = await walk(known(verb.was, parts), before); } catch { was = null; }
      if (before.missing) was = null;
    }
    const steps = known(verb.steps, parts), env = envOf(words);
    const out = await walk(steps, env);
    const none = env.missing || (verb["empty is none"] && out == null);
    const said = fill(none ? verb.none || "nothing is called {Name}" : verb.says || "done", { words: { ...words, result: word(out) } });
    let back = null;
    if (!undoing && !none) {
      const plain = (shapeOut, more) => given(shapeOut, envOf({ ...words, Was: word(was), ...more }));
      if (verb["undo each"] && Array.isArray(was)) back = rowsOf(was).map(([name, value]) => plain(verb["undo each"], { name, value }));
      else if (verb.was && was == null) back = verb["undo if none"] ? [plain(verb["undo if none"])] : null;
      else if (verb.undo) back = [plain(verb.undo)];
    }
    return { what: `${store.store} ${verb.verb}`, said, code: code(steps, env), back };
  };
  const runSteps = async (shape) => {
    const steps = known(shape.steps, (contract && contract.parts) || {}), env = envOf({ Name: word(shape.Name), Value: word(shape.Value) });
    const out = await walk(steps, env);
    return { what: "steps", said: env.missing ? "there was nothing there to act on" : word(out).slice(0, 200) || "done", code: code(steps, env), back: null };
  };

  // ---- the board ----------------------------------------------------------------------
  const board = el("main", null, { class: "board" });
  const head = el("header"), title = el("h1"), says = el("p", null, { class: "says" });
  head.append(title, says);
  const stores = el("section", null, { class: "knob", "aria-label": "Store" });
  const verbs = el("section", null, { class: "knob", "aria-label": "Verb" });
  const field = (label) => { const input = el("input", null, { autocomplete: "off", autocapitalize: "off", spellcheck: "false" }); const wrap = el("label", label + " "); wrap.append(input); return [wrap, input]; };
  const [nameLabel, name] = field("Name"), [valueLabel, value] = field("Value");
  const fields = el("section", null, { class: "fields" });
  fields.append(nameLabel, valueLabel);
  const doIt = el("button", "Do", { type: "button" }), undoIt = el("button", "Undo", { type: "button" });
  const acts = el("section", null, { class: "act" });
  acts.append(doIt, undoIt);
  const said = el("output", "Ready.", { class: "said", "aria-live": "polite" });
  const knobs = el("section", null, { class: "panel knobs", "aria-label": "Knobs" });
  knobs.append(stores, verbs, fields, acts, said);

  const held = el("section", null, { class: "panel held", "aria-label": "What the store holds" });
  const heading = el("h2"), rows = el("div", null, { class: "rows" });
  held.append(heading, rows, box);

  const doors = el("section", null, { class: "panel doors", "aria-label": "Shapes" });
  const ranHead = el("h2", "Ran"), ran = el("div", null, { class: "rows ran" });
  const codeLine = el("code", null, { class: "code", "aria-label": "Code" });
  const handBack = el("button", "Hand back", { type: "button" });
  const shapeLabel = el("label", "Shape "), shape = el("textarea", null, { autocomplete: "off", autocapitalize: "off", spellcheck: "false" });
  shapeLabel.append(shape);
  const generate = el("button", "Generate", { type: "button" });
  const save = el("button", "Save", { type: "button", title: "Download what the board is and holds, as plain JSON" });
  const load = el("button", "Load", { type: "button", title: "Rebuild the board from saved JSON" });
  const files = el("input", null, { type: "file", accept: ".json,application/json", multiple: "", hidden: "" });
  const doorActs = el("div", null, { class: "act" });
  doorActs.append(generate, handBack, save, load, files);
  doors.append(ranHead, ran, codeLine, shapeLabel, doorActs);
  board.append(head, knobs, held, doors);
  // The page opens on its cover: a title and one line. The board is built behind it and
  // is not shown until someone goes in, by touching the title or by calling board.enter().
  const cover = document.querySelector("main.cover") || el("main", null, { class: "cover" });
  const way = cover.querySelector("button") || cover.appendChild(el("h1")).appendChild(el("button", "The Missing Layer", { type: "button" }));
  const line = cover.querySelector("p") || cover.appendChild(el("p"));
  board.hidden = true;
  document.body.append(cover, board);

  let store, verb, original;
  const log = [], undone = [];
  const tell = (text) => { said.textContent = text; };
  const pressed = (group, button) => { for (const b of group.children) b.setAttribute("aria-pressed", String(b === button)); };
  // Only what fits is shown and the rest is counted, so nothing scrolls.
  const fit = (list) => {
    let more = 0;
    while (list.scrollHeight > list.clientHeight + 1 && list.children.length > 1) { list.lastChild.remove(); more++; }
    if (more) { list.lastChild.remove(); list.append(el("p", `and ${more + 1} more`)); }
  };

  const show = async () => {
    if (!store) return;
    let got;
    try { got = await walk(known(store.holds || [], contract.parts || {}), envOf({})); }
    catch { heading.textContent = `${store.store} is not available in this browser`; rows.replaceChildren(); rows.hidden = false; box.hidden = true; return; }
    box.hidden = got !== box;
    rows.hidden = got === box;
    if (got === box) { heading.textContent = `${store.store}: ${box.children.length} made here`; return; }
    const pairs = rowsOf(got);
    heading.textContent = `${store.store} holds ${pairs.length}`;
    rows.replaceChildren(...pairs.map(([n, v]) => {
      const row = el("button", v === undefined ? n : `${n} = ${v}`, { type: "button" });
      row.onclick = () => { if (!name.disabled) name.value = n; if (!value.disabled && v !== undefined) value.value = v; };
      return row;
    }));
    fit(rows);
  };
  const showRan = () => {
    ran.replaceChildren(...log.slice().reverse().map((line) => {
      const row = el("button", line, { type: "button" });
      row.onclick = () => { shape.value = line; };
      return row;
    }));
    fit(ran);
  };

  const pick = (v, button) => {
    verb = v;
    pressed(verbs, button);
    const uses = [...(v.needs || []), ...(v.may || [])];
    name.disabled = !uses.includes("Name");
    value.disabled = !uses.includes("Value");
    if (name.disabled) name.value = "";
    if (value.disabled) value.value = "";
  };
  const choose = async (s, button) => {
    store = s;
    pressed(stores, button);
    verbs.replaceChildren(...(s.verbs || []).map((v) => {
      const b = el("button", v.verb, { type: "button", title: v.does || "" });
      b.onclick = () => { pick(v, b); tell(v.does || v.verb); };
      return b;
    }));
    verb = null;
    if (verbs.firstChild) pick(s.verbs[0], verbs.firstChild);
    await show();
  };

  // A contract is a shape too: handing one in generates the board from it.
  const build = async (c) => {
    if (!Array.isArray(c.stores) || !c.stores.length) refuse("a contract needs stores");
    const parts = c.parts || {};
    for (const s of c.stores) {
      if (typeof s.store !== "string") refuse("every store needs a name");
      known(s.holds || [], parts);
      if (s.keep != null && (typeof s.keep !== "object" || Array.isArray(s.keep))) refuse(`${s.store} does not say how it is kept`);
      for (const v of s.verbs || []) { known(v.steps, parts); if (v.was) known(v.was, parts); }
    }
    contract = c;
    document.title = title.textContent = c.title || "";
    says.textContent = c.says || "";
    stores.replaceChildren(...c.stores.map((s) => {
      const b = el("button", s.store, { type: "button", title: s.is || "" });
      b.onclick = async () => { await choose(s, b); tell(s.is || s.store); };
      return b;
    }));
    await choose(c.stores[0], stores.firstChild);
  };

  // ---- the floppy ---------------------------------------------------------------------
  // What the board is and what its stores hold, written as plain records: the board,
  // each store, each thing held. No code is ever written out; a record is data, and
  // the generator rebuilds from it. The contract says, per store, how it is kept.
  const ENGINE = "1", FLOPPY = 1474560;
  const bytes = (text) => new TextEncoder().encode(text).length;
  const labelOf = (recs, engine) => {
    const text = engine + JSON.stringify(recs);
    let h = 0x811c9dc5;
    for (let i = 0; i < text.length; i++) h = Math.imul(h ^ text.charCodeAt(i), 0x01000193);
    return (h >>> 0).toString(16).padStart(8, "0");
  };
  const HTML = "http://www.w3.org/1999/xhtml";
  // An element as data, and data as an element again.
  const tree = (n) => {
    if (n.nodeType === 3) return n.data;
    if (n.nodeType !== 1) return null;
    const out = n.namespaceURI === HTML ? { kind: n.localName } : { kind: n.tagName, of: n.namespaceURI };
    if (n.attributes.length) out.has = Object.fromEntries([...n.attributes].map((a) => [a.name, a.value]));
    const inside = [...n.childNodes].map(tree).filter((x) => x != null);
    if (inside.length) out.holds = inside;
    return out;
  };
  const grow = (t, depth = 0) => {
    if (typeof t === "string") return document.createTextNode(t);
    if (!t || typeof t !== "object" || typeof t.kind !== "string" || depth > 256) refuse("not a thing the generator can rebuild");
    const node = t.of ? document.createElementNS(t.of, t.kind) : document.createElement(t.kind);
    for (const [k, v] of Object.entries(t.has || {})) node.setAttribute(k, word(v));
    for (const one of t.holds || []) node.append(grow(one, depth + 1));
    return node;
  };
  const records = async () => {
    const { stores: all, ...rest } = contract;
    const recs = [{ board: rest }, ...all.map((s) => ({ store: s }))];
    for (const s of all) {
      if (!s.keep) continue;
      let got;
      try { got = await walk(known(s.holds || [], contract.parts || {}), envOf({})); } catch { recs.push({ left: s.store }); continue; }
      if (got instanceof Element) { for (const n of got.childNodes) { const thing = tree(n); if (thing != null) recs.push({ in: s.store, thing }); } continue; }
      const pairs = rowsOf(got).sort((a, b) => (a[0] < b[0] ? -1 : a[0] > b[0] ? 1 : 0));
      for (const [name, value] of pairs) recs.push(value === undefined ? { in: s.store, name } : { in: s.store, name, value });
    }
    return recs;
  };
  // Records go onto floppies in order, as many as fit on each. No floppy is ever larger
  // than its size: a record too large for one is cut, as text, across as many as it needs.
  const kept = async (size) => {
    size = Number(size) > 0 ? Number(size) : FLOPPY;
    const recs = await records(), label = labelOf(recs, ENGINE);
    const text = (holds, disk, of) => JSON.stringify({ floppy: { engine: ENGINE, label, disk, of }, holds }, null, 2);
    const room = size - bytes(text([], 99999, 99999)) - 4;
    if (room < 64) refuse(`a floppy needs at least ${size - room + 64} bytes`);
    const costOf = (r) => { const t = JSON.stringify(r, null, 2); return bytes(t) + 4 * t.split("\n").length + 2; };
    const pieces = recs.flatMap((r) => {
      if (costOf(r) <= room) return [r];
      const whole = JSON.stringify(r), out = [];
      for (let at = 0; at < whole.length;) {
        let fit = 1, most = whole.length - at;
        while (fit < most) { const mid = (fit + most + 1) >> 1; if (costOf({ cut: whole.slice(at, at + mid), more: false }) <= room) fit = mid; else most = mid - 1; }
        out.push({ cut: whole.slice(at, at + fit), more: at + fit < whole.length });
        at += fit;
      }
      return out;
    });
    const sets = [[]];
    let used = 0;
    for (const r of pieces) {
      const cost = costOf(r);
      if (sets.at(-1).length && used + cost > room) { sets.push([]); used = 0; }
      sets.at(-1).push(r);
      used += cost;
    }
    const disks = sets.map((holds, i) => text(holds, i + 1, sets.length));
    return { disks, label, said: `kept on ${disks.length} ${disks.length === 1 ? "floppy" : "floppies"}, label ${label}` };
  };
  const quiet = (shape) => ("store" in shape ? runVerb(shape, true) : runSteps(shape));
  const rebuild = async (recs, set) => {
    const of = (key) => recs.filter((r) => r && typeof r === "object" && key in r);
    const head = of("board")[0];
    if (!head || !head.board || typeof head.board !== "object") refuse("the floppy holds no board");
    const c = { ...head.board, stores: of("store").map((r) => r.store) };
    const left = new Set(of("left").map((r) => r.left));
    const grown = of("thing").map((r) => [r.in, grow(r.thing)]);
    await build(c);   // refused here, before anything is wiped, if the board on the floppy is not one the generator knows
    // Everything goes first: the site is brought back to the board it shipped with, with
    // every kept store empty, and only then rebuilt from the floppies.
    if (original) {
      await build(original);
      for (const s of original.stores) if (s.keep && s.keep.empty) { try { await quiet(s.keep.empty); } catch { /* not in this browser */ } }
      await build(c);
    }
    log.length = undone.length = 0;
    codeLine.textContent = "";
    const failed = [];
    for (const s of c.stores) {
      if (!s.keep || left.has(s.store)) continue;
      try {
        if (s.keep.empty) await quiet(s.keep.empty);
        const mine = grown.filter(([where]) => where === s.store);
        if (mine.length) (await walk(known(s.holds || [], c.parts || {}), envOf({}))).append(...mine.map(([, node]) => node));
        if (s.keep.each) for (const r of of("name")) if (r.in === s.store) await quiet(given(s.keep.each, envOf({ name: word(r.name), value: word(r.value) })));
      } catch { failed.push(s.store); }
    }
    const same = labelOf(await records(), ENGINE) === labelOf(recs, ENGINE);
    return `rebuilt from ${set.of} ${set.of === 1 ? "floppy" : "floppies"}: ${same ? "the board keeps the same as what was handed in" : "this browser keeps it differently from what was handed in"}`
      + (failed.length ? `; could not rebuild ${failed.join(", ")}` : "")
      + (set.engine === ENGINE ? "" : `; written by engine ${word(set.engine)}, this is engine ${ENGINE}`);
  };
  // Floppies go in one at a time, in any order. The board is rebuilt when the set is whole.
  let slot = null;
  const insert = async (disk) => {
    const f = disk.floppy;
    if (!f || typeof f !== "object" || !Array.isArray(disk.holds) || !Number.isInteger(f.disk) || !Number.isInteger(f.of) || f.disk < 1 || f.disk > f.of) refuse("not a floppy the generator knows");
    if (!slot || slot.label !== f.label || slot.of !== f.of) slot = { label: f.label, of: f.of, engine: f.engine, disks: {} };
    slot.disks[f.disk] = disk.holds;
    const missing = [];
    for (let i = 1; i <= f.of; i++) if (!(i in slot.disks)) missing.push(i);
    if (missing.length) return `floppy ${f.disk} of ${f.of} is in; still needed: ${missing.join(", ")}`;
    const set = slot, recs = [];
    slot = null;
    let cut = "";
    for (let i = 1; i <= set.of; i++) for (const r of set.disks[i]) {
      if (!r || typeof r !== "object" || !("cut" in r)) { recs.push(r); continue; }
      cut += r.cut;
      if (!r.more) { recs.push(JSON.parse(cut)); cut = ""; }
    }
    return rebuild(recs, set);
  };

  // The one way in. The knobs and the Shape box both hand their shape to this.
  const give = async (given, undoing) => {
    if (Array.isArray(given)) { for (const one of given) await give(one, undoing); return; }
    try {
      if (!given || typeof given !== "object") refuse("not a shape the generator knows");
      if ("stores" in given) {
        await build(given);
        log.push(JSON.stringify(given));
        tell("the board was generated from the contract handed in");
        codeLine.textContent = "";
      } else if ("floppy" in given) {
        tell(await insert(given));
      } else if ("keep" in given) {
        const out = await kept(given.keep && given.keep.size);
        shape.value = out.disks.length === 1 ? out.disks[0] : `[\n${out.disks.join(",\n")}\n]`;
        tell(out.said);
      } else {
        const out = "store" in given ? await runVerb(given, undoing) : "steps" in given ? await runSteps(given) : refuse("not a shape the generator knows");
        log.push(JSON.stringify(given));
        tell(`${out.what}: ${out.said}`);
        codeLine.textContent = out.code;
        if (!undoing) undone.push({ what: given.Name ? `${out.what} ${given.Name}` : out.what, back: out.back });
      }
    } catch (e) {
      tell(e instanceof Refused ? `refused: ${e.message}` : `could not: ${e && e.message ? e.message : "not available in this browser"}`);
    }
    showRan();
    await show();
  };

  doIt.onclick = async () => {
    if (!verb) return;
    const n = name.value.trim(), v = value.value;
    for (const need of verb.needs || []) if (!(need === "Name" ? n : v.trim())) return tell(`${verb.verb} needs a ${need}`);
    const run = { store: store.store, verb: verb.verb };
    if (!name.disabled && n) run.Name = n;
    if (!value.disabled && v) run.Value = v;
    name.value = value.value = "";
    await give(run);
  };
  undoIt.onclick = async () => {
    const last = undone.pop();
    if (!last) return tell("nothing to take back");
    if (!last.back) return tell(`${last.what} cannot be taken back`);
    await give(last.back, true);
    tell(`taken back: ${last.what}`);
  };
  generate.onclick = async () => {
    let handed;
    try { handed = JSON.parse(shape.value); } catch { return tell("refused: that is not JSON"); }
    shape.value = "";
    await give(handed);
  };
  handBack.onclick = () => { shape.value = `[${log.join(",")}]`; };
  save.onclick = async () => {
    try {
      const out = await kept();
      out.disks.forEach((text, i) => {
        const a = el("a", null, { href: URL.createObjectURL(new Blob([text], { type: "application/json" })), download: `board-${out.label}-${i + 1}of${out.disks.length}.json` });
        a.click();
        setTimeout(() => URL.revokeObjectURL(a.href), 60000);
      });
      tell(out.said);
    } catch (e) { tell(`could not: ${e && e.message ? e.message : "not available in this browser"}`); }
  };
  // Loading wipes what is here, so it asks first: the second touch opens the files.
  let asked = false;
  load.onclick = () => {
    if (asked) { asked = false; return files.click(); }
    asked = true;
    tell("Load wipes everything here and rebuilds from the files. Touch Save first for a copy. Touch Load again to choose the files.");
  };
  files.onchange = async () => {
    let handed;
    try { handed = (await Promise.all([...files.files].map((f) => f.text()))).map((text) => JSON.parse(text)); } catch { handed = null; }
    files.value = "";
    if (!handed) { line.textContent = "refused: that is not JSON"; return tell(line.textContent); }
    await give(handed.flat());
    line.textContent = said.textContent;
    if (asking && /^rebuilt/.test(said.textContent)) { history.replaceState(history.state, "", "./"); enter(); }
  };
  const enter = async () => { cover.hidden = true; board.hidden = false; showRan(); await show(); };
  way.onclick = enter;
  // The same two things for a script or another seat: serialize gives the floppies as
  // JSON text, deserialize takes them back, as text or parsed, one or many, in any order.
  const parsed = (x) => (typeof x === "string" ? JSON.parse(x) : x);
  globalThis.board = Object.freeze({
    engine: ENGINE,
    enter,
    serialize: async (size) => (await kept(size)).disks,
    deserialize: async (handed) => {
      const disks = [parsed(handed)].flat().map(parsed).flat();
      if (!disks.every((d) => d && typeof d === "object" && "floppy" in d)) throw new Error("deserialize takes floppies");
      await give(disks);
      return said.textContent;
    },
  });
  for (const input of [name, value]) input.onkeydown = (e) => { if (e.key === "Enter") doIt.onclick(); };
  addEventListener("popstate", () => show());

  try { await build(original = await (await fetch("contract.json", { cache: "no-store" })).json()); }
  catch (e) { original = null; tell(e instanceof Refused ? `refused: ${e.message}` : "The generator could not read contract.json. Hand it a contract in Shape."); }

  // Two addresses do the same as Save and Load: /serialize and /deserialize.
  if (asking) {
    line.textContent = "This wipes everything the site holds in this browser and rebuilds it from the files you choose. Download a copy first?";
    const copy = el("button", "Download a copy", { type: "button" }), choose = el("button", "Choose files", { type: "button" });
    copy.onclick = async () => { await save.onclick(); line.textContent = `${said.textContent}. Now choose the files.`; };
    choose.onclick = () => files.click();
    const acts = el("div", null, { class: "act" });
    acts.append(copy, choose);
    cover.append(acts);
  } else if (address === "serialize") {
    await save.onclick();
    line.textContent = said.textContent;
  }
})();

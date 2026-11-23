// The generator. The one script on the site. It takes shapes in as JSON and turns the
// ones it knows into running code, in this tab. It holds the grammar of a step and how
// to draw a board; which stores and verbs exist, and what each does, is in the contract.
// Text is never run as code here, and the page's policy makes the browser refuse it.
// What the board is and holds can be kept as plain JSON on floppies and rebuilt from them.
// Beside the board it takes sheets: JSONs that name no device. What it makes of them is
// this browser's answer; generator.py makes a terminal's answer from the same files.
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

  // ---- the sheets: JSONs loaded beside the board, in any order --------------------------
  // A sheet says what exists and what moves, and names no device: nothing of a screen, a
  // key, a button or where a thing is kept. It has an id of two levels and may bring
  // kinds (a name and its parts), boxes (each holds things of one kind) and moves. A move
  // is one thing going from somewhere to somewhere: "from" a box or, left out, from
  // whoever is at the device, who makes it; "to" a box or, left out, to them; "when"
  // names a box, and the move then happens by itself for each thing that arrives there;
  // "after" is a wait in seconds; "with" fixes some of the thing's parts. That is all a
  // sheet can say. How a move is offered, how a thing is shown and where a box is kept is
  // this generator's own business, and another device's generator answers its own way.
  // Nothing happens because a sheet was loaded: each time the loaded set changes the
  // page is drawn again from all of it, in the order of the addresses.
  let contract, forget = null, drawn = 0;
  const loaded = new Map(), timers = new Set(), shownTo = new Map();
  const NAME = /^[^./\\]+$/, ID = /^[^./\\]+\.[^./\\]+$/, AT = /^[^./\\]+\.[^./\\]+\.[^./\\]+$/;
  const plain = (x) => !!x && typeof x === "object" && !Array.isArray(x);
  const only = (x, keys, what) => { for (const k of Object.keys(x)) if (!keys.includes(k)) refuse(`${what}: the generator does not know "${k}"`); };
  const checkedMove = (m, what) => {
    if (!plain(m)) refuse(`${what} is not a move`);
    only(m, ["from", "to", "when", "after", "with"], what);
    for (const k of ["from", "to", "when"]) if (k in m && (typeof m[k] !== "string" || !AT.test(m[k]))) refuse(`${what}: "${k}" needs the address of a box, like email.wire.inbox`);
    if ("after" in m && !(typeof m.after === "number" && m.after >= 0 && m.after <= 86400)) refuse(`${what}: "after" is a wait in seconds`);
    if ("with" in m && (!plain(m.with) || !Object.values(m.with).every((v) => typeof v === "string"))) refuse(`${what}: "with" names parts and the words they get`);
    if (m.when && m.from) refuse(`${what}: a move that happens by itself takes the thing that arrived`);
    if (!m.from && !m.to && !m.when) refuse(`${what}: a move needs a from or a to`);
    return m;
  };
  const checked = (j) => {
    if (!plain(j) || typeof j.id !== "string" || !ID.test(j.id)) refuse("a JSON needs an id of two levels, like email.wire");
    only(j, ["id", "says", "kinds", "boxes", "moves"], j.id);
    const names = new Set();
    for (const key of ["kinds", "boxes", "moves"]) {
      if (j[key] == null) continue;
      if (!plain(j[key])) refuse(`${j.id}: ${key} must be named`);
      for (const [name, v] of Object.entries(j[key])) {
        if (!NAME.test(name)) refuse(`${j.id}: "${name}" cannot be the third level of an address`);
        if (names.has(name)) refuse(`${j.id}: two things are called ${name}`);
        names.add(name);
        if (key === "kinds" && !(Array.isArray(v) && v.length && v.every((p) => typeof p === "string" && p) && new Set(v).size === v.length)) refuse(`${j.id}.${name}: a kind lists its parts`);
        if (key === "boxes" && !(typeof v === "string" && (NAME.test(v) || AT.test(v)))) refuse(`${j.id}.${name}: a box names the kind it holds`);
        if (key === "moves") checkedMove(v, `${j.id}.${name}`);
      }
    }
    return j;
  };
  // The dot is the folder: email.wire is the file email/wire.json on this site.
  const fetched = async (id) => {
    if (!/^[\w-]+\.[\w-]+$/.test(id)) refuse(`${id} is not the address of a JSON on this site`);
    const got = await fetch(new URL(`${id.replace(".", "/")}.json`, document.baseURI), { cache: "no-store" });
    const j = got.ok ? await got.json().catch(() => null) : null;
    if (!j || j.id !== id) refuse(`the site has no JSON called ${id}`);
    return j;
  };
  const every = (key) => [...loaded.keys()].sort().flatMap((id) => Object.entries(loaded.get(id)[key] || {}).map(([name, v]) => ({ id, name, at: `${id}.${name}`, key, v })));
  const byAt = (a, b) => (a.at < b.at ? -1 : a.at > b.at ? 1 : 0);
  // The kind a box holds, or what it waits for when that is not loaded.
  const kindOf = (boxAt) => {
    const b = every("boxes").find((x) => x.at === boxAt);
    if (!b) return { waits: boxAt };
    const at = AT.test(b.v) ? b.v : `${b.id}.${b.v}`, k = every("kinds").find((x) => x.at === at);
    return k ? { at, name: k.name, parts: k.v } : { waits: at };
  };
  // Where this generator keeps what the boxes hold: one database of its own in the browser.
  const boxes = (mode, fn) => new Promise((ok, no) => {
    const open = indexedDB.open("sheets", 1);
    open.onupgradeneeded = () => open.result.createObjectStore("boxes");
    open.onerror = () => no(open.error);
    open.onsuccess = () => {
      const db = open.result, t = db.transaction("boxes", mode);
      let out;
      fn(t.objectStore("boxes"), (x) => { out = x; });
      t.oncomplete = () => { db.close(); ok(out); };
      t.onerror = t.onabort = () => { db.close(); no(t.error); };
    };
  });
  const listed = (x) => (Array.isArray(x) ? x : []);
  const inBox = (at) => boxes("readonly", (s, out) => { const r = s.get(at); r.onsuccess = () => out(listed(r.result)); });
  const putIn = (at, thing) => boxes("readwrite", (s) => { const r = s.get(at); r.onsuccess = () => s.put([...listed(r.result), thing], at); });
  const setBox = (at, list) => boxes("readwrite", (s) => s.put(list, at));
  const emptyBoxes = () => boxes("readwrite", (s) => s.clear());

  // A thing arrives in a box, and every loaded move that waits on that box is told.
  const arrive = async (boxAt, thing, by, hops) => {
    const kind = kindOf(boxAt);
    if (kind.waits) refuse(`${by} waits for ${kind.waits}, which is not loaded`);
    const it = Object.fromEntries(kind.parts.map((p) => [p, word(thing[p])]));
    await putIn(boxAt, it);
    if (hops < 8) for (const m of every("moves")) if (m.v.when === boxAt) { try { await carry(m, it, hops + 1); } catch { /* one that cannot go does not stop the rest */ } }
    return kind;
  };
  // The rest of a move once its thing is in hand: fix the parts it names, wait, hand it on.
  const carry = async (m, thing, hops = 0) => {
    const it = { ...thing, ...(m.v.with || {}) };
    const go = async () => {
      if (m.v.to) return `${m.at}: a ${(await arrive(m.v.to, it, m.at, hops)).name} went to ${m.v.to}`;
      if (!m.id) return JSON.stringify(it);
      shownTo.set(m.at, it);
      return `${m.at}: ${word(Object.values(it)[0])}`;
    };
    if (!(m.v.after > 0)) return go();
    if (m.v.to && kindOf(m.v.to).waits) refuse(`${m.at} waits for ${kindOf(m.v.to).waits}, which is not loaded`);
    const t = { by: m.id };
    t.id = setTimeout(async () => {
      timers.delete(t);
      try { tell(await go()); } catch (e) { tell(e instanceof Refused ? `refused: ${e.message}` : `could not: ${e && e.message}`); }
      await draw();
    }, m.v.after * 1000);
    timers.add(t);
    return `${m.at}: in ${m.v.after} s it goes to ${m.v.to || "whoever is here"}`;
  };
  // A move done by whoever is at the device, or handed in through Shape.
  const doMove = async (m, given) => {
    if (m.v.when) refuse(`${m.at} happens by itself, when a thing arrives in ${m.v.when}`);
    if (!m.v.from) {
      const kind = kindOf(m.v.to), mine = plain(given.with) ? given.with : {};
      if (kind.waits) refuse(`${m.at} waits for ${kind.waits}, which is not loaded`);
      if (!kind.parts.some((p) => word({ ...mine, ...(m.v.with || {}) }[p]).trim())) refuse(`${m.at} needs a ${kind.name}: ${kind.parts.join(", ")}`);
      return carry(m, mine);
    }
    const kind = kindOf(m.v.from);
    if (kind.waits) refuse(`${m.at} waits for ${kind.waits}, which is not loaded`);
    const list = await inBox(m.v.from);
    if (given.pick == null && !m.id && !m.v.to) return JSON.stringify(list);
    return carry(m, list[Number(given.pick) - 1] || refuse(`${m.v.from} holds ${list.length}; pick one by its number, from 1`));
  };

  // What this generator makes of the loaded sheets, in this browser: every kind, box and
  // move gets a place under its address. A move from whoever is here becomes fields and
  // a button; a move from a box makes that box's rows touchable.
  const made = el("main", null, { class: "made", hidden: "" });
  const bar = el("header"), loadedLine = el("p", "nothing is loaded", { class: "says" }), heard = el("output", null, { class: "says", "aria-live": "polite" });
  const toBoard = el("button", "Board", { type: "button", title: "The board, where JSONs are loaded and unloaded" });
  bar.append(toBoard, loadedLine, heard);
  made.append(bar);
  made.addEventListener("click", async (e) => {
    const b = e.target.closest && e.target.closest("[data-do]");
    if (!b) return;
    const shape = { do: b.dataset.do }, fields = [...b.closest("section").querySelectorAll("[name]")];
    if (b.dataset.pick) shape.pick = Number(b.dataset.pick);
    if (fields.length) shape.with = Object.fromEntries(fields.map((f) => [f.name, f.value]));
    await give(shape);
  });
  const draw = async () => {
    const mine = ++drawn;
    for (const t of [...timers]) if (t.by && !loaded.has(t.by)) { clearTimeout(t.id); timers.delete(t); }
    const moves = every("moves");
    for (const at of [...shownTo.keys()]) if (!moves.some((m) => m.at === at)) shownTo.delete(at);
    const key = (f) => `${f.closest("section").id} ${f.name}`;
    const typed = new Map([...made.querySelectorAll("section [name]")].map((f) => [key(f), f.value]));
    const active = document.activeElement, focus = active && active.name && made.contains(active) ? key(active) : null;
    const ids = [...loaded.keys()].sort(), secs = [];
    for (const x of ["kinds", "boxes", "moves"].flatMap(every).sort(byAt)) {
      const sec = el("section", null, { id: x.at });
      sec.append(el("h2", x.at));
      const m = x.v, ends = x.key === "moves" ? [m.when, m.from, m.to].filter(Boolean).map(kindOf) : x.key === "boxes" ? [kindOf(x.at)] : [];
      const lacks = ends.find((k) => k.waits), kind = ends[0];
      if (lacks) sec.append(el("p", `waits for ${lacks.waits}, which is not loaded`));
      else if (x.key === "kinds") sec.append(el("p", `a ${x.name} has: ${x.v.join(", ")}`));
      else if (x.key === "boxes") {
        const list = await inBox(x.at), picks = moves.filter((p) => p.v.from === x.at), rows = el("div");
        sec.append(el("p", `holds ${list.length} ${kind.name}`));
        list.forEach((thing, i) => {
          const first = word(thing[kind.parts[0]]) || `(no ${kind.parts[0]})`;
          if (!picks.length) rows.append(el("p", first));
          for (const p of picks) rows.append(el("button", picks.length > 1 ? `${p.name}: ${first}` : first, { type: "button", "data-do": p.at, "data-pick": i + 1 }));
        });
        if (list.length) sec.append(rows);
      } else if (m.when) {
        sec.append(el("p", `when a ${kind.name} arrives in ${m.when}, ${m.after > 0 ? `after ${m.after} s ` : ""}it goes to ${m.to || "whoever is here"}`
          + (m.with ? `, with ${Object.entries(m.with).map(([k, v]) => `${k}: ${v}`).join("; ")}` : "")));
      } else if (m.from) {
        const it = shownTo.get(x.at);
        sec.append(el("p", `touch a ${kind.name} in ${m.from}${m.to ? `; it goes to ${m.to}` : ""}`));
        if (it) { const dl = el("dl"); for (const [k, v] of Object.entries(it)) dl.append(el("dt", k), el("dd", v)); sec.append(dl); }
      } else {
        kind.parts.forEach((part, i) => {
          if (m.with && part in m.with) return;
          const f = el(i ? "textarea" : "input", null, { name: part, autocomplete: "off", autocapitalize: "off", spellcheck: "false" }), label = el("label", part + " ");
          if (forget !== x.at && typed.has(`${x.at} ${part}`)) f.value = typed.get(`${x.at} ${part}`);
          label.append(f);
          sec.append(label);
        });
        sec.append(el("button", x.name, { type: "button", "data-do": x.at }));
      }
      secs.push(sec);
    }
    if (mine !== drawn) return;   // a later draw has already begun; it will show what is true
    forget = null;
    loadedLine.textContent = ids.length ? `loaded: ${ids.join(", ")}` : "nothing is loaded";
    made.replaceChildren(bar, ...secs);
    if (focus) for (const f of made.querySelectorAll("section [name]")) if (key(f) === focus) f.focus();
  };

  // ---- running a shape ----------------------------------------------------------------
  const envOf = (words) => ({ words, named: {}, missing: false });
  const runVerb = async (shape, undoing) => {
    const store = contract.stores.find((s) => s.store === shape.store) || refuse(`no store is called ${shape.store}`);
    const verb = (store.verbs || []).find((v) => v.verb === shape.verb) || refuse(`${shape.store} has no verb called ${shape.verb}`);
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
    return { what: `${shape.store} ${verb.verb}`, said, code: code(steps, env), back };
  };
  const runSteps = async (shape) => {
    const steps = known(shape.steps, (contract && contract.parts) || {}), env = envOf({ Name: word(shape.Name), Value: word(shape.Value) });
    const out = await walk(steps, env);
    return { what: "steps", said: env.missing ? "there was nothing there to act on" : word(out).slice(0, 200) || "done", code: code(steps, env), back: null };
  };

  // ---- the board ----------------------------------------------------------------------
  const board = el("main", null, { class: "board" });
  const head = el("header"), title = el("h1"), says = el("p", null, { class: "says" });
  const toPage = el("button", "Page", { type: "button", title: "What the loaded JSONs make", hidden: "" });
  head.append(title, toPage, says);
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
  document.body.append(cover, board, made);

  let store, verb, original;
  const log = [], undone = [];
  const tell = (text) => { said.textContent = heard.textContent = text; };
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
  const ENGINE = "2", FLOPPY = 1474560;
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
    const recs = [{ board: rest }, ...all.map((s) => ({ store: s })), ...[...loaded.keys()].sort().map((id) => ({ json: loaded.get(id) }))];
    const parts = contract.parts || {};
    for (const s of all) {
      const where = s.store;
      if (!s.keep) continue;
      let got;
      try { got = await walk(known(s.holds || [], parts), envOf({})); } catch { recs.push({ left: where }); continue; }
      if (got instanceof Element) { for (const n of got.childNodes) { const thing = tree(n); if (thing != null) recs.push({ in: where, thing }); } continue; }
      const pairs = rowsOf(got).sort((a, b) => (a[0] < b[0] ? -1 : a[0] > b[0] ? 1 : 0));
      for (const [name, value] of pairs) recs.push(value === undefined ? { in: where, name } : { in: where, name, value });
    }
    // What the boxes of the loaded sheets hold: one record a thing, the same on any device.
    for (const b of every("boxes").sort(byAt)) if (!kindOf(b.at).waits) for (const is of await inBox(b.at)) recs.push({ at: b.at, is });
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
    if (head && !plain(head.board)) refuse("the floppy holds no board");
    // A floppy written by a generator that has no board of its own carries only sheets and
    // what their boxes hold; the board is then the one this site shipped with.
    const c = head ? { ...head.board, stores: of("store").map((r) => r.store) } : original || refuse("the floppy holds no board");
    const things = new Map();
    for (const r of of("is")) if (typeof r.at === "string" && plain(r.is)) things.set(r.at, [...(things.get(r.at) || []), Object.fromEntries(Object.entries(r.is).map(([k, v]) => [k, word(v)]))]);
    const left = new Set(of("left").map((r) => r.left));
    const grown = of("thing").map((r) => [r.in, grow(r.thing)]);
    const sheets = of("json").map((r) => checked(r.json));
    await build(c);   // refused here, before anything is wiped, if the board on the floppy is not one the generator knows
    // Everything goes first: every kept store is emptied, every loaded JSON is taken out,
    // the site is brought back to the board it shipped with, and only then is it rebuilt.
    const empty = async () => { for (const s of contract.stores) if (s.keep && s.keep.empty) { try { await quiet(s.keep.empty); } catch { /* not in this browser */ } } };
    await empty();
    await emptyBoxes();
    loaded.clear();
    shownTo.clear();
    for (const t of timers) clearTimeout(t.id);
    timers.clear();
    if (original) {
      await build(original);
      await empty();
      await build(c);
    }
    for (const j of sheets) loaded.set(j.id, j);
    for (const [at, list] of things) await setBox(at, list);
    log.length = undone.length = 0;
    codeLine.textContent = "";
    const failed = [];
    const parts = contract.parts || {};
    for (const s of contract.stores) {
      const where = s.store;
      if (!s.keep || left.has(where)) continue;
      try {
        if (s.keep.empty) await quiet(s.keep.empty);
        const mine = grown.filter(([w]) => w === where);
        if (mine.length) (await walk(known(s.holds || [], parts), envOf({}))).append(...mine.map(([, node]) => node));
        if (s.keep.each) for (const r of of("name")) if (r.in === where) await quiet(given(s.keep.each, envOf({ name: word(r.name), value: word(r.value) })));
      } catch { failed.push(where); }
    }
    await draw();
    toPage.hidden = !loaded.size;
    const now = await records();
    const same = labelOf(head ? now : now.filter((r) => "json" in r || "is" in r), ENGINE) === labelOf(recs, ENGINE);
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
      if ("load" in given || ("id" in given && ("kinds" in given || "boxes" in given || "moves" in given))) {
        const j = checked(!("load" in given) ? given : typeof given.load === "string" ? await fetched(given.load) : given.load);
        loaded.set(j.id, j);
        await draw();
        log.push(JSON.stringify(given));
        tell(`loaded ${j.id}`);
        codeLine.textContent = "";
        if (!board.hidden || !cover.hidden) page();
      } else if ("unload" in given) {
        if (!loaded.delete(given.unload)) refuse(`${word(given.unload)} is not loaded`);
        await draw();
        log.push(JSON.stringify(given));
        tell(`unloaded ${given.unload}`);
        codeLine.textContent = "";
        if (!loaded.size && !made.hidden) await enter();
      } else if ("do" in given || (("from" in given || "to" in given) && !("store" in given) && !("steps" in given))) {
        // A move: one a loaded sheet names, or one handed in whole, which goes once, now.
        if (!("do" in given) && "when" in given) refuse("only a loaded JSON can wait for a thing to arrive");
        const m = "do" in given ? every("moves").find((x) => x.at === given.do) || refuse(`${word(given.do)} is not loaded`)
          : { id: "", name: "shape", at: "shape", v: checkedMove(Object.fromEntries(["from", "to", "after", "with"].filter((k) => k in given).map((k) => [k, given[k]])), "shape") };
        const out = await doMove(m, given);
        if (m.id && !m.v.from) forget = m.at;
        await draw();
        log.push(JSON.stringify(given));
        tell(out);
        codeLine.textContent = "";
      } else if ("stores" in given) {
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
    toPage.hidden = !loaded.size;
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
  const enter = async () => { cover.hidden = made.hidden = true; board.hidden = false; showRan(); await show(); };
  const page = () => { cover.hidden = board.hidden = true; made.hidden = false; };
  way.onclick = enter;
  toBoard.onclick = enter;
  toPage.onclick = page;
  // The same two things for a script or another seat: serialize gives the floppies as
  // JSON text, deserialize takes them back, as text or parsed, one or many, in any order.
  const parsed = (x) => (typeof x === "string" ? JSON.parse(x) : x);
  globalThis.board = Object.freeze({
    engine: ENGINE,
    enter,
    page,
    load: async (what) => { await give({ load: what }); return said.textContent; },
    unload: async (id) => { await give({ unload: id }); return said.textContent; },
    do: async (move) => { await give(move); return said.textContent; },
    loaded: () => [...loaded.keys()].sort(),
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
  } else if (address === "explore" && contract) {
    // The whole field of interaction on one page, written out from the contract: every
    // door, address, script call, store and verb, and the grammar. Read, not operated.
    const field = el("main", null, { class: "field" });
    const part = (name, ...inside) => { const sec = el("section"); sec.append(el("h2", name), ...inside); return sec; };
    const pairs = (all) => { const dl = el("dl"); for (const [k, v] of all) dl.append(el("dt", word(k)), el("dd", word(v))); return dl; };
    const go = el("button", "Go in", { type: "button" });
    go.onclick = () => { field.hidden = true; history.replaceState(history.state, "", "./"); enter(); };
    const top = el("header");
    top.append(el("h1", contract.title || ""), go);
    const cols = el("div", null, { class: "cols" });
    field.append(top, cols);
    for (const [key, v] of Object.entries(contract)) {
      if (key === "title" || key === "screen" || key === "parts") continue;
      if (key === "stores") {
        for (const s of v) cols.append(part(`store: ${s.store}`, el("p", `${s.is || ""} ${s.keep ? "Kept on a floppy." : `Not kept on a floppy. ${s["not kept"] || ""}`}`),
          pairs((s.verbs || []).map((x) => [[x.verb, ...(x.needs || []), ...(x.may || []).map((m) => `${m}?`)].join(" "), x.does || ""]))));
      } else if (typeof v === "string") cols.append(part(key, el("p", v)));
      else if (Array.isArray(v)) cols.append(v.every((x) => x && typeof x === "object") ? part(key, pairs(v.map((x) => Object.values(x)))) : part(key, ...v.map((x) => el("p", word(x)))));
      else if (v && typeof v === "object") cols.append(part(key, pairs(Object.entries(v))));
    }
    cover.hidden = true;
    document.body.append(field);
  } else if ((address === "" || address === "index") && contract && Array.isArray(contract.examples)) {
    // Shipped examples on the cover: each is a name, a line and a list of shapes. Touching one
    // hands its shapes to the one way in, as Shape would, and opens the page they make.
    const examples = el("nav", null, { class: "examples", "aria-label": "Shipped examples" });
    for (const x of contract.examples) {
      if (!x || typeof x.name !== "string" || !Array.isArray(x.shapes)) continue;
      const b = el("button", null, { type: "button" });
      b.append(el("b", x.name), el("span", typeof x.says === "string" ? x.says : ""));
      b.onclick = async () => { await give(x.shapes); if (loaded.size) page(); };
      examples.append(b);
    }
    if (examples.children.length) (cover.querySelector(".plate") || cover).append(examples);
  }
})();

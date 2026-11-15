// The board. It is built from contract.json: every store and verb named there becomes a
// knob here. Nothing is sent anywhere; every verb acts on what this tab already holds.
(async () => {
  const el = (kind, text, attrs) => {
    const node = document.createElement(kind);
    if (text != null) node.append(text);
    for (const [k, v] of Object.entries(attrs || {})) node.setAttribute(k, v);
    return node;
  };
  let contract;
  try { contract = await (await fetch("contract.json", { cache: "no-store" })).json(); }
  catch { document.body.append(el("p", "The board could not read contract.json.")); return; }

  // ---- stores that keep a value under a name ------------------------------------------
  const enc = encodeURIComponent;
  const plain = (s) => { try { return decodeURIComponent(s); } catch { return s; } };
  const reach = (get) => { try { return get(); } catch { return null; } };

  const web = (s) => ({
    all: async () => Array.from({ length: s.length }, (_, i) => s.key(i)).map((k) => [k, s.getItem(k)]),
    get: async (n) => s.getItem(n),
    put: async (n, v) => s.setItem(n, v),
    remove: async (n) => s.removeItem(n),
    clear: async () => s.clear(),
  });

  const table = (mode, work) => new Promise((ok, no) => {
    const open = indexedDB.open("board", 1);
    open.onupgradeneeded = () => open.result.createObjectStore("things");
    open.onerror = () => no(open.error);
    open.onsuccess = () => {
      const db = open.result, t = db.transaction("things", mode), out = work(t.objectStore("things"));
      t.oncomplete = () => { db.close(); ok(out()); };
      t.onerror = t.onabort = () => { db.close(); no(t.error); };
    };
  });
  const indexed = {
    all: () => table("readonly", (s) => { const k = s.getAllKeys(), v = s.getAll(); return () => k.result.map((key, i) => [String(key), String(v.result[i])]); }),
    get: (n) => table("readonly", (s) => { const r = s.get(n); return () => r.result ?? null; }),
    put: (n, v) => table("readwrite", (s) => { s.put(v, n); return () => null; }),
    remove: (n) => table("readwrite", (s) => { s.delete(n); return () => null; }),
    clear: () => table("readwrite", (s) => { s.clear(); return () => null; }),
  };

  const jar = () => document.cookie.split("; ").filter(Boolean).map((c) => {
    const i = c.indexOf("=");
    return [plain(c.slice(0, i)), plain(c.slice(i + 1))];
  });
  const bake = (n, v, age) => { document.cookie = `${enc(n)}=${enc(v)}; path=/; max-age=${age}; samesite=lax`; };
  const cookie = {
    all: async () => jar(),
    get: async (n) => (jar().find(([k]) => k === n) || [])[1] ?? null,
    put: async (n, v) => bake(n, v, 31536000),
    remove: async (n) => bake(n, "", 0),
    clear: async () => jar().forEach(([k]) => bake(k, "", 0)),
  };

  // A cache entry needs an address. These are never asked for; they only name the entry.
  const shelf = () => caches.open("board");
  const spot = (n) => new URL("held/" + enc(n), location.origin + location.pathname).href;
  const cache = {
    all: async () => { const c = await shelf(); return Promise.all((await c.keys()).map(async (r) => [plain(r.url.split("/").pop()), await (await c.match(r)).text()])); },
    get: async (n) => { const r = await (await shelf()).match(spot(n)); return r ? r.text() : null; },
    put: async (n, v) => (await shelf()).put(spot(n), new Response(v, { headers: { "content-type": "text/plain" } })),
    remove: async (n) => (await shelf()).delete(spot(n)),
    clear: async () => caches.delete("board"),
  };

  const none = (n) => ({ said: `nothing is called ${n}` });
  const kept = (s) => ({
    put: async (n, v) => { const old = await s.get(n); await s.put(n, v); return { said: `${n} = ${v}`, undo: () => (old == null ? s.remove(n) : s.put(n, old)) }; },
    get: async (n) => { const v = await s.get(n); return v == null ? none(n) : { said: `${n} holds ${v}` }; },
    remove: async (n) => { const old = await s.get(n); if (old == null) return none(n); await s.remove(n); return { said: `${n} is forgotten`, undo: () => s.put(n, old) }; },
    clear: async () => { const all = await s.all(); await s.clear(); return { said: `${all.length} forgotten`, undo: async () => { for (const [n, v] of all) await s.put(n, v); } }; },
  });

  // ---- the page itself -----------------------------------------------------------------
  const KINDS = new Set(("p span div b i em strong mark small code pre h2 h3 hr ul ol li dl dt dd table tbody tr td th " +
    "button input textarea select option label details summary fieldset legend progress meter output").split(" "));
  const REFUSED = /^(on.*|style|src|srcset|href|action|formaction|data|ping|poster|background|data-name)$/i;
  const stage = el("div", null, { class: "stage" });
  const things = () => [...stage.querySelectorAll("[data-name]")];
  const thing = (n) => things().find((e) => e.dataset.name === n);
  const fielded = (e) => e.localName === "input" || e.localName === "textarea";
  const own = (e) => fielded(e) ? e.value : [...e.childNodes].filter((c) => c.nodeType === 3).map((c) => c.data).join("");
  const reword = (e, text) => {
    if (fielded(e)) { e.value = text; return; }
    for (const c of [...e.childNodes]) if (c.nodeType === 3) c.remove();
    if (text) e.prepend(text);
  };
  const place = (e) => { const parent = e.parentNode, next = e.nextSibling; return () => parent.insertBefore(e, next); };
  const made = {
    make: async (n, v) => {
      const kind = v.trim().toLowerCase();
      if (!KINDS.has(kind)) return { said: `refused: the board does not make a ${kind}` };
      if (thing(n)) return { said: `${n} is already here` };
      const e = el(kind, null, { "data-name": n });
      stage.append(e);
      return { said: `${n} is a ${kind}`, undo: () => e.remove() };
    },
    say: async (n, v) => { const e = thing(n); if (!e) return none(n); const old = own(e); reword(e, v); return { said: `${n} says ${v}`, undo: () => reword(e, old) }; },
    set: async (n, v) => {
      const e = thing(n); if (!e) return none(n);
      const i = v.indexOf("="), name = (i < 0 ? v : v.slice(0, i)).trim().toLowerCase(), value = i < 0 ? "" : v.slice(i + 1);
      if (!/^[a-z][a-z0-9-]*$/.test(name) || REFUSED.test(name)) return { said: `refused: the board does not set ${name || "that"}` };
      const old = e.getAttribute(name);
      const put = (to) => (to == null || to === "" ? e.removeAttribute(name) : e.setAttribute(name, to));
      put(value);
      return { said: value === "" ? `${n} no longer has ${name}` : `${n} has ${name}=${value}`, undo: () => put(old) };
    },
    move: async (n, v) => {
      const e = thing(n); if (!e) return none(n);
      const into = v.trim() ? thing(v.trim()) : stage;
      if (!into) return none(v.trim());
      if (into === e || e.contains(into)) return { said: "refused: a thing cannot go inside itself" };
      const back = place(e);
      into.append(e);
      return { said: into === stage ? `${n} is at the end` : `${n} is inside ${v.trim()}`, undo: back };
    },
    read: async (n) => {
      const e = thing(n); if (!e) return none(n);
      const has = [...e.attributes].filter((a) => a.name !== "data-name").map((a) => `${a.name}=${a.value}`).join(", ");
      return { said: `${n} is a ${e.localName}` + (own(e) ? ` saying ${own(e)}` : "") + (has ? ` with ${has}` : "") };
    },
    remove: async (n) => { const e = thing(n); if (!e) return none(n); const back = place(e); e.remove(); return { said: `${n} is out of the page`, undo: back }; },
    clear: async () => { const all = [...stage.children]; stage.replaceChildren(); return { said: `${all.length} taken out`, undo: () => stage.append(...all) }; },
  };

  // ---- history: the address moves, nothing loads --------------------------------------
  // The board only steps among entries made since this page loaded. Stepping to an older
  // one would make the browser load the page again.
  const entry = () => (history.state && typeof history.state.board === "number" ? history.state : { board: 0 });
  const floor = entry().board;
  let top = floor;
  const step = (go) => new Promise((ok) => { addEventListener("popstate", () => ok(), { once: true }); go(); });
  const where = () => location.hash || "the start";
  const past = {
    push: async (n, v) => { top = entry().board + 1; history.pushState({ board: top, name: n, value: v }, "", "#" + enc(n)); return { said: `now at #${n}`, undo: () => step(() => history.back()) }; },
    replace: async (n, v) => { const old = [history.state, location.href]; history.replaceState({ board: entry().board, name: n, value: v }, "", "#" + enc(n)); return { said: `this entry is now #${n}`, undo: async () => history.replaceState(old[0], "", old[1]) }; },
    back: async () => { if (entry().board <= floor) return { said: "refused: nothing behind this that the board made in this visit" }; await step(() => history.back()); return { said: `now at ${where()}`, undo: () => step(() => history.forward()) }; },
    forward: async () => { if (entry().board >= top) return { said: "nothing ahead" }; await step(() => history.forward()); return { said: `now at ${where()}`, undo: () => step(() => history.back()) }; },
    peek: async () => ({ said: `at ${where()}` + (entry().value ? `, carrying ${entry().value}` : "") }),
  };
  const trail = { all: async () => [["address", where()], ["carries", entry().value || "nothing"], ["made in this visit", String(top - floor)], ["tab history length", String(history.length)]] };

  const STORES = { local: reach(() => web(localStorage)), session: reach(() => web(sessionStorage)), indexed, cookie, cache, history: trail };
  const VERBS = { dom: made, history: past };
  for (const name of ["local", "session", "indexed", "cookie", "cache"]) VERBS[name] = kept(STORES[name]);

  // ---- the board ----------------------------------------------------------------------
  const board = el("main", null, { class: "board" });
  const head = el("header");
  head.append(el("h1", contract.title), el("p", contract.says, { class: "says" }));
  const stores = el("section", null, { class: "knob", "aria-label": "Store" });
  const verbs = el("section", null, { class: "knob", "aria-label": "Verb" });
  const name = el("input", null, { autocomplete: "off", autocapitalize: "off", spellcheck: "false" });
  const value = el("input", null, { autocomplete: "off", autocapitalize: "off", spellcheck: "false" });
  const fields = el("section", null, { class: "fields" });
  const nameLabel = el("label", "Name "), valueLabel = el("label", "Value ");
  nameLabel.append(name); valueLabel.append(value);
  fields.append(nameLabel, valueLabel);
  const doIt = el("button", "Do", { type: "button" }), undoIt = el("button", "Undo", { type: "button" });
  const acts = el("section", null, { class: "act" });
  acts.append(doIt, undoIt);
  const said = el("output", "Ready.", { class: "said", "aria-live": "polite" });
  const held = el("section", null, { class: "held", "aria-label": "What the store holds" });
  const heading = el("h2"), rows = el("div", null, { class: "rows" });
  held.append(heading, rows, stage);
  board.append(head, stores, verbs, fields, acts, said, held);
  document.body.append(board);

  let store, verb;
  const undone = [];
  const tell = (text) => { said.textContent = text; };
  const pressed = (group, button) => { for (const b of group.children) b.setAttribute("aria-pressed", String(b === button)); };
  const count = (n) => `${n} ${n === 1 ? "thing" : "things"}`;

  const show = async () => {
    const on = store.store;
    stage.hidden = on !== "dom";
    rows.hidden = on === "dom";
    if (on === "dom") { heading.textContent = `the page holds ${count(things().length)} made here`; return; }
    let pairs;
    try { pairs = await STORES[on].all(); }
    catch { heading.textContent = `${on} is not available in this browser`; rows.replaceChildren(); return; }
    heading.textContent = on === "history" ? "history, in this tab" : `${on} holds ${count(pairs.length)}`;
    rows.replaceChildren(...pairs.map(([n, v]) => {
      const row = el("button", `${n} = ${v}`, { type: "button" });
      row.onclick = () => { if (!name.disabled) name.value = n; if (!value.disabled) value.value = v; };
      return row;
    }));
    let more = 0;   // only what fits is shown, and the rest is counted, so nothing scrolls
    while (rows.scrollHeight > rows.clientHeight + 1 && rows.children.length > 1) { rows.lastChild.remove(); more++; }
    if (more) { rows.lastChild.remove(); rows.append(el("p", `and ${more + 1} more`)); }
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
    verbs.replaceChildren(...s.verbs.map((v) => {
      const b = el("button", v.verb, { type: "button", title: v.does });
      b.disabled = !(VERBS[s.store] && VERBS[s.store][v.verb]);
      b.onclick = () => { pick(v, b); tell(v.does); };
      return b;
    }));
    const first = [...verbs.children].findIndex((b) => !b.disabled);
    if (first >= 0) pick(s.verbs[first], verbs.children[first]);
    await show();
  };

  const act = async () => {
    if (!verb) return;
    const n = name.value.trim(), v = value.value;
    for (const need of verb.needs || []) if (!(need === "Name" ? n : v.trim())) return tell(`${verb.verb} needs a ${need}`);
    const what = `${store.store} ${verb.verb}`;
    try {
      const out = await VERBS[store.store][verb.verb](n, v);
      tell(`${what}: ${out.said}`);
      if (out.undo) undone.push({ what: n ? `${what} ${n}` : what, undo: out.undo });
      name.value = value.value = "";
    } catch { tell(`${what}: not available in this browser`); }
    await show();
  };

  const undo = async () => {
    const last = undone.pop();
    if (!last) return tell("nothing to undo");
    try { await last.undo(); tell(`undone: ${last.what}`); } catch { tell(`could not undo: ${last.what}`); }
    await show();
  };

  doIt.onclick = act;
  undoIt.onclick = undo;
  for (const field of [name, value]) field.onkeydown = (e) => { if (e.key === "Enter") act(); };
  addEventListener("popstate", () => show());

  for (const s of contract.stores) {
    const b = el("button", s.store, { type: "button", title: s.is });
    b.disabled = !VERBS[s.store];
    b.onclick = async () => { await choose(s, b); tell(s.is); };
    stores.append(b);
  }
  const first = [...stores.children].findIndex((b) => !b.disabled);
  if (first >= 0) await choose(contract.stores[first], stores.children[first]);
})();

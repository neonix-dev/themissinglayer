// The site's own engine. It receives data and builds what the data asks for.
// Data is never run: no script, no style, no handler, nothing brought in from another site.
// A page is { "contract": what is wanted, "base": which native piece each word becomes,
// "at": optional folder its addresses are relative to }. The format is the one in GUIDE.md.
// Every piece has a name: the id it came with, or one the engine gives it. What is built
// is clay: a reader picks a piece by name and moves, changes, copies, removes or adds to it,
// and the engine writes the page down again as it then stands.
(() => {
  "use strict";
  const KEY = "themissinglayer.build.v1";
  const NEVER = new Set(["script", "style", "iframe", "frame", "frameset", "object", "embed", "link", "meta",
    "base", "template", "slot", "portal", "applet", "noscript", "svg", "math", "html", "head", "body", "title"]);
  const NOT_SET = new Set(["style", "srcdoc", "srcset", "ping", "is", "nonce", "integrity", "http-equiv"]);
  const ADDRESS = new Set(["href", "src", "action", "formaction", "poster", "background", "cite", "data"]);

  const STARTER = {
    contract: {
      title: "An empty sheet",
      says: "This page was built from data by the site's own engine. Open Build above and change it.",
      sections: [
        { heading: "What you can do", text: "Change any field, add a section, or give the engine a whole page as data." },
        { heading: "What the engine will not do", text: "Run anything. Scripts, styles, handlers and other sites are refused." }
      ]
    },
    base: {
      head: [["title", "{title}"]],
      body: [["h1", "{title}"], ["p", "{says}"], ["main", ["each", "sections"]]],
      words: [["heading", ["details", { name: "sections" }, ["summary", "{heading}"], ["p", "{text}"]]]]
    }
  };
  const EXAMPLES = {
    "Empty sheet": null,
    "Root page": { contract: "../contract.json", base: "../instrument/window.json", at: "../" },
    "Four paths": { contract: "../second/contract.json", base: "../second/sheet.json", at: "../second/" }
  };

  let page, refused, later, fromLink = false;
  const shapes = {};

  const el = (kind, text, attrs) => {
    const node = document.createElement(kind);
    if (text != null) node.append(text);
    for (const [k, v] of Object.entries(attrs || {})) node.setAttribute(k, v);
    return node;
  };

  // ---- building: data in, native pieces out -------------------------------------------
  const slug = (s) => s.toLowerCase().replace(/[^a-z0-9]+/g, "-").replace(/^-|-$/g, "");
  const fill = (text, thing) => page.base["as built"] ? String(text) : String(text).replace(/\{([^}:]+)(:slug)?\}/g, (_, key, safe) => {
    if (thing == null || !(key in Object(thing))) { refused.push(`nothing called "${key}" to fill in`); return ""; }
    return safe ? slug(String(thing[key])) : String(thing[key]);
  });
  const has = (thing, words) => {
    const [first, rest] = words.split(".");
    if (thing == null || typeof thing !== "object" || !(first in thing)) return false;
    return !rest || (Array.isArray(thing[first]) && thing[first].some((one) => one && typeof one === "object" && rest in one));
  };
  const address = (kind, name, value) => {
    let to;
    try { to = new URL(value, new URL(page.at || "./", location.href)); } catch { return null; }
    const web = to.protocol === "http:" || to.protocol === "https:";
    if (web && to.origin === location.origin) return to.pathname + to.search + to.hash;
    return web && kind === "a" && name === "href" ? to.href : null;
  };

  const allowed = (kind, name, value) => {
    if (!/^[a-z][a-z0-9-]*$/.test(name) || name.startsWith("on") || NOT_SET.has(name) || value.startsWith("tml-")) return null;
    return ADDRESS.has(name) ? address(kind, name, value) : value;
  };
  const makes = (kind) => /^[a-z][a-z0-9]*$/.test(kind) && !NEVER.has(kind);

  function place(parent, form, thing) {
    if (!Array.isArray(form) || typeof form[0] !== "string") return refused.push("a piece that is not a list starting with a name");
    const [kind, ...parts] = form;
    if (kind === "each") {
      const list = thing && thing[parts[0]];
      if (!Array.isArray(list)) return refused.push(`no list called "${parts[0]}"`);
      for (const one of list) {
        const match = (page.base.words || []).find(([words]) => has(one, words));
        if (match) place(parent, match[1], one); else refused.push(`no word in the base matches an entry of "${parts[0]}"`);
      }
      return;
    }
    if (kind === "later") return later.push([parts[0], thing]);
    if (!makes(kind)) return refused.push(`<${kind}>`);
    const node = document.createElement(kind);
    for (const part of parts) {
      if (typeof part === "string") node.append(fill(part, thing));
      else if (Array.isArray(part)) place(node, part, thing);
      else if (part && typeof part === "object") {
        for (const [name, raw] of Object.entries(part)) {
          const value = allowed(kind, name, fill(raw, thing));
          if (value == null) refused.push(`${name} on <${kind}>`); else node.setAttribute(name, value);
        }
      }
    }
    parent.append(node);
  }

  function build() {
    refused = []; later = [];
    const room = document.createDocumentFragment();
    const base = page.base && typeof page.base === "object" ? page.base : {};
    page.base = base;
    for (const form of base.body || []) place(room, form, page.contract);
    for (const [form, thing] of later) place(room, form, thing);
    const pieces = room.querySelectorAll("*").length;
    $("page").replaceChildren(room);
    name();
    const title = (base.head || []).find((f) => Array.isArray(f) && f[0] === "title");
    document.title = title ? fill(title[1] || "", page.contract) : "Build";
    $("notice").hidden = !fromLink;
    told(`Built ${pieces} pieces.`);
    survey();
  }

  function told(text) {
    $("status").replaceChildren(text + (refused.length ? ` Refused ${refused.length}:` : " Refused nothing."));
    if (!refused.length) return;
    const list = el("ul");
    for (const what of new Set(refused)) list.append(el("li", what));
    $("status").append(list);
  }

  // ---- every piece has a name -----------------------------------------------------------
  function name() {
    const room = $("page"), taken = new Set(), count = {};
    for (const node of room.querySelectorAll("[id]")) {
      if (taken.has(node.id)) { refused.push(`a second piece called "${node.id}"`); node.removeAttribute("id"); } else taken.add(node.id);
    }
    for (const node of room.querySelectorAll(":not([id])")) {
      const kind = node.localName;
      let id;
      do { count[kind] = (count[kind] || 0) + 1; id = `${kind}-${count[kind]}`; } while (taken.has(id) || document.getElementById(id));
      taken.add(id); node.id = id;
    }
  }
  const piece = (id) => id === "page" ? $("page") : (id && !id.startsWith("tml-") && $("page").querySelector("#" + CSS.escape(id))) || null;
  const choose = (id) => { $("piece").value = id; say(`Picked ${id}.`); };

  // The list of all pieces, and the overlay that shows each name where the piece is.
  function survey() {
    const walk = (node, into) => {
      for (const child of node.children) {
        const own = Array.from(child.childNodes).filter((c) => c.nodeType === 3).map((c) => c.data).join(" ").trim();
        const pick = el("button", `Pick ${child.id}`, { type: "button" });
        pick.onclick = () => choose(child.id);
        const row = el("li"); row.append(pick, ` ${child.localName}` + (own ? `: ${own.slice(0, 40)}` : ""));
        into.append(row);
        if (child.children.length) walk(child, row.appendChild(el("menu")));
      }
    };
    const list = el("menu"); walk($("page"), list);
    $("all").replaceChildren(list);
    labels();
  }
  function labels() {
    $("ids").replaceChildren();
    if (!$("show").checked) return;
    // A name sits at the right-hand end of its piece, clear of the words. Names that would
    // land on the same spot step leftwards, outermost piece first.
    const used = {};
    for (const node of $("page").querySelectorAll("*")) {
      const box = node.getBoundingClientRect();
      if (!node.checkVisibility() || (!box.width && !box.height)) continue;
      const wide = node.id.length * 6 + 8, line = Math.round(box.top / 6);
      const wanted = Math.max(box.right, box.left + wide) - wide;
      const left = Math.min(wanted, (used[line] ?? Infinity) - wide - 2);
      used[line] = left;
      const tag = el("button", node.id, { type: "button", style: `position:absolute;left:${Math.max(0, left) + scrollX}px;top:${box.top + scrollY}px;width:${wide}px;font:10px monospace;padding:0;margin:0;opacity:.85` });
      tag.onclick = () => choose(node.id);
      $("ids").append(tag);
    }
  }

  // ---- clay: pick a piece by name, then move, change, copy, remove or add to it ---------
  const written = (node) => node.nodeType === 3 ? node.data : [node.localName,
    ...(node.attributes.length ? [Object.fromEntries(Array.from(node.attributes, (a) => [a.name, a.value]))] : []),
    ...kept(node).map(written)];
  const kept = (node) => Array.from(node.childNodes).filter((c) => c.nodeType === 1 || (c.nodeType === 3 && c.data));

  function shape(act) {
    refused = [];
    const room = $("page"), node = piece($("piece").value.trim()), other = piece($("other").value.trim());
    const text = $("text").value;
    if (!node) return say("No piece is called that. Turn on Show names, or open All pieces, and pick one.");
    const whole = node === room;
    let done;
    if (act === "add") {
      const kind = $("kind").value.trim().toLowerCase();
      if (!makes(kind)) { refused.push(`<${kind}>`); return told("Added nothing."); }
      node.append(el(kind, text || null)); name();
      done = `Added ${node.lastElementChild.id} inside ${whole ? "page" : node.id}.`;
    } else if (whole) return say("The page itself can only be added to.");
    else if (act === "up" || act === "down") {
      const next = act === "up" ? node.previousElementSibling : node.nextElementSibling;
      if (!next) return say(`${node.id} is already ${act === "up" ? "first" : "last"} where it is.`);
      act === "up" ? next.before(node) : next.after(node);
      done = `Moved ${node.id} ${act}.`;
    } else if (act === "before" || act === "after" || act === "into") {
      if (!other || (other === room && act !== "into")) return say("Name the other piece first.");
      if (node.contains(other)) return say("A piece cannot be put inside itself.");
      act === "before" ? other.before(node) : act === "after" ? other.after(node) : other.append(node);
      done = `Put ${node.id} ${act === "into" ? "inside" : act} ${other === room ? "page" : other.id}.`;
    } else if (act === "remove") {
      node.remove(); $("piece").value = "";
      done = `Removed ${node.id}.`;
    } else if (act === "copy") {
      const twin = node.cloneNode(true);
      for (const each of [twin, ...twin.querySelectorAll("[id]")]) each.removeAttribute("id");
      node.after(twin); name();
      done = `Copied ${node.id} as ${twin.id}.`;
    } else if (act === "text") {
      const first = Array.from(node.childNodes).find((c) => c.nodeType === 3);
      if (first) first.data = text; else node.prepend(text);
      done = `Changed the text of ${node.id}.`;
    } else if (act === "attribute") {
      const attr = $("attr").value.trim().toLowerCase(), value = $("value").value;
      if (value === "") node.removeAttribute(attr);
      else {
        const safe = allowed(node.localName, attr, value);
        if (safe == null) { refused.push(`${attr} on <${node.localName}>`); return told("Changed nothing."); }
        if (attr === "id" && document.getElementById(safe)) return say(`Something is already called ${safe}.`);
        node.setAttribute(attr, safe);
        if (attr === "id") $("piece").value = safe;
      }
      done = `Set ${attr} on ${node.id}.`;
    }
    // The engine writes the page down as it now stands; from here the page is its pieces.
    name();
    page = { contract: {}, base: { "as built": true, head: [["title", document.title]], body: kept(room).map(written) } };
    fields(); keep(); survey(); told(done);
  }

  // ---- the page as data: kept, carried, saved -----------------------------------------
  const pack = (text) => btoa(Array.from(new TextEncoder().encode(text), (b) => String.fromCharCode(b)).join(""))
    .replace(/\+/g, "-").replace(/\//g, "_").replace(/=+$/, "");
  const unpack = (text) => new TextDecoder().decode(Uint8Array.from(atob(text.replace(/-/g, "+").replace(/_/g, "/")), (c) => c.charCodeAt(0)));

  function take(data, how) {
    if (!data || typeof data !== "object" || typeof data.contract !== "object" || typeof data.base !== "object")
      return say('That is not a page. A page is {"contract": {...}, "base": {...}}.');
    page = data; fromLink = how === "link";
    changed(true);
  }
  function changed(all) {
    build();
    if (all) fields();
    keep();
  }
  function keep() {
    const text = JSON.stringify(page, null, 1);
    if (document.activeElement !== $("data")) $("data").value = text;
    $("link").setAttribute("href", "#page=" + pack(JSON.stringify(page)));
    $("save").setAttribute("href", "data:application/json;charset=utf-8," + encodeURIComponent(text));
    try { localStorage.setItem(KEY, JSON.stringify(page)); } catch { /* the page still works without it */ }
  }
  const say = (text) => $("status").replaceChildren(text);
  const $ = (id) => document.getElementById("tml-" + id);

  // ---- the page as fields: every value can be changed, every list can grow ------------
  const blank = (v) => Array.isArray(v) ? [] : v && typeof v === "object" ? Object.fromEntries(Object.entries(v).map(([k, x]) => [k, blank(x)]))
    : typeof v === "number" ? 0 : typeof v === "boolean" ? false : "";
  const reach = (path) => path.slice(0, -1).reduce((at, step) => at[step], page.contract);
  const call = (path) => path.map((step) => typeof step === "number" ? step + 1 : step).join(" ");

  function field(value, path) {
    const name = call(path), last = path[path.length - 1];
    if (Array.isArray(value)) {
      const kind = path.filter((s) => typeof s !== "number").join(".");
      if (value.length) shapes[kind] = blank(value[0]);
      const set = el("fieldset"); set.append(el("legend", name));
      value.forEach((one, i) => {
        set.append(field(one, [...path, i]));
        const out = el("button", `Remove ${call([...path, i])}`, { type: "button" });
        out.onclick = () => { value.splice(i, 1); changed(true); };
        set.append(el("p", out));
      });
      const more = el("button", `Add to ${name}`, { type: "button" });
      more.onclick = () => { value.push(JSON.parse(JSON.stringify(shapes[kind] ?? ""))); changed(true); };
      set.append(el("p", more));
      return set;
    }
    if (value && typeof value === "object") {
      const set = el("fieldset"); set.append(el("legend", name));
      for (const [k, v] of Object.entries(value)) set.append(field(v, [...path, k]));
      return set;
    }
    const long = typeof value === "string" && value.length > 50;
    const input = long ? el("textarea", value, { rows: 3, cols: 36 })
      : el("input", null, typeof value === "boolean" ? { type: "checkbox" } : { type: typeof value === "number" ? "number" : "text", size: 30 });
    if (typeof value === "boolean") input.checked = value; else if (!long) input.value = value;
    input.oninput = () => {
      reach(path)[last] = typeof value === "boolean" ? input.checked : typeof value === "number" ? Number(input.value) : input.value;
      changed(false);
    };
    return wrap(name, input);
  }
  const wrap = (name, input) => { const label = el("label", name + " "); label.append(input); return el("p", label); };
  function fields() {
    $("fields").replaceChildren(...(page.base["as built"]
      ? [el("p", "This page has been shaped by hand, so it is now written down piece by piece. Change it under Shape.")]
      : Object.entries(page.contract).map(([k, v]) => field(v, [k]))));
  }

  const row = (...things) => { const p = el("p"); things.forEach((t, i) => p.append(i ? " " : "", t)); return p; };

  // ---- the tools, made once ------------------------------------------------------------
  function tools() {
    const box = el("details", null, { id: "tml-tools" });
    box.append(el("summary", "Build"));
    box.append(el("p", "This page is data. Change a field and the engine builds it again. Nothing here is run, and nothing leaves your browser."));
    box.append(el("form", null, { id: "tml-fields" }));
    const whole = el("form", null, { id: "tml-whole" });
    const area = el("textarea", null, { id: "tml-data", rows: 10, cols: 38, spellcheck: "false" });
    const label = el("label", "Page as data "); label.append(area);
    const go = el("button", "Build from this", { type: "button" });
    go.onclick = () => { try { take(JSON.parse(area.value), "typed"); } catch (e) { say("That is not valid JSON: " + e.message); } };
    const clear = el("button", "Empty the box", { type: "button" });
    clear.onclick = () => { area.value = ""; area.focus(); };
    whole.append(el("p", label), el("p", go), el("p", clear));
    const open = el("details"); open.append(el("summary", "Give it a whole page"), whole);
    box.append(open);
    const from = el("p", "Start from: ");
    for (const [name, where] of Object.entries(EXAMPLES)) {
      const b = el("button", name, { type: "button" });
      b.onclick = async () => {
        if (!where) return take(JSON.parse(JSON.stringify(STARTER)), "typed");
        try {
          const [contract, base] = await Promise.all([where.contract, where.base].map((u) => fetch(u).then((r) => r.json())));
          take({ contract, base, at: where.at }, "typed");
        } catch { say(`Could not load ${name} from this site.`); }
      };
      from.append(b, " ");
    }
    box.append(from);
    const carry = el("p");
    carry.append(el("a", "Link to this page", { id: "tml-link", href: "#" }), " · ", el("a", "Save as a file", { id: "tml-save", download: "page.json", href: "#" }));
    box.append(carry);

    const clay = el("details", null, { id: "tml-shape" });
    clay.append(el("summary", "Shape"));
    clay.append(el("p", "Everything on the page has a name. Pick a piece by its name, then move it, change it, copy it, remove it or add to it."));
    const ask = (label, id, attrs) => { const l = el("label", label + " "); l.append(el("input", null, { id: "tml-" + id, type: "text", size: 16, ...attrs })); return l; };
    const does = (label, act) => { const b = el("button", label, { type: "button" }); b.onclick = () => shape(act); return b; };
    const show = ask("Show names", "show", { type: "checkbox", size: null });
    show.firstElementChild.removeAttribute("size");
    show.firstElementChild.onchange = labels;
    const all = el("details"); all.append(el("summary", "All pieces"), el("div", null, { id: "tml-all" }));
    clay.append(el("p", show), all,
      el("p", ask("Piece", "piece")), row(does("Move up", "up"), does("Move down", "down"), does("Copy", "copy"), does("Remove", "remove")),
      el("p", ask("Other piece", "other")), row(does("Put before other", "before"), does("Put after other", "after"), does("Put inside other", "into")),
      el("p", ask("Text", "text", { size: 30 })), row(does("Set text", "text")),
      el("p", ask("Attribute", "attr")), el("p", ask("Value", "value")), row(does("Set attribute", "attribute")),
      el("p", ask("New piece", "kind")), row(does("Add inside", "add")));
    const status = el("p", el("output", null, { id: "tml-status" }));
    const notice = el("p", el("small", "Built from data carried in the link. It is not a page this site has published."), { id: "tml-notice", hidden: "" });
    const room = el("div", null, { id: "tml-page" });
    room.addEventListener("toggle", labels, true);
    addEventListener("resize", labels);
    document.body.append(box, clay, status, el("hr"), notice, room, el("div", null, { id: "tml-ids" }));
  }

  function arrive() {
    if (location.hash.startsWith("#page=")) {
      try { return take(JSON.parse(unpack(location.hash.slice(6))), "link"); } catch { say("The link does not carry a readable page."); }
    }
    let kept = null;
    try { kept = JSON.parse(localStorage.getItem(KEY)); } catch { /* start fresh */ }
    take(kept && kept.contract && kept.base ? kept : JSON.parse(JSON.stringify(STARTER)), "kept");
  }

  tools();
  page = JSON.parse(JSON.stringify(STARTER));
  arrive();
  addEventListener("hashchange", () => { if (location.hash.startsWith("#page=")) arrive(); });
})();

// Clay. What the browser holds is the material, not the output of anything.
// Every thing gets a name as it enters. Three words work on names:
//   make KIND in|before|after NAME      put NAME in|before|after NAME | put NAME out
//   set NAME text|ATTRIBUTE VALUE
// "it" is the last thing touched or made. {NAME} is what NAME holds. A thing's "does" is
// sentences it says when touched. Sentences are data: nothing in them is ever run as code.
// A name is given once and never handed to another thing. What was said is kept in the
// browser, so the world is there on the next visit; "put world out" forgets it.
(() => {
  "use strict";
  const NEVER = new Set(["script", "style", "iframe", "frame", "frameset", "object", "embed", "link", "meta",
    "base", "template", "slot", "portal", "applet", "noscript", "svg", "math", "html", "head", "body", "title"]);
  const NOT_SET = new Set(["style", "srcdoc", "srcset", "ping", "is", "nonce", "integrity", "http-equiv"]);
  const ADDRESS = new Set(["href", "src", "action", "formaction", "poster", "background", "cite", "data"]);

  const el = (kind, text, attrs) => {
    const node = document.createElement(kind);
    if (text != null) node.append(text);
    for (const [k, v] of Object.entries(attrs || {})) node.setAttribute(k, v);
    return node;
  };
  const world = el("div", null, { id: "world" }), names = el("div");
  const line = el("input", null, { type: "text", size: 34, autocomplete: "off", "aria-label": "Say" });
  const show = el("input", null, { type: "checkbox" }), status = el("output");
  const KEY = "themissinglayer.clay.v1";
  let it = world, count = {}, said = [];

  // ---- names ------------------------------------------------------------------------------
  const find = (name) => {
    const node = name === "it" ? it : name === "world" ? world : name && world.querySelector("#" + CSS.escape(name));
    if (!node || !node.isConnected) throw `nothing is called ${name || "that"}`;
    return node;
  };
  const fresh = (kind) => { do count[kind] = (count[kind] || 0) + 1; while (document.getElementById(`${kind}-${count[kind]}`)); return `${kind}-${count[kind]}`; };
  const holds = (node) => "value" in node && node.localName !== "li" && node.localName !== "button" ? node.value : node.textContent;
  const fill = (text) => text.replace(/\{([^}\s]+)\}/g, (_, name) => holds(find(name)));

  // ---- the three words --------------------------------------------------------------------
  function place(node, where, target) {
    if (node === world) throw "the world stays where it is";
    if (node.contains(target)) throw "a thing cannot go inside itself";
    if (where === "in") target.append(node);
    else if ((where === "before" || where === "after") && target !== world) target[where](node);
    else throw "say in, before or after a name (only in works for world)";
  }
  function say(sentence) {
    sentence = sentence.trimStart();
    const [verb, a, b, c] = sentence.trim().split(/\s+/);
    if (verb === "make") {
      if (!/^[a-z][a-z0-9]*$/.test(a || "") || NEVER.has(a)) throw `${a || "that"} cannot be made here; a kind is an HTML element such as h1, p, ul, li, button, input, details`;
      const target = find(c), node = el(a);
      place(node, b, target);
      node.id = fresh(a);
      it = node;
      return [`made ${node.id}`, `make ${a} ${b} ${target.id}`];
    }
    if (verb === "put") {
      const node = find(a);
      if (b === "out") {
        if (node === world) { world.replaceChildren(); it = world; count = {}; said = []; return ["emptied the world and forgot it", null]; }
        node.remove(); it = world;
        return [`put ${node.id} out`, `put ${node.id} out`];
      }
      const target = find(c);
      place(node, b, target);
      it = node;
      return [`put ${node.id} ${b} ${target.id}`, `put ${node.id} ${b} ${target.id}`];
    }
    if (verb === "set") {
      const node = find(a), kind = node.localName, was = node.id;
      if (node === world) throw "the world has no text or attributes of its own";
      let value = (sentence.match(/^\S+\s+\S+\s+\S+\s?([\s\S]*)$/) || [])[1] || "";
      if (!b) throw "say what to set: text or an attribute";
      if (b !== "does") value = fill(value);
      if (b === "text") {
        const own = Array.from(node.childNodes).find((n) => n.nodeType === 3);
        if (own) own.data = value; else node.prepend(value);
      } else if (value === "" && b !== "id") { node.removeAttribute(b); if (b === "value" && "value" in node) node.value = ""; }
      else {
        if (!/^[a-z][a-z0-9-]*$/.test(b) || b.startsWith("on") || NOT_SET.has(b)) throw `${b} cannot be set`;
        if (ADDRESS.has(b)) {
          let to; try { to = new URL(value, location.href); } catch { throw "that is not an address"; }
          const web = to.protocol === "http:" || to.protocol === "https:";
          if (!web) throw "that kind of address cannot be used";
          if (to.origin !== location.origin && !(kind === "a" && b === "href")) throw "that address leaves this site";
        }
        if (b === "id" && (!/^[A-Za-z][\w-]*$/.test(value) || value === "world" || value === "it" || document.getElementById(value))) throw `${value || "that"} cannot be a name here`;
        node.setAttribute(b, value);
        if (b === "value" && "value" in node) node.value = value;
      }
      it = node;
      return [`set ${b} of ${node.id}`, `set ${was} ${b} ${value}`];
    }
    throw "the words are make, put and set";
  }
  // A does takes everything after it, so a thing can be taught to make things that do things.
  const split = (text) => {
    const parts = text.split(";"), at = parts.findIndex((one) => /^\s*set\s+\S+\s+does(\s|$)/.test(one));
    return at < 0 ? parts : [...parts.slice(0, at), parts.slice(at).join(";")];
  };
  function speak(text) {
    const done = [];
    let failed = "";
    try {
      for (const one of split(text)) {
        if (!one.trim()) continue;
        const [told, kept] = say(one);
        done.push(told);
        if (kept) said.push(kept);
      }
    } catch (why) { failed = (done.length ? "; then not done: " : "Not done: ") + (why.message || why); }
    status.replaceChildren(done.join("; ") + failed + ".");
    try { localStorage.setItem(KEY, JSON.stringify(said)); } catch { /* the world still works without memory */ }
    label();
  }

  // ---- the overlay: each name, where its thing is ------------------------------------------
  function label() {
    names.replaceChildren();
    if (!show.checked) return;
    const used = {};
    for (const node of world.querySelectorAll("*")) {
      const box = node.getBoundingClientRect();
      if (!node.checkVisibility() || (!box.width && !box.height)) continue;
      const wide = node.id.length * 6 + 8, row = Math.round(box.top / 6);
      const left = Math.min(Math.max(box.right, box.left + wide) - wide, (used[row] ?? Infinity) - wide - 2);
      used[row] = left;
      const tag = el("button", node.id, { type: "button", style: `position:absolute;left:${Math.max(0, left) + scrollX}px;top:${box.top + scrollY}px;width:${wide}px;font:10px monospace;padding:0;margin:0;opacity:.85` });
      tag.onclick = () => { line.setRangeText(node.id + " ", line.selectionStart, line.selectionEnd, "end"); line.focus(); };
      names.append(tag);
    }
  }

  // ---- touching ----------------------------------------------------------------------------
  world.addEventListener("click", (e) => {
    const node = e.target.closest("[id]");
    if (!node || node === world || !world.contains(node)) return;
    it = node;
    const doer = e.target.closest("[does]");
    if (doer && world.contains(doer)) speak(doer.getAttribute("does"));
    else status.replaceChildren(`That is ${node.id}.`);
  });
  world.addEventListener("submit", (e) => e.preventDefault());
  world.addEventListener("toggle", label, true);
  addEventListener("resize", label);
  show.onchange = label;
  const go = () => { speak(line.value); line.value = ""; line.focus(); };
  line.onkeydown = (e) => { if (e.key === "Enter") go(); };
  const doIt = el("button", "Do", { type: "button" }); doIt.onclick = go;

  const bar = el("p"); bar.append(line, " ", doIt, " ");
  const seen = el("label", "Names "); seen.append(show); bar.append(seen);
  const words = el("p", el("small"));
  words.firstChild.append(
    "make KIND in|before|after NAME (a KIND is an HTML element: h1, p, ul, li, button, input, details, summary, a, font ...)", el("br"), "put NAME in|before|after NAME, or put NAME out", el("br"),
    "set NAME text WORDS, or set NAME ATTRIBUTE VALUE", el("br"),
    "The page is called world. it is the last thing touched or made. {NAME} is what NAME holds.", el("br"),
    "Several sentences can go on one line, split by ; and a thing's does is sentences it says when touched. A does takes the rest of its line.", el("br"),
    "set NAME value with nothing after it empties a field. Colour is set NAME color red on a font.", el("br"),
    "What you say is kept in this browser. put world out empties the world and forgets it.");
  document.body.append(bar, el("p", status), words, el("hr"), world, names);
  let remembered = [];
  try { remembered = JSON.parse(localStorage.getItem(KEY)) || []; } catch { /* start empty */ }
  let lost = 0;
  for (const one of remembered) { try { said.push(say(one)[1]); } catch { lost++; } }
  it = world;
  status.replaceChildren(lost ? `The world came back changed: ${lost} of ${remembered.length} remembered sentences could not be said again.`
    : world.firstChild ? `The world is as you left it: ${world.querySelectorAll("*").length} things.` : "The world is empty.");
  label();
})();

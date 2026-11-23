# The acceptance check for /map. Opens the page the way a visitor gets it, in landscape and
# in portrait, picks every choice of the select with the keyboard, and measures where every
# symbol stands. Prints HELD or FAILED per claim. Reads only; changes nothing.
#   python3 map.py <site> [--shots <folder>]
# With --shots it also saves what it saw: every theme, with the overlay off and on, landscape and portrait.
import base64, glob, itertools, json, os, shutil, sys, tempfile, time
from hand import Hand

ROOT = os.path.join(os.path.dirname(os.path.abspath(__file__)), "..")
args = sys.argv[1:]
shots = args[args.index("--shots") + 1] if "--shots" in args else None
site = args[0].rstrip("/") + "/"
sheets = {}
for path in glob.glob(os.path.join(ROOT, "map", "*.json")):
    sheets.update(json.load(open(path, encoding="utf-8")))
live, on, at, themes = sheets["components"], sheets["on"], sheets["at"], list(sheets["themes"])
WIDE, TALL = (1280, 800), (390, 844)

h = Hand()


def look(expr):
    got = h.say("Runtime.evaluate", expression=expr, returnByValue=True)
    if "exceptionDetails" in got:
        sys.exit(f"the check could not read the page: {got['exceptionDetails']}")
    return got["result"].get("value")


def open_at(size):
    w, hgt = size
    h.say("Emulation.setDeviceMetricsOverride", width=w, height=hgt, deviceScaleFactor=1, mobile=False)
    for path in ("map", "map.html"):   # Pages serves map.html as /map; a plain file server does not
        h.say("Page.navigate", url=site + path)
        time.sleep(1.2)
        if look("!!document.querySelector('svg')"):
            return
    sys.exit("no /map here")


def key(name, code):
    for kind in ("rawKeyDown", "keyUp"):
        h.say("Input.dispatchKeyEvent", type=kind, key=name, code=name, windowsVirtualKeyCode=code)


def choose(name, value):
    """Picks a choice the way a reader does: focus the select, then arrow keys."""
    sel = f"document.querySelector('select[name={name}]')"
    look(f"{sel}.focus()")
    for _ in range(12):
        key("ArrowUp", 38)
    want = look(f"[...{sel}.options].findIndex(o => o.value === {json.dumps(value)})")
    for _ in range(want):
        key("ArrowDown", 40)
    time.sleep(.2)
    return look(f"{sel}.value") == value


def shoot(name):
    if shots:
        data = h.say("Page.captureScreenshot", format="jpeg", quality=85)["data"]
        with open(os.path.join(shots, name + ".jpg"), "wb") as f:
            f.write(base64.b64decode(data))


# Where every symbol stands on the screen: shapes by their box, words by the point they hang from.
MEASURE = """(() => {
  const svg = [...document.querySelectorAll('svg')].find(s => getComputedStyle(s).display !== 'none');
  const r = (n) => n.toFixed(1);
  const on = (e) => { for (let n = e; n && n !== svg; n = n.parentNode) if (getComputedStyle(n).display === 'none') return false; return true; };
  const box = (e) => { const b = e.getBoundingClientRect(); return [r(b.x), r(b.y), r(b.width), r(b.height)].join(' '); };
  const point = (e) => { const m = e.getScreenCTM(), p = svg.createSVGPoint(); p.x = +e.getAttribute('x'); p.y = +e.getAttribute('y'); const q = p.matrixTransform(m); return r(q.x) + ' ' + r(q.y); };
  const img = svg.querySelector('image.art'), ctm = svg.getScreenCTM();
  const out = { svg: svg.getAttribute('class'), symbols: {}, holes: {} };
  out.scale = ctm.a; out.ox = ctm.e + (+img.getAttribute('x')) * ctm.a; out.oy = ctm.f + (+img.getAttribute('y')) * ctm.a;
  out.art = on(img); out.artbox = box(img);
  out.drawn = [...svg.querySelectorAll('g.th')].filter(on).map(g => g.getAttribute('class').split(' ')[1].slice(3));
  out.drawnArt = [...svg.querySelectorAll('g.th image')].length;
  svg.querySelectorAll('circle.th-hole').forEach(e => { if (on(e)) { const b = e.getBoundingClientRect(); out.holes[e.dataset.at] = [b.x + b.width / 2, b.y + b.height / 2]; } });
  const d = svg.querySelector('g.diagram');
  out.diagram = on(d);
  d.querySelectorAll('circle.spot, rect.tag, line.wire, rect.veil').forEach((e, i) => out.symbols[e.tagName + i] = box(e));
  d.querySelectorAll('text.name').forEach((e, i) => out.symbols['text' + i] = point(e));
  out.names = [...d.querySelectorAll('text.name')].map(e => ({ at: e.dataset.at, c: e.dataset.c, text: e.textContent, xy: point(e) }));
  out.spots = [...d.querySelectorAll('circle.spot')].map(e => { const b = e.getBoundingClientRect(); return { at: e.dataset.at, x: b.x + b.width / 2, y: b.y + b.height / 2 }; });
  out.wires = [...d.querySelectorAll('line.wire')].map(e => e.dataset.ends);
  const de = document.documentElement;
  out.scroll = [de.scrollWidth, de.scrollHeight, innerWidth, innerHeight];
  const sb = svg.getBoundingClientRect(); out.surface = [sb.width, sb.height];
  out.page = getComputedStyle(document.body).backgroundColor;
  out.scripts = document.scripts.length;
  out.policy = document.querySelector('meta[http-equiv="Content-Security-Policy"]')?.content || '';
  out.entry = svg.querySelector('a polygon') ? svg.querySelector('a').getAttribute('href') : null;
  out.selects = [...document.querySelectorAll('select')].map(s => s.name + '=' + s.value);
  return out;
})()"""

held = []


def claim(text, ok):
    held.append(bool(ok))
    print(f"  {'HELD  ' if ok else 'FAILED'}  {text}")


THEMES = sheets["themes"]
hand = themes[0]
drawn = [t for t in themes if THEMES[t]["draw"] == "own"]
if shots:
    os.makedirs(shots, exist_ok=True)
for size, orient in ((WIDE, "landscape"), (TALL, "portrait")):
    open_at(size)
    card = look(MEASURE)
    claim(f"{orient}: /map opens as paper over the whole surface, with nothing to scroll",
          card["scroll"][0] <= card["scroll"][2] and card["scroll"][1] <= card["scroll"][3]
          and card["surface"] == [size[0], size[1]] and card["page"] == "rgb(246, 233, 211)")
    claim(f"{orient}: it opens on neonix's hand-drawn card with no overlay: two selects, theme and overlay",
          card["selects"] == [f"theme={hand}", "overlay=none"] and card["art"] and not card["drawn"] and not card["diagram"])
    claim(f"{orient}: the page carries no script, and its policy refuses any", card["scripts"] == 0 and "script-src 'none'" in card["policy"])
    claim(f"{orient}: {'the card stands in the middle of a landscape surface' if orient == 'landscape' else 'the card alone fills the width'}",
          card["svg"] == ("wide" if orient == "landscape" else "tall"))
    claim(f"{orient}: the triangle is the entry and leads to /explore", card["entry"] == "explore")
    base, over = {}, {}
    for n, theme in enumerate(themes):
        picked = choose("theme", theme)
        got = look(MEASURE)
        base[theme] = got
        shoot(f"{orient}-{n}-{theme}")
        own = THEMES[theme]["draw"] == "own"
        claim(f"{orient}: theme {theme} fills the holes on the same surface" + (", drawn with its own hand and showing none of the art" if own else ", as the hand-drawn card"),
              picked and got["surface"] == card["surface"] and got["scale"] == card["scale"] and got["ox"] == card["ox"] and not got["diagram"]
              and (got["drawn"] == [theme] and not got["art"] and got["drawnArt"] == 0 if own else got["drawn"] == [] and got["art"]))
        choose("overlay", "live")
        over[theme] = look(MEASURE)
        shoot(f"{orient}-{n}-{theme}-live")
        claim(f"{orient}: the overlay lies on theme {theme}", over[theme]["diagram"] and over[theme]["drawn"] == got["drawn"] and over[theme]["art"] == got["art"])
        choose("overlay", "none")
    s, ox, oy = card["scale"], card["ox"], card["oy"]
    holes = [a for a, p in at.items() if p["r"]]
    off = [(t, a) for t in drawn for a in holes
           if a not in base[t]["holes"] or abs(base[t]["holes"][a][0] - (ox + at[a]["x"] * s)) > 1 or abs(base[t]["holes"][a][1] - (oy + at[a]["y"] * s)) > 1]
    claim(f"{orient}: in all {len(drawn)} drawn themes every one of the {len(holes)} holes stands where the hand-drawn card has it", not off)
    first = over[themes[0]]
    moved = [(t, k) for t in themes for k, v in over[t]["symbols"].items() if first["symbols"].get(k) != v]
    claim(f"{orient}: every overlay symbol keeps its place on all {len(themes)} themes ({len(first['symbols'])} symbols each)",
          not moved and all(len(over[t]["symbols"]) == len(first["symbols"]) for t in themes))
    offspot = [p["at"] for p in first["spots"] if abs(p["x"] - (ox + at[p["at"]]["x"] * s)) > 1 or abs(p["y"] - (oy + at[p["at"]]["y"] * s)) > 1]
    claim(f"{orient}: every element's mark in the overlay stands on its hole", not offspot and len(first["spots"]) == len(holes))
    count = {c: 0 for c in live}
    wrong = []
    for n in first["names"]:
        for c in (n["c"] or "").split():
            count[c] += 1
            p = at[n["at"]]
            x, y = map(float, n["xy"].split())
            near = abs(y - (oy + p["y"] * s)) <= (p["r"] + 130) * s and abs(x - (ox + p["x"] * s)) <= (p["r"] + 30) * s + 1
            if on.get(c) != n["at"] or live[c]["name"] not in n["text"] or not near:
                wrong.append(c)
    claim(f"{orient}: each of the {len(live)} live components stands at exactly one element, the one map.on gives it",
          all(v == 1 for v in count.values()) and not wrong)
    gaps = [a for a in at if not any(on[c] == a for c in live)]
    marked = {n["at"] for n in first["names"] if n["text"] == "missing"}
    claim(f"{orient}: an element nothing stands on says missing ({', '.join(gaps) or 'none'})", set(gaps) == marked)
    pairs = {" ".join(sorted((on[a], on[b]))) for a, b, _ in sheets["connections"] if on[a] != on[b]}
    claim(f"{orient}: every connection between elements is drawn ({len(pairs)} lines for {len(sheets['connections'])} connections)",
          sorted(" ".join(sorted(w.split())) for w in first["wires"]) == sorted(pairs))
    choose("theme", hand)
    claim(f"{orient}: overlay None and the hand-drawn card again give back the page as it opened", look(MEASURE)["symbols"] == card["symbols"] and not look(MEASURE)["diagram"] and look(MEASURE)["art"])
h.away()

# The page is what the map JSONs make, in any order they are found.
sys.path.insert(0, ROOT)
import generator  # noqa: E402

names = sorted(glob.glob(os.path.join(ROOT, "map", "*.json")))
made = set()
with tempfile.TemporaryDirectory() as tmp:
    for order in itertools.permutations(names):
        folder = tempfile.mkdtemp(dir=tmp)
        for i, path in enumerate(order):
            shutil.copy(path, os.path.join(folder, f"{i}.json"))
        made.add(open(generator.write_map(folder, os.path.join(folder, "out.html")), encoding="utf-8").read())
shipped = open(os.path.join(ROOT, "map.html"), encoding="utf-8").read()
claim(f"the map JSONs in all {len(list(itertools.permutations(names)))} orders write the same page, and it is the page shipped", made == {shipped})

if shots:
    try:
        from PIL import Image
        for tail in ("", "-live"):
            tiles = [Image.open(os.path.join(shots, f"landscape-{n}-{t}{tail}.jpg")) for n, t in enumerate(themes)]
            w, hgt = tiles[0].size
            sheet = Image.new("RGB", (w * 2, hgt * ((len(tiles) + 1) // 2)), "white")
            for i, im in enumerate(tiles):
                sheet.paste(im, ((i % 2) * w, (i // 2) * hgt))
            sheet.resize((sheet.width // 2, sheet.height // 2)).save(os.path.join(shots, f"landscape-themes{tail}.jpg"), quality=85)
    except ImportError:
        pass
sys.exit(0 if all(held) else 1)

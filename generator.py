#!/usr/bin/env python3
# The generator for a terminal. It takes the same sheets as the generator in the browser
# and makes of them what a terminal can: lines of text out, numbers and typed lines in.
# A sheet names no device, so nothing in it changes between the two. This file holds the
# same grammar of a sheet and the same floppy; how a move is offered, how a thing is
# shown and where a box is kept are its own answers. It needs only Python 3.
#   python3 sheets.py               then pick by number
# In daq.code this is kernel/term/sheets.py and the sheets are the apps beside it
# (apps/<app>/app.json with "sheets"), or the ones on a mounted DAQ carrier. Placed on
# the site as generator.py, with nothing beside it, it fetches them from the site.
# A line that starts with { or [ is a shape, as in the browser's Shape box:
#   {"load": "email.wire"}  {"unload": "email.stub"}  a sheet pasted whole
#   {"do": "email.touch.send", "with": {"subject": "hi", "body": "there"}}
#   {"do": "email.touch.read", "pick": 1}
#   {"from": "email.wire.sent"}  {"to": "email.wire.inbox", "with": {...}}
#   {"keep": true}  and a floppy, which wipes and rebuilds
import glob, json, os, re, sys, threading, urllib.request

ENGINE, FLOPPY = "2", 1474560
SITE = os.environ.get("MISSINGLAYER_SITE", "https://themissinglayer.org/")
HERE = os.path.dirname(os.path.abspath(sys.argv[0])) if sys.argv and sys.argv[0] not in ("", "-") else os.getcwd()
HOME = os.environ.get("MISSINGLAYER_HOME") or os.path.join(os.path.expanduser("~"), ".missinglayer")
# Where apps are: beside this file as daq.code lays them out, then on a mounted carrier.
APPS = [d for d in [os.path.join(HERE, "..", "..", "apps")] + [os.path.join(p, "code", "apps") for p in ["/media/daq", "/Volumes/DAQ", *glob.glob("/media/*/DAQ"), *glob.glob("/run/media/*/DAQ")]
                                                                 if os.path.exists(os.path.join(p, "stick.json"))] if os.path.isdir(d)]
NAME, ID, AT = (re.compile(r"^[^./\\]+" + r"\.[^./\\]+" * n + "$") for n in (0, 1, 2))


class Refused(Exception):
    pass


def refuse(why):
    raise Refused(why)


def stringify(x, indent=None):
    return json.dumps(x, ensure_ascii=False, indent=indent, separators=None if indent else (",", ":"))


def word(v):
    return "" if v is None else v if isinstance(v, str) else stringify(v)


def plain(x):
    return isinstance(x, dict)


# ---- the grammar of a sheet: the same as in the browser ----------------------------------
def only(x, keys, what):
    for k in x:
        if k not in keys:
            refuse(f'{what}: the generator does not know "{k}"')


def checked_move(m, what):
    if not plain(m):
        refuse(f"{what} is not a move")
    only(m, ["from", "to", "when", "after", "with"], what)
    for k in ("from", "to", "when"):
        if k in m and not (isinstance(m[k], str) and AT.match(m[k])):
            refuse(f'{what}: "{k}" needs the address of a box, like email.wire.inbox')
    if "after" in m and not (isinstance(m["after"], (int, float)) and not isinstance(m["after"], bool) and 0 <= m["after"] <= 86400):
        refuse(f'{what}: "after" is a wait in seconds')
    if "with" in m and not (plain(m["with"]) and all(isinstance(v, str) for v in m["with"].values())):
        refuse(f'{what}: "with" names parts and the words they get')
    if m.get("when") and m.get("from"):
        refuse(f"{what}: a move that happens by itself takes the thing that arrived")
    if not (m.get("from") or m.get("to") or m.get("when")):
        refuse(f"{what}: a move needs a from or a to")
    return m


def checked(j):
    if not plain(j) or not isinstance(j.get("id"), str) or not ID.match(j["id"]):
        refuse("a JSON needs an id of two levels, like email.wire")
    only(j, ["id", "says", "kinds", "boxes", "moves"], j["id"])
    names = set()
    for key in ("kinds", "boxes", "moves"):
        if j.get(key) is None:
            continue
        if not plain(j[key]):
            refuse(f"{j['id']}: {key} must be named")
        for name, v in j[key].items():
            if not NAME.match(name):
                refuse(f'{j["id"]}: "{name}" cannot be the third level of an address')
            if name in names:
                refuse(f"{j['id']}: two things are called {name}")
            names.add(name)
            if key == "kinds" and not (isinstance(v, list) and v and all(isinstance(p, str) and p for p in v) and len(set(v)) == len(v)):
                refuse(f"{j['id']}.{name}: a kind lists its parts")
            if key == "boxes" and not (isinstance(v, str) and (NAME.match(v) or AT.match(v))):
                refuse(f"{j['id']}.{name}: a box names the kind it holds")
            if key == "moves":
                checked_move(v, f"{j['id']}.{name}")
    return j


loaded, timers, shown = {}, set(), {}
carried = {"head": [], "tail": []}   # records of a floppy that belong to another generator
lock = threading.RLock()


def every(key):
    return [{"id": i, "name": n, "at": f"{i}.{n}", "key": key, "v": v} for i in sorted(loaded) for n, v in (loaded[i].get(key) or {}).items()]


def kind_of(box):
    b = next((x for x in every("boxes") if x["at"] == box), None)
    if not b:
        return {"waits": box}
    at = b["v"] if AT.match(b["v"]) else f"{b['id']}.{b['v']}"
    k = next((x for x in every("kinds") if x["at"] == at), None)
    return {"at": at, "name": k["name"], "parts": k["v"]} if k else {"waits": at}


# ---- where this generator keeps what the boxes hold: one file ----------------------------
def boxes():
    try:
        with open(os.path.join(HOME, "boxes.json"), encoding="utf-8") as f:
            got = json.load(f)
        return got if plain(got) else {}
    except (OSError, ValueError):
        return {}


def keep_boxes(all_):
    os.makedirs(HOME, exist_ok=True)
    path = os.path.join(HOME, "boxes.json")
    with open(path + ".new", "w", encoding="utf-8") as f:
        f.write(stringify(all_, 2))
    os.replace(path + ".new", path)


def in_box(at):
    got = boxes().get(at)
    return got if isinstance(got, list) else []


# ---- a move ------------------------------------------------------------------------------
def arrive(box, thing, by, hops):
    kind = kind_of(box)
    if "waits" in kind:
        refuse(f"{by} waits for {kind['waits']}, which is not loaded")
    it = {p: word(thing.get(p)) for p in kind["parts"]}
    all_ = boxes()
    all_[box] = in_box(box) + [it]
    keep_boxes(all_)
    if hops < 8:
        for m in every("moves"):
            if m["v"].get("when") == box:
                try:
                    carry(m, it, hops + 1)
                except Refused:
                    pass   # one that cannot go does not stop the rest
    return kind


def carry(m, thing, hops=0):
    v = m["v"]
    it = {**thing, **(v.get("with") or {})}

    def go():
        if v.get("to"):
            return f"{m['at']}: a {arrive(v['to'], it, m['at'], hops)['name']} went to {v['to']}"
        if not m["id"]:
            return stringify(it)
        shown[m["at"]] = it
        return f"{m['at']}: {word(next(iter(it.values()), ''))}"

    after = v.get("after") or 0
    if not after > 0:
        return go()
    if v.get("to") and "waits" in kind_of(v["to"]):
        refuse(f"{m['at']} waits for {kind_of(v['to'])['waits']}, which is not loaded")

    def due():
        with lock:
            timers.discard(t)
            if m["id"] and m["id"] not in loaded:
                return
            try:
                told = go()
            except Refused as e:
                told = f"refused: {e}"
            print()
            page(told)

    t = threading.Timer(after, due)
    t.by, t.daemon = m["id"], True
    timers.add(t)
    t.start()
    return f"{m['at']}: in {stringify(after)} s it goes to {v.get('to') or 'whoever is here'}"


def do_move(m, given):
    v = m["v"]
    if v.get("when"):
        refuse(f"{m['at']} happens by itself, when a thing arrives in {v['when']}")
    kind = kind_of(v.get("from") or v["to"])
    if "waits" in kind:
        refuse(f"{m['at']} waits for {kind['waits']}, which is not loaded")
    if not v.get("from"):
        mine = given.get("with") if plain(given.get("with")) else {}
        if not any(word({**mine, **(v.get("with") or {})}.get(p)).strip() for p in kind["parts"]):
            refuse(f"{m['at']} needs a {kind['name']}: {', '.join(kind['parts'])}")
        return carry(m, mine)
    held = in_box(v["from"])
    if given.get("pick") is None and not m["id"] and not v.get("to"):
        return stringify(held)
    pick = given.get("pick")
    if not (isinstance(pick, int) and 1 <= pick <= len(held)):
        refuse(f"{v['from']} holds {len(held)}; pick one by its number, from 1")
    return carry(m, held[pick - 1])


# ---- the floppy: the same records and the same bytes as the browser writes ---------------
def label_of(recs):
    h, data = 0x811C9DC5, (ENGINE + stringify(recs)).encode("utf-16-le", "surrogatepass")
    for i in range(0, len(data), 2):
        h = ((h ^ (data[i] | data[i + 1] << 8)) * 0x01000193) & 0xFFFFFFFF
    return format(h, "08x")


def records():
    recs = carried["head"] + [{"json": loaded[i]} for i in sorted(loaded)] + carried["tail"]
    for b in sorted(every("boxes"), key=lambda x: x["at"]):
        if "waits" not in kind_of(b["at"]):
            recs += [{"at": b["at"], "is": thing} for thing in in_box(b["at"])]
    return recs


def nbytes(text):
    return len(text.encode("utf-8", "surrogatepass"))


def kept(size=None):
    size = size if isinstance(size, (int, float)) and not isinstance(size, bool) and size > 0 else FLOPPY
    recs = records()
    label = label_of(recs)

    def text(holds, disk, of):
        return stringify({"floppy": {"engine": ENGINE, "label": label, "disk": disk, "of": of}, "holds": holds}, 2)

    room = size - nbytes(text([], 99999, 99999)) - 4
    if room < 64:
        refuse(f"a floppy needs at least {size - room + 64} bytes")

    def cost(r):
        t = stringify(r, 2)
        return nbytes(t) + 4 * len(t.split("\n")) + 2

    pieces = []
    for r in recs:
        if cost(r) <= room:
            pieces.append(r)
            continue
        whole, at = stringify(r), 0
        while at < len(whole):
            fit, most = 1, len(whole) - at
            while fit < most:
                mid = (fit + most + 1) >> 1
                if cost({"cut": whole[at:at + mid], "more": False}) <= room:
                    fit = mid
                else:
                    most = mid - 1
            pieces.append({"cut": whole[at:at + fit], "more": at + fit < len(whole)})
            at += fit
    sets, used = [[]], 0
    for r in pieces:
        c = cost(r)
        if sets[-1] and used + c > room:
            sets.append([])
            used = 0
        sets[-1].append(r)
        used += c
    disks = [text(holds, i + 1, len(sets)) for i, holds in enumerate(sets)]
    return disks, label


def rebuild(recs, slot_):
    sheets = [checked(r["json"]) for r in recs if plain(r) and "json" in r]   # refused here, before anything is wiped
    things = {}
    for r in recs:
        if plain(r) and "is" in r and isinstance(r.get("at"), str) and plain(r["is"]):
            things.setdefault(r["at"], []).append({k: word(v) for k, v in r["is"].items()})
    for t in list(timers):
        t.cancel()
    timers.clear()
    shown.clear()
    loaded.clear()
    for j in sheets:
        loaded[j["id"]] = j
    keep_boxes(things)
    rest = [r for r in recs if not (plain(r) and ("json" in r or "is" in r))]
    carried["head"] = [r for r in rest if plain(r) and ("board" in r or "store" in r)]
    carried["tail"] = [r for r in rest if not (plain(r) and ("board" in r or "store" in r))]
    same = label_of(records()) == label_of(recs)
    n = slot_["of"]
    return (f"rebuilt from {n} {'floppy' if n == 1 else 'floppies'}: "
            + ("this device keeps the same as what was handed in" if same else "this device keeps it differently from what was handed in")
            + ("" if slot_["engine"] == ENGINE else f"; written by engine {word(slot_['engine'])}, this is engine {ENGINE}"))


slot = None


def insert(disk):
    global slot
    f = disk.get("floppy")
    if not (plain(f) and isinstance(disk.get("holds"), list) and isinstance(f.get("disk"), int) and isinstance(f.get("of"), int) and 1 <= f["disk"] <= f["of"]):
        refuse("not a floppy the generator knows")
    if not slot or slot["label"] != f.get("label") or slot["of"] != f["of"]:
        slot = {"label": f.get("label"), "of": f["of"], "engine": f.get("engine"), "disks": {}}
    slot["disks"][f["disk"]] = disk["holds"]
    missing = [i for i in range(1, f["of"] + 1) if i not in slot["disks"]]
    if missing:
        return f"floppy {f['disk']} of {f['of']} is in; still needed: {', '.join(map(str, missing))}"
    whole, slot = slot, None
    recs, cut = [], ""
    for i in range(1, whole["of"] + 1):
        for r in whole["disks"][i]:
            if not (plain(r) and "cut" in r):
                recs.append(r)
                continue
            cut += r["cut"]
            if not r.get("more"):
                recs.append(json.loads(cut.encode("utf-16", "surrogatepass").decode("utf-16")))
                cut = ""
    return rebuild(recs, whole)


# ---- the one way in: a shape -------------------------------------------------------------
def read_json(rel):
    for root in APPS + [HERE]:
        local = os.path.join(root, *rel.split("/"))
        if os.path.exists(local):
            with open(local, encoding="utf-8") as f:
                return json.load(f)
    with urllib.request.urlopen(urllib.request.Request(SITE + rel, headers={"User-Agent": "missinglayer-generator"}), timeout=10) as r:
        return json.load(r)


def fetched(id_):
    if not re.match(r"^[\w-]+\.[\w-]+$", id_):
        refuse(f"{id_} is not the address of a JSON on the site")
    try:
        j = read_json(id_.replace(".", "/") + ".json")   # the dot is the folder
    except (OSError, ValueError):
        j = None
    if not plain(j) or j.get("id") != id_:
        refuse(f"the site has no JSON called {id_}")
    return j


def give(g):
    if isinstance(g, list):
        return "\n".join(give(one) for one in g) if g else "nothing was handed in"
    try:
        if not plain(g):
            refuse("not a shape the generator knows")
        if "load" in g or ("id" in g and ("kinds" in g or "boxes" in g or "moves" in g)):
            j = checked(g if "load" not in g else fetched(g["load"]) if isinstance(g["load"], str) else g["load"])
            loaded[j["id"]] = j
            return f"loaded {j['id']}"
        if "unload" in g:
            if not isinstance(g["unload"], str) or loaded.pop(g["unload"], None) is None:
                refuse(f"{word(g['unload'])} is not loaded")
            for t in [t for t in timers if t.by and t.by not in loaded]:
                t.cancel()
                timers.discard(t)
            for at in [at for at in shown if not any(m["at"] == at for m in every("moves"))]:
                del shown[at]
            return f"unloaded {g['unload']}"
        if "do" in g or (("from" in g or "to" in g) and "store" not in g and "steps" not in g):
            if "do" not in g and "when" in g:
                refuse("only a loaded JSON can wait for a thing to arrive")
            m = (next((x for x in every("moves") if x["at"] == g["do"]), None) or refuse(f"{word(g['do'])} is not loaded")) if "do" in g else \
                {"id": "", "name": "shape", "at": "shape", "v": checked_move({k: g[k] for k in ("from", "to", "after", "with") if k in g}, "shape")}
            return do_move(m, g)
        if "floppy" in g:
            return insert(g)
        if "keep" in g:
            disks, label = kept(g["keep"].get("size") if plain(g["keep"]) else None)
            for i, text in enumerate(disks):
                with open(f"board-{label}-{i + 1}of{len(disks)}.json", "w", encoding="utf-8") as f:
                    f.write(text)
            return f"kept on {len(disks)} {'floppy' if len(disks) == 1 else 'floppies'}, label {label}, in {os.getcwd()}"
        refuse("this generator has no board; it knows sheets, moves and floppies")
    except Refused as e:
        return f"refused: {e}"
    except OSError as e:
        return f"could not: {e}"


# ---- what a terminal makes of it ---------------------------------------------------------
def first_of(thing, kind):
    return word(thing.get(kind["parts"][0])) or f"(no {kind['parts'][0]})"


def shipped():
    """The sheets there are to load: those of the apps (app.json with "sheets"), else what the site ships."""
    found = []
    for root in APPS:
        for app in sorted(os.listdir(root)):
            try:
                with open(os.path.join(root, app, "app.json"), encoding="utf-8") as f:
                    found += [f"{app}.{name}" for name in json.load(f).get("sheets", []) if f"{app}.{name}" not in found]
            except (OSError, ValueError, AttributeError):
                pass
    if APPS:
        return found
    try:
        return list(read_json("contract.json").get("ships", {}))
    except (OSError, ValueError, AttributeError):
        return []


def menu():
    acts = []
    for m in sorted(every("moves"), key=lambda x: x["at"]):
        v = m["v"]
        ends = [kind_of(b) for b in (v.get("when"), v.get("from"), v.get("to")) if b]
        if not v.get("when") and not any("waits" in k for k in ends):
            acts.append((f"{m['name']}: " + (f"pick a {ends[0]['name']} in {v['from']}" if v.get("from") else f"make a {ends[0]['name']}, to {v['to']}"), ("move", m)))
    ships = shipped()
    acts += [(f"load {i}", ("give", {"load": i})) for i in ships if i not in loaded]
    acts += [(f"unload {i}", ("give", {"unload": i})) for i in sorted(loaded)]
    acts += [("save a floppy here", ("give", {"keep": True})), ("restore from a floppy", ("restore",)), ("leave", ("leave",))]
    return acts


def page(told=None):
    print(f"The Missing Layer, in a terminal. {'loaded: ' + ', '.join(sorted(loaded)) if loaded else 'nothing is loaded'}")
    moves = every("moves")
    for x in sorted(every("kinds") + every("boxes") + moves, key=lambda x: x["at"]):
        print(x["at"])
        v = x["v"]
        ends = [kind_of(b) for b in (v.get("when"), v.get("from"), v.get("to")) if b] if x["key"] == "moves" else [kind_of(x["at"])] if x["key"] == "boxes" else []
        lacks = next((k for k in ends if "waits" in k), None)
        if lacks:
            print(f"  waits for {lacks['waits']}, which is not loaded")
        elif x["key"] == "kinds":
            print(f"  a {x['name']} has: {', '.join(v)}")
        elif x["key"] == "boxes":
            held = in_box(x["at"])
            print(f"  holds {len(held)} {ends[0]['name']}")
            for i, thing in enumerate(held):
                print(f"    {i + 1}. {first_of(thing, ends[0])}")
        elif v.get("when"):
            print(f"  when a {ends[0]['name']} arrives in {v['when']}, " + (f"after {stringify(v['after'])} s " if v.get("after", 0) > 0 else "")
                  + f"it goes to {v.get('to') or 'whoever is here'}" + (", with " + "; ".join(f"{k}: {w}" for k, w in v["with"].items()) if v.get("with") else ""))
        elif v.get("from"):
            print(f"  pick a {ends[0]['name']} in {v['from']}" + (f"; it goes to {v['to']}" if v.get("to") else ""))
            for k, w in (shown.get(x["at"]) or {}).items():
                print(f"    {k}: {w}")
        else:
            print(f"  make a {ends[0]['name']} ({', '.join(p for p in ends[0]['parts'] if p not in (v.get('with') or {}))}); it goes to {v['to']}")
    print()
    for i, (name, _) in enumerate(menu()):
        print(f"{i + 1:3}  {name}")
    if told:
        print(f"> {told}")
    sys.stdout.flush()


def ask(prompt):
    print(prompt, end="", flush=True)
    line = sys.stdin.readline()
    if not line:
        raise EOFError
    return line.rstrip("\r\n")


def number(text, most):
    return int(text) if text.isdigit() and 1 <= int(text) <= most else None


def by_hand(m):
    v = m["v"]
    kind = kind_of(v.get("from") or v["to"])
    if not v.get("from"):
        fixed = v.get("with") or {}
        return give({"do": m["at"], "with": {p: ask(f"{p}: ") for p in kind["parts"] if p not in fixed}})
    held = in_box(v["from"])
    if not held:
        return f"{v['from']} holds nothing"
    for i, thing in enumerate(held):
        print(f"{i + 1:3}  {first_of(thing, kind)}")
    pick = number(ask("which: ").strip(), len(held))
    return give({"do": m["at"], "pick": pick}) if pick else "nothing was picked"


def restore():
    found = []
    for name in sorted(os.listdir(".")):
        if name.endswith(".json"):
            try:
                with open(name, encoding="utf-8") as f:
                    got = json.load(f)
                if plain(got) and "floppy" in got:
                    found.append((name, got))
            except (OSError, ValueError):
                pass
    if not found:
        return f"no floppy is in {os.getcwd()}"
    for i, (name, got) in enumerate(found):
        print(f"{i + 1:3}  {name}  ({got['floppy'].get('disk')} of {got['floppy'].get('of')})")
    pick = number(ask("which floppy: ").strip(), len(found))
    if not pick:
        return "nothing was picked"
    print("This wipes everything this generator holds on this device and rebuilds it from the floppy.\n  1  go on\n  2  leave it")
    if ask("which: ").strip() != "1":
        return "left as it was"
    label = found[pick - 1][1]["floppy"].get("label")
    return give([got for _, got in found if got["floppy"].get("label") == label])   # every floppy of that set that is here


def main():
    with lock:
        page()
    try:
        while True:
            line = ask("")
            with lock:
                text = line.strip()
                if not text:
                    page()
                    continue
                if text[0] in "{[":
                    try:
                        told = give(json.loads(text))
                    except ValueError:
                        told = "refused: that is not JSON"
                else:
                    acts = menu()
                    pick = number(text, len(acts))
                    what = acts[pick - 1][1] if pick else None
                    if what is None:
                        told = "pick by number, or hand in a shape"
                    elif what[0] == "leave":
                        return
                    else:
                        told = by_hand(what[1]) if what[0] == "move" else give(what[1]) if what[0] == "give" else restore()
                print()
                page(told)
    except (EOFError, KeyboardInterrupt):
        pass
    for t in list(timers):   # when the input ends, what is still on its way arrives first
        t.join(90)


# ---- /map: the card as a surface ---------------------------------------------------------
# python3 generator.py map   reads every map/*.json, in any order, and writes map.html. The
# card is a stencil: each element is a hole. A theme is what goes into the holes; the first is
# neonix's own hand-drawn card, the others draw their own. An overlay lies on top of any theme.
# The page carries no script: two selects, and the stylesheet shows what is selected. Each map
# JSON owns its own keys; two that claim the same key are refused.
MAP_KEYS = {"map.card": ("art", "at", "title", "joins"), "map.live": ("asof", "seen", "components", "connections"), "map.on": ("on", "missing", "conflicts"), "map.themes": ("themes",), "map.ring": ("ring",)}


def map_sheets(folder):
    got = {}
    for path in sorted(glob.glob(os.path.join(folder, "*.json"))):
        with open(path, encoding="utf-8") as f:
            j = json.load(f)
        if j.get("id") not in MAP_KEYS:
            refuse(f"{os.path.basename(path)} is not a map sheet")
        for k in MAP_KEYS[j["id"]]:
            if k in got:
                refuse(f"{k} is said twice")
            got[k] = j if j["id"] == "map.ring" else j.get(k)
    lost = [i for i, ks in MAP_KEYS.items() if ks[0] not in got]
    if lost:
        refuse(f"waiting for {', '.join(lost)}")
    for c, a in got["on"].items():
        if c not in got["components"]:
            refuse(f"map.on puts {c} at {a}, and map.live has no {c}")
        if a not in got["at"]:
            refuse(f"map.on puts {c} at {a}, and map.card has no {a}")
    for c in got["components"]:
        if c not in got["on"]:
            refuse(f"{c} stands at no address")
    THEME = {"name", "by", "draw", "symbols", "line", "grid", "stroke", "page", "hole", "veil", "veil_opacity", "ink", "muted",
             "wire", "wire_opacity", "tag", "tag_line", "seen", "repo", "gone", "conflict", "font"}
    ways = {"draw": ("art", "own"), "symbols": ("art", "glyph", "code", "letter", "word"), "line": ("solid", "dashed", "double")}
    for k, th in got["themes"].items():
        if not re.fullmatch(r"[a-z]+", k) or k in ("none", "live") or set(th) != THEME:
            refuse(f"theme {k} must be a lowercase name and say exactly {', '.join(sorted(THEME))}")
        for w, may in ways.items():
            if th[w] not in may:
                refuse(f"theme {k}: {w} is one of {', '.join(may)}")
        if (th["draw"] == "art") != (th["symbols"] == "art"):
            refuse(f"theme {k}: only the art's own drawing has the art's symbols")
        for v in th.values():
            if not re.fullmatch(r"[#\w .,'()\-]+", str(v)):
                refuse(f"theme {k} says something that is not a colour, a number, a word or a font: {v}")
    arts = [k for k, th in got["themes"].items() if th["draw"] == "art"]
    if arts != list(got["themes"])[:1]:
        refuse("the hand-drawn card is the one theme that shows the art, and it comes first")
    ring = got["ring"]
    for shape in ("wide", "tall"):
        around = set(got["at"]) - {ring["center"], ring["bus"], ring["base"]}
        if set(ring[shape]) != around:
            refuse(f"map.ring {shape} must place exactly {', '.join(sorted(around))}")
        for a, xy in ring[shape].items():
            if len(xy) != 2 or not all(0 <= v <= 1 for v in xy):
                refuse(f"map.ring {shape} {a}: a place is two fractions of the window")
    for a, b in got["joins"]:
        if a not in got["at"] or b not in got["at"]:
            refuse(f"the card joins {a} and {b}, and has no such element")
    for a, b, _ in got["connections"]:
        for c in (a, b):
            if c not in got["components"]:
                refuse(f"a connection names {c}, and map.live has no {c}")
    return got


def wrap(text, most):
    lines, line = [], ""
    for w in str(text).split():
        if line and len(line) + 1 + len(w) > most:
            lines.append(line)
            line = w
        else:
            line = f"{line} {w}".strip()
    return lines + ([line] if line else [])


def esc(s):
    return str(s).replace("&", "&amp;").replace("<", "&lt;").replace(">", "&gt;").replace('"', "&quot;")


def card_layer(m, ox):
    """The diagram drawn on the card: a veil over the art, the connections, each address and what stands there."""
    art, at, comps, on = m["art"], m["at"], m["components"], m["on"]
    W, H = art["width"], art["height"]
    here = {a: [c for c in comps if on[c] == a] for a in at}
    t = [f'<rect class="veil" x="{ox}" y="0" width="{W}" height="{H}"/>']
    pairs = {}
    for a, b, _ in m["connections"]:
        if on[a] != on[b]:
            pairs.setdefault(tuple(sorted((on[a], on[b]))), []).append(comps[a]["seen"] != "repo" and comps[b]["seen"] != "repo")
    for (pa, pb), firm in sorted(pairs.items()):
        A, B = at[pa], at[pb]
        t.append(f'<line class="wire{"" if all(firm) else " unseen"}" data-ends="{pa} {pb}" x1="{ox + A["x"]}" y1="{A["y"]}" x2="{ox + B["x"]}" y2="{B["y"]}"/>')
    for a, p in at.items():
        x, y, r = ox + p["x"], p["y"], p["r"]
        rows = [(comps[c]["name"], comps[c]["seen"]) for c in here[a]] or [("missing", "missing")]
        if r:
            t.append(f'<circle class="spot{"" if here[a] else " gone"}" data-at="{a}" cx="{x}" cy="{y}" r="{r}"/>')
        side = p.get("label", "left" if p["x"] < W / 2 - 20 else "right")
        if side == "row":
            text = "  ·  ".join(n for n, _ in rows)
            rows, side = [(text, "repo")], "below"
        n = len(rows)
        w = max(len(s) for s, _ in rows) * 10.5 + 18
        if side == "below":
            tx, anchor, ty = x, "middle", y + r + 32
            rx = tx - w / 2
        elif side == "left":
            tx, anchor, ty = x - r - 14, "end", y - (n - 1) * 12 + 6
            rx = tx - w + 9
        else:
            tx, anchor, ty = x + r + 14, "start", y - (n - 1) * 12 + 6
            rx = tx - 9
        t.append(f'<rect class="tag" x="{rx:.0f}" y="{ty - 20}" width="{w:.0f}" height="{n * 24 + 6}" rx="6"/>')
        ids = [c for c in here[a]] if here[a] else [""]
        if len(rows) == 1 and len(ids) > 1:
            ids = [" ".join(ids)]
        t += [f'<text class="name {s}" data-at="{a}" data-c="{ids[i]}" x="{tx}" y="{ty + i * 24}" text-anchor="{anchor}">{esc(name)}</text>' for i, (name, s) in enumerate(rows)]
    return "".join(t)


def margin_panels(m, x_left, x_right, height):
    """What stands where, in the left margin; connections, missing and conflicts in the right."""
    at, comps, on = m["at"], m["components"], m["on"]
    left = []
    for a, p in at.items():
        lines = []
        for c in [c for c in comps if on[c] == a]:
            lines += [(f'row {comps[c]["seen"]}' if i == 0 else "row more", l) for i, l in enumerate(wrap(f'{comps[c]["name"]}: {comps[c]["is"]}', 64))]
        left.append((f'{p["card"]}: {p["is"]}', lines or [("row gone", "missing")]))
    left.append((f'seen, as of {m["asof"]}', [(f"row {k}", f"{k}: {v}") for k, v in m["seen"].items()]))
    right = [("Connections", [("row", f'{comps[a]["name"]} to {comps[b]["name"]}: {how}') for a, b, how in m["connections"]])]
    for head, d, cls in (("Missing", m["missing"], "gone"), ("Conflicts", m["conflicts"], "conflict")):
        right.append((head, [(f"row {cls}" if i == 0 else "row more", l) for k, v in d.items() for i, l in enumerate(wrap(f"{k}: {v}", 62))]))
    t = []
    for x0, blocks, top in ((x_left, left, 40), (x_right, right, 110)):   # the right column starts below the select
        lines = sum(len(ls) for _, ls in blocks)
        step = min(22, (height - top - len(blocks) * 36) / lines)   # the lines close up until the column fits
        y = top
        for head, ls in blocks:
            t.append(f'<text class="head" x="{x0}" y="{y:.0f}">{esc(head)}</text>')
            y += 24
            for cls, line in ls:
                t.append(f'<text class="{cls}" x="{x0}" y="{y:.0f}">{esc(line)}</text>')
                y += step
            y += 12
    return "".join(t)


def own_drawing(m, k, th, ox, uid):
    """A theme drawn with its own hand into the card's holes: its holes, symbols, lines and type. No art."""
    at, title = m["at"], m["title"]
    W, H = m["art"]["width"], m["art"]["height"]
    dash = ' stroke-dasharray="10 7"' if th["line"] == "dashed" else ""
    t = [f'<g class="th th-{k}">']
    t.append(f'<rect class="th-sheet" x="{ox}" y="0" width="{W}" height="{H}"/>')
    if th["grid"]:
        t.append(f'<pattern id="grid-{uid}-{k}" width="40" height="40" patternUnits="userSpaceOnUse" x="{ox}" y="0">'
                 f'<path class="th-grid" d="M 40 0 L 0 0 0 40"/></pattern>'
                 f'<rect x="{ox}" y="0" width="{W}" height="{H}" fill="url(#grid-{uid}-{k})"/>')
    t.append(f'<text class="th-title" x="{ox + title["x"]}" y="{title["y"]}" text-anchor="middle">{esc(title["text"])}</text>')
    for a, b in m["joins"]:
        A, B = at[a], at[b]
        line = f'x1="{ox + A["x"]}" y1="{A["y"]}" x2="{ox + B["x"]}" y2="{B["y"]}"'
        if th["line"] == "double":
            t.append(f'<line class="th-line" {line} stroke-width="{th["stroke"] * 3}"/><line class="th-gap" {line} stroke-width="{th["stroke"]}"/>')
        else:
            t.append(f'<line class="th-line" {line} stroke-width="{th["stroke"]}"{dash}/>')
    tri = at["triangle"]
    x, y = ox + tri["x"], tri["y"]
    t.append(f'<polygon class="th-shape" points="{x - 160},{y - 65} {x + 160},{y - 65} {x},{y + 105}" stroke-width="{th["stroke"]}"{dash}/>')
    f = at["forest"]
    n, w = 24, f["w"]
    for i in range(n):
        cx = ox + f["x"] - w / 2 + (i + .5) * w / n
        hgt = 70 + (i * 37 % 5) * 9
        t.append(f'<polygon class="th-shape" points="{cx - 17:.0f},{f["y"] + 60} {cx + 17:.0f},{f["y"] + 60} {cx:.0f},{f["y"] + 60 - hgt}" stroke-width="{th["stroke"]}"/>')
    t.append(f'<line class="th-line" x1="{ox + f["x"] - w / 2}" y1="{f["y"] + 60}" x2="{ox + f["x"] + w / 2}" y2="{f["y"] + 60}" stroke-width="{th["stroke"]}"/>')
    t.append(f'<text class="th-word big" x="{ox + f["x"]}" y="{f["y"] - 115}" text-anchor="middle">{esc(f["word"])}</text>')
    for a, p in at.items():
        if not p["r"]:
            continue
        x, y, r = ox + p["x"], p["y"], p["r"]
        t.append(f'<circle class="th-hole" data-at="{a}" cx="{x}" cy="{y}" r="{r}" stroke-width="{th["stroke"]}"{dash}/>')
        if th["line"] == "double":
            t.append(f'<circle class="th-ring" cx="{x}" cy="{y}" r="{r + 7}" stroke-width="{th["stroke"] / 2}"/>')
        sym = {"glyph": p["glyph"], "code": p["code"], "letter": (p["word"] or p["code"])[:1], "word": p["word"] or p["code"]}[th["symbols"]]
        size = {"glyph": r * .9, "code": r * .5, "letter": r * 1.05, "word": min(22, 1.6 * r / (.58 * max(len(sym), 1)))}[th["symbols"]]
        t.append(f'<text class="th-sym {th["symbols"]}" x="{x}" y="{y + size * .35:.1f}" text-anchor="middle" font-size="{size:.1f}">{esc(sym)}</text>')
        if p["word"] and th["symbols"] != "word":
            ly = y - r - 14 if a in ("l1", "r1", "l2", "r2") else y + r + 24
            t.append(f'<text class="th-word" x="{x}" y="{ly}" text-anchor="middle">{esc(p["word"])}</text>')
    t.append('</g>')
    return "".join(t)


COVER_PARTS = {"tree": "U0", "triangle": "J1", "ask": "J2", "thoughts": "J3", "c": "U2", "achievements": "TP1", "workflows": "TP2",
               "compatibility": "TP3", "heartbeat": "TP4", "health": "TP5", "alerts": "TP6", "r": "U3",
               "l1": "SW1", "r1": "SW2", "l2": "SW3", "r2": "SW4"}
CONTROLS = ("l1", "r1", "l2", "r2")
COVER_SHAPES = {"wide": (2560, 1600, 150), "tall": (1180, 1900, 260)}   # a tall one shaped like a phone
# The cover's themes: each draws the same radial card in one domain's own language.
COVER_THEMES = {"circuit": "Circuit board", "processor": "Processor", "breadboard": "Breadboard", "neural": "Neural"}
COVERS = [f"cover-{t}-{s}.svg" for t in COVER_THEMES for s in COVER_SHAPES]


def cover_geometry(m, shape):
    """Where everything stands on a cover of this shape: the brain in the middle, the bus ring
    round it, every other element at its place in map.ring, and the point on the brain's edge
    each one is wired to, straight in towards the middle."""
    CW, CH, foot = COVER_SHAPES[shape]
    H = CH - foot
    ring = m["ring"]
    P = {a: (round(x * CW), round(y * H)) for a, (x, y) in ring[shape].items()}
    bw, bh = ring["brain"][shape]
    cx, cy, hw, hh = CW / 2, H / 2, CW * bw / 2, H * bh / 2

    def edge(x, y, grow=0):
        dx, dy = x - cx, y - cy
        t = min((hw + grow) / abs(dx) if dx else 1e9, (hh + grow) / abs(dy) if dy else 1e9)
        return round(cx + dx * t), round(cy + dy * t)
    return {"CW": CW, "CH": CH, "H": H, "foot": foot, "P": P, "cx": cx, "cy": cy, "hw": hw, "hh": hh, "edge": edge,
            "big": shape == "tall"}


def svg_open(g, style):
    return [f'<svg xmlns="http://www.w3.org/2000/svg" viewBox="0 0 {g["CW"]} {g["CH"]}" preserveAspectRatio="xMidYMid slice"><style>{style}</style>']


def ortho(x1, y1, x2, y2, c=26, cls=""):
    """A routed trace: straight, then a 45-degree corner, then straight."""
    k = f' class="{cls}"' if cls else ""
    if x1 == x2 or y1 == y2:
        return f'<line{k} x1="{x1}" y1="{y1}" x2="{x2}" y2="{y2}"/>'
    sx, sy = (1 if x2 > x1 else -1), (1 if y2 > y1 else -1)
    c = min(c, abs(x2 - x1), abs(y2 - y1))
    return f'<polyline{k} points="{x1},{y1} {x1},{y2 - sy * c} {x1 + sx * c},{y2} {x2},{y2}"/>'


def perimeter(g, inset, step):
    """Points every `step` along a rectangle `inset` in from the drawing's edge."""
    W, H = g["CW"] - 2 * inset, g["H"] - 2 * inset
    n = max(1, int(2 * (W + H) // step))
    pts = []
    for i in range(n):
        d = i * 2 * (W + H) / n
        if d < W:
            pts.append((inset + d, inset))
        elif d < W + H:
            pts.append((inset + W, inset + d - W))
        elif d < 2 * W + H:
            pts.append((inset + W - (d - W - H), inset + H))
        else:
            pts.append((inset, inset + H - (d - 2 * W - H)))
    return [(round(x), round(y)) for x, y in pts]


def brain_label(g, text, cls="lab"):
    return f'<text class="{cls}" x="{g["cx"] - g["hw"]:.0f}" y="{g["cy"] - g["hh"] - 16:.0f}">{esc(text)}</text>'


def draw_circuit(m, g):
    at, P, CW, H = m["at"], g["P"], g["CW"], g["H"]
    f = 30 if g["big"] else 22
    t = svg_open(g, 'path,line,polyline,rect,circle,polygon{fill:none;stroke:#93a9bf;stroke-width:2.5;stroke-linecap:round;stroke-linejoin:round}'
                 '.cu{stroke:#c2703d;stroke-width:3.5}.pad{fill:#f7f9fb;stroke:#6f8aa6}.via{fill:#93a9bf;stroke:none}.cuv{fill:#c2703d;stroke:none}'
                 '.chip{fill:#f7f9fb;stroke:#6f8aa6}.edge{stroke:#b7c7d8;stroke-dasharray:14 10}.ink{stroke:#6f8aa6}'
                 f'text{{font:600 {f}px ui-monospace,Menlo,Consolas,monospace;fill:#7a8ea3;letter-spacing:.06em}}.dg{{fill:#a4b5c7;font-size:{f - 4}px}}'
                 f'.lab{{fill:#c2703d;font-size:{f}px}}.tb{{font-size:{f - 2}px}}.tbh{{font-size:{f + 4}px;fill:#4a5d72}}')
    e = 30
    t.append(f'<rect class="edge" x="{e}" y="{e}" width="{CW - 2 * e}" height="{g["CH"] - 2 * e}" rx="24"/>')
    for hx, hy in ((90, 90), (CW - 90, 90), (90, H - 90), (CW - 90, H - 90)):
        t.append(f'<circle class="ink" cx="{hx}" cy="{hy}" r="26"/><circle cx="{hx}" cy="{hy}" r="14"/>')
    for fx, fy in ((170, 90), (CW - 170, 90), (170, H - 90)):
        t.append(f'<circle cx="{fx}" cy="{fy}" r="16"/><circle class="via" cx="{fx}" cy="{fy}" r="6"/>')
    # the forest: a ground ring round the whole board, stitched with vias
    t.append(f'<rect x="140" y="140" width="{CW - 280}" height="{H - 280}" rx="30"/>')
    t += [f'<circle class="via" cx="{x}" cy="{y}" r="5"/>' for x, y in perimeter(g, 140, 120)]
    # C: the bus ring round the brain
    cx, cy, hw, hh = g["cx"], g["cy"], g["hw"], g["hh"]
    t.append(f'<rect x="{cx - hw - 34:.0f}" y="{cy - hh - 34:.0f}" width="{2 * hw + 68:.0f}" height="{2 * hh + 68:.0f}" rx="22"/>')
    t.append(f'<rect class="cu" x="{cx - hw - 46:.0f}" y="{cy - hh - 46:.0f}" width="{2 * hw + 92:.0f}" height="{2 * hh + 92:.0f}" rx="28"/>')
    # the brain: a large chip footprint, pins all round
    t.append(f'<rect class="chip" x="{cx - hw:.0f}" y="{cy - hh:.0f}" width="{2 * hw:.0f}" height="{2 * hh:.0f}" rx="10"/>')
    for k in range(int(2 * hw // 40)):
        x = cx - hw + 20 + k * 40
        t.append(f'<line x1="{x:.0f}" y1="{cy - hh:.0f}" x2="{x:.0f}" y2="{cy - hh - 16:.0f}"/><line x1="{x:.0f}" y1="{cy + hh:.0f}" x2="{x:.0f}" y2="{cy + hh + 16:.0f}"/>')
    for k in range(int(2 * hh // 40)):
        y = cy - hh + 20 + k * 40
        t.append(f'<line x1="{cx - hw:.0f}" y1="{y:.0f}" x2="{cx - hw - 16:.0f}" y2="{y:.0f}"/><line x1="{cx + hw:.0f}" y1="{y:.0f}" x2="{cx + hw + 16:.0f}" y2="{y:.0f}"/>')
    t.append(brain_label(g, "U0  BRAIN: WHAT YOU BRING"))
    # every element wired in to the brain; the entry and the run in copper
    for a, (x, y) in P.items():
        ex, ey = g["edge"](x, y, 46)
        t.append(ortho(x, y, ex, ey, cls="cu" if a in ("triangle", "r") else ""))
        t.append(f'<circle class="{"cuv" if a in ("triangle", "r") else "via"}" cx="{ex}" cy="{ey}" r="7"/>')
    # the entry reaches out through the top, the run through the bottom
    x, y = P["triangle"]
    for dx in (-36, 0, 36):
        t.append(ortho(x + dx, y - 40, x + dx * 5, 0, cls="cu" if dx == 0 else ""))
    x, y = P["r"]
    t.append(f'<line class="cu" x1="{x}" y1="{y}" x2="{x}" y2="{g["CH"]}"/>')
    for a, (x, y) in P.items():
        if a in CONTROLS:
            side = -1 if x < CW / 2 else 1
            w, h = (170, 118) if g["big"] else (150, 104)
            t.append(f'<rect class="chip" x="{x - w / 2}" y="{y - h / 2}" width="{w}" height="{h}" rx="6"/>')
            for k in range(4):
                py = y - h / 2 + 18 + k * (h - 36) / 3
                edge_x = x + side * w / 2
                t.append(f'<line x1="{edge_x}" y1="{py:.0f}" x2="{edge_x + side * 14}" y2="{py:.0f}"/>')
                t.append(ortho(edge_x + side * 14, round(py), 0 if side < 0 else CW, round(py + (k - 1.5) * 50), 26))
            t.append(f'<text x="{x}" y="{y + 9}" text-anchor="middle">{esc(at[a]["code"])}</text>')
            t.append(f'<text class="dg" x="{x - w / 2}" y="{y - h / 2 - 12}">{COVER_PARTS[a]}</text>')
        else:
            r = 34 if a == "triangle" else 24
            if a == "triangle":
                t.append(f'<polygon class="cu" points="{x - 70},{y - 32} {x + 70},{y - 32} {x},{y + 46}"/>')
            t.append(f'<circle class="pad" cx="{x}" cy="{y}" r="{r}"/><circle class="{"cuv" if a in ("triangle", "r") else "via"}" cx="{x}" cy="{y}" r="{r * .34:.0f}"/>')
            t.append(f'<text x="{x + r + 12}" y="{y - 6}">{esc(at[a]["code"])}</text><text class="dg" x="{x + r + 12}" y="{y + f}">{COVER_PARTS[a]}</text>')
    # the title block
    bw, bh = (520, 165) if g["big"] else (470, 150)
    bx, by = (CW / 2 - bw / 2, H - 70 - bh) if g["big"] else (CW - 150 - bw, H - 70 - bh)
    t.append(f'<rect class="chip" x="{bx:.0f}" y="{by}" width="{bw}" height="{bh}"/><line x1="{bx:.0f}" y1="{by + bh / 3:.0f}" x2="{bx + bw:.0f}" y2="{by + bh / 3:.0f}"/>'
             f'<line x1="{bx:.0f}" y1="{by + 2 * bh / 3:.0f}" x2="{bx + bw:.0f}" y2="{by + 2 * bh / 3:.0f}"/><line x1="{bx + bw / 2:.0f}" y1="{by + bh / 3:.0f}" x2="{bx + bw / 2:.0f}" y2="{by + bh}"/>'
             f'<text class="tbh" x="{bx + 18:.0f}" y="{by + bh / 3 - 16:.0f}">THE MISSING LAYER</text>'
             f'<text class="tb" x="{bx + 18:.0f}" y="{by + 2 * bh / 3 - 16:.0f}">BOARD COVER</text><text class="tb" x="{bx + bw / 2 + 18:.0f}" y="{by + 2 * bh / 3 - 16:.0f}">REV 02</text>'
             f'<text class="tb" x="{bx + 18:.0f}" y="{by + bh - 16:.0f}">GRAMMAR ONLY</text><text class="tb" x="{bx + bw / 2 + 18:.0f}" y="{by + bh - 16:.0f}">SHEET 1 OF 1</text>')
    return t


def draw_processor(m, g):
    at, P, CW, H = m["at"], g["P"], g["CW"], g["H"]
    f = 30 if g["big"] else 22
    t = svg_open(g, 'line,polyline,rect,circle{fill:none;stroke:#7d8b9b;stroke-width:2.5;stroke-linejoin:round}'
                 '.die{stroke:#5b6b7c;stroke-width:4}.seal{stroke:#a9b4c0;stroke-dasharray:10 8}.blk{fill:#eef2f6;stroke:#5b6b7c}'
                 '.core{fill:#ece8f6;stroke:#6b4fbb;stroke-width:3.5}.cell{stroke:#cfc6ea;stroke-width:1.5}.bus{stroke:#9aa6b4;stroke-width:3}'
                 '.hot{stroke:#6b4fbb;stroke-width:3.5}.pad{fill:#dfe5ec;stroke:#7d8b9b;stroke-width:2}'
                 f'text{{font:700 {f}px ui-monospace,Menlo,Consolas,monospace;fill:#3e4c5b;letter-spacing:.05em}}'
                 f'.w{{font-weight:500;font-size:{f - 6}px;fill:#7d8b9b}}.lab{{fill:#6b4fbb}}')
    t.append(f'<rect class="die" x="30" y="30" width="{CW - 60}" height="{H - 60}"/><rect class="seal" x="58" y="58" width="{CW - 116}" height="{H - 116}"/>')
    # the forest: the pad ring, a bond pad every so often all round the die
    for x, y in perimeter(g, 100, 84):
        t.append(f'<rect class="pad" x="{x - 13}" y="{y - 13}" width="26" height="26"/>')
    cx, cy, hw, hh = g["cx"], g["cy"], g["hw"], g["hh"]
    # C: the interconnect, two rings round the core
    for grow in (40, 60):
        t.append(f'<rect class="bus" x="{cx - hw - grow:.0f}" y="{cy - hh - grow:.0f}" width="{2 * hw + 2 * grow:.0f}" height="{2 * hh + 2 * grow:.0f}"/>')
    # the brain: the core, an array of cells
    t.append(f'<rect class="core" x="{cx - hw:.0f}" y="{cy - hh:.0f}" width="{2 * hw:.0f}" height="{2 * hh:.0f}"/>')
    for k in range(1, int(2 * hw // 64)):
        t.append(f'<line class="cell" x1="{cx - hw + k * 64:.0f}" y1="{cy - hh:.0f}" x2="{cx - hw + k * 64:.0f}" y2="{cy + hh:.0f}"/>')
    for k in range(1, int(2 * hh // 64)):
        t.append(f'<line class="cell" x1="{cx - hw:.0f}" y1="{cy - hh + k * 64:.0f}" x2="{cx + hw:.0f}" y2="{cy - hh + k * 64:.0f}"/>')
    t.append(brain_label(g, "CORE  BRAIN: WHAT YOU BRING"))
    for a, (x, y) in P.items():
        ex, ey = g["edge"](x, y, 60)
        hot = "hot" if a in ("triangle", "r") else "bus"
        for k in (-10, 0, 10):
            if abs(ex - x) > abs(ey - y):
                t.append(ortho(x, y + k, ex, ey + k, 20, hot))
            else:
                t.append(ortho(x + k, y, ex + k, ey, 20, hot))
    for a, (x, y) in P.items():
        w, h = (250, 118) if a in CONTROLS else (200, 92)
        if g["big"]:
            h += 20
        t.append(f'<rect class="blk" x="{x - w / 2}" y="{y - h / 2}" width="{w}" height="{h}"/>')
        t.append(f'<text x="{x - w / 2 + 14}" y="{y - h / 2 + f + 10}">{esc(at[a]["code"])}</text>')
        t.append(f'<text class="w" x="{x - w / 2 + 14}" y="{y + h / 2 - 16}">{esc((at[a]["word"] or COVER_PARTS[a]).upper())}</text>')
    return t


def draw_breadboard(m, g):
    at, P, CW, H = m["at"], g["P"], g["CW"], g["H"]
    f = 30 if g["big"] else 22
    wires = ["#d9534f", "#f0ad4e", "#4cae4c", "#3b73b9", "#8e6bbf", "#5a5a5a"]
    t = svg_open(g, 'line,path,rect,circle,polygon{fill:none;stroke:#6f6a60;stroke-width:2.5;stroke-linecap:round;stroke-linejoin:round}'
                 '.plus{stroke:#d9534f;stroke-width:3}.minus{stroke:#3b73b9;stroke-width:3}.chan{fill:#ebe6db;stroke:none}'
                 '.ic{fill:#ebe7de;stroke:#4a4740;stroke-width:3}.pin{fill:#b9b3a6;stroke:none}.part{fill:#fbf9f4;stroke:#4a4740}'
                 '.wire{stroke-width:7;opacity:.85}'
                 f'text{{font:700 {f}px ui-monospace,Menlo,Consolas,monospace;fill:#5d584f;letter-spacing:.05em}}.lab{{fill:#d9534f}}')
    # the forest: the power rails along the top and the bottom, feeding everything
    for y0 in (70, H - 110):
        t.append(f'<line class="plus" x1="40" y1="{y0}" x2="{CW - 40}" y2="{y0}"/><line class="minus" x1="40" y1="{y0 + 40}" x2="{CW - 40}" y2="{y0 + 40}"/>')
        t.append(f'<text class="lab" x="16" y="{y0 + 8}">+</text><text x="16" y="{y0 + 48}" style="fill:#3b73b9">-</text>')
    cx, cy, hw, hh = g["cx"], g["cy"], g["hw"], g["hh"]
    # the centre channel the brain straddles
    t.append(f'<rect class="chan" x="0" y="{cy - 16:.0f}" width="{CW}" height="32"/>')
    # C: the pair of jumper buses either side of the brain
    t.append(f'<rect x="{cx - hw - 36:.0f}" y="{cy - hh - 36:.0f}" width="{2 * hw + 72:.0f}" height="{2 * hh + 72:.0f}" rx="18" stroke-dasharray="4 12"/>')
    # the brain: a DIP chip with its notch and two rows of legs
    t.append(f'<rect class="ic" x="{cx - hw:.0f}" y="{cy - hh:.0f}" width="{2 * hw:.0f}" height="{2 * hh:.0f}" rx="8"/>')
    t.append(f'<path d="M {cx - hw:.0f} {cy - 30:.0f} a 30 30 0 0 1 0 60"/>')
    for k in range(int(2 * hw // 48)):
        x = cx - hw + 24 + k * 48
        t.append(f'<rect class="pin" x="{x - 9:.0f}" y="{cy - hh - 20:.0f}" width="18" height="20"/><rect class="pin" x="{x - 9:.0f}" y="{cy + hh:.0f}" width="18" height="20"/>')
    t.append(brain_label(g, "IC1  BRAIN: WHAT YOU BRING"))
    for i, (a, (x, y)) in enumerate(P.items()):
        ex, ey = g["edge"](x, y, 20)
        mx, my = (x + ex) / 2 + (ey - y) * .18, (y + ey) / 2 - (ex - x) * .18
        t.append(f'<path class="wire" stroke="{wires[i % len(wires)]}" d="M {x} {y} Q {mx:.0f} {my:.0f} {ex} {ey}"/>')
        t.append(f'<circle class="pin" cx="{ex}" cy="{ey}" r="8"/>')
    for i, (a, (x, y)) in enumerate(P.items()):
        if a in CONTROLS:
            s = 84 if g["big"] else 72
            t.append(f'<rect class="part" x="{x - s / 2}" y="{y - s / 2}" width="{s}" height="{s}" rx="8"/><circle class="part" cx="{x}" cy="{y}" r="{s * .3:.0f}"/>')
            t.append(f'<text x="{x}" y="{y + s / 2 + f + 6}" text-anchor="middle">{esc(at[a]["code"])}</text>')
        elif a == "triangle":
            t.append(f'<line x1="{x - 70}" y1="{y}" x2="{x + 70}" y2="{y}"/><polygon class="part" points="{x - 26},{y - 26} {x - 26},{y + 26} {x + 22},{y}"/>'
                     f'<line x1="{x + 24}" y1="{y - 26}" x2="{x + 24}" y2="{y + 26}"/><text x="{x}" y="{y - 40}" text-anchor="middle">{esc(at[a]["code"])}</text>')
        elif a == "r":
            t.append(f'<line x1="{x - 60}" y1="{y}" x2="{x - 14}" y2="{y}"/><line x1="{x - 14}" y1="{y - 30}" x2="{x - 14}" y2="{y + 30}"/>'
                     f'<line x1="{x + 14}" y1="{y - 30}" x2="{x + 14}" y2="{y + 30}"/><line x1="{x + 14}" y1="{y}" x2="{x + 60}" y2="{y}"/>'
                     f'<text x="{x}" y="{y + 30 + f + 6}" text-anchor="middle">{esc(at[a]["code"])}</text>')
        else:
            led = wires[i % len(wires)]
            t.append(f'<line x1="{x - 8}" y1="{y + 20}" x2="{x - 8}" y2="{y + 52}"/><line x1="{x + 8}" y1="{y + 20}" x2="{x + 8}" y2="{y + 44}"/>'
                     f'<path class="part" style="stroke:{led}" d="M {x - 22} {y + 20} L {x - 22} {y - 4} A 22 22 0 0 1 {x + 22} {y - 4} L {x + 22} {y + 20} Z"/>'
                     f'<text x="{x + 34}" y="{y + 8}">{esc(at[a]["code"])}</text>')
    return t


def draw_neural(m, g):
    at, P, CW, H = m["at"], g["P"], g["CW"], g["H"]
    f = 30 if g["big"] else 22
    t = svg_open(g, 'path,line,circle,ellipse{fill:none;stroke:#7d8a99;stroke-width:2.5;stroke-linecap:round}'
                 '.soma{fill:#fdf5f2;stroke:#e07a5f;stroke-width:3.5}.mem{stroke:#f0c4b6;stroke-dasharray:3 10;stroke-width:3}'
                 '.axon{stroke:#e07a5f;stroke-width:3.5}.node{fill:#ffffff;stroke:#5c6b7a;stroke-width:3}.hot{stroke:#e07a5f}'
                 '.syn{fill:#9aa7b5;stroke:none}.net{stroke:#d5dbe2;stroke-width:2}'
                 f'text{{font:600 {f}px ui-monospace,Menlo,Consolas,monospace;fill:#5c6b7a;letter-spacing:.05em}}.lab{{fill:#e07a5f}}')
    # the forest: a loose network of many small cells round the edge
    pts = perimeter(g, 110, 150)
    for i, (x, y) in enumerate(pts):
        nx, ny = pts[(i + 1) % len(pts)]
        t.append(f'<path class="net" d="M {x} {y} Q {(x + nx) / 2 + (17 if i % 2 else -17):.0f} {(y + ny) / 2 + (17 if i % 3 else -17):.0f} {nx} {ny}"/>')
        t.append(f'<circle class="syn" cx="{x}" cy="{y}" r="{5 + (i * 7) % 4}"/>')
    cx, cy, hw, hh = g["cx"], g["cy"], g["hw"], g["hh"]
    # C: the membrane round the cell; the brain: the cell body
    t.append(f'<ellipse class="mem" cx="{cx}" cy="{cy}" rx="{hw + 46:.0f}" ry="{hh + 46:.0f}"/>')
    t.append(f'<ellipse class="soma" cx="{cx}" cy="{cy}" rx="{hw:.0f}" ry="{hh:.0f}"/>')
    t.append(brain_label(g, "SOMA  BRAIN: WHAT YOU BRING"))
    for i, (a, (x, y)) in enumerate(P.items()):
        # each element joined to the cell by a curving dendrite, with two twigs by the element
        dx, dy = x - cx, y - cy
        n = (dx * dx / (hw * hw) + dy * dy / (hh * hh)) ** .5
        ex, ey = round(cx + dx / n), round(cy + dy / n)
        bend = .22 if i % 2 else -.22
        mx, my = (x + ex) / 2 - (ey - y) * bend, (y + ey) / 2 + (ex - x) * bend
        hot = "axon" if a in ("triangle", "r") else ""
        t.append(f'<path class="{hot}" d="M {ex} {ey} Q {mx:.0f} {my:.0f} {x} {y}"/>')
        for s in (-1, 1):
            t.append(f'<path d="M {x} {y} q {s * 30 + (x - mx) * .15:.0f} {-24 + (y - my) * .15:.0f} {s * 52 + (x - mx) * .25:.0f} {-8 + (y - my) * .25:.0f}"/>')
        r = 22 if a not in CONTROLS else 30
        t.append(f'<circle class="node{" hot" if hot else ""}" cx="{x}" cy="{y}" r="{r}"/><circle class="syn" cx="{x}" cy="{y}" r="7"/>')
        t.append(f'<text x="{x + r + 12}" y="{y + 8}">{esc(at[a]["code"])}</text>')
    return t


COVER_DRAW = {"circuit": draw_circuit, "processor": draw_processor, "breadboard": draw_breadboard, "neural": draw_neural}


def write_covers(m, folder):
    """Every cover: each theme, for a wide window and for a tall one."""
    out = []
    for theme in COVER_THEMES:
        for shape in COVER_SHAPES:
            g = cover_geometry(m, shape)
            path = os.path.join(folder, f"cover-{theme}-{shape}.svg")
            with open(path, "w", encoding="utf-8") as fh:
                fh.write("".join(COVER_DRAW[theme](m, g)) + "</svg>\n")
            out.append(path)
    return out


def write_map(folder=None, out=None):
    m = map_sheets(folder or os.path.join(HERE, "map"))
    art, tri, themes = m["art"], m["at"]["triangle"], m["themes"]
    W, H = art["width"], art["height"]
    side = W // 2                     # landscape: the card in the middle of a 2:1 surface, the margins beside it

    def surface(cls, ox, sw, panels):
        entry = f'{ox + tri["x"] - 150},{tri["y"] - 75} {ox + tri["x"] + 150},{tri["y"] - 75} {ox + tri["x"]},{tri["y"] + 95}'
        drawn = "".join(own_drawing(m, k, th, ox, cls) for k, th in themes.items() if th["draw"] == "own")
        return (f'<svg class="{cls}" viewBox="0 0 {sw} {H}" preserveAspectRatio="xMidYMid meet" role="img" aria-label="The Missing Layer card">'
                f'<image class="art" href="{esc(art["file"])}" x="{ox}" y="0" width="{W}" height="{H}"/>{drawn}'
                f'<g class="diagram">{card_layer(m, ox)}{panels}</g>'
                f'<a href="explore" aria-label="The entry: explore"><polygon points="{entry}" fill="transparent"/></a></svg>')

    def vars(th):
        return " ".join(f"--{k.replace('_', '-')}: {v};" for k, v in th.items() if k not in ("name", "by", "draw", "symbols", "line", "grid", "stroke"))
    first = next(iter(themes))
    picked = lambda k: f'body:has(select[name="theme"] option[value="{k}"]:checked)'
    themes_css = (f"body {{ {vars(themes[first])} }}\n"
                  + "\n".join(f'{picked(k)} {{ {vars(th)} }}' for k, th in themes.items())
                  + "\n" + "\n".join(f'{picked(k)} .th-{k} {{ display: inline; }}' for k, th in themes.items() if th["draw"] == "own")
                  + "\n" + "\n".join(f'{picked(k)} image.art {{ display: inline; }}' for k, th in themes.items() if th["draw"] == "art"))
    theme_options = "".join(f'<option value="{k}"{" selected" if k == first else ""}>{esc(th["name"])}</option>' for k, th in themes.items())
    wide = surface("wide", side, W + 2 * side, margin_panels(m, 28, side + W + 36, H))
    tall = surface("tall", 0, W, "")
    html = f"""<!doctype html>
<html lang="en"><head><meta charset="utf-8"><meta name="viewport" content="width=device-width, initial-scale=1"><meta name="color-scheme" content="light"><meta http-equiv="Content-Security-Policy" content="script-src 'none'; object-src 'none'; base-uri 'none'"><title>The Missing Layer: map</title><style>
html, body {{ margin: 0; height: 100%; overflow: hidden; }}
body {{ background: var(--page); color: var(--ink); }}
svg {{ width: 100vw; height: 100vh; height: 100dvh; display: block; }}
.tall, .diagram, .th, image.art {{ display: none; }}
@media (orientation: portrait) {{ .wide {{ display: none; }} .tall {{ display: block; }} }}
body:has(select[name="overlay"] option[value="live"]:checked) .diagram {{ display: inline; }}
form {{ position: fixed; top: .6rem; right: .8rem; margin: 0; font: 15px/1 Georgia, serif; display: flex; gap: .5rem; }}
select {{ font: inherit; color: var(--ink); background: var(--tag); border: 1px solid var(--tag-line); border-radius: 4px; padding: .25rem .4rem; }}
label {{ color: var(--ink); }}
.th-sheet {{ fill: var(--page); }}
.th-grid {{ fill: none; stroke: var(--muted); stroke-width: .6; opacity: .45; }}
.th-line, .th-ring {{ stroke: var(--ink); fill: none; }}
.th-gap {{ stroke: var(--page); }}
.th-shape {{ fill: none; stroke: var(--ink); stroke-linejoin: round; }}
.th-hole {{ fill: var(--hole); stroke: var(--ink); }}
.th-sym {{ fill: var(--ink); font-family: "DejaVu Sans", "Segoe UI Symbol", sans-serif; }}
.th-sym.code, .th-sym.word {{ font-family: var(--font); font-weight: 700; }}
.th-sym.letter {{ font-family: var(--font); font-weight: 800; }}
.th-word, .th-title {{ paint-order: stroke; stroke: var(--page); stroke-width: 8px; stroke-linejoin: round; }}
.th-word {{ font-size: 22px; fill: var(--muted); }}
.th-word.big {{ font-size: 54px; fill: var(--ink); }}
.th-title {{ font-size: 64px; font-weight: 700; fill: var(--ink); }}
.veil {{ fill: var(--veil); opacity: var(--veil-opacity); }}
.wire {{ stroke: var(--wire); stroke-width: 2.5; opacity: var(--wire-opacity); }}
.wire.unseen {{ stroke-dasharray: 8 7; }}
.spot {{ fill: none; stroke: var(--ink); stroke-width: 3; }}
.spot.gone {{ fill: none; stroke: var(--gone); stroke-dasharray: 6 6; }}
.tag {{ fill: var(--tag); stroke: var(--tag-line); stroke-width: 1; }}
text {{ font-family: var(--font); fill: var(--ink); }}
.name {{ font-size: 18px; font-weight: 600; }}
.head {{ font-size: 18px; font-weight: 700; }}
.row {{ font-size: 15px; }}
.connector, .session {{ fill: var(--seen); }}
.repo {{ fill: var(--repo); }}
text.gone {{ fill: var(--gone); }}
.conflict {{ fill: var(--conflict); }}
.row.more {{ fill: var(--muted); }}
a:focus-visible polygon {{ stroke: var(--seen); stroke-width: 4; }}
{themes_css}
</style></head><body><form><label>Theme <select name="theme">{theme_options}</select></label><label>Overlay <select name="overlay"><option value="none" selected>None</option><option value="live">Live components</option></select></label></form>
{wide}
{tall}
</body></html>
"""
    out = out or os.path.join(HERE, "map.html")
    with open(out, "w", encoding="utf-8") as f:
        f.write(html)
    return out


if __name__ == "__main__":
    if sys.argv[1:2] == ["map"]:
        print(write_map())
        print(*write_covers(map_sheets(os.path.join(HERE, "map")), HERE), sep="\n")
    else:
        main()

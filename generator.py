#!/usr/bin/env python3
# The generator for a terminal. It takes the same sheets as the generator in the browser
# and makes of them what a terminal can: lines of text out, numbers and typed lines in.
# A sheet names no device, so nothing in it changes between the two. This file holds the
# same grammar of a sheet and the same floppy; how a move is offered, how a thing is
# shown and where a box is kept are its own answers. It needs only Python 3.
#   python3 sheets.py               then pick by number
# With apps beside it (apps/<app>/app.json with "sheets"), or on a mounted carrier, it
# reads the sheets from there. With nothing beside it, it fetches them from the site.
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
# Where apps are: two folders up beside this file, then on a mounted carrier.
APPS = [d for d in [os.path.join(HERE, "..", "..", "apps")] + [os.path.join(p, "code", "apps") for p in ["/media/daq", "/Volumes/DAQ", *glob.glob("/media/*/DAQ"), *glob.glob("/run/media/*/DAQ")]
                                                                 if os.path.exists(os.path.join(p, "stick.json"))] if os.path.isdir(d)]
NAME, ID, AT = (re.compile(r"^[^./\\:]+" + r"\.[^./\\:]+" * n + "$") for n in (0, 1, 2))


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


# How a page looks is said in a few plain words, the same as in the browser. A terminal has
# no paper, type or corners of its own to set, so it honours the accent, as the nearest of
# its colours, and the space; the rest it knows and lets be.
COLOUR = re.compile(r"^#[0-9a-f]{6}$", re.I)
LOOK = {"paper": COLOUR, "ink": COLOUR, "accent": COLOUR, "face": ["sans", "serif", "mono"], "size": ["small", "medium", "large"],
        "space": ["tight", "normal", "roomy"], "corner": ["square", "soft", "round"]}
DEVICE = "terminal"


def here(j):
    on = j.get("on")
    return on is None or DEVICE in (on if isinstance(on, list) else [on])


def checked(j):
    if not plain(j) or not isinstance(j.get("id"), str) or not ID.match(j["id"]):
        refuse("a JSON needs an id of two levels, like email.wire")
    only(j, ["id", "says", "on", "kinds", "boxes", "here", "moves", "look"], j["id"])
    if "on" in j and (j["on"] == [] or not all(isinstance(d, str) and NAME.match(d) for d in (j["on"] if isinstance(j["on"], list) else [j["on"]]))):
        refuse(f'{j["id"]}: "on" names the devices this JSON is for, like browser')
    if "look" in j:
        if not plain(j["look"]):
            refuse(f"{j['id']}: a look is words and what they are set to")
        only(j["look"], list(LOOK), f"{j['id']}.look")
        for k, v in j["look"].items():
            if not (isinstance(v, str) and (LOOK[k].match(v) if k in ("paper", "ink", "accent") else v in LOOK[k])):
                refuse(f'{j["id"]}.look: "{k}" is ' + ("a colour like #1a2b3c" if k in ("paper", "ink", "accent") else "one of " + ", ".join(LOOK[k])))
    names = set()
    for key in ("kinds", "boxes", "here", "moves"):
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
            if key in ("boxes", "here") and not (isinstance(v, str) and (NAME.match(v) or AT.match(v))):
                refuse(f"{j['id']}.{name}: a box names the kind it holds")
            if key == "moves":
                checked_move(v, f"{j['id']}.{name}")
    return j


loaded, timers, shown = {}, set(), {}
carried = {"head": [], "tail": []}   # records of a floppy that belong to another generator
lock = threading.RLock()


def each(key):
    return [{"id": i, "name": n, "at": f"{i}.{n}", "key": key, "v": v} for i in sorted(loaded) if here(loaded[i]) for n, v in sorted((loaded[i].get(key) or {}).items())]


def every(key):
    # Only what is meant for this device counts. The boxes are those kept for every run and
    # those this run holds for itself (a JSON lists them under "here").
    return each("boxes") + [dict(b, key="boxes", mine=True) for b in each("here")] if key == "boxes" else each(key)


mine = {}   # what the boxes of this run alone hold: gone when it ends, never on a floppy


def mine_only(at):
    return any(b["at"] == at and b.get("mine") for b in every("boxes"))


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
    if mine_only(at):
        return list(mine.get(at, []))
    got = boxes().get(at)
    return got if isinstance(got, list) else []


# ---- a move ------------------------------------------------------------------------------
def arrive(box, thing, by, hops):
    kind = kind_of(box)
    if "waits" in kind:
        refuse(f"{by} waits for {kind['waits']}, which is not loaded")
    it = {p: word(thing.get(p)) for p in kind["parts"]}
    if mine_only(box):
        mine.setdefault(box, []).append(it)
    else:
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
    for b in sorted((b for b in every("boxes") if not b.get("mine")), key=lambda x: x["at"]):
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
    mine.clear()
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
        if "load" in g or ("id" in g and any(k in g for k in ("kinds", "boxes", "here", "moves", "look", "says", "on"))):
            j = checked(g if "load" not in g else fetched(g["load"]) if isinstance(g["load"], str) else g["load"])
            shipped_one = "load" in g and isinstance(g["load"], str)
            if j["id"] in loaded and not shipped_one and stringify(loaded[j["id"]]) != stringify(j):
                refuse(f"{j['id']} is already loaded and this one differs; unload it first")
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


def looks():
    out = {}
    for i in sorted(loaded):
        if here(loaded[i]):
            out.update(loaded[i].get("look") or {})   # in the order of the addresses, a later one over an earlier
    return out


def tint(text):
    # The accent, as the nearest of the terminal's 256 colours, and only when a person is reading.
    accent = looks().get("accent")
    if not accent or not sys.stdout.isatty():
        return text
    r, g, b = (round(int(accent[i:i + 2], 16) / 255 * 5) for i in (1, 3, 5))
    return f"\033[38;5;{16 + 36 * r + 6 * g + b}m{text}\033[0m"


def page(told=None):
    away = [i for i in sorted(loaded) if not here(loaded[i])]
    print(f"The Missing Layer, in a terminal. {'loaded: ' + ', '.join(sorted(loaded)) if loaded else 'nothing is loaded'}" + (f"; not for a {DEVICE}: {', '.join(away)}" if away else ""))
    moves = every("moves")
    for x in sorted(every("kinds") + every("boxes") + moves, key=lambda x: x["at"]):
        print(tint(x["at"]))
        v = x["v"]
        ends = [kind_of(b) for b in (v.get("when"), v.get("from"), v.get("to")) if b] if x["key"] == "moves" else [kind_of(x["at"])] if x["key"] == "boxes" else []
        lacks = next((k for k in ends if "waits" in k), None)
        if lacks:
            print(f"  waits for {lacks['waits']}, which is not loaded")
        elif x["key"] == "kinds":
            print(f"  a {x['name']} has: {', '.join(v)}")
        elif x["key"] == "boxes":
            held = in_box(x["at"])
            print(f"  holds {len(held)} {ends[0]['name']}" + (", in this run only" if x.get("mine") else ""))
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
MAP_KEYS = {"map.card": ("art", "at", "title", "joins"), "map.live": ("asof", "seen", "components", "connections"), "map.on": ("on", "missing", "conflicts"), "map.themes": ("themes",), "map.ring": ("ring",), "map.domains": ("domains",)}


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
            got[k] = j if j["id"] in ("map.ring", "map.domains") else j.get(k)
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
    around = set(got["at"]) - {ring["center"], ring["bus"], ring["base"]}
    if set(ring["numbers"]) != set(got["at"]):
        refuse("map.ring must number every element of the card")
    for shape in ("wide", "tall"):
        if set(ring[shape]) != around:
            refuse(f"map.ring {shape} must place exactly {', '.join(sorted(around))}")
        for a, xy in [*ring[shape].items(), *((n, j[shape]) for n, j in ring["junctions"].items())]:
            if len(xy) != 2 or not all(0 <= v <= 1 for v in xy):
                refuse(f"map.ring {shape} {a}: a place is two fractions of the window")
    joined = [a for j in ring["junctions"].values() for a in j["joins"]]
    if len(joined) != len(set(joined)) or not set(joined) <= around:
        refuse("map.ring: a junction joins elements that stand round the brain, each at most once")
    doms = got["domains"]
    for k, d in doms["domains"].items():
        if not isinstance(d.get("title"), str) or set(d.get("words", {})) != set(DOMAIN_WORDS):
            refuse(f"domain {k} must say a title and a word for exactly {', '.join(DOMAIN_WORDS)}")
    for k, th in doms["themes"].items():
        if not re.fullmatch(r"[a-z]+", k) or set(th) != {"name", "group", "domain", "draw"}:
            refuse(f"cover theme {k} must be a lowercase name and say name, group, domain and draw")
        if th["domain"] not in doms["domains"] or th["draw"] not in SKINS:
            refuse(f"cover theme {k}: no domain {th['domain']} or no drawing {th['draw']} the generator knows")
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


import math

CONTROLS = ("l1", "r1", "l2", "r2")
DOMAIN_WORDS = ("ask", "thoughts", "achievements", "workflows", "compatibility", "heartbeat", "health", "alerts", "r", "forest", "controls")
COVER_SHAPES = {"wide": (2560, 1600, 150), "tall": (1180, 1960, 260)}   # a tall one shaped like a phone


def cover_themes(m):
    return m["domains"]["themes"]


def cover_files(m):
    return [f"cover-{t}-{s}.svg" for t in cover_themes(m) for s in COVER_SHAPES]


def cover_geometry(m, shape, theme):
    """Where everything stands on a cover of this shape, and what it is called in the theme's
    domain: the brain (C.0) in the middle, the interface ring (C.1) round it, every other
    element at its place in map.ring with its number and its word, the junctions (C.5, C.9)
    the branches meet at, and the wires: each element in to its junction or straight in to the
    brain, each junction in to the brain."""
    CW, CH, foot = COVER_SHAPES[shape]
    H = CH - foot
    ring, doms = m["ring"], m["domains"]
    dom = doms["domains"][doms["themes"][theme]["domain"]]
    P = {a: (round(x * CW), round(y * H)) for a, (x, y) in ring[shape].items()}
    J = {n: (round(j[shape][0] * CW), round(j[shape][1] * H)) for n, j in ring["junctions"].items()}
    via = {a: n for n, j in ring["junctions"].items() for a in j["joins"]}
    bw, bh = ring["brain"][shape]
    cx, cy, hw, hh = CW / 2, H / 2, CW * bw / 2, H * bh / 2
    gap = 46

    def edge(x, y, grow=0):
        dx, dy = x - cx, y - cy
        t = min((hw + grow) / abs(dx) if dx else 1e9, (hh + grow) / abs(dy) if dy else 1e9)
        return round(cx + dx * t), round(cy + dy * t)

    def word(a):
        return dom["words"]["controls"] if a in CONTROLS else dom["words"].get(a, "")
    links = [((P[a], J[via[a]]) if a in via else (P[a], edge(*P[a], gap)), a in ("tree", "r")) for a in P]
    links += [((J[n], edge(*J[n], gap)), False) for n in J]
    return {"CW": CW, "CH": CH, "H": H, "foot": foot, "P": P, "J": J, "cx": cx, "cy": cy, "hw": hw, "hh": hh, "gap": gap,
            "edge": edge, "links": links, "big": shape == "tall", "f": 30 if shape == "tall" else 22,
            "num": ring["numbers"], "word": word, "title": dom["title"], "at": m["at"]}


def ortho(x1, y1, x2, y2, c=26, cls=""):
    """A routed line: straight, then a 45-degree corner, then straight."""
    k = f' class="{cls}"' if cls else ""
    if x1 == x2 or y1 == y2:
        return f'<line{k} x1="{x1}" y1="{y1}" x2="{x2}" y2="{y2}"/>'
    sx, sy = (1 if x2 > x1 else -1), (1 if y2 > y1 else -1)
    c = min(c, abs(x2 - x1), abs(y2 - y1))
    return f'<polyline{k} points="{x1},{y1} {x1},{y2 - sy * c} {x1 + sx * c},{y2} {x2},{y2}"/>'


def bow(p, q, bend):
    """A quadratic curve from p to q, bowed to one side by `bend`."""
    (x1, y1), (x2, y2) = p, q
    mx, my = (x1 + x2) / 2 - (y2 - y1) * bend, (y1 + y2) / 2 + (x2 - x1) * bend
    return f"M {x1} {y1} Q {mx:.0f} {my:.0f} {x2} {y2}"


def curve(p, q, bend, cls=""):
    k = f' class="{cls}"' if cls else ""
    return f'<path{k} d="{bow(p, q, bend)}"/>'


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


def box(g, grow=0):
    return g["cx"] - g["hw"] - grow, g["cy"] - g["hh"] - grow, 2 * g["hw"] + 2 * grow, 2 * g["hh"] + 2 * grow


def rect(g, grow, cls, rx=0):
    x, y, w, h = box(g, grow)
    return f'<rect class="{cls}" x="{x:.0f}" y="{y:.0f}" width="{w:.0f}" height="{h:.0f}" rx="{rx}"/>'


def css(g, ink, muted, accent, accent2, font, more=""):
    f = g["f"]
    return (f'path,line,polyline,rect,circle,ellipse,polygon{{fill:none;stroke:{muted};stroke-width:2.5;stroke-linecap:round;stroke-linejoin:round}}'
            f'.ink{{stroke:{ink}}}.hot{{stroke:{accent};stroke-width:3.5}}.fill{{fill:{muted};stroke:none}}.fa{{fill:{accent};stroke:none}}'
            f'.fi{{fill:{ink};stroke:none}}.f2{{fill:{accent2};stroke:none}}.s2{{stroke:{accent2}}}.thin{{stroke-width:1.5}}.faint{{opacity:.45}}'
            f'text{{font:600 {f}px {font};fill:{ink};letter-spacing:.03em}}.n{{font-size:{f - 4}px;fill:{accent};font-weight:700}}'
            f'.w{{font-size:{f}px}}.lab{{font-size:{f}px;fill:{accent};font-weight:700;letter-spacing:.06em}}.sm{{font-size:{f - 6}px;fill:{muted}}}' + more)


def label(g, a, x, y, drop):
    """An element's number and its word in the domain, under it."""
    w = g["word"](a)
    t = f'<text class="n" x="{x}" y="{y + drop}" text-anchor="middle">{esc(g["num"][a])}</text>'
    return t + (f'<text class="w" x="{x}" y="{y + drop + g["f"] + 4}" text-anchor="middle">{esc(w)}</text>' if w else "")


def marks(g, base_at=None):
    """The words every theme writes: the brain, the interface ring, the junctions, the base. On a
    wide window they stand by what they name; on a phone, where the title covers the middle,
    they stand together as a legend at the top left."""
    x, y, w, h = box(g)
    if g["big"]:
        rows = [("lab", f'{g["num"]["c"]} BRAIN'), ("sm", "WHAT YOU BRING"), ("sm", g["title"].upper()),
                ("sm", f'{g["num"]["triangle"]} GAP / INTERFACE'), ("sm", f'{g["num"]["forest"]} {g["word"]("forest").upper()}')]
        t = [f'<text class="{c}" x="44" y="{150 + k * 32}">{esc(s)}</text>' for k, (c, s) in enumerate(rows)]
    else:
        bx, by = base_at or (round(g["cx"] + 330), g["P"]["r"][1] - 4)
        t = [f'<text class="lab" x="{x:.0f}" y="{y - g["gap"] - 14:.0f}">{esc(g["num"]["c"])}  {esc(g["title"].upper())} · BRAIN: WHAT YOU BRING</text>',
             f'<text class="sm" x="{x + w:.0f}" y="{y - g["gap"] - 14:.0f}" text-anchor="end">{esc(g["num"]["triangle"])} GAP / INTERFACE</text>',
             f'<text class="n" x="{bx}" y="{by}" text-anchor="middle">{esc(g["num"]["forest"])}</text>',
             f'<text class="w" x="{bx}" y="{by + g["f"] + 4}" text-anchor="middle">{esc(g["word"]("forest"))}</text>']
    for n, (jx, jy) in g["J"].items():
        t.append(f'<text class="sm" x="{jx}" y="{jy - 22}" text-anchor="middle">{esc(n)}</text>')
    return t


# ---- the skins: each draws the same card in one domain's own shape ------------------------

def skin_circuit(g):
    CW, H, P = g["CW"], g["H"], g["P"]
    t = [css(g, "#4a5d72", "#93a9bf", "#c2703d", "#6f8aa6", "ui-monospace,Menlo,Consolas,monospace",
             ".pad{fill:#f7f9fb;stroke:#6f8aa6}.chip{fill:#f7f9fb;stroke:#6f8aa6}.edge{stroke:#b7c7d8;stroke-dasharray:14 10}")]
    t.append(f'<rect class="edge" x="30" y="30" width="{CW - 60}" height="{g["CH"] - 60}" rx="24"/>')
    for hx, hy in ((90, 90), (CW - 90, 90), (90, H - 90), (CW - 90, H - 90)):
        t.append(f'<circle class="ink" cx="{hx}" cy="{hy}" r="26"/><circle cx="{hx}" cy="{hy}" r="14"/>')
    t.append(f'<rect x="140" y="140" width="{CW - 280}" height="{H - 280}" rx="30"/>')       # C.14: the ground ring
    t += [f'<circle class="fill" cx="{x}" cy="{y}" r="5"/>' for x, y in perimeter(g, 140, 120)]
    for (p, q), hot in g["links"]:
        t.append(ortho(*p, *q, cls="hot" if hot else ""))
        t.append(f'<circle class="{"fa" if hot else "fill"}" cx="{q[0]}" cy="{q[1]}" r="7"/>')
    t += [rect(g, 34, "", 22), rect(g, 46, "hot", 28), rect(g, 0, "chip", 10)]
    x, y, w, h = box(g)
    for k in range(int(w // 40)):
        px = x + 20 + k * 40
        t.append(f'<line x1="{px:.0f}" y1="{y:.0f}" x2="{px:.0f}" y2="{y - 16:.0f}"/><line x1="{px:.0f}" y1="{y + h:.0f}" x2="{px:.0f}" y2="{y + h + 16:.0f}"/>')
    for jx, jy in g["J"].values():
        t.append(f'<circle class="pad" cx="{jx}" cy="{jy}" r="14"/><circle class="fill" cx="{jx}" cy="{jy}" r="6"/>')
    for a, (x, y) in P.items():
        if a in CONTROLS:
            side = -1 if x < CW / 2 else 1
            cw, ch = (120, 84) if g["big"] else (150, 104)
            t.append(f'<rect class="chip" x="{x - cw / 2}" y="{y - ch / 2}" width="{cw}" height="{ch}" rx="6"/>')
            for k in range(4):
                py = round(y - ch / 2 + 18 + k * (ch - 36) / 3)
                ex = x + side * cw / 2
                t.append(f'<line x1="{ex}" y1="{py}" x2="{ex + side * 14}" y2="{py}"/>' + ortho(ex + side * 14, py, 0 if side < 0 else CW, round(py + (k - 1.5) * 50)))
            t.append(f'<text class="sm" x="{x}" y="{y + 9}" text-anchor="middle">IC</text>' + label(g, a, x, y, ch / 2 + 30))
        else:
            hot = a in ("tree", "r")
            t.append(f'<circle class="pad" cx="{x}" cy="{y}" r="24"/><circle class="{"fa" if hot else "fill"}" cx="{x}" cy="{y}" r="9"/>' + label(g, a, x, y, 52))
            if a == "tree":
                t += [ortho(x + dx, y - 26, x + dx * 6, 0, cls="hot" if dx == 0 else "") for dx in (-30, 0, 30)]
    if g["big"]:   # on a phone the legend names the board; there is no room for a title block
        return t, None
    bw, bh = 470, 110
    bx, by = CW - 150 - bw, H - 60 - bh
    t.append(f'<rect class="chip" x="{bx:.0f}" y="{by}" width="{bw}" height="{bh}"/><line x1="{bx:.0f}" y1="{by + bh / 2:.0f}" x2="{bx + bw:.0f}" y2="{by + bh / 2:.0f}"/>'
             f'<text x="{bx + 16:.0f}" y="{by + bh / 2 - 16:.0f}">{esc(g["title"].upper())}</text><text class="sm" x="{bx + 16:.0f}" y="{by + bh - 18:.0f}">BOARD COVER · REV 03 · SHEET 1 OF 1</text>')
    return t, None


def skin_processor(g):
    CW, H, P, f = g["CW"], g["H"], g["P"], g["f"]
    t = [css(g, "#3e4c5b", "#7d8b9b", "#6b4fbb", "#9aa6b4", "ui-monospace,Menlo,Consolas,monospace",
             ".die{stroke:#5b6b7c;stroke-width:4}.seal{stroke:#a9b4c0;stroke-dasharray:10 8}.blk{fill:#eef2f6;stroke:#5b6b7c}"
             ".core{fill:#ece8f6;stroke:#6b4fbb;stroke-width:3.5}.cell{stroke:#cfc6ea;stroke-width:1.5}.pad{fill:#dfe5ec;stroke:#7d8b9b;stroke-width:2}")]
    t.append(f'<rect class="die" x="30" y="30" width="{CW - 60}" height="{H - 60}"/><rect class="seal" x="58" y="58" width="{CW - 116}" height="{H - 116}"/>')
    t += [f'<rect class="pad" x="{x - 13}" y="{y - 13}" width="26" height="26"/>' for x, y in perimeter(g, 100, 84)]   # C.14: the pad ring
    for (p, q), hot in g["links"]:
        for k in (-9, 0, 9):
            if abs(q[0] - p[0]) > abs(q[1] - p[1]):
                t.append(ortho(p[0], p[1] + k, q[0], q[1] + k, 20, "hot" if hot else ""))
            else:
                t.append(ortho(p[0] + k, p[1], q[0] + k, q[1], 20, "hot" if hot else ""))
    t += [rect(g, 40, ""), rect(g, 58, ""), rect(g, 0, "core")]
    x, y, w, h = box(g)
    t += [f'<line class="cell" x1="{x + k * 64:.0f}" y1="{y:.0f}" x2="{x + k * 64:.0f}" y2="{y + h:.0f}"/>' for k in range(1, int(w // 64))]
    t += [f'<line class="cell" x1="{x:.0f}" y1="{y + k * 64:.0f}" x2="{x + w:.0f}" y2="{y + k * 64:.0f}"/>' for k in range(1, int(h // 64))]
    for jx, jy in g["J"].values():
        t.append(f'<rect class="blk" x="{jx - 16}" y="{jy - 16}" width="32" height="32"/>')
    for a, (x, y) in P.items():
        bw, bh = (200, 96) if g["big"] else ((250 if a in CONTROLS else 230), 92)
        small = ' style="font-size:22px"' if g["big"] else ""
        t.append(f'<rect class="blk" x="{x - bw / 2}" y="{y - bh / 2}" width="{bw}" height="{bh}"/>'
                 f'<text class="n" x="{x - bw / 2 + 12}" y="{y - bh / 2 + f + 2}">{esc(g["num"][a])}</text>'
                 f'<text class="w" x="{x - bw / 2 + 12}" y="{y + bh / 2 - 14}"{small}>{esc(g["word"](a) or "TREE")}</text>')
    return t, None


def skin_breadboard(g):
    CW, H, P, f = g["CW"], g["H"], g["P"], g["f"]
    wires = ["#d9534f", "#f0ad4e", "#4cae4c", "#3b73b9", "#8e6bbf", "#5a5a5a"]
    t = [css(g, "#4a4740", "#6f6a60", "#d9534f", "#3b73b9", "ui-monospace,Menlo,Consolas,monospace",
             ".ic{fill:#ebe7de;stroke:#4a4740;stroke-width:3}.pin{fill:#b9b3a6;stroke:none}.part{fill:#fbf9f4;stroke:#4a4740}.wire{stroke-width:7;opacity:.85}")]
    for y0 in (70, H - 110):   # C.14: the power rails
        t.append(f'<line class="hot" x1="40" y1="{y0}" x2="{CW - 40}" y2="{y0}"/><line class="s2" style="stroke-width:3" x1="40" y1="{y0 + 40}" x2="{CW - 40}" y2="{y0 + 40}"/>')
    t.append(f'<rect style="fill:#ebe6db;stroke:none" x="0" y="{g["cy"] - 16:.0f}" width="{CW}" height="32"/>')
    for i, ((p, q), hot) in enumerate(g["links"]):
        t.append(f'<path class="wire" style="stroke:{wires[i % len(wires)]}" d="{bow(p, q, .15)}"/>')
        t.append(f'<circle class="pin" cx="{q[0]}" cy="{q[1]}" r="8"/>')
    t += [rect(g, 36, "", 18).replace('class=""', 'style="stroke-dasharray:4 12"'), rect(g, 0, "ic", 8)]
    x, y, w, h = box(g)
    t.append(f'<path d="M {x:.0f} {g["cy"] - 30:.0f} a 30 30 0 0 1 0 60"/>')
    for k in range(int(w // 48)):
        px = x + 24 + k * 48
        t.append(f'<rect class="pin" x="{px - 9:.0f}" y="{y - 20:.0f}" width="18" height="20"/><rect class="pin" x="{px - 9:.0f}" y="{y + h:.0f}" width="18" height="20"/>')
    for jx, jy in g["J"].values():
        t.append(f'<circle class="fi" cx="{jx}" cy="{jy}" r="10"/>')
    for i, (a, (x, y)) in enumerate(P.items()):
        if a in CONTROLS:
            s = 80
            t.append(f'<rect class="part" x="{x - s / 2}" y="{y - s / 2}" width="{s}" height="{s}" rx="8"/><circle class="part" cx="{x}" cy="{y}" r="24"/>' + label(g, a, x, y, 70))
        else:
            led = wires[i % len(wires)]
            t.append(f'<line x1="{x - 8}" y1="{y + 20}" x2="{x - 8}" y2="{y + 50}"/><line x1="{x + 8}" y1="{y + 20}" x2="{x + 8}" y2="{y + 42}"/>'
                     f'<path class="part" style="stroke:{led}" d="M {x - 22} {y + 20} L {x - 22} {y - 4} A 22 22 0 0 1 {x + 22} {y - 4} L {x + 22} {y + 20} Z"/>' + label(g, a, x, y, 80))
    return t, None


def skin_neural(g):
    CW, H, P = g["CW"], g["H"], g["P"]
    t = [css(g, "#5c6b7a", "#7d8a99", "#e07a5f", "#9aa7b5", "ui-monospace,Menlo,Consolas,monospace",
             ".soma{fill:#fdf5f2;stroke:#e07a5f;stroke-width:3.5}.mem{stroke:#f0c4b6;stroke-dasharray:3 10;stroke-width:3}.node{fill:#fff;stroke:#5c6b7a;stroke-width:3}.net{stroke:#d5dbe2;stroke-width:2}")]
    pts = perimeter(g, 110, 150)   # C.14: a network of small cells round the edge
    for i, (x, y) in enumerate(pts):
        t.append(curve((x, y), pts[(i + 1) % len(pts)], .12 if i % 2 else -.12, "net") + f'<circle class="fill" cx="{x}" cy="{y}" r="{5 + i % 4}"/>')
    for i, ((p, q), hot) in enumerate(g["links"]):
        t.append(curve(q, p, .2 if i % 2 else -.2, "hot" if hot else ""))
    cx, cy = g["cx"], g["cy"]
    t.append(f'<ellipse class="mem" cx="{cx}" cy="{cy}" rx="{g["hw"] + 46:.0f}" ry="{g["hh"] + 46:.0f}"/><ellipse class="soma" cx="{cx}" cy="{cy}" rx="{g["hw"]:.0f}" ry="{g["hh"]:.0f}"/>')
    for jx, jy in g["J"].values():
        t.append(f'<circle class="fill" cx="{jx}" cy="{jy}" r="9"/><circle class="fill" cx="{jx + 14}" cy="{jy + 8}" r="5"/><circle class="fill" cx="{jx - 12}" cy="{jy + 10}" r="4"/>')
    for a, (x, y) in P.items():
        r = 30 if a in CONTROLS else 22
        t.append(f'<path d="M {x} {y} q 26 -30 52 -26"/><path d="M {x} {y} q -26 -30 -52 -22"/>'
                 f'<circle class="node{" hot" if a in ("tree", "r") else ""}" cx="{x}" cy="{y}" r="{r}"/><circle class="fill" cx="{x}" cy="{y}" r="7"/>' + label(g, a, x, y, r + 30))
    return t, None


def skin_raga(g):
    """Indian classical: the taal cycle round the drone, tabla heads, meend glides, an audience."""
    CW, H, P = g["CW"], g["H"], g["P"]
    cx, cy, hw, hh = g["cx"], g["cy"], g["hw"], g["hh"]
    t = [css(g, "#5b3a2e", "#9c7a62", "#d9822b", "#9b2d3a", "Georgia,'Times New Roman',serif",
             ".skin{fill:#fffaf2;stroke:#5b3a2e;stroke-width:3}.str{stroke:#c9ab8f;stroke-width:1.5}.rug{fill:#fbefe0;stroke:#9b2d3a}")]
    for k, dx in enumerate((-90, -30, 30, 90)):   # tanpura strings, top to bottom
        t.append(f'<line class="str" x1="{cx + dx * .4:.0f}" y1="0" x2="{cx + dx * 4:.0f}" y2="{H}"/>')
    for row in range(3):   # C.14: the audience, in rows round the stage
        n = 22 + row * 6
        for i in range(n):
            a = 3.14159 * (.12 + .76 * i / (n - 1))
            t.append(f'<circle class="fill" cx="{cx - (CW * .46 + row * 40) * math.cos(a):.0f}" cy="{H + 260 - (330 + row * 40) * math.sin(a):.0f}" r="{6 - row}"/>')
    for i, ((p, q), hot) in enumerate(g["links"]):
        t.append(curve(p, q, .25 if i % 2 else -.25, "hot" if hot else "ink thin"))   # meend: the glide
    rx, ry = hw + g["gap"], hh + g["gap"]
    t.append(f'<ellipse class="ink" cx="{cx}" cy="{cy}" rx="{rx:.0f}" ry="{ry:.0f}"/><ellipse cx="{cx}" cy="{cy}" rx="{hw:.0f}" ry="{hh:.0f}" style="fill:#fdf3e6;stroke:#c9ab8f"/>')
    for k in range(16):   # C.1: the taal, sixteen beats; sam on one, khali on nine
        a = -math.pi / 2 + k * math.pi / 8
        x, y = cx + rx * math.cos(a), cy + ry * math.sin(a)
        x2, y2 = cx + (rx + 22) * math.cos(a), cy + (ry + 22) * math.sin(a)
        t.append(f'<line class="ink" x1="{x:.0f}" y1="{y:.0f}" x2="{x2:.0f}" y2="{y2:.0f}"/>')
        mark = {0: "×", 8: "○", 4: "2", 12: "3"}.get(k)
        if mark:
            t.append(f'<text class="lab" x="{cx + (rx + 50) * math.cos(a):.0f}" y="{cy + (ry + 50) * math.sin(a) + 9:.0f}" text-anchor="middle">{mark}</text>')
    for jx, jy in g["J"].values():
        t.append(f'<circle class="f2" cx="{jx}" cy="{jy}" r="10"/>')
    for a, (x, y) in P.items():
        if a in CONTROLS:
            t.append(f'<rect class="rug" x="{x - 64}" y="{y - 40}" width="128" height="80" rx="6"/><polygon class="s2" points="{x},{y - 28} {x + 44},{y} {x},{y + 28} {x - 44},{y}"/>' + label(g, a, x, y, 72))
        elif a == "r":
            t.append(f'<rect class="skin" x="{x - 60}" y="{y - 38}" width="120" height="76" rx="4"/>' + "".join(f'<line class="ink thin" x1="{x - 44}" y1="{y - 18 + k * 18}" x2="{x + 44}" y2="{y - 18 + k * 18}"/>' for k in range(3)) + label(g, a, x, y, 68))
        else:   # a tabla head: the skin, its ring, the syahi
            t.append(f'<circle class="skin" cx="{x}" cy="{y}" r="28"/><circle class="ink thin" cx="{x}" cy="{y}" r="20"/><circle class="{"fa" if a == "tree" else "fi"}" cx="{x}" cy="{y}" r="9"/>' + label(g, a, x, y, 58))
    return t, (g["cx"], H - 60)


def skin_blues(g):
    """Blues: a guitar neck across the board, the sound hole as the brain, notes, a 12-bar strip."""
    CW, H, P, f = g["CW"], g["H"], g["P"], g["f"]
    cx, cy, hw, hh = g["cx"], g["cy"], g["hw"], g["hh"]
    t = [css(g, "#2b3a55", "#7d8aa3", "#2f5da8", "#b04a3b", "Georgia,'Times New Roman',serif",
             ".neck{stroke:#c4ccd9}.knob{fill:#fff;stroke:#2b3a55;stroke-width:3}.cell{fill:#fff;stroke:#7d8aa3}")]
    for k in range(6):   # the strings, the full width
        y = cy - hh * .75 + k * hh * .3
        t.append(f'<line class="neck" style="stroke-width:{1.2 + k * .5:.1f}" x1="0" y1="{y:.0f}" x2="{CW}" y2="{y:.0f}"/>')
    for side in (-1, 1):   # frets closing in towards the sound hole, with inlays
        x = cx + side * (hw + g["gap"] + 30)
        step = 150
        for k in range(12):
            if not 0 < x < CW:
                break
            t.append(f'<line class="neck" x1="{x:.0f}" y1="{cy - hh * .8:.0f}" x2="{x:.0f}" y2="{cy + hh * .8:.0f}"/>')
            if k in (2, 4, 6, 8):
                t.append(f'<circle class="fill faint" cx="{x + side * step / 2:.0f}" cy="{cy:.0f}" r="9"/>')
            x += side * step
            step *= .94
    bars = "I I I I IV IV I I V IV I V".split()   # C.14: the twelve bars along the floor
    cw = (CW - 120) / 12
    for k, b in enumerate(bars):
        x = 60 + k * cw
        t.append(f'<rect class="cell" x="{x:.0f}" y="{H - 96}" width="{cw:.0f}" height="60"/><text class="sm" x="{x + cw / 2:.0f}" y="{H - 56}" text-anchor="middle">{b}</text>')
    for i, ((p, q), hot) in enumerate(g["links"]):
        t.append(curve(p, q, .22 if i % 2 else -.22, "hot" if hot else "ink thin"))   # slurs
    for grow in (g["gap"], g["gap"] - 10, g["gap"] - 22):   # C.1: the rosette round the sound hole
        t.append(f'<ellipse class="ink thin" cx="{cx}" cy="{cy}" rx="{hw + grow:.0f}" ry="{hh + grow:.0f}"/>')
    t.append(f'<ellipse cx="{cx}" cy="{cy}" rx="{hw:.0f}" ry="{hh:.0f}" style="fill:#e9ecf2;stroke:#2b3a55;stroke-width:3"/>')
    for jx, jy in g["J"].values():
        t.append(f'<ellipse class="fi" cx="{jx}" cy="{jy}" rx="14" ry="10" transform="rotate(-20 {jx} {jy})"/>')
    for a, (x, y) in P.items():
        if a in CONTROLS:   # an amp knob
            t.append(f'<circle class="knob" cx="{x}" cy="{y}" r="34"/><line class="ink" x1="{x}" y1="{y}" x2="{x + 18}" y2="{y - 24}"/>'
                     + "".join(f'<line class="thin" x1="{x + 44 * math.cos(a2):.0f}" y1="{y + 44 * math.sin(a2):.0f}" x2="{x + 52 * math.cos(a2):.0f}" y2="{y + 52 * math.sin(a2):.0f}"/>' for a2 in [2.4 + k * .75 for k in range(7)]) + label(g, a, x, y, 80))
        elif a == "r":   # a record
            t.append(f'<circle class="fi" cx="{x}" cy="{y}" r="40"/><circle style="stroke:#7d8aa3" cx="{x}" cy="{y}" r="30"/><circle style="stroke:#7d8aa3" cx="{x}" cy="{y}" r="20"/><circle class="f2" cx="{x}" cy="{y}" r="9"/>' + label(g, a, x, y, 70))
        elif a == "tree":   # the headstock and its six pegs
            t.append(f'<rect class="knob" x="{x - 34}" y="{y - 56}" width="68" height="112" rx="14"/>' + "".join(f'<circle class="fi" cx="{x + s * 48}" cy="{y - 34 + k * 34}" r="9"/>' for s in (-1, 1) for k in range(3)) + label(g, a, x, y, 84))
        else:   # a note
            t.append(f'<ellipse class="{"fa" if a in ("alerts",) else "fi"}" cx="{x}" cy="{y}" rx="20" ry="14" transform="rotate(-20 {x} {y})"/>'
                     f'<line class="ink" style="stroke-width:3" x1="{x + 18}" y1="{y - 4}" x2="{x + 18}" y2="{y - 62}"/><path class="ink" style="stroke-width:3" d="M {x + 18} {y - 62} q 22 14 14 38"/>' + label(g, a, x, y, 48))
    return t, None


def skin_pipeline(g):
    """Production: stages as boxes, pipes flowing in, a manifold round the plant, a distribution fan."""
    CW, H, P, f = g["CW"], g["H"], g["P"], g["f"]
    t = [css(g, "#33433c", "#7b8a83", "#2e8b57", "#c9772b", "system-ui,-apple-system,'Segoe UI',sans-serif",
             ".pipe{stroke:#7b8a83;stroke-width:12}.bore{stroke:#f4f6f4;stroke-width:6}.stage{fill:#fff;stroke:#33433c;stroke-width:2.5}.hotp{stroke:#2e8b57;stroke-width:12}")]
    rx, ry = P["r"]
    ends = max(8, CW // 230)
    for k in range(ends):   # C.14: the distribution field, a fan out to many ends
        ex = round(CW * (k + .5) / ends)
        t.append(f'<line class="thin" x1="{rx}" y1="{ry + 40}" x2="{ex}" y2="{H - 70}"/><rect class="stage" x="{ex - 22}" y="{H - 70}" width="44" height="30" rx="4"/>')
    for (p, q), hot in g["links"]:
        t.append(ortho(*p, *q, 30, "hotp" if hot else "pipe") + ortho(*p, *q, 30, "bore"))
        t.append(f'<circle class="{"fa" if hot else "fill"}" cx="{q[0]}" cy="{q[1]}" r="9"/>')
    t += [rect(g, 46, "ink", 18), rect(g, 0, "", 10).replace('class=""', 'style="fill:#eef3ef;stroke:#33433c;stroke-dasharray:12 8"')]
    x, y, w, h = box(g, 46)
    for k in range(1, int(w // 120)):
        px = x + k * 120
        t.append(f'<polyline class="hot" points="{px - 8:.0f},{y - 8:.0f} {px + 4:.0f},{y:.0f} {px - 8:.0f},{y + 8:.0f}"/><polyline class="hot" points="{px + 8:.0f},{y + h - 8:.0f} {px - 4:.0f},{y + h:.0f} {px + 8:.0f},{y + h + 8:.0f}"/>')
    for jx, jy in g["J"].values():   # a valve
        t.append(f'<polygon class="stage" points="{jx - 18},{jy - 12} {jx},{jy} {jx - 18},{jy + 12}"/><polygon class="stage" points="{jx + 18},{jy - 12} {jx},{jy} {jx + 18},{jy + 12}"/>')
    for a, (x, y) in P.items():
        if a in CONTROLS:
            t.append(f'<polygon class="stage" points="{x - 40},{y - 26} {x},{y} {x - 40},{y + 26}"/><polygon class="stage" points="{x + 40},{y - 26} {x},{y} {x + 40},{y + 26}"/><line class="ink" x1="{x}" y1="{y}" x2="{x}" y2="{y - 40}"/><line class="ink" x1="{x - 16}" y1="{y - 40}" x2="{x + 16}" y2="{y - 40}"/>' + label(g, a, x, y, 60))
        elif a == "tree":   # the source tank
            t.append(f'<path class="stage" d="M {x - 50} {y - 30} v 60 a 50 14 0 0 0 100 0 v -60"/><ellipse class="stage" cx="{x}" cy="{y - 30}" rx="50" ry="14"/>' + label(g, a, x, y, 70))
        else:
            bw, bh = 200, 72
            edge = ' style="stroke:#c9772b;stroke-width:3.5"' if a == "r" else ""
            t.append(f'<rect class="stage" x="{x - bw / 2}" y="{y - bh / 2}" width="{bw}" height="{bh}" rx="10"{edge}/>'
                     f'<text class="n" x="{x - bw / 2 + 12}" y="{y - bh / 2 + f}">{esc(g["num"][a])}</text><text class="w" x="{x}" y="{y + bh / 2 - 12}" text-anchor="middle">{esc(g["word"](a))}</text>')
    return t, None


def skin_flight(g):
    """Flight deck: round gauges, the attitude indicator as the brain, a heading bezel, the recorder's tape."""
    CW, H, P, f = g["CW"], g["H"], g["P"], g["f"]
    cx, cy = g["cx"], g["cy"]
    t = [css(g, "#2a3744", "#7a8794", "#d98a00", "#c0392b", "ui-monospace,Menlo,Consolas,monospace",
             ".gauge{fill:#fff;stroke:#2a3744;stroke-width:3}.tape{fill:#fff;stroke:#7a8794}.wave{stroke:#d98a00;stroke-width:2.5}")]
    for hx, hy in ((60, 60), (CW - 60, 60), (60, H - 150), (CW - 60, H - 150)):   # panel screws
        t.append(f'<circle cx="{hx}" cy="{hy}" r="14"/><line x1="{hx - 8}" y1="{hy - 8}" x2="{hx + 8}" y2="{hy + 8}"/>')
    t.append(f'<rect class="tape" x="40" y="{H - 110}" width="{CW - 80}" height="72" rx="6"/>')   # C.14: the recorder's tape
    t += [f'<line class="thin" x1="{x}" y1="{H - 110}" x2="{x}" y2="{H - 96 if x % 100 else H - 88}"/>' for x in range(60, CW - 40, 20)]
    t.append('<polyline class="wave" points="' + " ".join(f"{x},{H - 64 + 16 * math.sin(x / 37) * math.cos(x / 151):.0f}" for x in range(60, CW - 40, 12)) + '"/>')
    for (p, q), hot in g["links"]:
        t.append(ortho(*p, *q, 20, "hot" if hot else "thin"))
    x, y, w, h = box(g, g["gap"])
    t.append(rect(g, g["gap"], "ink", 30))
    for k in range(int(w // 30)):   # C.1: the heading bezel
        px = x + 15 + k * 30
        t.append(f'<line class="thin" x1="{px:.0f}" y1="{y:.0f}" x2="{px:.0f}" y2="{y + (16 if k % 3 else 26):.0f}"/>')
    t.append(rect(g, 0, "", 20).replace('class=""', 'style="fill:#eef3f8;stroke:#2a3744;stroke-width:3"'))
    t.append(f'<line class="hot" x1="{cx - g["hw"]:.0f}" y1="{cy:.0f}" x2="{cx + g["hw"]:.0f}" y2="{cy:.0f}"/>')   # the horizon
    t += [f'<line class="thin" x1="{cx - 60 + (k % 2) * 30:.0f}" y1="{cy + k * 40:.0f}" x2="{cx + 60 - (k % 2) * 30:.0f}" y2="{cy + k * 40:.0f}"/>' for k in (-3, -2, -1, 1, 2, 3)]
    for jx, jy in g["J"].values():
        t.append(f'<circle class="gauge" cx="{jx}" cy="{jy}" r="12"/><circle class="fa" cx="{jx}" cy="{jy}" r="4"/>')
    for i, (a, (x, y)) in enumerate(P.items()):
        if a in CONTROLS:   # a toggle switch
            t.append(f'<rect class="gauge" x="{x - 30}" y="{y - 46}" width="60" height="92" rx="12"/><line class="ink" style="stroke-width:6" x1="{x}" y1="{y + 10}" x2="{x + 14}" y2="{y - 30}"/><circle class="fa" cx="{x + 14}" cy="{y - 30}" r="9"/>' + label(g, a, x, y, 76))
        elif a == "tree":   # the beacon
            t.append(f'<line class="ink" x1="{x}" y1="{y + 30}" x2="{x}" y2="{y - 30}"/><circle class="fa" cx="{x}" cy="{y - 30}" r="8"/>'
                     f'<path class="hot" d="M {x - 26} {y - 52} a 36 36 0 0 1 52 0"/><path class="hot" d="M {x - 42} {y - 66} a 58 58 0 0 1 84 0"/>' + label(g, a, x, y, 60))
        else:   # a round gauge with its ticks and needle
            r = 34
            t.append(f'<circle class="gauge" cx="{x}" cy="{y}" r="{r}"/>')
            for k in range(9):
                a2 = math.radians(135 + k * 33.75)
                t.append(f'<line class="thin" x1="{x + (r - 4) * math.cos(a2):.0f}" y1="{y + (r - 4) * math.sin(a2):.0f}" x2="{x + (r - 12) * math.cos(a2):.0f}" y2="{y + (r - 12) * math.sin(a2):.0f}"/>')
            a2 = math.radians(160 + (i * 47) % 200)
            t.append(f'<line class="{"s2" if a == "alerts" else "hot"}" x1="{x}" y1="{y}" x2="{x + (r - 10) * math.cos(a2):.0f}" y2="{y + (r - 10) * math.sin(a2):.0f}"/><circle class="fi" cx="{x}" cy="{y}" r="5"/>' + label(g, a, x, y, r + 30))
    return t, None


SKINS = {"circuit": skin_circuit, "processor": skin_processor, "breadboard": skin_breadboard, "neural": skin_neural,
         "raga": skin_raga, "blues": skin_blues, "pipeline": skin_pipeline, "flight": skin_flight}


def write_covers(m, folder):
    """Every cover: each theme, for a wide window and for a tall one."""
    out = []
    for theme, th in cover_themes(m).items():
        for shape in COVER_SHAPES:
            g = cover_geometry(m, shape, theme)
            body, base_at = SKINS[th["draw"]](g)
            style, body = body[0], body[1:]
            svg = (f'<svg xmlns="http://www.w3.org/2000/svg" viewBox="0 0 {g["CW"]} {g["CH"]}" preserveAspectRatio="xMidYMid slice"><style>{style}</style>'
                   + "".join(body) + "".join(marks(g, base_at)) + "</svg>\n")
            path = os.path.join(folder, f"cover-{theme}-{shape}.svg")
            with open(path, "w", encoding="utf-8") as fh:
                fh.write(svg)
            out.append(path)
    return out


# The cover's paper and grid for each theme, and the select that picks one: written into
# cover.css and into the four copies of the page, from map/domains.json.
COVER_PAPER = {"circuit": ("#f7f9fb", "#e6edf4", "24px", "transparent"), "processor": ("#f3f5f8", "#e8ecf1", "16px", "transparent"),
               "breadboard": ("#f6f3ec", "transparent", "20px", "#d8d1c2"), "neural": ("#fbfaf7", "transparent", "24px", "transparent"),
               "raga": ("#fbf6ee", "transparent", "24px", "transparent"), "blues": ("#f4f2ee", "transparent", "24px", "transparent"),
               "pipeline": ("#f4f6f4", "#e7ece8", "32px", "transparent"), "flight": ("#f3f5f7", "#e5eaef", "20px", "transparent")}
PAGES = ("index.html", "explore.html", "serialize.html", "deserialize.html")


def cover_css(m):
    rules = ["/* Written by generator.py from map/domains.json: each cover theme's drawing, paper and grid. */"]
    for k, th in cover_themes(m).items():
        paper, line, cell, dot = COVER_PAPER[th["draw"]]
        rules.append(f'.cover:has(option[value="{k}"]:checked) {{ --wide: url("cover-{k}-wide.svg"); --tall: url("cover-{k}-tall.svg"); '
                     f'--paper: {paper}; --line: {line}; --cell: {cell}; --dot: {dot}; }}')
    return "\n".join(rules) + "\n"


def cover_select(m):
    themes, groups = cover_themes(m), {}
    first = next(iter(themes))
    for k, th in themes.items():
        groups.setdefault(th["group"], []).append(f'<option value="{k}"{" selected" if k == first else ""}>{esc(th["name"])}</option>')
    return '<select name="cover" aria-label="Cover theme">' + "".join(f'<optgroup label="{esc(gname)}">{"".join(opts)}</optgroup>' for gname, opts in groups.items()) + '</select>'


def write_cover_page(m, folder):
    """cover.css, and the select in the four copies of the page, from map/domains.json."""
    with open(os.path.join(folder, "cover.css"), "w", encoding="utf-8") as fh:
        fh.write(cover_css(m))
    page = open(os.path.join(folder, "index.html"), encoding="utf-8").read()
    page = re.sub(r'<select name="cover".*?</select>', lambda _: cover_select(m), page, count=1, flags=re.S)
    if '<link rel="stylesheet" href="cover.css">' not in page:
        page = page.replace('<link rel="stylesheet" href="board.css">', '<link rel="stylesheet" href="board.css"><link rel="stylesheet" href="cover.css">')
    out = [os.path.join(folder, "cover.css")]
    for name in PAGES:
        with open(os.path.join(folder, name), "w", encoding="utf-8") as fh:
            fh.write(page)
        out.append(os.path.join(folder, name))
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
        m = map_sheets(os.path.join(HERE, "map"))
        print(*write_covers(m, HERE), *write_cover_page(m, HERE), sep="\n")
    else:
        main()

#!/usr/bin/env python3
# The generator for a terminal. It takes the same sheets as the generator in the browser
# and makes of them what a terminal can: lines of text out, numbers and typed lines in.
# A sheet names no device, so nothing in it changes between the two. This file holds the
# same grammar of a sheet and the same floppy; how a move is offered, how a thing is
# shown and where a box is kept are its own answers. It needs only Python 3.
#   python3 generator.py            then pick by number
# A line that starts with { or [ is a shape, as in the browser's Shape box:
#   {"load": "email.wire"}  {"unload": "email.stub"}  a sheet pasted whole
#   {"do": "email.touch.send", "with": {"subject": "hi", "body": "there"}}
#   {"do": "email.touch.read", "pick": 1}
#   {"from": "email.wire.sent"}  {"to": "email.wire.inbox", "with": {...}}
#   {"keep": true}  and a floppy, which wipes and rebuilds
import json, os, re, sys, threading, urllib.request

ENGINE, FLOPPY = "2", 1474560
SITE = os.environ.get("MISSINGLAYER_SITE", "https://themissinglayer.org/")
HERE = os.path.dirname(os.path.abspath(sys.argv[0])) if sys.argv and sys.argv[0] not in ("", "-") else os.getcwd()
HOME = os.environ.get("MISSINGLAYER_HOME") or os.path.join(os.path.expanduser("~"), ".missinglayer")
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
    local = os.path.join(HERE, *rel.split("/"))
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


def menu():
    acts = []
    for m in sorted(every("moves"), key=lambda x: x["at"]):
        v = m["v"]
        ends = [kind_of(b) for b in (v.get("when"), v.get("from"), v.get("to")) if b]
        if not v.get("when") and not any("waits" in k for k in ends):
            acts.append((f"{m['name']}: " + (f"pick a {ends[0]['name']} in {v['from']}" if v.get("from") else f"make a {ends[0]['name']}, to {v['to']}"), ("move", m)))
    try:
        ships = list(read_json("contract.json").get("ships", {}))
    except (OSError, ValueError, AttributeError):
        ships = []
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


if __name__ == "__main__":
    main()

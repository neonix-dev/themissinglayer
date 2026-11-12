# Opens the page the way a visitor gets it and plays it with real input events.
# This file knows nothing about any page: the contract lists the claims, the proof
# says how each one is played. Reads only; changes nothing.
#   python3 observe.py <site> [contract] [proof]
import json, sys, time
from urllib.parse import urljoin
from hand import Hand, fetch

names = sys.argv[2:] + ["../contract.json", "../proof.json"][len(sys.argv) - 2:]
site, contract, proof = sys.argv[1].rstrip("/") + "/", json.load(open(names[0])), json.load(open(names[1]))
h = Hand()
h.say("Emulation.setDeviceMetricsOverride", width=390, height=760, deviceScaleFactor=2, mobile=True)

def nodes(node=None, parent=None):
    node = node or h.say("DOM.getDocument", depth=-1)["root"]
    a = node.get("attributes", [])
    node["has"], node["parent"] = dict(zip(a[::2], a[1::2])), parent
    node["words"] = "".join(c.get("nodeValue", "") for c in node.get("children", []) if c["nodeName"] == "#text").strip()
    yield node
    for child in node.get("children", []):
        yield from nodes(child, node)

def named(name):
    for node in nodes():
        if node["words"] == name and node["nodeName"] == "LABEL":
            return next(n for n in nodes(node) if n["nodeName"] == "INPUT")
        if node["nodeName"] != "TITLE" and name in (node["words"], node["has"].get("value")):
            return node
    sys.exit(f"nothing on the page is called {name!r}")

def heard():
    return [n for n in h.say("Accessibility.getFullAXTree")["nodes"] if not n.get("ignored")]

def said(n, key):
    return n.get(key, {}).get("value", "")

def here():
    past = h.say("Page.getNavigationHistory")
    return past["entries"][past["currentIndex"]]["url"]

def middle(name):
    q = h.say("DOM.getBoxModel", nodeId=named(name)["nodeId"])["model"]["content"]
    return (q[0] + q[4]) / 2, (q[1] + q[5]) / 2

def touch(name):
    x, y = middle(name)
    for kind in ("mousePressed", "mouseReleased"):
        h.say("Input.dispatchMouseEvent", type=kind, x=x, y=y, button="left", clickCount=1)
    time.sleep(0.5)

def type_in(text):
    h.say("Input.insertText", text=text)

def given(value):
    if not value.startswith("@"):
        return value
    at = contract
    for step in value[1:].split("."):
        at = at[int(step)] if isinstance(at, list) else at[step]
    return at

# Each move either acts (returns None) or answers whether something holds.
moves = {
    "touch": touch,
    "type": type_in,
    "open": lambda name: "open" in named(name)["parent"]["has"],
    "closed": lambda name: "open" not in named(name)["parent"]["has"],
    "at": lambda path: here() == urljoin(site, path),
    "exists": lambda name: bool(middle(name)) and fetch(urljoin(site, named(name)["has"]["href"])).status == 200,
    "holds": lambda name, text: any(said(n, "name") == name and said(n, "value") == text for n in heard() if said(n, "role") == "textbox"),
    "shows": lambda text: any(text in said(n, "name") for n in heard()),
    "hides": lambda text: not any(text in said(n, "name") for n in heard()),
}

held = []
for claim in contract["proves"]:
    h.say("Page.navigate", url=site)
    time.sleep(1)
    answers = [moves[move](*map(given, args)) for move, *args in proof.get(claim, [])]
    answers = [a for a in answers if a is not None]   # a claim with nothing checked does not hold
    held.append(bool(answers) and all(answers))
    print(f"  {'HELD  ' if held[-1] else 'FAILED'}  {claim}")
h.away()
sys.exit(0 if all(held) else 1)

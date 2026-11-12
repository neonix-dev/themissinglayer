# Opens the page the way a visitor gets it and plays it with real input events.
# This file knows nothing about any page: the contract lists the claims, the proof
# says how each one is played. Reads only; changes nothing.
#   python3 observe.py <site> [contract] [proof]
import json, sys, time
from urllib.parse import urljoin
from hand import Hand

names = sys.argv[2:] + ["../contract.json", "../proof.json"][len(sys.argv) - 2:]
site, contract, proof = sys.argv[1].rstrip("/") + "/", json.load(open(names[0])), json.load(open(names[1]))
h = Hand()
h.say("Emulation.setDeviceMetricsOverride", width=390, height=760, deviceScaleFactor=2, mobile=True)

def nodes(node=None, parent=None):
    node = node or h.say("DOM.getDocument", depth=-1)["root"]
    a = node.get("attributes", [])
    node["has"], node["parent"] = dict(zip(a[::2], a[1::2])), parent
    yield node
    for child in node.get("children", []):
        yield from nodes(child, node)

def words(node):
    return node.get("nodeValue", "") if node["nodeName"] == "#text" else "".join(map(words, node.get("children", [])))

def within(node, kind):
    while node and node["nodeName"] != kind:
        node = node["parent"]
    return node

def inside(node, other):
    while node and node is not other:
        node = node["parent"]
    return node is other

# A thing is called by all the text it holds, however that text is split into pieces
# inside it. Of the things with that name, the innermost is the one meant.
def named(name):
    hit = None
    for node in nodes():
        if node["nodeName"] in ("TITLE", "#text") or name not in (words(node).strip(), node["has"].get("value")):
            continue
        if hit is None or inside(node, hit):
            hit = node
    if hit is None:
        sys.exit(f"nothing on the page is called {name!r}")
    return next((n for n in nodes(hit, hit["parent"]) if n["nodeName"] == "INPUT"), hit) if hit["nodeName"] == "LABEL" else hit

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

# Asked of the browser itself, so the answer is the one a visitor would get. A site
# that answers every address with some page is caught by asking for one that cannot exist.
def served(url):
    frame = h.say("Page.getFrameTree")["frameTree"]["frame"]["id"]
    got = h.say("Network.loadNetworkResource", frameId=frame, url=url, options={"disableCache": True, "includeCredentials": False})["resource"]
    if not got.get("success") or got.get("httpStatusCode") != 200:
        return None
    body = ""
    while True:
        part = h.say("IO.read", handle=got["stream"])
        body += part["data"]
        if part["eof"]:
            h.say("IO.close", handle=got["stream"])
            return body

def exists(name):
    there = served(urljoin(here(), named(name)["has"]["href"]))
    return bool(middle(name)) and there is not None and there != served(urljoin(site, "no-such-page-7f3a/"))

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
    "open": lambda name: "open" in within(named(name), "DETAILS")["has"],
    "closed": lambda name: "open" not in within(named(name), "DETAILS")["has"],
    "at": lambda path: here() == urljoin(site, path),
    "exists": exists,
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

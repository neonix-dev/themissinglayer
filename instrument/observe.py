# Opens the page the way a visitor gets it, plays it with real input events,
# and checks each claim in ../contract.json. Reads only; changes nothing.
import base64, json, sys, time, urllib.request
from hand import Hand, find

site = sys.argv[1].rstrip("/") + "/"
shots = sys.argv[2] if len(sys.argv) > 2 else None
contract = json.load(open("../contract.json"))
h = Hand()
h.say("Emulation.setDeviceMetricsOverride", width=390, height=760, deviceScaleFactor=2, mobile=True)

def load(url=site):
    h.say("Page.navigate", url=url)
    time.sleep(1)

def tree():
    return h.say("DOM.getDocument", depth=-1)["root"]

def every(node, kind, out=None):
    out = [] if out is None else out
    if node["nodeName"].lower() == kind:
        out.append(node)
    for child in node.get("children", []):
        every(child, kind, out)
    return out

def attrs(node):
    a = node.get("attributes", [])
    return dict(zip(a[::2], a[1::2]))

def words(node):
    return "".join(c.get("nodeValue", "") for c in node.get("children", []) if c["nodeName"] == "#text").strip()

def menu(name):
    return next(d for d in every(tree(), "details") if words(find(d, "summary")) == name)

def touch(node):
    q = h.say("DOM.getBoxModel", nodeId=node["nodeId"])["model"]["content"]
    x, y = (q[0] + q[4]) / 2, (q[1] + q[5]) / 2
    for kind in ("mousePressed", "mouseReleased"):
        h.say("Input.dispatchMouseEvent", type=kind, x=x, y=y, button="left", clickCount=1)
    time.sleep(0.4)

def heard():
    return [n for n in h.say("Accessibility.getFullAXTree")["nodes"] if not n.get("ignored")]

def picture(name):
    if shots:
        data = h.say("Page.captureScreenshot", format="png")["data"]
        open(f"{shots}/{name}.png", "wb").write(base64.b64decode(data))

def here():
    hist = h.say("Page.getNavigationHistory")
    return hist["entries"][hist["currentIndex"]]["url"]

names = [m["menu"] for m in contract["menus"]]
results = []
load()
picture("1-closed")

results.append(all("open" not in attrs(d) for d in every(tree(), "details")))

touch(find(menu(names[0]), "summary"))
results.append("open" in attrs(menu(names[0])))

touch(find(menu(names[-1]), "summary"))
results.append("open" in attrs(menu(names[-1])) and "open" not in attrs(menu(names[0])))

touch(find(menu(names[0]), "summary"))
touch(find(menu("Open"), "summary"))
picture("2-file-open")
links = every(menu("Open"), "a")
wanted = contract["menus"][0]["items"][0]["opens"]
exist = [urllib.request.build_opener(urllib.request.ProxyHandler({})).open(site + attrs(a)["href"]).status == 200 for a in links]
results.append([words(a) for a in links] == [w["item"] for w in wanted] and all(exist))

touch(links[0])
time.sleep(1)
results.append(here() == site + wanted[0]["goes"])

load()
touch(find(menu("Edit"), "summary"))
field = find(menu("Edit"), "input")
touch(field)
h.say("Input.insertText", text="intent travels")
typed = next(n["value"]["value"] for n in heard() if n["role"]["value"] == "textbox")
touch(every(menu("Edit"), "input")[1])
emptied = next(n.get("value", {}).get("value", "") for n in heard() if n["role"]["value"] == "textbox")
results.append(typed == "intent travels" and emptied == "")

about = contract["menus"][-1]["items"][0]
def showing():
    return any(about["shows"] in n.get("name", {}).get("value", "") for n in heard())
touch(find(menu("Help"), "summary"))
before = showing()
touch(find(menu("Help"), "button"))
during = showing()
picture("3-about")
ok = next(b for b in every(tree(), "button") if words(b) == about["dismiss"])
touch(ok)
results.append(not before and during and not showing())

for claim, held in zip(contract["proves"], results):
    print(f"  {'HELD  ' if held else 'FAILED'}  {claim}")
h.away()
sys.exit(0 if all(results) and len(results) == len(contract["proves"]) else 1)

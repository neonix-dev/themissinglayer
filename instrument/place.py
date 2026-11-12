# Places a page with the browser's own DOM verbs: copy a node, rename it, set an
# attribute, set a text value. No markup, style or script is sent. This file knows
# nothing about any page: the contract says what is wanted, the base says which
# native piece each word becomes. The engine then writes out the document it holds.
#   python3 place.py [contract] [base] [page]
import json, re, sys, time
from hand import Hand, find

names = sys.argv[1:] + ["../contract.json", "window.json", "../index.html"][len(sys.argv) - 1:]
contract, base, page = json.load(open(names[0])), json.load(open(names[1])), names[2]
h = Hand()
h.say("Page.navigate", url="data:text/plain,seed")
time.sleep(0.5)
root = h.say("DOM.getDocument", depth=-1)["root"]
html, head, body = find(root, "html"), find(root, "head"), find(root, "body")
pre, word = find(root, "pre"), find(root, "#text")

# The engine made one bare element and one text node. Everything else is copied from them.
blank = h.say("DOM.copyTo", nodeId=find(root, "meta")["nodeId"], targetNodeId=body["nodeId"])["nodeId"]
for name in ("name", "content"):
    h.say("DOM.removeAttribute", nodeId=blank, name=name)

def fill(text, thing):
    def value(m):
        said = str(thing[m[1]])
        return re.sub(r"[^a-z0-9]+", "-", said.lower()).strip("-") if m[2] else said
    return re.sub(r"\{([^}:]+)(:slug)?\}", value, text)

def has(thing, words):
    first, _, rest = words.partition(".")
    return first in thing and (not rest or any(rest in one for one in thing[first]))

later = []
def place(parent, form, thing):
    kind, *parts = form
    if kind == "each":
        for one in thing[parts[0]]:
            place(parent, next(f for words, f in base["words"] if has(one, words)), one)
        return
    if kind == "later":
        return later.append((parts[0], thing))
    node = h.say("DOM.copyTo", nodeId=blank, targetNodeId=parent)["nodeId"]
    node = h.say("DOM.setNodeName", nodeId=node, name=kind)["nodeId"]
    for part in parts:
        if isinstance(part, dict):
            for key, value in part.items():
                h.say("DOM.setAttributeValue", nodeId=node, name=key, value=fill(value, thing))
        elif isinstance(part, str):
            text = h.say("DOM.copyTo", nodeId=word["nodeId"], targetNodeId=node)["nodeId"]
            h.say("DOM.setNodeValue", nodeId=text, value=fill(part, thing))
        else:
            place(node, part, thing)

for key, value in base.get("html", {}).items():
    h.say("DOM.setAttributeValue", nodeId=html["nodeId"], name=key, value=value)
for form in base["head"]:
    place(head["nodeId"], form, contract)
for form in base["body"]:
    place(body["nodeId"], form, contract)
for form, thing in later:
    place(body["nodeId"], form, thing)

# Take the scaffolding away, then let the engine write down what it holds.
h.say("DOM.removeNode", nodeId=blank)
h.say("DOM.removeNode", nodeId=pre["nodeId"])
document = h.say("DOM.getOuterHTML", nodeId=html["nodeId"])["outerHTML"]
open(page, "w", encoding="utf-8").write(document + "\n")
h.away()
print(f"Placed. The engine wrote {len(document)} characters to {page}.")

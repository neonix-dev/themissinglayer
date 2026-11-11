# Reads ../contract.json and places each piece with the browser's own DOM verbs:
# copy a node, rename it, set an attribute, set a text value. No markup, style or
# script is sent. When the board is complete the engine writes out its own document.
import json, re
from hand import Hand, find

contract = json.load(open("../contract.json"))
h = Hand()
root = h.say("DOM.getDocument", depth=-1)["root"]
html, head, body = find(root, "html"), find(root, "head"), find(root, "body")
pre, word = find(root, "pre"), find(root, "#text")

# The engine made one bare element and one text node. Everything else is copied from them.
blank = h.say("DOM.copyTo", nodeId=find(root, "meta")["nodeId"], targetNodeId=body["nodeId"])["nodeId"]
for name in ("name", "content"):
    h.say("DOM.removeAttribute", nodeId=blank, name=name)

def piece(parent, kind, text=None, **attrs):
    node = h.say("DOM.copyTo", nodeId=blank, targetNodeId=parent)["nodeId"]
    node = h.say("DOM.setNodeName", nodeId=node, name=kind)["nodeId"]
    for key, value in attrs.items():
        h.say("DOM.setAttributeValue", nodeId=node, name=key.replace("_", "-"), value=value)
    if text is not None:
        say(node, text)
    return node

def say(parent, text):
    node = h.say("DOM.copyTo", nodeId=word["nodeId"], targetNodeId=parent)["nodeId"]
    h.say("DOM.setNodeValue", nodeId=node, value=text)

def slug(text):
    return re.sub(r"[^a-z0-9]+", "-", text.lower()).strip("-")

def place_item(listing, item, shown):
    row = piece(listing, "li")
    label = item["item"]
    if "opens" in item:
        sub = piece(row, "details")
        piece(sub, "summary", label)
        inner = piece(sub, "menu")
        for child in item["opens"]:
            place_item(inner, child, shown)
    elif "goes" in item:
        piece(row, "a", label, href=item["goes"])
    elif "saves" in item:
        piece(row, "a", label, href=item["saves"], download=item["saves"])
    elif "accepts" in item:
        field = piece(row, "label", label + " ")
        piece(field, "input", type=item["accepts"], name=slug(label))
    elif "clears" in item:
        piece(row, "input", type="reset", value=label)
    elif "shows" in item:
        piece(row, "button", label, type="button", popovertarget=slug(label))
        shown.append(item)

h.say("DOM.setAttributeValue", nodeId=html["nodeId"], name="lang", value="en")
piece(head["nodeId"], "meta", charset="utf-8")
piece(head["nodeId"], "meta", name="viewport", content="width=device-width, initial-scale=1")
piece(head["nodeId"], "title", contract["title"])

piece(body["nodeId"], "h1", contract["title"])
bar = piece(body["nodeId"], "nav", aria_label="Menu bar")
table = piece(bar, "table", role="presentation")
strip = piece(piece(table, "tbody"), "tr")
shown = []
for menu in contract["menus"]:
    cell = piece(strip, "td", valign="top")
    drop = piece(cell, "details", name="menubar")
    piece(drop, "summary", menu["menu"])
    holder = piece(drop, "form", method="dialog") if any("accepts" in i for i in menu["items"]) else drop
    listing = piece(holder, "menu")
    for item in menu["items"]:
        place_item(listing, item, shown)

piece(body["nodeId"], "hr")
piece(piece(body["nodeId"], "main"), "p", contract["work area"])
piece(body["nodeId"], "hr")
piece(piece(body["nodeId"], "footer"), "small", contract["status line"])

for item in shown:
    box = piece(body["nodeId"], "div", popover="auto", id=slug(item["item"]))
    piece(box, "p", item["shows"])
    piece(box, "button", item["dismiss"], type="button",
          popovertarget=slug(item["item"]), popovertargetaction="hide")

# Take the scaffolding away, then let the engine write down what it holds.
h.say("DOM.removeNode", nodeId=blank)
h.say("DOM.removeNode", nodeId=pre["nodeId"])
document = h.say("DOM.getOuterHTML", nodeId=html["nodeId"])["outerHTML"]
open("../index.html", "w", encoding="utf-8").write(document + "\n")
h.away()
print(f"Placed. The engine wrote {len(document)} characters to index.html.")

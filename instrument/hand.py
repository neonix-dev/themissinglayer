# One connection to the browser's own protocol. Sends engine verbs, nothing else.
import json, sys, urllib.request, websocket

def connect():
    tabs = json.load(urllib.request.build_opener(urllib.request.ProxyHandler({})).open("http://127.0.0.1:9222/json/list"))
    page = next(t for t in tabs if t["type"] == "page")
    return websocket.create_connection(page["webSocketDebuggerUrl"], suppress_origin=True)

class Hand:
    def __init__(self):
        self.ws, self.n = connect(), 0
    def say(self, method, **params):
        self.n += 1
        self.ws.send(json.dumps({"id": self.n, "method": method, "params": params}))
        while True:
            msg = json.loads(self.ws.recv())
            if msg.get("id") == self.n:
                if "error" in msg:
                    sys.exit(f"{method}: {msg['error']}")
                return msg["result"]
    def away(self):
        self.ws.close()

def outline(node, depth=0):
    attrs = node.get("attributes", [])
    pairs = " ".join(f'{attrs[i]}="{attrs[i+1]}"' for i in range(0, len(attrs), 2))
    print("  " * depth + node["nodeName"].lower() + (f"  [{pairs}]" if pairs else ""))
    for child in node.get("children", []):
        outline(child, depth + 1)

def find(node, name):
    if node["nodeName"].lower() == name:
        return node
    for child in node.get("children", []):
        hit = find(child, name)
        if hit:
            return hit

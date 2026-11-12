# One connection to the browser's own protocol, over the standard library alone.
# Sends engine verbs, nothing else.
import base64, json, os, socket, struct, sys, urllib.request

PORT = os.environ.get("BROWSER", "9222")

def fetch(url):
    return urllib.request.build_opener(urllib.request.ProxyHandler({})).open(url)

class Hand:
    def __init__(self):
        tabs = json.load(fetch(f"http://127.0.0.1:{PORT}/json/list"))
        url = next(t for t in tabs if t["type"] == "page")["webSocketDebuggerUrl"]
        host, path = url[5:].split("/", 1)
        self.sock = socket.create_connection((host.split(":")[0], int(host.split(":")[1])))
        key = base64.b64encode(os.urandom(16)).decode()
        self.sock.sendall((f"GET /{path} HTTP/1.1\r\nHost: {host}\r\nUpgrade: websocket\r\n"
                           f"Connection: Upgrade\r\nSec-WebSocket-Key: {key}\r\n"
                           "Sec-WebSocket-Version: 13\r\n\r\n").encode())
        self.wire, self.n = self.sock.makefile("rb"), 0
        while self.wire.readline().strip():
            pass

    def say(self, method, **params):
        self.n += 1
        data = json.dumps({"id": self.n, "method": method, "params": params}).encode()
        size, mask = len(data), os.urandom(4)
        head = bytes([0x80 | size]) if size < 126 else b"\xfe" + struct.pack(">H", size) if size < 65536 else b"\xff" + struct.pack(">Q", size)
        self.sock.sendall(b"\x81" + head + mask + bytes(b ^ mask[i % 4] for i, b in enumerate(data)))
        while True:
            msg = json.loads(self.hear())
            if msg.get("id") == self.n:
                if "error" in msg:
                    sys.exit(f"{method}: {msg['error']}")
                return msg["result"]

    def hear(self):
        whole = b""
        while True:
            first, size = self.wire.read(2)
            size &= 127
            if size == 126:
                size = struct.unpack(">H", self.wire.read(2))[0]
            elif size == 127:
                size = struct.unpack(">Q", self.wire.read(8))[0]
            whole += self.wire.read(size)
            if first & 0x80:
                return whole.decode()

    def away(self):
        self.sock.close()

def find(node, name):
    if node["nodeName"].lower() == name:
        return node
    for child in node.get("children", []):
        hit = find(child, name)
        if hit:
            return hit

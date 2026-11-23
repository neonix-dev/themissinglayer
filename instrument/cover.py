# The acceptance check for the cover on an iPhone and in Chrome. Opens the site as each device
# gets it, with the window each one really shows, taps (or clicks) the shipped examples, types
# into what they make, and prints HELD or FAILED per claim. Reads only; changes nothing.
#   python3 cover.py <site> [--shots <folder>]
# The iPhones are emulated in Chromium: their window, pixel density, touch and user agent.
# Safari itself is not run here; its own toolbars are allowed for by the window sizes below.
import base64, json, os, sys, time
from hand import Hand

args = sys.argv[1:]
shots = args[args.index("--shots") + 1] if "--shots" in args else None
site = args[0].rstrip("/") + "/"
ROOT = os.path.join(os.path.dirname(os.path.abspath(__file__)), "..")
contract = json.load(open(os.path.join(ROOT, "contract.json"), encoding="utf-8"))
examples = [x["name"] for x in contract["examples"]]
IPHONE = "Mozilla/5.0 (iPhone; CPU iPhone OS 18_0 like Mac OS X) AppleWebKit/605.1.15 (KHTML, like Gecko) Version/18.0 Mobile/15E148 Safari/604.1"
# name, width, height (the part of the screen Safari or Chrome leaves to the page), density, touch
DEVICES = [
    ("iphone-15", 393, 659, 3, True),             # upright, Safari's bars showing
    ("iphone-se", 375, 553, 2, True),             # the smallest iPhone still sold, upright
    ("iphone-15-landscape", 734, 340, 3, True),   # on its side, Safari's bars showing
    ("chrome-laptop", 1280, 720, 1, False),
    ("chrome-desktop", 1440, 900, 1, False),
]

h = Hand()
held = []


def claim(text, ok):
    held.append(bool(ok))
    print(f"  {'HELD  ' if ok else 'FAILED'}  {text}")


def look(expr):
    got = h.say("Runtime.evaluate", expression=expr, returnByValue=True, awaitPromise=True)
    if "exceptionDetails" in got:
        sys.exit(f"the check could not read the page: {got['exceptionDetails']}")
    return got["result"].get("value")


def shoot(name):
    if shots:
        data = h.say("Page.captureScreenshot", format="jpeg", quality=85)["data"]
        with open(os.path.join(shots, name + ".jpg"), "wb") as f:
            f.write(base64.b64decode(data))


def place(js):
    """Brings what the expression finds into view and answers its middle, or None."""
    return look(f"""(() => {{ const e = {js}; if (!e) return null; e.scrollIntoView({{block: 'center'}});
      const b = e.getBoundingClientRect(); return [b.x + b.width / 2, b.y + b.height / 2]; }})()""")


def tap(js, touch):
    at = place(js)
    if at is None:
        return False
    x, y = at
    if touch:
        h.say("Input.dispatchTouchEvent", type="touchStart", touchPoints=[{"x": x, "y": y}])
        h.say("Input.dispatchTouchEvent", type="touchEnd", touchPoints=[])
    else:
        for kind in ("mousePressed", "mouseReleased"):
            h.say("Input.dispatchMouseEvent", type=kind, x=x, y=y, button="left", clickCount=1)
    time.sleep(.5)
    return True


def type_in(js, text, touch):
    tap(js, touch)
    h.say("Input.insertText", text=text)


def button(text):
    return f"[...document.querySelectorAll('button')].find(b => !b.closest('[hidden]') && b.textContent.trim() === {json.dumps(text)})"


def example(name):
    return f"[...document.querySelectorAll('.examples button')].find(b => b.querySelector('b')?.textContent === {json.dumps(name)})"


def holds(box):
    return look(f"document.getElementById({json.dumps(box)})?.querySelector('p')?.textContent || ''")


def fits():
    return look("(() => { const d = document.documentElement; return d.scrollWidth <= innerWidth && d.scrollHeight <= innerHeight; })()")


INSIDE = """(() => {
  const r = (e) => e.getBoundingClientRect();
  const parts = [document.querySelector('.cover h1 button'), document.querySelector('.cover .plate p'),
                 ...document.querySelectorAll('.cover .examples button'), document.querySelector('.cover footer')];
  return { all: parts.every(e => e && (b => b.left >= 0 && b.top >= 0 && b.right <= innerWidth + .5 && b.bottom <= innerHeight + .5)(r(e))),
           count: parts.length };
})()"""

if shots:
    os.makedirs(shots, exist_ok=True)
for name, w, hgt, dpr, touch in DEVICES:
    h.say("Emulation.setDeviceMetricsOverride", width=w, height=hgt, deviceScaleFactor=dpr, mobile=touch)
    h.say("Emulation.setTouchEmulationEnabled", **({"enabled": True, "maxTouchPoints": 5} if touch else {"enabled": False}))
    h.say("Emulation.setUserAgentOverride", userAgent=IPHONE if touch else "")
    h.say("Storage.clearDataForOrigin", origin=site.rstrip("/"), storageTypes="all")
    h.say("Page.navigate", url=site)
    time.sleep(1.5)
    shoot(f"{name}-1-cover")
    inside = look(INSIDE)
    claim(f"{name}: the cover shows in full: title, line, {len(examples)} examples and the purpose inside the window, nothing to scroll",
          inside["all"] and inside["count"] == 3 + len(examples) and fits())
    tall = hgt > w
    art = look("(() => { const s = getComputedStyle(document.querySelector('.cover')), b = document.querySelector('.cover').getBoundingClientRect();"
               " return { image: s.backgroundImage, size: s.backgroundSize, full: b.width === innerWidth && b.height === innerHeight }; })()")
    claim(f"{name}: the line art fills the whole window, drawn for a {'tall' if tall else 'wide'} window",
          art["full"] and art["size"].startswith("cover") and ("cover-tall.svg" if tall else "cover-wide.svg") in art["image"])
    small = look("[...document.querySelectorAll('.cover button')].filter(b => b.getBoundingClientRect().height < 44).length")
    claim(f"{name}: every button on the cover is at least 44 px tall", small == 0)
    # Mail: tap it, write a mail, send it, and the stub answers
    ok = tap(example("Mail"), touch)
    begun = ok and look("!document.querySelector('.made').hidden") and look("!!document.querySelector('input[name=subject]')")
    type_in("document.querySelector('input[name=subject]')", "hello", touch)
    type_in("document.querySelector('textarea[name=body]')", "from the cover", touch)
    if touch:
        small_fields = look("[...document.querySelectorAll('.made input, .made textarea')].filter(e => parseFloat(getComputedStyle(e).fontSize) < 16).length")
        claim(f"{name}: every text field is 16 px or more, so the iPhone does not zoom when one is touched", small_fields == 0)
    tap(button("send"), touch)
    sent = holds("email.wire.sent")
    shoot(f"{name}-2-mail")
    claim(f"{name}: touching Mail begins it: the page opens, a mail is written and sent", begun and sent == "holds 1 mail")
    claim(f"{name}: the page Mail makes fits the window's width", look("document.documentElement.scrollWidth <= innerWidth"))
    time.sleep(11)
    claim(f"{name}: the shipped stub answers the mail within ten seconds", holds("email.wire.inbox") == "holds 1 mail")
    # Notes: from a fresh cover, tap it, write a note
    h.say("Page.navigate", url=site)
    time.sleep(1.5)
    ok = tap(example("Notes"), touch)
    begun = ok and look("!document.querySelector('.made').hidden") and look("!!document.querySelector('input[name=title]')")
    type_in("document.querySelector('input[name=title]')", "first", touch)
    type_in("document.querySelector('textarea[name=text]')", "a note from the cover", touch)
    tap(button("write"), touch)
    claim(f"{name}: touching Notes begins it: the page opens, a note is written and the notebook holds it",
          begun and holds("notes.wire.notes") == "holds 1 note")
    shoot(f"{name}-3-notes")
    tap(button("Board"), touch)
    time.sleep(.5)
    claim(f"{name}: from the page, Board opens the board, and the whole board fits the window",
          look("!document.querySelector('main.board').hidden") and fits())
    shoot(f"{name}-4-board")
h.away()
sys.exit(0 if all(held) else 1)

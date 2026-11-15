# The Missing Layer

The site is one page. On load it shows a title and one line, centred, and nothing else. Behind that is a busy board for the browser, on one screen, with no scroll and no navigation.

## The way in

The board is built when the page loads and is not shown. There are two ways in:

- Touch the title.
- From a script or an extension: `board.enter()`. The board's buttons and fields are in the page and can also be operated through the DOM without going in.

`/explore` is the whole field of interaction on one page: every door, address, script call, store and verb, and the grammar, written out from `contract.json` by the generator. It is for reading; Go in opens the board.

The cover says only that a bot should explore, and the word explore links to `/explore`. `contract.json` describes everything and is not linked from the page.

## What is here

| File | What it is |
|---|---|
| `contract.json` | The whole board as data: every store, every verb, and each verb written as a list of steps. Also the grammar of a step, and the claims the board must prove. |
| `generator.js` | The one script. It takes shapes in as JSON and turns the ones it knows into running code in the tab. It knows the grammar of a step, how to draw a board, and how to keep one on floppies; it knows nothing about any store or verb. |
| `index.html`, `board.css` | The cover and the layout. |
| `serialize.html`, `deserialize.html`, `explore.html` | The same page at the addresses `/serialize`, `/deserialize` and `/explore`. |
| `proof.json` | How each claim in the contract is played and checked. |
| `instrument/` | The checker: it opens the page in a browser, plays it with real clicks and typing, and prints HELD or FAILED per claim. |

## The two doors

1. **Knobs.** Touch a store, touch a verb, type a Name and a Value, touch Do. Undo takes back the last thing done.
2. **Shape.** Type or paste JSON into Shape and touch Generate. A shape is a run (`{"store", "verb", "Name", "Value"}`), bare steps (`{"steps": [...]}`), a list of shapes, or a whole contract, which rebuilds the board.

Both doors hand their shape to the same place in the generator.

Everything that runs is listed under Ran as the shape it was, with the code it stood for underneath. Touch a line to put it back in Shape, or touch Hand back for all of it in order, then Generate. The result must be the same both ways.

## The matrix: JSONs loaded beside the board

The site ships JSONs of its own. Each can be loaded alone, first or last, and unloaded again.

| File | Id | What it brings |
|---|---|---|
| `email/wire.json` | `email.wire` | The wireframe of an email with an inbox and a sent box, and the two stores the mail is kept in. |
| `email/touch.json` | `email.touch` | The interaction: one layout at a time, compose opens, send sends, a row opens. |
| `email/stub.json` | `email.stub` | A stub on the other end: ten seconds after a mail is sent, it answers. |

The id is the address: the dot is the folder, so `email.wire` is `email/wire.json`, and `email.wire.inbox` is the thing called `inbox` in it.

- Through Shape: `{"load": "email.wire"}`, `{"unload": "email.wire"}`, or paste a JSON whole.
- From a script: `board.load(id or JSON)`, `board.unload(id)`, `board.loaded()`, `board.page()`.
- **Page** shows what the loaded JSONs make. **Board** comes back.

A JSON holds named things, each a list of steps, and may bring stores and parts. It carries no script. Nothing runs because a JSON was loaded: each time the loaded set changes, the generator draws the page again from all of it, in the order of the addresses. So any order of loading gives the same page and the same floppy.

Every thing gets its place on the page under its address. A thing that waits on something not loaded says what it waits for and does nothing. That part is left to the reader.

The email, step by step:

1. Load `email.wire` alone. Every layout is laid out, one after the other, with its id. Nothing happens on a touch.
2. Load `email.touch`. One layout shows at a time; Compose opens, Send sends, a row opens.
3. Load `email.stub`. Ten seconds after Send, an answer is in the inbox under the same subject.
4. Unload `email.stub`. Nothing answers. A reader outside the page (Claude's extension) answers through Shape: `{"store": "email.wire.inbox", "verb": "put", "Name": "<subject>", "Value": "<answer>"}`.
5. Save. The floppy carries the three JSONs and the mail. Load it in any browser and the email is back.

The grammar of a step grew by three, and the engine number is now 2:

- `{"touched": "<address>", "then": [...]}` waits for a touch on the thing at that address.
- `{"changed": "<store address>", "then": [...]}` waits for a store to hold something else. The generator looks after everything it runs itself; a write that does not come through it is not seen.
- `{"after": <milliseconds>, "then": [...]}` waits a time.

A reload forgets what was loaded. What the stores hold stays.

## Floppies: keeping the board and rebuilding it

What the board is and what its stores hold can be written out as plain JSON and read back.

- **Save** downloads it. **Load** takes the files back and rebuilds the board.
- Through Shape: `{"keep": true}` writes the floppies into Shape, and Generate takes them back.
- By address: `/serialize` downloads the floppies. `/deserialize` asks whether to download a copy first, then takes the files, rebuilds, and opens the board at `/`.
- From a script: `await board.serialize(size)` gives a list of JSON texts, one per floppy; `await board.deserialize(floppies)` takes them back, as text or parsed, one or many.

A floppy holds records and nothing else: the board, each store, each loaded JSON, each row a store holds, each element in the page as its kind, attributes and children. It never holds code. The generator rebuilds everything from the records, the same way it builds the board from `contract.json`.

A floppy has a size, 1,474,560 bytes unless one is given: `{"keep": {"size": 4000}}` or `board.serialize(4000)`. What does not fit on one goes on the next, numbered `disk` of `of`. No floppy is larger than its size; a record too large for one is cut across several. Floppies go back in any order, one at a time or together, and the board is rebuilt when the set is whole.

Keeping, rebuilding and keeping again gives the same bytes, any number of times, as long as the engine is the same. Each floppy carries the engine's number, and after every rebuild the generator keeps the board again and says whether it matches what was handed in. Change `ENGINE` in `generator.js` whenever the grammar of a step or the form of a record changes.

The contract says how each store is kept: its `keep` names the shape that empties it and the shape that puts one thing back. A store with no `keep` is not kept. History has none, because the browser does not hand over a tab's history. What an element holds only as live state, such as text typed into an input, is not in its attributes and is not kept.

Rebuilding wipes everything first. The site goes back to the board it shipped with, every kept store is emptied, and only then is it rebuilt from the floppies. Anything not on the floppies is gone, so Load asks before it opens the files (the second touch opens them), and `/deserialize` offers a copy first. `board.deserialize` does not ask.

## What cannot get in

No text is run as code. The page carries a policy that makes the browser refuse inline script and evaluated text, and the generator refuses any step it does not know, and any step that writes markup.

## Changing the board

Change `contract.json`. A knob exists because the contract names it; a verb does what its steps say. The generator changes only when the grammar of a step has to grow.

## Steps

Nobody has to run anything to use the site.

1. **neonix** — merge the pull request. Cloudflare Pages publishes it.

2. **Any seat with Python 3 and Chromium**, to check the board, from the repository root:

```sh
chromium --headless=new --remote-debugging-port=9222 "data:text/plain,seed" &
python3 -m http.server 8000 &
cd instrument && python3 observe.py http://127.0.0.1:8000/
```

Every claim must print HELD. Chrome works in place of Chromium; `BROWSER=<port>` names another debugging port.

3. **claude.extn**, to demonstrate: open the site, read `contract.json`, operate the knobs, then hand the lines under Ran back through Shape.

## What was here before

Earlier pages (the candidates, the menu window, `/build/`, `/clay/`, `/second/`, the placing instrument and its guide) were deleted. Git history has them.

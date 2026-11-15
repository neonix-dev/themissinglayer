# Ashwamedh exhibition

Root `index.html` is the board: a busy board for the browser, on one screen, with no scroll and no navigation. The menu window that used to be the root page is at `window/`. The earlier card selector is kept as `selector.html`.

Building a page here? Read `GUIDE.md` first.

## The board

`contract.json` names every store this tab has (the page itself, localStorage, sessionStorage, IndexedDB, cookies, the cache, history) and every verb each one takes. `board.js` reads that file and turns each entry into a knob: pick a store, pick a verb, type a Name and a Value, touch Do. The line under the buttons says what happened, the box under it shows what the store holds, and Undo takes back the last thing done.

- The board is built from the contract. To add or change a knob, change `contract.json` first.
- Nothing goes out. The page carries a policy that makes the browser refuse every address but this site's own, and the board itself only reads `contract.json`.
- `proof.json` plays each line under `proves` with real clicks and typing.

Nobody has to run anything to use it. To check it:

1. Any seat with Python 3 and Chromium, from the repository root:

```sh
chromium --headless=new --remote-debugging-port=9222 "data:text/plain,seed" &
python3 -m http.server 8000 &
cd instrument && python3 observe.py http://127.0.0.1:8000/
```

Every claim must print HELD.

## The instrument

Pages other than the board are not written by anyone. Three plain files say everything, and the instrument knows nothing about any of them:

- a `contract.json` states the intent and the behaviour the page must show;
- a base, such as `instrument/window.json`, says which native browser piece each word in the contract becomes;
- a `proof.json` says how each line under `proves` is played and checked.

`instrument/place.py` reads a contract and a base and places each piece in a running browser using the browser's own DOM verbs (copy a node, rename it, set an attribute, set a text value), then asks the engine to write out the document it holds. No markup, stylesheet or script is sent to the browser, and a placed page contains no style or script.

`instrument/observe.py` opens the served page, plays it with real input events, and prints HELD or FAILED for every claim. A claim with no proof fails.

The instrument needs only Python's standard library and a Chromium browser. With the browser and server above running:

```sh
python3 place.py ../window/contract.json window.json ../window/index.html
python3 observe.py http://127.0.0.1:8000/window/ ../window/contract.json ../window/proof.json
```

To change the menu window, change `window/contract.json` and run both again. Do not edit a placed `index.html` by hand.

## Another page from the same instrument

`second/` is a different page, placed and checked by the same two programs with nothing changed in them: its own contract, its own base (`sheet.json`) and its own proof.

```sh
python3 place.py ../second/contract.json ../second/sheet.json ../second/index.html
python3 observe.py http://127.0.0.1:8000/second/ ../second/contract.json ../second/proof.json
```

A base is a list of pieces. A piece is `[element, {attributes}, children...]`; text in braces is filled from the contract (`{item:slug}` makes it safe for an id). `["each", "menus"]` places every entry of that list using the first entry under `words` that matches it, and `["later", piece]` places a piece at the end of the page.

## Candidates

Place each complete static website into its designated directory, with an `index.html` at the directory root:

- `candidates/claude-code/`
- `candidates/chatgpt/`
- `candidates/muse/`
- `candidates/claude-chat/`

Keep each candidate's assets alongside its entrypoint and ensure relative asset URLs work under its own subpath. For bundled applications, use a subpath-aware build or relative base path.

Run `python3 -m http.server 8000` at the repository root to test. GitHub Pages must be separately enabled in repository Settings > Pages, using `main` and `/(root)` for deployment.

`selector.html` checks for each candidate's `index.html` and enables the corresponding card when it is available. Empty folders are not tracked by Git, so they will appear only when candidates are committed.

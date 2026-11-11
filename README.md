# Ashwamedh exhibition

Root `index.html` is an application-style menu bar that opens four independent websites. The earlier card selector is kept as `selector.html`.

## How the root page is made

Nobody writes the root page. `contract.json` states the intent: the menus, their items, and the behaviour the page must show. `instrument/place.py` reads it and places each piece in a running browser using the browser's own DOM verbs (copy a node, rename it, set an attribute, set a text value), then asks the engine to write out the document it holds. No markup, stylesheet or script is sent to the browser, and the page contains no style or script.

`instrument/observe.py` opens the served page, plays it with real input events, and checks every line under `proves` in the contract.

```sh
chromium --headless=new --remote-debugging-port=9222 "data:text/plain,seed" &
python3 -m http.server 8000 &
cd instrument
pip install websocket-client
python3 place.py                            # rewrites ../index.html from ../contract.json
python3 observe.py http://127.0.0.1:8000/   # checks the claims
```

To change the root page, change `contract.json` and run both again. Do not edit `index.html` by hand.

## Candidates

Place each complete static website into its designated directory, with an `index.html` at the directory root:

- `candidates/claude-code/`
- `candidates/chatgpt/`
- `candidates/muse/`
- `candidates/claude-chat/`

Keep each candidate's assets alongside its entrypoint and ensure relative asset URLs work under its own subpath. For bundled applications, use a subpath-aware build or relative base path.

Run `python3 -m http.server 8000` at the repository root to test. GitHub Pages must be separately enabled in repository Settings > Pages, using `main` and `/(root)` for deployment.

The index checks for each candidate's `index.html` and enables the corresponding card when it is available. Empty folders are not tracked by Git, so they will appear only when candidates are committed.

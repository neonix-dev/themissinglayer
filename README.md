# The Missing Layer

The site is one page: a busy board for the browser, on one screen, with no scroll and no navigation.

## What is here

| File | What it is |
|---|---|
| `contract.json` | The whole board as data: every store, every verb, and each verb written as a list of steps. Also the grammar of a step, and the claims the board must prove. |
| `generator.js` | The one script. It takes shapes in as JSON and turns the ones it knows into running code in the tab. It knows the grammar of a step and how to draw a board; it knows nothing about any store or verb. |
| `index.html`, `board.css` | The empty page and its layout. |
| `proof.json` | How each claim in the contract is played and checked. |
| `instrument/` | The checker: it opens the page in a browser, plays it with real clicks and typing, and prints HELD or FAILED per claim. |

## The two doors

1. **Knobs.** Touch a store, touch a verb, type a Name and a Value, touch Do. Undo takes back the last thing done.
2. **Shape.** Type or paste JSON into Shape and touch Generate. A shape is a run (`{"store", "verb", "Name", "Value"}`), bare steps (`{"steps": [...]}`), a list of shapes, or a whole contract, which rebuilds the board.

Both doors hand their shape to the same place in the generator.

Everything that runs is listed under Ran as the shape it was, with the code it stood for underneath. Touch a line to put it back in Shape, or touch Hand back for all of it in order, then Generate. The result must be the same both ways.

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

Every claim must print HELD.

3. **claude.extn**, to demonstrate: open the site, read `contract.json`, operate the knobs, then hand the lines under Ran back through Shape.

## What was here before

Earlier pages (the candidates, the menu window, `/build/`, `/clay/`, `/second/`, the placing instrument and its guide) were deleted. Git history has them.

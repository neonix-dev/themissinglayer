# Guide for a party building a page here

This is for any AI or person who can touch this repository. You do not write a page. You state what it should be, and the browser writes it.

## The rule

- Touch, never inject. No markup, stylesheet or script is handed to the browser, and none appears in the page.
- The only moves are the browser's own: copy a node, rename it, set an attribute, set a text value; then real clicks, keys and typing to check it.
- The page on disk is whatever the browser's engine wrote out. Never edit an `index.html` by hand.

## What you write

Make a folder for your page and put three plain files in it. `second/` is a complete small example; the root page is a larger one.

| File | Says | Example |
|---|---|---|
| `contract.json` | What is wanted, in your own words, and a `proves` list of behaviours the page must show | `second/contract.json` |
| a base, such as `sheet.json` | Which native browser piece each word in the contract becomes | `second/sheet.json`, `instrument/window.json` |
| `proof.json` | For each line under `proves`, the moves that play and check it | `second/proof.json` |

### The base

A base has `html` (attributes for the page), `head`, `body` and `words`.

- A piece is `[element, {attributes}, children...]`. A child is a string of text or another piece.
- `{name}` in any text or attribute is filled from the contract. `{name:slug}` makes it safe to use as an id.
- `["each", "list"]` places every entry of that contract list. Each entry is placed with the first form under `words` whose word the entry has.
- A word like `items.accepts` matches an entry whose `items` list has any member with `accepts`.
- `["later", piece]` places the piece at the end of the page instead of here.

Use native elements that already behave: `details` with a shared `name` for things that open one at a time, `popover` and `popovertarget` for things that appear, a `form` with `input type="reset"` to clear, `a` to go somewhere.

### The proof

Each claim starts from a fresh load of the page. A claim with no moves, or with nothing checked, fails.

| Move | Does |
|---|---|
| `["touch", name]` | Clicks the thing called `name` (its text, its label, or its button value) |
| `["type", text]` | Types into whatever has focus |
| `["open", name]` / `["closed", name]` | Checks the fold with that summary is open or closed |
| `["at", path]` | Checks the browser is now at that path, relative to the page |
| `["exists", name]` | Checks that link is visible and its target loads |
| `["holds", name, text]` | Checks the text field with that label holds exactly `text` |
| `["shows", text]` / `["hides", text]` | Checks the text is, or is not, presented to the visitor |

A value starting with `@` is read from the contract: `@menus.3.items.0.shows`.

## Place it and check it

You need Python 3 and a Chromium browser. Nothing else is installed.

```sh
chromium --headless=new --remote-debugging-port=9222 "data:text/plain,seed" &
python3 -m http.server 8000 &
cd instrument
python3 place.py ../yours/contract.json ../yours/sheet.json ../yours/index.html
python3 observe.py http://127.0.0.1:8000/yours/ ../yours/contract.json ../yours/proof.json
```

Every claim must print HELD. Report any that print FAILED as failed; do not reword the claim to make it pass.

## If you cannot run a browser

Write the three files and stop there. Say plainly that the page has not been placed or checked, and leave `index.html` for a party who can run the instrument. Do not write the page by hand.

## Boundaries

- Work in your own folder. Do not change another party's folder, the root contract, or `instrument/` without the owner's say.
- Open a pull request; do not merge it.
- If the instrument cannot express what you need, say what is missing instead of working around the rule.

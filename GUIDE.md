# Guide for a party building a page here

This is for any AI or person who can touch this site. You do not write a page. You state what it should be, and the browser writes it.

**If all you have is a browser that clicks and types,** read "The base" below for the format, then go straight to "Building from inside the site". You need no files, no proof and no repository.

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
- `words` is a list of pairs, `[word, piece]`. A word is the name of a key.
- `["each", "list"]` places every entry of that contract list. Each entry is placed with the piece of the first pair whose word is a key the entry has.
- Fill-ins work anywhere in a text or an attribute value, alone or inside a longer line: `"Recent: {expense}"`, `{"color": "{tone}"}`.
- To make entries differ, put the difference in the data and fill an attribute from it. A friend entry `{"friend": "Ben", "owes": "you owe $15", "tone": "red"}` with the piece `["li", "{friend} ", ["font", {"color": "{tone}"}, "{owes}"]]` shows each amount in its own colour, and every new entry has a `tone` to set.
- A word like `items.accepts` matches an entry whose `items` list has any member with `accepts`.
- `["later", piece]` places the piece at the end of the page instead of here.

Use native elements that already behave:

- **Open one at a time:** `["details", {"name": "groups"}, ["summary", "{group}"], ...]`. Folds sharing a `name` close each other.
- **Appear without leaving the page:** a button `["button", {"type": "button", "popovertarget": "new"}, "Add"]` and, anywhere on the page, `["div", {"id": "new", "popover": "auto"}, ...]`. The `id` and the `popovertarget` must match. `later` is only needed when the piece is placed from inside a list.
- **Clear what was typed:** fields inside a `form`, with `["input", {"type": "reset", "value": "Clear"}]`.
- **Go somewhere:** `["a", {"href": "..."}, "..."]`.
- **Colour and layout:** `font` takes `color`; `table`, `td` and `body`-level blocks take `bgcolor`, `align` and `width`.

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

A thing's name is all the text it holds, read as one line, however the text is split into pieces inside it. So one part of a row can carry its own colour or weight and the row keeps its name: a summary holding `Asha ` and a coloured `owes you $20` is called `Asha owes you $20`.

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

The same check runs against the public site once the page is there: `python3 observe.py https://themissinglayer.org/yours/ ...`. A page is on the site only when it has been merged; until then the address shows the root page instead, and `exists` reports such a destination as missing.

## Building from inside the site

If all you have is a browser that clicks and types, use `/build/` on the site. It ships the site's own engine, which receives a page as data and builds it in front of you. Nothing is installed and nothing is sent anywhere.

1. Open `https://themissinglayer.org/build/` and touch **Build**.
2. To change what is there, edit any field; replace its text as you would in any text field. Fields are named by where they sit in the data: `title`, `friends 2 owes`. To grow or shrink a list, touch **Add to friends** or **Remove friends 2**. A new entry has the same fields as the first entry of its list, empty. The page is built again at once.
3. To bring your own page, touch **Give it a whole page**, then **Empty the box**, type your page as JSON into **Page as data**, and touch **Build from this**.
4. Read the line that starts `Built`, just above the page. It lists anything the engine refused. The box now shows your page as the engine holds it, laid out one value per line.
5. **Link to this page** is an address that carries the whole page. Give that address to someone and the page builds for them on the site. **Save as a file** gives the same data as a file. **Start from** loads a ready page to change: an empty sheet, the site's root page, or the four paths.

A page is one JSON object: `{"contract": {...}, "base": {...}}`. The contract and the base are exactly the ones described above. This is a complete page:

```json
{"contract": {"title": "Groups", "groups": [{"group": "Flat", "owed": "you are owed $40"}]},
 "base": {"head": [["title", "{title}"]],
          "body": [["h1", "{title}"], ["menu", ["each", "groups"]]],
          "words": [["group", ["li", "{group}: ", ["b", "{owed}"]]]]}}
```

Data is never run. The engine refuses `script`, `style`, frames, embedded objects, any attribute starting with `on`, the `style` attribute, and any address that leaves the site (a plain link in an `a` may point elsewhere). For looks, use the native attributes listed under "The base".

### Shaping what is built

What is built is clay. Every piece has a name: the `id` it came with, or one the engine gives it, such as `h1-1` or `li-3`.

1. Touch **Shape**, then **Show names**. Each name appears at the right-hand end of its piece. **All pieces** lists them as an outline.
2. Pick a piece by touching its name, or by typing the name into **Piece**. `page` means the whole page.
3. Reshape it:

| Control | Does |
|---|---|
| **Move up**, **Move down** | Moves the piece among its neighbours |
| **Put before other**, **Put after other**, **Put inside other** | Moves the piece next to or into the piece named in **Other piece** |
| **Set text** | Replaces the piece's own words with what is in **Text** |
| **Set attribute** | Sets **Attribute** to **Value** on the piece; an empty value takes the attribute away |
| **Add inside** | Adds a new piece of the kind in **New piece** (`p`, `li`, `details` …) inside it, holding the words in **Text** |
| **Copy**, **Remove** | Copies the piece after itself, or takes it away |

The same refusals apply: no `script`, no handlers, no `style`, nothing from another site. The status line says what was done or refused.

After the first reshaping the engine writes the page down as it stands, piece by piece, with every name in it. From then on the page is changed under **Shape**, not through fields, and its link carries the shaped page.

A page built this way lives in its link and in your own browser. It becomes a published page of the site only when its data is placed and merged as described above; a page opened from a link says so.

## If you cannot run a browser

Build the page at `/build/` if you can reach the site, and hand over its link. Otherwise write the three files and stop there. Say plainly that the page has not been placed or checked, and leave `index.html` for a party who can run the instrument. Do not write the page by hand.

## Boundaries

- Work in your own folder. Do not change another party's folder, the root contract, or `instrument/` without the owner's say.
- Open a pull request; do not merge it.
- If the instrument cannot express what you need, say what is missing instead of working around the rule.

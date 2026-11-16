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
| `email/*.json` | Sheets: JSONs that say what exists and what moves, and name no device. |
| `generator.py` | The generator for a terminal. It takes the same sheets and the same floppies. |
| `serialize.html`, `deserialize.html`, `explore.html` | The same page at the addresses `/serialize`, `/deserialize` and `/explore`. |
| `proof.json` | How each claim in the contract is played and checked. |
| `instrument/` | The checker: it opens the page in a browser, plays it with real clicks and typing, and prints HELD or FAILED per claim. |

## The two doors

1. **Knobs.** Touch a store, touch a verb, type a Name and a Value, touch Do. Undo takes back the last thing done.
2. **Shape.** Type or paste JSON into Shape and touch Generate. A shape is a run (`{"store", "verb", "Name", "Value"}`), bare steps (`{"steps": [...]}`), a list of shapes, or a whole contract, which rebuilds the board.

Both doors hand their shape to the same place in the generator.

Everything that runs is listed under Ran as the shape it was, with the code it stood for underneath. Touch a line to put it back in Shape, or touch Hand back for all of it in order, then Generate. The result must be the same both ways.

## Sheets: JSONs that name no device

The site ships JSONs of its own, called sheets. A sheet says what exists and what moves. It never says screen, key, button, layout or where anything is kept, so the same file works on any device that has a generator. Each can be loaded alone, first or last, and unloaded again.

| File | Id | What it says |
|---|---|---|
| `email/wire.json` | `email.wire` | What exists: a mail has a subject and a body; an inbox and a sent box hold mails. |
| `email/touch.json` | `email.touch` | What whoever is at the device can do: send, read, look. |
| `email/stub.json` | `email.stub` | A stub on the other end: ten seconds after a mail arrives in sent, it answers. |

The three files are 961 bytes together. This is all of `email.touch`:

```json
{ "send": { "to": "email.wire.sent" },
  "read": { "from": "email.wire.inbox" },
  "look": { "from": "email.wire.sent" } }
```

### Everything a sheet can say

- **`id`**: two levels, like `email.wire`. Everything in the sheet has the address `id.name`, three levels. The dot is the folder: `email.wire` is `email/wire.json`.
- **`kinds`**: a name and its parts. `"mail": ["subject", "body"]`.
- **`boxes`**: a name and the kind it holds. `"inbox": "mail"`.
- **`moves`**: a name and one thing going from somewhere to somewhere, said with five words:
  - `from`: the box it is picked from. Left out, whoever is at the device makes it.
  - `to`: the box it is put in. Left out, whoever is at the device is shown it.
  - `when`: a box. The move then happens by itself for each thing that arrives there.
  - `after`: a wait in seconds.
  - `with`: parts of the thing and the words they get.

A sheet that says anything else is refused. Nothing happens because a sheet was loaded: each time the loaded set changes, the generator makes its page again from all of it, in the order of the addresses. So any order of loading gives the same page and the same floppy. A move that needs something not loaded says what it waits for and does nothing.

A thing stays where it came from, so a sheet cannot yet say "take this out of the box".

### Two generators, one set of files

| Generator | Runs on | A move from whoever is here | A move from a box | Where a box is kept |
|---|---|---|---|---|
| `generator.js` | a browser | fields and a button | the box's rows can be touched | a database in the browser |
| `generator.py` | a terminal, Python 3 only | pick its number, type the parts | pick its number, then the row's number | one file, `~/.missinglayer/boxes.json` |

In the browser:

- Through Shape: `{"load": "email.wire"}`, `{"unload": "email.wire"}`, or paste a sheet whole.
- A move through Shape: `{"do": "email.touch.send", "with": {"subject": "hi", "body": "there"}}` or `{"do": "email.touch.read", "pick": 1}`.
- A move handed in whole goes once: `{"from": "email.wire.sent"}` answers what the box holds; `{"to": "email.wire.inbox", "with": {...}}` puts a thing in.
- From a script: `board.load(id or sheet)`, `board.unload(id)`, `board.loaded()`, `board.do(move)`, `board.page()`.
- **Page** shows what the loaded sheets make. **Board** comes back.

In a terminal, `python3 generator.py` prints the same things under the same addresses and a numbered list of what can be done. A line that starts with `{` is a shape, the same shapes as above. With the repository beside it, it reads the sheets from there; alone, it fetches them from the site.

The email, step by step, on either:

1. Load `email.wire` alone. What exists is shown, each under its address. Nothing can be done.
2. Load `email.touch`. A mail can be sent, and the rows of both boxes open.
3. Load `email.stub`. Ten seconds after a mail is sent, an answer is in the inbox under the same subject.
4. Unload `email.stub`. Nothing answers. A reader outside (Claude's extension) reads with `{"from": "email.wire.sent"}` and answers with `{"to": "email.wire.inbox", "with": {"subject": "...", "body": "..."}}`.
5. Save. The floppy carries the sheets and the mail. It rebuilds in the other generator, and written back from there it is the same bytes.

What is loaded and what the boxes hold are both kept in the browser. A reload opens with them.

### Three more words: `look`, `here`, `on`

- **`look`** says how the page looks, in seven words and no others: `paper`, `ink`, `accent` (colours as six digits), `face` (sans, serif, mono), `size`, `space`, `corner`. Each device reads them its own way. A look cannot hide a thing, move it, or put words in the page. `email.look` is one; load it and only the look changes.
- **`here`** lists boxes that one sitting holds alone: in a browser this tab, in a terminal this run. `email.draft` keeps drafts that way. A floppy does not carry them.
- **`on`** names the devices a JSON is for (`browser`, `terminal`, `pi5`, `pi0`). A device that is not named keeps it loaded, says so, and takes nothing from it.

Load in any order; the generator always reads what exists first, then what moves, then how it looks, each by address.

### Tabs

Every tab of the site in one browser is the same layer: the loaded JSONs and the common boxes are shared, and a change in one tab shows in the others at once. Each tab alone has its `here` boxes. So a person in one tab and readers in other tabs of the same browser work on one email; `board.wait(box)` tells a reader when a thing arrives. Tabs in different browsers share nothing but the shipped files.

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

No text is run as code. The page carries a policy that makes the browser refuse inline script and evaluated text, and the generator refuses any step it does not know and a short list of calls that write markup. That list is not complete: a board handed in on a floppy can still make elements and set their attributes, so load only floppies you trust. The site's headers stop the page loading or sending anything outside this site.

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

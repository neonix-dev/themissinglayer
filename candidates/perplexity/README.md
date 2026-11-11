# Zen Garden — Perplexity candidate

A self-contained, dependency-free static browser experience. No build step, CDN, analytics, account, or remote backend. All assets are relative to this folder. The repository root selector and other candidates are intentionally unchanged; the current selector does not automatically add this fifth candidate.

## Approach (one-page brief)

Start with “What is it for?” rather than a file or application. Give purpose an address before requiring an artifact. The entrance is a short invitation and Explore; the possibilities emerge through use rather than an exhaustive catalogue.

The missing layer is the separation between a browser runtime and the experiences it interprets. People manipulate places and their behavior, not source code. This candidate implements that contract with maps, observations, and repetition counters. Any place can contain another map. Only three levels appear at once: the current center, its children, and their children. Opening a place establishes a fresh local context. Numeric addresses belong to that context, while persistent node IDs identify places across navigation.

Creating a nested experience adds data to the same executable environment, rather than generating another hard-coded application. A saved garden contains the complete rooted tree, behavior types, text, repetition state, current focus, and ID sequence. JSON export and single-file import reconstruct that supported behavior using the existing runtime. It is not a snapshot of arbitrary browser execution, and it does not implement a general programming language or arbitrary website generator.

Human controls and the bot API use the same immutable action reducer. `window.zenGarden.inspect()` returns a detached snapshot and the visible local addresses. `window.zenGarden.dispatch(action)` validates and performs the same supported actions as the UI. Examples: `{type:'focus',id:'build'}`, `{type:'add',title:'My practice',kind:'counter'}`, `{type:'repeat',id:'practice'}`. Supported actions are focus, add, edit, repeat, and remove. Create children under a specified `id`, or under the current focus by default. Dispatch errors throw without modifying the previous state.

Imported files are data, not executable code. The runtime accepts map, note, and counter behavior only; imported strings are rendered as text. Validation checks version, field types, references, rooted-tree integrity, cycles, counts, and limits. Imports are capped at 2 MB, gardens at 2,000 places and 100 edges of depth; titles at 160 characters and body text at 20,000. These are implementation bounds, not conceptual limits of the approach.

The first delivery proves: enter, establish a map, interact, create a nested experience, export, reload, continue. Local persistence is best effort: unavailable or full browser storage produces a visible warning and export remains available. Loading replaces the local garden only after validation and user confirmation. Removing a place requires confirmation and removes its subtree. Separate tabs are not synchronized; the most recent save wins.

## Run

From the repository root:

```sh
python3 -m http.server 8000
```

Open `http://localhost:8000/candidates/perplexity/`. Use HTTP rather than opening the HTML as a file because JavaScript modules require a server. No deployment settings are changed by this candidate.

## Tests

Runtime tests (Node.js with the built-in test runner):

```sh
node --test candidates/perplexity/runtime.test.mjs
node --check candidates/perplexity/app.mjs
node --check candidates/perplexity/runtime.mjs
```

Browser integration tests (Python with Playwright and its Chromium browser installed), while the static server above runs:

```sh
python3 candidates/perplexity/browser_test.py
```

The test uses an isolated browser context and verifies entrance, nested creation, repetition, inert HTML, JSON export, browser reload persistence, JSON import restoration, rejected-import rollback, 390px layout overflow, numeric navigation, subtree removal and absence of page errors. Runtime tests cover round-trip fidelity, local depth/address rules, immutability, deletion, malformed imports, unsupported actions, ID collision handling, and HTML-as-data.

## Verification performed before commit

- Eight Node runtime tests passed; zero failures.
- Both JavaScript modules passed Node syntax checks.
- Headless Chromium integration passed at a nested URL, including the 390 × 844 mobile viewport check; zero page errors.
- No claim of Safari/Firefox, assistive-technology, or exhaustive accessibility testing. No external dependencies are loaded by the application.

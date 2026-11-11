# The Missing Layer

> The model is stateless by design. You are not. Continuity is your problem to solve.

A reconstruction of themissinglayer.org from the author's own documents (Rajan Thakurdesai):

- **Read** — the thesis, Modes of Practice, the note for platform engineers, and the self-evaluation.
- **Fit** — the self-evaluation as an interactive diagnostic.
- **Build** — write the eight categories that must cross the session boundary; get a `CLAUDE.md` with reflection and disclosure built in; seal versions; keep score of predictions against outcomes.
- **Sources** — what is the author's text, what was built from it, and what was named but not found.

Static files only: `index.html`, `style.css`, `content.js` (generated from the author's documents), `app.js`, `sw.js`. No build step to run, no dependencies, no network calls. Visitor data stays in `localStorage`.

```sh
python3 -m http.server 8300
```

`round1/` holds this candidate's first-round site (a practice bench), kept for comparison.

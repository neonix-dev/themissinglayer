# Ashwamedh exhibition

Root `index.html` is a selector for four independent websites.

Place each complete static website into its designated directory, with an `index.html` at the directory root:

- `candidates/claude-code/`
- `candidates/chatgpt/`
- `candidates/muse/`
- `candidates/claude-chat/`

Do not overwrite the root index. Keep each candidate's assets alongside its entrypoint and ensure relative asset URLs work under its own subpath. For bundled applications, use a subpath-aware build or relative base path.

Run `python3 -m http.server 8000` at the repository root to test. GitHub Pages must be separately enabled in repository Settings > Pages, using `main` and `/(root)` for deployment.

The index checks for each candidate's `index.html` and enables the corresponding card when it is available. Empty folders are not tracked by Git, so they will appear only when candidates are committed.

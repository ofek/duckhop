# Repository instructions

- DuckHop targets DuckDB 2.x only. The current baseline is a pre-release revision.
- DuckDB and extension-ci-tools are pinned submodules. Update them deliberately with compatibility evidence; do not edit their contents or advance them incidentally.
- Use `mise run ...` tasks for contributor workflows. Keep tooling versions and lockfiles synchronized.
- Run `mise run check` for deterministic, offline checks and `mise run verify` before finalizing substantial changes. Report any checks that could not run.
- Prefer sqllogictest for SQL-facing behavior. The bootstrap extension exposes no public graph API.
- Edit site documentation under `docs/`; never edit generated `site/` output or `gh-pages` manually.
- Keep tutorials, how-to guides, reference, and explanations separate according to Diátaxis.
- Do not weaken lint or static-analysis rules to silence findings. Use a narrow suppression with a concrete explanation when one is justified.
- Write comments, docstrings, and configuration annotations as complete, concise sentences that add information beyond the surrounding code.
- Never hard-wrap Markdown; keep each paragraph or bullet on one line.
- Follow the pull request template. Describe changed behavior in flowing prose, and use backticks only for commands, flags, filenames, and configuration keys.

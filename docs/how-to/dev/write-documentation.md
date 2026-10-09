# Write documentation

Edit source pages under `docs/` and add new pages to the explicit navigation in `zensical.toml`. Use lowercase kebab-case filenames, relative Markdown links, and one line per paragraph or bullet.

## Choose a page type

Use the [Diátaxis](https://diataxis.fr/) category that matches the reader's need:

| Category | Reader's need | Content |
| --- | --- | --- |
| Tutorials | Learn by completing an exercise. | A guided sequence with a clear starting point and observable result. |
| How-to guides | Complete a specific task. | Steps and relevant choices for a contributor with a prepared environment. |
| Reference | Look up exact information. | Commands, prerequisites, configuration, and repository conventions. |
| Explanation | Understand context. | Responsibilities, tradeoffs, and the reasons behind decisions. |

Add a page only when it answers a concrete reader need; the site does not need a page in every category. Split content when it serves different needs. Distinguish planned graph functionality from the extension's current behavior.

## Preview and validate

Start the local preview:

```text
mise run docs:serve
```

Open the local address printed by the task and check the changed pages, navigation, tables, and links. Stop the preview with ++ctrl+c++.

Format and validate the source:

```text
mise run fmt
mise run docs:check
mise run check
```

`docs:check` performs strict documentation validation. `check` also checks Markdown, terminology, and local links. Use `mise run docs:build` to produce a site for inspection; the generated `site/` directory is ignored and must not be committed.

The prose gate uses Vale for canonical capitalization and the native Harper CLI for grammar, spelling, and style. `mise install --locked` installs both tools; prose checks run offline and exclude personal Harper dictionaries. Both tools use `.config/prose/config/vocabularies/DuckHop/accept.txt`. Add canonical names as literal words or phrases; prefix an entry with `(?i)` when any capitalization is valid. The prose check reads the vocabulary location from `.vale.ini` and derives Harper's dictionary from these entries, so there is no second list to maintain. The prose gate preserves sentence-case headings and excludes Control-key abbreviation advice inside complete keyboard shortcuts such as `++ctrl+c++`. Run `mise run check:prose` to see findings, which must be reviewed before the gate can pass.

The [task reference](../../reference/dev/tasks.md) is generated from the descriptions in `mise.toml`. After changing task metadata, run `mise run docs:tasks`; `mise run check:tasks` checks that the committed reference is current. Edit the metadata rather than the generated table.

CI publishes documentation changes from the main branch. Edit the source pages under `docs/`; do not edit the generated `gh-pages` branch.

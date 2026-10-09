# Repository layout

| Path | Purpose |
| --- | --- |
| `src/` | DuckHop's C++ extension implementation and headers. |
| `test/sql/` | `sqllogictest` files for observable SQL behavior and extension loading. |
| `duckdb/` | The exact DuckDB 2.x source submodule used for builds. |
| `extension-ci-tools/` | Pinned upstream extension build and distribution tooling. |
| `CMakeLists.txt`, `extension_config.cmake`, `Makefile` | Conventional DuckDB extension build integration. |
| `mise.toml`, `mise.lock` | Contributor tasks and locked tool installations. |
| `pyproject.toml`, `uv.lock` | Locked non-package Python tooling environment. |
| `scripts/` | Python tooling and tests behind the mise tasks. |
| `docs/`, `zensical.toml` | Diátaxis documentation sources and explicit site navigation. |
| `ast-grep/` | Structural rules and their positive and negative fixtures. |
| `.github/` | Workflows, contribution templates, and maintainer setup notes. |

Generated build output, `site/`, virtual environments, and tool caches are ignored. `gh-pages` contains only generated site output, including `.nojekyll`; it is never a documentation source branch.

## Naming and formatting

Use snake_case for C++ source, headers, and SQL test filenames. Use kebab-case for documentation and workflow filenames. Conventional root filenames keep their standard spelling.

C++ formatting follows the pinned DuckDB style. EditorConfig supplies UTF-8, LF, final newlines, and indentation defaults without replacing formatters. Markdown paragraphs and bullets stay on single lines. Explanatory comments and docstrings use complete, concise sentences and add context beyond the code.

## Build and dependency changes

The root Makefile remains compatible with upstream extension tooling; contributors use mise tasks. Keep DuckHop-owned checks scoped to project sources and do not reformat submodules. Change dependency pins deliberately and verify the affected platforms.

The bootstrap adds no external C/C++ library dependencies. The extension uses the MIT License.

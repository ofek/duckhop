# Task reference

<!-- This page is generated from mise.toml by scripts/task_docs.py. -->

This page is generated from the task descriptions in `mise.toml`. Run `mise run docs:tasks` after changing task metadata; `mise run check:tasks` detects stale output without modifying files.

Run these commands from the repository root after installing the locked tools and running setup. Publishing helpers are reserved for CI and are omitted from this contributor reference.

| Command | Behavior |
| --- | --- |
| `mise run build` | Build DuckDB and DuckHop with debug symbols. |
| `mise run build:debug` | Build the debug CLI, test runner, and loadable extension. |
| `mise run build:release` | Build the optimized CLI, test runner, and loadable extension. |
| `mise run check` | Run read-only, offline checks without building DuckDB. |
| `mise run check:actions` | Validate workflow syntax and audit workflow security offline. |
| `mise run check:ast` | Test and enforce structural C++ rules and suppression hygiene. |
| `mise run check:cpp` | Analyze project C++ using the existing debug compilation database. |
| `mise run check:docs` | Validate the documentation with a strict temporary build. |
| `mise run check:files` | Validate source, documentation, and workflow file names. |
| `mise run check:format` | Check formatting without changing source files. |
| `mise run check:links:external` | Validate external links over the network. |
| `mise run check:links:local` | Validate local links and fragments without network access. |
| `mise run check:markdown` | Check Markdown formatting and structure. |
| `mise run check:prose` | Check prose against terminology and grammar rules. |
| `mise run check:tasks` | Check that the generated task reference matches mise metadata. |
| `mise run check:toml` | Check TOML formatting and lint TOML offline. |
| `mise run ci` | Run comprehensive verification on the current platform. |
| `mise run clean` | Remove generated build and documentation output. |
| `mise run docs:build` | Build strict documentation into site/. |
| `mise run docs:check` | Check documentation prose, links, formatting, and a strict build. |
| `mise run docs:serve` | Preview the documentation with live reload. |
| `mise run docs:tasks` | Generate the contributor task reference from mise metadata. |
| `mise run doctor` | Validate installed tools, submodules, and the native compiler. |
| `mise run fix` | Apply the project's deterministic formatters. |
| `mise run fmt` | Format project C++, CMake, TOML, and Markdown files. |
| `mise run release:check` | Validate release tag and revision prerequisites without publishing. |
| `mise run setup` | Initialize pinned submodules and synchronize locked Python tooling. |
| `mise run test` | Run debug SQL smoke tests and verify release asset loading. |
| `mise run test:release` | Verify optimized extension loading through sqllogictest and release asset names. |
| `mise run test:sql` | Verify debug extension loading through sqllogictest and release asset names. |
| `mise run test:tooling` | Test release, documentation publication, and distribution build safeguards. |
| `mise run verify` | Check, build, test, analyze C++, and validate documentation. |

`fmt` and `fix` modify files. The `check` gate is read-only and offline on a prepared checkout. Build-backed C++ analysis and strict documentation validation also run in `verify`; external URL checking stays separate because it needs the network.

# Develop and verify a change

## Set up a checkout

Install Git, [mise](https://mise.jdx.dev/getting-started.html), and the [native compiler and SDK](../../reference/dev/platforms.md) for your operating system. `mise` manages the remaining project tools. Windows builds use the Visual Studio compiler environment automatically and do not require WSL.

Clone the repository, review `mise.toml`, then install the locked tools and initialize the pinned submodules:

```text
git clone https://github.com/ofek/duckhop.git
cd duckhop
mise trust
mise install --locked
mise run setup
mise run doctor
```

The first setup needs network access. Rerun `mise install --locked` and `mise run setup` after pulling changes to locked tools or submodules. Use `mise run doctor` to diagnose missing prerequisites.

## Build and test

Use the debug build during development, then run the SQL tests:

```text
mise run build
mise run test
```

Use `mise run build:release` when you need an optimized artifact, then `mise run test:release` to test it. `mise run test:sql` runs the debug SQL suite. Place new SQL-facing tests under `test/sql/` and assert observable results.

If a stale build prevents configuration after a compiler or dependency change, use `mise run clean`, then rebuild. `clean` removes generated build output; it does not replace the setup task.

## Format and check

Run the formatters and inspect the resulting changes:

```text
mise run fmt
mise run check
```

`fmt` modifies C++, TOML, Markdown, and CMake files. `fix` currently applies the same formatters. Review either task's edits before committing.

`check` uses only the prepared checkout and locked tools; it does not download schemas, prose styles, or external URLs. It checks formatting, configuration, prose, local links, structural rules, filenames, workflows, and a strict documentation build. The [task reference](../../reference/dev/tasks.md) lists focused checks for faster iteration.

## Finish a change

Before submitting substantial changes, run:

```text
mise run verify
```

This adds the native build, SQL tests, and compiler-backed static analysis. Follow the pull request template and describe the changed behavior, documentation impact, and any platform or DuckDB compatibility changes. Report the commands and platforms you verified, including checks you could not run.

Discuss public API, persistence, or dependency baseline changes in an issue before implementing them. GitHub generates release notes, so no manual changelog update is required. Report suspected vulnerabilities through the [private reporting path](https://github.com/ofek/duckhop/security/policy).

Use `mise run check:links:external` only when you want a network check of external URLs. That check is separate because remote service failures are not reproducible.

## Diagnose failures

Run `mise run doctor` first when a tool, compiler, or submodule is missing. Run `mise run setup` again after locked dependencies change. Static analysis needs the compilation database from a successful build; run `mise run build` before `mise run check:cpp`.

Fix the source of a diagnostic before considering a suppression. If an upstream header needs a suppression, keep it scoped to the reported issue and explain why it is necessary. Do not disable an entire check to hide a diagnostic.

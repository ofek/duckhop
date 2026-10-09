# Platforms and dependencies

## Developer platforms

Locked tooling supports Linux x64, macOS x64 and ARM64, and native Windows x64. The same mise tasks select each platform's build configuration. CI builds and tests Linux x64, macOS ARM64, and Windows x64.

| Platform | Prerequisite supplied by the operating system |
| --- | --- |
| Linux x64 | A working C/C++ compiler and standard development headers. Clang is the primary CI compiler. |
| macOS x64 or ARM64 | Xcode Command Line Tools with AppleClang and a macOS SDK. |
| Windows x64 | Visual Studio 2022 Build Tools with Desktop development with C++, the MSVC toolset, and a Windows SDK. |

Git and mise are required on every platform. WSL is not required on Windows. `mise` manages the remaining project tools; Python-based tooling is resolved through `uv.lock`. The tooling environment is not a Python distribution of DuckHop.

## DuckDB baseline

DuckHop supports DuckDB 2.x only and uses C++17. The initial baseline is **prerelease**: there was no stable DuckDB 2.x tag when the bootstrap pins were selected.

Git records exact commits for the [DuckDB](https://github.com/duckdb/duckdb) and [extension-ci-tools](https://github.com/duckdb/extension-ci-tools) submodules; `mise run setup` does not follow moving branch tips. Run `mise run doctor` to inspect the checked-out revisions. The distribution workflow must use the same pins, which the tooling tests verify.

The extension-ci-tools reusable workflow uses a prerelease commit because no compatible released 2.x tag exists. This is a documented exception to released-tag provenance, while retaining an immutable full SHA. Other GitHub Actions use full SHAs associated with release tags.

An extension binary must match the targeted DuckDB version and platform; compatibility with DuckDB 1.x or arbitrary 2.x builds is not promised.

## Tool versions

`mise.toml` declares the tools and `mise.lock` resolves their installations. `pyproject.toml` and `uv.lock` define the small Python tooling environment, including Zensical and CMake formatting. Install with `mise install --locked`, then run `mise run setup` to synchronize the Python environment and submodules.

Python workflow scripts run through `uv run --isolated --no-project --offline` with the Python interpreter installed by mise. They use only the standard library and repository modules, so their temporary environments need no project dependencies. Python-based tools run from the prepared project environment through `uv run --no-active --no-sync --offline`; `--no-active` keeps them separate from the workflow script's temporary environment.

`mise run doctor` reports the actual tool, compiler, and submodule state of a checkout. Required checks use committed local rules and exclude submodule and generated output.

## Build controls

The build tasks automatically load the Visual Studio compiler environment on Windows, so a special developer terminal is not required. Compiler caching is an optimization and can be disabled for a clean-build investigation.

| Environment variable | Effect |
| --- | --- |
| `DUCKHOP_NO_CACHE=1` | Disables the compiler cache launcher for the next build configuration. |
| `CMAKE_BUILD_PARALLEL_LEVEL` | Overrides the number of parallel compile jobs, for example when memory is limited. |

## Windows prerelease debug limitation

The pinned DuckDB prerelease does not compile with its normal MSVC debug assertions: some assertions reference planner helpers available only under a different debug definition. Enabling those helpers instead exposes an upstream debugger-helper incompatibility with the MSVC standard library.

On Windows, `mise run build:debug` therefore retains CMake's Debug configuration, unoptimized code, debug symbols, and the MSVC debug runtime, but defines `NDEBUG` to disable DuckDB's internal assertions. Linux and macOS retain their normal debug assertions. This workaround changes no submodule files and must be reconsidered when the DuckDB baseline advances.

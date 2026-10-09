# DuckHop

DuckHop is a DuckDB extension for persistent graph indexing and native traversal.

DuckHop aims to support graph traversal workloads such as reachability, dependency analysis, data lineage, authorization relationships, and infrastructure topology while keeping ordinary DuckDB tables authoritative. A dependency graph or network topology can then be explored alongside the relational data that describes it.

DuckHop is in early development. This repository currently contains a loadable extension skeleton and its contributor tooling; graph indexing and traversal are not implemented, and no public graph API or storage format is defined.

DuckHop targets **DuckDB 2.x only**. The initial baseline is an exact prerelease commit from DuckDB's official `v2.0-cyanoptera` branch. See [platforms and dependencies](docs/reference/dev/platforms.md) for the pinned revisions and compiler prerequisites.

## Get started

Install Git, [mise](https://mise.jdx.dev/getting-started.html), and your platform's native C++ compiler and SDK. On Windows, install Visual Studio 2022 Build Tools with Desktop development with C++; WSL is not required.

```text
git clone https://github.com/ofek/duckhop.git
cd duckhop
mise trust
mise install --locked
mise run setup
mise run build
mise run test
```

The smoke test loads `duckhop` and checks DuckDB's extension metadata. Run `mise run check` for deterministic checks and `mise run verify` for the full local build, test, analysis, and documentation gate.

Read the [development guide](docs/how-to/dev/index.md) and [full documentation](https://ofek.dev/duckhop/) for contributor workflows.

DuckHop is licensed under the [MIT License](LICENSE).

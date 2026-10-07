# Project scope

DuckHop is a standalone DuckDB extension intended for persistent graph adjacency indexing and native traversal over relational edge data. Ordinary DuckDB tables remain authoritative: the extension's role is to make graph-oriented access useful within that relational environment.

Graph traversal can answer reachability questions across a dependency graph, trace data lineage, explore authorization relationships, or examine network topology. These workloads share graph operations, but their meanings differ. An application decides what an edge means, which relationships are valid, and how traversal results affect a business decision.

For example, a reachable node in an authorization graph is not automatically a permission grant. The application still owns its authorization rules. Likewise, a dependency path does not by itself decide deployment order or failure policy. DuckHop's intended responsibilities are generic indexing and traversal; application semantics belong with the application.

## Current boundary

The bootstrap repository supplies a loadable extension, a metadata smoke test, contributor tooling, documentation, and CI/release scaffolding. It does not implement graph indexing, traversal operators, a persistence format, or a public SQL API. The use cases above explain the direction of the project, not features available in the initial extension.

## DuckDB integration

DuckHop uses DuckDB's conventional C++ extension architecture because future indexing and traversal work may need lower-level engine integration. It targets DuckDB 2.x only and follows an exact pre-release baseline until an appropriate stable 2.x release is available.

The pinned submodules make that integration reproducible. Advancing them is a compatibility change that requires build and test evidence, rather than a routine side effect of another change. No external C/C++ library is needed by the initial extension.

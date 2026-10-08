# Maintainer setup

Configure these repository and account settings before publishing documentation or releases from `ofek/duckhop`.

## Repository identity

- Set the description to exactly "DuckDB extension for persistent graph indexing and native traversal".
- Set the website to `https://ofek.dev/duckhop/` once the site is available.
- Add the focused topics `duckdb`, `duckdb-extension`, `graph`, `graph-indexing`, `graph-traversal`, `reachability`, `dependency-graph`, `data-lineage`, `network-topology`, and `cpp`.

## Pages

If `gh-pages` does not exist yet, run the documentation workflow in `docs.yml` once to create it. The workflow then reports that Pages configuration is required. Select the branch and root folder in repository settings, then rerun the workflow to build and verify the published site.

- Configure GitHub Pages to deploy from the `gh-pages` branch and the root `/` folder.
- Verify that the owner's user Pages site owns the `ofek.dev` custom domain and that the domain is verified at the account level.
- Leave DuckHop's repository-specific custom domain unset. Project-site inheritance supplies `/duckhop/`; do not add a `CNAME` for `ofek.dev` or wildcard DNS solely for DuckHop.
- After a successful deployment, verify `https://ofek.dev/duckhop/`, its navigation, and asset URLs under `/duckhop/`.

The documentation workflow builds the current main branch, including on reruns, and publishes generated `site/` contents with `.nojekyll` and the checked-out source commit in its deployment commit message. It uses the temporary `GITHUB_TOKEN` with `contents: write` and `pages: write`, explicitly requests a Pages build, and waits for the generated commit to finish. This request is necessary because [pushes using that token do not automatically trigger a Pages build](https://docs.github.com/en/pages/getting-started-with-github-pages/configuring-a-publishing-source-for-your-github-pages-site). No personal access token is required.

## Release protection

Check out the intended `vMAJOR.MINOR.PATCH` version tag, then run `mise run release:check` to validate its relationship to the source revision. This task is read-only and does not publish; an untagged checkout produces an actionable error.

- Enable GitHub release immutability **before the first real release**; it applies only to future releases.
- Protect the release environment and restrict release tag creation to the maintainers who should publish.
- Require the release workflow to finish validation and asset uploads while the release is still a draft, then publish once. Do not use a manual release that bypasses artifact verification.

The release asset set initially covers `linux_amd64`, `macos_arm64`, and `windows_amd64`, with a checksum manifest. The workflow verifies publication and uploaded assets; it cannot enable repository settings on behalf of an administrator. See [GitHub's immutable release documentation](https://docs.github.com/en/code-security/concepts/supply-chain-security/immutable-releases).

## Branch and Actions settings

- Set the repository's default `GITHUB_TOKEN` permissions to read-only. Individual publishing jobs request only the write permissions they need.
- Add a main-branch ruleset that blocks force pushes and deletion. Require pull requests and conversation resolution if they fit the maintainer workflow.
- Require the key CI checks only after they have completed successfully at least once under their stable names.
- Confirm that the Linux, macOS, and Windows jobs in `test.yml` and the official DuckDB builds in `build.yml` pass before claiming cross-platform validation.

## Updates and reporting

- Install or authorize Renovate for this repository and verify that it can maintain both `mise.lock` and `uv.lock` under its execution policy.
- Review DuckDB and extension-ci-tools updates together for compatibility. Their update pull requests must not auto-merge.
- When adopting a stable DuckDB baseline, update the ABI identifier check in [`validate_binary`](../scripts/release.py) to match `DUCKDB_NORMALIZED_VERSION` in DuckDB's `CMakeLists.txt`. Stable builds record a version string instead of the shortened commit hash that the current validator expects, so it would reject valid artifacts. Add regression coverage and validate real release artifacts before publishing.
- Enable GitHub private vulnerability reporting and confirm that the security policy's reporting link works.

Renovate groups routine developer-tool updates and schedules weekly lockfile maintenance. Major tools and dependency baseline changes require review. No duplicate Dependabot configuration is needed.

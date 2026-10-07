"""Package tested DuckDB artifacts and publish complete immutable releases."""

import argparse
import hashlib
import json
import os
from pathlib import Path
import re
import shutil
import subprocess
import sys
import time


ROOT = Path(__file__).resolve().parents[1]
# Map release platform names to DuckDB's artifact and metadata identifiers.
PLATFORMS = {
    "linux_amd64": "linux_amd64",
    "macos_arm64": "osx_arm64",
    "windows_amd64": "windows_amd64",
}
SEMVER = re.compile(
    r"v(0|[1-9][0-9]*)\.(0|[1-9][0-9]*)\.(0|[1-9][0-9]*)"
    r"(?:-((?:0|[1-9][0-9]*|[0-9]*[A-Za-z-][0-9A-Za-z-]*)"
    r"(?:\.(?:0|[1-9][0-9]*|[0-9]*[A-Za-z-][0-9A-Za-z-]*))*))?"
)


def run(*arguments, capture=False):
    """Pass arguments directly to tools without interpreting a shell command."""
    result = subprocess.run(
        arguments, cwd=ROOT, check=True, text=True,
        stdout=subprocess.PIPE if capture else None,
    )
    return result.stdout.strip() if capture else None


def git_revision(reference):
    return run("git", "rev-parse", "--verify", f"{reference}^{{commit}}", capture=True)


def validate_tag(tag):
    if not SEMVER.fullmatch(tag):
        raise ValueError("Use vMAJOR.MINOR.PATCH with an optional SemVer prerelease suffix.")
    if len(tag.encode("ascii")) > 32:
        raise ValueError("Release tags must fit DuckDB's 32-byte extension version metadata field.")


def validate_source(tag, revision):
    validate_tag(tag)
    if not re.fullmatch(r"[0-9a-f]{40}", revision):
        raise ValueError("The release revision must be a full Git commit SHA.")
    if git_revision("HEAD") != revision or git_revision(f"refs/tags/{tag}") != revision:
        raise ValueError("The checked-out commit and release tag must match the release revision.")


def resolve_source(tag, revision):
    revision = revision or git_revision("HEAD")
    if not tag:
        try:
            tag = run("git", "describe", "--tags", "--exact-match", "HEAD", capture=True)
        except subprocess.CalledProcessError as error:
            raise ValueError(
                "The checkout has no exact version tag. Check out a vMAJOR.MINOR.PATCH tag before running release:check."
            ) from error
    return tag, revision


def pinned_revision(name):
    entry = run("git", "ls-tree", "HEAD", name, capture=True).split()
    if len(entry) != 4 or entry[:2] != ["160000", "commit"]:
        raise ValueError(f"The release source does not pin the {name} submodule.")
    return entry[2]


def digest(path):
    with path.open("rb") as handle:
        return hashlib.file_digest(handle, "sha256").hexdigest()


def validate_binary(path, platform, duckdb, tag):
    """Check the pinned DuckDB footer format and the platform recorded by the build."""
    if path.is_symlink() or not path.is_file() or path.stat().st_size <= 512:
        raise ValueError(f"Missing or invalid extension binary: {path}")
    with path.open("rb") as handle:
        handle.seek(-512, os.SEEK_END)
        footer = handle.read(512)
    if footer[224:256].rstrip(b"\0") != b"4":
        raise ValueError(f"Unexpected DuckDB extension metadata version: {path}")
    if footer[192:224].rstrip(b"\0") != PLATFORMS[platform].encode("ascii"):
        raise ValueError(f"Extension metadata does not match platform {platform}: {path}")
    if footer[160:192].rstrip(b"\0") != duckdb[:10].encode("ascii"):
        raise ValueError(f"The extension targets a different DuckDB ABI revision: {path}")
    if footer[96:128].rstrip(b"\0") != b"CPP":
        raise ValueError(f"The extension does not use the required DuckDB C++ ABI: {path}")
    if footer[128:160].rstrip(b"\0") != tag.encode("ascii"):
        raise ValueError(f"The extension version does not match the tagged source: {path}")


def asset_names(tag):
    # DuckDB derives the C++ entrypoint from the filename before its first period.
    return {platform: f"duckhop.{tag}.{platform}.duckdb_extension" for platform in PLATFORMS}


def package(tag, revision, artifacts, output):
    validate_source(tag, revision)
    duckdb = pinned_revision("duckdb")
    ci_tools = pinned_revision("extension-ci-tools")
    expected = {f"duckhop-{duckdb}-extension-{platform}" for platform in PLATFORMS.values()}
    if artifacts.is_symlink() or not artifacts.is_dir():
        raise ValueError("The official build artifact directory is missing.")
    if {path.name for path in artifacts.iterdir()} != expected:
        raise ValueError(f"Expected exactly these official build artifacts: {sorted(expected)}")
    if output.is_symlink() or (output.exists() and any(output.iterdir())):
        raise ValueError("The release output directory must be empty.")
    binaries = {}
    for platform, duckdb_platform in PLATFORMS.items():
        folder = artifacts / f"duckhop-{duckdb}-extension-{duckdb_platform}"
        if folder.is_symlink() or not folder.is_dir():
            raise ValueError(f"Invalid artifact directory: {folder}")
        if any(path.is_symlink() for path in folder.rglob("*")):
            raise ValueError(f"Artifact directories must not contain symlinks: {folder}")
        files = sorted(folder.rglob("*.duckdb_extension"))
        binary = folder / "duckhop.duckdb_extension"
        if files != [binary]:
            raise ValueError(f"Expected one duckhop extension at the artifact root: {folder}")
        validate_binary(binary, platform, duckdb, tag)
        binaries[platform] = binary
    output.mkdir(parents=True, exist_ok=True)
    names = asset_names(tag)
    for platform, binary in binaries.items():
        shutil.copyfile(binary, output / names[platform])
    manifest = {
        "tag": tag,
        "source_commit": revision,
        "duckdb_commit": duckdb,
        "extension_ci_tools_commit": ci_tools,
        "assets": {
            platform: {"name": names[platform], "sha256": digest(output / names[platform])}
            for platform in PLATFORMS
        },
    }
    (output / "manifest.json").write_text(
        json.dumps(manifest, indent=2, sort_keys=True) + "\n", encoding="utf-8", newline="\n"
    )
    files = sorted(path for path in output.iterdir() if path.is_file())
    (output / "SHA256SUMS").write_text(
        "".join(f"{digest(path)}  {path.name}\n" for path in files), encoding="utf-8", newline="\n"
    )
    verify_local(tag, revision, output)


def verify_local(tag, revision, directory):
    validate_source(tag, revision)
    names = asset_names(tag)
    expected = set(names.values()) | {"manifest.json", "SHA256SUMS"}
    if directory.is_symlink() or not directory.is_dir():
        raise ValueError("The release asset directory is missing.")
    paths = list(directory.iterdir())
    if {path.name for path in paths} != expected or any(
        path.is_symlink() or not path.is_file() for path in paths
    ):
        raise ValueError("The release directory must contain exactly the expected asset set.")
    manifest = json.loads((directory / "manifest.json").read_text(encoding="utf-8"))
    if (
        manifest.get("tag") != tag
        or manifest.get("source_commit") != revision
        or manifest.get("duckdb_commit") != pinned_revision("duckdb")
        or manifest.get("extension_ci_tools_commit") != pinned_revision("extension-ci-tools")
        or set(manifest.get("assets", {})) != set(PLATFORMS)
    ):
        raise ValueError("The release manifest does not match the tagged source and targets.")
    for platform, name in names.items():
        validate_binary(directory / name, platform, manifest["duckdb_commit"], tag)
        if manifest["assets"][platform] != {"name": name, "sha256": digest(directory / name)}:
            raise ValueError(f"The manifest checksum does not match {name}.")
    expected_checksums = "".join(
        f"{digest(directory / name)}  {name}\n" for name in sorted(expected - {"SHA256SUMS"})
    )
    if (directory / "SHA256SUMS").read_text(encoding="utf-8") != expected_checksums:
        raise ValueError("The checksum manifest does not match the complete release asset set.")
    return {path.name: path for path in paths}


def api(repo, endpoint, *, paginate=False):
    options = ("--paginate", "--slurp") if paginate else ()
    return json.loads(run("gh", "api", f"repos/{repo}/{endpoint}", *options, capture=True))


def remote_revision(repo, tag):
    reference = api(repo, f"git/ref/tags/{tag}")["object"]
    for _ in range(10):
        if reference["type"] == "commit":
            return reference["sha"]
        if reference["type"] != "tag":
            break
        reference = api(repo, f"git/tags/{reference['sha']}")["object"]
    raise ValueError("The remote release tag does not resolve to a commit.")


def find_release(repo, tag):
    matches = [
        release for page in api(repo, "releases?per_page=100", paginate=True)
        for release in page if release["tag_name"] == tag
    ]
    if len(matches) > 1:
        raise ValueError("Multiple releases refer to the requested tag.")
    return matches[0] if matches else None


def remote_assets(repo, release):
    return [
        asset for page in api(repo, f"releases/{release['id']}/assets?per_page=100", paginate=True)
        for asset in page
    ]


def verify_assets(assets, files, *, complete):
    names = [asset["name"] for asset in assets]
    if len(set(names)) != len(names) or not set(names) <= set(files):
        raise ValueError("The release contains duplicate or unexpected assets.")
    if complete and set(names) != set(files):
        raise ValueError("The release does not contain the complete expected asset set.")
    for asset in assets:
        path = files[asset["name"]]
        if (
            asset["state"] != "uploaded"
            or asset["size"] != path.stat().st_size
            or asset.get("digest") != f"sha256:{digest(path)}"
        ):
            raise ValueError(f"The uploaded asset does not match the local file: {path.name}")


def publish(repo, tag, revision, directory):
    files = verify_local(tag, revision, directory)
    if remote_revision(repo, tag) != revision:
        raise ValueError("The remote tag has moved since this source was checked out.")
    release = find_release(repo, tag)
    if release is None:
        options = ("--prerelease",) if "-" in tag else ()
        run(
            "gh", "release", "create", tag, "--repo", repo, "--draft", "--verify-tag",
            "--target", revision, "--title", tag, "--generate-notes", *options,
        )
        release = find_release(repo, tag)
    if release is None:
        raise ValueError("The draft release was not created.")
    if not release["draft"]:
        if not release.get("immutable"):
            raise ValueError("The published release is not immutable; enable repository release immutability.")
        verify_assets(remote_assets(repo, release), files, complete=True)
        print("The immutable release is already published; no changes were made.")
        return
    if release["prerelease"] != ("-" in tag):
        raise ValueError("The draft prerelease setting does not match the version tag.")
    assets = remote_assets(repo, release)
    verify_assets(assets, files, complete=False)
    uploaded = {asset["name"] for asset in assets}
    for name, path in sorted(files.items()):
        if name not in uploaded:
            run("gh", "release", "upload", tag, str(path), "--repo", repo)
    release = find_release(repo, tag)
    if release is None or not release["draft"]:
        raise ValueError("The draft changed while assets were being uploaded.")
    verify_assets(remote_assets(repo, release), files, complete=True)
    if remote_revision(repo, tag) != revision:
        raise ValueError("The tag moved while assets were being uploaded; the draft was not published.")
    run("gh", "release", "edit", tag, "--repo", repo, "--draft=false")


def verify(repo, tag, revision, directory):
    files = verify_local(tag, revision, directory)
    release = find_release(repo, tag)
    if release is None or release["draft"] or not release.get("immutable"):
        raise ValueError("The release must be published and immutable before verification.")
    if remote_revision(repo, tag) != revision:
        raise ValueError("The published release tag does not match the built revision.")
    verify_assets(remote_assets(repo, release), files, complete=True)
    for attempt in range(6):
        try:
            run("gh", "release", "verify", tag, "--repo", repo)
            break
        except subprocess.CalledProcessError:
            if attempt == 5:
                raise
            # GitHub may take a short time to make the new release attestation available.
            time.sleep(10)
    for path in sorted(files.values()):
        run("gh", "release", "verify-asset", tag, str(path), "--repo", repo)


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("command", choices=("validate", "package", "publish", "verify"))
    parser.add_argument("--tag", default=os.environ.get("GITHUB_REF_NAME", ""))
    parser.add_argument("--revision", default=os.environ.get("GITHUB_SHA", ""))
    parser.add_argument("--repo", default=os.environ.get("GITHUB_REPOSITORY", ""))
    parser.add_argument("--artifacts", type=Path, default=ROOT / "artifacts")
    parser.add_argument("--output", type=Path, default=ROOT / "dist")
    parser.add_argument("--directory", type=Path, default=ROOT / "dist")
    args = parser.parse_args()
    args.tag, args.revision = resolve_source(args.tag, args.revision)
    if args.command == "validate":
        validate_source(args.tag, args.revision)
        if output := os.environ.get("GITHUB_OUTPUT"):
            with open(output, "a", encoding="utf-8", newline="\n") as handle:
                handle.write(f'extension_config=set(DUCKDB_EXTENSION_DUCKHOP_EXT_VERSION "{args.tag}")\n')
    elif args.command == "package":
        package(args.tag, args.revision, args.artifacts, args.output)
    else:
        if not re.fullmatch(r"[A-Za-z0-9_.-]+/[A-Za-z0-9_.-]+", args.repo):
            raise ValueError("Provide a GitHub repository in OWNER/REPO form.")
        operation = publish if args.command == "publish" else verify
        operation(args.repo, args.tag, args.revision, args.directory)


if __name__ == "__main__":
    try:
        main()
    except (ValueError, OSError, subprocess.CalledProcessError) as error:
        sys.exit(str(error))

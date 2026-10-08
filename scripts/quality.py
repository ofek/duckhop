"""Keep file selection and platform differences out of contributor commands."""

import argparse
import os
from pathlib import Path
import shutil
import subprocess
import tempfile


ROOT = Path(__file__).resolve().parents[1]
UV = ["uv", "run", "--no-sync", "--offline"]


def run(*args):
    subprocess.run([str(arg) for arg in args], cwd=ROOT, check=True)


def files(*suffixes):
    """Include new project files while excluding submodules and ignored output."""
    result = subprocess.check_output(
        ["git", "ls-files", "--cached", "--others", "--exclude-standard", "-z"],
        cwd=ROOT,
    )
    return sorted(
        path for path in set(result.decode().split("\0"))
        if path and Path(path).suffix in suffixes and (ROOT / path).is_file()
    )


def markdown(write=False):
    paths = files(".md")
    options = ["--no-cache", "--deny-config-warnings"]
    run("rumdl", "fmt", *([] if write else ["--check"]), *options, *paths)
    if not write:
        run("rumdl", "check", *options, *paths)


def toml(write=False):
    paths = files(".toml")
    run("tombi", "format", "--offline", *([] if write else ["--check"]), *paths)
    if not write:
        run("tombi", "lint", "--offline", "--error-on-warnings", *paths)


def formatting(write=False):
    run(*UV, "clang-format", *(["-i"] if write else ["--dry-run", "--Werror"]), *files(".cpp", ".hpp", ".h"))
    run(*UV, "gersemi", "--in-place" if write else "--check", "--warnings-as-errors", "--definitions", "duckdb/extension/extension_build_tools.cmake", "--", "CMakeLists.txt", "extension_config.cmake")
    toml(write)
    markdown(write)


def docs():
    """Keep strict validation output outside the repository."""
    with tempfile.TemporaryDirectory(prefix="duckhop-docs-") as directory:
        temporary = Path(directory)
        shutil.copytree(ROOT / "docs", temporary / "docs")
        shutil.copyfile(ROOT / "zensical.toml", temporary / "zensical.toml")
        executable = ROOT / ".venv" / ("Scripts/zensical.exe" if os.name == "nt" else "bin/zensical")
        subprocess.run([str(executable), "build", "--strict", "--clean"], cwd=temporary, check=True)


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("command", choices=["format", "toml", "markdown", "prose", "ast", "links", "docs"])
    parser.add_argument("--write", action="store_true")
    parser.add_argument("--external", action="store_true")
    args = parser.parse_args()
    os.chdir(ROOT)
    if args.command == "format":
        formatting(args.write)
    elif args.command == "toml":
        toml(args.write)
    elif args.command == "markdown":
        markdown(args.write)
    elif args.command == "prose":
        run("vale", *files(".md"))
    elif args.command == "ast":
        run("ast-grep", "test", "--skip-snapshot-tests")
        run("ast-grep", "scan", "--error=unused-suppression", "--error=no-suppress-all", "src")
    elif args.command == "links":
        run("lychee", "--no-progress", *([] if args.external else ["--offline"]), *files(".md", ".html"))
    else:
        docs()


if __name__ == "__main__":
    main()

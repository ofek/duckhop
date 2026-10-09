"""Keep file selection and platform differences out of contributor commands."""

import argparse
import configparser
import json
import os
from pathlib import Path
import re
import shutil
import subprocess
import sys
import tempfile


ROOT = Path(__file__).resolve().parents[1]
UV = ["uv", "run", "--no-active", "--no-sync", "--offline"]


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


def keyboard_shortcut(lint, source):
    """Exclude abbreviation advice only inside complete Zensical keyboard shortcuts."""
    if lint["rule"] != "ExpandControl":
        return False
    span = lint["span"]
    return any(
        match.start() <= span["char_start"] and span["char_end"] <= match.end()
        for match in re.finditer(r"\+\+[^+\n]+(?:\+[^+\n]+)*\+\+", source)
    )


def harper_dictionary():
    """Derive Harper's literal words from the shared Vale vocabulary."""
    entries = []
    config = configparser.ConfigParser(interpolation=None)
    config.read_string("[DEFAULT]\n" + (ROOT / ".vale.ini").read_text(encoding="utf-8"))
    vocabulary = ROOT / config["DEFAULT"]["StylesPath"] / "config/vocabularies" / config["DEFAULT"]["Vocab"] / "accept.txt"
    for line in vocabulary.read_text(encoding="utf-8").splitlines():
        entry = line.strip()
        if not entry or entry.startswith("# "):
            continue
        word = entry.removeprefix("(?i)")
        if re.search(r"[\\\[\]{}()*+?|^$]", word):
            raise ValueError(f"Shared vocabulary entries must be literal words or phrases: {entry}")
        entries.append(word)
        # Harper checks hyphen-separated components as individual words.
        if "-" in word:
            entries.extend(word.split("-"))
    return "\n".join(entries) + "\n"


def harper(paths):
    """Report native Harper findings using project vocabulary and explicit file paths."""
    failures = 0
    with tempfile.TemporaryDirectory(prefix="duckhop-harper-") as directory:
        dictionary = Path(directory) / "dictionary.txt"
        dictionary.write_text(harper_dictionary(), encoding="utf-8")
        for path in paths:
            # The repository uses sentence-case headings rather than title case.
            result = subprocess.run(
                [
                    "harper-cli", "lint", "--format", "json", "--quiet", "--dialect", "us",
                    "--ignore", "UseTitleCase", "--user-dict-path", str(dictionary),
                    "--file-dict-path", directory, path,
                ],
                cwd=ROOT, capture_output=True, text=True, encoding="utf-8",
            )
            if result.returncode not in (0, 1):
                result.check_returncode()
            source = (ROOT / path).read_text(encoding="utf-8")
            documents = json.loads(result.stdout)
            if len(documents) != 1:
                raise RuntimeError(f"Expected one Harper result for {path}.")
            for document in documents:
                if document.get("error"):
                    raise RuntimeError(document["error"])
                for lint in document["lints"]:
                    if keyboard_shortcut(lint, source):
                        continue
                    print(f"{path}:{lint['line']}:{lint['column']}: {lint['rule']}: {lint['message']}")
                    failures += 1
    print(f"Harper found {failures} issues in {len(paths)} files.")
    return failures


def prose():
    """Keep prose checks independent of personal Harper dictionaries."""
    paths = files(".md")
    run("vale", *paths)
    if harper(paths):
        sys.exit(1)


def docs():
    """Keep strict validation output outside the repository."""
    with tempfile.TemporaryDirectory(prefix="duckhop-docs-") as directory:
        temporary = Path(directory)
        shutil.copytree(ROOT / "docs", temporary / "docs")
        shutil.copyfile(ROOT / "zensical.toml", temporary / "zensical.toml")
        subprocess.run([*UV, "--project", str(ROOT), "zensical", "build", "--strict", "--clean"], cwd=temporary, check=True)


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
        prose()
    elif args.command == "ast":
        run("ast-grep", "test", "--skip-snapshot-tests")
        run("ast-grep", "scan", "--error=unused-suppression", "--error=no-suppress-all", "src")
    elif args.command == "links":
        run("lychee", "--no-progress", *([] if args.external else ["--offline"]), *files(".md", ".html"))
    else:
        docs()


if __name__ == "__main__":
    main()

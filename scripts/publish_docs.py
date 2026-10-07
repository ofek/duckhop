"""Publish only generated documentation to the gh-pages branch."""

import argparse
import base64
import json
import os
from pathlib import Path
import re
import shutil
import subprocess
import sys
import tempfile
import time


ROOT = Path(__file__).resolve().parents[1]


def validate_site(site):
    if site.is_symlink() or not site.is_dir() or not (site / "index.html").is_file():
        raise ValueError("Build the documentation before publishing it.")
    for path in site.rglob("*"):
        if path.is_symlink() or path.name == ".git":
            raise ValueError("Generated documentation must not contain symlinks or Git metadata.")
    if (site / "CNAME").exists():
        raise ValueError("DuckHop inherits ofek.dev/duckhop/ and must not publish a CNAME override.")


def pages_api(repository, environment, endpoint="", *, method="GET"):
    response = subprocess.check_output(
        ["gh", "api", "--method", method, f"repos/{repository}/pages{endpoint}"],
        env=environment, text=True,
    )
    return json.loads(response)


def validate_pages_settings(settings):
    if settings.get("build_type") != "legacy" or settings.get("source") != {"branch": "gh-pages", "path": "/"}:
        raise ValueError("Configure GitHub Pages to publish from the gh-pages branch root before deployment.")
    if settings.get("cname"):
        raise ValueError("Remove the DuckHop custom-domain override so the project inherits ofek.dev/duckhop/.")


def request_build(repository, environment, revision):
    """Request branch deployment because GITHUB_TOKEN pushes do not trigger Pages builds."""
    pages_api(repository, environment, "/builds", method="POST")
    for _ in range(60):
        build = pages_api(repository, environment, "/builds/latest")
        if build.get("commit") == revision:
            if build["status"] == "built":
                print(f"GitHub Pages deployed generated commit {revision}.")
                return
            if build["status"] == "errored":
                raise ValueError(f"GitHub Pages build failed: {build.get('error', {}).get('message', '')}")
        time.sleep(5)
    raise ValueError("GitHub Pages did not confirm deployment of the generated commit within five minutes.")


def publish(site):
    validate_site(site)
    repository = os.environ.get("GITHUB_REPOSITORY", "")
    token = os.environ.get("GITHUB_TOKEN", "")
    if os.environ.get("GITHUB_ACTIONS") != "true" or os.environ.get("GITHUB_REF") != "refs/heads/main":
        raise ValueError("Publish documentation only from the main-branch GitHub Actions workflow.")
    if not re.fullmatch(r"[A-Za-z0-9_.-]+/[A-Za-z0-9_.-]+", repository):
        raise ValueError("GITHUB_REPOSITORY must identify the source repository.")
    if not token:
        raise ValueError("The documentation publishing token is required.")
    revision = subprocess.check_output(["git", "rev-parse", "HEAD"], cwd=ROOT, text=True).strip()
    environment = os.environ.copy()
    environment["GH_TOKEN"] = token
    credential = base64.b64encode(f"x-access-token:{token}".encode()).decode()
    environment.update({
        "GIT_CONFIG_COUNT": "1",
        "GIT_CONFIG_KEY_0": "http.https://github.com/.extraheader",
        "GIT_CONFIG_VALUE_0": f"AUTHORIZATION: basic {credential}",
        "GIT_TERMINAL_PROMPT": "0",
    })
    with tempfile.TemporaryDirectory(prefix="duckhop-pages-") as temporary:
        checkout = Path(temporary)

        def git(*arguments, capture=False):
            result = subprocess.run(
                ["git", *arguments], cwd=checkout, env=environment, check=True, text=True,
                stdout=subprocess.PIPE if capture else None,
            )
            return result.stdout.strip() if capture else None

        git("init", "--initial-branch=gh-pages")
        git("remote", "add", "origin", f"https://github.com/{repository}.git")
        remote = git("ls-remote", "--heads", "origin", "refs/heads/gh-pages", capture=True)
        if remote:
            git("fetch", "--depth=1", "origin", "refs/heads/gh-pages")
            git("reset", "--soft", "FETCH_HEAD")
        shutil.copytree(site, checkout, dirs_exist_ok=True)
        (checkout / ".nojekyll").touch()
        git("add", "--all")
        if remote and not git("diff", "--cached", "--name-only", capture=True):
            print("The published documentation already matches the generated site.")
        else:
            git(
                "-c", "user.name=github-actions[bot]", "-c",
                "user.email=41898282+github-actions[bot]@users.noreply.github.com",
                "commit", "--message", f"docs: publish {revision}",
            )
            git("push", "origin", "HEAD:refs/heads/gh-pages")
        generated_revision = git("rev-parse", "HEAD", capture=True)
    try:
        settings = pages_api(repository, environment)
    except subprocess.CalledProcessError as error:
        raise ValueError(
            "The gh-pages branch is ready, but Pages settings could not be read. Check the GitHub CLI error above. "
            "If Pages is not configured, select the gh-pages branch root and rerun Documentation."
        ) from error
    validate_pages_settings(settings)
    request_build(repository, environment, generated_revision)


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--site", type=Path, default=ROOT / "site")
    args = parser.parse_args()
    publish(args.site)


if __name__ == "__main__":
    try:
        main()
    except (ValueError, OSError, subprocess.CalledProcessError) as error:
        sys.exit(str(error))

"""Exercise release integrity checks without contacting GitHub or publishing artifacts."""

import csv
import json
import os
from pathlib import Path
import re
import shutil
import tempfile
import subprocess
import sys
import unittest
from unittest import mock

from scripts import release


TAG = "v0.1.0-rc.1"
REVISION = "a" * 40
DUCKDB = "b" * 40
CI_TOOLS = "c" * 40


class DistributionPinTests(unittest.TestCase):
    def test_workflow_uses_the_checked_out_submodule_revisions(self):
        workflow = (release.ROOT / ".github/workflows/build.yml").read_text(encoding="utf-8")
        patterns = {
            "duckdb": [r"duckdb_version: ([0-9a-f]{40})"],
            "extension-ci-tools": [
                r"ci_tools_version: ([0-9a-f]{40})",
                r"uses: duckdb/extension-ci-tools/\.github/workflows/_extension_distribution\.yml@([0-9a-f]{40})",
            ],
        }
        for name, expressions in patterns.items():
            revision = subprocess.check_output(
                ["git", "-C", str(release.ROOT / name), "rev-parse", "HEAD"], text=True,
            ).strip()
            for expression in expressions:
                with self.subTest(dependency=name, setting=expression):
                    self.assertEqual(re.findall(r"(?m)^\s+" + expression + r"\s*$", workflow), [revision])


def binary(path, platform, tag=TAG):
    footer = bytearray(512)
    footer[96:99] = b"CPP"
    footer[128:160] = tag.encode()[:32].ljust(32, b"\0")
    footer[160:170] = DUCKDB[:10].encode()
    footer[192:192 + len(platform)] = platform.encode()
    footer[224] = ord("4")
    path.write_bytes(b"binary" + footer)


class VersionTests(unittest.TestCase):
    def test_accepts_stable_and_prerelease_versions(self):
        for tag in ("v0.0.0", "v12.34.56", TAG, "v1.0.0-alpha.0.x-2"):
            with self.subTest(tag=tag):
                release.validate_tag(tag)

    def test_rejects_ambiguous_versions_and_shell_input(self):
        for tag in ("1.0.0", "v01.0.0", "v1.0", "v1.0.0-01", "v1.0.0+build", "v1.0.0\n", "v1.0.0;echo bad"):
            with self.subTest(tag=tag), self.assertRaises(ValueError):
                release.validate_tag(tag)

    def test_rejects_tags_that_exceed_metadata_field(self):
        for tag in ("v" + "1" * 28 + ".0.0", "v1.0.0-" + "a" * 26):
            with self.subTest(tag=tag), self.assertRaisesRegex(ValueError, "32-byte"):
                release.validate_tag(tag)

    def test_rejects_checkout_that_differs_from_tag(self):
        with mock.patch.object(release, "git_revision", side_effect=[REVISION, DUCKDB]):
            with self.assertRaisesRegex(ValueError, "checked-out commit"):
                release.validate_source(TAG, REVISION)

    def test_invalid_source_does_not_emit_build_configuration(self):
        with tempfile.TemporaryDirectory() as temporary:
            output = Path(temporary) / "github-output"
            with (
                mock.patch.object(release, "git_revision", return_value=DUCKDB),
                mock.patch.object(sys, "argv", ["release", "validate", "--tag", TAG, "--revision", REVISION]),
                mock.patch.dict(os.environ, {"GITHUB_OUTPUT": str(output)}),
                self.assertRaisesRegex(ValueError, "checked-out commit"),
            ):
                release.main()
            self.assertFalse(output.exists())

    def test_resolves_local_source_without_github_environment(self):
        with (
            mock.patch.object(release, "git_revision", return_value=REVISION),
            mock.patch.object(release, "run", return_value=TAG) as command,
        ):
            self.assertEqual(release.resolve_source("", ""), (TAG, REVISION))
        command.assert_called_once_with("git", "describe", "--tags", "--exact-match", "HEAD", capture=True)

    def test_explicit_source_does_not_require_tag_discovery(self):
        with mock.patch.object(release, "run") as command:
            self.assertEqual(release.resolve_source(TAG, REVISION), (TAG, REVISION))
        command.assert_not_called()

    def test_untagged_checkout_has_actionable_error(self):
        with mock.patch.object(release, "run", side_effect=subprocess.CalledProcessError(128, "git")):
            with self.assertRaisesRegex(ValueError, "Check out a vMAJOR.MINOR.PATCH tag"):
                release.resolve_source("", REVISION)


class BuildVersionTests(unittest.TestCase):
    def test_explicit_release_version_overrides_competing_git_tags(self):
        with tempfile.TemporaryDirectory(prefix="duckhop-version-") as temporary:
            root = Path(temporary)
            source = root / "source"
            source.mkdir()
            config = source / "extension_config.cmake"
            shutil.copyfile(release.ROOT / "extension_config.cmake", config)
            git = ["git", "-C", str(source)]
            subprocess.run([*git, "init", "--quiet"], check=True)
            identity = [
                "-c", f"core.hooksPath={root / 'empty-hooks'}",
                "-c", "user.name=Fixture", "-c", "user.email=fixture@example.invalid",
                "-c", "commit.gpgsign=false", "-c", "tag.gpgsign=false",
            ]
            subprocess.run([*git, *identity, "commit", "--quiet", "--allow-empty", "-m", "Fixture"], check=True)
            subprocess.run([*git, *identity, "tag", "--annotate", TAG, "-m", "Release candidate"], check=True)
            subprocess.run([*git, *identity, "tag", "v0.1.0"], check=True)
            subprocess.run([*git, *identity, "tag", "v0.1.0-rc-test.1"], check=True)
            revision = subprocess.check_output([*git, "rev-parse", "HEAD"], text=True).strip()
            detected = subprocess.check_output(
                [*git, "describe", "--tags", "--always", "--match", "v*.*.*"], text=True,
            ).strip()
            self.assertEqual(detected, TAG)

            harness = root / "harness"
            (harness / "extension").mkdir(parents=True)
            (harness / "extension/extension_config.cmake").touch()
            (harness / "CMakeLists.txt").write_text(
                'cmake_minimum_required(VERSION 3.15...3.29)\n'
                'project(ReleaseVersion NONE)\n'
                'set(EXTENSION_CONFIG_BUILD TRUE)\n'
                'set(EXTENSION_TESTS_ONLY FALSE)\n'
                'set(BUILD_EXTENSIONS_ONLY FALSE)\n'
                'set(EXPORT_DLL_SYMBOLS FALSE)\n'
                'set(EXTENSION_CONFIG_BASE_DIR "${CMAKE_CURRENT_SOURCE_DIR}/extension")\n'
                'set(VERSIONING_TAG_MATCH "v*.*.*")\n'
                f'set(DUCKDB_EXTENSION_CONFIGS "{config.as_posix()}")\n'
                f'include("{(release.ROOT / "duckdb/extension/extension_build_tools.cmake").as_posix()}")\n',
                encoding="utf-8",
            )
            original_config = config.read_text(encoding="utf-8")
            for tag in ("v0.1.0", "v0.1.0-rc-test.1"):
                with self.subTest(tag=tag):
                    github_output = root / f"{tag}.output"
                    with (
                        mock.patch.object(release, "ROOT", source),
                        mock.patch.object(sys, "argv", ["release", "validate", "--tag", tag, "--revision", revision]),
                        mock.patch.dict(os.environ, {"GITHUB_OUTPUT": str(github_output)}),
                    ):
                        release.main()
                    name, separator, extra_config = github_output.read_text(encoding="utf-8").partition("=")
                    self.assertEqual((name, separator), ("extension_config", "="))
                    # The upstream workflow appends extra_extension_config before configuring each platform.
                    config.write_text(
                        original_config + "\n" + extra_config,
                        encoding="utf-8",
                    )
                    build = root / tag
                    result = subprocess.run(
                        ["cmake", "-S", str(harness), "-B", str(build), "-G", "Ninja"],
                        capture_output=True, text=True,
                    )
                    self.assertEqual(result.returncode, 0, result.stdout + result.stderr)
                    with (build / "extensions.csv").open(encoding="utf-8", newline="") as handle:
                        self.assertEqual(list(csv.DictReader(handle, skipinitialspace=True)), [
                            {"name": "duckhop", "version": tag},
                        ])
                    artifact = root / "duckhop.duckdb_extension"
                    binary(artifact, "linux_amd64", tag)
                    release.validate_binary(artifact, "linux_amd64", DUCKDB, tag)


class ArtifactTests(unittest.TestCase):
    def setUp(self):
        self.temporary = tempfile.TemporaryDirectory()
        self.addCleanup(self.temporary.cleanup)
        self.root = Path(self.temporary.name)
        self.artifacts = self.root / "artifacts"
        self.output = self.root / "dist"
        self.artifacts.mkdir()
        self.source = mock.patch.object(release, "validate_source")
        self.source.start()
        self.addCleanup(self.source.stop)
        self.pins = mock.patch.object(
            release, "pinned_revision", side_effect=lambda name: DUCKDB if name == "duckdb" else CI_TOOLS
        )
        self.pins.start()
        self.addCleanup(self.pins.stop)
        for platform in release.PLATFORMS.values():
            directory = self.artifacts / f"duckhop-{DUCKDB}-extension-{platform}"
            directory.mkdir()
            binary(directory / "duckhop.duckdb_extension", platform)

    def package(self):
        release.package(TAG, REVISION, self.artifacts, self.output)

    def test_packages_all_targets_and_checksums(self):
        self.package()
        files = release.verify_local(TAG, REVISION, self.output)
        self.assertEqual(len(files), 5)
        manifest = json.loads((self.output / "manifest.json").read_text())
        self.assertEqual(manifest["source_commit"], REVISION)
        self.assertEqual(manifest["duckdb_commit"], DUCKDB)
        name = f"duckhop.{TAG}.macos_arm64.duckdb_extension"
        self.assertEqual(manifest["assets"]["macos_arm64"]["name"], name)
        self.assertNotIn("osx_arm64", manifest["assets"])
        source = self.artifacts / f"duckhop-{DUCKDB}-extension-osx_arm64" / "duckhop.duckdb_extension"
        self.assertEqual((self.output / name).read_bytes(), source.read_bytes())

    def test_rejects_macos_alias_in_duckdb_metadata(self):
        path = self.artifacts / f"duckhop-{DUCKDB}-extension-osx_arm64" / "duckhop.duckdb_extension"
        binary(path, "macos_arm64")
        with self.assertRaisesRegex(ValueError, "platform"):
            self.package()

    def test_missing_platform_does_not_create_output(self):
        directory = self.artifacts / f"duckhop-{DUCKDB}-extension-linux_amd64"
        (directory / "duckhop.duckdb_extension").unlink()
        directory.rmdir()
        with self.assertRaisesRegex(ValueError, "exactly"):
            self.package()
        self.assertFalse(self.output.exists())

    def test_rejects_binary_for_wrong_platform(self):
        path = self.artifacts / f"duckhop-{DUCKDB}-extension-linux_amd64" / "duckhop.duckdb_extension"
        binary(path, "windows_amd64")
        with self.assertRaisesRegex(ValueError, "platform"):
            self.package()

    def test_rejects_binary_for_wrong_duckdb_revision(self):
        path = self.artifacts / f"duckhop-{DUCKDB}-extension-linux_amd64" / "duckhop.duckdb_extension"
        data = bytearray(path.read_bytes())
        data[-352:-342] = CI_TOOLS[:10].encode()
        path.write_bytes(data)
        with self.assertRaisesRegex(ValueError, "DuckDB ABI revision"):
            self.package()
        self.assertFalse(self.output.exists())

    def test_rejects_binary_with_wrong_extension_version(self):
        path = self.artifacts / f"duckhop-{DUCKDB}-extension-linux_amd64" / "duckhop.duckdb_extension"
        data = bytearray(path.read_bytes())
        data[-384:-352] = b"v0.0.0".ljust(32, b"\0")
        path.write_bytes(data)
        with self.assertRaisesRegex(ValueError, "extension version"):
            self.package()

    def test_accepts_version_that_fills_metadata_field(self):
        tag = "v1.0.0-" + "a" * 25
        release.validate_tag(tag)
        path = self.root / "duckhop.duckdb_extension"
        binary(path, "linux_amd64", tag)
        release.validate_binary(path, "linux_amd64", DUCKDB, tag)

    def test_rejects_truncated_extension_version(self):
        tag = "v1.0.0-" + "a" * 26
        path = self.root / "duckhop.duckdb_extension"
        binary(path, "linux_amd64", tag)
        with self.assertRaisesRegex(ValueError, "extension version"):
            release.validate_binary(path, "linux_amd64", DUCKDB, tag)

    def test_rejects_c_api_binary(self):
        path = self.artifacts / f"duckhop-{DUCKDB}-extension-linux_amd64" / "duckhop.duckdb_extension"
        data = bytearray(path.read_bytes())
        data[-416:-384] = b"C_STRUCT".ljust(32, b"\0")
        path.write_bytes(data)
        with self.assertRaisesRegex(ValueError, r"C\+\+ ABI"):
            self.package()

    def test_rejects_modified_binary_before_publication(self):
        self.package()
        path = self.output / release.asset_names(TAG)["linux_amd64"]
        data = bytearray(path.read_bytes())
        data[0] ^= 1
        path.write_bytes(data)
        with self.assertRaisesRegex(ValueError, "checksum"):
            release.verify_local(TAG, REVISION, self.output)

    def test_rejects_extra_asset_and_modified_checksum_manifest(self):
        self.package()
        extra = self.output / "extra.txt"
        extra.write_text("Unexpected asset.")
        with self.assertRaisesRegex(ValueError, "exactly"):
            release.verify_local(TAG, REVISION, self.output)
        extra.unlink()
        (self.output / "SHA256SUMS").write_text("")
        with self.assertRaisesRegex(ValueError, "checksum manifest"):
            release.verify_local(TAG, REVISION, self.output)


class PublicationTests(unittest.TestCase):
    def setUp(self):
        self.temporary = tempfile.TemporaryDirectory()
        self.addCleanup(self.temporary.cleanup)
        self.path = Path(self.temporary.name) / "asset"
        self.path.write_bytes(b"verified bytes")
        self.files = {"asset": self.path}
        self.asset = {
            "name": "asset", "state": "uploaded", "size": self.path.stat().st_size,
            "digest": f"sha256:{release.digest(self.path)}",
        }
        self.draft = {"id": 1, "draft": True, "prerelease": True, "immutable": False}
        self.published = {**self.draft, "draft": False, "immutable": True}
        for name, value in (("verify_local", self.files), ("remote_revision", REVISION)):
            patch = mock.patch.object(release, name, return_value=value)
            patch.start()
            self.addCleanup(patch.stop)

    def test_creates_the_correct_draft_before_uploading_and_publishing(self):
        for tag in ("v0.1.0", TAG):
            with self.subTest(tag=tag):
                draft = {**self.draft, "prerelease": "-" in tag}
                with (
                    mock.patch.object(release, "find_release", side_effect=[None, draft, draft]),
                    mock.patch.object(release, "remote_assets", side_effect=[[], [self.asset]]),
                    mock.patch.object(release, "run") as command,
                ):
                    release.publish("ofek/duckhop", tag, REVISION, self.path.parent)
                calls = command.call_args_list
                self.assertEqual([call.args[2] for call in calls], ["create", "upload", "edit"])
                self.assertEqual(calls[0].args, (
                    "gh", "release", "create", tag, "--repo", "ofek/duckhop", "--draft", "--verify-tag",
                    "--target", REVISION, "--title", tag, "--generate-notes",
                    *(("--prerelease",) if "-" in tag else ()),
                ))

    def test_rejects_a_draft_with_the_wrong_prerelease_setting(self):
        with (
            mock.patch.object(release, "find_release", return_value=self.draft),
            mock.patch.object(release, "run") as command,
        ):
            with self.assertRaisesRegex(ValueError, "prerelease setting"):
                release.publish("ofek/duckhop", "v0.1.0", REVISION, self.path.parent)
        command.assert_not_called()

    def test_uploads_missing_assets_before_publishing(self):
        with (
            mock.patch.object(release, "find_release", return_value=self.draft),
            mock.patch.object(release, "remote_assets", side_effect=[[], [self.asset]]),
            mock.patch.object(release, "run") as command,
        ):
            release.publish("ofek/duckhop", TAG, REVISION, self.path.parent)
        self.assertEqual(command.call_args_list[0].args[2], "upload")
        self.assertEqual(command.call_args_list[1].args[2], "edit")
        self.assertIn("--draft=false", command.call_args_list[1].args)
        self.assertNotIn("--clobber", str(command.call_args_list))

    def test_published_release_is_never_modified(self):
        with (
            mock.patch.object(release, "find_release", return_value=self.published),
            mock.patch.object(release, "remote_assets", return_value=[self.asset]),
            mock.patch.object(release, "run") as command,
        ):
            release.publish("ofek/duckhop", TAG, REVISION, self.path.parent)
        command.assert_not_called()

    def test_incomplete_upload_never_publishes(self):
        with (
            mock.patch.object(release, "find_release", return_value=self.draft),
            mock.patch.object(release, "remote_assets", return_value=[]),
            mock.patch.object(release, "run") as command,
        ):
            with self.assertRaisesRegex(ValueError, "complete"):
                release.publish("ofek/duckhop", TAG, REVISION, self.path.parent)
        self.assertEqual(len(command.call_args_list), 1)
        self.assertEqual(command.call_args.args[2], "upload")

    def test_draft_with_different_asset_digest_is_never_modified(self):
        with (
            mock.patch.object(release, "find_release", return_value=self.draft),
            mock.patch.object(release, "remote_assets", return_value=[{**self.asset, "digest": "sha256:bad"}]),
            mock.patch.object(release, "run") as command,
        ):
            with self.assertRaisesRegex(ValueError, "does not match"):
                release.publish("ofek/duckhop", TAG, REVISION, self.path.parent)
        command.assert_not_called()

    def test_tag_move_prevents_publication(self):
        with (
            mock.patch.object(release, "find_release", return_value=self.draft),
            mock.patch.object(release, "remote_assets", return_value=[self.asset]),
            mock.patch.object(release, "remote_revision", side_effect=[REVISION, DUCKDB]),
            mock.patch.object(release, "run") as command,
        ):
            with self.assertRaisesRegex(ValueError, "tag moved"):
                release.publish("ofek/duckhop", TAG, REVISION, self.path.parent)
        command.assert_not_called()

    def test_rejects_unexpected_or_duplicate_remote_assets(self):
        for assets in ([self.asset, self.asset], [{**self.asset, "name": "unexpected"}]):
            with self.subTest(assets=assets), self.assertRaises(ValueError):
                release.verify_assets(assets, self.files, complete=True)

    def test_verifies_immutable_release_and_each_asset_attestation(self):
        with (
            mock.patch.object(release, "find_release", return_value=self.published),
            mock.patch.object(release, "remote_assets", return_value=[self.asset]),
            mock.patch.object(release, "run") as command,
        ):
            release.verify("ofek/duckhop", TAG, REVISION, self.path.parent)
        self.assertEqual([call.args[2] for call in command.call_args_list], ["verify", "verify-asset"])


if __name__ == "__main__":
    unittest.main()

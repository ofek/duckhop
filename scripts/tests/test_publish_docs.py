"""Check that documentation publication accepts only generated main-branch output."""

import os
from pathlib import Path
import tempfile
import unittest
from unittest import mock

from scripts import publish_docs


class DocumentationPublicationTests(unittest.TestCase):
    def setUp(self):
        self.temporary = tempfile.TemporaryDirectory()
        self.addCleanup(self.temporary.cleanup)
        self.site = Path(self.temporary.name)
        (self.site / "index.html").write_text("<html><title>DuckHop</title></html>")

    def test_rejects_custom_domain_override(self):
        (self.site / "CNAME").write_text("ofek.dev")
        with self.assertRaisesRegex(ValueError, "CNAME"):
            publish_docs.validate_site(self.site)

    def test_rejects_git_metadata(self):
        (self.site / ".git").mkdir()
        with self.assertRaisesRegex(ValueError, "Git metadata"):
            publish_docs.validate_site(self.site)

    def test_rejects_output_without_homepage(self):
        (self.site / "index.html").unlink()
        with self.assertRaisesRegex(ValueError, "Build the documentation"):
            publish_docs.validate_site(self.site)

    def test_rejects_non_main_branch_before_running_git(self):
        with (
            mock.patch.dict(os.environ, {"GITHUB_ACTIONS": "true", "GITHUB_REF": "refs/heads/topic"}),
            mock.patch.object(publish_docs.subprocess, "run") as command,
        ):
            with self.assertRaisesRegex(ValueError, "main-branch"):
                publish_docs.publish(self.site)
        command.assert_not_called()

    def test_rerun_records_checkout_revision_instead_of_stale_event_revision(self):
        event_revision = "a" * 40
        source_revision = "b" * 40
        generated_revision = "c" * 40

        def git_result(arguments, **_kwargs):
            return mock.Mock(stdout=generated_revision if arguments[1:] == ["rev-parse", "HEAD"] else "")

        with (
            mock.patch.dict(os.environ, {
                "GITHUB_ACTIONS": "true", "GITHUB_REF": "refs/heads/main",
                "GITHUB_REPOSITORY": "ofek/duckhop", "GITHUB_SHA": event_revision,
                "GITHUB_TOKEN": "test-token",
            }),
            mock.patch.object(publish_docs.subprocess, "check_output", return_value=source_revision),
            mock.patch.object(publish_docs.subprocess, "run", side_effect=git_result) as command,
            mock.patch.object(publish_docs, "pages_api", return_value={
                "build_type": "legacy", "source": {"branch": "gh-pages", "path": "/"},
            }),
            mock.patch.object(publish_docs, "request_build") as build,
        ):
            publish_docs.publish(self.site)
        commits = [call.args[0] for call in command.call_args_list if "commit" in call.args[0]]
        self.assertEqual(len(commits), 1)
        self.assertEqual(commits[0][-2:], ["--message", f"docs: publish {source_revision}"])
        build.assert_called_once_with("ofek/duckhop", mock.ANY, generated_revision)

    def test_existing_branch_preserves_history_and_pushes_only_changed_output(self):
        revision = "a" * 40
        for changed in (False, True):
            with self.subTest(changed=changed):
                def git_result(arguments, **_kwargs):
                    if arguments[1] == "ls-remote":
                        return mock.Mock(stdout=f"{revision}\trefs/heads/gh-pages")
                    if arguments[1] == "diff":
                        return mock.Mock(stdout="index.html" if changed else "")
                    return mock.Mock(stdout=revision if arguments[1] == "rev-parse" else "")

                with (
                    mock.patch.dict(os.environ, {
                        "GITHUB_ACTIONS": "true", "GITHUB_REF": "refs/heads/main",
                        "GITHUB_REPOSITORY": "ofek/duckhop", "GITHUB_TOKEN": "test-token",
                    }),
                    mock.patch.object(publish_docs.subprocess, "check_output", return_value=revision),
                    mock.patch.object(publish_docs.subprocess, "run", side_effect=git_result) as command,
                    mock.patch.object(publish_docs, "pages_api", return_value={
                        "build_type": "legacy", "source": {"branch": "gh-pages", "path": "/"},
                    }),
                    mock.patch.object(publish_docs, "request_build") as build,
                ):
                    publish_docs.publish(self.site)
                commands = [call.args[0][1:] for call in command.call_args_list]
                self.assertIn(["fetch", "--depth=1", "origin", "refs/heads/gh-pages"], commands)
                self.assertIn(["reset", "--soft", "FETCH_HEAD"], commands)
                self.assertEqual(any("commit" in arguments for arguments in commands), changed)
                self.assertEqual(["push", "origin", "HEAD:refs/heads/gh-pages"] in commands, changed)
                build.assert_called_once_with("ofek/duckhop", mock.ANY, revision)

    def test_requires_branch_publishing_from_generated_root(self):
        for settings in (
            {"build_type": "workflow", "source": {"branch": "gh-pages", "path": "/"}},
            {"build_type": "legacy", "source": {"branch": "main", "path": "/"}},
            {"build_type": "legacy", "source": {"branch": "gh-pages", "path": "/docs"}},
        ):
            with self.subTest(settings=settings), self.assertRaisesRegex(ValueError, "branch root"):
                publish_docs.validate_pages_settings(settings)

    def test_build_confirmation_must_match_generated_commit(self):
        revision = "a" * 40
        with (
            mock.patch.object(publish_docs, "pages_api", side_effect=[
                {}, {"commit": "b" * 40, "status": "built"},
                {"commit": revision, "status": "building"}, {"commit": revision, "status": "built"},
            ]) as api,
            mock.patch.object(publish_docs.time, "sleep") as sleep,
        ):
            publish_docs.request_build("ofek/duckhop", {}, revision)
        self.assertEqual(api.call_args_list[0].kwargs, {"method": "POST"})
        self.assertEqual(sleep.call_count, 2)

    def test_failed_build_is_reported(self):
        revision = "a" * 40
        with mock.patch.object(publish_docs, "pages_api", side_effect=[
            {}, {"commit": revision, "status": "errored", "error": {"message": "Failed."}},
        ]):
            with self.assertRaisesRegex(ValueError, "Failed"):
                publish_docs.request_build("ofek/duckhop", {}, revision)


if __name__ == "__main__":
    unittest.main()

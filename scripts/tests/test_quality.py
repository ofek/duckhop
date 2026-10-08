"""Verify that prose exceptions preserve nearby grammar and spelling findings."""

import contextlib
import io
import json
from pathlib import Path
import subprocess
import tempfile
import unittest
from unittest.mock import patch

from scripts import quality


class VocabularyTests(unittest.TestCase):
    def vale(self, source):
        return subprocess.run(
            [
                "vale", "--config", str(quality.ROOT / ".vale.ini"), "--no-global",
                "--output=JSON", "--ext=.md", "--path=vocabulary-test.md",
            ],
            input=source, capture_output=True, text=True, encoding="utf-8", cwd=quality.ROOT,
        )

    def test_canonical_names_and_ordinary_word_capitalization_are_accepted(self):
        result = self.vale(
            "DuckDB and DuckHop use GitHub Actions on Windows, Linux, and macOS with mise.\n\n"
            "Reachability and reachability are graph terms. CI uses extension-ci-tools.\n"
        )
        self.assertEqual(result.returncode, 0, result.stdout + result.stderr)

    def test_capitalization_variants_are_detected_without_variant_rules(self):
        variants = ("Duckdb", "duckDB", "DUCKDB", "duckhop", "DuckHOP", "Github", "GITHUB", "MacOS", "Mise", "MISE")
        result = self.vale("\n\n".join(f"Use {word} here." for word in variants))
        self.assertEqual(result.returncode, 1, result.stdout + result.stderr)
        alerts = json.loads(result.stdout)["vocabulary-test.md"]
        self.assertEqual({alert["Match"] for alert in alerts}, set(variants))
        self.assertTrue(all(alert["Check"] == "Vale.Terms" for alert in alerts))

    def test_spelling_remains_harpers_responsibility(self):
        result = self.vale("We check dependancies.\n")
        self.assertEqual(result.returncode, 0, result.stdout + result.stderr)

    def test_lowercase_ci_is_only_accepted_inside_the_canonical_dependency_name(self):
        result = self.vale("CI uses extension-ci-tools.\n\nWe run ci checks.\n")
        alerts = json.loads(result.stdout)["vocabulary-test.md"]
        self.assertEqual(result.returncode, 1, result.stdout + result.stderr)
        self.assertEqual(len(alerts), 1)
        self.assertEqual(alerts[0]["Match"], "ci")
        self.assertEqual(alerts[0]["Line"], 3)

    def test_harper_dictionary_preserves_names_and_removes_vale_annotations(self):
        words = quality.harper_dictionary().splitlines()
        self.assertIn("DuckDB", words)
        self.assertIn("DuckDB's", words)
        self.assertIn("reachability", words)
        self.assertIn("extension-ci-tools", words)
        self.assertIn("ci", words)
        self.assertFalse(any(word.startswith(("# ", "(?i)")) for word in words))

    def test_unsupported_vocabulary_patterns_fail_instead_of_becoming_words(self):
        with tempfile.TemporaryDirectory() as directory:
            root = Path(directory)
            (root / ".vale.ini").write_text("StylesPath = .config/prose\nVocab = DuckHop\n", encoding="utf-8")
            vocabulary = root / ".config/prose/config/vocabularies/DuckHop/accept.txt"
            vocabulary.parent.mkdir(parents=True)
            vocabulary.write_text("[Rr]eachability\n", encoding="utf-8")
            with patch.object(quality, "ROOT", root):
                with self.assertRaisesRegex(ValueError, "literal words or phrases"):
                    quality.harper_dictionary()


class KeyboardShortcutTests(unittest.TestCase):
    def lint(self, source, word="ctrl", rule="ExpandControl"):
        start = source.index(word)
        return {"rule": rule, "span": {"char_start": start, "char_end": start + len(word)}}

    def test_control_key_advice_is_excluded_inside_complete_shortcuts(self):
        source = "Press ++ctrl+c++."
        self.assertTrue(quality.keyboard_shortcut(self.lint(source), source))

    def test_abbreviations_outside_shortcuts_are_still_reported(self):
        source = "Use ctrl or press ++ctrl+c++."
        self.assertFalse(quality.keyboard_shortcut(self.lint(source), source))

    def test_incomplete_shortcuts_are_still_checked(self):
        source = "Press ++ctrl+c."
        self.assertFalse(quality.keyboard_shortcut(self.lint(source), source))

    def test_other_rules_inside_shortcuts_are_still_reported(self):
        source = "Press ++ctrl+c++."
        self.assertFalse(quality.keyboard_shortcut(self.lint(source, rule="SpellCheck"), source))

    def test_shortcut_spans_use_characters_after_unicode_text(self):
        source = "Diátaxis: press ++ctrl+c++."
        self.assertTrue(quality.keyboard_shortcut(self.lint(source), source))


class HarperTests(unittest.TestCase):
    def test_filtered_shortcuts_do_not_hide_grammar_findings(self):
        source = "Press ++ctrl+c++. There is bugs."
        findings = [
            {
                "rule": "ExpandControl",
                "span": {"char_start": 8, "char_end": 12},
                "line": 1, "column": 9, "message": "Expand ctrl.",
            },
            {
                "rule": "ThereIsAgreement",
                "span": {"char_start": 23, "char_end": 25},
                "line": 1, "column": 24, "message": "Check agreement.",
            },
        ]
        result = subprocess.CompletedProcess([], 1, json.dumps([{"lints": findings}]), "")
        with tempfile.TemporaryDirectory() as directory:
            root = Path(directory)
            (root / "probe.md").write_text(source, encoding="utf-8")
            output = io.StringIO()
            with patch.object(quality, "ROOT", root), patch.object(quality, "harper_dictionary", return_value="DuckDB\n"), patch.object(quality.subprocess, "run", return_value=result), contextlib.redirect_stdout(output):
                self.assertEqual(quality.harper(["probe.md"]), 1)
        self.assertIn("probe.md:1:24: ThereIsAgreement", output.getvalue())
        self.assertNotIn("ExpandControl", output.getvalue())

    def test_missing_file_results_do_not_pass_the_gate(self):
        result = subprocess.CompletedProcess([], 1, "[]", "Could not read input.")
        with tempfile.TemporaryDirectory() as directory:
            root = Path(directory)
            (root / "probe.md").write_text("A sentence.", encoding="utf-8")
            with patch.object(quality, "ROOT", root), patch.object(quality, "harper_dictionary", return_value="DuckDB\n"), patch.object(quality.subprocess, "run", return_value=result):
                with self.assertRaisesRegex(RuntimeError, "Expected one Harper result"):
                    quality.harper(["probe.md"])

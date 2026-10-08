"""Keep the upstream distribution environment compatible with DuckHop."""

import json
import os
from pathlib import Path
import shutil
import subprocess
import sys
import tempfile
import unittest


ROOT = Path(__file__).resolve().parents[2]
MAKE = shutil.which("gmake") or shutil.which("make")


@unittest.skipUnless(MAKE, "The official distribution Makefile check requires GNU make.")
class DistributionEnvironmentTests(unittest.TestCase):
    def setUp(self):
        self.temporary = tempfile.TemporaryDirectory(prefix="duckhop-make-")
        self.addCleanup(self.temporary.cleanup)
        self.root = Path(self.temporary.name)
        shutil.copyfile(ROOT / "Makefile", self.root / "Makefile")
        duckdb = self.root / "duckdb"
        duckdb.mkdir()
        subprocess.run(["git", "init", "--quiet"], cwd=duckdb, check=True)
        subprocess.run(
            ["git", "-c", "core.hooksPath=" + str(self.root / "empty-hooks"),
             "-c", "user.name=Fixture", "-c", "user.email=fixture@example.invalid", "-c", "commit.gpgsign=false",
             "commit", "--quiet", "--allow-empty", "--message=Fixture"],
            cwd=duckdb, check=True,
        )
        self.revision = subprocess.check_output(
            ["git", "rev-parse", "HEAD"], cwd=duckdb, text=True,
        ).strip()
        tools = self.root / "extension-ci-tools" / "makefiles"
        tools.mkdir(parents=True)
        (tools / "duckdb_extension.Makefile").write_text(
            '.PHONY: probe\nprobe:\n\t@"$(FIXTURE_PYTHON)" probe.py\n', encoding="utf-8"
        )
        (self.root / "probe.py").write_text(
            "import json, os\n"
            "print(json.dumps({key: os.environ.get(key) for key in "
            "('DUCKDB_VERSION', 'DUCKDB_GIT_VERSION')}))\n",
            encoding="utf-8",
        )

    def environment(self, version):
        environment = os.environ.copy()
        environment.update({
            "DUCKDB_VERSION": version,
            "DUCKDB_GIT_VERSION": self.revision,
            "FIXTURE_PYTHON": Path(sys.executable).as_posix(),
        })
        output = subprocess.check_output(
            [MAKE, "--no-print-directory", "--silent", "probe"],
            cwd=self.root, env=environment, text=True,
        )
        return json.loads(output)

    def test_checkout_sha_is_unexported_but_checkout_reference_survives(self):
        self.assertEqual(self.environment(self.revision), {
            "DUCKDB_VERSION": None, "DUCKDB_GIT_VERSION": self.revision,
        })

    def test_semantic_version_is_preserved(self):
        self.assertEqual(self.environment("v2.0.0"), {
            "DUCKDB_VERSION": "v2.0.0", "DUCKDB_GIT_VERSION": self.revision,
        })

    def test_distribution_build_does_not_enable_an_unused_vcpkg_toolchain(self):
        include = "extension-ci-tools/makefiles/duckdb_extension.Makefile"
        shutil.copyfile(ROOT / include, self.root / include)
        environment = os.environ.copy()
        environment["VCPKG_TOOLCHAIN_PATH"] = str(self.root / "unused-vcpkg.cmake")
        commands = subprocess.check_output(
            [MAKE, "--no-print-directory", "--dry-run", "release"],
            cwd=self.root, env=environment, text=True,
        )
        self.assertIn("-DCMAKE_BUILD_TYPE=Release", commands)
        for option in ("-DCMAKE_TOOLCHAIN_FILE", "-DVCPKG_BUILD", "-DVCPKG_MANIFEST_DIR"):
            with self.subTest(option=option):
                self.assertNotIn(option, commands)


if __name__ == "__main__":
    unittest.main()

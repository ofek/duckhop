"""Keep CMake interpreter paths valid after isolated workflow environments exit."""

from pathlib import Path
import tempfile
import unittest
from unittest.mock import patch

from scripts import build


class BuildInterpreterTests(unittest.TestCase):
    def test_cmake_records_the_project_environment_interpreter(self):
        with tempfile.TemporaryDirectory() as directory:
            root = Path(directory)
            output = root / "build/debug"
            artifact = output / "extension/duckhop/duckhop.duckdb_extension"
            artifact.parent.mkdir(parents=True)
            artifact.touch()
            (output / "compile_commands.json").write_text("[]", encoding="utf-8")
            with patch.object(build, "ROOT", root), patch.object(build, "require_submodules"), patch.object(build, "native_environment", return_value={"DUCKHOP_NO_CACHE": "1"}), patch.object(build, "tool", side_effect=lambda name: f"managed-{name}"), patch.object(build.sys, "executable", "temporary-python"), patch.object(build, "output", return_value="project-venv-python") as resolve, patch.object(build, "run") as run:
                build.build("debug")
            resolve.assert_called_once_with([
                "managed-uv", "run", "--no-active", "--no-sync", "--offline",
                "python", "-c", "import sys; print(sys.executable)",
            ])
            configure = run.call_args_list[0].args[0]
            self.assertIn("-DPython3_EXECUTABLE=project-venv-python", configure)
            self.assertNotIn("-DPython3_EXECUTABLE=temporary-python", configure)

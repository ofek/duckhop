"""Adapt DuckDB's native build and test commands to the contributor's platform."""

from __future__ import annotations

import argparse
import json
import os
from pathlib import Path
import platform
import shlex
import shutil
import subprocess
import sys
import tempfile

from scripts.release import asset_names


ROOT = Path(__file__).resolve().parents[1]


def tool(name: str) -> str:
    return subprocess.check_output(["mise", "which", name], cwd=ROOT, text=True).strip()


def run(arguments: list[str], *, env: dict[str, str] | None = None) -> None:
    if arguments[0] == "uv":
        arguments = [tool("uv"), *arguments[1:]]
    print("+ " + subprocess.list2cmdline(arguments), flush=True)
    subprocess.run(arguments, cwd=ROOT, env=env, check=True)


def output(arguments: list[str], *, env: dict[str, str] | None = None) -> str:
    return subprocess.check_output(
        arguments, cwd=ROOT, env=env, text=True, encoding="utf-8", errors="replace"
    ).strip()


def native_environment() -> dict[str, str]:
    env = os.environ.copy()
    if os.name != "nt":
        return env
    if shutil.which("cl", path=env.get("PATH")) and env.get("INCLUDE") and env.get("LIB"):
        return env

    installer = Path(env.get("ProgramFiles(x86)", r"C:\Program Files (x86)"))
    vswhere = installer / "Microsoft Visual Studio/Installer/vswhere.exe"
    if not vswhere.is_file():
        raise RuntimeError(
            "Install Visual Studio 2022 Build Tools with Desktop development with C++ and a Windows SDK."
        )
    installation = output(
        [
            str(vswhere),
            "-latest",
            "-products",
            "*",
            "-requires",
            "Microsoft.VisualStudio.Component.VC.Tools.x86.x64",
            "-property",
            "installationPath",
        ]
    )
    if not installation:
        raise RuntimeError(
            "Add Desktop development with C++ and a Windows SDK in Visual Studio Installer."
        )
    script = Path(installation) / "VC/Auxiliary/Build/vcvarsall.bat"
    command = f'"{script}" x64 >nul && set'
    result = subprocess.run(
        command,
        shell=True,
        executable=env.get("COMSPEC", "cmd.exe"),
        cwd=ROOT,
        env=env,
        capture_output=True,
        text=True,
        check=True,
    )
    for line in result.stdout.splitlines():
        name, separator, value = line.partition("=")
        if separator and name:
            env[name.upper()] = value
    if not shutil.which("cl", path=env.get("PATH")):
        raise RuntimeError("Visual Studio's developer environment did not provide the MSVC compiler.")
    return env


def require_submodules() -> None:
    status = output(["git", "submodule", "status", "--recursive"])
    if not status or any(line[0] in "-+U" for line in status.splitlines()):
        raise RuntimeError("Pinned submodules are missing or differ from the checkout. Run mise run setup.")
    for name in ("duckdb", "extension-ci-tools"):
        if not (ROOT / name / "CMakeLists.txt").is_file() and name == "duckdb":
            raise RuntimeError("The DuckDB submodule is missing. Run mise run setup.")
        revision = output(["git", "-C", name, "rev-parse", "HEAD"])
        print(f"{name}: {revision}", flush=True)


def setup() -> None:
    run(["git", "submodule", "sync", "--recursive"])
    run(["git", "submodule", "update", "--init", "--recursive"])
    run(["uv", "sync", "--locked"])


def doctor() -> None:
    print(f"Platform: {platform.system()} {platform.release()} ({platform.machine()})")
    for executable in ("mise", "git", "cmake", "ninja", "uv"):
        if not shutil.which(executable):
            raise RuntimeError(f"{executable} is missing. Install Git and mise, then run mise install --locked.")
        binary = executable if executable in ("mise", "git") else tool(executable)
        print(output([binary, "--version"]).splitlines()[0])
    print(f"Python: {platform.python_version()} ({sys.executable})")
    tools = json.loads(output(["mise", "ls", "--json"]))
    for name, versions in tools.items():
        for version in versions:
            source = version.get("source", {}).get("path")
            if source and Path(source).resolve() == ROOT / "mise.toml":
                if not version.get("installed"):
                    raise RuntimeError(f"{name} {version['version']} is missing. Run mise install --locked.")
                print(f"Locked tool: {name} {version['version']}")
    require_submodules()
    env = native_environment()
    compiler_name = "cl" if os.name == "nt" else (env.get("CXX") or "c++")
    compiler = shutil.which(compiler_name, path=env.get("PATH"))
    if not compiler:
        raise RuntimeError("Install your platform's C/C++ compiler and SDK, then rerun mise run doctor.")
    identity = subprocess.run(
        [compiler, "/Bv"] if os.name == "nt" else [compiler, "--version"],
        cwd=ROOT,
        env=env,
        capture_output=True,
        text=True,
    )
    print((identity.stdout + identity.stderr).strip().splitlines()[0])
    run(["uv", "sync", "--locked", "--offline", "--check"])


def build(config: str) -> None:
    require_submodules()
    env = native_environment()
    directory = ROOT / "build" / config
    cmake = [
        tool("cmake"),
        "-S",
        str(ROOT / "duckdb"),
        "-B",
        str(directory),
        "-G",
        "Ninja",
        f"-DCMAKE_MAKE_PROGRAM={tool('ninja')}",
        f"-DCMAKE_BUILD_TYPE={config.title()}",
        "-DCMAKE_CXX_STANDARD=17",
        f"-DPython3_EXECUTABLE={sys.executable}",
        f"-DDUCKDB_EXTENSION_CONFIGS={(ROOT / 'extension_config.cmake').as_posix()}",
        f"-DUNITTEST_ROOT_DIRECTORY={ROOT.as_posix()}",
        "-DBUILD_SHELL=ON",
        "-DBUILD_UNITTESTS=ON",
        "-DENABLE_UNITTEST_CPP_TESTS=OFF",
        "-DEXTENSION_STATIC_BUILD=ON",
        "-DENABLE_SANITIZER=OFF",
        "-DENABLE_UBSAN=OFF",
    ]
    if os.name == "nt":
        # Embedded debug data avoids shared PDB contention and permits compiler caching.
        cmake.append("-DCMAKE_MSVC_DEBUG_INFORMATION_FORMAT=Embedded")
        cmake.append("-DFORCE_DEBUG=OFF")
        if config == "debug":
            # This DuckDB prerelease's DEBUG-only LLDB helpers do not compile with MSVC.
            # Keep an unoptimized symbol build while disabling assertions that reference those helpers.
            cmake.append("-DCMAKE_CXX_FLAGS_DEBUG=/Ob0 /Od /RTC1 /DNDEBUG")
    if env.get("DUCKHOP_NO_CACHE") == "1":
        cmake.extend(["-DCMAKE_C_COMPILER_LAUNCHER=", "-DCMAKE_CXX_COMPILER_LAUNCHER="])
    elif shutil.which("sccache", path=env.get("PATH")):
        cache = tool("sccache")
        cmake.extend([f"-DCMAKE_C_COMPILER_LAUNCHER={cache}", f"-DCMAKE_CXX_COMPILER_LAUNCHER={cache}"])
    run(cmake, env=env)
    jobs = env.get("CMAKE_BUILD_PARALLEL_LEVEL", str(min(os.cpu_count() or 2, 8)))
    targets = ["duckhop_extension", "duckhop_loadable_extension", "shell", "unittest"]
    if os.name != "nt":
        targets.append("clangd_cache")
    # DuckDB's default target also links unrelated demo binaries and their large debug databases.
    run([cmake[0], "--build", str(directory), "--target", *targets, "--parallel", jobs], env=env)
    if os.name == "nt":
        # DuckDB updates this editor cache itself on Unix, but not on Windows.
        cache = ROOT / ".cache/clangd"
        cache.mkdir(parents=True, exist_ok=True)
        shutil.copyfile(directory / "compile_commands.json", cache / "compile_commands.json")
    artifact = directory / "extension/duckhop/duckhop.duckdb_extension"
    if not artifact.is_file():
        raise RuntimeError(f"The build did not produce {artifact}.")
    print(f"Extension: {artifact}")


def test(config: str) -> None:
    directory = ROOT / "build" / config
    suffix = ".exe" if os.name == "nt" else ""
    runner = directory / "test" / f"unittest{suffix}"
    shell = directory / f"duckdb{suffix}"
    artifact = directory / "extension/duckhop/duckhop.duckdb_extension"
    if not runner.is_file() or not shell.is_file() or not artifact.is_file():
        raise RuntimeError(f"Build artifacts are missing. Run mise run build:{config} first.")
    flags = shlex.join(["--temp-dir-root", (directory / "test-tmp").as_posix()])
    run(
        [
            sys.executable,
            str(ROOT / "duckdb/scripts/ci/run_tests.py"),
            str(runner),
            "test/sql/*",
            f"--test-flags={flags}",
        ]
    )
    with tempfile.TemporaryDirectory(prefix="duckhop-distribution-") as temporary:
        for tag in ("v0.1.0", "v0.1.0-rc.1"):
            for name in asset_names(tag).values():
                binary = Path(temporary) / name
                shutil.copyfile(artifact, binary)
                path = binary.as_posix().replace("'", "''")
                run([str(shell), "-no-init", "-unsigned", "-c", f"LOAD '{path}';"])


def tidy(config: str) -> None:
    directory = ROOT / "build" / config
    database = directory / "compile_commands.json"
    if not database.is_file():
        raise RuntimeError(f"The compilation database is missing. Run mise run build:{config} first.")
    entries = json.loads(database.read_text(encoding="utf-8"))
    sources = sorted({Path(entry["file"]).resolve() for entry in entries})
    owned = [source for source in sources if source.is_relative_to(ROOT / "src")]
    if not owned:
        raise RuntimeError("The compilation database contains no DuckHop sources. Rebuild the extension.")
    env = native_environment()
    for source in owned:
        run(["uv", "run", "--no-sync", "--offline", "clang-tidy", "-p", str(directory), str(source)], env=env)


def clean() -> None:
    for relative in ("build", ".cache/clangd", "site"):
        target = ROOT / relative
        resolved = target.resolve()
        if resolved == ROOT or not resolved.is_relative_to(ROOT):
            raise RuntimeError(f"Refusing to remove a path outside the repository: {resolved}")
        if target.is_symlink():
            raise RuntimeError(f"Refusing to remove a symbolic link: {target}")
        if target.exists():
            print(f"Removing {target}")
            shutil.rmtree(target)


def main() -> None:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("command", choices=("setup", "doctor", "build", "test", "tidy", "clean"))
    parser.add_argument("--config", choices=("debug", "release"), default="debug")
    arguments = parser.parse_args()
    actions = {"setup": setup, "doctor": doctor, "clean": clean}
    if arguments.command in actions:
        actions[arguments.command]()
    else:
        {"build": build, "test": test, "tidy": tidy}[arguments.command](arguments.config)


if __name__ == "__main__":
    try:
        main()
    except (OSError, RuntimeError, subprocess.CalledProcessError) as error:
        print(f"error: {error}", file=sys.stderr)
        sys.exit(1)

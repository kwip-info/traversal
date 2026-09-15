"""Validate the installed native distribution and its shipped skill."""

import importlib.machinery
import importlib.resources
import runpy
from importlib.metadata import version

import traversal
from packaging.version import Version
from traversal import _native


def test_native_core_matches_distribution():
    assert any(_native.__file__.endswith(s) for s in importlib.machinery.EXTENSION_SUFFIXES)
    assert Version(_native.__version__) == Version(version("traversal"))
    assert traversal.__version__ == version("traversal")


def test_shipped_skill_example(capsys):
    skill = importlib.resources.files("traversal").joinpath("skills/traversal")
    assert skill.joinpath("SKILL.md").is_file()
    assert skill.joinpath("references/semantics.md").is_file()
    with importlib.resources.as_file(skill.joinpath("scripts/check_install.py")) as script:
        runpy.run_path(str(script), run_name="__main__")
    assert "native core loaded" in capsys.readouterr().out


def test_shipped_quickstart(capsys):
    skill = importlib.resources.files("traversal").joinpath("skills/traversal")
    with importlib.resources.as_file(skill.joinpath("scripts/quickstart.py")) as script:
        runpy.run_path(str(script), run_name="__main__")
    assert "total = 18" in capsys.readouterr().out


def test_shipped_history_example(capsys):
    skill = importlib.resources.files("traversal").joinpath("skills/traversal")
    with importlib.resources.as_file(skill.joinpath("scripts/history_example.py")) as script:
        runpy.run_path(str(script), run_name="__main__")
    assert "explicit reuse verified" in capsys.readouterr().out


def test_skill_export_and_no_overwrite(tmp_path):
    import subprocess
    import sys

    destination = tmp_path / "skill"
    command = [sys.executable, "-m", "traversal", "skill", "--output", str(destination)]
    subprocess.run(command, check=True, capture_output=True)
    assert (destination / "references/history.md").is_file()
    assert (destination / "scripts/history_example.py").is_file()
    result = subprocess.run(command, capture_output=True, check=False)
    assert result.returncode != 0

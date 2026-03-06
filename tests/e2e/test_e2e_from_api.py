from pathlib import Path

import pytest

from pythinfer import Project

PROJECT_ROOT = Path(__file__).parent.parent.parent

def test_eg0_basic() -> None:
    """Test that we can run the example project.

    Don't rely on default project file existing because it is changed in other tests.
    """
    project_path = (
        PROJECT_ROOT / "example_projects" / "eg0-basic" / "expected_pythinfer.yaml"
    )
    project = Project.load(project_path)

    project.merge()
    project.infer()

def test_no_project_file(monkeypatch: pytest.MonkeyPatch, tmp_path: Path) -> None:
    """Test that we can load a project without specifying a config file.

    This should discover the nearest pythinfer.yaml, and if none is found, create
    a new project in the current directory by scanning for RDF files.
    """
    monkeypatch.chdir(tmp_path)
    with pytest.raises(FileNotFoundError, match="No such file"):
        Project.load(tmp_path / "nonexistent.yaml")
    with pytest.raises(FileNotFoundError, match="No RDF files found"):
        Project.load()

    ttl_file = tmp_path / "example.ttl"
    ttl_file.write_text( "# Empty.", encoding="utf-8")

    # Create a new project by scanning for RDF files (should create pythinfer.yaml)
    project = Project.load()
    assert project is not None
    assert project.path_self == tmp_path / "pythinfer.yaml"
    assert project.path_self.exists()
    assert project.focus[0] == ttl_file.resolve()




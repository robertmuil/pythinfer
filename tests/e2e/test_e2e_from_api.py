from pathlib import Path

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

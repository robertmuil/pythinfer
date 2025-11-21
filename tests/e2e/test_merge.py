"""End-to-end tests for the merge command."""

import shutil
import subprocess
from pathlib import Path

import pytest
from rdflib import Dataset

UV_PATH = shutil.which("uv")
if UV_PATH is None:
    msg = "uv command not found in PATH"
    raise RuntimeError(msg)
UV_PATH = Path(UV_PATH)
PROJECT_ROOT = Path(__file__).parent.parent.parent


@pytest.mark.parametrize(
    ("project_name", "command"),
    [
        ("eg0-basic", "merge"),
        ("eg0-basic", "infer"),
    ],
)
def test_cli_command(
    project_name: str,
    command: str,
) -> None:
    """Test that CLI commands produce expected output for example projects."""
    project_dir = PROJECT_ROOT / "example_projects" / project_name

    # Ensure the example directory exists
    assert project_dir.exists(), f"Project directory not found: {project_dir}"

    actual_file = "merged.trig" if (command == "merge") else "inferred_owlrl.trig"
    expected_file = "expected_" + actual_file

    # Path to expected and actual output files
    expected_file_path = project_dir / "derived" / expected_file
    actual_file_path = project_dir / "derived" / actual_file

    # Ensure expected file exists
    assert expected_file_path.exists(), (
        f"Expected file not found: `{expected_file_path}`"
    )

    # Remove actual output if it exists from previous runs
    if actual_file_path.exists():
        actual_file_path.unlink()

    # Run the command from the project directory
    # This is safe as no user-input is passed.
    result = subprocess.run(  # noqa: S603
        [str(UV_PATH), "run", "pythinfer", command],
        cwd=project_dir,
        capture_output=True,
        text=True,
        check=False,
    )

    # Check the command succeeded
    assert result.returncode == 0, (
        f"`{command}` command failed:\n"
        f"STDOUT:\n{result.stdout}\n"
        f"STDERR:\n{result.stderr}"
    )

    # Verify the output file was created
    assert actual_file_path.exists(), f"Output file not created: {actual_file_path}"

    # Load both graphs and compare them
    expected_ds = Dataset()
    expected_ds.parse(expected_file_path, format="trig")

    actual_ds = Dataset()
    actual_ds.parse(actual_file_path, format="trig")

    # Check that all quads in expected are in actual
    expected_quads = set(expected_ds.quads())
    actual_quads = set(actual_ds.quads())

    missing_quads = expected_quads - actual_quads
    extra_quads = actual_quads - expected_quads

    assert not missing_quads, f"Missing quads:\n{missing_quads}"
    assert not extra_quads, f"Extra quads:\n{extra_quads}"

    # Check they have the same number of quads - redundant but explicit
    assert len(expected_ds) == len(actual_ds), (
        f"Dataset length mismatch: expected {len(expected_ds)}, "
        f"got {len(actual_ds)}"
    )

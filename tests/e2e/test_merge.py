"""End-to-end tests for the merge command."""

import shutil
import subprocess
from pathlib import Path

from rdflib import Dataset

UV_PATH = shutil.which("uv")
if UV_PATH is None:
    msg ="uv command not found in PATH"
    raise RuntimeError(msg)
UV_PATH = Path(UV_PATH)
MERGE_CMD: tuple[Path, str, str, str] = (UV_PATH, "run", "pythinfer", "merge")
PROJECT_ROOT = Path(__file__).parent.parent.parent
EG0_DIR = PROJECT_ROOT / "example_projects" / "eg0-basic"

def test_merge_cli_eg0_basic() -> None:
    """Test that merge CLI produces expected output for eg0-basic example."""
    # Ensure the example directory exists
    assert EG0_DIR.exists(), f"Example directory not found: {EG0_DIR}"

    # Path to expected and actual output files
    expected_file = EG0_DIR / "derived" / "expected_merged.trig"
    actual_file = EG0_DIR / "derived" / "merged.trig"

    # Ensure expected file exists
    assert expected_file.exists(), f"Expected file not found: `{expected_file}`"

    # Remove actual output if it exists from previous runs
    if actual_file.exists():
        actual_file.unlink()

    # Run the merge command from the eg0-basic directory

    # This is safe as no user-input is passed.
    result = subprocess.run(  # noqa: S603
        MERGE_CMD,
        cwd=EG0_DIR,
        capture_output=True,
        text=True,
        check=False,
    )

    # Check the command succeeded
    assert result.returncode == 0, (
        f"Merge command failed:\n"
        f"STDOUT:\n{result.stdout}\n"
        f"STDERR:\n{result.stderr}"
    )

    # Verify the output file was created
    assert actual_file.exists(), f"Output file not created: {actual_file}"

    # Load both graphs and compare them
    expected_ds = Dataset()
    expected_ds.parse(expected_file, format="trig")

    actual_ds = Dataset()
    actual_ds.parse(actual_file, format="trig")

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
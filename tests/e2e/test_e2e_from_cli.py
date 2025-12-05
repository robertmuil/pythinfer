"""End-to-end tests for the merge and infer commands."""

import os
from pathlib import Path

import pytest
from rdflib import Dataset
from rdflib.compare import graph_diff, isomorphic
from typer.testing import CliRunner

from pythinfer.cli import app
from pythinfer.inout import INFERRED_WANTED_FILESTEM, MERGED_FILESTEM

PROJECT_ROOT = Path(__file__).parent.parent.parent


@pytest.mark.parametrize(
    ("project_name", "command"),
    [
        ("eg0-basic", "merge"),
        ("eg0-basic", "infer"),
        ("eg1-ancestors", "merge"),
        ("eg1-ancestors", "infer"),
        ("eg2-projects", "infer"),
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

    actual_file = (
        f"{MERGED_FILESTEM}.trig"
        if (command == "merge")
        else f"{INFERRED_WANTED_FILESTEM}.trig"
    )
    expected_file = (
        "expected_merged.trig"
        if (command == "merge")
        else "expected_inferred_wanted.trig"
    )

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

    # Run the command using CliRunner but with proper working directory
    # Save current working directory and change to project directory
    original_cwd = Path.cwd()
    try:
        os.chdir(project_dir)
        runner = CliRunner()
        cmd_args = [command, "--output", str(actual_file_path)]
        # Disable cache for infer command to ensure fresh runs
        if command == "infer":
            cmd_args.append("--no-cache")
        result = runner.invoke(app, cmd_args)
    finally:
        os.chdir(original_cwd)

    # Check the command succeeded
    assert result.exit_code == 0, (
        f"`{command}` command failed with exit code {result.exit_code}:\n"
        f"Output:\n{result.stdout}"
    )

    # Verify the output file was created
    assert actual_file_path.exists(), f"Output file not created: {actual_file_path}"

    # Load both graphs and compare them
    expected_ds = Dataset()
    expected_ds.parse(expected_file_path, format="trig")

    actual_ds = Dataset()
    actual_ds.parse(actual_file_path, format="trig")

    # Compare datasets by checking each named graph individually (handles blank nodes)
    # First check we have the same graph identifiers
    expected_graphs = {g.identifier for g in expected_ds.graphs()}
    actual_graphs = {g.identifier for g in actual_ds.graphs()}
    assert expected_graphs == actual_graphs, (
        f"Graph identifiers don't match:\n"
        f"Expected: {expected_graphs}\n"
        f"Actual: {actual_graphs}"
    )

    # Then check each named graph is isomorphic
    for graph_id in expected_graphs:
        expected_graph = expected_ds.graph(graph_id)
        actual_graph = actual_ds.graph(graph_id)

        if not isomorphic(expected_graph, actual_graph):
            # Compute the difference to show what's missing/extra
            in_both, in_expected_only, in_actual_only = graph_diff(
                expected_graph,
                actual_graph,
            )

            error_msg = [
                f"Graphs with identifier {graph_id} are not isomorphic:",
                f"\nTriples in both graphs: {len(in_both)}",
                f"\nTriples only in expected ({len(in_expected_only)}):",
            ]
            if len(in_expected_only) > 0:
                error_msg.append(in_expected_only.serialize(format="turtle"))

            error_msg.append(f"\nTriples only in actual ({len(in_actual_only)}):")
            if len(in_actual_only) > 0:
                error_msg.append(in_actual_only.serialize(format="turtle"))

            pytest.fail("\n".join(error_msg))

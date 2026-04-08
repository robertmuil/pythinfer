"""End-to-end tests for the merge and infer commands."""

from pathlib import Path

import pytest
from rdflib import Dataset, Graph
from rdflib.compare import graph_diff, isomorphic
from typer.testing import CliRunner

from pythinfer.cli import app
from pythinfer.project import INFERRED_FILESTEM, MERGED_FILESTEM

PROJECT_ROOT = Path(__file__).parent.parent.parent


def _assert_graphs_isomorphic(expected_graph: Graph, actual_graph: Graph,
                               label: str) -> None:
    """Assert two graphs are isomorphic, with a detailed diff on failure."""
    if isomorphic(expected_graph, actual_graph):
        return

    in_both, in_expected_only, in_actual_only = graph_diff(
        expected_graph,
        actual_graph,
    )

    error_msg = [
        f"{label}:",
        f"\nTriples in both graphs: {len(in_both)}",
        f"\nTriples only in expected ({len(in_expected_only)}):",
    ]
    if len(in_expected_only) > 0:
        error_msg.append(in_expected_only.serialize(format="turtle"))
    error_msg.append(f"\nTriples only in actual ({len(in_actual_only)}):")
    if len(in_actual_only) > 0:
        error_msg.append(in_actual_only.serialize(format="turtle"))
    pytest.fail("\n".join(error_msg))


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
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    """Test that CLI commands produce expected output for example projects."""
    project_dir = PROJECT_ROOT / "example_projects" / project_name

    # Ensure the example directory exists
    assert project_dir.exists(), f"Project directory not found: {project_dir}"

    actual_file = (
        f"{MERGED_FILESTEM}.trig"
        if (command == "merge")
        else f"{INFERRED_FILESTEM}.trig"
    )
    expected_file = "expected-" + actual_file

    # Path to expected and actual output files
    expected_file_path = project_dir / "expected" / expected_file
    actual_file_path = project_dir / "derived" / "test_cli_command" / actual_file

    # Ensure expected file exists
    assert expected_file_path.exists(), (
        f"Expected file not found: `{expected_file_path}`"
    )

    # Remove actual output if it exists from previous runs
    if actual_file_path.exists():
        actual_file_path.unlink()

    # Make sure intermediate output folder exists
    actual_file_path.parent.mkdir(parents=True, exist_ok=True)

    # Run the command using CliRunner but with proper working directory
    monkeypatch.chdir(project_dir)
    runner = CliRunner()
    cmd_args = [command, "--output", str(actual_file_path)]
    # Disable cache for infer command to ensure fresh runs
    if command == "infer":
        cmd_args.append("--no-cache")
    result = runner.invoke(app, cmd_args)

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

        _assert_graphs_isomorphic(
            expected_graph,
            actual_graph,
            f"Graphs with identifier {graph_id} are not isomorphic",
        )

    # --- Check provenance file ---
    expected_provenance_filename = (
        "expected-0-merged-provenance.ttl"
        if command == "merge"
        else "expected-1-inferred-provenance.ttl"
    )
    expected_provenance_path = project_dir / "expected" / expected_provenance_filename
    assert expected_provenance_path.exists(), (
        f"Expected provenance file not found: {expected_provenance_path}"
    )

    # Determine actual provenance file path
    actual_provenance_path = actual_file_path.with_stem(
        f"{actual_file_path.stem}-provenance"
    ).with_suffix(".ttl")

    assert actual_provenance_path.exists(), (
        f"Provenance file not created: {actual_provenance_path}"
    )

    # Load expected provenance, substituting $PROJ_FOLDER with actual path
    proj_folder = str(PROJECT_ROOT.parent).lstrip("/")
    expected_prov_text = expected_provenance_path.read_text()
    expected_prov_text = expected_prov_text.replace("$PROJ_FOLDER", proj_folder)

    expected_prov_graph = Graph()
    expected_prov_graph.parse(data=expected_prov_text, format="turtle")

    # Load actual provenance (trig format, extract the provenance named graph)
    actual_prov_graph = Graph()
    actual_prov_graph.parse(actual_provenance_path, format="turtle")

    _assert_graphs_isomorphic(
        expected_prov_graph,
        actual_prov_graph,
        "Provenance graphs are not isomorphic",
    )

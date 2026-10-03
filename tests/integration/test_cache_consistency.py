"""Regression test: a fresh run and a cached run must return the same Dataset.

Bug: a fresh `infer` returned the full Dataset, including reference graphs and
external inferences, while the cache (`2-combined.trig`) excludes them. Queries
therefore gave different answers on the first run than on subsequent runs.
"""

import shutil
from pathlib import Path

from typer.testing import CliRunner

from pythinfer import Project
from pythinfer.cli import app

PROJECT_ROOT = Path(__file__).parent.parent.parent
COUNT_QUERY = "SELECT (COUNT(*) AS ?n) WHERE { ?s ?p ?o }"


def _make_project(tmp_path: Path) -> Path:
    src = PROJECT_ROOT / "example_projects" / "eg0-basic"
    shutil.copy(src / "basic-data.ttl", tmp_path)
    shutil.copy(src / "basic-model.ttl", tmp_path)
    project_file = tmp_path / "pythinfer.yaml"
    project_file.write_text(
        "name: cache-consistency\n"
        "focus:\n  - basic-data.ttl\n"
        "reference:\n  - basic-model.ttl\n",
    )
    return project_file


def test_api_fresh_and_cached_infer_match(tmp_path: Path) -> None:
    project = Project.from_yaml(_make_project(tmp_path))

    fresh = project.infer()
    cached = project.infer()

    assert len(fresh) == len(cached)


def test_cli_fresh_and_cached_query_match(tmp_path: Path) -> None:
    project_file = _make_project(tmp_path)
    args = ["--project", str(project_file), "query", COUNT_QUERY, "-f", "csv"]
    runner = CliRunner()

    fresh = runner.invoke(app, args)
    cached = runner.invoke(app, args)

    assert fresh.exit_code == 0, fresh.output
    assert cached.exit_code == 0, cached.output
    assert fresh.stdout == cached.stdout

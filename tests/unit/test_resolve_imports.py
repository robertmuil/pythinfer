"""Unit tests for owl:imports resolution."""

from pathlib import Path
from unittest.mock import patch

import pytest
import yaml
from rdflib import OWL, Graph, Namespace, URIRef
from typer.testing import CliRunner

from pythinfer.cli import app
from pythinfer.project import ProjectSpec
from pythinfer.resolve_imports import _sanitize_url_to_filename, resolve_imports


EX = Namespace("http://example.org/")


def _write_ttl(path: Path, content: str) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(content)


class TestSanitizeUrlToFilename:
    def test_simple_url(self) -> None:
        assert _sanitize_url_to_filename("http://purl.org/dc/terms/") == "purl.org_dc_terms.ttl"

    def test_url_without_trailing_slash(self) -> None:
        result = _sanitize_url_to_filename("http://www.w3.org/ns/prov")
        assert result == "www.w3.org_ns_prov.ttl"

    def test_url_with_hash(self) -> None:
        result = _sanitize_url_to_filename("http://www.w3.org/2004/02/skos/core")
        assert result == "www.w3.org_2004_02_skos_core.ttl"


class TestResolveImports:
    def test_no_imports(self, tmp_path: Path) -> None:
        """Files without owl:imports produce an empty result."""
        data = tmp_path / "data.ttl"
        _write_ttl(data, """\
@prefix ex: <http://example.org/> .
ex:a ex:b ex:c .
""")
        project = ProjectSpec(
            name="test",
            focus=[data],
            path_self=tmp_path / "pythinfer.yaml",
        )
        result = resolve_imports(project)
        assert result == {}

    def test_resolves_local_file_import(self, tmp_path: Path) -> None:
        """owl:imports pointing to a local file URI is resolved."""
        imported = tmp_path / "vocab.ttl"
        _write_ttl(imported, """\
@prefix ex: <http://example.org/> .
ex:Thing a ex:Class .
""")

        data = tmp_path / "data.ttl"
        import_url = imported.resolve().as_uri()
        _write_ttl(data, f"""\
@prefix owl: <http://www.w3.org/2002/07/owl#> .
@prefix ex: <http://example.org/> .
<http://example.org/ont> owl:imports <{import_url}> .
ex:a a ex:Thing .
""")

        project = ProjectSpec(
            name="test",
            focus=[data],
            path_self=tmp_path / "pythinfer.yaml",
        )
        download_dir = tmp_path / "imports"
        result = resolve_imports(project, download_dir=download_dir)

        assert len(result) == 1
        assert import_url in result
        assert result[import_url].exists()
        assert result[import_url].parent == download_dir

        # Check URL mapping file is created
        mapping_file = download_dir / "url-mapping.yaml"
        assert mapping_file.exists()
        mapping = yaml.safe_load(mapping_file.read_text())
        assert import_url in mapping

    def test_resolves_import_closure(self, tmp_path: Path) -> None:
        """Imports from imported files are also resolved (closure)."""
        # level2 has no imports
        level2 = tmp_path / "level2.ttl"
        _write_ttl(level2, """\
@prefix ex: <http://example.org/> .
ex:Deep a ex:Class .
""")

        # level1 imports level2
        level1 = tmp_path / "level1.ttl"
        level2_url = level2.resolve().as_uri()
        _write_ttl(level1, f"""\
@prefix owl: <http://www.w3.org/2002/07/owl#> .
@prefix ex: <http://example.org/> .
<http://example.org/ont1> owl:imports <{level2_url}> .
ex:Mid a ex:Class .
""")

        # data imports level1
        data = tmp_path / "data.ttl"
        level1_url = level1.resolve().as_uri()
        _write_ttl(data, f"""\
@prefix owl: <http://www.w3.org/2002/07/owl#> .
@prefix ex: <http://example.org/> .
<http://example.org/ont> owl:imports <{level1_url}> .
ex:a a ex:Thing .
""")

        project = ProjectSpec(
            name="test",
            focus=[data],
            path_self=tmp_path / "pythinfer.yaml",
        )
        result = resolve_imports(project, download_dir=tmp_path / "imports")

        assert len(result) == 2
        assert level1_url in result
        assert level2_url in result

    def test_handles_import_cycle(self, tmp_path: Path) -> None:
        """Circular owl:imports do not cause infinite loops."""
        file_a = tmp_path / "a.ttl"
        file_b = tmp_path / "b.ttl"
        url_a = file_a.resolve().as_uri()
        url_b = file_b.resolve().as_uri()

        _write_ttl(file_a, f"""\
@prefix owl: <http://www.w3.org/2002/07/owl#> .
<http://example.org/a> owl:imports <{url_b}> .
""")
        _write_ttl(file_b, f"""\
@prefix owl: <http://www.w3.org/2002/07/owl#> .
<http://example.org/b> owl:imports <{url_a}> .
""")

        data = tmp_path / "data.ttl"
        _write_ttl(data, f"""\
@prefix owl: <http://www.w3.org/2002/07/owl#> .
<http://example.org/ont> owl:imports <{url_a}> .
""")

        project = ProjectSpec(
            name="test",
            focus=[data],
            path_self=tmp_path / "pythinfer.yaml",
        )
        result = resolve_imports(project, download_dir=tmp_path / "imports")

        assert len(result) == 2

    def test_skips_already_cached(self, tmp_path: Path) -> None:
        """Already-downloaded files are not re-downloaded."""
        imported = tmp_path / "vocab.ttl"
        _write_ttl(imported, """\
@prefix ex: <http://example.org/> .
ex:Thing a ex:Class .
""")

        import_url = imported.resolve().as_uri()
        data = tmp_path / "data.ttl"
        _write_ttl(data, f"""\
@prefix owl: <http://www.w3.org/2002/07/owl#> .
<http://example.org/ont> owl:imports <{import_url}> .
""")

        download_dir = tmp_path / "imports"
        project = ProjectSpec(
            name="test",
            focus=[data],
            path_self=tmp_path / "pythinfer.yaml",
        )

        # First resolve
        result1 = resolve_imports(project, download_dir=download_dir)
        cached_path = list(result1.values())[0]
        mtime_before = cached_path.stat().st_mtime

        # Second resolve should use cache
        result2 = resolve_imports(project, download_dir=download_dir)
        assert cached_path.stat().st_mtime == mtime_before
        assert len(result2) == 1

    def test_skips_unfetchable_url(self, tmp_path: Path) -> None:
        """Unfetchable URLs are skipped with a warning, not an error."""
        data = tmp_path / "data.ttl"
        _write_ttl(data, """\
@prefix owl: <http://www.w3.org/2002/07/owl#> .
<http://example.org/ont> owl:imports <http://does-not-exist.invalid/ontology> .
""")

        project = ProjectSpec(
            name="test",
            focus=[data],
            path_self=tmp_path / "pythinfer.yaml",
        )
        result = resolve_imports(project, download_dir=tmp_path / "imports")

        assert result == {}
        assert not (tmp_path / "imports" / "url-mapping.yaml").exists()

    def test_duplicate_import_url_across_files(self, tmp_path: Path) -> None:
        """Same owl:imports URL in multiple files is resolved only once."""
        imported = tmp_path / "vocab.ttl"
        _write_ttl(imported, """\
@prefix ex: <http://example.org/> .
ex:Thing a ex:Class .
""")
        import_url = imported.resolve().as_uri()

        data1 = tmp_path / "data1.ttl"
        _write_ttl(data1, f"""\
@prefix owl: <http://www.w3.org/2002/07/owl#> .
<http://example.org/ont1> owl:imports <{import_url}> .
""")
        data2 = tmp_path / "data2.ttl"
        _write_ttl(data2, f"""\
@prefix owl: <http://www.w3.org/2002/07/owl#> .
<http://example.org/ont2> owl:imports <{import_url}> .
""")

        project = ProjectSpec(
            name="test",
            focus=[data1, data2],
            path_self=tmp_path / "pythinfer.yaml",
        )
        result = resolve_imports(project, download_dir=tmp_path / "imports")

        assert len(result) == 1

    def test_no_mapping_file_when_no_imports(self, tmp_path: Path) -> None:
        """No url-mapping.yaml is created when there are no imports."""
        data = tmp_path / "data.ttl"
        _write_ttl(data, """\
@prefix ex: <http://example.org/> .
ex:a ex:b ex:c .
""")
        project = ProjectSpec(
            name="test",
            focus=[data],
            path_self=tmp_path / "pythinfer.yaml",
        )
        resolve_imports(project, download_dir=tmp_path / "imports")

        assert not (tmp_path / "imports" / "url-mapping.yaml").exists()

    def test_skips_already_resolved_url_from_closure(self, tmp_path: Path) -> None:
        """A URL discovered via closure that was already resolved is skipped."""
        # shared is imported by both level1a and level1b
        shared = tmp_path / "shared.ttl"
        _write_ttl(shared, """\
@prefix ex: <http://example.org/> .
ex:Shared a ex:Class .
""")
        shared_url = shared.resolve().as_uri()

        level1a = tmp_path / "a.ttl"
        _write_ttl(level1a, f"""\
@prefix owl: <http://www.w3.org/2002/07/owl#> .
<http://example.org/a> owl:imports <{shared_url}> .
""")
        level1b = tmp_path / "b.ttl"
        _write_ttl(level1b, f"""\
@prefix owl: <http://www.w3.org/2002/07/owl#> .
<http://example.org/b> owl:imports <{shared_url}> .
""")

        # data imports both a and b, which both import shared
        data = tmp_path / "data.ttl"
        url_a = level1a.resolve().as_uri()
        url_b = level1b.resolve().as_uri()
        _write_ttl(data, f"""\
@prefix owl: <http://www.w3.org/2002/07/owl#> .
<http://example.org/ont> owl:imports <{url_a}> , <{url_b}> .
""")

        project = ProjectSpec(
            name="test",
            focus=[data],
            path_self=tmp_path / "pythinfer.yaml",
        )
        result = resolve_imports(project, download_dir=tmp_path / "imports")

        # shared_url should appear once despite being discovered from both a and b
        assert len(result) == 3
        assert shared_url in result

    def test_imports_from_reference_files(self, tmp_path: Path) -> None:
        """owl:imports in reference files are also resolved."""
        imported = tmp_path / "deep.ttl"
        _write_ttl(imported, """\
@prefix ex: <http://example.org/> .
ex:Deep a ex:Class .
""")
        import_url = imported.resolve().as_uri()

        ref = tmp_path / "ref.ttl"
        _write_ttl(ref, f"""\
@prefix owl: <http://www.w3.org/2002/07/owl#> .
<http://example.org/ref> owl:imports <{import_url}> .
""")

        data = tmp_path / "data.ttl"
        _write_ttl(data, """\
@prefix ex: <http://example.org/> .
ex:a a ex:Thing .
""")

        project = ProjectSpec(
            name="test",
            focus=[data],
            reference=[ref],
            path_self=tmp_path / "pythinfer.yaml",
        )
        result = resolve_imports(project, download_dir=tmp_path / "imports")

        assert len(result) == 1
        assert import_url in result


class TestResolveImportsCLI:
    def test_cli_no_imports(self, tmp_path: Path, monkeypatch: pytest.MonkeyPatch) -> None:
        """CLI reports when no imports are found."""
        monkeypatch.chdir(tmp_path)
        data = tmp_path / "data.ttl"
        _write_ttl(data, """\
@prefix ex: <http://example.org/> .
ex:a ex:b ex:c .
""")
        project_file = tmp_path / "pythinfer.yaml"
        project_file.write_text(yaml.dump({"name": "test", "focus": ["data.ttl"]}))

        runner = CliRunner()
        result = runner.invoke(app, ["-p", str(project_file), "resolve-imports"])

        assert result.exit_code == 0
        assert "No owl:imports found" in result.output

    def test_cli_resolves_and_updates_yaml(self, tmp_path: Path, monkeypatch: pytest.MonkeyPatch) -> None:
        """CLI resolves imports and updates the project YAML file."""
        monkeypatch.chdir(tmp_path)

        imported = tmp_path / "vocab.ttl"
        _write_ttl(imported, """\
@prefix ex: <http://example.org/> .
ex:Thing a ex:Class .
""")
        import_url = imported.resolve().as_uri()

        data = tmp_path / "data.ttl"
        _write_ttl(data, f"""\
@prefix owl: <http://www.w3.org/2002/07/owl#> .
<http://example.org/ont> owl:imports <{import_url}> .
""")

        # Include an extra key to verify it is preserved
        project_file = tmp_path / "pythinfer.yaml"
        project_file.write_text(yaml.dump({
            "name": "test",
            "focus": ["data.ttl"],
            "custom_key": "should be preserved",
        }))

        runner = CliRunner()
        result = runner.invoke(app, ["-p", str(project_file), "resolve-imports"])

        assert result.exit_code == 0
        assert "Resolved 1 import(s)" in result.output

        # Verify YAML was updated with reference and extra key preserved
        updated = yaml.safe_load(project_file.read_text())
        assert "reference" in updated
        assert len(updated["reference"]) == 1
        assert updated["custom_key"] == "should be preserved"

    def test_cli_appends_to_aliased_reference_key(self, tmp_path: Path, monkeypatch: pytest.MonkeyPatch) -> None:
        """CLI appends to existing aliased key (e.g. external-vocabs) instead of creating a separate reference key."""
        monkeypatch.chdir(tmp_path)

        imported = tmp_path / "vocab.ttl"
        _write_ttl(imported, """\
@prefix ex: <http://example.org/> .
ex:Thing a ex:Class .
""")
        import_url = imported.resolve().as_uri()

        model = tmp_path / "model.ttl"
        _write_ttl(model, f"""\
@prefix owl: <http://www.w3.org/2002/07/owl#> .
<http://example.org/ont> owl:imports <{import_url}> .
""")

        data = tmp_path / "data.ttl"
        _write_ttl(data, """\
@prefix ex: <http://example.org/> .
ex:a a ex:Thing .
""")

        # Use external-vocabs alias in the YAML
        project_file = tmp_path / "pythinfer.yaml"
        project_file.write_text(
            "name: test\nfocus:\n- data.ttl\nexternal-vocabs:\n- model.ttl\n"
        )

        runner = CliRunner()
        result = runner.invoke(app, ["-p", str(project_file), "resolve-imports"])

        assert result.exit_code == 0
        assert "Resolved 1 import(s)" in result.output

        updated = yaml.safe_load(project_file.read_text())
        # Should append to external-vocabs, not create a new reference key
        assert "external-vocabs" in updated
        assert "reference" not in updated
        assert "model.ttl" in updated["external-vocabs"]
        assert len(updated["external-vocabs"]) == 2

"""Unit tests for owl:imports resolution."""

from pathlib import Path

import pytest
from rdflib import OWL, Graph, Namespace, URIRef

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

"""Unit tests for ProjectSpec internals and helpers."""

from pathlib import Path
from unittest.mock import patch

import pytest
import yaml

from pythinfer.project import (
    PROJECT_FILE_NAME,
    ProjectSpec,
    discover_project,
)


class TestProjectHelpers:
    """Tests for small helper functions used by ProjectSpec."""

    def test_default_path_self_returns_cwd_config_path(
        self,
        tmp_path: Path,
        monkeypatch: pytest.MonkeyPatch,
    ) -> None:
        """Default path_self should point to cwd/pythinfer.yaml."""
        monkeypatch.chdir(tmp_path)

        project = ProjectSpec(name="demo", focus=[Path("a.ttl")])

        assert project.path_self == tmp_path / PROJECT_FILE_NAME

    def test_default_path_self_raises_when_existing_config(
        self,
        tmp_path: Path,
        monkeypatch: pytest.MonkeyPatch,
    ) -> None:
        """Default path generation should fail if cwd config already exists."""
        monkeypatch.chdir(tmp_path)
        (tmp_path / PROJECT_FILE_NAME).write_text("name: x\nfocus: [a.ttl]\n")

        with pytest.raises(
            Exception,
            match="Path for new Project points to existing file",
        ):
            ProjectSpec(name="demo", focus=[Path("a.ttl")])

    def test_reference_default_factory_returns_fresh_list(self, tmp_path: Path) -> None:
        """Each instance gets its own default reference list."""
        first = ProjectSpec(
            name="one",
            focus=[Path("a.ttl")],
            path_self=tmp_path / "a.yaml",
        )
        first.reference.append(Path("v.ttl"))
        second = ProjectSpec(
            name="two",
            focus=[Path("b.ttl")],
            path_self=tmp_path / "b.yaml",
        )

        assert second.reference == []


class TestProjectSpecCoreBehavior:
    """Tests core model behavior not covered by roundtrip/path tests."""

    def test_equality_and_hash_exclude_path_self(self, tmp_path: Path) -> None:
        """Different config file locations do not affect identity/hash."""
        project_a = ProjectSpec(
            name="demo",
            focus=[Path("a.ttl")],
            reference=[Path("v.ttl")],
            path_self=tmp_path / "a.yaml",
        )
        project_b = ProjectSpec(
            name="demo",
            focus=[Path("a.ttl")],
            reference=[Path("v.ttl")],
            path_self=tmp_path / "b.yaml",
        )

        assert project_a == project_b
        assert hash(project_a) == hash(project_b)
        assert ProjectSpec.__eq__(project_a, object()) is NotImplemented

    def test_aliases_cover_paths_data_external_and_sparql(self, tmp_path: Path) -> None:
        """Alternative field spellings should normalize to canonical fields."""
        project = ProjectSpec.model_validate(
            {
                "name": "aliases",
                "path_self": tmp_path / "cfg.yaml",
                "paths_data": ["focus.ttl"],
                "paths_vocab_ext": ["vocab.ttl"],
                "paths_sparql_inference": ["infer.rq"],
                "external_vocabs": ["vocab2.ttl"],
                "owl_backend": "owlrl",
            }
        )

        assert project.focus == [Path("focus.ttl")]
        # The later alias assignment wins for the same canonical field.
        assert project.reference == [Path("vocab2.ttl")]
        assert project.sparql_inference == [Path("infer.rq")]

    def test_paths_stay_relative_without_validation_context(
        self,
        tmp_path: Path,
    ) -> None:
        """Direct model construction should not force absolute paths."""
        project = ProjectSpec.model_validate(
            {
                "name": "relative",
                "path_self": tmp_path / "cfg.yaml",
                "focus": ["nested/data.ttl"],
            }
        )

        assert project.focus[0] == Path("nested/data.ttl")

    def test_from_yaml_sets_default_name_from_parent(self, tmp_path: Path) -> None:
        """Missing name should default to the config parent folder name."""
        project_dir = tmp_path / "my-project"
        project_dir.mkdir()
        config_path = project_dir / PROJECT_FILE_NAME
        config_path.write_text("focus:\n  - data.ttl\n")

        project = ProjectSpec.from_yaml(config_path)

        assert project.name == "my-project"
        assert project.path_self == config_path.resolve()

    def test_discover_classmethod_uses_discover_project(
        self,
        tmp_path: Path,
        monkeypatch: pytest.MonkeyPatch,
    ) -> None:
        """ProjectSpec.discover should locate and load nearest project file."""
        project_dir = tmp_path / "proj"
        project_dir.mkdir()
        config_path = project_dir / PROJECT_FILE_NAME
        config_path.write_text("name: found\nfocus:\n  - data.ttl\n")

        nested = project_dir / "a" / "b"
        nested.mkdir(parents=True)
        monkeypatch.chdir(nested)

        project = ProjectSpec.discover()

        assert project.name == "found"
        assert project.path_self == config_path.resolve()

    def test_path_to_yaml_str_uses_raw_string_for_nonexistent_stem(
        self,
        tmp_path: Path,
    ) -> None:
        """For synthetic path_self names, keep path string untouched."""
        project = ProjectSpec(
            name="demo",
            focus=[Path("../outside.ttl")],
            path_self=tmp_path / "demo.nonexistent.yaml",
        )

        dumped = yaml.safe_load(project.to_yaml_str())
        assert dumped["focus"] == ["../outside.ttl"]

    def test_to_yaml_str_omits_optional_empty_fields(self, tmp_path: Path) -> None:
        """Optional keys should not appear when values are empty/None."""
        project = ProjectSpec(
            name="demo",
            focus=[Path("a.ttl")],
            reference=[],
            owl_backend=None,
            sparql_inference=None,
            path_self=tmp_path / "cfg.yaml",
        )

        dumped = yaml.safe_load(project.to_yaml_str())

        assert dumped == {"name": "demo", "focus": ["a.ttl"]}

    def test_to_yaml_writes_file(self, tmp_path: Path) -> None:
        """to_yaml should persist serialized project to the target path."""
        project = ProjectSpec(
            name="demo",
            focus=[Path("a.ttl")],
            path_self=tmp_path / "cfg.yaml",
        )
        output_path = tmp_path / "output.yaml"

        project.to_yaml(output_path)

        saved = yaml.safe_load(output_path.read_text())
        assert saved["name"] == "demo"

    def test_persist_if_absent_creates_when_missing(self, tmp_path: Path) -> None:
        """persist_if_absent writes config when the file does not exist."""
        config_path = tmp_path / "new" / PROJECT_FILE_NAME
        project = ProjectSpec(
            name="demo",
            focus=[Path("a.ttl")],
            path_self=config_path,
        )

        project.persist_if_absent()

        assert config_path.exists()

    def test_persist_if_absent_keeps_existing_file(self, tmp_path: Path) -> None:
        """persist_if_absent should not overwrite existing config."""
        config_path = tmp_path / PROJECT_FILE_NAME
        config_path.write_text("sentinel")

        project = ProjectSpec(
            name="demo",
            focus=[Path("a.ttl")],
            path_self=config_path,
        )

        project.persist_if_absent()

        assert config_path.read_text() == "sentinel"

    def test_path_and_gid_properties(self, tmp_path: Path) -> None:
        """Computed paths and graph IDs should be deterministic."""
        project_dir = tmp_path / "project"
        project_dir.mkdir()
        config_path = project_dir / PROJECT_FILE_NAME
        project = ProjectSpec(
            name="demo",
            focus=[Path("a.ttl")],
            reference=[Path("v.ttl")],
            sparql_inference=[Path("infer.rq")],
            path_self=config_path,
        )

        assert project.path_output == project_dir / "derived" / "pythinfer"
        assert project.paths_all_input == [Path("a.ttl"), Path("v.ttl")]
        assert project.paths_all == [Path("a.ttl"), Path("v.ttl"), Path("infer.rq")]
        assert str(project.namespace) == "http://pythinfer.local/demo/"
        assert str(project.provenance_gid) == "http://pythinfer.local/demo/provenance"
        assert (
            str(project.inference_gid("owl"))
            == "http://pythinfer.local/demo/inferences/owl"
        )

    def test_source_file_gid_inside_project(self, tmp_path: Path) -> None:
        """Source files inside project dir should use relative file path."""
        project_dir = tmp_path / "project"
        data_dir = project_dir / "data"
        data_dir.mkdir(parents=True)

        project = ProjectSpec(
            name="demo",
            focus=[Path("data/a.ttl")],
            path_self=project_dir / PROJECT_FILE_NAME,
        )
        file_path = data_dir / "a.ttl"
        file_path.touch()

        gid = project.source_file_gid(file_path)

        assert str(gid) == "http://pythinfer.local/demo/file/data/a.ttl"

    def test_source_file_gid_preserves_symlink_path_when_outside_target(
        self,
        tmp_path: Path,
    ) -> None:
        """If resolved path is external, unresolved symlink path is preserved."""
        project_dir = tmp_path / "project"
        project_dir.mkdir()
        outside_dir = tmp_path / "outside"
        outside_dir.mkdir()
        outside_file = outside_dir / "x.ttl"
        outside_file.touch()

        symlink_dir = project_dir / "link"
        symlink_dir.symlink_to(outside_dir, target_is_directory=True)

        project = ProjectSpec(
            name="demo",
            focus=[Path("link/x.ttl")],
            path_self=project_dir / PROJECT_FILE_NAME,
        )

        gid = project.source_file_gid(symlink_dir / "x.ttl")

        assert str(gid) == "http://pythinfer.local/demo/file/link/x.ttl"

    def test_source_file_gid_falls_back_to_filename(
        self,
        tmp_path: Path,
        monkeypatch: pytest.MonkeyPatch,
    ) -> None:
        """If relative mapping fails, gid should use only the filename."""
        monkeypatch.chdir(tmp_path)
        project_dir = tmp_path / "project"
        project_dir.mkdir()

        project = ProjectSpec(
            name="demo",
            focus=[Path("a.ttl")],
            path_self=project_dir / PROJECT_FILE_NAME,
        )

        gid = project.source_file_gid(Path("other/place.ttl"))

        assert str(gid) == "http://pythinfer.local/demo/file/place.ttl"


class TestDiscoverProjectHomeBoundary:
    """Tests for discover_project branches not exercised by existing tests."""

    def test_discover_project_stops_at_home_directory(self, tmp_path: Path) -> None:
        """Search should stop once recursion reaches the configured home path."""
        subdir = tmp_path / "child"
        subdir.mkdir()

        with patch("pythinfer.project.Path.home", return_value=tmp_path), pytest.raises(
            FileNotFoundError,
            match="reached `\\$HOME` directory",
        ):
            discover_project(subdir)

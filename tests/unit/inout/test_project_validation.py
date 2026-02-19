"""Tests for Pydantic validation in Project model."""

from pathlib import Path

import pytest
from pydantic import ValidationError

from pythinfer.inout import Project


class TestProjectValidConfiguration:
    """Test valid Project configurations."""

    def test_valid_config_with_hyphenated_keys(self, tmp_path: Path) -> None:
        """Test that Project accepts hyphenated keys (YAML-style)."""
        config_path = tmp_path / "test.yaml"
        config = {
            "name": "test-project",
            "path_self": config_path,
            "data": ["file1.ttl", "file2.ttl"],
            "external-vocabs": ["vocab2.ttl"],
            "owl-backend": "owlrl",
            "sparql-inference": ["query1.sparql"],
        }

        project = Project(**config)

        assert project.name == "test-project"
        assert len(project.focus) == 2
        assert len(project.reference) == 1
        assert project.owl_backend == "owlrl"
        assert len(project.sparql_inference) == 1

    def test_valid_config_with_underscored_keys(self, tmp_path: Path) -> None:
        """Test that Project accepts underscored keys (Python-style)."""
        config_path = tmp_path / "test.yaml"
        config = {
            "name": "test-project",
            "path_self": config_path,
            "focus": ["file1.ttl"],
            "reference": ["vocab1.ttl", "vocab2.ttl"],
            "owl_backend": "owlrl",
            "sparql_inference": ["query1.sparql"],
        }

        project = Project(**config)

        assert project.name == "test-project"
        assert len(project.focus) == 1
        assert len(project.reference) == 2
        assert project.owl_backend == "owlrl"
        assert len(project.sparql_inference) == 1

    def test_valid_config_minimal_fields(self, tmp_path: Path) -> None:
        """Test that Project works with only required fields."""
        config_path = tmp_path / "test.yaml"
        config = {
            "name": "minimal-project",
            "path_self": config_path,
            "focus": ["file1.ttl"],
        }

        project = Project(**config)

        assert project.name == "minimal-project"
        assert len(project.focus) == 1
        assert project.reference == []
        assert project.owl_backend is None
        assert project.sparql_inference is None


class TestProjectInvalidConfiguration:
    """Test invalid Project configurations that should raise ValidationError."""

    def test_rejects_unexpected_field(self, tmp_path: Path) -> None:
        """Test that Project rejects config with unexpected fields."""
        config_path = tmp_path / "test.yaml"
        config = {
            "name": "test-project",
            "path_self": config_path,
            "focus": ["file1.ttl"],
            "unexpected_field": "this should cause an error",
        }

        with pytest.raises(ValidationError) as exc_info:
            Project(**config)

        assert "unexpected_field" in str(exc_info.value)

    def test_rejects_missing_required_name(self, tmp_path: Path) -> None:
        """Test that Project requires 'name' field."""
        config_path = tmp_path / "test.yaml"
        config = {
            "path_self": config_path,
            "focus": ["file1.ttl"],
        }

        with pytest.raises(ValidationError) as exc_info:
            Project(**config)

        assert "name" in str(exc_info.value)

    def test_accepts_missing_path_self_with_default(self, tmp_path: Path) -> None:
        """Test that Project provides default for 'path_self' when missing."""
        config = {
            "name": "test-project",
            "focus": ["file1.ttl"],
        }

        project = Project(**config)

        # path_self should have a default sentinel value
        assert project.path_self is not None
        assert "generated_by_code" in str(project.path_self)

    def test_rejects_empty_focus_list(self, tmp_path: Path) -> None:
        """Test that Project rejects empty focus (data) list."""
        config_path = tmp_path / "test.yaml"
        config = {
            "name": "test-project",
            "path_self": config_path,
            "focus": [],  # Empty list should fail min_length=1 constraint
        }

        with pytest.raises(ValidationError) as exc_info:
            Project(**config)

        error_str = str(exc_info.value)
        assert "focus" in error_str

    def test_accepts_any_owl_backend_string(self, tmp_path: Path) -> None:
        """Test that Project accepts any string for owl_backend (no validation)."""
        config_path = tmp_path / "test.yaml"
        config = {
            "name": "test-project",
            "path_self": config_path,
            "focus": ["file1.ttl"],
            "owl_backend": "any-string-value",
        }

        # This should NOT raise - owl_backend currently has no validation
        project = Project(**config)
        assert project.owl_backend == "any-string-value"


class TestProjectLoadFromYAML:
    """Test loading Project from actual YAML files."""

    def test_load_from_yaml_with_basic_config(self) -> None:
        """Test loading from eg0-basic example project."""
        yaml_path = Path("example_projects/eg0-basic/pythinfer.yaml")
        if not yaml_path.exists():
            pytest.skip("Example project not found")

        project = Project.from_yaml(yaml_path)

        assert project.name
        assert len(project.focus) > 0
        # path_self is resolved to absolute path
        assert project.path_self.name == "pythinfer.yaml"

    def test_load_from_yaml_with_hyphenated_keys(self) -> None:
        """Test loading from YAML with hyphenated keys (eg2-projects)."""
        yaml_path = Path("example_projects/eg2-projects/pythinfer.yaml")
        if not yaml_path.exists():
            pytest.skip("Example project not found")

        project = Project.from_yaml(yaml_path)

        assert project.name
        # eg2-projects has external-vocabs defined
        assert isinstance(project.reference, list)

    def test_load_from_yaml_with_sparql_inference(self) -> None:
        """Test loading from YAML with SPARQL inference rules."""
        yaml_path = Path("example_projects/eg1-ancestors/pythinfer.yaml")
        if not yaml_path.exists():
            pytest.skip("Example project not found")

        project = Project.from_yaml(yaml_path)

        assert project.name
        assert len(project.focus) > 0


class TestProjectFieldAliases:
    """Test that field aliases work correctly for both input and output."""

    def test_data_alias_for_focus(self, tmp_path: Path) -> None:
        """Test that 'data' is an alias for 'focus'."""
        config_path = tmp_path / "test.yaml"
        config = {
            "name": "test-project",
            "path_self": config_path,
            "data": ["file1.ttl", "file2.ttl"],
        }

        project = Project(**config)

        # Should be accessible via 'focus' attribute (as Path objects)
        assert len(project.focus) == 2
        assert project.focus[0].name == "file1.ttl"
        assert project.focus[1].name == "file2.ttl"

    def test_local_alias_for_focus(self, tmp_path: Path) -> None:
        """Test that 'local' is an alias for 'focus'."""
        config_path = tmp_path / "test.yaml"
        config = {
            "name": "test-project",
            "path_self": config_path,
            "local": ["file1.ttl"],
        }

        project = Project(**config)

        # Should be accessible via 'focus' attribute
        assert len(project.focus) == 1
        assert project.focus[0].name == "file1.ttl"

    def test_external_vocabs_alias_for_reference(self, tmp_path: Path) -> None:
        """Test that 'external-vocabs' is an alias for 'reference'."""
        config_path = tmp_path / "test.yaml"
        config = {
            "name": "test-project",
            "path_self": config_path,
            "focus": ["file1.ttl"],
            "external-vocabs": ["vocab1.ttl", "vocab2.ttl"],
        }

        project = Project(**config)

        # Should be accessible via 'reference' attribute (as Path objects)
        assert len(project.reference) == 2
        assert project.reference[0].name == "vocab1.ttl"
        assert project.reference[1].name == "vocab2.ttl"


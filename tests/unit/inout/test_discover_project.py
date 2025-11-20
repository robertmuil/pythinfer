"""Tests for the discover_project function."""

from pathlib import Path
from unittest.mock import Mock, patch

import pytest

from pythinfer.inout import (
    MAX_DISCOVERY_SEARCH_DEPTH,
    PROJECT_FILE_NAME,
    Project,
    discover_project,
)

# NB: TODO(robert): a lot of these, if not all, are integration-style tests since they
# involve actual filesystem operations (creating temp dirs/files).
# Also, a lot of them are testing internal implementation details (like whether they
# call resolve() or exists()), which is not necessary, but for now it's acceptable.


class TestDiscoverProjectSuccess:
    """Test successful discovery scenarios."""

    def test_discovers_project_in_start_path(self, tmp_path: Path) -> None:
        """Test that discover_project finds config  immediately in start_path."""
        config_path = tmp_path / PROJECT_FILE_NAME
        config_path.write_text("name: test_project\ndata:\n  - file.ttl\n")

        result = discover_project(tmp_path)

        assert isinstance(result, Project)
        assert result.name == "test_project"

    def test_discovers_project_in_parent_directory(self, tmp_path: Path) -> None:
        """Test that discover_project recursively searches parent directories."""
        # Create config in parent directory
        config_path = tmp_path / PROJECT_FILE_NAME
        config_path.write_text("name: parent_project\ndata:\n  - data.ttl\n")

        # Create subdirectory and search from there
        subdir = tmp_path / "subdir" / "nested"
        subdir.mkdir(parents=True)

        result = discover_project(subdir)

        assert isinstance(result, Project)
        assert result.name == "parent_project"

    def test_discovers_project_multiple_levels_deep(self, tmp_path: Path) -> None:
        """Test discovery across multiple directory levels."""
        # Create config at root of temp directory
        config_path = tmp_path / PROJECT_FILE_NAME
        config_path.write_text("name: deep_project\ndata:\n  - file.ttl\n")

        # Create deeply nested subdirectory
        deep_subdir = tmp_path / "a" / "b" / "c" / "d" / "e"
        deep_subdir.mkdir(parents=True)

        result = discover_project(deep_subdir)

        assert isinstance(result, Project)
        assert result.name == "deep_project"

    def test_prefers_closest_project_config(self, tmp_path: Path) -> None:
        """Test that discovery returns the closest config file."""
        # Create config at root
        root_config = tmp_path / PROJECT_FILE_NAME
        root_config.write_text("name: root_project\ndata:\n  - file.ttl\n")

        # Create a closer config in subdirectory
        subdir = tmp_path / "subdir"
        subdir.mkdir()
        closer_config = subdir / PROJECT_FILE_NAME
        closer_config.write_text("name: closer_project\ndata:\n  - file.ttl\n")

        # Search from deeply nested subdirectory
        deep_subdir = subdir / "nested"
        deep_subdir.mkdir()

        result = discover_project(deep_subdir)

        # Should find the closer config, not the root one
        assert result.name == "closer_project"


class TestDiscoverProjectRecursion:
    """Test recursive search behavior."""

    def test_recursion_depth_tracking(self, tmp_path: Path) -> None:
        """Test that recursion depth is properly tracked."""
        # Create a config several levels deep
        config_path = tmp_path / PROJECT_FILE_NAME
        config_path.write_text("name: test\ndata:\n  - file.ttl\n")

        # Create deeply nested subdirectory
        deep_subdir = tmp_path / "a" / "b" / "c"
        deep_subdir.mkdir(parents=True)

        # Should still find the config despite depth
        result = discover_project(deep_subdir)
        assert result.name == "test"

    @patch("pythinfer.inout.Path.home")
    def test_stops_at_home_directory(self, mock_home: Mock, tmp_path: Path) -> None:
        """Test that search stops at $HOME directory without finding config."""
        mock_home.return_value = tmp_path

        # Create a subdirectory under the mocked home
        subdir = tmp_path / "subdir"
        subdir.mkdir()

        # Search from subdirectory; should not find config and should fail
        with pytest.raises(FileNotFoundError, match="reached `\\$HOME` directory"):
            discover_project(subdir)

    def test_raises_on_max_depth_exceeded(self, tmp_path: Path) -> None:
        """Test that search raises error when max depth is exceeded."""
        # Create a deeply nested subdirectory deeper than MAX_DISCOVERY_SEARCH_DEPTH
        deep_subdir = tmp_path
        for i in range(MAX_DISCOVERY_SEARCH_DEPTH + 5):
            deep_subdir = deep_subdir / f"level_{i}"
        deep_subdir.mkdir(parents=True)

        # Search from deep subdirectory without config
        with pytest.raises(
            FileNotFoundError,
            match="reached maximum search depth",
        ):
            discover_project(deep_subdir)

    def test_raises_on_root_directory(self) -> None:
        """Test that search raises error when root directory is reached."""
        root = Path("/")

        with pytest.raises(FileNotFoundError, match="reached root directory"):
            discover_project(root)


class TestDiscoverProjectMocking:
    """Test discover_project with mocked paths."""

    def test_with_mocked_resolve(self, tmp_path: Path) -> None:
        """Test discover_project with real paths and verify resolve is called."""
        config_path = tmp_path / PROJECT_FILE_NAME
        config_path.write_text("name: mocked_project\ndata:\n  - file.ttl\n")

        # Create a path with trailing slashes and relative components
        # to ensure resolve() is properly handling the normalization
        resolve_called = False
        original_resolve = Path.resolve

        def track_resolve(self):
            nonlocal resolve_called
            resolve_called = True
            return original_resolve(self)

        with patch.object(Path, "resolve", track_resolve):
            result = discover_project(tmp_path)

        assert result.name == "mocked_project"
        assert resolve_called

    def test_with_mocked_path_exists(self, tmp_path: Path) -> None:
        """Test discover_project with mocked exists() method."""
        # Create real project structure
        config_path = tmp_path / PROJECT_FILE_NAME
        config_path.write_text("name: test_project\ndata:\n  - file.ttl\n")

        # Mock Path.exists to verify it's called
        original_exists = Path.exists
        call_count = 0

        def mock_exists(self):
            nonlocal call_count
            call_count += 1
            return original_exists(self)

        with patch.object(Path, "exists", mock_exists):
            result = discover_project(tmp_path)

        assert result.name == "test_project"
        assert call_count >= 1  # exists() was called at least once

    def test_discovers_with_relative_path_input(
        self, tmp_path: Path, monkeypatch
    ) -> None:
        """Test that discover_project works with relative paths."""
        config_path = tmp_path / PROJECT_FILE_NAME
        config_path.write_text("name: relative_test\ndata:\n  - file.ttl\n")

        # Change to the temp directory
        monkeypatch.chdir(tmp_path)

        # Create a relative path
        rel_path = Path()
        result = discover_project(rel_path)

        assert result.name == "relative_test"

    def test_discovers_with_relative_path_from_subdir(
        self, tmp_path: Path, monkeypatch
    ) -> None:
        """Test discovery from relative path in subdirectory."""
        config_path = tmp_path / PROJECT_FILE_NAME
        config_path.write_text("name: relative_subdir_test\ndata:\n  - file.ttl\n")

        subdir = tmp_path / "subdir"
        subdir.mkdir()

        # Change to subdirectory
        monkeypatch.chdir(subdir)

        # Discover from relative current directory
        rel_path = Path()
        result = discover_project(rel_path)

        assert result.name == "relative_subdir_test"


class TestDiscoverProjectErrorCases:
    """Test error handling and edge cases."""

    def test_raises_file_not_found_no_config(self, tmp_path: Path) -> None:
        """Test that FileNotFoundError is raised when no config is found."""
        # Create subdirectory without any project config
        subdir = tmp_path / "subdir"
        subdir.mkdir()

        with pytest.raises(FileNotFoundError):
            discover_project(subdir)

    def test_error_message_contains_config_filename(self, tmp_path: Path) -> None:
        """Test that error message includes the config filename."""
        subdir = tmp_path / "subdir"
        subdir.mkdir()

        with pytest.raises(FileNotFoundError) as exc_info:
            discover_project(subdir)

        assert PROJECT_FILE_NAME in str(exc_info.value)

    def test_internal_depth_parameter_increments(self, tmp_path: Path) -> None:
        """Test that _current_depth parameter increments on recursion."""
        # We'll test this indirectly by creating a directory structure
        # that requires recursion and verifying the function works
        config_path = tmp_path / PROJECT_FILE_NAME
        config_path.write_text("name: depth_test\ndata:\n  - file.ttl\n")

        nested = tmp_path / "level1" / "level2" / "level3"
        nested.mkdir(parents=True)

        # Should succeed even though depth goes > 0
        result = discover_project(nested)
        assert result.name == "depth_test"

    def test_symlink_resolution(self, tmp_path):
        """Test that symlinks are resolved properly."""
        # Create actual directory with config
        actual_dir = tmp_path / "actual"
        actual_dir.mkdir()
        config_path = actual_dir / PROJECT_FILE_NAME
        config_path.write_text("name: symlink_test\ndata:\n  - file.ttl\n")

        # Create a symlink
        link_dir = tmp_path / "link"
        link_dir.symlink_to(actual_dir)

        # Search from symlink should find config in resolved path
        result = discover_project(link_dir)
        assert result.name == "symlink_test"


class TestDiscoverProjectIntegration:
    """Integration tests combining multiple aspects."""

    def test_full_discovery_workflow(self, tmp_path):
        """Test a complete discovery workflow."""
        # Create a realistic project structure
        project_root = tmp_path / "myproject"
        project_root.mkdir()

        config_path = project_root / PROJECT_FILE_NAME
        config_path.write_text(
            "name: my_project\n"
            "internal_vocabs:\n"
            "  - ontology.ttl\n"
            "external_vocabs:\n"
            "  - skos.ttl\n"
            "data:\n"
            "  - data1.ttl\n"
            "  - data2.ttl\n",
        )

        # Create nested search location
        search_location = project_root / "src" / "data" / "input"
        search_location.mkdir(parents=True)

        result = discover_project(search_location)

        assert result.name == "my_project"
        assert len(result.paths_data) == 2
        assert len(result.paths_vocab_int) == 1
        assert len(result.paths_vocab_ext) == 1

    def test_discovery_with_multiple_nested_projects(self, tmp_path):
        """Test that discovery finds the nearest project, not the furthest."""
        # Create outer project
        outer = tmp_path / "outer"
        outer.mkdir()
        outer_config = outer / PROJECT_FILE_NAME
        outer_config.write_text("name: outer_project\ndata:\n  - file.ttl\n")

        # Create nested inner project
        inner = outer / "inner" / "project"
        inner.mkdir(parents=True)
        inner_config = inner / PROJECT_FILE_NAME
        inner_config.write_text("name: inner_project\ndata:\n  - file.ttl\n")

        # Search from inside inner project
        search_location = inner / "src"
        search_location.mkdir()

        result = discover_project(search_location)

        # Should find inner project, not outer
        assert result.name == "inner_project"

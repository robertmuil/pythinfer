"""Tests for project path resolution relative to project file location."""

from pathlib import Path
from tempfile import TemporaryDirectory

from pythinfer.inout import Project


class TestProjectPathResolution:
    """Test that paths in project files are resolved relative to the project file."""

    def test_paths_resolved_relative_to_project_file(self) -> None:
        """Test that relative paths are resolved to project file's directory."""
        with TemporaryDirectory() as tmpdir:
            tmpdir_path = Path(tmpdir).resolve()

            # Create directory structure:
            # tmpdir/
            #   projects/
            #     my-project/
            #       pythinfer.yaml
            #       data1.ttl
            #       data2.ttl
            projects_dir = tmpdir_path / "projects"
            projects_dir.mkdir()
            project_dir = projects_dir / "my-project"
            project_dir.mkdir()

            # Create dummy data files
            data1 = project_dir / "data1.ttl"
            data1.touch()
            data2 = project_dir / "data2.ttl"
            data2.touch()

            # Create project file with relative paths
            project_file = project_dir / "pythinfer.yaml"
            project_yaml = """\
name: my-project
data:
  - data1.ttl
  - data2.ttl
"""
            project_file.write_text(project_yaml)

            # Load the project from the subdir location
            project = Project.from_yaml(project_file)

            # Verify that paths are resolved to the project directory
            assert project.paths_data[0] == data1
            assert project.paths_data[1] == data2

    def test_paths_with_subdirectories(self) -> None:
        """Test that relative paths in subdirectories are resolved correctly."""
        with TemporaryDirectory() as tmpdir:
            tmpdir_path = Path(tmpdir).resolve()

            # Create structure:
            # tmpdir/
            #   projects/
            #     my-project/
            #       pythinfer.yaml
            #       data.ttl
            #       models/
            #         model.ttl
            projects_dir = tmpdir_path / "projects"
            projects_dir.mkdir()
            project_dir = projects_dir / "my-project"
            project_dir.mkdir()
            models_dir = project_dir / "models"
            models_dir.mkdir()

            # Create files
            data_file = project_dir / "data.ttl"
            data_file.touch()
            model_file = models_dir / "model.ttl"
            model_file.touch()

            # Create project file with relative paths
            project_file = project_dir / "pythinfer.yaml"
            project_yaml = """\
name: my-project
data:
  - data.ttl
  - models/model.ttl
"""
            project_file.write_text(project_yaml)

            # Load the project
            project = Project.from_yaml(project_file)

            # Verify paths are correct
            assert project.paths_data[0] == data_file
            assert project.paths_data[1] == model_file

    def test_absolute_paths_remain_unchanged(self) -> None:
        """Test that absolute paths are not modified during loading."""
        with TemporaryDirectory() as tmpdir:
            tmpdir_path = Path(tmpdir)

            # Create a project directory
            project_dir = tmpdir_path / "project"
            project_dir.mkdir()

            # Create an external data file outside the project
            external_dir = tmpdir_path / "external"
            external_dir.mkdir()
            external_file = external_dir / "external.ttl"
            external_file.touch()

            # Create project file with absolute path
            project_file = project_dir / "pythinfer.yaml"
            project_yaml = f"""\
name: my-project
data:
  - {external_file.as_posix()}
"""
            project_file.write_text(project_yaml)

            # Load the project
            project = Project.from_yaml(project_file)

            # Verify absolute path is preserved
            assert project.paths_data[0] == external_file

    def test_yaml_serialization_uses_relative_paths(self) -> None:
        """Test that YAML output uses relative paths when possible."""
        with TemporaryDirectory() as tmpdir:
            tmpdir_path = Path(tmpdir)

            # Create structure
            project_dir = tmpdir_path / "my-project"
            project_dir.mkdir()
            data_dir = project_dir / "data"
            data_dir.mkdir()

            # Create files
            data_file = data_dir / "data.ttl"
            data_file.touch()

            # Create project file
            project_file = project_dir / "pythinfer.yaml"
            original_yaml = """\
name: my-project
data:
  - data/data.ttl
"""
            project_file.write_text(original_yaml)

            # Load the project
            project = Project.from_yaml(project_file)

            # Get the YAML representation
            yaml_output = project.to_yaml()

            # The YAML should have relative paths
            assert "data/data.ttl" in yaml_output

    def test_yaml_serialization_uses_absolute_paths_for_external_files(
        self,
    ) -> None:
        """Test that YAML output uses absolute paths for external files."""
        with TemporaryDirectory() as tmpdir:
            tmpdir_path = Path(tmpdir)

            # Create structure
            project_dir = tmpdir_path / "project"
            project_dir.mkdir()

            # Create an external file outside the project
            external_dir = tmpdir_path / "external"
            external_dir.mkdir()
            external_file = external_dir / "external.ttl"
            external_file.touch()

            # Create project file with absolute path
            project_file = project_dir / "pythinfer.yaml"
            project_yaml = f"""\
name: my-project
data:
  - {external_file.as_posix()}
"""
            project_file.write_text(project_yaml)

            # Load the project
            project = Project.from_yaml(project_file)

            # Get the YAML representation
            yaml_output = project.to_yaml()

            # The YAML should have the absolute path for external files
            assert external_file.as_posix() in yaml_output

    def test_vocab_paths_also_resolved(self) -> None:
        """Test that vocabulary file paths are also resolved correctly."""
        with TemporaryDirectory() as tmpdir:
            tmpdir_path = Path(tmpdir).resolve()

            # Create structure
            project_dir = tmpdir_path / "project"
            project_dir.mkdir()
            data_dir = project_dir / "data"
            data_dir.mkdir()
            vocab_dir = project_dir / "vocab"
            vocab_dir.mkdir()

            # Create files
            data_file = data_dir / "data.ttl"
            data_file.touch()
            int_vocab_file = vocab_dir / "int.ttl"
            int_vocab_file.touch()
            ext_vocab_file = vocab_dir / "ext.ttl"
            ext_vocab_file.touch()

            # Create project file
            project_file = project_dir / "pythinfer.yaml"
            project_yaml = """\
name: my-project
data:
  - data/data.ttl
internal_vocabs:
  - vocab/int.ttl
external_vocabs:
  - vocab/ext.ttl
"""
            project_file.write_text(project_yaml)

            # Load the project
            project = Project.from_yaml(project_file)

            # Verify all paths are resolved correctly
            assert project.paths_data[0] == data_file
            assert project.paths_vocab_int[0] == int_vocab_file
            assert project.paths_vocab_ext[0] == ext_vocab_file

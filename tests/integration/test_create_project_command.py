"""Integration tests for the create_project command."""

from pathlib import Path
from tempfile import TemporaryDirectory

import pytest

from pythinfer.inout import PROJECT_FILE_NAME, Project, create_project


class TestCreateProjectCommand:
    """Test the create_project command functionality."""

    def test_create_project_scans_current_directory_for_rdf_files(
        self,
    ) -> None:
        """Test that create_project scans directory and detects RDF files."""
        with TemporaryDirectory() as tmpdir:
            tmp_path = Path(tmpdir)

            # Create test RDF files with different extensions
            ttl_file1 = tmp_path / "model.ttl"
            ttl_file1.touch()

            ttl_file2 = tmp_path / "data.ttl"
            ttl_file2.touch()

            rdf_file = tmp_path / "vocab.rdf"
            rdf_file.touch()

            # Create a non-RDF file that should be ignored
            txt_file = tmp_path / "readme.txt"
            txt_file.touch()

            # Call create_project with explicit scan_directory
            project = create_project(
                scan_directory=tmp_path,
                output_path=tmp_path / PROJECT_FILE_NAME,
            )

            # Verify config file was created
            assert project.path_self.exists()
            assert project.path_self.name == PROJECT_FILE_NAME

            # Should find all RDF files
            found_files = {str(p) for p in project.paths_data}
            assert (
                "model.ttl" in found_files
                or str(ttl_file1.relative_to(tmp_path)) in found_files
            )
            assert (
                "data.ttl" in found_files
                or str(ttl_file2.relative_to(tmp_path)) in found_files
            )
            assert (
                "vocab.rdf" in found_files
                or str(rdf_file.relative_to(tmp_path)) in found_files
            )

            # Should not include non-RDF files
            assert not any("readme.txt" in str(f) for f in found_files)

    def test_create_project_with_eg0_example(self) -> None:
        """Test create_project using the eg0-basic example project."""
        eg0_path = (
            Path(__file__).parent.parent.parent / "example_projects" / "eg0-basic"
        )

        # Path to expected output
        expected_config_path = eg0_path / "expected_pythinfer.yaml"
        if not expected_config_path.exists():
            pytest.skip("expected_pythinfer.yaml not found in eg0-basic")

        with TemporaryDirectory() as tmpdir:
            tmp_path = Path(tmpdir)

            # Create output directory for generated project
            output_dir = tmp_path / "generated_project"
            output_dir.mkdir()

            # Call create_project to scan eg0-basic
            project_generated = create_project(
                scan_directory=eg0_path,
                output_path=output_dir / PROJECT_FILE_NAME,
            )

            # Verify config file was created
            assert project_generated.path_self.exists()
            assert project_generated.path_self.name == PROJECT_FILE_NAME

            # Load the expected project specification
            project_expected = Project.from_yaml(expected_config_path)

            # Compare the configurations
            assert project_generated.to_yaml() == project_expected.to_yaml()

    def test_create_project_generates_valid_yaml(self) -> None:
        """Test that create_project generates valid YAML that can be loaded."""
        with TemporaryDirectory() as tmpdir:
            tmp_path = Path(tmpdir)

            # Create some RDF files
            (tmp_path / "data1.ttl").touch()
            (tmp_path / "vocab.rdf").touch()

            # Create project
            create_project(
                scan_directory=tmp_path,
                output_path=tmp_path / PROJECT_FILE_NAME,
            )

    def test_create_project_respects_output_path(self) -> None:
        """Test that create_project creates file at specified output path."""
        with TemporaryDirectory() as tmpdir:
            tmp_path = Path(tmpdir)

            # Create a subdirectory for output
            output_dir = tmp_path / "config"
            output_dir.mkdir()

            # Create some RDF files in parent directory
            (tmp_path / "data.ttl").touch()

            # Specify custom output path
            custom_config_path = output_dir / "custom.yaml"
            project = create_project(
                scan_directory=tmp_path,
                output_path=custom_config_path,
            )

            # Should create file at custom location
            assert project.path_self == custom_config_path
            assert project.path_self.exists()

    def test_create_project_handles_nested_directories(self) -> None:
        """Test that create_project scans nested directories for RDF files."""
        with TemporaryDirectory() as tmpdir:
            tmp_path = Path(tmpdir)

            # Create nested structure
            subdir1 = tmp_path / "models"
            subdir1.mkdir()
            (subdir1 / "model1.ttl").touch()

            subdir2 = tmp_path / "data"
            subdir2.mkdir()
            (subdir2 / "data1.rdf").touch()

            # Create project
            project = create_project(
                scan_directory=tmp_path,
                output_path=tmp_path / PROJECT_FILE_NAME,
            )

            file_names = [f.stem for f in project.paths_data]

            # Should find files in subdirectories
            assert any("model1" in f for f in file_names) or any(
                "data1" in f for f in file_names
            )

    def test_create_project_with_no_rdf_files(self) -> None:
        """Test create_project behavior when no RDF files are found."""
        with TemporaryDirectory() as tmpdir:
            tmp_path = Path(tmpdir)

            # Create only non-RDF files
            (tmp_path / "readme.txt").touch()
            (tmp_path / "notes.md").touch()

            # Should fail with FileNotFoundError
            with pytest.raises(FileNotFoundError):
                create_project(
                    scan_directory=tmp_path,
                    output_path=tmp_path / PROJECT_FILE_NAME,
                )

    def test_create_project_excludes_derived_output(self) -> None:
        """Test that create_project excludes the 'derived' directory."""
        with TemporaryDirectory() as tmpdir:
            tmp_path = Path(tmpdir)

            # Create RDF files in root
            (tmp_path / "data.ttl").touch()

            # Create a 'derived' directory with output files
            derived_dir = tmp_path / "derived"
            derived_dir.mkdir()
            (derived_dir / "inference_output.ttl").touch()

            # Create project
            project = create_project(output_path=tmp_path / PROJECT_FILE_NAME)

            # Should not include files from 'derived' directory
            assert not any("derived" in str(f) for f in project.paths_data)

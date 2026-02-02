"""Integration tests for cache isolation with multiple project files."""

import os
import shutil
from pathlib import Path

import pytest

from pythinfer.infer import load_cache, run_inference_backend
from pythinfer.inout import COMBINED_FULL_FILESTEM, load_project
from pythinfer.merge import merge_graphs

PROJECT_ROOT = Path(__file__).parent.parent.parent


class TestCacheIsolation:
    """Test that different project files in the same directory have isolated caches."""

    @pytest.fixture
    def eg0_temp_dir(self, tmp_path: Path) -> Path:
        """Create temporary copy of eg0-basic to avoid modifying the repository."""
        shutil.copytree(
            PROJECT_ROOT / "example_projects" / "eg0-basic", tmp_path / "eg0-basic"
        )

        return tmp_path / "eg0-basic"

    def test_separate_cache_directories_for_different_projects(
        self, eg0_temp_dir: Path
    ) -> None:
        """Test that different project files create separate cache directories.

        This verifies the fix for the bug where --project argument would use
        the wrong cache if a cache existed for the default pythinfer.yaml.
        """
        # Verify example project exists and has both config files
        default_config = eg0_temp_dir / "pythinfer.yaml"
        celebrity_config = eg0_temp_dir / "pythinfer_celebrity.yaml"

        assert default_config.exists(), "pythinfer.yaml not found"
        assert celebrity_config.exists(), "pythinfer_celebrity.yaml not found"

        # Load both projects
        default_project = load_project(default_config)
        celebrity_project = load_project(celebrity_config)

        # Verify they have different output paths based on project file stem
        default_output = default_project.path_output
        celebrity_output = celebrity_project.path_output

        assert default_output == eg0_temp_dir / "derived" / "pythinfer"
        assert celebrity_output == eg0_temp_dir / "derived" / "pythinfer_celebrity"
        assert default_output != celebrity_output

    def test_different_inference_results_with_different_projects(
        self, eg0_temp_dir: Path
    ) -> None:
        """Test that different project files produce different inference results.

        The celebrity project includes an additional SPARQL inference rule
        that the default project does not, so they should have different
        inferred triples and cache files.
        """
        original_cwd = Path.cwd()
        try:
            os.chdir(eg0_temp_dir)

            # Default project inference
            default_project = load_project(None)  # Uses discovery
            default_project.owl_backend = "owlrl"
            default_ds, default_external_ids = merge_graphs(
                default_project,
                output=True,
                export_external=False,
                extra_export_formats=None,
            )
            run_inference_backend(
                default_ds,
                default_external_ids,
                default_project,
                None,
                include_unwanted_triples=False,
                export_full=True,
                export_external_inferences=False,
                extra_export_formats=None,
            )
            default_count = len(default_ds)

            # Celebrity project inference
            celebrity_project = load_project(Path("pythinfer_celebrity.yaml"))
            celebrity_project.owl_backend = "owlrl"
            celebrity_ds, celebrity_external_ids = merge_graphs(
                celebrity_project,
                output=True,
                export_external=False,
                extra_export_formats=None,
            )
            run_inference_backend(
                celebrity_ds,
                celebrity_external_ids,
                celebrity_project,
                None,
                include_unwanted_triples=False,
                export_full=True,
                export_external_inferences=False,
                extra_export_formats=None,
            )
            celebrity_count = len(celebrity_ds)

            # Verify different numbers of triples (celebrity has more due
            # to extra inference)
            assert default_count > 0
            assert celebrity_count > 0
            assert celebrity_count > default_count, (
                f"Celebrity project should have more inferences ({celebrity_count}) "
                f"than default ({default_count})"
            )

            # Verify cache files exist in separate directories
            default_cache = (
                default_project.path_output / f"{COMBINED_FULL_FILESTEM}.trig"
            )
            celebrity_cache = (
                celebrity_project.path_output / f"{COMBINED_FULL_FILESTEM}.trig"
            )

            assert default_cache.exists(), (
                f"Default cache not found at {default_cache}"
            )
            assert celebrity_cache.exists(), (
                f"Celebrity cache not found at {celebrity_cache}"
            )

            # Verify they're in different directories
            assert default_cache.parent != celebrity_cache.parent

        finally:
            os.chdir(original_cwd)

    def test_cache_not_mixed_between_projects(self, eg0_temp_dir: Path) -> None:
        """Test that loading project doesn't confuse caches between projects.

        This is the specific bug scenario: if we run infer with default project,
        then run infer with celebrity project, the celebrity project should not
        load the default project's cache.
        """
        original_cwd = Path.cwd()
        try:
            os.chdir(eg0_temp_dir)

            # Step 1: Run inference for default project (creates cache)
            default_project = load_project(None)
            default_project.owl_backend = "owlrl"
            default_ds, default_external_ids = merge_graphs(
                default_project,
                output=True,
                export_external=False,
            )
            run_inference_backend(
                default_ds,
                default_external_ids,
                default_project,
                None,
                include_unwanted_triples=False,
                export_full=True,
                export_external_inferences=False,
            )

            # Verify default cache was created
            default_cache = load_cache(default_project)
            assert default_cache is not None, (
                "Default project cache should exist"
            )
            default_triple_count = len(default_cache)

            # Step 2: Load celebrity project and verify it doesn't use
            # default cache
            celebrity_project = load_project(Path("pythinfer_celebrity.yaml"))
            celebrity_cache = load_cache(celebrity_project)

            # If cache was incorrectly shared, this assertion would fail
            # because celebrity cache would have same triple count as default
            if celebrity_cache is not None:
                celebrity_triple_count = len(celebrity_cache)
                # Celebrity has more triples due to additional inference
                assert celebrity_triple_count > default_triple_count, (
                    f"Celebrity cache should have more triples "
                    f"({celebrity_triple_count}) than default "
                    f"({default_triple_count}), but got fewer. "
                    f"This suggests the wrong cache is being used."
                )
        finally:
            os.chdir(original_cwd)

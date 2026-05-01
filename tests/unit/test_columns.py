"""Tests for the equitable column width distribution algorithm."""

import pytest

from pythinfer.tui.columns import clip_middle, distribute_column_widths


class TestDistributeColumnWidths:
    """Tests for distribute_column_widths()."""

    def test_all_fit(self) -> None:
        """When all columns fit naturally, no clipping needed."""
        result = distribute_column_widths([5, 10, 8], available=30, separator_width=1)
        assert result == [5, 10, 8]

    def test_one_dominant(self) -> None:
        """One huge column gets shrunk; smaller columns keep natural width."""
        # available=30, sep=3 each → usable=30-6=24, 3 cols
        # natural: [5, 5, 200]
        # fair_share = 24/3 = 8 → cols 0,1 settle at 5 each
        # remaining usable = 24-10 = 14 → col 2 gets 14
        result = distribute_column_widths([5, 5, 200], available=30, separator_width=3)
        assert result == [5, 5, 14]

    def test_all_oversized(self) -> None:
        """All columns too wide → equal distribution."""
        # available=30, sep=3 → usable=24, 3 cols → 8 each
        result = distribute_column_widths([100, 100, 100], available=30, separator_width=3)
        assert result == [8, 8, 8]

    def test_single_column(self) -> None:
        result = distribute_column_widths([50], available=40, separator_width=3)
        assert result == [40]

    def test_empty(self) -> None:
        assert distribute_column_widths([], available=80) == []

    def test_min_width_enforced(self) -> None:
        """Columns never go below min_width."""
        result = distribute_column_widths([100, 100, 100], available=12, separator_width=3, min_width=3)
        # usable = 12-6 = 6, fair_share = max(3, 6//3) = 3
        assert all(w >= 3 for w in result)

    def test_redistribution(self) -> None:
        """Space freed by small columns goes to oversized ones."""
        # available=40, sep=3 → usable=40-6=34
        # natural: [3, 3, 200]
        # round 1: fair_share=34/3=11, cols 0,1 settle at 3
        # round 2: remaining=34-6=28, col 2 gets 28
        result = distribute_column_widths([3, 3, 200], available=40, separator_width=3)
        assert result == [3, 3, 28]

    def test_two_oversized_one_small(self) -> None:
        """Two oversized columns share remaining space after small one settles."""
        # available=40, sep=3 → usable=34
        # natural: [4, 100, 100]
        # round 1: fair_share=34/3=11, col 0 settles at 4
        # round 2: remaining=30, fair_share=30/2=15 → cols 1,2 each get 15
        result = distribute_column_widths([4, 100, 100], available=40, separator_width=3)
        assert result == [4, 15, 15]


class TestClipMiddle:
    """Tests for clip_middle()."""

    def test_no_clip_needed(self) -> None:
        assert clip_middle("hello", 10) == "hello"

    def test_exact_fit(self) -> None:
        assert clip_middle("hello", 5) == "hello"

    def test_clip(self) -> None:
        result = clip_middle("abcdefghij", 6)
        # left = (6-2)//2 = 2, right = 6-2-2 = 2
        assert result == "ab..ij"
        assert len(result) == 6

    def test_clip_odd_width(self) -> None:
        result = clip_middle("abcdefghij", 7)
        # left = (7-2)//2 = 2, right = 7-2-2 = 3
        assert result == "ab..hij"
        assert len(result) == 7

    def test_very_narrow(self) -> None:
        """Width too small for clip marker → simple truncation."""
        assert clip_middle("abcdefgh", 3) == "abc"

    def test_width_4(self) -> None:
        """Minimum width for clip marker."""
        result = clip_middle("abcdefgh", 4)
        # left = (4-2)//2 = 1, right = 4-2-1 = 1
        assert result == "a..h"
        assert len(result) == 4

    def test_empty_string(self) -> None:
        assert clip_middle("", 5) == ""

    def test_width_zero(self) -> None:
        assert clip_middle("hello", 0) == ""

    @pytest.mark.parametrize("width", range(1, 20))
    def test_output_length_never_exceeds_max(self, width: int) -> None:
        text = "a" * 30
        result = clip_middle(text, width)
        assert len(result) <= width

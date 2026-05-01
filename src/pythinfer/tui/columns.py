"""Equitable column width distribution and middle-clipping utilities."""

_MIN_COL_WIDTH = 3
_CLIP_MARKER = ".."
_CLIP_MARKER_LEN = len(_CLIP_MARKER)


def distribute_column_widths(
    natural_widths: list[int],
    available: int,
    separator_width: int = 3,
    min_width: int = _MIN_COL_WIDTH,
) -> list[int]:
    """Distribute *available* terminal width equitably across columns.

    Columns whose natural (max-content) width fits within a fair share
    keep their natural width.  The remaining space is redistributed
    among the oversized columns.  Every column gets at least *min_width*.

    Parameters
    ----------
    natural_widths:
        The max-content width of each column.
    available:
        Total available character width (e.g. terminal width).
    separator_width:
        Characters consumed by each inter-column separator.
    min_width:
        Minimum width any column may be assigned.

    Returns
    -------
    list[int]
        Allocated width for each column.
    """
    n = len(natural_widths)
    if n == 0:
        return []

    total_sep = separator_width * (n - 1)
    usable = max(0, available - total_sep)

    allocated = [0] * n
    settled = [False] * n

    while True:
        remaining = sum(1 for s in settled if not s)
        if remaining == 0:
            break
        space_left = usable - sum(allocated[i] for i in range(n) if settled[i])
        fair_share = max(min_width, space_left // max(1, remaining))

        changed = False
        for i in range(n):
            if settled[i]:
                continue
            if natural_widths[i] <= fair_share:
                allocated[i] = natural_widths[i]
                settled[i] = True
                changed = True

        if not changed:
            # All remaining columns are oversized — give each the fair share
            for i in range(n):
                if not settled[i]:
                    allocated[i] = max(min_width, fair_share)
                    settled[i] = True
            break

    return allocated


def clip_middle(text: str, max_width: int) -> str:
    """Clip *text* in the middle if it exceeds *max_width*.

    Replaces the middle portion with ``..`` so that the beginning and
    end of the string are preserved.  If *max_width* is too small for
    the clip marker, the text is simply truncated from the right.
    """
    if len(text) <= max_width:
        return text
    if max_width < _CLIP_MARKER_LEN + 2:  # noqa: PLR2004
        return text[:max_width]
    left = (max_width - _CLIP_MARKER_LEN) // 2
    right = max_width - _CLIP_MARKER_LEN - left
    return text[:left] + _CLIP_MARKER + text[-right:]

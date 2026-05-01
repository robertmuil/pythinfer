"""TUI backends for pythinfer interactive query interface."""

import curses
import enum
import logging
from pathlib import Path

from rdflib import Dataset

logger = logging.getLogger(__name__)


class TuiBackend(enum.StrEnum):
    """Available TUI backend implementations."""

    auto = "auto"
    textual = "textual"
    prompt_toolkit = "prompt-toolkit"
    curses = "curses"


def launch_query_tui(
    ds: Dataset,
    num_triples: int,
    project_dir: Path,
    backend: TuiBackend = TuiBackend.auto,
) -> None:
    """Launch the interactive query TUI with the specified backend.

    When *backend* is ``auto``, tries Textual first, then prompt-toolkit,
    then falls back to curses.  When an explicit backend is requested but
    its dependency is not installed, the ImportError propagates.
    """
    if backend == TuiBackend.textual:
        from pythinfer.tui.query_tui_textual import interactive_query_textual

        interactive_query_textual(ds, num_triples, project_dir)
    elif backend == TuiBackend.prompt_toolkit:
        from pythinfer.tui.query_tui_pt import interactive_query_pt

        interactive_query_pt(ds, num_triples, project_dir)
    elif backend == TuiBackend.curses:
        from pythinfer.tui.query_tui import interactive_query

        curses.wrapper(
            lambda stdscr: interactive_query(stdscr, ds, num_triples, project_dir),
        )
    else:
        # Auto: try best available, fall back gracefully
        try:
            from pythinfer.tui.query_tui_textual import interactive_query_textual

            logger.info("Using Textual TUI backend")
            interactive_query_textual(ds, num_triples, project_dir)
        except ImportError:
            logger.info("Textual not available, trying prompt-toolkit")
            try:
                from pythinfer.tui.query_tui_pt import interactive_query_pt

                logger.info("Using prompt-toolkit TUI backend")
                interactive_query_pt(ds, num_triples, project_dir)
            except ImportError:
                logger.info("prompt-toolkit not available, using curses")
                from pythinfer.tui.query_tui import interactive_query

                curses.wrapper(
                    lambda stdscr: interactive_query(
                        stdscr, ds, num_triples, project_dir,
                    ),
                )

"""Local diagnostics and Tk callback error handling."""

from __future__ import annotations

import logging
from logging.handlers import RotatingFileHandler
from pathlib import Path
from types import TracebackType
from typing import Any


def configure_logging(data_dir: str | Path) -> tuple[logging.Logger, Path]:
    log_path = Path(data_dir) / "better-together.log"
    log_path.parent.mkdir(parents=True, exist_ok=True)
    logger = logging.getLogger("better_together")
    logger.setLevel(logging.INFO)
    logger.propagate = False
    if not any(
        isinstance(handler, RotatingFileHandler)
        and Path(handler.baseFilename) == log_path.resolve()
        for handler in logger.handlers
    ):
        handler = RotatingFileHandler(
            log_path,
            maxBytes=1_000_000,
            backupCount=2,
            encoding="utf-8",
        )
        handler.setFormatter(
            logging.Formatter("%(asctime)s %(levelname)s %(name)s: %(message)s")
        )
        logger.addHandler(handler)
    return logger, log_path


def install_tk_exception_handler(
    root: Any, logger: logging.Logger, log_path: Path
) -> None:
    """Turn otherwise-console-only Tk callback failures into actionable errors."""

    def report(
        exception_type: type[BaseException],
        exception: BaseException,
        traceback: TracebackType | None,
    ) -> None:
        logger.error(
            "Unhandled Tk callback error",
            exc_info=(exception_type, exception, traceback),
        )
        from tkinter import messagebox

        messagebox.showerror(
            "Unexpected Error",
            "Better Together encountered an unexpected error. "
            f"Details were written to:\n{log_path}",
            parent=root,
        )

    root.report_callback_exception = report

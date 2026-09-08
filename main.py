import argparse
import logging
import tkinter as tk
from tkinter import messagebox

from better_together import __version__
from better_together.app import EGSApp
from better_together.config import AppPaths
from better_together.constants import APP_NAME
from better_together.diagnostics import configure_logging, install_tk_exception_handler
from better_together.manager import EGSManager, ManagerError


def _show_startup_error(message):
    root = tk.Tk()
    root.withdraw()
    messagebox.showerror(APP_NAME, message)
    root.destroy()


def main(argv=None):
    parser = argparse.ArgumentParser(description=APP_NAME)
    parser.add_argument(
        "--version",
        action="version",
        version=f"%(prog)s {__version__}",
    )
    parser.parse_args(argv)

    paths = AppPaths.for_current_user()
    logger = logging.getLogger("better_together")
    try:
        logger, log_path = configure_logging(paths.data_dir)
        logger.info("Starting Better Together %s", __version__)
        app = EGSApp(manager=EGSManager(paths))
        install_tk_exception_handler(app, logger, log_path)
    except ManagerError as exc:
        logger.error("Startup failed: %s", exc)
        _show_startup_error(str(exc))
        return
    except Exception:
        logger.exception("Unexpected startup failure")
        _show_startup_error(
            "Better Together could not start. See the local diagnostic log for details."
        )
        return
    app.mainloop()


if __name__ == "__main__":
    main()

"""Application-specific exceptions.

Keeping errors independent from UI and service modules prevents circular imports and
lets callers consistently present friendly messages at the application boundary.
"""


class ManagerError(Exception):
    """A recoverable launcher error that is safe to show to the user."""


class ConfigurationError(ManagerError):
    """The persisted application configuration is unreadable or invalid."""


class OperationCancelled(ManagerError):
    """A background operation was intentionally cancelled by the user."""

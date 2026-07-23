"""Shared error contract for grab: one exception, distinct exit codes per failure class."""

EXIT_UNEXPECTED = 1
EXIT_USAGE = 2
EXIT_NO_CAPTIONS = 3
EXIT_BLOCKED = 4
EXIT_UNAVAILABLE = 5
EXIT_WEBSITE_FAILED = 6


class GrabError(Exception):
    """Known fetch failure: message goes to stderr, exit_code to the shell."""

    def __init__(self, message, exit_code):
        super().__init__(message)
        self.exit_code = exit_code

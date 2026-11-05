"""Shared error contract for rawfetch: one exception, distinct exit codes per failure class."""
from urllib.request import getproxies_environment

EXIT_UNEXPECTED = 1
EXIT_USAGE = 2
EXIT_NO_CAPTIONS = 3
EXIT_BLOCKED = 4
EXIT_UNAVAILABLE = 5
EXIT_WEBSITE_FAILED = 6
EXIT_NETWORK = 7
EXIT_NOT_INSTALLED = 8  # an optional source (Reddit) was asked for but is not installed


class RawfetchError(Exception):
    """Known fetch failure: message goes to stderr, exit_code to the shell."""

    def __init__(self, message, exit_code):
        super().__init__(message)
        self.exit_code = exit_code


def network_error(exc):
    """RawfetchError for a transport failure: DNS, refused connection, timeout, dead proxy.

    Distinct from "reached the source and it said no": exit 7 means the request never
    got an answer at all. When env proxies (HTTPS_PROXY/HTTP_PROXY) are in effect the
    message says so, because a broken proxy is the most likely culprit then — but only
    the scheme names are printed: proxy URLs routinely carry user:pass credentials.
    """
    schemes = sorted(getproxies_environment())
    hint = ("; note: a proxy from the environment is in effect for: "
            + ", ".join(schemes)) if schemes else ""
    return RawfetchError(
        "network error: could not reach the source: {}{}".format(exc, hint),
        EXIT_NETWORK)

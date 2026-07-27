#!/usr/bin/env python3
"""Website adapter for rawfetch: quiet fallback for static articles.

WHY: not the headline (AI assistants already fetch the web) — kept so `rawfetch <any-url>`
still answers with verbatim article text. Static pages only: JS-heavy SPAs and paywalls
may extract to nothing, and that is reported as an honest error, never invented text.

The body is read with a hard byte cap. Without one, a large page is a memory bomb: article
extraction allocates many times the input size, so an unbounded read turns a fat URL into
gigabytes of RSS and minutes of CPU. A cap fails fast and honestly instead.
"""
import requests
import trafilatura

from rawfetch.errors import RawfetchError, network_error, EXIT_WEBSITE_FAILED

UA = ("Mozilla/5.0 (Macintosh; Intel Mac OS X 10_15_7) AppleWebKit/605.1.15 "
      "(KHTML, like Gecko) Version/17.0 Safari/605.1.15")

MAX_BYTES = 5 * 1024 * 1024  # 5 MiB of HTML is a very long article already
CHUNK = 64 * 1024


def fetch(url):
    """Return {"title": str|None, "text": str}. Raises RawfetchError on failure."""
    try:
        resp = requests.get(url, timeout=30, headers={"User-Agent": UA}, stream=True)
    except requests.RequestException as e:
        # Transport failure = exit 7, same as the YouTube path: "could not reach the
        # site" is a different fact than "reached it, nothing extractable" (exit 6).
        raise network_error(e)
    # Closed explicitly: with stream=True the connection stays checked out of the pool
    # until the body is drained or the response is closed, and the size cap deliberately
    # stops draining early.
    try:
        if not 200 <= resp.status_code < 300:
            raise RawfetchError(
                "website fetch failed: HTTP {}".format(resp.status_code),
                EXIT_WEBSITE_FAILED)
        payload = _read_capped(resp)
    finally:
        resp.close()
    text = extract_text(payload)
    if not text:
        raise RawfetchError(
            "website fetch failed: no article text extracted "
            "(JS-heavy or paywalled pages are out of scope)", EXIT_WEBSITE_FAILED)
    return {"title": _title(payload), "text": text}


def _read_capped(resp):
    """Body for the extractor, refusing anything over MAX_BYTES instead of buffering it.

    Returns str when the server declared a charset, raw bytes otherwise. Never touches
    resp.apparent_encoding: that property reads resp.content, which raises once the body
    has been consumed by iter_content, so using it as a fallback turns a missing
    Content-Type into an unexpected error. Undeclared bytes go to trafilatura instead,
    which reads the document's own meta charset and defaults to UTF-8.
    """
    declared = resp.headers.get("Content-Length") if resp.headers else None
    if declared and declared.isdigit() and int(declared) > MAX_BYTES:
        raise RawfetchError(_too_large(int(declared)), EXIT_WEBSITE_FAILED)
    chunks = []
    total = 0
    try:
        for chunk in resp.iter_content(chunk_size=CHUNK):
            if not chunk:
                continue
            total += len(chunk)
            if total > MAX_BYTES:
                raise RawfetchError(_too_large(None), EXIT_WEBSITE_FAILED)
            chunks.append(chunk)
    except requests.RequestException as e:
        # Connection dying mid-body is still a transport failure.
        raise network_error(e)
    raw = b"".join(chunks)
    if resp.encoding:
        # Header charset wins: it is what the server says the bytes are. Bytes that do
        # not fit it become U+FFFD rather than killing the run — documented in the README
        # so "verbatim" does not quietly mean "verbatim except where it wasn't".
        return raw.decode(resp.encoding, errors="replace")
    return raw


def _too_large(size):
    limit = MAX_BYTES // (1024 * 1024)
    seen = " ({} bytes declared)".format(size) if size else ""
    return ("website fetch failed: page larger than {} MiB{} — refusing to buffer it "
            "(rawfetch targets articles, not bulk downloads)".format(limit, seen))


def extract_text(html):
    """Verbatim main text via trafilatura; None when nothing extractable."""
    return trafilatura.extract(html)


def _title(html):
    """Page title from trafilatura metadata; any failure -> None, never fatal."""
    try:
        meta = trafilatura.extract_metadata(html)
        return meta.title if meta else None
    except Exception:
        return None

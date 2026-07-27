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

from rawfetch.errors import RawfetchError, EXIT_WEBSITE_FAILED

UA = ("Mozilla/5.0 (Macintosh; Intel Mac OS X 10_15_7) AppleWebKit/605.1.15 "
      "(KHTML, like Gecko) Version/17.0 Safari/605.1.15")

MAX_BYTES = 5 * 1024 * 1024  # 5 MiB of HTML is a very long article already
CHUNK = 64 * 1024


def fetch(url):
    """Return {"title": str|None, "text": str}. Raises RawfetchError on failure."""
    try:
        resp = requests.get(url, timeout=30, headers={"User-Agent": UA}, stream=True)
    except requests.RequestException as e:
        raise RawfetchError("website fetch failed: {}".format(e), EXIT_WEBSITE_FAILED)
    if not 200 <= resp.status_code < 300:
        raise RawfetchError(
            "website fetch failed: HTTP {}".format(resp.status_code),
            EXIT_WEBSITE_FAILED)
    html = _read_capped(resp)
    text = extract_text(html)
    if not text:
        raise RawfetchError(
            "website fetch failed: no article text extracted "
            "(JS-heavy or paywalled pages are out of scope)", EXIT_WEBSITE_FAILED)
    return {"title": _title(html), "text": text}


def _read_capped(resp):
    """Body as text, refusing anything over MAX_BYTES instead of buffering it."""
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
        raise RawfetchError("website fetch failed: {}".format(e), EXIT_WEBSITE_FAILED)
    raw = b"".join(chunks)
    encoding = resp.encoding or getattr(resp, "apparent_encoding", None) or "utf-8"
    return raw.decode(encoding, errors="replace")


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

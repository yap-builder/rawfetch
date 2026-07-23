#!/usr/bin/env python3
"""Website adapter for grab: quiet fallback for static articles.

WHY: not the headline (AI assistants already fetch the web) — kept so `grab <any-url>`
still answers with verbatim article text. Static pages only: JS-heavy SPAs and paywalls
may extract to nothing, and that is reported as an honest error, never invented text.
"""
import requests
import trafilatura

from errors import GrabError, EXIT_WEBSITE_FAILED

UA = ("Mozilla/5.0 (Macintosh; Intel Mac OS X 10_15_7) AppleWebKit/605.1.15 "
      "(KHTML, like Gecko) Version/17.0 Safari/605.1.15")


def fetch(url):
    """Return {"title": str|None, "text": str}. Raises GrabError on failure."""
    try:
        resp = requests.get(url, timeout=30, headers={"User-Agent": UA})
    except requests.RequestException as e:
        raise GrabError("website fetch failed: {}".format(e), EXIT_WEBSITE_FAILED)
    if not 200 <= resp.status_code < 300:
        raise GrabError("website fetch failed: HTTP {}".format(resp.status_code),
                        EXIT_WEBSITE_FAILED)
    text = extract_text(resp.text)
    if not text:
        raise GrabError(
            "website fetch failed: no article text extracted "
            "(JS-heavy or paywalled pages are out of scope)", EXIT_WEBSITE_FAILED)
    return {"title": _title(resp.text), "text": text}


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

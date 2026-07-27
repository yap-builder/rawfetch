"""Offline tests for the website adapter: committed real fixture, mocked HTTP."""
import os

import pytest

from rawfetch import website_fetch
from rawfetch.errors import RawfetchError

FIXTURE = os.path.join(os.path.dirname(__file__), "tests", "fixtures", "article.html")


def fixture_html():
    with open(FIXTURE, encoding="utf-8") as f:
        return f.read()


class FakeResp:
    """Mimics the streamed response rawfetch actually consumes."""

    def __init__(self, status_code, text="", headers=None, encoding="utf-8"):
        self.status_code = status_code
        enc = encoding or "utf-8"
        self._body = text.encode(enc) if isinstance(text, str) else text
        self.headers = headers if headers is not None else {}
        self.encoding = encoding
        self.closed = False

    def iter_content(self, chunk_size=1):
        for i in range(0, len(self._body), chunk_size):
            yield self._body[i:i + chunk_size]

    def close(self):
        self.closed = True


def test_extract_text_from_real_article():
    text = website_fetch.extract_text(fixture_html())
    assert text and "Beautiful is better than ugly" in text


def test_fetch_happy_path(monkeypatch):
    monkeypatch.setattr(website_fetch.requests, "get",
                        lambda *a, **k: FakeResp(200, fixture_html()))
    out = website_fetch.fetch("https://example.com/article")
    assert "Beautiful is better than ugly" in out["text"]
    assert "title" in out


def test_http_error_exit6(monkeypatch):
    monkeypatch.setattr(website_fetch.requests, "get",
                        lambda *a, **k: FakeResp(404, "nope"))
    with pytest.raises(RawfetchError) as ei:
        website_fetch.fetch("https://example.com/gone")
    assert ei.value.exit_code == 6


def test_network_error_exit6(monkeypatch):
    def boom(*a, **k):
        raise website_fetch.requests.ConnectionError("refused")
    monkeypatch.setattr(website_fetch.requests, "get", boom)
    with pytest.raises(RawfetchError) as ei:
        website_fetch.fetch("https://example.com/x")
    assert ei.value.exit_code == 6


def test_empty_extraction_exit6(monkeypatch):
    monkeypatch.setattr(
        website_fetch.requests, "get",
        lambda *a, **k: FakeResp(200, "<html><body><script>1</script></body></html>"))
    with pytest.raises(RawfetchError) as ei:
        website_fetch.fetch("https://example.com/spa")
    assert ei.value.exit_code == 6


def test_declared_oversize_refused_without_reading(monkeypatch):
    """Content-Length over the cap must fail before a single chunk is buffered."""
    class NeverRead(FakeResp):
        def iter_content(self, chunk_size=1):
            raise AssertionError("body must not be read when the size is declared")

    huge = str(website_fetch.MAX_BYTES + 1)
    monkeypatch.setattr(
        website_fetch.requests, "get",
        lambda *a, **k: NeverRead(200, "x", headers={"Content-Length": huge}))
    with pytest.raises(RawfetchError) as ei:
        website_fetch.fetch("https://example.com/huge")
    assert ei.value.exit_code == 6
    assert "larger than" in str(ei.value)


def test_streamed_oversize_refused(monkeypatch):
    """No Content-Length: the cap must still trip while streaming."""
    body = "a" * (website_fetch.MAX_BYTES + 1024)
    monkeypatch.setattr(website_fetch.requests, "get",
                        lambda *a, **k: FakeResp(200, body))
    with pytest.raises(RawfetchError) as ei:
        website_fetch.fetch("https://example.com/huge")
    assert ei.value.exit_code == 6
    assert "larger than" in str(ei.value)


def test_body_just_under_cap_is_accepted(monkeypatch):
    """The cap must not reject an ordinary long article."""
    padding = "<p>filler</p>" * 1000
    html = fixture_html() + padding
    assert len(html.encode("utf-8")) < website_fetch.MAX_BYTES
    monkeypatch.setattr(website_fetch.requests, "get",
                        lambda *a, **k: FakeResp(200, html))
    out = website_fetch.fetch("https://example.com/long")
    assert "Beautiful is better than ugly" in out["text"]


def test_non_utf8_body_decodes(monkeypatch):
    """Declared encoding is honoured rather than assumed."""
    html = "<html><body><article><p>Ünïcödé tëxt that is long enough to extract properly " \
           "so trafilatura keeps it as a real paragraph of content.</p></article></body></html>"
    monkeypatch.setattr(
        website_fetch.requests, "get",
        lambda *a, **k: FakeResp(200, html.encode("latin-1"), encoding="latin-1"))
    out = website_fetch.fetch("https://example.com/latin")
    assert "Ünïcödé" in out["text"]


def test_missing_content_type_does_not_crash(monkeypatch):
    """No charset from the server: bytes go to the extractor, not to apparent_encoding.

    Regression guard. apparent_encoding reads resp.content, which raises once the body
    has been streamed, so using it as a fallback turned a header-less response into an
    unexpected error instead of a normal fetch.
    """
    html = ("<html><body><article><p>" +
            "Real sentence with enough words to be extracted properly. " * 8 +
            "</p></article></body></html>")
    monkeypatch.setattr(website_fetch.requests, "get",
                        lambda *a, **k: FakeResp(200, html, encoding=None))
    out = website_fetch.fetch("https://example.com/no-ctype")
    assert "Real sentence" in out["text"]


def test_response_closed_even_when_cap_trips(monkeypatch):
    """stream=True holds the connection until close(); the cap stops draining early."""
    resp = FakeResp(200, "a" * (website_fetch.MAX_BYTES + 1024))
    monkeypatch.setattr(website_fetch.requests, "get", lambda *a, **k: resp)
    with pytest.raises(RawfetchError):
        website_fetch.fetch("https://example.com/huge")
    assert resp.closed


def test_response_closed_on_http_error(monkeypatch):
    resp = FakeResp(404, "nope")
    monkeypatch.setattr(website_fetch.requests, "get", lambda *a, **k: resp)
    with pytest.raises(RawfetchError):
        website_fetch.fetch("https://example.com/gone")
    assert resp.closed


def test_response_closed_on_success(monkeypatch):
    resp = FakeResp(200, fixture_html())
    monkeypatch.setattr(website_fetch.requests, "get", lambda *a, **k: resp)
    website_fetch.fetch("https://example.com/article")
    assert resp.closed

"""Offline tests for the website adapter: committed real fixture, mocked HTTP."""
import os

import pytest

import website_fetch
from errors import GrabError

FIXTURE = os.path.join(os.path.dirname(__file__), "tests", "fixtures", "article.html")


def fixture_html():
    with open(FIXTURE, encoding="utf-8") as f:
        return f.read()


class FakeResp:
    def __init__(self, status_code, text=""):
        self.status_code = status_code
        self.text = text


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
    with pytest.raises(GrabError) as ei:
        website_fetch.fetch("https://example.com/gone")
    assert ei.value.exit_code == 6


def test_network_error_exit6(monkeypatch):
    def boom(*a, **k):
        raise website_fetch.requests.ConnectionError("refused")
    monkeypatch.setattr(website_fetch.requests, "get", boom)
    with pytest.raises(GrabError) as ei:
        website_fetch.fetch("https://example.com/x")
    assert ei.value.exit_code == 6


def test_empty_extraction_exit6(monkeypatch):
    monkeypatch.setattr(website_fetch.requests, "get",
                        lambda *a, **k: FakeResp(200, "<html><body><script>1</script></body></html>"))
    with pytest.raises(GrabError) as ei:
        website_fetch.fetch("https://example.com/spa")
    assert ei.value.exit_code == 6

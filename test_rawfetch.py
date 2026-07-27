"""Offline tests for routing and the CLI contract (adapters mocked)."""
import json

import pytest

from rawfetch import cli
from rawfetch.errors import RawfetchError


@pytest.mark.parametrize("url,vid", [
    ("https://www.youtube.com/watch?v=dQw4w9WgXcQ", "dQw4w9WgXcQ"),
    ("https://youtube.com/watch?foo=1&v=dQw4w9WgXcQ", "dQw4w9WgXcQ"),
    ("https://youtu.be/dQw4w9WgXcQ", "dQw4w9WgXcQ"),
    ("https://m.youtube.com/watch?v=dQw4w9WgXcQ", "dQw4w9WgXcQ"),
    ("https://music.youtube.com/watch?v=dQw4w9WgXcQ", "dQw4w9WgXcQ"),
    ("https://www.youtube.com/shorts/dQw4w9WgXcQ", "dQw4w9WgXcQ"),
    ("https://www.youtube.com/live/dQw4w9WgXcQ", "dQw4w9WgXcQ"),
    ("https://www.youtube.com/embed/dQw4w9WgXcQ", "dQw4w9WgXcQ"),
])
def test_route_youtube(url, vid):
    assert cli.route(url) == ("youtube", vid)


@pytest.mark.parametrize("url", [
    "https://example.com/article",
    "http://blog.example.org/post?v=dQw4w9WgXcQ",   # v= param on non-youtube host
    "https://myyoutube.com/watch?v=dQw4w9WgXcQ",     # lookalike host
])
def test_route_website(url):
    assert cli.route(url) == ("website", None)


@pytest.mark.parametrize("url", [
    "ftp://example.com/x",
    "not a url",
    "https://www.youtube.com/feed/history",          # youtube host, no video id
])
def test_route_rejects_exit2(url):
    with pytest.raises(RawfetchError) as ei:
        cli.route(url)
    assert ei.value.exit_code == 2


def test_main_plain_prints_only_text(monkeypatch, capsys):
    monkeypatch.setattr(cli.website_fetch, "fetch",
                        lambda url: {"title": "T", "text": "verbatim body"})
    rc = cli.main(["https://example.com/a"])
    out = capsys.readouterr()
    assert rc == 0
    assert out.out == "verbatim body\n"   # no title, pipe-clean


def test_main_json_shape(monkeypatch, capsys):
    monkeypatch.setattr(cli.youtube_fetch, "fetch",
                        lambda vid, url, languages=None: {"title": "T", "text": "txt"})
    rc = cli.main(["https://youtu.be/dQw4w9WgXcQ", "--json"])
    data = json.loads(capsys.readouterr().out)
    assert rc == 0
    assert data == {"source_type": "youtube",
                    "url": "https://youtu.be/dQw4w9WgXcQ",
                    "title": "T", "text": "txt"}


def test_main_passes_lang_priority(monkeypatch):
    seen = {}

    def fake(vid, url, languages=None):
        seen["languages"] = languages
        return {"title": None, "text": "x"}

    monkeypatch.setattr(cli.youtube_fetch, "fetch", fake)
    cli.main(["https://youtu.be/dQw4w9WgXcQ", "--lang", "ru,en"])
    assert seen["languages"] == ["ru", "en"]


def test_main_rawfetcherror_to_stderr_and_code(monkeypatch, capsys):
    def fail(url):
        raise RawfetchError("website fetch failed: HTTP 404", 6)

    monkeypatch.setattr(cli.website_fetch, "fetch", fail)
    rc = cli.main(["https://example.com/gone"])
    err = capsys.readouterr()
    assert rc == 6
    assert "HTTP 404" in err.err and err.out == ""


def test_main_unexpected_exit1(monkeypatch, capsys):
    def boom(url):
        raise RuntimeError("surprise")

    monkeypatch.setattr(cli.website_fetch, "fetch", boom)
    rc = cli.main(["https://example.com/x"])
    assert rc == 1
    assert "unexpected" in capsys.readouterr().err


def test_version_flag_prints_version(capsys):
    with pytest.raises(SystemExit) as ei:
        cli.main(["--version"])
    assert ei.value.code == 0
    assert "rawfetch" in capsys.readouterr().out

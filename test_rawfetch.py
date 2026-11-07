"""Offline tests for routing and the CLI contract (adapters mocked)."""
import json
import socket

import pytest

from rawfetch import cli
from rawfetch.errors import RawfetchError, network_error


@pytest.mark.parametrize("url,vid", [
    ("https://www.youtube.com/watch?v=dQw4w9WgXcQ", "dQw4w9WgXcQ"),
    ("https://youtube.com/watch?foo=1&v=dQw4w9WgXcQ", "dQw4w9WgXcQ"),
    ("https://youtu.be/dQw4w9WgXcQ", "dQw4w9WgXcQ"),
    ("https://m.youtube.com/watch?v=dQw4w9WgXcQ", "dQw4w9WgXcQ"),
    ("https://music.youtube.com/watch?v=dQw4w9WgXcQ", "dQw4w9WgXcQ"),
    ("https://www.youtube.com/shorts/dQw4w9WgXcQ", "dQw4w9WgXcQ"),
    ("https://www.youtube.com/live/dQw4w9WgXcQ", "dQw4w9WgXcQ"),
    ("https://www.youtube.com/embed/dQw4w9WgXcQ", "dQw4w9WgXcQ"),
    ("HTTPS://WWW.YOUTUBE.COM/watch?v=dQw4w9WgXcQ", "dQw4w9WgXcQ"),  # scheme+host case
    ("HTTPS://youtu.be/dQw4w9WgXcQ", "dQw4w9WgXcQ"),
])
def test_route_youtube(url, vid):
    assert cli.route(url) == ("youtube", vid)


@pytest.mark.parametrize("url", [
    "https://example.com/article",
    "http://blog.example.org/post?v=dQw4w9WgXcQ",   # v= param on non-youtube host
    "https://myyoutube.com/watch?v=dQw4w9WgXcQ",     # lookalike host
    "HTTP://Example.COM/article",                    # uppercase scheme, plain site
])
def test_route_website(url):
    assert cli.route(url) == ("website", None)


@pytest.mark.parametrize("url", [
    "ftp://example.com/x",
    "not a url",
    "https://www.youtube.com/feed/history",          # youtube host, no video id
    "https://",                                      # scheme, no host
    "http://",
    "https:///path",                                 # empty host, non-empty path
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


def _refused_local_port():
    """A localhost port that was just free — connecting to it gets refused, fast."""
    s = socket.socket()
    s.bind(("127.0.0.1", 0))
    port = s.getsockname()[1]
    s.close()
    return port


@pytest.fixture
def dead_proxy_env(monkeypatch):
    """Route everything through a proxy that refuses connections. Offline by design:
    the real libraries run, but the only connection attempted is to localhost."""
    proxy = "http://127.0.0.1:{}".format(_refused_local_port())
    monkeypatch.setenv("HTTPS_PROXY", proxy)
    monkeypatch.setenv("HTTP_PROXY", proxy)
    for var in ("NO_PROXY", "no_proxy"):
        monkeypatch.delenv(var, raising=False)


def test_dead_proxy_youtube_is_exit7_not_unexpected(dead_proxy_env, capsys):
    """End-to-end proof that env proxies are honoured on the YouTube path and that a
    broken proxy lands as a classed network error, not exit 1."""
    rc = cli.main(["https://www.youtube.com/watch?v=jNQXAC9IVRw"])
    assert rc == 7
    assert "network error" in capsys.readouterr().err


def test_dead_proxy_website_is_exit7_not_unexpected(dead_proxy_env, capsys):
    rc = cli.main(["https://example.com/article"])
    assert rc == 7
    assert "network error" in capsys.readouterr().err


def test_version_flag_prints_version(capsys):
    with pytest.raises(SystemExit) as ei:
        cli.main(["--version"])
    assert ei.value.code == 0
    assert "rawfetch" in capsys.readouterr().out


# --- found by the QA pass: newcomer-friendly messages --------------------------------------

def test_bare_domain_suggests_https():
    with pytest.raises(RawfetchError) as ei:
        cli.route("example.com/page")
    assert ei.value.exit_code == 2
    assert "did you mean https://example.com/page" in str(ei.value)


def test_plain_word_gets_no_suggestion():
    with pytest.raises(RawfetchError) as ei:
        cli.route("hello")
    assert "did you mean" not in str(ei.value)


@pytest.mark.parametrize("raw,short", [
    ("HTTPSConnectionPool(host='x.invalid', port=443): Max retries exceeded "
     "(Caused by NameResolutionError(\"Failed to resolve 'x.invalid'\"))",
     "could not resolve the host name"),
    ("HTTPConnectionPool(host='localhost', port=9): Max retries exceeded "
     "(Caused by NewConnectionError('[Errno 61] Connection refused'))",
     "connection refused"),
    ("HTTPSConnectionPool(host='a.b', port=443): Read timed out. (read timeout=20)",
     "timed out"),
])
def test_network_error_is_short_and_plain(raw, short, monkeypatch):
    for var in ("HTTPS_PROXY", "https_proxy", "HTTP_PROXY", "http_proxy", "ALL_PROXY",
                "all_proxy"):
        monkeypatch.delenv(var, raising=False)
    msg = str(network_error(Exception(raw)))
    assert msg.startswith("network error: could not reach the source: " + short)
    assert "Max retries" not in msg

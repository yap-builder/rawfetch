"""Offline tests for the YouTube adapter: fakes for the instance API, no network."""
import pytest
import requests

from rawfetch import youtube_fetch
from rawfetch.errors import RawfetchError
from youtube_transcript_api._errors import (
    TranscriptsDisabled, NoTranscriptFound, VideoUnavailable,
    IpBlocked, RequestBlocked, PoTokenRequired, AgeRestricted,
)


REAL_TITLE = youtube_fetch._title  # captured before the autouse stub below


class FakeSnippet:  # v1.2.4: snippets are objects with .text, NOT dicts
    def __init__(self, text):
        self.text = text


class FakeTranscript:
    def __init__(self, texts):
        self.snippets = [FakeSnippet(t) for t in texts]


class FakeListed:
    def __init__(self, texts):
        self._texts = texts

    def fetch(self):
        return FakeTranscript(self._texts)


def make_api(fetch_result=None, fetch_raises=None, listed=None):
    class FakeApi:
        last_languages = None

        def fetch(self, video_id, languages=None):
            FakeApi.last_languages = languages
            if fetch_raises is not None:
                raise fetch_raises
            return fetch_result

        def list(self, video_id):
            return list(listed or [])

    return FakeApi


@pytest.fixture(autouse=True)
def no_oembed(monkeypatch):
    monkeypatch.setattr(youtube_fetch, "_title", lambda url: "stub-title")


def exc(cls):
    e = cls.__new__(cls)  # bypass __init__: signatures vary across lib versions
    return e


def test_join_is_verbatim(monkeypatch):
    api = make_api(fetch_result=FakeTranscript(["hello", "world\nfoo"]))
    monkeypatch.setattr(youtube_fetch, "YouTubeTranscriptApi", api)
    out = youtube_fetch.fetch("v" * 11, "u")
    assert out["text"] == "hello world\nfoo"
    assert out["title"] == "stub-title"


def test_empty_transcript_is_exit3_not_silent_success(monkeypatch):
    """A transcript with no words must fail loudly, not print nothing with exit 0."""
    api = make_api(fetch_result=FakeTranscript(["", "   ", "\n"]))
    monkeypatch.setattr(youtube_fetch, "YouTubeTranscriptApi", api)
    with pytest.raises(RawfetchError) as ei:
        youtube_fetch.fetch("v" * 11, "u")
    assert ei.value.exit_code == 3
    assert "no text" in str(ei.value)


def test_lang_priority_passed_in_order(monkeypatch):
    api = make_api(fetch_result=FakeTranscript(["x"]))
    monkeypatch.setattr(youtube_fetch, "YouTubeTranscriptApi", api)
    youtube_fetch.fetch("v" * 11, "u", languages=["ru", "en"])
    assert api.last_languages == ["ru", "en"]


def test_default_lang_is_en(monkeypatch):
    api = make_api(fetch_result=FakeTranscript(["x"]))
    monkeypatch.setattr(youtube_fetch, "YouTubeTranscriptApi", api)
    youtube_fetch.fetch("v" * 11, "u")
    assert api.last_languages == ["en"]


def test_fallback_to_any_available(monkeypatch):
    api = make_api(fetch_raises=exc(NoTranscriptFound), listed=[FakeListed(["fall", "back"])])
    monkeypatch.setattr(youtube_fetch, "YouTubeTranscriptApi", api)
    out = youtube_fetch.fetch("v" * 11, "u")
    assert out["text"] == "fall back"


def test_no_transcripts_at_all_exit3(monkeypatch):
    api = make_api(fetch_raises=exc(NoTranscriptFound), listed=[])
    monkeypatch.setattr(youtube_fetch, "YouTubeTranscriptApi", api)
    with pytest.raises(RawfetchError) as ei:
        youtube_fetch.fetch("v" * 11, "u")
    assert ei.value.exit_code == 3


@pytest.mark.parametrize("cls,code", [
    (TranscriptsDisabled, 3),
    (IpBlocked, 4),
    (RequestBlocked, 4),
    (PoTokenRequired, 4),
    (VideoUnavailable, 5),
    (AgeRestricted, 5),
])
def test_error_classes_map_to_exit_codes(monkeypatch, cls, code):
    api = make_api(fetch_raises=exc(cls))
    monkeypatch.setattr(youtube_fetch, "YouTubeTranscriptApi", api)
    with pytest.raises(RawfetchError) as ei:
        youtube_fetch.fetch("v" * 11, "u")
    assert ei.value.exit_code == code


@pytest.mark.parametrize("transport_exc", [
    requests.exceptions.ProxyError("proxy refused the connection"),
    requests.exceptions.ConnectionError("dns lookup failed"),
    requests.exceptions.Timeout("read timed out"),
])
def test_transport_errors_exit7(monkeypatch, transport_exc):
    """A dead network or broken proxy is a classed failure, not 'unexpected error'."""
    api = make_api(fetch_raises=transport_exc)
    monkeypatch.setattr(youtube_fetch, "YouTubeTranscriptApi", api)
    with pytest.raises(RawfetchError) as ei:
        youtube_fetch.fetch("v" * 11, "u")
    assert ei.value.exit_code == 7
    assert "network error" in str(ei.value)


def test_network_error_names_proxy_scheme_never_credentials(monkeypatch):
    """When env proxies are in effect the message says so — but proxy URLs can carry
    user:pass, so only the scheme names may appear, never the values."""
    monkeypatch.setenv("HTTPS_PROXY", "http://user:sekretpass@127.0.0.1:9")
    api = make_api(fetch_raises=requests.exceptions.ProxyError("boom"))
    monkeypatch.setattr(youtube_fetch, "YouTubeTranscriptApi", api)
    with pytest.raises(RawfetchError) as ei:
        youtube_fetch.fetch("v" * 11, "u")
    msg = str(ei.value)
    assert "proxy" in msg
    assert "sekretpass" not in msg and "127.0.0.1:9" not in msg


def test_network_error_without_proxy_env_has_no_proxy_hint(monkeypatch):
    for var in ("HTTP_PROXY", "HTTPS_PROXY", "ALL_PROXY",
                "http_proxy", "https_proxy", "all_proxy"):
        monkeypatch.delenv(var, raising=False)
    api = make_api(fetch_raises=requests.exceptions.ConnectionError("refused"))
    monkeypatch.setattr(youtube_fetch, "YouTubeTranscriptApi", api)
    with pytest.raises(RawfetchError) as ei:
        youtube_fetch.fetch("v" * 11, "u")
    assert "proxy" not in str(ei.value)


def test_messages_differ_between_classes(monkeypatch):
    msgs = {}
    for cls in (TranscriptsDisabled, IpBlocked, VideoUnavailable):
        api = make_api(fetch_raises=exc(cls))
        monkeypatch.setattr(youtube_fetch, "YouTubeTranscriptApi", api)
        with pytest.raises(RawfetchError) as ei:
            youtube_fetch.fetch("v" * 11, "u")
        msgs[cls.__name__] = str(ei.value)
    assert len(set(msgs.values())) == 3


class FakeResp:
    def __init__(self, status_code, payload=None):
        self.status_code = status_code
        self._payload = payload

    def json(self):
        return self._payload


def test_title_ok(monkeypatch):
    monkeypatch.setattr(youtube_fetch.requests, "get",
                        lambda *a, **k: FakeResp(200, {"title": "My Video"}))
    assert REAL_TITLE("u") == "My Video"


def test_title_non200_is_none(monkeypatch):
    monkeypatch.setattr(youtube_fetch.requests, "get", lambda *a, **k: FakeResp(404))
    assert REAL_TITLE("u") is None


def test_title_network_error_is_none(monkeypatch):
    def boom(*a, **k):
        raise OSError("net down")
    monkeypatch.setattr(youtube_fetch.requests, "get", boom)
    assert REAL_TITLE("u") is None

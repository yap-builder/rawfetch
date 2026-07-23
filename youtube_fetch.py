#!/usr/bin/env python3
"""YouTube transcript adapter for grab (verbatim capture, zero LLM).

WHY: an AI assistant can't pull YouTube captions itself — this adapter turns a video URL
into the raw caption text. Capture, not judgment: plain space-join of caption snippets,
no cleanup. Errors are classed (no captions != IP block != video gone) so the user can
tell what actually happened. Title comes from keyless oEmbed and is never fatal.
"""
import requests
from youtube_transcript_api import YouTubeTranscriptApi
from youtube_transcript_api._errors import (
    TranscriptsDisabled, NoTranscriptFound, VideoUnavailable,
    IpBlocked, RequestBlocked, PoTokenRequired, AgeRestricted,
)

from errors import GrabError, EXIT_NO_CAPTIONS, EXIT_BLOCKED, EXIT_UNAVAILABLE

OEMBED = "https://www.youtube.com/oembed"


def fetch(video_id, url, languages=None):
    """Return {"title": str|None, "text": str}. Raises GrabError on known failures."""
    langs = list(languages) if languages else ["en"]
    api = YouTubeTranscriptApi()
    try:
        try:
            transcript = api.fetch(video_id, languages=langs)
        except NoTranscriptFound:
            transcript = _any_available(api, video_id)
    except (TranscriptsDisabled, NoTranscriptFound):
        raise GrabError(
            "no captions: this video has no transcripts at all "
            "(subtitles disabled or missing)", EXIT_NO_CAPTIONS)
    except PoTokenRequired:
        raise GrabError(
            "blocked: YouTube demands a PO token for this request "
            "(common on datacenter IPs; try a residential IP)", EXIT_BLOCKED)
    except IpBlocked:
        raise GrabError(
            "blocked: YouTube has blocked this IP for transcript requests "
            "(common on datacenter IPs; try a residential IP)", EXIT_BLOCKED)
    except RequestBlocked:
        raise GrabError(
            "blocked: YouTube rejected the request (bot protection); "
            "try again later or from a residential IP", EXIT_BLOCKED)
    except AgeRestricted:
        raise GrabError(
            "video unavailable: age-restricted, captions need a signed-in "
            "session which grab does not do", EXIT_UNAVAILABLE)
    except VideoUnavailable:
        raise GrabError(
            "video unavailable: private, deleted or region-locked",
            EXIT_UNAVAILABLE)
    text = " ".join(s.text for s in transcript.snippets)
    return {"title": _title(url), "text": text}


def _any_available(api, video_id):
    """Requested languages missing -> first available transcript, else no-captions."""
    transcripts = list(api.list(video_id))
    if not transcripts:
        raise TranscriptsDisabled(video_id)
    return transcripts[0].fetch()


def _title(url):
    """Video title via oEmbed (no API key). Any failure -> None, never fatal."""
    try:
        resp = requests.get(OEMBED, params={"url": url, "format": "json"}, timeout=10)
        if resp.status_code != 200:
            return None
        return resp.json().get("title")
    except Exception:
        return None

#!/usr/bin/env python3
"""Command line entry point: route a URL to the right adapter, print verbatim text.

Routing is deliberately dumb and readable — host match, then video id — so a reader can
tell at a glance which source a URL will hit. No network happens in this module.
"""
import argparse
import json
import re
import sys

from rawfetch import __version__, website_fetch, youtube_fetch
from rawfetch.errors import RawfetchError, EXIT_UNEXPECTED, EXIT_USAGE


def route(url):
    """Classify url -> ("youtube", video_id) or ("website", None). RawfetchError on junk."""
    if not re.match(r"^https?://", url):
        raise RawfetchError("not an http(s) URL: {}".format(url), EXIT_USAGE)
    host = re.match(r"^https?://([^/]+)", url).group(1).lower().split(":")[0]
    if host == "youtu.be" or host == "youtube.com" or host.endswith(".youtube.com"):
        vid = _video_id(url, host)
        if not vid:
            raise RawfetchError(
                "youtube URL, but no 11-char video id found in it", EXIT_USAGE)
        return "youtube", vid
    return "website", None


def _video_id(url, host):
    if host == "youtu.be":
        m = re.match(r"^https?://youtu\.be/([A-Za-z0-9_-]{11})", url)
        return m.group(1) if m else None
    m = re.search(r"[?&]v=([A-Za-z0-9_-]{11})", url)
    if m:
        return m.group(1)
    m = re.search(r"/(?:shorts|live|embed)/([A-Za-z0-9_-]{11})", url)
    return m.group(1) if m else None


def main(argv=None):
    parser = argparse.ArgumentParser(
        prog="rawfetch",
        description="Print verbatim text from a URL: YouTube captions, or the "
                    "article text of a plain web page. No LLM, no summaries.")
    parser.add_argument("url")
    parser.add_argument("--lang", metavar="ru,en",
                        help="caption language priority for YouTube (ordered)")
    parser.add_argument("--json", action="store_true", dest="as_json",
                        help="print {source_type, url, title, text} as JSON")
    parser.add_argument("--version", action="version",
                        version="rawfetch {}".format(__version__))
    args = parser.parse_args(argv)
    try:
        source_type, video_id = route(args.url)
        if source_type == "youtube":
            languages = ([s.strip() for s in args.lang.split(",") if s.strip()]
                         if args.lang else None)
            result = youtube_fetch.fetch(video_id, args.url, languages=languages)
        else:
            result = website_fetch.fetch(args.url)
    except RawfetchError as e:
        print("rawfetch: {}".format(e), file=sys.stderr)
        return e.exit_code
    except Exception as e:  # honest catch-all: report, never fabricate
        print("rawfetch: unexpected error: {!r}".format(e), file=sys.stderr)
        return EXIT_UNEXPECTED
    if args.as_json:
        print(json.dumps({"source_type": source_type, "url": args.url,
                          "title": result["title"], "text": result["text"]},
                         ensure_ascii=False))
    else:
        print(result["text"])
    return 0


if __name__ == "__main__":
    sys.exit(main())

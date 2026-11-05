"""Offline tests for the Reddit adapter: URL handling, output formatting, error classes.

The browser is never launched here. The page-side extractor returns plain dicts, so the
tests feed dicts of the same shape (synthetic content, not copied Reddit posts) and the
browser seam (`reddit_fetch._browse`) is monkeypatched.
"""
import sys

import pytest

from rawfetch import cli, reddit_fetch
from rawfetch.errors import RawfetchError

POST = {
    "kind": "post",
    "subreddit": "r/example",
    "title": "Which editor do you use?",
    "author": "alice",
    "score": "120",
    "comment_count": "57",
    "body": "First paragraph.\n\nSecond paragraph.",
    "comments": [
        {"author": "bob", "depth": "0", "score": "40", "text": "Vim.\nAlways vim.",
         "hidden_replies": 3},
        {"author": "carol", "depth": "1", "score": "12", "text": "Same here.",
         "hidden_replies": 0},
        {"author": "dave", "depth": "0", "score": "-2", "text": "Notepad.",
         "hidden_replies": 0},
    ],
}

LISTING = {
    "kind": "listing",
    "page_title": "r/example - top this week",
    "posts": [
        {"title": "First post", "url": "https://www.reddit.com/r/example/comments/aaa111/first/",
         "subreddit": "r/example", "score": "900", "comments": "300"},
        {"title": "Second post", "url": "https://www.reddit.com/r/example/comments/bbb222/second/",
         "subreddit": None, "score": None, "comments": None},
    ],
}


# --- routing -----------------------------------------------------------------------------

@pytest.mark.parametrize("url", [
    "https://www.reddit.com/r/ClaudeAI/comments/abc123/some_title/",
    "https://reddit.com/r/ClaudeAI/top/?t=week",
    "https://old.reddit.com/r/ClaudeAI/",
    "https://new.reddit.com/r/ClaudeAI/search/?q=x",
    "https://redd.it/abc123",
    "HTTPS://WWW.REDDIT.COM/r/x/",
])
def test_route_reddit(url):
    assert cli.route(url) == ("reddit", None)


@pytest.mark.parametrize("url", [
    "https://notreddit.com/r/x/",
    "https://reddit.com.evil.example/r/x/",
])
def test_route_lookalike_reddit_is_website(url):
    assert cli.route(url) == ("website", None)


@pytest.mark.parametrize("url,expected", [
    ("https://old.reddit.com/r/x/comments/abc/t/", "https://www.reddit.com/r/x/comments/abc/t/"),
    ("https://new.reddit.com/r/x/?t=week#frag", "https://www.reddit.com/r/x/?t=week"),
    ("https://reddit.com/r/x/search/?q=a%20b", "https://www.reddit.com/r/x/search/?q=a%20b"),
    ("https://m.reddit.com/r/x/", "https://www.reddit.com/r/x/"),
    ("https://redd.it/abc123", "https://redd.it/abc123"),
])
def test_normalize_url(url, expected):
    assert reddit_fetch.normalize_url(url) == expected


@pytest.mark.parametrize("url,is_post", [
    ("https://www.reddit.com/r/x/comments/abc123/title/", True),
    ("https://www.reddit.com/comments/abc123", True),
    ("https://www.reddit.com/user/u/comments/abc123/t/", True),
    ("https://www.reddit.com/r/x/top/?t=week", False),
    ("https://www.reddit.com/r/x/search/?q=comments", False),
    ("https://www.reddit.com/r/x/", False),
])
def test_is_post_url(url, is_post):
    assert reddit_fetch.is_post_url(url) is is_post


# --- formatting --------------------------------------------------------------------------

def test_format_post_header_and_body():
    text = reddit_fetch.format_post(POST)
    lines = text.splitlines()
    assert lines[0] == "Which editor do you use?"
    assert lines[1] == "r/example · u/alice · 120 points · 57 comments"
    assert "First paragraph.\n\nSecond paragraph." in text


def test_format_post_comments_are_verbatim_and_indented_by_depth():
    text = reddit_fetch.format_post(POST)
    assert "u/bob · 40 points\nVim.\nAlways vim." in text
    # depth 1: every line of the comment is indented, header included
    assert "    u/carol · 12 points\n    Same here." in text
    assert "u/dave · -2 points\nNotepad." in text


def test_format_post_marks_hidden_replies_under_their_parent():
    text = reddit_fetch.format_post(POST)
    bob = text.index("Always vim.")
    marker = text.index("[+3 more replies not loaded]")
    carol = text.index("u/carol")
    assert bob < marker < carol
    assert text[marker - 4:marker] == "    "  # marker sits one level under bob


def test_format_post_states_honestly_how_many_comments_are_shown():
    text = reddit_fetch.format_post(POST)
    assert "showing 3 of 57 comments" in text


def test_format_post_without_comments_says_so():
    post = dict(POST, comments=[], comment_count="0")
    text = reddit_fetch.format_post(post)
    assert "no comments loaded" in text


def test_format_post_survives_missing_metadata():
    post = dict(POST, author=None, score=None, comment_count=None, subreddit=None,
                comments=[dict(POST["comments"][0], score=None, author=None)])
    text = reddit_fetch.format_post(post)
    assert text.splitlines()[0] == "Which editor do you use?"
    assert "None" not in text
    assert "u/[unknown]" in text


def test_format_listing_numbers_posts_with_links():
    text = reddit_fetch.format_listing(LISTING)
    assert text.splitlines()[0] == "r/example - top this week"
    assert "1. First post\n   r/example · 900 points · 300 comments\n" \
           "   https://www.reddit.com/r/example/comments/aaa111/first/" in text
    # missing metadata line is skipped, not printed as "None"
    assert "2. Second post\n   https://www.reddit.com/r/example/comments/bbb222/second/" in text
    assert "None" not in text


# --- fetch: error classes and the browser seam --------------------------------------------

def test_fetch_post_uses_browser_result(monkeypatch):
    monkeypatch.setattr(reddit_fetch, "_browse", lambda url: POST)
    out = reddit_fetch.fetch("https://www.reddit.com/r/example/comments/abc/t/")
    assert out["title"] == "Which editor do you use?"
    assert "u/bob · 40 points" in out["text"]


def test_fetch_listing_uses_browser_result(monkeypatch):
    monkeypatch.setattr(reddit_fetch, "_browse", lambda url: LISTING)
    out = reddit_fetch.fetch("https://www.reddit.com/r/example/top/")
    assert out["title"] == "r/example - top this week"
    assert out["text"].startswith("r/example - top this week")


def test_missing_playwright_is_exit8_with_install_hint(monkeypatch):
    monkeypatch.setitem(sys.modules, "playwright", None)
    monkeypatch.setitem(sys.modules, "playwright.sync_api", None)
    with pytest.raises(RawfetchError) as ei:
        reddit_fetch.fetch("https://www.reddit.com/r/example/")
    assert ei.value.exit_code == 8
    assert "rawfetch[reddit]" in str(ei.value)
    assert "playwright install webkit" in str(ei.value)


def test_cli_reddit_without_playwright_exits8(monkeypatch, capsys):
    monkeypatch.setitem(sys.modules, "playwright", None)
    monkeypatch.setitem(sys.modules, "playwright.sync_api", None)
    rc = cli.main(["https://www.reddit.com/r/example/"])
    assert rc == 8
    assert "reddit" in capsys.readouterr().err.lower()


def test_cli_reddit_json_shape(monkeypatch, capsys):
    monkeypatch.setattr(reddit_fetch, "_browse", lambda url: POST)
    rc = cli.main(["https://www.reddit.com/r/example/comments/abc/t/", "--json"])
    assert rc == 0
    import json
    data = json.loads(capsys.readouterr().out)
    assert set(data) == {"source_type", "url", "title", "text"}
    assert data["source_type"] == "reddit"


@pytest.mark.parametrize("page,code", [
    ({"title": "Blocked", "text": "You've been blocked by network security."}, 4),
    ({"title": "Reddit", "text": "whoa there, pardner! too many requests"}, 4),
    ({"title": "r/x", "text": "Sorry, this post was deleted by the person who posted it."}, 5),
    ({"title": "r/x", "text": "Sorry, this post has been removed by the moderators of r/x."}, 5),
    ({"title": "Page not found", "text": "page not found"}, 5),
    ({"title": "r/privatesub", "text": "This community is private"}, 5),
])
def test_classify_failure_page(page, code):
    err = reddit_fetch.classify_failure(page["title"], page["text"], http_status=200)
    assert err is not None and err.exit_code == code


def test_classify_failure_http_404_is_exit5():
    err = reddit_fetch.classify_failure("Reddit", "", http_status=404)
    assert err.exit_code == 5


def test_classify_failure_http_429_is_exit4():
    err = reddit_fetch.classify_failure("Reddit", "", http_status=429)
    assert err.exit_code == 4


def test_classify_failure_normal_page_is_none():
    assert reddit_fetch.classify_failure("Some post : r/x", "normal text", http_status=200) is None


def test_private_community_with_403_is_unavailable_not_blocked():
    """Text that names the reason beats the bare status: a private sub is gone, not a ban."""
    err = reddit_fetch.classify_failure("r/x", "This community is private", http_status=403)
    assert err.exit_code == 5


# --- check_result: what the browser saw vs what was asked --------------------------------

POST_URL = "https://www.reddit.com/r/example/comments/abc123/t/"


def test_check_result_missing_post_with_related_links_is_exit5_not_a_listing():
    """A dead post page still carries 'related posts' links. Returning those as a listing
    would answer a different question than the one asked, with exit 0."""
    with pytest.raises(RawfetchError) as ei:
        reddit_fetch.check_result(POST_URL, POST_URL, LISTING, "Reddit", "", 200)
    assert ei.value.exit_code == 5


def test_check_result_post_link_redirected_away_is_exit5():
    with pytest.raises(RawfetchError) as ei:
        reddit_fetch.check_result(POST_URL, "https://www.reddit.com/r/example/", LISTING,
                                  "r/example", "", 200)
    assert ei.value.exit_code == 5


def test_check_result_share_link_landing_on_post_is_fine():
    share = "https://www.reddit.com/r/example/s/AbCdEf"
    assert reddit_fetch.check_result(share, POST_URL, POST, "t", "", 200) is POST


def test_check_result_blocked_post_page_is_exit4():
    with pytest.raises(RawfetchError) as ei:
        reddit_fetch.check_result(POST_URL, POST_URL, dict(LISTING, posts=[]), "Blocked",
                                  "You've been blocked by network security.", 403)
    assert ei.value.exit_code == 4


def test_check_result_listing_is_fine():
    url = "https://www.reddit.com/r/example/top/"
    assert reddit_fetch.check_result(url, url, LISTING, "t", "", 200) is LISTING


def test_check_result_empty_listing_is_exit6():
    url = "https://www.reddit.com/r/example/top/"
    with pytest.raises(RawfetchError) as ei:
        reddit_fetch.check_result(url, url, dict(LISTING, posts=[]), "r/example", "", 200)
    assert ei.value.exit_code == 6


# --- error messages say what Reddit actually answered -------------------------------------

def test_blocked_error_names_status_and_title():
    with pytest.raises(RawfetchError) as ei:
        reddit_fetch.check_result(POST_URL, POST_URL, dict(LISTING, posts=[]), "Blocked",
                                  "You've been blocked by network security.", 403)
    msg = str(ei.value)
    assert "HTTP 403" in msg
    assert 'page title "Blocked"' in msg


def test_unavailable_error_names_status_and_empty_title():
    with pytest.raises(RawfetchError) as ei:
        reddit_fetch.check_result(POST_URL, POST_URL, LISTING, "", "", 200)
    msg = str(ei.value)
    assert ei.value.exit_code == 5
    assert "HTTP 200" in msg
    assert "empty page title" in msg


def test_empty_listing_error_names_status():
    url = "https://www.reddit.com/r/example/top/"
    with pytest.raises(RawfetchError) as ei:
        reddit_fetch.check_result(url, url, dict(LISTING, posts=[]), "r/example", "", None)
    assert "no HTTP status" in str(ei.value)


def test_blocked_error_says_post_links_may_still_work():
    err = reddit_fetch.classify_failure("Blocked", "blocked by network security", 403)
    assert "search" in str(err) and "post link" in str(err)

"""Reddit adapter for rawfetch: a post with its top comments, or a list of posts.

WHY: Reddit closed anonymous .json access in 2026 and AI assistants' own fetchers get a
403, so "read this thread" is exactly the source an AI can't reach. A real browser engine
still can: headless WebKit passes Reddit's JS challenge anonymously, while headless
Chromium gets "blocked by network security". So this path drives Playwright-WebKit,
reads what the page renders, and prints it verbatim. No login, no API key, no LLM.

Two shapes, decided by where the browser actually lands (share links and redd.it
redirect, so the final URL is the truth, not the input):
  - a post page (/comments/<id>) -> title, post text, and the comments Reddit renders
    without clicking anything (roughly the top 30, best-first). Replies hidden behind
    "N more replies" are marked in place, never silently dropped.
  - anything else (subreddit, /top, /search) -> numbered list of posts with links,
    so the next call can fetch the one you want.

Playwright is an optional extra (`pip install 'rawfetch[reddit]'` plus a ~300 MB browser
download), imported lazily so the YouTube and website paths never need it.
"""
import os
import re
import sys
import time
from urllib.parse import urlsplit, urlunsplit

from rawfetch.errors import (RawfetchError, network_error, EXIT_BLOCKED, EXIT_NOT_INSTALLED,
                             EXIT_UNAVAILABLE, EXIT_WEBSITE_FAILED)

UA = ("Mozilla/5.0 (Macintosh; Intel Mac OS X 10_15_7) AppleWebKit/605.1.15 "
      "(KHTML, like Gecko) Version/17.0 Safari/605.1.15")

INSTALL_HINT = ("Reddit support is not installed. Install it with:\n"
                "  pip install 'rawfetch[reddit]' && playwright install webkit\n"
                "(or re-run ./install.sh and choose Reddit)")

POST_PATH = re.compile(r"^/(?:(?:r|user|u)/[^/]+/)?comments/[a-z0-9]+", re.IGNORECASE)

# Wait for the page to show content, not a fixed sleep: Reddit sometimes serves a JS
# challenge first and redirects to the real page a few seconds later.
CONTENT_SELECTOR = "shreddit-post, shreddit-comment, a[href*='/comments/']"
SEARCH_BLOCK_HINT = "Search pages are blocked first; a post link may still work."
ADDRESS_BLOCK_HINT = ("From a server or cloud machine Reddit blocks the address itself: "
                      "run from a home connection or set HTTPS_PROXY to a residential proxy.")
SETTLE_SECONDS = 30
# Gentle scrolling lets the lazily-rendered comments appear. Measured 2026-11-04: on
# posts with 92, 173 and 1674 comments this settles at ~34 rendered comments every time.
# Listings render only ~3 posts until scrolled (measured the same day), so they scroll too.
SCROLL_STEPS_POST = 6
SCROLL_STEPS_LISTING = 4
SCROLL_PAUSE_MS = 2000

EXTRACT = r"""() => {
  const txt = el => el ? (el.innerText || '').trim() : '';
  const post = document.querySelector('shreddit-post');
  if (post && /\/comments\/[^/]+/i.test(location.pathname)) {
    const body = post.querySelector('[slot="text-body"]');
    const comments = [...document.querySelectorAll('shreddit-comment')].map(c => {
      const slot = c.querySelector(':scope > [slot="comment"]')
        || c.querySelector('[slot="comment"]');
      let hidden = 0;
      [...c.children].forEach(ch => {
        if (ch.matches('shreddit-comment') || ch.getAttribute('slot') === 'comment') return;
        const t = (ch.innerText || '').trim();
        const m = t.length < 60 && t.match(/(\d[\d,]*)\s+more\s+repl/i);
        if (m) hidden += parseInt(m[1].replace(/,/g, ''), 10);
      });
      return {author: c.getAttribute('author'), depth: c.getAttribute('depth'),
              score: c.getAttribute('score'), text: txt(slot), hidden_replies: hidden};
    });
    return {kind: 'post', subreddit: post.getAttribute('subreddit-prefixed-name'),
            title: post.getAttribute('post-title'), author: post.getAttribute('author'),
            score: post.getAttribute('score'), comment_count: post.getAttribute('comment-count'),
            body: txt(body), comments};
  }
  const posts = [], seen = new Set();
  const add = (href, title, sub, score, comments) => {
    if (!href || !title) return;
    const url = (href.startsWith('http') ? href : location.origin + href).split('?')[0];
    if (!/\/comments\//.test(url) || seen.has(url)) return;
    seen.add(url);
    posts.push({title: title.trim(), url, subreddit: sub, score, comments});
  };
  document.querySelectorAll('shreddit-post').forEach(el => add(
    el.getAttribute('permalink'), el.getAttribute('post-title'),
    el.getAttribute('subreddit-prefixed-name'), el.getAttribute('score'),
    el.getAttribute('comment-count')));
  if (!posts.length) {
    const root = document.querySelector('main') || document.body;
    root.querySelectorAll('a[href*="/comments/"]').forEach(a =>
      add(a.getAttribute('href'), txt(a), null, null, null));
  }
  return {kind: 'listing', page_title: document.title, posts};
}"""


def normalize_url(url):
    """Any reddit host -> www.reddit.com (old./new./m. render differently or not at all);
    redd.it short links are left for the browser to follow. Fragment dropped."""
    parts = urlsplit(url)
    host = parts.hostname or ""
    if host != "redd.it":
        host = "www.reddit.com"
    return urlunsplit(("https", host, parts.path or "/", parts.query, ""))


def is_post_url(url):
    return bool(POST_PATH.match(urlsplit(url).path))


def fetch(url):
    """Return {"title": str|None, "text": str}. Raises RawfetchError on failure."""
    data = _browse(normalize_url(url))
    if data["kind"] == "post":
        return {"title": data.get("title"), "text": format_post(data)}
    return {"title": data.get("page_title"), "text": format_listing(data)}


def _load_playwright():
    try:
        from playwright.sync_api import sync_playwright, Error
    except ImportError:
        raise RawfetchError(INSTALL_HINT, EXIT_NOT_INSTALLED)
    return sync_playwright, Error


def _browse(url):
    """Open url in headless WebKit, return the extractor's dict. The one networked seam."""
    sync_playwright, PwError = _load_playwright()
    with sync_playwright() as p:
        try:
            browser = p.webkit.launch(headless=True, proxy=_proxy_from_env())
        except PwError as e:
            err = launch_error(str(e))
            if err:
                raise err
            raise
        try:
            page = browser.new_context(user_agent=UA, locale="en-US",
                                       viewport={"width": 1280, "height": 1000}).new_page()
            try:
                resp = page.goto(url, wait_until="domcontentloaded", timeout=45000)
            except PwError as e:
                raise network_error(e)
            status = resp.status if resp else None
            if _wait_for_content(page):
                steps = SCROLL_STEPS_POST if is_post_url(page.url) else SCROLL_STEPS_LISTING
                for _ in range(steps):
                    page.mouse.wheel(0, 2500)
                    page.wait_for_timeout(SCROLL_PAUSE_MS)
            data = _evaluate(page)
            return check_result(url, page.url, data, _safe_title(page), _body_text(page), status)
        finally:
            browser.close()


def launch_error(message):
    """Turn a browser-launch failure the user can fix into exit 8 with the fix; else None."""
    if "missing dependencies" in message or "missing libraries" in message.lower():
        playwright_bin = os.path.join(os.path.dirname(sys.executable), "playwright")
        return RawfetchError(
            "Reddit's browser engine is installed, but this system lacks libraries it needs "
            "(common on Linux servers and containers). Install them once with:\n"
            "  sudo {} install-deps webkit\n(drop sudo if you are root)".format(playwright_bin),
            EXIT_NOT_INSTALLED)
    if "Executable doesn't exist" in message or "playwright install" in message:
        return RawfetchError(INSTALL_HINT, EXIT_NOT_INSTALLED)
    return None


def _wait_for_content(page):
    """True once post/comment/listing markup is present; survives the challenge redirect."""
    deadline = time.time() + SETTLE_SECONDS
    while time.time() < deadline:
        try:
            if page.query_selector(CONTENT_SELECTOR):
                page.wait_for_timeout(1500)  # let the first batch finish rendering
                return True
        except Exception:
            pass  # navigation in progress (challenge redirect): context was replaced
        time.sleep(1)
    return False


def _evaluate(page):
    try:
        return page.evaluate(EXTRACT)
    except Exception:
        return {"kind": "listing", "page_title": None, "posts": []}


def _body_text(page):
    try:
        return page.evaluate("() => document.body ? document.body.innerText.slice(0, 5000) : ''")
    except Exception:
        return ""


def _safe_title(page):
    try:
        return page.title()
    except Exception:
        return ""


def check_result(requested_url, final_url, data, title, text, http_status):
    """Accept the extractor's dict, or raise the right error class.

    A post link must yield a post: a dead post page still shows 'related posts' links,
    and handing those back as a listing would answer a different question with exit 0.
    Share links (/s/...) and redd.it are not post URLs until they redirect, so the
    requirement keys off either end being a post URL.
    """
    wanted_post = is_post_url(requested_url) or is_post_url(final_url)
    got_post = data.get("kind") == "post" and data.get("title")
    if got_post:
        return data
    if wanted_post or not data.get("posts"):
        err = classify_failure(title, text, http_status)
        if not err and wanted_post:
            err = RawfetchError(
                "reddit post unavailable: the link did not open a post "
                "(deleted, removed, or not found)", EXIT_UNAVAILABLE)
        if not err:
            err = RawfetchError(
                "reddit fetch failed: the page loaded but listed no posts", EXIT_WEBSITE_FAILED)
        hint = ""
        if err.exit_code == EXIT_BLOCKED:
            hint = " " + (SEARCH_BLOCK_HINT if "/search" in urlsplit(requested_url).path
                          else ADDRESS_BLOCK_HINT)
        raise RawfetchError("{}{} ({})".format(err, hint, _what_reddit_said(http_status, title)),
                            err.exit_code)
    return data


def _what_reddit_said(http_status, title):
    """The raw signal behind an error, so a failure can be diagnosed without re-fetching."""
    status = "HTTP {}".format(http_status) if http_status else "no HTTP status"
    title = (title or "").strip()
    shown = 'page title "{}"'.format(title[:80]) if title else "empty page title"
    return "Reddit answered: {}, {}".format(status, shown)


def _proxy_from_env():
    """Honour HTTPS_PROXY/HTTP_PROXY like the other paths. Credentials go to Playwright
    as separate fields and are never printed."""
    raw = os.environ.get("HTTPS_PROXY") or os.environ.get("https_proxy") \
        or os.environ.get("HTTP_PROXY") or os.environ.get("http_proxy")
    if not raw:
        return None
    parts = urlsplit(raw)
    proxy = {"server": "{}://{}{}".format(parts.scheme or "http", parts.hostname,
                                          ":{}".format(parts.port) if parts.port else "")}
    if parts.username:
        proxy["username"] = parts.username
        proxy["password"] = parts.password or ""
    return proxy


def classify_failure(title, text, http_status=None):
    """Map a page that yielded nothing to an exit class; None when it looks normal."""
    blob = "{}\n{}".format(title or "", text or "").lower()
    blocked = RawfetchError(
        "blocked by Reddit (bot protection / rate limit) — wait a while before retrying.",
        EXIT_BLOCKED)
    gone = RawfetchError(
        "reddit post or community unavailable (deleted, removed, private, or not found)",
        EXIT_UNAVAILABLE)
    # Text that names the reason wins over the bare status code: a private community
    # can answer 403 and is still "gone", not "you are banned".
    if "blocked by network security" in blob or "too many requests" in blob or \
            (title or "").strip().lower() == "blocked":
        return blocked
    if any(s in blob for s in ("page not found", "this post was deleted", "has been removed",
                               "community is private", "this community has been banned")):
        return gone
    if http_status in (403, 429):
        return blocked
    if http_status in (404, 410):
        return gone
    return None


def format_post(data):
    meta = _join([data.get("subreddit"), _user(data.get("author"), always=False),
                  _points(data.get("score")), _count(data.get("comment_count"), "comment")])
    out = [data.get("title") or "", meta] if meta else [data.get("title") or ""]
    if data.get("body"):
        out += ["", data["body"]]
    comments = data.get("comments") or []
    out.append("")
    if not comments:
        out.append("--- no comments loaded ---")
        return "\n".join(out)
    total = data.get("comment_count")
    shown = "showing {} of {} comments".format(len(comments), total) if total is not None \
        else "showing {} comments".format(len(comments))
    out.append("--- {} (top of the thread as Reddit renders it) ---".format(shown))
    for c in comments:
        indent = "    " * _int(c.get("depth"))
        out.append("")
        out.append(indent + _join([_user(c.get("author"), always=True), _points(c.get("score"))]))
        out += [(indent + line) if line else "" for line in (c.get("text") or "").splitlines()]
        if c.get("hidden_replies"):
            out.append("{}    [+{} more {} not loaded]".format(
                indent, c["hidden_replies"], "reply" if c["hidden_replies"] == 1 else "replies"))
    return "\n".join(out)


def format_listing(data):
    out = [data.get("page_title") or "reddit"]
    for i, p in enumerate(data.get("posts") or [], 1):
        out.append("")
        out.append("{}. {}".format(i, p.get("title")))
        meta = _join([p.get("subreddit"), _points(p.get("score")),
                      _count(p.get("comments"), "comment")])
        if meta:
            out.append("   " + meta)
        out.append("   " + p.get("url"))
    return "\n".join(out)


def _join(parts):
    return " · ".join(p for p in parts if p)


def _user(name, always):
    if name:
        return "u/" + name
    return "u/[unknown]" if always else None


def _points(score):
    return _count(score, "point")


def _count(value, noun):
    if value is None or value == "":
        return None
    return "{} {}{}".format(value, noun, "" if str(value) in ("1", "-1") else "s")


def _int(value):
    try:
        return max(0, int(value))
    except (TypeError, ValueError):
        return 0

# rawfetch

**Grab verbatim text from sources your AI can't reach — one command, zero LLM.**

Paste a YouTube link into an AI assistant and you get a guess. Paste a Reddit link and
you get a 403. `rawfetch` prints the actual captions, the actual thread. Capture, not
judgment: raw text to stdout, nothing summarized, nothing rewritten, honest errors when
the source can't be reached.

Sources: YouTube captions · Reddit posts with their top comments (plus post lists:
top of a subreddit, search) · article text from plain web pages.

Versus using the raw libraries yourself: one entry point for every source type,
one output contract (plain text, or `--json` with the same four fields), and a
deterministic, classed error contract — "no captions" is a different exit code
than "your IP is blocked", so scripts (and AI agents) can react correctly.

## Install

### Easiest: let your AI agent do it

If you use Claude Code, Cursor, or any agent that can run terminal commands, paste this
to it:

```text
Install rawfetch for me: clone https://github.com/yap-builder/rawfetch, read its
INSTALL.md and follow it. Ask me whether I want Reddit support first (it downloads a
~300 MB browser engine). When done, show me the verification output.
```

[`INSTALL.md`](INSTALL.md) is written for the agent: exact commands, how to check that
it worked, and what to do about the usual errors.

### Yourself

```bash
git clone https://github.com/yap-builder/rawfetch.git
cd rawfetch
./install.sh
```

The installer asks one question — whether to add Reddit — and installs into `.venv`
inside the folder. No sudo, nothing system-wide, safe to re-run. YouTube and web
articles are always included (small); Reddit is optional because it needs a real browser
engine (Playwright WebKit, ~300 MB). Skip the question with `./install.sh --reddit` or
`./install.sh --no-reddit`.

Prefer plain pip? `pip install .` gives YouTube + web; for Reddit:

```bash
pip install '.[reddit]'
playwright install webkit
```

Python 3.9+.

If pip prints a warning that the `rawfetch` script landed in a directory *not on
your PATH* (common with `pip install --user`: `~/.local/bin` on Linux,
`~/Library/Python/3.X/bin` on macOS), add that directory to your PATH — or skip
the problem entirely with `python -m rawfetch <url>`.

## Usage

```bash
rawfetch <url>                # verbatim text to stdout
rawfetch <url> --lang ru,en   # YouTube caption language priority (ordered)
rawfetch <reddit-post-url>    # post + its top comments
rawfetch "https://www.reddit.com/r/ClaudeAI/top/?t=week"
                              # numbered list of posts with links
rawfetch <url> --json         # {"source_type", "url", "title", "text"}
rawfetch --version
```

Also runs as `python -m rawfetch <url>`.

Real output, truncated:

```
$ rawfetch https://www.youtube.com/watch?v=jNQXAC9IVRw
All right, so here we are, in front of the
elephants the cool thing about these guys is that they
have really... really really long trunks and that's cool
…
```

```
$ rawfetch https://www.youtube.com/watch?v=jNQXAC9IVRw --json
{"source_type": "youtube", "url": "https://www.youtube.com/watch?v=jNQXAC9IVRw",
 "title": "Me at the zoo", "text": "All right, so here we are, in front of the…"}
```

If none of the requested `--lang` languages exist, rawfetch falls back to any
available transcript; it fails only when the video has no captions at all.

## Exit codes

| code | meaning |
|------|---------|
| 0 | success |
| 1 | unexpected error |
| 2 | bad URL / usage |
| 3 | no captions on this video (none at all, or an empty transcript) |
| 4 | blocked by the source (YouTube IP gate / PO token, Reddit bot protection / rate limit) |
| 5 | unavailable (video private/deleted/region-locked; Reddit post or community deleted, removed, private, not found) |
| 6 | page fetch failed (HTTP error, nothing extractable, or over the size cap) |
| 7 | network error: never reached the source at all (DNS, refused connection, timeout, or a broken proxy) |
| 8 | that source is not installed (Reddit without the `reddit` extra) — the message says how to add it |

## YouTube caveat

Caption access is IP-gated by YouTube. From a normal residential IP it just
works; from servers and datacenter IPs YouTube often blocks transcript
requests or demands a PO token (exit code 4). If you hit that, run rawfetch from
a home connection or route it through a residential proxy (see below).

## Proxies

rawfetch honours the standard `HTTPS_PROXY` / `HTTP_PROXY` / `NO_PROXY`
environment variables — YouTube and websites go through `requests`, which reads them;
the Reddit path hands `HTTPS_PROXY` / `HTTP_PROXY` to the browser (`NO_PROXY` does not
apply there). This is the practical answer to the caveat above when you have to run
from a server:

```bash
HTTPS_PROXY=http://user:pass@proxy.example:8080 rawfetch <youtube-url>
```

A proxy that can't be reached is exit code 7 (network error), and the error
message notes that an environment proxy was in effect — when you see that, the
proxy itself is the usual suspect. Proxy credentials are never echoed back.

## Reddit

Reddit stopped serving anonymous `.json` in 2026, and AI assistants' own web fetchers get
a 403. A real browser still gets the page, so this path drives headless **WebKit** —
Chromium gets "blocked by network security", WebKit passes Reddit's JS check. No login,
no API key, no account.

What you get, by link type:

- **A post** (`/r/<sub>/comments/<id>/...`, share links, `redd.it`): title, post text,
  and the comments Reddit renders without clicking anything — about the top 30,
  best-first, nested replies indented. The header says how many of the total you are
  seeing. Collapsed reply branches are marked in place (`[+17 more replies not loaded]`)
  where the extractor finds the count — it does not catch every one yet.
- **Anything else** (a subreddit, `/top/?t=week`, `/search/?q=...`): a numbered list of
  posts with links. Fetch the one you want next. Search is the least reliable of these:
  Reddit guards it hardest (see Limits).

Output shape:

```
<post title>
r/<sub> · u/<author> · 120 points · 173 comments

<post text>

--- showing 34 of 173 comments (top of the thread as Reddit renders it) ---

u/<author> · 408 points
<comment text, verbatim>
    [+2 more replies not loaded]
    u/<author> · 31 points
    <reply text, verbatim>
```

Limits worth knowing:

- **Top of the thread only.** "Load more" is not clicked: each click is another request
  to Reddit, and a big thread would take hundreds of them. Roughly the top 30 is what
  most people read anyway; the counts tell you what was left.
- **Slow on purpose.** About 20 seconds per page: it waits for the page and scrolls
  gently. Use it to read threads, not to crawl. Hammering Reddit gets you blocked
  (exit code 4) — if that happens, wait before retrying.
- **Search gets blocked first.** Search pages are Reddit's most protected. After a burst
  of requests ours got "blocked by network security" while post links and subreddit pages
  kept working, and the block was still there the next day. A logged-in person on the same
  connection was not affected. The error message says what Reddit answered (HTTP status
  and page title), so you can tell a block from a missing post without fetching again.
- **Reddit's terms.** Reddit does not welcome automated browsing. This is a personal
  reading tool: low volume, anonymous, read-only. Don't republish what it fetches.
- **It can break.** It reads the page Reddit renders today; if Reddit changes its markup
  or its bot checks, this path may stop working until updated.
- **Linux:** if the browser fails to start with missing system libraries, run
  `sudo .venv/bin/playwright install-deps webkit` once.

## Website fallback

Any non-YouTube URL is fetched as a plain web page and the main article text
is extracted verbatim. Static articles and blog posts work; JS-heavy apps and
paywalled pages may extract to nothing — rawfetch reports that honestly (exit
code 6) instead of inventing content.

## Limits worth knowing

**Size cap.** Page bodies over 5 MiB are refused (exit code 6) rather than buffered.
Article extraction allocates several times the input size, so an unbounded read turns a
fat URL into gigabytes of memory and minutes of CPU. rawfetch targets articles, not bulk
downloads.

**No URL filtering.** rawfetch fetches whatever URL you hand it, including `localhost`
and private network addresses — same as `curl` or any other HTTP client. That is a
property, not a feature: if you are driving rawfetch from an agent, do not feed it URLs
from untrusted input.

**Encoding.** When the server declares a charset, that is what the bytes are decoded as,
and bytes that do not fit it become `U+FFFD` rather than aborting the run. When no charset
is declared, the raw bytes go to the extractor, which reads the page's own `meta charset`
and falls back to UTF-8. So "verbatim" means verbatim up to undecodable bytes — the one
place rawfetch alters what it received, stated here rather than hidden.

## Roadmap

Planned: X threads. Website fetch included as a fallback.

## License

MIT

# rawfetch

**Paste a link, get the verbatim text: YouTube captions, Reddit threads with comments, articles.**

```
$ rawfetch https://www.youtube.com/watch?v=jNQXAC9IVRw
All right, so here we are, in front of the
elephants the cool thing about these guys is that they
have really... really really long trunks and that's cool
…
```

Paste a YouTube link into an AI assistant and you often get a guess. Paste a Reddit link
and many assistants hit a 403. `rawfetch` prints the actual captions, the actual thread.
It only captures: raw text to stdout, nothing summarized, nothing rewritten, and an
honest error when the source can't be reached. No AI model runs inside it, and it needs
no API keys and no accounts.

**Who it's for:** anyone who feeds links to Claude, ChatGPT, Cursor or their own agent
and needs the real text, not a retelling. And scripts or agents that need to know why a
fetch failed. It is just as useful without any AI: save captions and articles as plain
text into your notes, grep them, or pipe them into your own scripts.

**Sources:** YouTube captions · Reddit posts with their top comments (plus post lists:
top of a subreddit, search) · article text from plain web pages.

**Why not just call the libraries it uses** (youtube-transcript-api, trafilatura,
Playwright)? One command for every source type, one output format
(plain text, or `--json` with the same four fields), and each common kind of failure has
its own exit code. "No captions" and "your IP is blocked" are different codes, so a script or
an AI agent can tell whether retrying makes sense.

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

The installer asks one question, whether to add Reddit, and installs into `.venv` inside
the folder. No sudo, nothing system-wide, safe to re-run. YouTube and web articles are
always included (small). Reddit is optional because it needs a real browser engine
(Playwright WebKit, ~300 MB). Skip the question with `./install.sh --reddit` or
`./install.sh --no-reddit`.

Prefer plain pip? `pip install .` gives YouTube + web; for Reddit:

```bash
pip install '.[reddit]'
playwright install webkit
```

Python 3.9+. Tested on macOS and Linux; Windows has not been tested. If the `rawfetch`
command is not found after a pip install, see
[If something goes wrong](#if-something-goes-wrong).

To upgrade: run `git pull` in the folder, then `./install.sh` again. The installer
upgrades what is already there.

## Usage

```bash
rawfetch <url>                # verbatim text to stdout
rawfetch <url> --lang ru,en   # YouTube caption language priority (ordered; ignored for other links)
rawfetch <reddit-post-url>    # post + its top comments
rawfetch "https://www.reddit.com/r/ClaudeAI/top/?t=week"
                              # numbered list of posts with links
rawfetch <url> --json         # {"source_type", "url", "title", "text"}
rawfetch --version
```

Also runs as `python -m rawfetch <url>`.

The same video as above, as JSON (truncated):

```
$ rawfetch https://www.youtube.com/watch?v=jNQXAC9IVRw --json
{"source_type": "youtube", "url": "https://www.youtube.com/watch?v=jNQXAC9IVRw",
 "title": "Me at the zoo", "text": "All right, so here we are, in front of the…"}
```

## Exit codes

| code | meaning |
|------|---------|
| 0 | success |
| 1 | unexpected error |
| 2 | bad URL / usage |
| 3 | no captions on this video (none at all, or an empty transcript) |
| 4 | blocked by the source (YouTube IP gate / PO token, Reddit bot protection / rate limit) |
| 5 | unavailable (video private/deleted/region-locked; Reddit post or community deleted, removed, private, not found) |
| 6 | page fetch failed (HTTP error, nothing extractable, over the size cap, or a Reddit page that listed no posts) |
| 7 | network error: never reached the source at all (DNS, refused connection, timeout, or a broken proxy) |
| 8 | that source is not installed (Reddit without the `reddit` extra). The message says how to add it. |

## YouTube

Without `--lang`, English captions are tried first. If none of the requested languages exist, rawfetch falls back to any available
transcript (which may be in another language). It fails only when the video has no
captions at all.

YouTube gates caption access by IP address. From a normal home connection it just works.
From servers and datacenter IPs YouTube often blocks transcript requests or demands a
PO token, an extra check YouTube asks for before it serves the captions (exit code 4).
If you hit that, run rawfetch from a home connection or route it through a residential
proxy: a proxy whose traffic leaves through a home internet connection, so the site sees
a home address instead of a datacenter (see [Proxies](#proxies)).

## Reddit

In our tests in 2026, Reddit no longer served anonymous `.json`, and many AI assistants'
own web fetchers got a 403. A real browser still gets the page, so this path drives headless **WebKit**.
Chromium gets "blocked by network security", WebKit passes Reddit's JS check. No login,
no API key, no account.

What you get, by link type:

- **A post** (`/r/<sub>/comments/<id>/...`, share links, `redd.it`): title, post text,
  and the comments Reddit renders without clicking anything, about the top 30,
  best-first, nested replies indented. The header says how many of the total you are
  seeing. Collapsed reply branches are marked in place (`[+17 more replies not loaded]`)
  where the extractor finds the count. It does not catch every one yet.
- **Anything else** (a subreddit, `/top/?t=week`, `/search/?q=...`): a numbered list of
  posts with links. Fetch the one you want next. Search is the least reliable of these:
  Reddit guards it hardest (see below).

Output shape:

```
<post title>
r/<sub> · u/<author> · 120 points · 173 comments

<post text>

--- showing 30 of 173 comments (top of the thread as Reddit renders it) ---

u/<author> · 408 points
<comment text, verbatim>
    [+2 more replies not loaded]
    u/<author> · 31 points
    <reply text, verbatim>
```

### Reddit limits

- **Top of the thread only.** "Load more" is not clicked: each click is another request
  to Reddit, and a big thread would take hundreds of them. Roughly the top 30 is what
  most people read anyway; the counts tell you what was left.
- **Slow on purpose.** About 20 seconds per page: it waits for the page and scrolls
  gently. Use it to read threads, not to crawl. Hammering Reddit gets you blocked
  (exit code 4). If that happens, wait before retrying.
- **Search gets blocked first.** Search pages are Reddit's most protected. After a burst
  of requests ours got "blocked by network security" while post links and subreddit pages
  kept working, and the block was still there the next day. A logged-in person on the same
  connection was not affected. The error message says what Reddit answered (HTTP status
  and page title), so you can tell a block from a missing post without fetching again.
- **Reddit's terms.** Reddit does not welcome automated browsing. This is a personal
  reading tool: low volume, anonymous, read-only. Don't republish what it fetches.
- **It can break.** It reads the page Reddit renders today. If Reddit changes its markup
  or its bot checks, this path may stop working until updated.
- **Servers and cloud machines.** Reddit blocks many datacenter addresses outright, every
  page, not just search, so from a VPS or a cloud agent expect exit code 4. Run it from a
  home connection, or set `HTTPS_PROXY` to a residential proxy (see
  [Proxies](#proxies); tested on a Linux server: posts and subreddit pages work through
  one).

## Websites

Any URL that is not YouTube or Reddit is fetched as a plain web page and the main article
text is extracted verbatim. Static articles and blog posts work. JS-heavy apps and
paywalled pages may extract to nothing. rawfetch reports that honestly (exit code 6)
instead of inventing content.

## Proxies

rawfetch honours the standard `HTTPS_PROXY` / `HTTP_PROXY` / `NO_PROXY` environment
variables. YouTube and websites go through `requests`, which reads them; the Reddit path
hands `HTTPS_PROXY` / `HTTP_PROXY` to the browser (`NO_PROXY` does not apply there). This
is the practical answer to the YouTube and Reddit blocks above when you have to run from
a server:

```bash
HTTPS_PROXY=http://user:pass@proxy.example:8080 rawfetch <youtube-url>
```

A proxy that can't be reached is exit code 7 (network error), and the error message notes
that an environment proxy was in effect. When you see that, the proxy itself is the usual
suspect. Proxy credentials are never echoed back.

## General limits

**Size cap.** Page bodies over 5 MiB are refused (exit code 6) rather than buffered.
Article extraction allocates several times the input size, so an unbounded read turns a
fat URL into gigabytes of memory and minutes of CPU. rawfetch targets articles, not bulk
downloads.

**No URL filtering.** rawfetch fetches whatever URL you hand it, including `localhost`
and private network addresses, same as `curl` or any other HTTP client. It does not
protect you here: if you are driving rawfetch from an agent, do not feed it URLs from
untrusted input.

**Encoding.** When the server declares a charset, that is what the bytes are decoded as,
and bytes that do not fit it become `U+FFFD` rather than aborting the run. When no charset
is declared, the raw bytes go to the extractor, which reads the page's own `meta charset`
and falls back to UTF-8. So "verbatim" means verbatim up to undecodable bytes. That is the
one place rawfetch alters what it received, and it is stated here rather than hidden.

## If something goes wrong

- **`rawfetch: command not found` after a pip install.** pip may have put the script in a
  directory that is not on your PATH (common with `pip install --user`: `~/.local/bin` on
  Linux, `~/Library/Python/3.X/bin` on macOS). Add that directory to your PATH, or skip the
  problem entirely with `python -m rawfetch <url>`.
- **macOS: "You are using a frozen webkit browser which does not receive updates
  anymore".** Some macOS versions print this during the browser download. It comes from
  Playwright, not rawfetch, and Reddit fetching works regardless.
- **Linux: the browser fails to start with missing system libraries.** Run
  `sudo .venv/bin/playwright install-deps webkit` once.
- More cases, written for an AI agent but readable by people: the table at the end of
  [`INSTALL.md`](INSTALL.md).

## License

MIT

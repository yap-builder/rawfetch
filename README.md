# rawfetch

**Grab verbatim text from sources your AI can't reach — one command, zero LLM.**

Paste a YouTube link into an AI assistant and you get a guess. `rawfetch` prints the
actual captions. Capture, not judgment: raw text to stdout, nothing summarized,
nothing rewritten, honest errors when the source can't be reached.

Versus using the raw libraries yourself: one entry point for every source type,
one output contract (plain text, or `--json` with the same four fields), and a
deterministic, classed error contract — "no captions" is a different exit code
than "your IP is blocked", so scripts (and AI agents) can react correctly.

## Install

```bash
git clone https://github.com/yap-builder/rawfetch.git
cd rawfetch
pip install .
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
| 4 | blocked by YouTube (IP / bot protection / PO token) |
| 5 | video unavailable (private, deleted, region-locked, age-restricted) |
| 6 | website fetch failed (HTTP error, nothing extractable, or over the size cap) |
| 7 | network error: never reached the source at all (DNS, refused connection, timeout, or a broken proxy) |

## YouTube caveat

Caption access is IP-gated by YouTube. From a normal residential IP it just
works; from servers and datacenter IPs YouTube often blocks transcript
requests or demands a PO token (exit code 4). If you hit that, run rawfetch from
a home connection or route it through a residential proxy (see below).

## Proxies

rawfetch honours the standard `HTTPS_PROXY` / `HTTP_PROXY` / `NO_PROXY`
environment variables on both paths — YouTube and websites go through `requests`,
which reads them. This is the practical answer to the caveat above when you have
to run from a server:

```bash
HTTPS_PROXY=http://user:pass@proxy.example:8080 rawfetch <youtube-url>
```

A proxy that can't be reached is exit code 7 (network error), and the error
message notes that an environment proxy was in effect — when you see that, the
proxy itself is the usual suspect. Proxy credentials are never echoed back.

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

Planned: X threads, Reddit. Website fetch included as a fallback.

## License

MIT

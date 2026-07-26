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

## Usage

```bash
rawfetch <url>                # verbatim text to stdout
rawfetch <url> --lang ru,en   # YouTube caption language priority (ordered)
rawfetch <url> --json         # {"source_type", "url", "title", "text"}
```

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
| 3 | no captions on this video |
| 4 | blocked by YouTube (IP / bot protection / PO token) |
| 5 | video unavailable (private, deleted, region-locked, age-restricted) |
| 6 | website fetch failed |

## YouTube caveat

Caption access is IP-gated by YouTube. From a normal residential IP it just
works; from servers and datacenter IPs YouTube often blocks transcript
requests or demands a PO token (exit code 4). If you hit that, run rawfetch from
a home connection or route it through a residential proxy.

## Website fallback

Any non-YouTube URL is fetched as a plain web page and the main article text
is extracted verbatim. Static articles and blog posts work; JS-heavy apps and
paywalled pages may extract to nothing — rawfetch reports that honestly (exit
code 6) instead of inventing content.

## Roadmap

Planned: X threads, Reddit. Website fetch included as a fallback.

## License

MIT

# Installing rawfetch — instructions for an AI agent

You are installing rawfetch for a person. Follow these steps in order. Run commands from
the repository root (the folder that contains `install.sh`).

## 1. Ask one question first

Ask the person: **"Do you want Reddit support? It downloads a browser engine, about
300 MB."** YouTube captions and web articles are always included; only Reddit is
optional. Do not guess — the download is large.

## 2. Run the installer with the matching flag

```bash
./install.sh --reddit       # they said yes
./install.sh --no-reddit    # they said no
```

The flag skips the interactive menu. It installs into `.venv` inside this folder, needs
no sudo, and is safe to re-run (re-running with `--reddit` later adds Reddit).

## 3. Verify, and show the person the output

```bash
.venv/bin/rawfetch --version
.venv/bin/rawfetch https://peps.python.org/pep-0020/
```

Expected: the version line (`rawfetch 0.3.0` or newer), then the text of "The Zen of
Python" (it contains "Beautiful is better than ugly").

If Reddit was installed, also run exactly one Reddit fetch — a link to a public post
the person cares about (`https://www.reddit.com/r/<sub>/comments/<id>/...`).

Expected, after about 20 seconds: the post title, its text, then its top comments.
Do not loop or batch Reddit requests to "test more", and do not test search: repeated
requests get the person blocked, and search pages are blocked first.

## 4. Tell the person how to run it

Either the full path, `/path/to/rawfetch/.venv/bin/rawfetch <url>`, or add this line to
their shell profile (`~/.zshrc` on macOS, `~/.bashrc` on most Linux):

```bash
export PATH="/path/to/rawfetch/.venv/bin:$PATH"
```

Only edit their profile if they ask you to.

## When something goes wrong

| what you see | what to do |
|---|---|
| `rawfetch needs Python 3.9 or newer` | Install Python 3.9+ (python.org, or the system package manager), then re-run the installer. |
| "Could not create a virtual environment" (Debian/Ubuntu) | Ask the person, then `sudo apt install python3-venv` and re-run the installer. |
| `exit 8` / "Reddit support is not installed" | Run `./install.sh --reddit`. |
| Linux: browser fails to start, mentions missing libraries | Run `sudo .venv/bin/playwright install-deps webkit` — ask the person first, it needs sudo. |
| `exit 4` on a Reddit link | Reddit's bot protection or rate limit. Stop. Do not retry in a loop. A block on search can last more than a day; a post link may still work. |
| `exit 7` | Network never reached the source: check the connection or any `HTTPS_PROXY` setting. |
| `playwright install webkit` fails mid-download | Re-run `./install.sh --reddit`; it retries the download. |

All exit codes are listed in the README under "Exit codes".

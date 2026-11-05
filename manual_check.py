#!/usr/bin/env python3
"""Manual LIVE check for rawfetch — deliberately NOT pytest.

WHY: YouTube captions are IP-gated (datacenter IPs get blocked), so live calls in the
test suite would flap on CI. Run this by hand on a residential IP and eyeball that the
output is verbatim. Usage: python3 manual_check.py [youtube_url] [article_url]

Reddit cases run only when the `reddit` extra is installed, and only two of them, spaced
out: this is an eyeball check, not a load test — repeated requests get an IP blocked.

Uses sys.executable, not a hardcoded interpreter path: the dependencies live in whatever
environment you installed into, which is usually a venv and almost never /usr/bin/python3.
"""
import subprocess
import sys

YT = sys.argv[1] if len(sys.argv) > 1 else "https://www.youtube.com/watch?v=jNQXAC9IVRw"
ART = sys.argv[2] if len(sys.argv) > 2 else "https://peps.python.org/pep-0020/"
PY = sys.executable
GONE = "https://www.youtube.com/watch?v=aaaaaaaaaaa"

CASES = [
    [PY, "-m", "rawfetch", YT],
    [PY, "-m", "rawfetch", YT, "--json"],
    [PY, "-m", "rawfetch", ART],
    [PY, "-m", "rawfetch", GONE],  # expect nonzero
]

try:
    import playwright  # noqa: F401  (only to decide whether to run the Reddit cases)
    CASES += [
        [PY, "-m", "rawfetch", "https://www.reddit.com/r/Python/top/?t=week"],
        [PY, "-m", "rawfetch", "https://www.reddit.com/r/Python/comments/zzzzzzz/x/"],  # 5
    ]
except ImportError:
    print("(reddit extra not installed: skipping Reddit cases)")

for cmd in CASES:
    print("=" * 60)
    print("$", " ".join(cmd))
    p = subprocess.run(cmd, capture_output=True, text=True, timeout=120)
    print("exit:", p.returncode)
    print("stdout[:400]:", p.stdout[:400])
    if p.stderr.strip():
        print("stderr:", p.stderr.strip()[:300])

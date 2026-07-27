"""Allow `python -m rawfetch <url>` alongside the installed `rawfetch` command."""
import sys

from rawfetch.cli import main

if __name__ == "__main__":
    sys.exit(main())

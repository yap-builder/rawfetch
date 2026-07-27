"""rawfetch — verbatim text from sources your AI can't reach. One command, zero LLM.

WHY: pasting a YouTube link into an AI assistant gets a guess; rawfetch prints the actual
captions. Capture, not judgment: raw text to stdout, honest classed errors to stderr
(no captions != IP block != video gone). YouTube today; X threads and Reddit planned;
plain websites included as a fallback.
"""
import warnings

# Narrow, not blanket: LibreSSL Macs emit this on every urllib3 import and it is noise for
# a CLI whose stdout is meant to be piped. Filtered by message so real warnings still show,
# and here in __init__ so submodules keep clean top-level imports.
warnings.filterwarnings(
    "ignore", message="urllib3 v2 only supports OpenSSL", module="urllib3")

__version__ = "0.2.0"
__all__ = ["__version__"]

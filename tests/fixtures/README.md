# Test fixtures

## `article.html`

A saved copy of <https://peps.python.org/pep-0020/> — the rendered "Zen of Python" page.

**Why this page.** Extraction has to be tested against real-world markup, not a hand-made
snippet: a hand-made one would only prove the extractor handles markup written to please
it. This page has the shape that matters — site chrome, navigation, a table of contents,
and footer boilerplate wrapped around a short body of actual prose — so a test that finds
"Beautiful is better than ugly" in the output is proving the extractor discarded the
furniture.

**Why it is safe to redistribute.** PEP 20 places itself in the public domain (see its own
Copyright section), and the surrounding page is python.org site markup, included here only
as an offline test input, unmodified and not served to anyone.

**Refreshing it.** Nothing here depends on the page staying current — it is frozen input,
and freezing is the point: if the live page changes, the tests must not change with it.
If you do replace it, keep a page whose article text is short and distinctive enough to
assert on.

"""Text cleaning and section-extraction utilities for SEC HTML filings."""

import re
from typing import Optional

from selectolax.parser import HTMLParser


def normalize_whitespace(text: str) -> str:
    """
    Collapse runs of whitespace (spaces, tabs, newlines) into single spaces
    and strip leading/trailing whitespace.

    Args:
        text: Input string.

    Returns:
        Whitespace-normalised string.
    """
    return re.sub(r"\s+", " ", text).strip()


def strip_html_to_text(html: str) -> str:
    """
    Convert an HTML document to plain text suitable for regex extraction.

    Uses selectolax for fast parsing. Preserves block-level structure by
    inserting newlines around block elements so section boundaries survive
    the conversion.

    Args:
        html: Raw HTML string (e.g. from a SEC EDGAR prospectus page).

    Returns:
        Plain text with normalised line breaks.
    """
    if not html:
        return ""

    tree = HTMLParser(html)

    # Remove non-content nodes entirely
    for tag in tree.css("script, style, head"):
        tag.decompose()

    # Insert newlines around common block elements so text stays readable
    _BLOCK_TAGS = {
        "p", "div", "tr", "li", "h1", "h2", "h3", "h4", "h5", "h6",
        "table", "br", "hr", "blockquote", "pre",
    }
    for node in tree.css(", ".join(_BLOCK_TAGS)):
        # Prepend a newline via the text content trick — selectolax exposes
        # .text() so we work at the tree level rather than mutating nodes.
        pass  # handled below via text(separator)

    raw = tree.text(separator="\n")

    # Collapse runs of blank lines to at most two, keep single newlines
    text = re.sub(r"\n{3,}", "\n\n", raw)
    # Strip trailing spaces on each line
    text = "\n".join(line.rstrip() for line in text.splitlines())
    return text.strip()


# Section boundary: a line that looks like a heading (all-caps words,
# or Title-Cased short line, or a line ending with a colon).
_SECTION_BOUNDARY = re.compile(
    r"^(?:[A-Z][A-Z\s\-,&]{4,}|[A-Z][a-z]+(?:\s+[A-Z][a-z]+){1,6})\s*$",
    re.MULTILINE,
)

# Maximum characters returned from a matched section
_SECTION_WINDOW = 8_000


def find_section(text: str, section_titles: list[str]) -> Optional[str]:
    """
    Locate a named section in plain text and return its content.

    Searches for each entry in section_titles (case-insensitive substring
    match). Returns text from the first match onward, stopping at the next
    detected section boundary or after _SECTION_WINDOW characters —
    whichever comes first.

    Args:
        text: Plain text (typically from strip_html_to_text).
        section_titles: Candidate section header strings to search for,
                        in priority order.

    Returns:
        Section text if found, otherwise None.
    """
    for title in section_titles:
        pattern = re.compile(re.escape(title), re.IGNORECASE)
        match = pattern.search(text)
        if match is None:
            continue

        start = match.start()
        window = text[start: start + _SECTION_WINDOW]

        # Try to cut off at the next section boundary after the title line
        lines = window.splitlines()
        result_lines: list[str] = []
        for i, line in enumerate(lines):
            result_lines.append(line)
            # After we've consumed at least a few lines, stop at the next
            # heading-like boundary (skip the very first line which is the
            # matched title itself)
            if i > 2 and _SECTION_BOUNDARY.match(line.strip()):
                break

        return "\n".join(result_lines).strip()

    return None

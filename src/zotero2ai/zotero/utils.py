"""Utility functions for Zotero data processing."""

import re
from html import unescape


def clean_html(html_content: str, preserve_newlines: bool = False) -> str:
    """Remove HTML tags and unescape entities from a string.

    Args:
        html_content: String containing HTML tags.
        preserve_newlines: Whether to keep newlines instead of collapsing to single space.

    Returns:
        Cleaned plain text string.
    """
    if not html_content:
        return ""

    # Remove head, script and style elements COMPLETELY (including content)
    # Using non-greedy match to handle multiple blocks
    # We use a very robust pattern to avoid regex recursion limits on huge files
    for tag in ["head", "script", "style", "svg", "header", "footer", "nav"]:
        pattern = re.compile(f"<{tag}[^>]*?>.*?</{tag}>", re.DOTALL | re.IGNORECASE)
        html_content = pattern.sub("", html_content)

    cleaned = html_content

    # Replace <br>, </p>, </div> tags with newlines if preserving
    if preserve_newlines:
        cleaned = re.sub(r"<(br|p|div|tr|h\d)[^>]*?>", "\n", cleaned, flags=re.IGNORECASE)

    # Replace <img> tags with placeholders
    def replace_img(match: re.Match) -> str:
        alt = re.search(r'alt=["\'](.*?)["\']', match.group(0), re.IGNORECASE)
        if alt:
            return f" [Image: {alt.group(1)}] "
        return " [Image] "

    cleaned = re.sub(r"<img[^>]*?>", replace_img, cleaned, flags=re.IGNORECASE)

    # Remove all remaining HTML tags
    clean_re = re.compile("<[^>]*?>")
    cleaned = clean_re.sub("", cleaned)

    if preserve_newlines:
        # Normalize whitespace while keeping structure
        # Replace 3+ newlines with 2
        cleaned = re.sub(r"\r\n", "\n", cleaned)
        cleaned = re.sub(r" [ \t]+", " ", cleaned)  # Collapse horizontal whitespace
        cleaned = re.sub(r"\n\s*\n\s*\n+", "\n\n", cleaned)
        cleaned = cleaned.strip()
    else:
        # Replace multiple whitespaces/newlines with a single space
        cleaned = re.sub(r"\s+", " ", cleaned).strip()

    return unescape(cleaned)


def clean_html_snippet(html_content: str) -> str:
    """Thin wrapper around clean_html for backward compat and snippets."""
    return clean_html(html_content, preserve_newlines=False)


def generate_friendly_name(content: str, max_length: int = 50) -> str:
    """Generate a friendly display name from note content.

    Args:
        content: HTML or plain text content of the note.
        max_length: Maximum length of the generated name.

    Returns:
        A human-readable snippet of the content.
    """
    cleaned = clean_html_snippet(content)
    if not cleaned:
        return "Untitled Note"

    if len(cleaned) <= max_length:
        return cleaned

    # Try to cut at the last word
    truncated = cleaned[:max_length]
    last_space = truncated.rfind(" ")

    if last_space > 0:
        return truncated[:last_space].strip() + "..."

    return truncated.strip() + "..."

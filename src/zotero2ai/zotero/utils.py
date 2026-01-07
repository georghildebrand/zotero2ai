"""Utility functions for Zotero data processing."""

import re
from html import unescape


def clean_html(html_content: str) -> str:
    """Remove HTML tags and unescape entities from a string.

    Args:
        html_content: String containing HTML tags.

    Returns:
        Cleaned plain text string.
    """
    if not html_content:
        return ""

    # Remove script and style elements
    clean_re = re.compile("<(script|style)[^>]*?>.*?</\\1>", re.DOTALL | re.IGNORECASE)
    cleaned = clean_re.sub("", html_content)

    # Remove all other HTML tags
    clean_re = re.compile("<[^>]*?>")
    cleaned = clean_re.sub("", cleaned)

    # Replace multiple whitespaces/newlines with a single space
    cleaned = re.sub(r"\s+", " ", cleaned).strip()

    return unescape(cleaned)


def generate_friendly_name(content: str, max_length: int = 50) -> str:
    """Generate a friendly display name from note content.

    Args:
        content: HTML or plain text content of the note.
        max_length: Maximum length of the generated name.

    Returns:
        A human-readable snippet of the content.
    """
    cleaned = clean_html(content)
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

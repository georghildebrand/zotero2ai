import re
from html import unescape
from re import Match
from typing import Any


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

    # Strip base64 data URIs FIRST before any tag processing.
    # SingleFile-saved HTML pages embed fonts/images as base64 blobs directly
    # in <style> tags (e.g. url(data:font/woff2;base64,...)) which are hundreds
    # of KB each. Removing them early makes subsequent regex much faster.
    html_content = re.sub(r"data:[a-zA-Z0-9+/\-]+;base64,[A-Za-z0-9+/=]+", "", html_content)

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
    def replace_img(m: Match[str]) -> str:
        alt = re.search(r'alt=["\'](.*?)["\']', m.group(0), re.IGNORECASE)
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


def normalize_tags(raw_tags: object) -> list[str]:
    """Normalize Zotero tag payloads to a list of tag strings.

    The bridge can return tags as either:
    - list[str]
    - list[dict] with shape {"tag": "..."}
    - None / empty
    """
    if raw_tags is None:
        return []
    if not isinstance(raw_tags, list):
        return []

    normalized: list[str] = []
    for tag in raw_tags:
        if isinstance(tag, dict):
            value = tag.get("tag", "")
            if isinstance(value, str) and value:
                normalized.append(value)
            continue
        if isinstance(tag, str) and tag:
            normalized.append(tag)
            continue
        normalized.append(str(tag))
    return normalized


def repair_text_encoding(text: str) -> str:
    """Best-effort repair for common UTF-8/Latin-1 mojibake."""
    if not text:
        return text

    suspicious_markers = ("Ã", "Â", "â", "ð", "\ufffd")
    if not any(marker in text for marker in suspicious_markers):
        return text

    try:
        repaired = text.encode("latin-1").decode("utf-8")
    except (UnicodeEncodeError, UnicodeDecodeError):
        return text

    original_score = sum(text.count(marker) for marker in suspicious_markers)
    repaired_score = sum(repaired.count(marker) for marker in suspicious_markers)
    if repaired_score < original_score:
        return repaired
    return text


def repair_payload_encoding(value: Any) -> Any:
    """Recursively repair common mojibake in JSON-like payloads."""
    if isinstance(value, str):
        return repair_text_encoding(value)
    if isinstance(value, list):
        return [repair_payload_encoding(item) for item in value]
    if isinstance(value, dict):
        return {key: repair_payload_encoding(item) for key, item in value.items()}
    return value

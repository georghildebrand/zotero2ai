import logging
import re
from difflib import SequenceMatcher
from typing import Any, cast

from mcp.server.fastmcp import FastMCP
from zotero2ai.mcp_server.common import get_client
from zotero2ai.zotero.collections import ActiveCollectionManager
from zotero2ai.zotero.memory import MemoryManager
from zotero2ai.zotero.utils import clean_html, generate_friendly_name

logger = logging.getLogger(__name__)


def _normalize_search_text(value: str) -> str:
    normalized = re.sub(r"[^a-z0-9]+", " ", value.lower())
    return re.sub(r"\s+", " ", normalized).strip()


def _search_tokens(query: str) -> list[str]:
    stopwords = {
        "pdf",
        "we",
        "hk",
        "abrg",
        "korr",
        "und",
        "der",
        "die",
        "das",
    }
    tokens: list[str] = []
    for token in _normalize_search_text(query).split():
        if len(token) <= 1:
            continue
        if token in stopwords:
            continue
        tokens.append(token)
    return tokens


def _similarity_score(query: str, *texts: str) -> float:
    normalized_query = _normalize_search_text(query)
    if not normalized_query:
        return 0.0

    best = 0.0
    query_tokens = set(_search_tokens(query))
    for text in texts:
        normalized_text = _normalize_search_text(text or "")
        if not normalized_text:
            continue
        ratio = SequenceMatcher(None, normalized_query, normalized_text).ratio()
        text_tokens = set(normalized_text.split())
        overlap = len(query_tokens & text_tokens) / max(len(query_tokens), 1)
        best = max(best, ratio * 0.65 + overlap * 0.35)
    return best


def _document_search_variants(query: str) -> list[str]:
    normalized = _normalize_search_text(query)
    tokens = _search_tokens(query)
    variants: list[str] = [query]
    if normalized and normalized != query:
        variants.append(normalized)
    if tokens:
        variants.append(" ".join(tokens))
        if len(tokens) > 4:
            variants.append(" ".join(sorted(tokens, key=len, reverse=True)[:4]))

    deduped: list[str] = []
    seen: set[str] = set()
    for variant in variants:
        compact = variant.strip()
        if not compact:
            continue
        key = compact.lower()
        if key in seen:
            continue
        seen.add(key)
        deduped.append(compact)
    return deduped


def _token_fallback_variants(query: str, max_tokens: int = 8) -> list[str]:
    """Build additional robust token fallbacks for long, punctuation-heavy titles."""
    stopwords = {
        "and",
        "the",
        "of",
        "for",
        "with",
        "through",
        "into",
        "from",
        "a",
        "an",
        "to",
    }
    variants: list[str] = []
    seen: set[str] = set()
    for token in _normalize_search_text(query).split():
        if len(token) < 4:
            continue
        if token in stopwords:
            continue
        if token in seen:
            continue
        seen.add(token)
        variants.append(token)
        if len(variants) >= max_tokens:
            break
    return variants


def _format_item_result(item: dict[str, Any], score: float | None = None, reason: str | None = None) -> str:
    creators_list = item.get("creators", [])
    creators = ", ".join(creators_list) if creators_list else "Unknown Authors"
    item_info = (
        f"### {item.get('title', 'Untitled')}\n"
        f"- Key: {item['key']}\n"
        f"- Type: {item.get('itemType', 'unknown')}\n"
        f"- Creators: {creators}\n"
        f"- Date: {item.get('date', 'Unknown')}"
    )
    if score is not None:
        item_info += f"\n- Match Score: {score:.3f}"
    if reason:
        item_info += f"\n- Match Reason: {reason}"
    if item.get("url"):
        item_info += f"\n- URL: {item['url']}"
    if item.get("tags"):
        item_info += f"\n- Tags: {', '.join(item['tags'])}"

    attachments = item.get("attachments", [])
    if attachments:
        item_info += "\n- Attachments:"
        for att in attachments:
            item_info += f"\n  - {att['title']} ({att['contentType']})"
            if att.get("path"):
                item_info += f"\n    Path: `{att['path']}`"
    return item_info


def _rank_document_candidates(query: str, items: list[dict[str, Any]], reason: str) -> list[tuple[float, dict[str, Any], str]]:
    ranked: list[tuple[float, dict[str, Any], str]] = []
    for item in items:
        candidate_texts = [item.get("title", "")]
        for attachment in item.get("attachments", []):
            candidate_texts.append(attachment.get("title", ""))
            candidate_texts.append(attachment.get("path", ""))
        score = _similarity_score(query, *candidate_texts)
        if score > 0:
            ranked.append((score, item, reason))
    ranked.sort(key=lambda entry: entry[0], reverse=True)
    return ranked

def register_item_tools(mcp: FastMCP):
    # Legacy helper: intentionally not exposed as MCP tool anymore.
    # Keep it temporarily for local fallback/reference during migration.
    def search_papers(query: str | None = None, tag: str | None = None, collection_key: str | None = None, limit: int = 10) -> str:
        """Search for papers by title or tag in the Zotero library.

        Args:
            query: Optional search query for titles.
            tag: Optional tag to filter by.
            collection_key: Optional collection key to search within.
            limit: Maximum number of results.
        """
        try:
            with get_client() as client:
                items = client.search_items(query=query, tag=tag, collection_key=collection_key, limit=limit)
                if not items:
                    msg = "No papers found"
                    if query: msg += f" matching '{query}'"
                    if tag: msg += f" with tag '{tag}'"
                    if collection_key: msg += f" in collection '{collection_key}'"
                    return msg + "."

                lines = []
                for item in items:
                    if "error" in item:
                        lines.append(f"### Item {item.get('key', 'unknown')}\n- Error: {item['error']}")
                        continue
                    lines.append(_format_item_result(item))
                return "\n\n".join(lines)
        except Exception as e:
            return f"Error searching papers: {str(e)}"

    @mcp.tool()
    def find_document(query: str, collection_key: str | None = None, limit: int = 5, cursor: int = 0) -> str:
        """Find a Zotero document by consolidated multi-strategy retrieval.

        Strategies are executed together (title/keyword, token fallback, and optional
        collection scans), then merged and de-duplicated into one ranked result set.
        """
        try:
            with get_client() as client:
                capped_limit = max(1, min(limit, 10))
                safe_cursor = max(0, cursor)
                candidate_map: dict[str, dict[str, Any]] = {}

                def add_candidates(items: list[dict[str, Any]], reason: str) -> None:
                    for score, item, _ in _rank_document_candidates(query, items, reason):
                        key = item["key"]
                        existing = candidate_map.get(key)
                        if not existing:
                            candidate_map[key] = {
                                "score": score,
                                "item": item,
                                "reasons": {reason},
                            }
                            continue
                        if score > float(existing["score"]):
                            existing["score"] = score
                        cast_reasons = existing["reasons"]
                        if isinstance(cast_reasons, set):
                            cast_reasons.add(reason)

                # Strategy 1: collection-constrained scan when explicitly requested.
                if collection_key:
                    items = client.get_collection_items(collection_key, limit=500)
                    add_candidates(items, f"collection-constrained scan in {collection_key}")

                # Strategy 2: direct query variants over item search.
                for variant in _document_search_variants(query):
                    items = client.search_items(query=variant, collection_key=collection_key, limit=max(limit, 10))
                    add_candidates(items, f"title search via '{variant}'")

                # Strategy 3: token fallback queries for long phrases.
                for token_variant in _token_fallback_variants(query):
                    items = client.search_items(query=token_variant, collection_key=collection_key, limit=max(limit, 10))
                    add_candidates(items, f"token fallback via '{token_variant}'")

                # Strategy 4: semantic collection discovery + collection scans (global mode only).
                collection_queries: list[str] = []
                tokens = _search_tokens(query)
                if tokens:
                    collection_queries.append(" ".join(sorted(tokens, key=len, reverse=True)[:2]))
                    collection_queries.extend(sorted(tokens, key=len, reverse=True)[:3])

                candidate_collections: dict[str, dict[str, Any]] = {}
                for collection_query in collection_queries:
                    for collection in client.search_collections(collection_query, limit=5):
                        candidate_collections[collection["key"]] = collection

                ranked_collection_keys = sorted(
                    candidate_collections,
                    key=lambda key: _similarity_score(
                        query,
                        candidate_collections[key].get("name", ""),
                        candidate_collections[key].get("fullPath", ""),
                    ),
                    reverse=True,
                )

                if not collection_key:
                    for key in ranked_collection_keys[:3]:
                        collection = candidate_collections[key]
                        items = client.get_collection_items(key, limit=100)
                        add_candidates(items, f"collection scan in {collection.get('fullPath', key)}")

                consolidated = sorted(
                    [
                        (float(data["score"]), data["item"], ", ".join(sorted(cast(set[str], data["reasons"]))))
                        for data in candidate_map.values()
                    ],
                    key=lambda entry: entry[0],
                    reverse=True,
                )
                total = len(consolidated)
                if total == 0:
                    if collection_key:
                        return f"No documents found matching '{query}' in collection '{collection_key}'."
                    return f"No documents found matching '{query}'."

                page = consolidated[safe_cursor:safe_cursor + capped_limit]
                next_cursor = safe_cursor + capped_limit if safe_cursor + capped_limit < total else None

                lines = [
                    "## Document Matches",
                    "- Strategy: consolidated multi-retrieval",
                    f"- Query: {query}",
                    f"- Total candidates: {total}",
                    f"- Returned: {len(page)} (cursor={safe_cursor}, limit={capped_limit})",
                ]
                if collection_key:
                    lines.append(f"- Collection: {collection_key}")
                if next_cursor is not None:
                    lines.append(f"- Next cursor: {next_cursor}")

                for score, item, reason in page:
                    lines.append("")
                    lines.append(_format_item_result(item, score=score, reason=reason))
                return "\n".join(lines)
        except Exception as e:
            return f"Error finding document: {str(e)}"

    @mcp.tool()
    def get_recent_papers(limit: int = 5) -> str:
        """Get the most recently added papers from Zotero."""
        try:
            with get_client() as client:
                items = client.get_recent_items(limit=limit)
                if not items: return "No papers found."
                lines = []
                for item in items:
                    if "error" in item:
                        lines.append(f"### Item {item.get('key', 'unknown')}\n- Error: {item['error']}")
                        continue
                    creators_list = item.get("creators", [])
                    creators = ", ".join(creators_list) if creators_list else "Unknown Authors"
                    item_info = f"### {item.get('title', 'Untitled')}\n- Key: {item['key']}\n- Creators: {creators}"
                    attachments = item.get("attachments", [])
                    if attachments:
                        item_info += "\n- Attachments:"
                        for att in attachments:
                            item_info += f"\n  - {att['title']} ({att['contentType']})"
                    lines.append(item_info)
                return "\n\n".join(lines)
        except Exception as e:
            return f"Error fetching recent papers: {str(e)}"

    @mcp.tool()
    def read_note(key: str) -> str:
        """Read the full content of a Zotero note by its key."""
        try:
            with get_client() as client:
                note = client.get_note(key)
                if not note: return f"Note with key {key} not found."
                return f"## Note {key}\n\n{note.get('note', 'No content.')}"
        except Exception as e:
            return f"Error reading note: {str(e)}"

    @mcp.tool()
    def list_notes(collection_key: str | None = None, parent_item_key: str | None = None) -> str:
        """List notes from Zotero."""
        try:
            with get_client() as client:
                manager = ActiveCollectionManager(client)
                if not collection_key and not parent_item_key:
                    collection_key = manager.get_active_collection_key()
                if not collection_key and not parent_item_key:
                    return "Error: Provide a collection_key, parent_item_key, or set an active collection first."
                notes = client.get_notes(collection_key=collection_key, parent_item_key=parent_item_key)
                if not notes: return "No notes found."
                lines = [f"- {generate_friendly_name(n.get('note', ''))} ({n['key']})" for n in notes]
                return "Available Notes:\n" + "\n".join(lines)
        except Exception as e:
            return f"Error listing notes: {str(e)}"

    @mcp.tool()
    def list_notes_recursive(collection_key: str, date_from: str | None = None, date_to: str | None = None, include_content: bool = False, query: str | None = None, max_items: int = 200, cursor: int = 0) -> str:
        """Bulk-read notes recursively."""
        import json
        try:
            with get_client() as client:
                mm = MemoryManager(client)
                result = mm.list_notes_recursive(collection_key=collection_key, date_from=date_from, date_to=date_to, include_content=include_content, query=query, max_items=max_items, cursor=cursor)
                return json.dumps(result, indent=2, default=str)
        except Exception as e:
            return f"Error in list_notes_recursive: {str(e)}"

    @mcp.tool()
    def create_or_extend_note(content: str, note_key: str | None = None, parent_item_key: str | None = None, collection_key: str | None = None, extend: bool = False, tags: list[str] | None = None, related: list[str] | None = None) -> str:
        """Create or extend a Zotero note."""
        try:
            with get_client() as client:
                if extend and note_key:
                    client.extend_note(note_key, content)
                    if tags or related: client.update_note(note_key, tags=tags or None, related=related or None)
                    return f"Successfully extended note {note_key}."
                if note_key:
                    client.update_note(note_key, content=content, tags=tags if tags else None, related=related if related else None)
                    return f"Successfully updated note {note_key}."
                target_collection = collection_key
                if not target_collection and not parent_item_key:
                    target_collection = ActiveCollectionManager(client).get_active_collection_key()
                if not target_collection and not parent_item_key:
                    return "Error: target not resolved."
                result = client.create_note(content=content, parent_item_key=parent_item_key, collections=[target_collection] if target_collection else None, tags=tags if tags else None)
                new_key = result.get("key", "")
                if related and new_key: client.update_note(new_key, related=related)
                return f"Successfully created note. Key: {new_key}"
        except Exception as e:
            return f"Error in create_or_extend_note: {str(e)}"

    @mcp.tool()
    def get_item_attachments(item_key: str) -> str:
        """Get attachments for an item."""
        try:
            with get_client() as client:
                item = client.get_item(item_key)
                if not item: return f"Item {item_key} not found."
                attachments = item.get("attachments", [])
                if not attachments and item.get("itemType") != "attachment": return "No attachments."
                lines = [f"## Attachments for: {item.get('title', item_key)}"]
                if item.get("itemType") == "attachment": attachments = [item]
                for att in attachments:
                    lines.append(f"- {att['title']} ({att['contentType']}) [Key: {att['key']}]")
                    if att.get("path"): lines.append(f"  Path: `{att['path']}`")
                return "\n".join(lines)
        except Exception as e:
            return f"Error getting attachments: {str(e)}"

    @mcp.tool()
    def get_item_content(key: str) -> str:
        """Get text content of an item (PDF/HTML)."""
        try:
            with get_client() as client:
                data = client.get_item_content(key)
                if not data: return "No content."
                content = data.get("content") or ""
                if filename := data.get("filename"):
                    if filename.lower().endswith((".html", ".htm")):
                        content = clean_html(content, preserve_newlines=True)
                return f"## Content of {data.get('filename', 'Unknown')}\n\n{content}"
        except Exception as e:
            return f"Error getting content: {str(e)}"

    @mcp.tool()
    def rename_tag(old_name: str, new_name: str) -> str:
        """Rename a tag."""
        try:
            with get_client() as client:
                client.rename_tag(old_name, new_name)
                return f"Renamed {old_name} to {new_name}."
        except Exception as e:
            return f"Error renaming tag: {str(e)}"

    @mcp.tool()
    def list_tags() -> str:
        """List all tags."""
        try:
            with get_client() as client:
                tags = client.get_tags()
                return "Available Tags:\n- " + "\n- ".join(tags) if tags else "No tags."
        except Exception as e:
            return f"Error listing tags: {str(e)}"

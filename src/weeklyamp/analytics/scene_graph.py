"""Scene Graph — extract entities from newsletter content and build
an interconnected knowledge base of artists, venues, labels, producers,
and cities mentioned across published issues.

The extractor uses regex/heuristic patterns only (no AI calls) so it
can run cheaply on every publish.
"""

from __future__ import annotations

import html
import json
import logging
import re
import unicodedata
from typing import Optional

logger = logging.getLogger(__name__)

# ---------------------------------------------------------------------------
# Slugify helper
# ---------------------------------------------------------------------------

def slugify(text: str) -> str:
    """Lowercase, strip non-alphanumeric, replace spaces with hyphens."""
    text = unicodedata.normalize("NFKD", text)
    text = text.encode("ascii", "ignore").decode("ascii")
    text = text.lower().strip()
    text = re.sub(r"[^a-z0-9\s-]", "", text)
    text = re.sub(r"[\s_-]+", "-", text)
    return text.strip("-")


# ---------------------------------------------------------------------------
# Known music cities (common major cities + locales from data/locales/)
# ---------------------------------------------------------------------------

_MUSIC_CITIES = {
    # Major US
    "New York", "Los Angeles", "Nashville", "Austin", "Chicago",
    "Atlanta", "Miami", "Detroit", "Memphis", "New Orleans",
    "Philadelphia", "Seattle", "San Francisco", "Portland",
    "Minneapolis", "Denver", "Dallas", "Houston",
    "Brooklyn", "Oakland", "Las Vegas", "San Diego",
    "Kansas City", "St. Louis", "Cleveland", "Milwaukee",
    "Boston", "Baltimore", "Pittsburgh", "Cincinnati",
    # International
    "London", "Berlin", "Tokyo", "Lagos", "Havana",
    "Paris", "Toronto", "Montreal", "Melbourne", "Sydney",
    "Manchester", "Bristol", "Glasgow", "Kingston",
    "Ibiza", "Amsterdam", "Seoul", "Mumbai", "Johannesburg",
    "Rio de Janeiro", "Buenos Aires", "Mexico City",
    "Stockholm", "Copenhagen", "Accra",
    # Local editions
    "Tucson", "Corrales",
}


def _load_locale_cities() -> set[str]:
    """Load city names from data/locales/*.yaml if available."""
    import os
    from pathlib import Path

    cities = set(_MUSIC_CITIES)
    locales_dir = Path(__file__).parent.parent.parent.parent / "data" / "locales"
    if locales_dir.is_dir():
        for f in locales_dir.glob("*.yaml"):
            # File name pattern: city-state.yaml -> city
            stem = f.stem  # e.g. "tucson-az"
            parts = stem.rsplit("-", 1)
            if parts:
                city_name = parts[0].replace("-", " ").title()
                cities.add(city_name)
    return cities


_ALL_CITIES: set[str] | None = None


def _get_cities() -> set[str]:
    global _ALL_CITIES
    if _ALL_CITIES is None:
        _ALL_CITIES = _load_locale_cities()
    return _ALL_CITIES


# ---------------------------------------------------------------------------
# HTML text extraction
# ---------------------------------------------------------------------------

_TAG_RE = re.compile(r"<[^>]+>")
_MULTI_SPACE = re.compile(r"\s+")
_SECTION_RE = re.compile(
    r'<(?:h[1-3]|div)[^>]*(?:class|id)=["\'][^"\']*section[^"\']*["\'][^>]*>(.*?)</(?:h[1-3]|div)>',
    re.IGNORECASE | re.DOTALL,
)


def _strip_tags(text: str) -> str:
    return _MULTI_SPACE.sub(" ", _TAG_RE.sub(" ", text)).strip()


def _html_to_sections(html_content: str) -> list[dict]:
    """Split HTML into rough sections. Each dict has 'slug' and 'text'."""
    if not html_content:
        return []

    # Try to split on headings
    heading_re = re.compile(
        r'<h[1-3][^>]*>(.*?)</h[1-3]>',
        re.IGNORECASE | re.DOTALL,
    )
    parts = heading_re.split(html_content)
    sections = []
    current_slug = "intro"
    current_text = ""

    for i, part in enumerate(parts):
        if i % 2 == 0:
            # Content block
            current_text += " " + _strip_tags(part)
        else:
            # Heading — flush previous section
            if current_text.strip():
                sections.append({
                    "slug": current_slug,
                    "text": current_text.strip(),
                })
            current_slug = slugify(_strip_tags(part)) or "section"
            current_text = ""

    if current_text.strip():
        sections.append({"slug": current_slug, "text": current_text.strip()})

    if not sections:
        # Fallback: whole thing as one section
        sections.append({"slug": "full", "text": _strip_tags(html_content)})

    return sections


# ---------------------------------------------------------------------------
# Entity extraction patterns
# ---------------------------------------------------------------------------

# Bold/strong text (often artist names in newsletters)
_BOLD_RE = re.compile(r"<(?:b|strong)[^>]*>(.*?)</(?:b|strong)>", re.IGNORECASE | re.DOTALL)

# Link text
_LINK_RE = re.compile(r'<a[^>]*>(.*?)</a>', re.IGNORECASE | re.DOTALL)

# Venue patterns: "at [Venue Name]", "live at [Venue Name]", "@ [Venue Name]"
_VENUE_RE = re.compile(
    r'(?:(?:live\s+)?at|@)\s+(?:the\s+)?([A-Z][A-Za-z\'\-\.\s]{2,40}?)(?:\s+(?:in|on|for|this|last|next|tonight|,|\.|$))',
    re.MULTILINE,
)

# Label patterns: "on [Label]", "signed to [Label]", "released on [Label]", "via [Label]"
_LABEL_RE = re.compile(
    r'(?:(?:released?\s+)?on|signed\s+to|via)\s+([A-Z][A-Za-z\'\-\.\s]{2,40}?)(?:\s+(?:Records?|Music|Entertainment|Label|Group|Audio))?(?:\s*[,\.\)]|\s+(?:and|with|for|the|this|in|at|$))',
    re.MULTILINE,
)

# Producer patterns: "produced by [Name]", "production by [Name]"
_PRODUCER_RE = re.compile(
    r'(?:produced?|production|mixed|mastered)\s+by\s+([A-Z][A-Za-z\'\-\.\s]{2,40}?)(?:\s*[,\.\)]|\s+(?:and|with|for|the|at|$))',
    re.IGNORECASE | re.MULTILINE,
)

# Words to skip — common false positives
_SKIP_WORDS = frozenset({
    "the", "a", "an", "and", "or", "but", "in", "on", "at", "to",
    "for", "of", "with", "by", "from", "this", "that", "it", "is",
    "are", "was", "were", "be", "been", "have", "has", "had", "do",
    "does", "did", "will", "would", "could", "should", "may", "might",
    "can", "must", "shall", "not", "no", "yes", "all", "each",
    "every", "both", "few", "more", "most", "other", "some", "such",
    "only", "very", "just", "also", "still", "already", "too",
    "here", "there", "now", "then", "when", "where", "how", "what",
    "who", "which", "why", "click", "read", "more", "subscribe",
    "listen", "watch", "check", "out", "learn", "view", "full",
    "new", "album", "single", "track", "song", "release", "tour",
    "show", "live", "music", "band", "artist", "record", "label",
    "studio", "venue", "concert", "festival", "ep", "lp",
    "monday", "tuesday", "wednesday", "thursday", "friday",
    "saturday", "sunday", "january", "february", "march", "april",
    "may", "june", "july", "august", "september", "october",
    "november", "december", "today", "tonight", "week", "month",
    "year", "edition", "issue", "newsletter", "dispatch",
    "truefans", "read more", "learn more", "click here",
    "subscribe now", "sign up", "join", "free",
})


def _is_valid_entity_name(name: str) -> bool:
    """Check if name is a plausible entity name (not just a common word)."""
    clean = name.strip()
    if len(clean) < 2 or len(clean) > 80:
        return False
    if clean.lower() in _SKIP_WORDS:
        return False
    # Must have at least one letter
    if not any(c.isalpha() for c in clean):
        return False
    # Skip all-lowercase single words (likely common nouns)
    words = clean.split()
    if len(words) == 1 and clean.islower():
        return False
    return True


def _clean_name(name: str) -> str:
    """Clean up extracted entity name."""
    # Unescape HTML entities
    name = html.unescape(name)
    # Strip tags that might have leaked through
    name = _TAG_RE.sub("", name)
    # Normalize whitespace
    name = _MULTI_SPACE.sub(" ", name).strip()
    # Remove trailing punctuation
    name = name.rstrip(".,;:!?")
    return name


def extract_entities_from_html(html_content: str) -> list[dict]:
    """Parse newsletter HTML and extract entities.

    Returns a list of dicts with keys: name, entity_type, section_slug,
    context_snippet.
    """
    if not html_content:
        return []

    entities: list[dict] = []
    seen: set[tuple[str, str, str]] = set()  # (name_lower, type, section)
    cities = _get_cities()

    sections = _html_to_sections(html_content)

    for section in sections:
        section_slug = section["slug"]
        text = section["text"]
        # Also search the raw HTML for this section for bold/link tags
        # Find the raw HTML segment corresponding to this section text
        section_html_raw = html_content  # fallback: search whole doc

        def _add(name: str, etype: str):
            name = _clean_name(name)
            if not _is_valid_entity_name(name):
                return
            key = (name.lower(), etype, section_slug)
            if key in seen:
                return
            seen.add(key)
            # Build context snippet: surrounding 60 chars
            idx = text.lower().find(name.lower())
            if idx >= 0:
                start = max(0, idx - 30)
                end = min(len(text), idx + len(name) + 30)
                snippet = text[start:end]
                if start > 0:
                    snippet = "..." + snippet
                if end < len(text):
                    snippet = snippet + "..."
            else:
                snippet = text[:80] + "..." if len(text) > 80 else text
            entities.append({
                "name": name,
                "entity_type": etype,
                "section_slug": section_slug,
                "context_snippet": snippet,
            })

        # --- Artists: bold text and link text in the HTML ---
        for match in _BOLD_RE.finditer(html_content):
            bold_text = _clean_name(match.group(1))
            if _is_valid_entity_name(bold_text) and len(bold_text.split()) <= 5:
                # Check if it looks like a name (starts with uppercase words)
                if bold_text[0].isupper():
                    _add(bold_text, "artist")

        for match in _LINK_RE.finditer(html_content):
            link_text = _clean_name(match.group(1))
            if _is_valid_entity_name(link_text) and len(link_text.split()) <= 5:
                if link_text[0].isupper():
                    _add(link_text, "artist")

        # --- Venues ---
        for match in _VENUE_RE.finditer(text):
            venue = match.group(1).strip()
            _add(venue, "venue")

        # --- Labels ---
        for match in _LABEL_RE.finditer(text):
            label = match.group(1).strip()
            _add(label, "label")

        # --- Producers ---
        for match in _PRODUCER_RE.finditer(text):
            producer = match.group(1).strip()
            _add(producer, "producer")

        # --- Cities ---
        for city in cities:
            # Match whole word only
            pattern = r'\b' + re.escape(city) + r'\b'
            if re.search(pattern, text, re.IGNORECASE):
                _add(city, "city")

    return entities


# ---------------------------------------------------------------------------
# Connection building
# ---------------------------------------------------------------------------

def build_connections(entities: list[dict]) -> list[dict]:
    """Build connections between co-occurring entities.

    Entities in the same section get a 'mentioned_with' relationship.
    Venue entities get 'performed_at' with co-occurring artists.
    Label entities get 'signed_to' with co-occurring artists.
    Producer entities get 'produced_by' with co-occurring artists.
    City entities get 'based_in' with co-occurring artists/venues.
    """
    connections: list[dict] = []
    seen: set[tuple[str, str, str]] = set()

    # Group entities by section
    by_section: dict[str, list[dict]] = {}
    for ent in entities:
        sec = ent["section_slug"]
        by_section.setdefault(sec, []).append(ent)

    for section_slug, section_entities in by_section.items():
        artists = [e for e in section_entities if e["entity_type"] == "artist"]
        venues = [e for e in section_entities if e["entity_type"] == "venue"]
        labels = [e for e in section_entities if e["entity_type"] == "label"]
        producers = [e for e in section_entities if e["entity_type"] == "producer"]
        cities = [e for e in section_entities if e["entity_type"] == "city"]

        # Artist <-> Venue = performed_at
        for a in artists:
            for v in venues:
                key = (a["name"].lower(), v["name"].lower(), "performed_at")
                rkey = (v["name"].lower(), a["name"].lower(), "performed_at")
                if key not in seen and rkey not in seen:
                    seen.add(key)
                    connections.append({
                        "source_name": a["name"],
                        "source_type": "artist",
                        "target_name": v["name"],
                        "target_type": "venue",
                        "relationship": "performed_at",
                    })

        # Artist <-> Label = signed_to
        for a in artists:
            for l in labels:
                key = (a["name"].lower(), l["name"].lower(), "signed_to")
                rkey = (l["name"].lower(), a["name"].lower(), "signed_to")
                if key not in seen and rkey not in seen:
                    seen.add(key)
                    connections.append({
                        "source_name": a["name"],
                        "source_type": "artist",
                        "target_name": l["name"],
                        "target_type": "label",
                        "relationship": "signed_to",
                    })

        # Artist <-> Producer = produced_by
        for a in artists:
            for p in producers:
                key = (a["name"].lower(), p["name"].lower(), "produced_by")
                if key not in seen:
                    seen.add(key)
                    connections.append({
                        "source_name": a["name"],
                        "source_type": "artist",
                        "target_name": p["name"],
                        "target_type": "producer",
                        "relationship": "produced_by",
                    })

        # Artist/Venue <-> City = based_in
        for ent in artists + venues:
            for c in cities:
                key = (ent["name"].lower(), c["name"].lower(), "based_in")
                if key not in seen:
                    seen.add(key)
                    connections.append({
                        "source_name": ent["name"],
                        "source_type": ent["entity_type"],
                        "target_name": c["name"],
                        "target_type": "city",
                        "relationship": "based_in",
                    })

        # Artist <-> Artist (same section) = mentioned_with
        for i, a1 in enumerate(artists):
            for a2 in artists[i + 1:]:
                key = tuple(sorted([a1["name"].lower(), a2["name"].lower()]))
                full_key = key + ("mentioned_with",)
                if full_key not in seen:
                    seen.add(full_key)
                    connections.append({
                        "source_name": a1["name"],
                        "source_type": "artist",
                        "target_name": a2["name"],
                        "target_type": "artist",
                        "relationship": "mentioned_with",
                    })

    return connections


# ---------------------------------------------------------------------------
# Issue indexing
# ---------------------------------------------------------------------------

def index_issue(repo, issue_id: int) -> dict:
    """Extract entities from a published issue, upsert to DB, build connections.

    Returns summary stats: {entities_found, connections_found, new_entities, new_connections}.
    """
    # Get assembled HTML for this issue
    assembled = repo.get_assembled(issue_id)
    if not assembled:
        logger.warning("No assembled HTML for issue %d", issue_id)
        return {"entities_found": 0, "connections_found": 0, "new_entities": 0, "new_connections": 0}

    html_content = assembled.get("html_content", "")
    if not html_content:
        return {"entities_found": 0, "connections_found": 0, "new_entities": 0, "new_connections": 0}

    entities = extract_entities_from_html(html_content)
    connections = build_connections(entities)

    # Track entity name -> entity_id mapping for connection building
    entity_ids: dict[str, int] = {}
    new_entities = 0
    new_connections = 0

    for ent in entities:
        slug = slugify(ent["name"])
        if not slug:
            continue
        eid = repo.upsert_scene_entity(
            name=ent["name"],
            entity_type=ent["entity_type"],
            slug=slug,
            issue_id=issue_id,
        )
        if eid:
            entity_ids[ent["name"].lower()] = eid
            repo.add_entity_mention(
                entity_id=eid,
                issue_id=issue_id,
                section_slug=ent.get("section_slug", ""),
                context_snippet=ent.get("context_snippet", ""),
            )

    for conn in connections:
        source_id = entity_ids.get(conn["source_name"].lower())
        target_id = entity_ids.get(conn["target_name"].lower())
        if source_id and target_id and source_id != target_id:
            repo.upsert_scene_connection(
                source_id=source_id,
                target_id=target_id,
                relationship=conn["relationship"],
                issue_id=issue_id,
            )

    logger.info(
        "Indexed issue %d: %d entities, %d connections",
        issue_id, len(entities), len(connections),
    )
    return {
        "entities_found": len(entities),
        "connections_found": len(connections),
    }


# ---------------------------------------------------------------------------
# Graph queries (thin wrappers around repo methods)
# ---------------------------------------------------------------------------

def get_entity_graph(repo, entity_id: int | None = None) -> dict:
    """Return graph data for visualization: {nodes: [...], edges: [...]}."""
    return repo.get_scene_graph_data(entity_id=entity_id)


def search_entities(repo, query: str, entity_type: str | None = None) -> list[dict]:
    """Search entities by name, optionally filtered by type."""
    return repo.search_scene_entities(query, entity_type=entity_type)

"""Locale fact-sheet loader, prompt builder, and post-draft guardrail.

Hyperlocal editions hallucinate without a constraint. This module loads a
`data/locales/<slug>.yaml` sheet of verified entities and produces:

  * `build_writer_context(slug)` — a prompt fragment the writer must adhere to.
  * `audit_draft(text, slug)` — extracts proper nouns from a draft and reports
    anything that isn't on the sheet, plus any explicit do_not_mention hits.

Editor-facing, not auto-blocking. A human approves before send.
"""
from __future__ import annotations

import re
import sys
from dataclasses import dataclass
from datetime import date, datetime, timedelta
from pathlib import Path
from typing import Iterable

import yaml

DATA_DIR = Path(__file__).resolve().parents[3] / "data"
LOCALES_DIR = DATA_DIR / "locales"
ARTISTS_DIR = DATA_DIR / "artists"
SHEET_DIRS = (LOCALES_DIR, ARTISTS_DIR)

STALE_AFTER_DAYS = 365


def _locale_path(slug: str) -> Path:
    """Resolve a sheet slug to a YAML path under data/locales or data/artists."""
    for directory in SHEET_DIRS:
        candidate = directory / f"{slug}.yaml"
        if candidate.exists():
            return candidate
    # Fall back to the locales path for the not-found error message.
    return LOCALES_DIR / f"{slug}.yaml"


def load_locale(slug: str) -> dict:
    path = _locale_path(slug)
    if not path.exists():
        raise FileNotFoundError(f"No locale sheet at {path}")
    with path.open() as f:
        return yaml.safe_load(f)


def build_writer_context(slug: str) -> str:
    """Return a prompt fragment the writer is hard-constrained to.

    Works for both locale sheets (`data/locales/`) and artist sheets
    (`data/artists/`). Locale sheets have a top-level `locale:` block;
    artist sheets have a top-level `artist:` block. Schema is otherwise
    similar — venues/studios/festivals + scene_facts + do_not_mention.
    Artist sheets may also include `members:` and `albums:` lists.
    """
    sheet = load_locale(slug)
    if "artist" in sheet:
        meta = sheet["artist"]
        header = (
            f"=== VERIFIED FACTS FOR {meta['name'].upper()} "
            f"(last full review {meta['last_full_review']}) ==="
        )
    else:
        meta = sheet["locale"]
        header = (
            f"=== VERIFIED FACTS FOR {meta['name'].upper()}, {meta['state']} "
            f"(last full review {meta['last_full_review']}) ==="
        )
    lines: list[str] = [header]
    lines.append(
        "You may reference ONLY the venues, studios, festivals, and facts listed "
        "below. If a section needs an entity not on this list, write the section "
        "without naming a specific entity, or omit the section. Do not assert "
        "founders, owners, dates, or addresses beyond what is given here."
    )

    if sheet.get("members"):
        lines.append("\nMEMBERS (current and notable past):")
        for m in sheet["members"]:
            era = m.get("era") or m.get("status", "current")
            lines.append(f"- {m['name']} &mdash; {m.get('role', '')} ({era}). {m.get('notes', '')}".rstrip())

    if sheet.get("albums"):
        lines.append("\nDISCOGRAPHY:")
        for a in sheet["albums"]:
            studio = f", recorded at {a['studio']}" if a.get("studio") else ""
            label = f", {a['label']}" if a.get("label") else ""
            lines.append(f"- {a['title']} ({a.get('year', 'unknown')}){studio}{label}.")

    if sheet.get("venues"):
        lines.append("\nVENUES:")
        for v in sheet["venues"]:
            books = v.get("books_original_music", "unknown")
            cap = f", cap {v['capacity']}" if v.get("capacity") else ""
            lines.append(
                f"- {v['name']} ({v['type']}, {v['city']}{cap}; books original: {books}). "
                f"{v.get('notes', '')}"
            )

    if sheet.get("studios"):
        lines.append("\nSTUDIOS:")
        for s in sheet["studios"]:
            focus = s.get("focus", "music")
            warn = "  <-- POST-PRODUCTION ONLY, do not pitch as a music tracking room" if focus == "post_production" else ""
            clients = ""
            if s.get("notable_clients"):
                clients = " Known clients: " + ", ".join(s["notable_clients"]) + "."
            lines.append(f"- {s['name']} ({s['city']}, focus: {focus}).{clients}{warn}")

    if sheet.get("festivals"):
        lines.append("\nFESTIVALS:")
        for f in sheet["festivals"]:
            lines.append(f"- {f['name']} — {f['when']}, {f['location']}.")

    if sheet.get("scene_facts"):
        lines.append("\nSCENE FACTS (paraphrase, do not extend):")
        for fact in sheet["scene_facts"]:
            lines.append(f"- {fact['claim']}")

    if sheet.get("do_not_mention"):
        lines.append("\nDO NOT MENTION (these are wrong, closed, or unverified):")
        for d in sheet["do_not_mention"]:
            lines.append(f"- {d['name']} — {d['reason']}")

    return "\n".join(lines)


# ---------------------------------------------------------------- audit ----

_STYLE_RE = re.compile(r"<style\b[^>]*>.*?</style>", re.DOTALL | re.IGNORECASE)
_SCRIPT_RE = re.compile(r"<script\b[^>]*>.*?</script>", re.DOTALL | re.IGNORECASE)
_TAG_RE = re.compile(r"<[^>]+>")
_ENTITY_RE = re.compile(r"&[a-z]+;|&#\d+;")

# Capitalized phrase, 1-6 words, no internal punctuation runs. We then filter by
# keyword to avoid flagging every capitalized phrase in the draft.
_PHRASE_RE = re.compile(
    r"\b([A-Z][A-Za-z0-9&'\-]+(?:\s+(?:[A-Z][A-Za-z0-9&'\-]+|of|the|de|los|las|y|and|&)){0,5})\b"
)

# Words that strongly suggest an entity is a venue/studio/festival/label — the
# things the writer is most likely to fabricate. If a candidate phrase contains
# one of these as a token, it gets checked against the sheet.
_VENUE_KEYWORDS = {
    "studio", "studios", "brewery", "brewing", "pub", "bar", "hall", "theatre",
    "theater", "center", "cafe", "café", "church", "festival", "records",
    "recording", "tavern", "lounge", "club", "house", "garden", "ballroom",
    "auditorium", "amphitheater", "amphitheatre", "playhouse", "society",
    "association", "workshop", "coalition", "academy", "circle", "collective",
}

# Sentence-opener tokens — when a phrase starts with one of these, it's
# overwhelmingly a sentence start, not a proper noun.
_SENTENCE_OPENERS = {
    "the", "a", "an", "this", "that", "these", "those", "if", "when", "where",
    "while", "after", "before", "every", "even", "plenty", "half", "most",
    "many", "some", "all", "no", "any", "each", "we", "i", "they", "you", "it",
    "build", "keep", "find", "used", "bring", "talk", "make", "start", "get",
    "welcome", "call", "send", "email", "book", "consider", "pro", "thanks",
    "look", "vocals", "field", "pedal", "adobe", "thick", "even", "from",
    "across", "downtown", "uptown", "save", "avoid", "wind", "worth",
    "several", "channel", "sources", "session", "stories", "fun",
}

# Geographic names that come up in tour-route discussion — legit references,
# not entities to fact-check. Extend as needed per locale or globally.
_KNOWN_PLACES = {
    "albuquerque", "santa fe", "tucson", "flagstaff", "sedona", "phoenix",
    "el paso", "las cruces", "marfa", "silver city", "amarillo", "lubbock",
    "denver", "colorado springs", "pueblo", "trinidad", "taos",
    "rio rancho", "north valley", "south valley", "loma larga", "bosque",
    "wells park", "nob hill", "old church", "downtown abq",
    "new mexico", "arizona", "texas", "colorado", "california",
    "i-10", "i-25", "i-40", "central ave",
}

_NOISE_EXACT = {
    "from the editor", "sponsored", "sponsored partner", "trivia answer",
    "this week's trivia", "quick poll", "free trial", "thanks for voting",
    "high desert", "high desert light", "high desert road",
    "industry professionals", "music artists", "music artists and fans",
    "truefans newsletter", "truefans dispatch", "truefans connect",
    "truefans ecosystem", "apple music", "tiktok", "youtube", "linkedin",
    "instagram", "twitter", "facebook", "bandsintown", "distrokid",
    "new mexico americana", "kitchen sink studios",   # alias of "The Kitchen Sink"
    "wavelab of new mexico",
}

# Bylines & internal staff — author names baked into the template, not
# claims the writer is making about the world.
_STAFF_NAMES = {
    "sarah collins", "brooke callahan", "derek hollis", "miles bennett",
}


def _strip_html(text: str) -> str:
    text = _STYLE_RE.sub(" ", text)
    text = _SCRIPT_RE.sub(" ", text)
    text = _TAG_RE.sub(" ", text)
    text = _ENTITY_RE.sub(" ", text)
    return text


def _normalize(name: str) -> str:
    return re.sub(r"\s+", " ", name).strip().lower()


@dataclass
class AuditFinding:
    severity: str   # "error" | "warn"
    kind: str       # "do_not_mention" | "unknown_entity" | "stale_entry"
    name: str
    detail: str


def audit_draft(text: str, slug: str) -> list[AuditFinding]:
    """Scan a draft for entities not on the verified sheet."""
    sheet = load_locale(slug)
    findings: list[AuditFinding] = []

    allowed: set[str] = set()
    for v in sheet.get("venues") or []:
        allowed.add(_normalize(v["name"]))
    for s in sheet.get("studios") or []:
        allowed.add(_normalize(s["name"]))
    for f in sheet.get("festivals") or []:
        allowed.add(_normalize(f["name"]))
    # Artist sheets: members, album titles, and labels are also allowed names.
    for m in sheet.get("members") or []:
        allowed.add(_normalize(m["name"]))
    for a in sheet.get("albums") or []:
        allowed.add(_normalize(a["title"]))
        if a.get("studio"):
            allowed.add(_normalize(a["studio"]))
        if a.get("label"):
            allowed.add(_normalize(a["label"]))

    blocked = {_normalize(d["name"]): d for d in (sheet.get("do_not_mention") or [])}

    plain = _strip_html(text)
    # Scan paragraph-by-paragraph so candidates can't span structural breaks.
    paragraphs = [p for p in re.split(r"\n+", plain) if p.strip()]

    seen: set[str] = set()
    for paragraph in paragraphs:
        line = re.sub(r"\s+", " ", paragraph).strip()
        for match in _PHRASE_RE.finditer(line):
            name = match.group(1).strip()
            if len(name) < 6 or len(name) > 60:
                continue
            words = name.split()
            if len(words) < 2 or len(words) > 6:
                continue
            # Section headers like "RECORDING WITHIN AN HOUR" are all-caps.
            if any(w.isupper() and len(w) > 2 for w in words):
                continue
            first_word = words[0].lower()
            if first_word in _SENTENCE_OPENERS:
                continue
            norm = _normalize(name)
            if norm in _NOISE_EXACT or norm in _KNOWN_PLACES or norm in _STAFF_NAMES:
                continue

            # Hard-block hits first — substring match so a closed venue is
            # caught whether the writer wrote the full name or a short form.
            blocked_hit = next(
                (b for b in blocked if b == norm or b in norm or norm in b),
                None,
            )
            if blocked_hit:
                if norm in seen:
                    continue
                seen.add(norm)
                d = blocked[blocked_hit]
                findings.append(AuditFinding(
                    severity="error",
                    kind="do_not_mention",
                    name=name,
                    detail=f"Listed in do_not_mention: {d['reason']}",
                ))
                continue

            # Allowed entity? (substring match handles "Casa Vieja" inside
            # "Casa Vieja Brewery".)
            if any(a == norm or a in norm or norm in a for a in allowed):
                continue

            # Only warn on entity-shaped phrases: must contain a venue keyword
            # OR look like a person's name (2 words, both capitalized, no
            # joiners). Everything else is too noisy to be useful.
            tokens = {w.lower().rstrip("s") for w in words}
            looks_like_venue = bool(tokens & _VENUE_KEYWORDS) or any(
                w.lower() in _VENUE_KEYWORDS for w in words
            )
            looks_like_person = (
                len(words) == 2
                and all(w[0].isupper() and w[1:].islower() and len(w) >= 3 for w in words)
            )
            if not (looks_like_venue or looks_like_person):
                continue

            if norm in seen:
                continue
            seen.add(norm)

            findings.append(AuditFinding(
                severity="warn",
                kind="unknown_entity",
                name=name,
                detail="Not on the verified sheet — verify or remove.",
            ))

    # Staleness check: any entry verified more than STALE_AFTER_DAYS ago.
    cutoff = date.today() - timedelta(days=STALE_AFTER_DAYS)
    for group in ("venues", "studios", "festivals", "scene_facts"):
        for entry in sheet.get(group) or []:
            v = entry.get("verified_on")
            if isinstance(v, str):
                v = datetime.fromisoformat(v).date()
            if v and v < cutoff:
                findings.append(AuditFinding(
                    severity="warn",
                    kind="stale_entry",
                    name=entry.get("name") or entry.get("claim", "")[:60],
                    detail=f"Last verified {v.isoformat()} — older than {STALE_AFTER_DAYS} days. Re-verify.",
                ))

    return findings


def format_findings(findings: Iterable[AuditFinding]) -> str:
    findings = list(findings)
    if not findings:
        return "No issues. Sheet is current and the draft only references verified entities."
    out: list[str] = []
    errors = [f for f in findings if f.severity == "error"]
    warns = [f for f in findings if f.severity == "warn"]
    if errors:
        out.append(f"ERRORS ({len(errors)}) — fix before send:")
        for f in errors:
            out.append(f"  [{f.kind}] {f.name}: {f.detail}")
    if warns:
        out.append(f"\nWARNINGS ({len(warns)}) — review:")
        for f in warns:
            out.append(f"  [{f.kind}] {f.name}: {f.detail}")
    return "\n".join(out)


def _cli(argv: list[str]) -> int:
    if len(argv) < 2:
        print("usage: locale_facts.py context <slug>")
        print("       locale_facts.py audit <draft_path> <slug>")
        return 2
    cmd = argv[1]
    if cmd == "context" and len(argv) == 3:
        print(build_writer_context(argv[2]))
        return 0
    if cmd == "audit" and len(argv) == 4:
        text = Path(argv[2]).read_text()
        findings = audit_draft(text, argv[3])
        print(format_findings(findings))
        return 1 if any(f.severity == "error" for f in findings) else 0
    print("bad arguments")
    return 2


if __name__ == "__main__":
    sys.exit(_cli(sys.argv))

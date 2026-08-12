"""Inject ad slots, a poll, and a trivia question into the demo newsletters.

The committed ``demo_*.html`` files are standalone artifacts served by
``/sample/{edition}`` — they are not produced by the assembly pipeline, so
adding engagement units to the real pipeline does not change what prospects
see. This script closes that gap.

Blocks are produced by the *real* renderers (``render_sponsor_block`` and
``TriviaManager.render_trivia_email_html``) so the samples look exactly like
production output rather than an approximation of it.

Two deliberate constraints:

* **Illustrative, not live.** Vote links are rewritten to ``#`` so demo
  traffic never lands in real poll results.
* **No fabrication.** Ads are house ads for DISPATCH's own inventory — no
  invented brands, no invented subscriber numbers. Artist trivia is drawn
  from the verified-facts YAML in ``data/artists/`` (see
  ``feedback_no_fabrication_in_editions``), and the remaining questions are
  general industry facts.

Idempotent: files already carrying the marker are skipped.

Usage:  python3 generate_sample_engagement.py [--check]
"""

from __future__ import annotations

import os
import re
import sys

sys.path.insert(0, os.path.join(os.path.dirname(__file__), "src"))

from weeklyamp.content.trivia_polls import TriviaManager  # noqa: E402
from weeklyamp.core.models import TriviaPollsConfig  # noqa: E402
from weeklyamp.delivery.templates import render_sponsor_block  # noqa: E402

MARKER = "<!-- dispatch:engagement -->"
END_MARKER = "<!-- /dispatch:engagement -->"

# Absolute base for CTA links. Samples get emailed and forwarded, so relative
# URLs are not an option. This deliberately points at the live Railway host
# rather than a branded domain: truefansdispatch.com and the configured
# site_domain (truefansdispatch.com) are both unregistered (NXDOMAIN), so
# linking to either ships dead CTAs. Swap this once a domain is live.
BASE_URL = os.environ.get(
    "WEEKLYAMP_SAMPLE_BASE_URL", "https://web-production-2684b.up.railway.app"
).rstrip("/")

# House ads: three angles on DISPATCH's own inventory. Metric-free by design.
ADS = {
    "top": {
        "sponsor_name": "TrueFans DISPATCH",
        "headline": "Your brand, in front of a music-obsessed audience",
        "body_html": "Reach artists, industry professionals, and superfans in the inbox they actually open.",
        "cta_url": f"{BASE_URL}/advertise",
        "cta_text": "Advertise in DISPATCH",
        "image_url": "",
    },
    "mid": {
        "sponsor_name": "TrueFans DISPATCH",
        "headline": "Sponsor a section",
        "body_html": "Put your message beside the stories readers came for — one advertiser per section, per issue.",
        "cta_url": f"{BASE_URL}/advertise",
        "cta_text": "See section packages",
        "image_url": "",
    },
    "bottom": {
        "sponsor_name": "TrueFans DISPATCH",
        "headline": "Run DISPATCH in your city",
        "body_html": "License the format for your local scene and keep the majority of the revenue.",
        "cta_url": f"{BASE_URL}/license",
        "cta_text": "Explore licensing",
        "image_url": "",
    },
}

# question_text, options, correct_index (-1 for a poll = no right answer)
GENERIC_POLL = (
    "How do you discover most of your new music?",
    ["Streaming playlists", "Friends and word of mouth", "Live shows", "Social media"],
    -1,
)
GENERIC_TRIVIA = (
    "In the music industry, what does A&R stand for?",
    ["Artists and Repertoire", "Audio and Recording", "Arts and Revenue"],
    0,
)

ENGAGEMENT: dict[str, dict] = {
    "demo_fan_monday.html": {
        "poll": GENERIC_POLL,
        "trivia": (
            "Which of these albums was released first?",
            ["Rumours", "Thriller", "Back in Black"],
            0,
        ),
    },
    "demo_artist_monday.html": {
        "poll": (
            "What's the biggest bottleneck in your music career right now?",
            ["Funding", "Time", "Growing an audience", "Distribution"],
            -1,
        ),
        "trivia": (
            "Which royalty is paid to songwriters when their song is played publicly?",
            ["Performance royalties", "Mechanical royalties", "Sync royalties"],
            0,
        ),
    },
    "demo_industry_monday.html": {
        "poll": (
            "Where do you expect the most revenue growth next year?",
            ["Live", "Sync licensing", "Direct-to-fan", "Catalog"],
            -1,
        ),
        "trivia": GENERIC_TRIVIA,
    },
    # Artist editions. Sugar Lime Blue's question comes from its verified-facts
    # sheet (data/artists/sugar-lime-blue.yaml); the others use a general
    # industry question rather than risk inventing artist details.
    "demo_sugar_lime_blue.html": {
        "poll": (
            "What would you like more of from the band?",
            ["Tour dates", "Studio stories", "Gear talk", "Full setlists"],
            -1,
        ),
        "trivia": (
            "Sugar Lime Blue self-describe their sound as which of these?",
            ["Cosmic Cowgirl", "Desert Soul", "Delta Gothic"],
            0,
        ),
    },
    "demo_nashville_artist.html": {"poll": GENERIC_POLL, "trivia": GENERIC_TRIVIA},
    "demo_tucson_artist.html": {"poll": GENERIC_POLL, "trivia": GENERIC_TRIVIA},
    "demo_corrales_artist.html": {"poll": GENERIC_POLL, "trivia": GENERIC_TRIVIA},
}

_manager = TriviaManager(repo=None, config=TriviaPollsConfig(enabled=True))


def _make_block(spec: tuple, poll_id: int) -> str:
    """Render a poll/trivia block, then defuse its vote links."""
    question_text, options, correct_index = spec
    import json

    poll = {
        "id": poll_id,
        "question_text": question_text,
        "options_json": json.dumps(options),
        "question_type": "trivia" if correct_index >= 0 else "poll",
    }
    html = _manager.render_trivia_email_html(poll, BASE_URL, 0)
    # Illustrative only — never point demo clicks at the live vote endpoint.
    return re.sub(r'href="[^"]*/t/vote/[^"]*"', 'href="#"', html)


def _wrap(html: str) -> str:
    """Fence a block between markers so --force can strip it later.

    Without a closing marker there is no reliable way to find where an
    injected block ends, which makes changing the blocks (say, fixing a CTA
    URL) a manual edit of every demo file.
    """
    return f"\n{MARKER}\n{html}\n{END_MARKER}\n"


def strip_blocks(source: str) -> str:
    """Remove previously injected blocks.

    Only fenced blocks are removable. Matching an unfenced block by element
    would need depth-aware parsing — the sponsor block nests divs, so a
    non-greedy match to the first ``</div>`` truncates it and leaves broken
    markup. Blocks predating END_MARKER must be reverted via git instead.
    """
    return re.sub(
        re.escape(MARKER) + r".*?" + re.escape(END_MARKER),
        "",
        source,
        flags=re.DOTALL,
    )


def inject(path: str, force: bool = False) -> str:
    """Inject blocks into one demo file. Returns a short status string."""
    with open(path, encoding="utf-8") as fh:
        source = fh.read()

    replaced = False
    if MARKER in source:
        if not force:
            return "skipped (already injected — use --force to replace)"
        source = strip_blocks(source)
        replaced = True

    section_starts = [m.start() for m in re.finditer(r'<div class="section"', source)]
    footer = re.search(r'<div class="footer"', source)
    if not section_starts or not footer:
        return "SKIPPED — unrecognised structure (no sections or no footer)"

    spec = ENGAGEMENT.get(os.path.basename(path))
    if not spec:
        return "SKIPPED — no engagement content configured"

    count = len(section_starts)
    # Insertions are applied back-to-front so earlier offsets stay valid.
    # The trivia block and bottom ad share the footer offset, so they are
    # concatenated into a single edit — two edits at one offset would come
    # out in reverse order.
    tail = _wrap(_make_block(spec["trivia"], 902)) + _wrap(render_sponsor_block(ADS["bottom"]))
    edits: list[tuple[int, str]] = [
        (section_starts[0], _wrap(render_sponsor_block(ADS["top"]))),
        (section_starts[max(1, count // 3)], _wrap(_make_block(spec["poll"], 901))),
        (section_starts[max(1, count // 2)], _wrap(render_sponsor_block(ADS["mid"]))),
        (footer.start(), tail),
    ]

    result = source
    for offset, block in sorted(edits, key=lambda e: e[0], reverse=True):
        result = result[:offset] + block + result[offset:]

    with open(path, "w", encoding="utf-8") as fh:
        fh.write(result)
    verb = "replaced" if replaced else "injected"
    return f"{verb} (3 ads, 1 poll, 1 trivia across {count} sections)"


def verify_cta_links() -> bool:
    """Fetch every CTA target and report its status.

    Added after shipping samples whose CTAs pointed at an unregistered
    domain. A dead call-to-action in a document sent to advertisers and
    prospective licensees is worse than no call-to-action, so this runs
    before any file is written.

    Note the gate: while WEEKLYAMP_COMING_SOON is on, these pages return 503
    to anyone without the preview cookie, so both are checked.
    """
    # httpx (a declared dependency) rather than urllib: it bundles a CA
    # trust store, so this does not fail on Python installs lacking system
    # certificates.
    import httpx

    token = os.environ.get("WEEKLYAMP_SAMPLE_PREVIEW_TOKEN", "")
    ok = True
    for url in sorted({ad["cta_url"] for ad in ADS.values()}):
        for label, target in (
            ("public", url),
            ("preview", f"{url}?preview={token}" if token else None),
        ):
            if target is None:
                continue
            try:
                code = httpx.get(target, timeout=20, follow_redirects=True).status_code
            except Exception as exc:  # DNS failure, timeout, refused connection
                print(f"  {label:8s} {url}  UNREACHABLE ({type(exc).__name__})")
                ok = False
                continue
            flag = "" if code == 200 else "  <-- not reachable"
            if code != 200 and label == "public" and code == 503:
                flag = "  <-- gated by coming-soon (expected while pre-launch)"
            elif code != 200:
                ok = False
            print(f"  {label:8s} {url}  {code}{flag}")
    return ok


def main() -> int:
    check_only = "--check" in sys.argv
    here = os.path.dirname(os.path.abspath(__file__))
    missing = 0

    if "--skip-link-check" not in sys.argv:
        print(f"Verifying CTA links against {BASE_URL} ...")
        if not verify_cta_links() and not check_only:
            print("\nAborting: at least one CTA is not reachable. "
                  "Fix BASE_URL or the target route, or pass --skip-link-check.")
            return 2
        print()

    for name in sorted(ENGAGEMENT):
        path = os.path.join(here, name)
        if not os.path.exists(path):
            print(f"{name:32s} MISSING")
            missing += 1
            continue
        if check_only:
            with open(path, encoding="utf-8") as fh:
                state = "present" if MARKER in fh.read() else "ABSENT"
            print(f"{name:32s} {state}")
            missing += state == "ABSENT"
        else:
            print(f"{name:32s} {inject(path, force='--force' in sys.argv)}")

    return 1 if (check_only and missing) else 0


if __name__ == "__main__":
    raise SystemExit(main())

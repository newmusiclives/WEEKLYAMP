"""Venue Edition wiring.

The Venue Edition is the fourth audience edition (Fan / Artist / Venue /
Industry). Adding an edition touches seed data, the cost model, promo
routing, and the AI staff page, and most of those links are plain strings
that fail quietly — a mistyped section slug just disappears from the
issue. These tests pin the joins that have no other guard.
"""

from __future__ import annotations

import json

from weeklyamp.core.cost_model import CANONICAL_EDITIONS
from weeklyamp.core.database import (
    DEFAULT_AGENTS,
    DEFAULT_EDITIONS,
    DEFAULT_SECTIONS,
    get_connection,
    init_database,
    seed_agents,
    seed_editions,
    seed_sections,
)
from weeklyamp.core.models import GHLConfig, PromoConfig


def _editions_by_slug():
    keys = ("slug", "name", "tagline", "description", "audience",
            "color", "icon", "section_slugs", "sort_order")
    return {e[0]: dict(zip(keys, e)) for e in DEFAULT_EDITIONS}


def _agent_config(name):
    for _atype, aname, _persona, _prompt, _autonomy, cfg in DEFAULT_AGENTS:
        if aname == name:
            return json.loads(cfg)
    raise AssertionError(f"agent {name!r} not in DEFAULT_AGENTS")


# ---- Seed data ----

def test_venue_edition_is_seeded():
    venue = _editions_by_slug()["venue"]
    assert venue["name"] == "Venue Edition"
    assert venue["section_slugs"]


def test_audience_editions_are_ordered_fan_artist_venue_industry():
    by_slug = _editions_by_slug()
    order = [s for s in ("fan", "artist", "venue", "industry")]
    sort_orders = [by_slug[s]["sort_order"] for s in order]
    assert sort_orders == sorted(sort_orders), sort_orders
    assert len(set(sort_orders)) == len(sort_orders), "sort_order collision"


def test_every_edition_section_slug_exists():
    """A slug that isn't in section_definitions is dropped silently at
    assembly, so the edition just quietly runs short."""
    known = {s[0] for s in DEFAULT_SECTIONS}
    for edition in DEFAULT_EDITIONS:
        slug, section_slugs = edition[0], edition[7]
        for section in filter(None, section_slugs.split(",")):
            assert section in known, f"{slug} references unknown section {section!r}"


def test_venue_sections_are_seeded_into_the_database(tmp_path):
    db = str(tmp_path / "venue.db")
    init_database(db)
    seed_sections(db)
    seed_editions(db)

    conn = get_connection(db)
    row = conn.execute(
        "SELECT section_slugs FROM newsletter_editions WHERE slug = ?", ("venue",)
    ).fetchone()
    assert row is not None, "venue edition row missing after seeding"
    slugs = row["section_slugs"].split(",")

    placeholders = ",".join("?" for _ in slugs)
    found = conn.execute(
        f"SELECT slug FROM section_definitions WHERE slug IN ({placeholders})", slugs
    ).fetchall()
    conn.close()
    assert {r["slug"] for r in found} == set(slugs)


def test_seed_editions_resyncs_sort_order(tmp_path):
    """Inserting venue mid-list renumbers the editions after it, and the
    seed is the only writer of newsletter_editions — so a re-seed has to
    correct an existing row, not just leave it where it was."""
    db = str(tmp_path / "resort.db")
    init_database(db)
    seed_editions(db)

    conn = get_connection(db)
    conn.execute("UPDATE newsletter_editions SET sort_order = 99 WHERE slug = ?", ("industry",))
    conn.commit()
    conn.close()

    seed_editions(db)

    conn = get_connection(db)
    row = conn.execute(
        "SELECT sort_order FROM newsletter_editions WHERE slug = ?", ("industry",)
    ).fetchone()
    conn.close()
    assert row["sort_order"] == _editions_by_slug()["industry"]["sort_order"]


# ---- Editorial team ----

def test_venue_edition_has_a_full_team():
    roles = [atype for atype, _n, _p, _sp, _a, cfg in DEFAULT_AGENTS
             if json.loads(cfg).get("edition") == "venue"]
    assert roles.count("editor") == 1
    assert roles.count("researcher") == 2
    assert roles.count("writer") == 3
    assert roles.count("sales") == 1
    assert roles.count("promotion") == 1
    # growth_lead + marketing_lead, matching the other editions
    assert roles.count("growth") == 1
    assert roles.count("marketing") == 1


def test_venue_agent_section_assignments_are_real_sections():
    known = {s[0] for s in DEFAULT_SECTIONS}
    for _atype, name, _persona, _prompt, _autonomy, cfg in DEFAULT_AGENTS:
        parsed = json.loads(cfg)
        if parsed.get("edition") != "venue":
            continue
        for section in parsed.get("sections", []):
            assert section in known, f"{name} assigned unknown section {section!r}"


def test_venue_agents_are_inserted_on_seed(tmp_path):
    db = str(tmp_path / "agents.db")
    init_database(db)
    seed_agents(db)

    conn = get_connection(db)
    rows = conn.execute("SELECT name, config_json FROM ai_agents").fetchall()
    conn.close()
    venue = [r["name"] for r in rows if json.loads(r["config_json"]).get("edition") == "venue"]
    assert len(venue) == 10


def test_cross_edition_agents_cover_venue():
    """The Editor-in-Chief and the cross-portfolio leads scope their work
    by an `editions` list; leaving venue out means nobody owns it."""
    for name in ('Marcy "Mars" Holloway', "Grant Sullivan", "Theo Bassett",
                 "Morgan Blake", "Paul Saunders"):
        assert "venue" in _agent_config(name)["editions"], name


# ---- Downstream wiring ----

def test_venue_is_a_canonical_edition_for_costing():
    assert "venue" in CANONICAL_EDITIONS


def test_venue_has_a_ghl_tag_and_promo_route():
    assert GHLConfig().edition_tags["venue"] == "newsletter-venue"
    assert PromoConfig().routing["venue"] in PromoConfig().targets

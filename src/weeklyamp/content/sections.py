"""Section registry — reads active sections from the database."""

from __future__ import annotations

from collections import defaultdict

from weeklyamp.db.repository import Repository


def get_section_slugs(repo: Repository) -> list[str]:
    """Return ordered list of active section slugs (the full library).

    For a drafting run use :func:`get_draftable_section_slugs` instead —
    this returns every active section, which is the whole library rather
    than one issue's worth.
    """
    sections = repo.get_active_sections()
    return [s["slug"] for s in sections]


def get_edition_section_slugs(repo: Repository, edition_slug: str) -> list[str]:
    """Return an edition's declared running order, filtered to live sections.

    ``newsletter_editions.section_slugs`` is a comma-separated ordered
    list. Entries that no longer resolve to an active section are dropped
    rather than handed to a writer.
    """
    if not edition_slug:
        return []
    edition = repo.get_edition_by_slug(edition_slug)
    if not edition:
        return []
    raw = (edition.get("section_slugs") or "").strip()
    if not raw:
        return []
    active = set(get_section_slugs(repo))
    return [s.strip() for s in raw.split(",") if s.strip() and s.strip() in active]


def get_draftable_section_slugs(
    repo: Repository, config=None, edition_slug: str = ""
) -> list[str]:
    """Return the section slugs a single drafting run should generate.

    The section library is much larger than any one issue — 74 active
    sections as of 2026-08, of which only 7 are ``core`` — and a run that
    drafts all of them costs one API call per section plus one
    editor-review call per resulting draft. That was the dominant line in
    the cost model, so a run is capped at
    ``config.ai.max_sections_per_issue``.

    ``edition_slug`` scopes the run to that edition's declared running
    order. Without it the candidate pool is the whole library, which
    produces a technically-capped but editorially incoherent issue — a
    fan edition full of industry sections. An edition with no declared
    list falls back to the library.

    Within the pool the cap honours editorial structure rather than
    slicing blindly: every ``core`` section runs, and the remaining slots
    are filled from the rotating pool by
    :func:`weeklyamp.content.rotation.select_rotating_sections`, which
    favours sections that haven't appeared recently and spreads them
    across categories. Order follows the edition's declared order when
    scoped, otherwise ``sort_order``.

    Pass ``config=None``, or set the cap to 0, to draft the whole pool.
    """
    pool = get_edition_section_slugs(repo, edition_slug) or get_section_slugs(repo)
    cap = getattr(getattr(config, "ai", None), "max_sections_per_issue", 0) or 0
    if cap <= 0 or len(pool) <= cap:
        return pool

    pool_set = set(pool)
    core = [s["slug"] for s in repo.get_sections_by_type("core") if s["slug"] in pool_set]
    # Core alone can exceed the cap; truncating it is better than blowing
    # through the budget, and the pool's order decides which core stays.
    if len(core) >= cap:
        chosen = set(core)
    else:
        from weeklyamp.content.rotation import select_rotating_sections
        rotating = [
            s for s in select_rotating_sections(repo, max_rotating=len(pool))
            if s in pool_set
        ]
        chosen = set(core) | set(rotating[: cap - len(core)])
        # Rotation can come up short inside a narrow pool; top up in order
        # so the cap is a ceiling we reach, not one we undershoot.
        if len(chosen) < cap:
            for slug in pool:
                if len(chosen) >= cap:
                    break
                chosen.add(slug)

    ordered = [slug for slug in pool if slug in chosen]
    return ordered[:cap]


def get_section_map(repo: Repository) -> dict[str, dict]:
    """Return {slug: section_dict} for all active sections."""
    sections = repo.get_active_sections()
    return {s["slug"]: s for s in sections}


def validate_section(repo: Repository, slug: str) -> bool:
    """Check if a section slug exists and is active."""
    section = repo.get_section(slug)
    return section is not None and bool(section.get("is_active", False))


def get_sections_by_category(repo: Repository) -> dict[str, list[dict]]:
    """Return active sections grouped by category."""
    sections = repo.get_active_sections()
    grouped: dict[str, list[dict]] = defaultdict(list)
    for s in sections:
        cat = s.get("category") or "uncategorized"
        grouped[cat].append(s)
    return dict(grouped)


def build_week_section_plan(
    repo: Repository,
    schedules: list[dict],
) -> dict[str, list[str]]:
    """Build a section plan ensuring at least 1 section from each category per week.

    Takes the configured send schedules (with their assigned section_slugs)
    and fills in any missing category coverage by rotating sections across days.

    Returns {day_of_week: [slugs]}.
    """
    sections_by_cat = get_sections_by_category(repo)
    all_categories = set(sections_by_cat.keys())

    # Build initial plan from schedule config
    plan: dict[str, list[str]] = {}
    for sched in schedules:
        day = sched["day_of_week"]
        raw = sched.get("section_slugs", "")
        slugs = [s.strip() for s in raw.split(",") if s.strip()] if raw else []
        plan[day] = slugs

    if not plan:
        return plan

    # Map slugs to categories for quick lookup
    section_map = get_section_map(repo)
    slug_to_cat: dict[str, str] = {}
    for slug, sec in section_map.items():
        slug_to_cat[slug] = sec.get("category") or "uncategorized"

    # Find which categories are already covered
    covered_categories: set[str] = set()
    for slugs in plan.values():
        for slug in slugs:
            cat = slug_to_cat.get(slug)
            if cat:
                covered_categories.add(cat)

    # Use rotation log to pick least-recently-used sections for uncovered categories
    recent_log = repo.get_recent_rotation_log(n=8)
    recently_used_slugs = {r["section_slug"] for r in recent_log}

    uncovered = all_categories - covered_categories
    days = list(plan.keys())

    for cat in sorted(uncovered):
        cat_sections = sections_by_cat.get(cat, [])
        if not cat_sections:
            continue

        # Pick the section from this category that was least recently used
        unused = [s for s in cat_sections if s["slug"] not in recently_used_slugs]
        pick = unused[0] if unused else cat_sections[0]

        # Add to the day with fewest sections
        target_day = min(days, key=lambda d: len(plan[d]))
        if pick["slug"] not in plan[target_day]:
            plan[target_day].append(pick["slug"])

    # Always ensure ps_from_ps is on every day
    for day in plan:
        if "ps_from_ps" not in plan[day]:
            plan[day].append("ps_from_ps")

    return plan

"""Genre matching and section weighting engine.

Maps subscriber genre preferences to section content for personalized
newsletter ordering.  INACTIVE by default — enable via config.
"""

from __future__ import annotations

import logging
from typing import Optional

from weeklyamp.core.models import GenrePreferencesConfig
from weeklyamp.db.repository import Repository

logger = logging.getLogger(__name__)


class GenreEngine:
    """Score and reorder newsletter sections based on subscriber genre affinity."""

    def __init__(self, repo: Repository, config: GenrePreferencesConfig) -> None:
        self.repo = repo
        self.config = config

    # ------------------------------------------------------------------
    # Subscriber genre affinity
    # ------------------------------------------------------------------

    def get_subscriber_genre_affinity(self, subscriber_id: int) -> dict[str, float]:
        """Return subscriber's genres as ``{genre: weight}`` where weight = 1.0 / priority.

        Higher-priority genres (lower priority number) get a higher weight.
        """
        if not self.config.enabled:
            return {}

        conn = self.repo._conn()
        rows = conn.execute(
            "SELECT genre, priority FROM subscriber_genres WHERE subscriber_id = ? ORDER BY priority",
            (subscriber_id,),
        ).fetchall()
        conn.close()

        return {r["genre"]: 1.0 / max(r["priority"], 1) for r in rows}

    # ------------------------------------------------------------------
    # Section-genre match scoring
    # ------------------------------------------------------------------

    def get_section_genre_match(
        self, section_slug: str, subscriber_genres: dict[str, float],
    ) -> float:
        """Score how well *section_slug* matches *subscriber_genres* (0.0–1.0).

        Uses the ``section_genres`` table.  The score is the sum of matching
        genre weights (subscriber side) multiplied by relevance weights
        (section side), normalised to [0, 1].
        """
        if not self.config.enabled or not subscriber_genres:
            return 0.0

        conn = self.repo._conn()
        rows = conn.execute(
            "SELECT genre, relevance_weight FROM section_genres WHERE section_slug = ?",
            (section_slug,),
        ).fetchall()
        conn.close()

        if not rows:
            return 0.0

        score = 0.0
        max_possible = 0.0
        for r in rows:
            genre = r["genre"]
            relevance = r["relevance_weight"] or 1.0
            max_possible += relevance
            if genre in subscriber_genres:
                score += subscriber_genres[genre] * relevance

        if max_possible == 0.0:
            return 0.0

        return min(score / max_possible, 1.0)

    # ------------------------------------------------------------------
    # Reorder sections by genre affinity
    # ------------------------------------------------------------------

    def weight_sections_for_subscriber(
        self, sections: list[dict], subscriber_id: int,
    ) -> list[dict]:
        """Reorder *sections* by genre affinity for *subscriber_id*.

        Sections with a non-zero genre match score are sorted highest-first.
        Unmatched sections keep their original relative order and appear at
        the end.
        """
        if not self.config.enabled or not self.config.weight_sections_by_genre:
            return sections

        affinity = self.get_subscriber_genre_affinity(subscriber_id)
        if not affinity:
            return sections

        scored: list[tuple[float, int, dict]] = []
        unmatched: list[tuple[int, dict]] = []

        for idx, sec in enumerate(sections):
            slug = sec.get("slug", sec.get("section_slug", ""))
            match_score = self.get_section_genre_match(slug, affinity)
            if match_score > 0.0:
                scored.append((match_score, idx, sec))
            else:
                unmatched.append((idx, sec))

        # Sort matched sections by score descending (stable by original index)
        scored.sort(key=lambda t: (-t[0], t[1]))

        result = [s for _, _, s in scored] + [s for _, s in unmatched]
        return result

    # ------------------------------------------------------------------
    # Combined ranker: genre affinity + click history
    # ------------------------------------------------------------------

    def get_subscriber_engagement_scores(self, subscriber_id: int) -> dict[str, float]:
        """Return ``{section_slug: normalised_engagement_score}`` from
        ``subscriber_interest_profiles``. Scores are normalised to [0, 1]
        by dividing by the max score across the subscriber's profile so
        a subscriber with universally low engagement still gets ordering
        signal from their relative click history."""
        conn = self.repo._conn()
        rows = conn.execute(
            "SELECT section_slug, engagement_score FROM subscriber_interest_profiles "
            "WHERE subscriber_id = ?",
            (subscriber_id,),
        ).fetchall()
        conn.close()
        if not rows:
            return {}
        scores = {r["section_slug"]: float(r["engagement_score"] or 0.0) for r in rows}
        max_score = max(scores.values()) if scores else 0.0
        if max_score <= 0.0:
            return {}
        return {slug: score / max_score for slug, score in scores.items()}

    def rank_sections_for_subscriber(
        self, sections: list[dict], subscriber_id: int,
        *, genre_weight: float = 0.6,
    ) -> list[dict]:
        """Reorder *sections* by a combined score of genre affinity and
        click engagement.

        ``genre_weight`` controls the blend: 1.0 = pure genre affinity
        (cold-start friendly, no history needed); 0.0 = pure engagement
        history (only useful once a subscriber has clicked things).
        Default 0.6 favours stated preferences over inferred behaviour
        because genre prefs are explicit and engagement scores are noisy
        for low-volume subscribers.

        Returns sections with non-zero combined scores first (descending),
        followed by unscored sections in their original order. The base
        order falls through unchanged when the engine is disabled or the
        subscriber has neither prefs nor history — keeping per-subscriber
        ranking purely additive over the static ``sort_order`` layout.
        """
        if not self.config.enabled:
            return sections

        affinity = self.get_subscriber_genre_affinity(subscriber_id)
        engagement = self.get_subscriber_engagement_scores(subscriber_id)
        if not affinity and not engagement:
            return sections

        # Clamp the blend factor to [0, 1] in case a caller misconfigures.
        gw = max(0.0, min(1.0, genre_weight))

        scored: list[tuple[float, int, dict]] = []
        unscored: list[tuple[int, dict]] = []
        for idx, sec in enumerate(sections):
            slug = sec.get("slug", sec.get("section_slug", ""))
            genre_match = self.get_section_genre_match(slug, affinity) if affinity else 0.0
            eng_score = engagement.get(slug, 0.0)
            combined = gw * genre_match + (1.0 - gw) * eng_score
            if combined > 0.0:
                scored.append((combined, idx, sec))
            else:
                unscored.append((idx, sec))

        # Sort descending by combined score, with original index as a
        # stable tiebreaker so two equally-scored sections preserve their
        # editorial order.
        scored.sort(key=lambda t: (-t[0], t[1]))
        return [s for _, _, s in scored] + [s for _, s in unscored]

    # ------------------------------------------------------------------
    # Analytics
    # ------------------------------------------------------------------

    def get_genre_analytics(self) -> dict[str, dict[str, int]]:
        """Return ``{genre: {subscribers: N, sections: N}}`` for the dashboard."""
        if not self.config.enabled:
            return {}

        conn = self.repo._conn()

        sub_rows = conn.execute(
            "SELECT genre, COUNT(DISTINCT subscriber_id) as cnt FROM subscriber_genres GROUP BY genre",
        ).fetchall()

        sec_rows = conn.execute(
            "SELECT genre, COUNT(DISTINCT section_slug) as cnt FROM section_genres GROUP BY genre",
        ).fetchall()

        conn.close()

        analytics: dict[str, dict[str, int]] = {}
        for r in sub_rows:
            analytics.setdefault(r["genre"], {"subscribers": 0, "sections": 0})
            analytics[r["genre"]]["subscribers"] = r["cnt"]
        for r in sec_rows:
            analytics.setdefault(r["genre"], {"subscribers": 0, "sections": 0})
            analytics[r["genre"]]["sections"] = r["cnt"]

        return analytics

    # ------------------------------------------------------------------
    # Seed section genres
    # ------------------------------------------------------------------

    def seed_section_genres(self, sections_with_genres: dict[str, list[str]]) -> None:
        """Bulk set section genre mappings from ``{slug: [genres]}``.

        Replaces existing genres for each provided slug.
        """
        if not self.config.enabled:
            logger.info("Genre engine disabled — skipping seed_section_genres")
            return

        for slug, genres in sections_with_genres.items():
            self.repo.set_section_genres(slug, genres)

        logger.info("Seeded genres for %d sections", len(sections_with_genres))

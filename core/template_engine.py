"""Template engine — Tier 2 of the hybrid LLM architecture (zero cost).

Weighted-random narrative fragments stored in `narrative_templates`,
with `{placeholder}` substitution. The bot feels alive without any API call.
"""
from __future__ import annotations

import random
import re
from collections import defaultdict

from db.database import Database

_PLACEHOLDER_RE = re.compile(r"\{(\w+)\}")

# Hardcoded last-resort fallbacks (used if a category has no fragments)
_FALLBACKS: dict[str, str] = {
    "cultivate": "{name} absorbs the drifting spiritual essence. The world feels... quieter.",
    "breakthrough_success": "The bottleneck shatters! {name} rises to {realm}.",
    "breakthrough_fail": "The qi within {name} scatters like startled cranes. The breakthrough fails.",
    "heart_demon_backlash": "A 心魔 (Heart Demon) stirs within {name}, cackling from the shadows.",
    "erasure": "The Heaven's gaze turns cold. {name} is scattered to the mortal dust.",
    "register": "{name} takes their first breath upon the path of cultivation.",
    "startup": "The Heavenly Dao has awakened.",
    "world_event": "A great calamity stirs upon the horizon...",
    "dao_punish": "The Heaven's will descends upon {name}.",
    "dao_bless": "A golden light bathes {name}. Heaven smiles today.",
    "companion": "{companion} regards {name} with a knowing gaze.",
    "_default": "The Dao flows on, patient as stone.",
}


class TemplateEngine:
    def __init__(self, db: Database) -> None:
        self.db = db
        self._cache: dict[str, list[tuple[str, float]]] | None = None

    async def load(self) -> None:
        rows = await self.db.fetchall("SELECT category, fragment, weight FROM narrative_templates")
        groups: dict[str, list[tuple[str, float]]] = defaultdict(list)
        for row in rows:
            groups[row["category"]].append((row["fragment"], row["weight"]))
        self._cache = dict(groups)

    def reload(self, cache: dict[str, list[tuple[str, float]]] | None) -> None:
        self._cache = cache

    async def get(self, category: str, **kwargs) -> str:
        if self._cache is None:
            await self.load()
        candidates = self._cache.get(category) if self._cache else None
        if not candidates:
            fragment = _FALLBACKS.get(category, _FALLBACKS["_default"])
        else:
            weights = [w for _, w in candidates]
            fragment = random.choices(
                [f for f, _ in candidates], weights=weights, k=1
            )[0]
        return self._render(fragment, kwargs)

    @staticmethod
    def _render(fragment: str, kwargs: dict) -> str:
        return _PLACEHOLDER_RE.sub(
            lambda m: str(kwargs.get(m.group(1), m.group(0))), fragment
        )

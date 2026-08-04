"""Optional Groq free-tier LLM client.

The bot is 100% playable with this DISABLED (the default). When enabled it is
only used for Tier-4 narrative moments (Heart Demon trials, companion first
meetings, world-event climaxes) and every failure falls back to the template
engine. Rate limits are enforced so the free quota stretches across members.
"""
from __future__ import annotations

import time

import aiohttp

from config import default as config
from db.database import Database


class GroqClient:
    def __init__(
        self,
        api_key: str = "",
        db: Database | None = None,
        enabled: bool | None = None,
        model: str = "",
    ) -> None:
        self.api_key = api_key
        self.db = db
        self.enabled = config.ENABLE_GROQ if enabled is None else enabled
        self.model = model or config.GROQ_MODEL

    @property
    def available(self) -> bool:
        return self.enabled and bool(self.api_key)

    async def can_use(self, user_id: int, guild_id: int) -> bool:
        """Fail closed: any limit hit (or missing DB) blocks the call."""
        if self.db is None:
            return False
        player, hourly, daily = await self._usage_counts(user_id, guild_id)
        return (
            player < 1
            and hourly < config.GROQ_GLOBAL_HOURLY_LIMIT
            and daily < config.GROQ_GLOBAL_DAILY_LIMIT
        )

    async def _usage_counts(self, user_id: int, guild_id: int) -> tuple[int, int, int]:
        assert self.db is not None
        player = await self.db.fetchone(
            "SELECT COUNT(*) AS c FROM llm_usage WHERE user_id=? AND created_at > ?",
            (user_id, _iso_hours_ago(config.GROQ_PLAYER_COOLDOWN_HOURS)),
        )
        hourly = await self.db.fetchone(
            "SELECT COUNT(*) AS c FROM llm_usage WHERE created_at > ?",
            (_iso_hours_ago(1),),
        )
        daily = await self.db.fetchone(
            "SELECT COUNT(*) AS c FROM llm_usage WHERE created_at > ?",
            (_iso_hours_ago(24),),
        )
        return (
            int(player["c"]) if player else 0,
            int(hourly["c"]) if hourly else 0,
            int(daily["c"]) if daily else 0,
        )

    async def generate(
        self,
        system_prompt: str,
        user_prompt: str,
        purpose: str = "narrative",
        user_id: int = 0,
        guild_id: int = 0,
    ) -> str | None:
        """Returns LLM text or None on ANY failure (caller falls back to templates)."""
        if not self.available:
            return None
        if user_id and not await self.can_use(user_id, guild_id):
            return None
        payload = {
            "model": self.model,
            "messages": [
                {"role": "system", "content": system_prompt},
                {"role": "user", "content": user_prompt},
            ],
            "max_tokens": config.GROQ_MAX_TOKENS,
            "temperature": config.GROQ_TEMPERATURE,
        }
        try:
            timeout = aiohttp.ClientTimeout(total=config.GROQ_TIMEOUT_SECONDS)
            async with aiohttp.ClientSession(timeout=timeout) as session:
                async with session.post(
                    "https://api.groq.com/openai/v1/chat/completions",
                    headers={
                        "Authorization": f"Bearer {self.api_key}",
                        "Content-Type": "application/json",
                    },
                    json=payload,
                ) as resp:
                    if resp.status != 200:
                        return None
                    data = await resp.json()
                    text = data["choices"][0]["message"]["content"].strip()
        except Exception:
            return None
        if self.db is not None and user_id:
            await self.db.execute(
                "INSERT INTO llm_usage (user_id, guild_id, model, prompt_purpose)"
                " VALUES (?,?,?,?)",
                (user_id, guild_id, self.model, purpose),
            )
        return text or None


async def generate_or_template(
    groq: GroqClient | None,
    templates,
    category: str,
    purpose: str,
    user_id: int = 0,
    guild_id: int = 0,
    **kwargs,
) -> str:
    """Tier-4 call with automatic Tier-2 template fallback."""
    if groq is not None and groq.available:
        text = await groq.generate(
            system_prompt=(
                "You are the Heavenly Dao of a Xianxia world. Reply in 2-3 vivid, "
                "concise sentences with Chinese xianxia flavor (道侣, 心魔, 雷劫). "
                "Never break character."
            ),
            user_prompt=kwargs.get("prompt", ""),
            purpose=purpose,
            user_id=user_id,
            guild_id=guild_id,
        )
        if text:
            return text
    return await templates.get(category, **kwargs)


def _iso_hours_ago(hours: int) -> str:
    from datetime import datetime, timedelta, timezone

    return (datetime.now(timezone.utc) - timedelta(hours=hours)).strftime(
        "%Y-%m-%d %H:%M:%S"
    )

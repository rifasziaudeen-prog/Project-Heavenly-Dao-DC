"""Tests for the optional Groq client — it must always fail closed."""
import asyncio

from core.groq_client import GroqClient


def test_disabled_by_default_returns_none():
    client = GroqClient(api_key="", enabled=False)
    assert client.available is False
    assert asyncio.run(client.generate("sys", "user")) is None


def test_enabled_without_key_returns_none():
    client = GroqClient(api_key="", enabled=True, db=None)
    assert client.available is False
    assert asyncio.run(client.generate("sys", "user", user_id=1, guild_id=1)) is None


def test_can_use_fails_closed_without_db():
    client = GroqClient(api_key="k", enabled=True, db=None)
    assert asyncio.run(client.can_use(1, 1)) is False

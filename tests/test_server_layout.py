"""Tests for the Heavenly Dao server blueprint (core/server_layout.py)."""
from __future__ import annotations

import discord

from core import server_layout as layout


def _roles() -> dict[str, discord.Object]:
    """Hashable stand-ins for guild roles (only used as overwrite keys).

    Ids start at 1000 so they can never collide with the @everyone stand-in
    (discord.Object equality is by id).
    """
    return {r["name"]: discord.Object(id=1000 + i) for i, r in enumerate(layout.ROLES_SPEC)}


def _default() -> discord.Object:
    return discord.Object(id=0)


# --------------------------------------------------------------------------- integrity
def test_layout_has_no_validation_errors() -> None:
    assert layout.validate_layout() == []


def test_blueprint_sizes() -> None:
    assert len(layout.ROLES_SPEC) == 28
    assert len([c for cat in layout.STRUCTURE for c in cat["channels"]]) == 34
    assert len(layout.STRUCTURE) == 8


def test_reaction_map_emojis_are_normalized() -> None:
    for emoji in layout.REACTION_ROLE_MAP:
        assert "\ufe0f" not in emoji, f"emoji {emoji!r} should be stored without variation selector"


def test_exclusive_groups_reference_self_assignable_roles() -> None:
    assignable = layout.SELF_ASSIGNABLE_ROLE_NAMES
    for group in layout.EXCLUSIVE_GROUPS:
        assert set(group) <= assignable


def test_staff_roles_exist() -> None:
    names = {r["name"] for r in layout.ROLES_SPEC}
    assert set(layout.STAFF_ROLES) <= names


# --------------------------------------------------------------------------- role permissions
def test_admin_role_gets_all_permissions() -> None:
    dao_ancestor = next(r for r in layout.ROLES_SPEC if r["name"] == "👑 Dao Ancestor")
    assert layout.role_permissions(dao_ancestor) == discord.Permissions.all()


def test_enforcer_gets_moderation_permissions() -> None:
    enforcer = next(r for r in layout.ROLES_SPEC if r["name"] == "🛡️ Heavenly Enforcer")
    perms = layout.role_permissions(enforcer)
    assert perms.kick_members and perms.ban_members
    assert perms.manage_messages and perms.moderate_members
    assert not perms.administrator


# --------------------------------------------------------------------------- channel overwrites
def test_read_only_channel_blocks_mortals_from_posting() -> None:
    ch_spec = {"name": "announcements", "read_only": True, "topic": "t"}
    default = _default()
    ow = layout.channel_overwrites(ch_spec, _roles(), default)
    assert ow[default].send_messages is False
    assert ow[default].view_channel is True
    assert ow[default].add_reactions is True


def test_read_only_channel_staff_can_post() -> None:
    ch_spec = {
        "name": "announcements", "read_only": True, "topic": "t",
        "perms": [{"role": "🛡️ Heavenly Enforcer", "allow": ["send_messages"]}],
    }
    roles = _roles()
    ow = layout.channel_overwrites(ch_spec, roles, _default())
    assert ow[roles["🛡️ Heavenly Enforcer"]].send_messages is True


def test_hidden_channel_denies_everyone_but_allows_staff() -> None:
    ch_spec = {"name": "staff-chat", "hidden": True, "topic": "t"}
    roles = _roles()
    default = _default()
    ow = layout.channel_overwrites(ch_spec, roles, default)
    assert ow[default].view_channel is False
    for staff in layout.STAFF_ROLES:
        assert ow[roles[staff]].view_channel is True


def test_deny_overwrites_are_applied() -> None:
    ch_spec = {
        "name": "quiet", "topic": "t",
        "perms": [{"role": "☯️ Yang Cultivator", "deny": ["send_messages"]}],
    }
    roles = _roles()
    ow = layout.channel_overwrites(ch_spec, roles, _default())
    assert ow[roles["☯️ Yang Cultivator"]].send_messages is False


def test_unknown_role_in_perms_is_skipped() -> None:
    ch_spec = {
        "name": "x", "topic": "t",
        "perms": [{"role": "👻 Ghost Role", "allow": ["send_messages"]}],
    }
    ow = layout.channel_overwrites(ch_spec, _roles(), _default())
    assert len(ow) == 0  # no default overwrite either (not read_only/hidden)


def test_plain_channel_has_no_overwrites() -> None:
    ch_spec = {"name": "general-chat", "topic": "t"}
    ow = layout.channel_overwrites(ch_spec, _roles(), _default())
    assert ow == {}

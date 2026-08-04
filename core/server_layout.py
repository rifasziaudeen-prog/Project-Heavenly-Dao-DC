"""Single source of truth for the Heavenly Dao server blueprint (v2).

Both `/setup_server` (the slash command), the `!setup` text fallback, and the
standalone `scripts/setup_discord_server.py` build the server from THIS module,
so a layout change upgrades every entry point at once.

Everything here is plain data + pure functions (no Discord objects required
except where noted), which keeps the layout unit-testable without a gateway.
"""
from __future__ import annotations

import discord

# --------------------------------------------------------------------------- names
WELCOME_CHANNEL = "welcome"
RULES_CHANNEL = "rules-and-guide"
ANNOUNCEMENTS_CHANNEL = "announcements"
ROLE_SELECTION_CHANNEL = "role-selection"
GETTING_STARTED_CHANNEL = "getting-started"
COMMAND_REFERENCE_CHANNEL = "command-reference"

STAFF_ROLES = [
    "👑 Dao Ancestor",
    "🛡️ Heavenly Enforcer",
    "⚖️ Law Keeper",
    "🧹 Sect Steward",
]

# --------------------------------------------------------------------------- roles
ROLES_SPEC: list[dict] = [
    # --- Governance ----------------------------------------------------------
    {"name": "👑 Dao Ancestor", "color": "gold", "hoist": True, "admin": True,
     "self_assignable": False, "mentionable": True,
     "permissions": []},
    {"name": "🛡️ Heavenly Enforcer", "color": "dark_blue", "hoist": True, "admin": False,
     "self_assignable": False, "mentionable": True,
     "permissions": ["kick_members", "ban_members", "moderate_members", "manage_messages",
                     "mute_members", "deafen_members", "move_members", "manage_nicknames",
                     "view_audit_log", "read_message_history"]},
    {"name": "⚖️ Law Keeper", "color": "purple", "hoist": True, "admin": False,
     "self_assignable": False, "mentionable": True,
     "permissions": ["moderate_members", "manage_messages", "mute_members", "deafen_members",
                     "read_message_history", "view_audit_log"]},
    {"name": "🧹 Sect Steward", "color": "green", "hoist": True, "admin": False,
     "self_assignable": False, "mentionable": True,
     "permissions": ["manage_messages", "moderate_members", "move_members",
                     "manage_nicknames", "connect", "speak"]},
    # --- Gender identity (self-assignable) ------------------------------------
    {"name": "☯️ Yang Cultivator", "color": "blue", "hoist": False, "admin": False,
     "self_assignable": True, "mentionable": True, "permissions": []},
    {"name": "☯️ Yin Cultivator", "color": "magenta", "hoist": False, "admin": False,
     "self_assignable": True, "mentionable": True, "permissions": []},
    # --- Realm tiers -----------------------------------------------------------
    {"name": "✨ Mortal Meridian", "color": "light_grey", "hoist": False, "admin": False,
     "self_assignable": False, "mentionable": False, "permissions": []},
    {"name": "🥉 Tier 1: Qi Condensation (练气)", "color": "dark_teal", "hoist": False, "admin": False,
     "self_assignable": False, "mentionable": False, "permissions": []},
    {"name": "🥈 Tier 2: Foundation Establishment (筑基)", "color": "teal", "hoist": False, "admin": False,
     "self_assignable": False, "mentionable": False, "permissions": []},
    {"name": "🥇 Tier 3: Golden Core (金丹)", "color": "gold", "hoist": False, "admin": False,
     "self_assignable": False, "mentionable": False, "permissions": []},
    {"name": "💎 Tier 4: Nascent Soul (元婴)", "color": "purple", "hoist": False, "admin": False,
     "self_assignable": False, "mentionable": False, "permissions": []},
    {"name": "🌌 Tier 5: Soul Formation (化神)", "color": "dark_purple", "hoist": False, "admin": False,
     "self_assignable": False, "mentionable": False, "permissions": []},
    {"name": "🔮 Tier 6: Void Refinement (炼虚)", "color": "dark_magenta", "hoist": False, "admin": False,
     "self_assignable": False, "mentionable": False, "permissions": []},
    {"name": "👑 Tier 7: Mahayana (大乘)", "color": "dark_gold", "hoist": False, "admin": False,
     "self_assignable": False, "mentionable": False, "permissions": []},
    {"name": "⚡ Tier 8: Tribulation Transcendance (渡劫)", "color": "red", "hoist": False, "admin": False,
     "self_assignable": False, "mentionable": False, "permissions": []},
    {"name": "☀️ Tier 9: Immortal Ascension (仙人)", "color": "lighter_grey", "hoist": True, "admin": False,
     "self_assignable": False, "mentionable": False, "permissions": []},
    # --- Martial paths (self-assignable) --------------------------------------
    {"name": "🗡️ Sword Saint 剑修", "color": "light_grey", "hoist": False, "admin": False,
     "self_assignable": True, "mentionable": True, "permissions": []},
    {"name": "⚔️ Sabre Lord 刀修", "color": "dark_red", "hoist": False, "admin": False,
     "self_assignable": True, "mentionable": True, "permissions": []},
    {"name": "🏹 Spear Master 枪修", "color": "dark_blue", "hoist": False, "admin": False,
     "self_assignable": True, "mentionable": True, "permissions": []},
    {"name": "👊 Fist Tyrant 拳修", "color": "orange", "hoist": False, "admin": False,
     "self_assignable": True, "mentionable": True, "permissions": []},
    # --- Element roots (self-assignable) --------------------------------------
    {"name": "🔥 Fire Affinity 火灵根", "color": "red", "hoist": False, "admin": False,
     "self_assignable": True, "mentionable": True, "permissions": []},
    {"name": "💧 Water Affinity 水灵根", "color": "blue", "hoist": False, "admin": False,
     "self_assignable": True, "mentionable": True, "permissions": []},
    {"name": "🌿 Wood Affinity 木灵根", "color": "green", "hoist": False, "admin": False,
     "self_assignable": True, "mentionable": True, "permissions": []},
    {"name": "🪨 Earth Affinity 土灵根", "color": "dark_gold", "hoist": False, "admin": False,
     "self_assignable": True, "mentionable": True, "permissions": []},
    {"name": "⚙️ Metal Affinity 金灵根", "color": "greyple", "hoist": False, "admin": False,
     "self_assignable": True, "mentionable": True, "permissions": []},
    {"name": "🌪️ Qi Affinity 炁灵根", "color": "blurple", "hoist": False, "admin": False,
     "self_assignable": True, "mentionable": True, "permissions": []},
    # --- Culture (self-assignable) ---------------------------------------------
    {"name": "📜 Dao Scholar 道子", "color": "dark_green", "hoist": False, "admin": False,
     "self_assignable": True, "mentionable": True, "permissions": []},
    {"name": "🎨 Spirit Painter 画仙", "color": "dark_purple", "hoist": False, "admin": False,
     "self_assignable": True, "mentionable": True, "permissions": []},
]

SELF_ASSIGNABLE_ROLE_NAMES = {
    r["name"] for r in ROLES_SPEC if r.get("self_assignable")
}

# --------------------------------------------------------------------------- reaction roles
# Emoji → role name. Emojis are stored without variation selectors; the handler
# normalizes incoming reactions the same way.
REACTION_ROLE_MAP: dict[str, str] = {
    "🌞": "☯️ Yang Cultivator",
    "🌙": "☯️ Yin Cultivator",
    "🗡": "🗡️ Sword Saint 剑修",
    "⚔": "⚔️ Sabre Lord 刀修",
    "🏹": "🏹 Spear Master 枪修",
    "👊": "👊 Fist Tyrant 拳修",
    "🔥": "🔥 Fire Affinity 火灵根",
    "💧": "💧 Water Affinity 水灵根",
    "🌿": "🌿 Wood Affinity 木灵根",
    "🪨": "🪨 Earth Affinity 土灵根",
    "⚙": "⚙️ Metal Affinity 金灵根",
    "🌪": "🌪️ Qi Affinity 炁灵根",
    "📜": "📜 Dao Scholar 道子",
    "🎨": "🎨 Spirit Painter 画仙",
}

# Picking a role removes the others in its group (one gender, one path, one root).
EXCLUSIVE_GROUPS: list[list[str]] = [
    ["☯️ Yang Cultivator", "☯️ Yin Cultivator"],
    ["🗡️ Sword Saint 剑修", "⚔️ Sabre Lord 刀修", "🏹 Spear Master 枪修", "👊 Fist Tyrant 拳修"],
    ["🔥 Fire Affinity 火灵根", "💧 Water Affinity 水灵根", "🌿 Wood Affinity 木灵根",
     "🪨 Earth Affinity 土灵根", "⚙️ Metal Affinity 金灵根", "🌪️ Qi Affinity 炁灵根"],
]

# --------------------------------------------------------------------------- channels
# Channel spec fields:
#   name       — unique Discord channel slug (must be unique server-wide)
#   kind       — "text" (default) or "voice"
#   topic      — bilingual description shown under the channel name
#   read_only  — mortals may read but not post
#   hidden     — staff-only (default role cannot see it)
#   perms      — extra per-role overwrites: [{role, allow: [...], deny: [...]}]
STRUCTURE: list[dict] = [
    {
        "category": "🌄 THE MORTAL WORLD · 凡界",
        "channels": [
            {"name": "welcome", "read_only": True, "topic": "🌅 The gateway to the realm — read the welcome, then choose your path below · 初入凡尘，先读此卷"},
            {"name": "rules-and-guide", "read_only": True, "topic": "📜 Server rules, conduct, and the way of the Dao · 门规与修行之道"},
            {"name": "announcements", "read_only": True, "topic": "📢 World events, broadcasts, and heavenly decrees · 天道公告",
             "perms": [
                 {"role": "🛡️ Heavenly Enforcer", "allow": ["send_messages"]},
                 {"role": "⚖️ Law Keeper", "allow": ["send_messages"]},
                 {"role": "🧹 Sect Steward", "allow": ["send_messages"]},
             ]},
            {"name": "role-selection", "topic": "🎭 React below to claim your gender, martial path, and element root · 道途抉择"},
            {"name": "server-status", "read_only": True, "topic": "🛠️ Bot status and maintenance notices · 天机阁"},
        ],
    },
    {
        "category": "📖 THE SCRIPTURES · 藏经阁",
        "channels": [
            {"name": "getting-started", "read_only": True, "topic": "🌱 A mortal's first steps: register, cultivate, break through · 入门须知"},
            {"name": "command-reference", "read_only": True, "topic": "📚 Every slash command, organized by realm · 功法总纲"},
            {"name": "faq", "topic": "❓ Questions and answers about the realm · 疑难解答"},
        ],
    },
    {
        "category": "🌌 CULTIVATION GROUNDS · 修炼场",
        "channels": [
            {"name": "meditation-hall", "topic": "🧘 Chat and passively absorb Qi (15 msgs/hour cap) · 闲聊亦积灵气"},
            {"name": "breakthrough-tribulations", "topic": "⚡ /cultivate and /breakthrough attempts · 渡劫之地"},
            {"name": "secret-realms", "topic": "🏔️ /realms, /enter_realm, /explore, /retreat · 秘境探险"},
            {"name": "dao-comprehension", "topic": "📜 /laws, /comprehend, /law_status · 悟道场"},
            {"name": "alchemy-pavilion", "topic": "⚗️ /recipes, /refine_pill, /alchemy_status · 丹房"},
            {"name": "heavenly-market", "topic": "🏪 /market, /sell, /buy, /bid, /trade · 坊市交易"},
        ],
    },
    {
        "category": "🏯 SECTS & BONDS · 宗门道侣",
        "channels": [
            {"name": "sect-hall", "topic": "🏛️ /sect_create, /sect_join, /sect_donate, /sect_upgrade · 宗门大殿"},
            {"name": "dao-bonds", "topic": "💞 /dao_bond, /dao_bond_accept, /dual_cultivate · 道侣结缘"},
        ],
    },
    {
        "category": "⚔️ CALAMITIES & EVENTS · 天地大劫",
        "channels": [
            {"name": "world-boss-battlefield", "topic": "🐉 /events, /event_join, /event_attack, /event_claim · 讨伐魔尊"},
            {"name": "heavenly-calamities", "topic": "⛈️ Scheduled calamities and event coordination · 天劫预告",
             "perms": [
                 {"role": "🛡️ Heavenly Enforcer", "allow": ["send_messages"]},
                 {"role": "⚖️ Law Keeper", "allow": ["send_messages"]},
             ]},
            {"name": "victory-hall", "read_only": True, "topic": "🏆 World boss victories and tournament champions · 封神榜"},
        ],
    },
    {
        "category": "🗣️ IMMORTAL PAVILION · 仙家宴",
        "channels": [
            {"name": "general-chat", "topic": "🎐 The main social hall — talk about anything · 仙家闲聊"},
            {"name": "memes", "topic": "😂 Cultivation memes and scrolls of humor · 趣闻妙语"},
            {"name": "art-gallery", "topic": "🎨 Fan art and screenshots of your cultivation · 丹青阁"},
            {"name": "music-poetry", "topic": "🎶 Music, poetry, and immortal songs · 仙乐诗词"},
            {"name": "introductions", "topic": "👋 New cultivators introduce themselves · 初入江湖"},
            {"name": "pet-pavilion", "topic": "🐾 Show off your spirit beasts and familiars · 灵兽园"},
            {"name": "venting-cave", "topic": "🕳️ A safe cave to vent — be kind to fellow cultivators · 心魔洞（倾诉）"},
            {"name": "meditation-grove", "kind": "voice", "topic": "🎧 Voice chat for quiet cultivation · 静修语音"},
            {"name": "battle-arena", "kind": "voice", "topic": "⚔️ Voice arena for tournaments and debates · 论武台"},
        ],
    },
    {
        "category": "📜 RECORDS & ARCHIVES · 天机藏卷",
        "channels": [
            {"name": "leaderboards", "read_only": True, "topic": "🏅 Realm leaderboards and rankings · 天骄榜"},
            {"name": "world-lore", "read_only": True, "topic": "📖 The history and lore of the realm · 山海经"},
            {"name": "screenshots", "topic": "📸 Screenshot moments of your journey · 留影壁"},
            {"name": "suggestions", "topic": "💡 Suggest features — the Heaven reads these · 献策"},
        ],
    },
    {
        "category": "🏛️ HEAVENLY COURT · 天庭",
        "channels": [
            {"name": "staff-chat", "hidden": True, "topic": "🔒 Staff-only coordination · 天庭议事"},
            {"name": "staff-voice", "kind": "voice", "hidden": True, "topic": "🔒 Private staff voice · 天庭密语"},
        ],
    },
]

# --------------------------------------------------------------------------- pure helpers
def resolve_color(name: str) -> discord.Color:
    """Map a color name to a discord.Color (e.g. \"gold\" -> Color.gold())."""
    return getattr(discord.Color, name)()


def role_permissions(rspec: dict) -> discord.Permissions:
    """Full permissions for admins, general + explicit flags otherwise."""
    if rspec.get("admin"):
        return discord.Permissions.all()
    perms = discord.Permissions.general()
    perms.update(**{flag: True for flag in rspec.get("permissions", [])})
    return perms


def channel_overwrites(ch_spec: dict, roles: dict, default_role) -> dict:
    """Build permission overwrites for a channel.

    ``roles`` maps role NAME → Role-like object (used only as overwrite keys);
    ``default_role`` is the guild's @everyone role. Returns a dict suitable for
    ``create_text_channel(..., overwrites=...)``.
    """
    overwrites: dict = {}
    if ch_spec.get("read_only"):
        overwrites[default_role] = discord.PermissionOverwrite(
            view_channel=True, send_messages=False, add_reactions=True
        )
    if ch_spec.get("hidden"):
        overwrites[default_role] = discord.PermissionOverwrite(view_channel=False)
        for staff in STAFF_ROLES:
            role = roles.get(staff)
            if role is not None:
                overwrites[role] = discord.PermissionOverwrite(
                    view_channel=True, send_messages=True
                )
    for entry in ch_spec.get("perms", []):
        role = roles.get(entry["role"])
        if role is None:
            continue
        allow = discord.PermissionOverwrite()
        deny = discord.PermissionOverwrite()
        allow.update(**{flag: True for flag in entry.get("allow", [])})
        deny.update(**{flag: True for flag in entry.get("deny", [])})
        if allow._values or deny._values:
            overwrites[role] = discord.PermissionOverwrite.from_pair(allow, deny)
    return overwrites


def resolve_reaction_add(current: set[str], emoji: str) -> tuple[list[str], list[str]]:
    """Roles to add/remove when a member reacts with ``emoji``.

    Exclusive groups mean adding a gender/path/element removes its siblings.
    Returns ([to_add], [to_remove]); both empty if unknown emoji or already held.
    """
    role_name = REACTION_ROLE_MAP.get(emoji)
    if role_name is None or role_name in current:
        return [], []
    to_remove: list[str] = []
    for group in EXCLUSIVE_GROUPS:
        if role_name in group:
            to_remove = [n for n in group if n != role_name and n in current]
            break
    return [role_name], to_remove


def resolve_reaction_remove(current: set[str], emoji: str) -> list[str]:
    """Roles to remove when a member un-reacts with ``emoji``."""
    role_name = REACTION_ROLE_MAP.get(emoji)
    if role_name is None or role_name not in current:
        return []
    return [role_name]


# --------------------------------------------------------------------------- validation
_VALID_FLAGS = set(discord.Permissions.VALID_FLAGS)


def validate_layout() -> list[str]:
    """Return a list of layout problems (empty = blueprint is healthy)."""
    errors: list[str] = []

    role_names = [r["name"] for r in ROLES_SPEC]
    if len(role_names) != len(set(role_names)):
        errors.append("ROLES_SPEC contains duplicate role names")

    for rspec in ROLES_SPEC:
        try:
            resolve_color(rspec["color"])
        except AttributeError:
            errors.append(f"Role {rspec['name']!r}: unknown color {rspec['color']!r}")
        for flag in rspec.get("permissions", []):
            if flag not in _VALID_FLAGS:
                errors.append(f"Role {rspec['name']!r}: invalid permission {flag!r}")

    self_assignable = {r["name"] for r in ROLES_SPEC if r.get("self_assignable")}
    for emoji, role_name in REACTION_ROLE_MAP.items():
        if role_name not in role_names:
            errors.append(f"Reaction emoji {emoji!r} maps to unknown role {role_name!r}")
        elif role_name not in self_assignable:
            errors.append(f"Reaction emoji {emoji!r} maps to non-self-assignable role {role_name!r}")
    for group in EXCLUSIVE_GROUPS:
        for role_name in group:
            if role_name not in self_assignable:
                errors.append(f"Exclusive group role {role_name!r} is not self-assignable")

    categories = [c["category"] for c in STRUCTURE]
    if len(categories) != len(set(categories)):
        errors.append("STRUCTURE contains duplicate category names")

    channel_names: list[str] = []
    for cat_spec in STRUCTURE:
        for ch_spec in cat_spec["channels"]:
            name = ch_spec["name"]
            if name in channel_names:
                errors.append(f"Duplicate channel name {name!r} (must be unique server-wide)")
            channel_names.append(name)
            if ch_spec.get("kind", "text") not in ("text", "voice"):
                errors.append(f"Channel {name!r}: invalid kind {ch_spec.get('kind')!r}")
            if not ch_spec.get("topic"):
                errors.append(f"Channel {name!r}: missing topic")
            for entry in ch_spec.get("perms", []):
                if entry.get("role") not in role_names:
                    errors.append(f"Channel {name!r}: perms reference unknown role {entry.get('role')!r}")
                for flag in entry.get("allow", []) + entry.get("deny", []):
                    if flag not in _VALID_FLAGS:
                        errors.append(f"Channel {name!r}: invalid permission {flag!r}")
    return errors

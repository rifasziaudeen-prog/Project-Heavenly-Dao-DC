"""cogs/affinities.py

Slash commands for the Spiritual Aptitude & Martial Intent Engine (v1.1.0).

Commands:
  /aptitudes [member]   — Display a cultivator's full aptitude profile embed.
"""
from __future__ import annotations

import discord
from discord import app_commands
from discord.ext import commands

from bot import utils as ui
from core import affinities as aff
from core.affinities import (
    ELEMENT_KEYS, ELEMENT_META,
    INTENT_KEYS, INTENT_META,
    AptitudeProfile,
    aptitude_stat_multipliers,
    yin_yang_color,
)


def _profile_from_row(row) -> AptitudeProfile:
    """Build an AptitudeProfile from an aiosqlite Row / dict."""
    d = dict(row)
    return AptitudeProfile(
        yin_yang_balance=d.get("yin_yang_balance", 0),
        affinity_fire=d.get("affinity_fire", 10),
        affinity_water=d.get("affinity_water", 10),
        affinity_wood=d.get("affinity_wood", 10),
        affinity_metal=d.get("affinity_metal", 10),
        affinity_earth=d.get("affinity_earth", 10),
        affinity_qi=d.get("affinity_qi", 10),
        intent_sword=d.get("intent_sword", 5),
        intent_sabre=d.get("intent_sabre", 5),
        intent_spear=d.get("intent_spear", 5),
        intent_fist=d.get("intent_fist", 5),
        special_root=d.get("special_root"),
    )


def _bar(value: int, max_val: int = 100, width: int = 12) -> str:
    """Compact aptitude progress bar."""
    filled = int(round(width * max(0.0, min(1.0, value / max_val))))
    return "▰" * filled + "▱" * (width - filled)


def _yin_yang_bar(balance: int) -> str:
    """Visual bar for Yin-Yang balance: [Yin ←→ Yang]."""
    # -100 = full left (Yin), +100 = full right (Yang), 0 = centre
    width = 20
    centre = width // 2
    normalised = (balance + 100) / 200.0   # 0.0 = pure yin, 1.0 = pure yang
    pos = int(round(normalised * width))
    bar = ["─"] * width
    pos = max(0, min(width - 1, pos))
    bar[pos] = "●"
    return "☯ [" + "".join(bar) + "]"


class AffinitiesCog(commands.Cog):
    def __init__(self, bot) -> None:
        self.bot = bot

    # ========================================================== /aptitudes
    @app_commands.command(
        name="aptitudes",
        description="View your Spiritual Aptitude profile — Five Phases, Martial Intents & Yin-Yang balance",
    )
    async def aptitudes(
        self,
        interaction: discord.Interaction,
        member: discord.Member | None = None,
    ) -> None:
        target = member or interaction.user
        row = await self.bot.db.fetchone(
            "SELECT * FROM cultivators WHERE guild_id=? AND user_id=?",
            (interaction.guild_id, target.id),
        )
        if not row:
            embed = discord.Embed(
                title="Unawakened",
                description=f"{target.mention} has not yet `/register`ed.",
                color=ui.CYAN,
            )
            await interaction.response.send_message(embed=embed, ephemeral=True)
            return

        profile = _profile_from_row(row)
        mults = aptitude_stat_multipliers(profile)

        # Embed colour based on Yin-Yang balance
        color = yin_yang_color(profile.yin_yang_balance)

        dom_el = profile.dominant_element()
        dom_in = profile.dominant_intent()
        dom_el_meta = ELEMENT_META[dom_el]
        dom_in_meta = INTENT_META[dom_in]

        title = f"🌀 {target.display_name}'s Spiritual Aptitude Profile"
        if profile.special_root == "chaos":
            title += " ✨ [Chaos Root]"

        embed = discord.Embed(title=title, color=color)
        embed.set_thumbnail(url=target.display_avatar.url)

        # ── Yin-Yang ──────────────────────────────────────────────────────
        yy = profile.yin_yang_balance
        yy_label = (
            "Pure Yang (Solar / Righteous)" if yy >= 80
            else "Yang Leaning" if yy >= 20
            else "Pure Yin (Phantom / Demonic)" if yy <= -80
            else "Yin Leaning" if yy <= -20
            else "Balanced"
        )
        embed.add_field(
            name="☯ Yin-Yang Balance",
            value=f"{_yin_yang_bar(yy)}\n`{yy:+d}` — {yy_label}",
            inline=False,
        )

        # ── Five Phases ───────────────────────────────────────────────────
        el_lines = []
        for key in ELEMENT_KEYS:
            m = ELEMENT_META[key]
            val = getattr(profile, key)
            star = " ⭐" if key == dom_el else ""
            el_lines.append(f"{m['emoji']} **{m['name']}** `{val:>3}` {_bar(val)}{star}")
        embed.add_field(
            name="🌀 Five Phases (五行) Aptitudes",
            value="\n".join(el_lines),
            inline=False,
        )

        # ── Martial Intents ───────────────────────────────────────────────
        in_lines = []
        for key in INTENT_KEYS:
            m = INTENT_META[key]
            val = getattr(profile, key)
            star = " ⭐" if key == dom_in else ""
            in_lines.append(f"{m['emoji']} **{m['name']}** `{val:>3}` {_bar(val, max_val=100)}{star}")
        embed.add_field(
            name="⚔️ Martial Weapon Intents (武道真意)",
            value="\n".join(in_lines),
            inline=False,
        )

        # ── Dominant bonuses summary ──────────────────────────────────────
        embed.add_field(
            name=f"Dominant Element — {dom_el_meta['emoji']} {dom_el_meta['name']}",
            value=dom_el_meta["effects"],
            inline=True,
        )
        embed.add_field(
            name=f"Dominant Intent — {dom_in_meta['emoji']} {dom_in_meta['name']}",
            value=dom_in_meta["effects"],
            inline=True,
        )

        # ── Special root notice ───────────────────────────────────────────
        if profile.special_root == "chaos":
            embed.add_field(
                name="✨ Special Root — Chaos Five-Element Root (混沌五行根)",
                value=(
                    "A legendary balanced root. You are equally attuned to all Five Phases, "
                    "granting high aptitude in every element and compatibility with all manuals."
                ),
                inline=False,
            )

        embed.set_footer(text="Use /aptitudes to track growth as you cultivate higher realms.")
        await interaction.response.send_message(embed=embed)


async def setup(bot) -> None:
    await bot.add_cog(AffinitiesCog(bot))

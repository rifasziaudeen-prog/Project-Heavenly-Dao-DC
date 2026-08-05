"""Deterministic item generation, drop tables, effect parser, and equip logic.

All math, rates, and effect resolution here are pure Python and auditable — no LLM involvement.
"""
from __future__ import annotations

import json
import random

from core.affinities import check_prerequisites as _check_apt_prereqs

EQUIP_SLOTS = {
    "Weapon": "Weapon",
    "Technique_Scroll": "Technique_Scroll",
}

ITEM_GRADES = ("Mortal", "Earth", "Heaven", "Immortal", "God")


def parse_effect_data(raw: str | dict | None) -> dict:
    """Parse effect_data JSON into a dict."""
    if not raw:
        return {}
    if isinstance(raw, dict):
        return raw
    try:
        data = json.loads(raw)
        return data if isinstance(data, dict) else {}
    except (json.JSONDecodeError, TypeError):
        return {}


def format_effect_description(effect: dict, lang: str = "bilingual") -> str:
    """Format an effect dict into human-readable text."""
    if not effect:
        return "No special effect."
    etype = effect.get("type")
    if etype == "qi_boost":
        amount = effect.get("amount", 0)
        return f"+{amount:,} Qi" if lang == "english" else f"+{amount:,} 灵力"
    if etype == "stat_buff":
        stat = effect.get("stat", "stat").title()
        amount = effect.get("amount", 0)
        return f"+{amount} {stat}"
    if etype == "breakthrough_aid":
        pct = effect.get("bonus_percent", 0)
        return f"+{pct}% Breakthrough Chance" if lang == "english" else f"+{pct}% 突破成功率"
    if etype == "heart_demon_purge":
        pct = effect.get("amount", 0.0) * 100
        return f"-{pct:.0f}% Heart Demon" if lang == "english" else f"-{pct:.0f}% 心魔"
    if etype == "protection":
        ctype = effect.get("charm_type", "charm").replace("_", " ").title()
        return f"Grants {ctype} Charm" if lang == "english" else f"获得 {ctype} 护符"
    return str(effect)


def roll_breakthrough_drops(realm_tier: int) -> list[dict]:
    """Roll item drops on successful breakthrough.

    Rates:
      * Protection Charm: 5%
      * Random Pill: 15% (tier-appropriate grade)
      * Technique Scroll: 8% (tier-appropriate grade)
    """
    drops: list[dict] = []
    grade = (
        "Mortal" if realm_tier <= 2
        else "Earth" if realm_tier <= 5
        else "Heaven" if realm_tier <= 11
        else "Immortal" if realm_tier <= 14
        else "God"
    )

    # 1. Protection Charm (5%)
    if random.random() < 0.05:
        if realm_tier <= 4:
            charm_type = "karmic_shield"
            name = "Karmic Shield Talisman"
        elif random.random() < 0.5:
            charm_type = "reincarnation_seed"
            name = "Reincarnation Seed Talisman"
        else:
            charm_type = "dao_heart_anchor"
            name = "Dao Heart Anchor Talisman"

        drops.append({
            "name": name,
            "item_type": "Talisman",
            "grade": grade,
            "effect_data": json.dumps({"type": "protection", "charm_type": charm_type}),
        })

    # 2. Pill drop (15%)
    if random.random() < 0.15:
        pills_by_grade = {
            "Mortal": ("Qi Gathering Pill", {"type": "qi_boost", "amount": 250}),
            "Earth": ("Foundation Pill", {"type": "qi_boost", "amount": 1000}),
            "Heaven": ("Nine Revolutions Spirit Pill", {"type": "qi_boost", "amount": 5000}),
            "Immortal": ("Immortal Awakening Pill", {"type": "qi_boost", "amount": 50000}),
            "God": ("Dao Ancestor Pill", {"type": "qi_boost", "amount": 1000000}),
        }
        pill_name, pill_eff = pills_by_grade.get(grade, pills_by_grade["Mortal"])
        drops.append({
            "name": pill_name,
            "item_type": "Pill",
            "grade": grade,
            "effect_data": json.dumps(pill_eff),
        })

    # 3. Scroll drop (8%)
    if random.random() < 0.08:
        scrolls_by_grade = {
            "Mortal": ("Basic Qi Breathing Manual", {"type": "breakthrough_aid", "bonus_percent": 5}),
            "Earth": ("Nine Heavens Tribulation Manual", {"type": "breakthrough_aid", "bonus_percent": 12}),
            "Heaven": ("Immortal Sovereign Scripture", {"type": "breakthrough_aid", "bonus_percent": 25}),
            "Immortal": ("Celestial Tribulation Scripture", {"type": "breakthrough_aid", "bonus_percent": 40}),
            "God": ("Transcendent Dao Manual", {"type": "breakthrough_aid", "bonus_percent": 60}),
        }
        scroll_name, scroll_eff = scrolls_by_grade.get(grade, scrolls_by_grade["Mortal"])
        drops.append({
            "name": scroll_name,
            "item_type": "Technique_Scroll",
            "grade": grade,
            "effect_data": json.dumps(scroll_eff),
        })

    return drops


def roll_cultivate_streak_drops(streak_count: int) -> list[dict]:
    """Roll item drops for daily cultivation streaks.

    Rates:
      * 5+ streak: Material (20%)
      * 10+ streak: Talisman (10%)
    """
    drops: list[dict] = []
    if streak_count >= 5 and random.random() < 0.20:
        materials = [
            ("Spirit Herb", "Mortal"),
            ("Monster Core", "Earth"),
            ("Heavenly Jade", "Heaven"),
        ]
        mat_name, mat_grade = random.choice(materials)
        drops.append({
            "name": mat_name,
            "item_type": "Material",
            "grade": mat_grade,
            "effect_data": "{}",
        })

    if streak_count >= 10 and random.random() < 0.10:
        talismans = [
            ("Karmic Shield Talisman", "Earth", {"type": "protection", "charm_type": "karmic_shield"}),
            ("Reincarnation Seed Talisman", "Heaven", {"type": "protection", "charm_type": "reincarnation_seed"}),
            ("Dao Heart Anchor Talisman", "Heaven", {"type": "protection", "charm_type": "dao_heart_anchor"}),
        ]
        t_name, t_grade, t_eff = random.choice(talismans)
        drops.append({
            "name": t_name,
            "item_type": "Talisman",
            "grade": t_grade,
            "effect_data": json.dumps(t_eff),
        })

    return drops


def can_equip_item(item_type: str) -> bool:
    """Only Weapon and Technique_Scroll items can be equipped."""
    return item_type in ("Weapon", "Technique_Scroll")


def equip_toggle(
    equipped_items: list[dict],
    target_item: dict,
    cultivator_aptitudes: dict | None = None,
) -> tuple[bool, str, list[int], list[int]]:
    """Determine equip/unequip changes for a target item.

    Rules:
      * Only Weapon and Technique_Scroll can be equipped.
      * Max 1 Weapon and 1 Technique_Scroll equipped at a time.
      * If target item is already equipped -> unequip it.
      * If another item of the same slot is equipped -> unequip old one, equip target.
      * High-tier items may embed aptitude prerequisites in effect_data
        (keys like "min_affinity_fire", "min_intent_sword").

    Returns:
      (success: bool, message: str, item_ids_to_equip: list[int], item_ids_to_unequip: list[int])
    """
    item_type = target_item.get("item_type")
    if not can_equip_item(item_type):
        return False, f"Items of type '{item_type}' cannot be equipped.", [], []

    target_id = target_item["id"]
    is_currently_equipped = bool(target_item.get("is_equipped", 0))

    if is_currently_equipped:
        # Unequip target — no aptitude check needed
        return True, f"Unequipped **{target_item['name']}**.", [], [target_id]

    # ── Aptitude prerequisite check ─────────────────────────────────────────
    if cultivator_aptitudes:
        eff = parse_effect_data(target_item.get("effect_data"))
        apt_reqs = {k: v for k, v in eff.items() if k.startswith("min_")}
        if apt_reqs:
            ok, missing = _check_apt_prereqs(apt_reqs, cultivator_aptitudes)
            if not ok:
                lines = "\n".join(f"• {m}" for m in missing)
                return (
                    False,
                    f"**{target_item['name']}** requires higher aptitudes:\n{lines}",
                    [], [],
                )

    # ── Slot management ─────────────────────────────────────────────────────
    # Unequip any existing item of the same slot
    to_unequip: list[int] = []
    for eq in equipped_items:
        if eq.get("item_type") == item_type and eq["id"] != target_id:
            to_unequip.append(eq["id"])

    return True, f"Equipped **{target_item['name']}**.", [target_id], to_unequip


def calculate_equipped_bonuses(equipped_items: list[dict]) -> dict:
    """Aggregate stat buffs and breakthrough bonuses from equipped items."""
    stat_buffs = {"physique": 0, "spirit": 0, "luck": 0, "comprehension": 0}
    breakthrough_aid = 0.0

    for item in equipped_items:
        if not item.get("is_equipped"):
            continue
        eff = parse_effect_data(item.get("effect_data"))
        etype = eff.get("type")
        if etype == "stat_buff":
            stat = eff.get("stat", "").lower()
            if stat in stat_buffs:
                stat_buffs[stat] += eff.get("amount", 0)
        elif etype == "breakthrough_aid":
            breakthrough_aid += eff.get("bonus_percent", 0.0)

    return {
        "stat_buffs": stat_buffs,
        "breakthrough_aid": breakthrough_aid,
    }


async def consume_ingredients(db, owner_id: int, ingredients: list[dict]) -> None:
    """Deduct ingredients from cultivator's inventory."""
    for ing in ingredients:
        req_name = ing["item_name"]
        req_qty = ing["quantity"]
        req_grade_min = ing.get("grade_min", "Mortal")
        min_rank = GRADE_RANK.get(req_grade_min, 1)

        # Find matching items in inventory ordered by grade ASC
        rows = await db.fetchall(
            "SELECT * FROM items WHERE owner_id=? AND LOWER(name)=LOWER(?) AND quantity > 0",
            (owner_id, req_name.strip()),
        )
        rem = req_qty
        for r in rows:
            if GRADE_RANK.get(r["grade"], 1) >= min_rank:
                take = min(rem, r["quantity"])
                if take >= r["quantity"]:
                    await db.execute("DELETE FROM items WHERE id=?", (r["id"],))
                else:
                    await db.execute("UPDATE items SET quantity=quantity-? WHERE id=?", (take, r["id"]))
                rem -= take
                if rem <= 0:
                    break


async def grant_pill(
    db, owner_id: int, pill_name: str, grade: str, effect_data: dict | str, quantity: int = 1
) -> None:
    """Add refined pill into cultivator inventory (stacking if unequipped stack exists)."""
    eff_str = json.dumps(effect_data) if isinstance(effect_data, dict) else effect_data
    existing = await db.fetchone(
        "SELECT * FROM items WHERE owner_id=? AND LOWER(name)=LOWER(?) AND is_equipped=0",
        (owner_id, pill_name.strip()),
    )
    if existing:
        await db.execute("UPDATE items SET quantity=quantity+? WHERE id=?", (quantity, existing["id"]))
    else:
        await db.execute(
            "INSERT INTO items (owner_id, name, item_type, grade, effect_data, quantity) VALUES (?,?,?,?,?,?)",
            (owner_id, pill_name, "Pill", grade, eff_str, quantity),
        )

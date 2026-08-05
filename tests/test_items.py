"""Pure logic tests for inventory & item mechanics (core/items.py)."""
import json
from core import items as core_items


def test_parse_effect_data():
    raw_str = '{"type": "qi_boost", "amount": 500}'
    parsed = core_items.parse_effect_data(raw_str)
    assert parsed["type"] == "qi_boost" and parsed["amount"] == 500

    parsed_dict = core_items.parse_effect_data({"type": "stat_buff", "stat": "physique", "amount": 10})
    assert parsed_dict["stat"] == "physique"

    assert core_items.parse_effect_data(None) == {}
    assert core_items.parse_effect_data("invalid json") == {}


def test_format_effect_description():
    eff_qi = {"type": "qi_boost", "amount": 1000}
    assert "1,000 Qi" in core_items.format_effect_description(eff_qi, "english")
    assert "1,000 灵力" in core_items.format_effect_description(eff_qi, "bilingual")

    eff_stat = {"type": "stat_buff", "stat": "physique", "amount": 5}
    assert "+5 Physique" in core_items.format_effect_description(eff_stat, "english")

    eff_aid = {"type": "breakthrough_aid", "bonus_percent": 15}
    assert "+15% Breakthrough Chance" in core_items.format_effect_description(eff_aid, "english")

    eff_hd = {"type": "heart_demon_purge", "amount": 0.15}
    assert "-3 Heart Demon Points" in core_items.format_effect_description(eff_hd, "english")
    assert "-3 心魔点" in core_items.format_effect_description(eff_hd, "chinese")


def test_equip_toggle_constraints():
    # 1. Non-equippable items should fail
    pill = {"id": 1, "name": "Qi Pill", "item_type": "Pill", "grade": "Mortal", "is_equipped": 0}
    ok, msg, eq, uneq = core_items.equip_toggle([], pill)
    assert ok is False and "cannot be equipped" in msg

    # 2. Equip a weapon
    sword1 = {"id": 10, "name": "Wooden Sword", "item_type": "Weapon", "grade": "Mortal", "is_equipped": 0}
    ok, msg, eq, uneq = core_items.equip_toggle([], sword1)
    assert ok is True and eq == [10] and uneq == []

    # 3. Equip a 2nd weapon -> unequips old weapon 10
    sword1_eq = dict(sword1, is_equipped=1)
    sword2 = {"id": 11, "name": "Azure Dragon Sword", "item_type": "Weapon", "grade": "Earth", "is_equipped": 0}
    ok, msg, eq, uneq = core_items.equip_toggle([sword1_eq], sword2)
    assert ok is True and eq == [11] and uneq == [10]

    # 4. Equip a technique scroll alongside weapon 11
    scroll = {"id": 20, "name": "Tribulation Manual", "item_type": "Technique_Scroll", "grade": "Earth", "is_equipped": 0}
    ok, msg, eq, uneq = core_items.equip_toggle([dict(sword2, is_equipped=1)], scroll)
    assert ok is True and eq == [20] and uneq == []

    # 5. Unequip an already equipped item
    ok, msg, eq, uneq = core_items.equip_toggle([dict(sword2, is_equipped=1)], dict(sword2, is_equipped=1))
    assert ok is True and eq == [] and uneq == [11]


def test_calculate_equipped_bonuses():
    sword = {
        "id": 1, "name": "Heavenly Flame Blade", "item_type": "Weapon", "is_equipped": 1,
        "effect_data": json.dumps({"type": "stat_buff", "stat": "physique", "amount": 35}),
    }
    scroll = {
        "id": 2, "name": "Immortal Scripture", "item_type": "Technique_Scroll", "is_equipped": 1,
        "effect_data": json.dumps({"type": "breakthrough_aid", "bonus_percent": 25}),
    }
    unequipped_item = {
        "id": 3, "name": "Unused Sword", "item_type": "Weapon", "is_equipped": 0,
        "effect_data": json.dumps({"type": "stat_buff", "stat": "spirit", "amount": 50}),
    }

    bonuses = core_items.calculate_equipped_bonuses([sword, scroll, unequipped_item])
    assert bonuses["stat_buffs"]["physique"] == 35
    assert bonuses["stat_buffs"]["spirit"] == 0  # unequipped
    assert bonuses["breakthrough_aid"] == 25.0


def test_drop_generators():
    # Test roll_breakthrough_drops structure
    drops = core_items.roll_breakthrough_drops(realm_tier=5)
    for drop in drops:
        assert "name" in drop and "item_type" in drop and "grade" in drop and "effect_data" in drop

    # Test roll_cultivate_streak_drops structure
    streak_drops = core_items.roll_cultivate_streak_drops(streak_count=10)
    for drop in streak_drops:
        assert "name" in drop and "item_type" in drop and "grade" in drop and "effect_data" in drop

-- Migration 021: Artifact actives — spirit-energy weapon abilities
--
-- Equipped weapons can carry an "active_ability" in their effect_data:
--   {"type": "stat_buff", ..., "active_ability": {"name": ..., "power": N,
--    "energy_cost": N}}
-- Each such artifact gets a spirit-energy pool that depletes on activation and
-- recharges flat over time (or instantly via /recharge_artifact with spirit
-- stones). Generic tuning numbers (energy cap, recharge rate, stone price)
-- live as named constants in core/items.py; per-ability power/cost is data.
ALTER TABLE items ADD COLUMN spirit_energy INTEGER NOT NULL DEFAULT 0;
ALTER TABLE items ADD COLUMN spirit_energy_max INTEGER NOT NULL DEFAULT 0;
ALTER TABLE items ADD COLUMN last_energy_at TEXT;

-- Give the existing Heaven-grade blade an active ability.
UPDATE item_templates SET effect_data =
  '{"type": "stat_buff", "stat": "physique", "amount": 35, "active_ability": {"name": "Inferno Slash 炎斩", "power": 18, "energy_cost": 40}}'
WHERE name = 'Heavenly Flame Blade';

-- New God-grade sword with a stronger active.
INSERT OR IGNORE INTO item_templates (name, item_type, grade, description, effect_data) VALUES
('Sword of Annihilation', 'Weapon', 'God',
 'A blade that sunders karma itself. Grants +60 Physique and the Annihilation Rend active.',
 '{"type": "stat_buff", "stat": "physique", "amount": 60, "active_ability": {"name": "Annihilation Rend 湮灭裂", "power": 30, "energy_cost": 60}}');

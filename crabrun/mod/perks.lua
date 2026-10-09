-- Crab Champions perks working in Cyberpunk. Each perk row in sheets/crab_perks.json names one effect kind.
local util = require("util")
local M = {}

function M.new(data, game)
  return { data = data, game = game, byKey = util.index(data.crab_perks, "key"),
           stacks = {}, mods = {}, aura_t = {} }
end

local function sorted_keys(t)
  local k = {}
  for key in pairs(t) do k[#k + 1] = key end
  table.sort(k)
  return k
end

function M.stacks(P, key) return P.stacks[key] or 0 end

function M.can_take(P, key)
  local row = P.byKey[key]
  return row ~= nil and M.stacks(P, key) < row.max_stacks
end

function M.add(P, key)
  local row = P.byKey[key]
  P.stacks[key] = M.stacks(P, key) + 1
  if row.effect == "stat" then
    local m = P.game.add_stat(row.stat, row.mod, row.value)
    if m then P.mods[#P.mods + 1] = m end
  end
end

-- sum of amount * stacks over perks with this effect
function M.total(P, effect)
  local t = 0
  for key, n in pairs(P.stacks) do
    local row = P.byKey[key]
    if row.effect == effect then t = t + row.amount * n end
  end
  return t
end

function M.crystal_gain(P, base)
  return math.floor(base * (1 + M.total(P, "crystals_mult")) + 0.5)
end

function M.price_factor(P)
  return math.max(0.5, 1 - M.total(P, "discount"))
end

-- per-frame effects: regeneration and auras
function M.tick(P, dt, enemies, player_pos)
  local regen = M.total(P, "regen")
  if regen > 0 then P.game.heal_pct(regen * dt) end
  for key, n in pairs(P.stacks) do
    local row = P.byKey[key]
    if row.effect == "aura" then
      P.aura_t[key] = (P.aura_t[key] or 0) + dt
      local interval = row.interval / n
      if P.aura_t[key] >= interval then
        P.aura_t[key] = 0
        for _, e in ipairs(enemies) do
          if e.handle and not e.dead and e.pos and player_pos and util.dist(e.pos, player_pos) <= row.radius then
            P.game.apply_status(e.handle, row.status)
          end
        end
      end
    end
  end
end

-- an enemy died at `pos`: on-kill perks may spread their effect to its neighbours
function M.on_kill(P, rng, pos, enemies)
  local fired = {}
  for _, key in ipairs(sorted_keys(P.stacks)) do   -- sorted: the same seed must draw the same numbers
    local n, row = P.stacks[key], P.byKey[key]
    if row.effect == "on_kill" and pos and rng:next() < math.min(1, row.chance * n) then
      fired[#fired + 1] = key
      for _, e in ipairs(enemies) do
        if e.handle and not e.dead and e.pos and util.dist(e.pos, pos) <= row.radius then
          P.game.apply_status(e.handle, row.status)
        end
      end
    end
  end
  return fired
end

function M.clear(P)
  for _, m in ipairs(P.mods) do P.game.remove_stat(m) end
  P.mods, P.stacks, P.aura_t = {}, {}, {}
end

return M

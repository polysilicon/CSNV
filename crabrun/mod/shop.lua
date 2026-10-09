-- The crystal shop between waves: six cards rolled (seeded) from Crab perks, Cyberpunk cyberware and weapons.
local perks = require("perks")
local M = {}

local function base_price(R, card)
  local sys = R.data.systems
  local growth = 1 + sys.price_growth_per_wave * math.max(0, R.wave - 1)
  return math.floor(card.row.price * growth * perks.price_factor(R.perks) + 0.5)
end
M.price = base_price

local function candidates(R, pool, taken)
  local out = {}
  if pool == "crab_perks" then
    for _, row in ipairs(R.data.crab_perks) do
      if perks.can_take(R.perks, row.key) and not taken[row.key] then out[#out + 1] = { kind = "perk", id = row.key, row = row } end
    end
  elseif pool == "shop_cyberware" then
    for _, row in ipairs(R.data.shop_cyberware) do
      if R.valid[row.record] ~= false and not R.owned[row.id] and not taken[row.id] then
        out[#out + 1] = { kind = "cyberware", id = row.id, row = row }
      end
    end
  elseif pool == "shop_weapons" then
    for _, row in ipairs(R.data.shop_weapons) do
      local ok = not row.starter and (not row.iconic or R.wave >= 5)
      if ok and R.valid[row.record] ~= false and not R.owned[row.id] and not taken[row.id] then
        out[#out + 1] = { kind = "weapon", id = row.id, row = row }
      end
    end
  end
  return out
end

function M.roll(R)
  local cards, taken = {}, {}
  for _, slot in ipairs(R.data.shop_layout) do
    local c = R.rng_shop:pick(candidates(R, slot.pool, taken))
    if c then
      taken[c.id] = true
      c.price = base_price(R, c)
    end
    cards[slot.slot] = c or false
  end
  R.shop.cards = cards
end

function M.open(R)
  R.shop = { cards = {}, rerolls = 0, t = R.data.systems.shop_time_s }
  M.roll(R)
end

function M.reroll_price(R)
  local s = R.data.systems
  return s.reroll_price + s.reroll_growth * R.shop.rerolls
end

function M.reroll(R)
  local p = M.reroll_price(R)
  if R.crystals < p then return false, "not enough crystals" end
  R.crystals = R.crystals - p
  R.shop.rerolls = R.shop.rerolls + 1
  M.roll(R)
  return true
end

-- returns ok, message
function M.buy(R, slot)
  local c = R.shop.cards[slot]
  if not c then return false, "empty" end
  if c.sold then return false, "sold" end
  if R.crystals < c.price then return false, "not enough crystals" end
  R.crystals = R.crystals - c.price
  c.sold = true
  if c.kind == "perk" then
    perks.add(R.perks, c.id)
    R.emit("perk")
  else
    R.owned[c.id] = true
    R.grant(c.kind, c.row)
    R.emit("buy")
  end
  return true
end

return M

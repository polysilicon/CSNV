-- A Crab Champions run in Night City: countdown, waves, crystal shop, island hops, run over.
-- States: idle -> countdown -> wave -> shop -> (hop) -> countdown -> wave ... -> over
local util = require("util")
local rngmod = require("rng")
local perks = require("perks")
local shop = require("shop")

local M = {}

-- deps: data (generated from sheets), game (game.lua or a test double), emit(event), files {ledger, best}
function M.new(deps)
  local R = {
    data = deps.data, game = deps.game, emit = deps.emit or function() end, files = deps.files or {},
    log = deps.log or function() end,
    state = "idle", banner = nil, valid = {}, names = {}, failed = {}, seed_input = nil, last = nil,
    best = { wave = 0 },
  }
  R.enemyRows = R.data.enemies
  R.stages = R.data.stages
  local best = R.files.best and util.load_json(R.files.best)
  if type(best) == "table" and best.wave then R.best = best end
  R.grant = function(kind, row) M.grant(R, kind, row) end
  return R
end

local function banner(R, text, sub, t)
  R.banner = { text = text, sub = sub, t = t or 2.5 }
end

-- check every record the run may use once, so a bad row is skipped instead of failing mid-run
function M.validate(R)
  local bad = {}
  for _, sheet in ipairs({ "enemies", "shop_weapons", "shop_cyberware" }) do
    for _, row in ipairs(R.data[sheet]) do
      if R.valid[row.record] == nil then
        R.valid[row.record] = R.game.record_ok(row.record)
        if R.valid[row.record] and sheet ~= "enemies" then R.names[row.record] = R.game.item_name(row.record) end
      end
      if not R.valid[row.record] then bad[#bad + 1] = row.record end
    end
  end
  table.sort(bad)
  return bad
end

------------------------------------------------------------------ ledger (survives a reload mid-run)
local function save_ledger(R)
  if not R.files.ledger then return end
  local given = {}
  for _, g in ipairs(R.given or {}) do given[#given + 1] = g.record end
  util.save_json(R.files.ledger, { active = R.state ~= "idle" and R.state ~= "over", given = given })
end

-- a save made mid-run still holds the run's items: take them back before a new run
function M.cleanup_stale(R)
  if not R.files.ledger then return 0 end
  local l = util.load_json(R.files.ledger)
  if type(l) ~= "table" or not l.active or type(l.given) ~= "table" then return 0 end
  for _, rec in ipairs(l.given) do R.game.remove_record(rec) end
  util.save_json(R.files.ledger, { active = false, given = {} })
  return #l.given
end

------------------------------------------------------------------ gear
function M.grant(R, kind, row)
  local g = R.game
  if kind == "cyberware" and not R.snap[row.area] then
    R.snap[row.area] = g.equipped(row.area)
  end
  local id = g.give_item(row.record)
  if id then
    g.equip(id)
    R.given[#R.given + 1] = { id = id, record = row.record, kind = kind, area = row.area }
    save_ledger(R)
  end
end

-- fresh start: stash the save's weapons and cyberware (they stay in the inventory) and remember them
local function fresh_start_gear(R)
  local g = R.game
  R.snap = {}
  local n = 0
  for _, area in ipairs(R.data.systems.strip_areas) do
    local slots = g.equipped(area)
    R.snap[area] = slots
    for slot in pairs(slots) do g.unequip(area, slot) n = n + 1 end
  end
  R.log("fresh start: stashed " .. n .. " equipped weapons/cyberware")
  local starter = util.index(R.data.shop_weapons, "id")[R.data.systems.starter_weapon]
  R.owned[starter.id] = true
  M.grant(R, "weapon", starter)
end

local function restore_gear(R)
  local g = R.game
  for _, it in ipairs(R.given or {}) do
    g.remove_item(it.id)
  end
  local n = 0
  for _, area in ipairs(R.data.systems.strip_areas) do
    for _, id in pairs((R.snap or {})[area] or {}) do g.equip(id) n = n + 1 end
  end
  R.log("run end: took back " .. #(R.given or {}) .. " run items, re-equipped " .. n .. " of yours")
  R.given, R.snap = {}, {}
end

------------------------------------------------------------------ run lifecycle
function M.start(R, seed)
  local sys = R.data.systems
  if R.state ~= "idle" and R.state ~= "over" then M.finish(R, "restart") end
  seed = seed or rngmod.random_seed(sys.seed_alphabet, sys.seed_length)
  R.seed = seed
  R.rng = rngmod.new(seed .. ":waves")
  R.rng_shop = rngmod.new(seed .. ":shop")
  R.rng_fx = rngmod.new(seed .. ":fx")
  R.wave, R.kills, R.time, R.crystals = 0, 0, 0, sys.start_crystals
  R.enemies, R.queue, R.owned, R.given, R.snap = {}, {}, {}, {}, {}
  R.perks = perks.new(R.data, R.game)
  R.stage_order = R.rng:shuffle(R.stages)
  R.stage_i = 1
  R.home = R.game.player_pos()
  R.home_yaw = R.game.player_yaw()
  R.game.set_immortal(true)
  fresh_start_gear(R)
  M.hop(R, true)
  R.state = "countdown"
  R.t = sys.countdown_s
  R.last_tick = math.ceil(R.t)
  banner(R, "CRAB RUN", "Seed " .. seed, sys.countdown_s)
  R.emit("music")
  save_ledger(R)
end

function M.stage(R) return R.stage_order[R.stage_i] end

function M.hop(R, first)
  if not first then R.stage_i = R.stage_i % #R.stage_order + 1 end
  local st = M.stage(R)
  R.game.teleport_player(st.x, st.y, st.z, st.yaw)
  R.emit("portal")
  banner(R, string.upper(st.name), st.district, 3)
end

function M.band(R, wave)
  for _, b in ipairs(R.data.waves) do
    if wave >= b.from_wave and wave <= b.to_wave then return b end
  end
  return R.data.waves[#R.data.waves]
end

local function usable(R, row) return R.valid[row.record] ~= false and (R.failed[row.record] or 0) < 2 end

-- the list of enemy rows for a wave, drawn from the wave RNG
function M.compose(R, wave)
  local sys, b = R.data.systems, M.band(R, wave)
  local list = {}
  local pool = util.filter(R.enemyRows, function(e)
    if e.boss or not usable(R, e) then return false end
    for _, t in ipairs(b.tiers) do if e.tier == t then return true end end
    return false
  end)
  for i = 1, b.count do list[#list + 1] = R.rng:pick(pool) end
  local boss_wave = b.boss and wave % sys.boss_every == 0
  if boss_wave then
    local top = wave >= 15 and 5 or 4
    local bosses = util.filter(R.enemyRows, function(e) return e.boss and e.tier <= top and usable(R, e) end)
    for i = 1, sys.bosses_per_boss_wave do list[#list + 1] = R.rng:pick(bosses) end
  end
  return list, boss_wave
end

function M.begin_wave(R)
  R.wave = R.wave + 1
  local list, boss = M.compose(R, R.wave)
  R.queue, R.enemies, R.spawn_t, R.wave_t, R.boss = list, {}, 0, 0, boss
  R.log(string.format("wave %d: %d enemies%s", R.wave, #list, boss and " (boss wave)" or ""))
  R.state = "wave"
  R.emit(boss and "boss" or "wave_start")
  banner(R, boss and ("BOSS WAVE " .. R.wave) or ("WAVE " .. R.wave), M.stage(R).name, 2)
end

local function spawn_one(R)
  local item = table.remove(R.queue, 1)
  if not item then return true end
  local row, tries = item.row or item, item.tries or 0
  local sys = R.data.systems
  local center = M.stage(R)
  local ppos = R.game.player_pos() or center
  local pos
  for _ = 1, 6 do
    local a = R.rng:range(0, 2 * math.pi)
    pos = R.game.find_spawn_point(ppos, a, R.rng:range(sys.spawn_radius_min, sys.spawn_radius_max))
    if pos then break end
  end
  if not pos then table.insert(R.queue, 1, item); return false end  -- navmesh not streamed yet: retry soon
  local id = R.game.spawn_npc(row.record, pos, 0)
  if not id then
    R.failed[row.record] = (R.failed[row.record] or 0) + 1
    R.log("could not spawn " .. row.id .. " (" .. row.record .. ")")
    return true
  end
  R.enemies[#R.enemies + 1] = { id = id, row = row, age = 0, pos = pos, tries = tries }
  R.log(string.format("spawned %s (%s)", row.id, row.record))
  return true
end

local function alive_count(R)
  local n = 0
  for _, e in ipairs(R.enemies) do if not e.dead then n = n + 1 end end
  return n
end
M.alive_count = alive_count

function M.gain(R, base)
  local g = perks.crystal_gain(R.perks, base)
  R.crystals = R.crystals + g
  return g
end

local function kill(R, e, credit)
  e.dead = true
  if credit then
    R.kills = R.kills + 1
    M.gain(R, e.row.crystals + perks.total(R.perks, "crystals_kill"))
    perks.on_kill(R.perks, R.rng_fx, e.pos, R.enemies)
    R.emit("crystal")
  end
end

-- An enemy leaves the count only when it is seen alive and then seen dead. One that never shows up (or
-- vanishes) is spawned again; after enemy_respawn_attempts tries it is dropped, and every step is logged.
local function respawn(R, e, why)
  R.game.despawn(e.id)
  e.dead = true
  e.tries = (e.tries or 0) + 1
  if e.tries > R.data.systems.enemy_respawn_attempts then
    R.failed[e.row.record] = (R.failed[e.row.record] or 0) + 1
    R.log(string.format("enemy %s dropped after %d tries (%s)", e.row.id, e.tries, why))
    return
  end
  R.log(string.format("enemy %s %s, spawning it again", e.row.id, why))
  table.insert(R.queue, 1, { row = e.row, tries = e.tries })   -- queue items are rows, or {row, tries} for a respawn
end

local function update_enemies(R, dt)
  local sys, ppos = R.data.systems, R.game.player_pos()
  for _, e in ipairs(R.enemies) do
    if not e.dead then
      e.age = e.age + dt
      local h = R.game.get_entity(e.id)
      e.handle = h
      if h then
        if not e.appeared then e.appeared = true R.log(string.format("enemy %s appeared after %.1fs", e.row.id, e.age)) end
        if not e.hostile then e.hostile = R.game.make_hostile(h) end
        e.pos = R.game.entity_pos(h) or e.pos
        local dead = R.game.is_dead(h)
        if not dead then
          e.alive = true
        elseif e.alive then
          R.log(string.format("enemy %s killed", e.row.id))
          kill(R, e, true)
        elseif e.age > 3 then
          respawn(R, e, "spawned dead")
        end
        if not e.dead and ppos and e.pos and e.age > sys.stuck_timeout_s and util.dist(ppos, e.pos) > sys.despawn_distance then
          respawn(R, e, "wandered off")
        end
      elseif e.appeared then
        respawn(R, e, "vanished")
      elseif e.age > sys.enemy_appear_timeout_s then
        respawn(R, e, "never appeared")
      end
    end
  end
end

local function clear_bodies(R)
  for _, e in ipairs(R.enemies or {}) do R.game.despawn(e.id) end
  R.enemies = {}
end

function M.wave_cleared(R)
  local b = M.band(R, R.wave)
  M.gain(R, b.clear_bonus + perks.total(R.perks, "crystals_wave"))
  R.emit("wave_clear")
  clear_bodies(R)
  if R.wave > R.best.wave then
    R.best = { wave = R.wave, seed = R.seed, crystals = R.crystals }
    if R.files.best then util.save_json(R.files.best, R.best) end
  end
  R.hop_due = R.wave % R.data.systems.waves_per_stage == 0
  shop.open(R)
  R.state = "shop"
  R.game.time_dilation(true, R.data.systems.shop_time_dilation)
  banner(R, "WAVE " .. R.wave .. " CLEARED", "Crystal shop open", 2)
end

function M.close_shop(R)
  R.game.time_dilation(false)
  R.shop = nil
  if R.hop_due then M.hop(R, false) end
  R.state = "countdown"
  R.t = 3
  R.last_tick = 3
end

function M.finish(R, why)
  clear_bodies(R)
  R.game.time_dilation(false)
  if R.perks then perks.clear(R.perks) end
  restore_gear(R)
  R.game.heal_pct(100)
  R.game.set_immortal(false)
  if R.home then R.game.teleport_player(R.home.x, R.home.y, R.home.z, R.home_yaw) end
  R.last = { wave = R.wave, kills = R.kills, crystals = R.crystals, seed = R.seed, why = why, time = R.time }
  R.state = "over"
  R.shop = nil
  R.emit("music_stop")
  if why == "died" then R.emit("death") end
  banner(R, why == "died" and "RUN OVER" or "RUN ENDED", "Wave " .. R.wave .. "  ·  Seed " .. tostring(R.seed), 6)
  save_ledger(R)
end

------------------------------------------------------------------ input (relayed by the bridge)
function M.input(R, action, char)
  local sys = R.data.systems
  if R.seed_input then
    if action == "seed_char" and char and #R.seed_input < sys.seed_length then
      R.seed_input = R.seed_input .. char
    elseif action == "seed_back" then
      R.seed_input = R.seed_input:sub(1, -2)
    elseif action == "continue" then
      local s = R.seed_input
      R.seed_input = nil
      if #s == sys.seed_length then M.start(R, s) end
    elseif action == "seed_entry" then
      R.seed_input = nil
    end
    return
  end
  if action == "seed_entry" and (R.state == "over" or R.state == "countdown" or R.state == "idle") then
    R.seed_input = ""
  elseif action == "new_run" and (R.state == "over" or R.state == "idle") then
    M.start(R)
  elseif action == "end_run" and R.state ~= "idle" and R.state ~= "over" then
    M.finish(R, "quit")
  elseif R.state == "shop" then
    local n = action:match("^buy(%d)$")
    if n then shop.buy(R, tonumber(n))
    elseif action == "reroll" then shop.reroll(R)
    elseif action == "continue" then M.close_shop(R) end
  end
end

------------------------------------------------------------------ per-frame
function M.update(R, dt)
  if R.banner then
    R.banner.t = R.banner.t - dt
    if R.banner.t <= 0 then R.banner = nil end
  end
  local s = R.state
  if s == "idle" or s == "over" then return end
  R.time = R.time + dt
  if R.game.health_pct() <= R.data.systems.death_health_pct then
    M.finish(R, "died")
    return
  end
  if s == "countdown" then
    if R.seed_input then return end
    R.t = R.t - dt
    if math.ceil(R.t) < R.last_tick then
      R.last_tick = math.ceil(R.t)
      if R.last_tick > 0 then R.emit("countdown") end
    end
    if R.t <= 0 then M.begin_wave(R) end
  elseif s == "wave" then
    local b = M.band(R, R.wave)
    R.wave_t = R.wave_t + dt
    R.spawn_t = R.spawn_t - dt
    if R.spawn_t <= 0 and #R.queue > 0 and alive_count(R) < b.max_alive then
      R.spawn_t = spawn_one(R) and b.spawn_interval or 0.5
    end
    update_enemies(R, dt)
    perks.tick(R.perks, dt, R.enemies, R.game.player_pos())
    if #R.queue == 0 and alive_count(R) == 0 then M.wave_cleared(R) end
  elseif s == "shop" then
    perks.tick(R.perks, dt, {}, nil)
    R.shop.t = R.shop.t - dt
    if R.shop.t <= 0 then M.close_shop(R) end
  end
end

return M

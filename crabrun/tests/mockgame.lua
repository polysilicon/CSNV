-- A stand-in for game.lua: records every call and simulates NPCs that die when the test says so.
local M = {}

function M.new(opts)
  opts = opts or {}
  local g = { calls = {}, ents = {}, nextid = 1, hp = 100, pos = { x = 0, y = 0, z = 0 }, inv = {}, equipped = {},
              stats = {}, status = {}, bad = opts.bad or {}, navfail = opts.navfail or 0 }
  local function log(name, ...) g.calls[#g.calls + 1] = { name, ... } end
  function g.count(name) local n = 0 for _, c in ipairs(g.calls) do if c[1] == name then n = n + 1 end end return n end
  g.session_ok = function() return true end
  g.is_paused = function() return false end
  g.player_pos = function() return { x = g.pos.x, y = g.pos.y, z = g.pos.z } end
  g.player_yaw = function() return 0 end
  g.health_pct = function() return g.hp end
  g.heal_pct = function(p) log("heal", p) end
  g.set_immortal = function(on) log("immortal", on) g.immortal = on end
  g.teleport_player = function(x, y, z, yaw) log("teleport", x, y, z) g.pos = { x = x, y = y, z = z } end
  g.find_spawn_point = function(c, a, r)
    if g.navfail > 0 then g.navfail = g.navfail - 1 return nil end
    return { x = c.x + math.cos(a) * r, y = c.y + math.sin(a) * r, z = c.z }
  end
  g.spawn_npc = function(rec, pos) log("spawn", rec)
    if opts.spawn_fails and opts.spawn_fails > 0 then opts.spawn_fails = opts.spawn_fails - 1 return nil, "bad spec field" end
    local id = g.nextid g.nextid = id + 1
    g.ents[id] = { rec = rec, pos = pos, dead = opts.born_dead or false } return id end
  g.get_entity = function(id) if opts.ghost then return nil end return g.ents[id] end
  g.make_hostile = function(h) log("hostile") return true end
  g.is_dead = function(h) return h.dead end
  g.entity_pos = function(h) return h.pos end
  g.despawn = function(id) log("despawn", id) g.ents[id] = nil end
  g.apply_status = function(h, s) log("status", s) end
  g.add_stat = function(stat, mod, v) log("add_stat", stat, mod, v) local m = { stat, mod, v } g.stats[m] = true return m end
  g.remove_stat = function(m) log("remove_stat") g.stats[m] = nil end
  g.record_ok = function(rec) return not g.bad[rec] end
  g.item_name = function(rec) return "Name of " .. rec end
  g.give_item = function(rec) log("give", rec) local id = { rec = rec } g.inv[id] = true return id end
  g.remove_item = function(id) log("remove", id.rec) g.inv[id] = nil end
  g.remove_record = function(rec) log("remove_record", rec) end
  g.equip = function(id) log("equip", id.rec) end
  g.unequip = function(area, slot) log("unequip", area, slot) end
  g.equipped = function(area)
    if area == "Weapon" then return { [0] = { rec = "orig_gun" } } end
    return { [0] = { rec = "orig_" .. area } }
  end
  g.time_dilation = function(on, v) log("dilation", on) g.dilated = on end
  function g.kill_all() for _, e in pairs(g.ents) do e.dead = true end end
  return g
end
return M

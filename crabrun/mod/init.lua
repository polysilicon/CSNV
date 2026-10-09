-- Crab Run: Night City. Crab Champions runs inside Cyberpunk 2077.
-- Loading a save starts a run; CrabRunBridge.exe (started by Melty) brings Crab Champions' own perks,
-- icons and sounds from the player's install and relays the shop keys.
local data = require("data")
local util = require("util")
local game = require("game")
local run = require("run")
local hud = require("hud")
local bridge = require("bridge")

local CrabRun = { R = nil, crab = nil, session = false, settle = 0, bridge_ok = false, alive_t = 0, attached = false }

-- print goes to CET's console and to CrabRun.log, which CET keeps for this mod in its folder
local function log(s)
  print("[CrabRun] " .. s)
end

local function load_crab()
  local c = util.load_json("crab/crab_data.json")
  if type(c) ~= "table" or not c.ok then
    log("Crab Champions content not found (crab/crab_data.json); perks use their sheet names until the bridge extracts it")
    return { perks = {}, art = {} }
  end
  local n = 0
  for _ in pairs(c.perks or {}) do n = n + 1 end
  log(string.format("Crab Champions content: %d perks, from %s", n, tostring(c.source)))
  return c
end

registerForEvent("onInit", function()
  log("Crab Run " .. data.version .. " loaded")
  bridge.init()
  CrabRun.crab = load_crab()
  CrabRun.R = run.new({ data = data, game = game, emit = bridge.emit,
                        files = { ledger = "io/ledger.json", best = "io/best.json" } })
  -- PlayerPuppet attaches on every load / new game: that is a fresh session and a fresh run
  Observe("PlayerPuppet", "OnGameAttached", function() CrabRun.attached = true end)
end)

local function on_session_start()
  local R = CrabRun.R
  local bad = run.validate(R)
  for _, rec in ipairs(bad) do log("record missing in this game version, skipped: " .. rec) end
  local n = run.cleanup_stale(R)
  if n > 0 then log("took back " .. n .. " items from a run that was saved mid-way") end
  run.start(R)
  log("run started, seed " .. R.seed)
end

registerForEvent("onUpdate", function(dt)
  local R = CrabRun.R
  if not R then return end
  CrabRun.alive_t = CrabRun.alive_t + dt
  if CrabRun.alive_t > 1 then CrabRun.alive_t = 0 CrabRun.bridge_ok = bridge.alive() end

  local ok = game.session_ok()
  if not ok or CrabRun.attached then
    if CrabRun.session and R.state ~= "idle" and R.state ~= "over" then R.state = "idle" end -- left to menu / reloading
    CrabRun.session, CrabRun.settle, CrabRun.attached = false, 0, false
    if not ok then return end
  end
  if not CrabRun.session then
    CrabRun.settle = CrabRun.settle + dt
    if CrabRun.settle > 3 then CrabRun.session = true on_session_start() end
    return
  end
  if game.is_paused() then return end
  for _, k in ipairs(bridge.read_keys(dt)) do run.input(R, k.action, k.char) end
  local ok2, err = pcall(run.update, R, dt)
  if not ok2 then log("update error: " .. tostring(err)) end
  bridge.flush()
end)

registerForEvent("onDraw", function()
  local R = CrabRun.R
  if not R or not CrabRun.session or game.is_paused() then return end
  local ok, err = pcall(hud.draw, R, CrabRun.crab, CrabRun.bridge_ok)
  if not ok and not CrabRun.draw_err then CrabRun.draw_err = true log("draw error: " .. tostring(err)) end
end)

registerForEvent("onShutdown", function()
  local R = CrabRun.R
  if R and R.state ~= "idle" and R.state ~= "over" then pcall(run.finish, R, "quit") end
end)

return CrabRun

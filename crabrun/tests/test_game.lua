-- Loads the real game.lua with CET-like globals, so mistakes in how it calls the game show up here
-- (the run tests use a mock game and can't see them).
package.path = "../mod/?.lua;" .. package.path
local pass, fail = 0, 0
local function check(n, c) if c then pass = pass + 1 else fail = fail + 1 print("FAIL " .. n) end end
local function fresh() package.loaded.game = nil return require("game") end

local player = { IsAttached = function() return true end }
-- Game has no GetSystemRequestsHandler (it belongs to inkMenuScenario): the 0.1.0 bug
Game = { GetPlayer = function() return player end }
GetSingleton = function(name)
  assert(name == "inkMenuScenario")
  return { GetSystemRequestsHandler = function() return { IsPreGame = function() return _G.PREGAME end } end }
end
PREGAME = false
local g = fresh()
check("loaded save counts as a session", g.session_ok() == true)
PREGAME = true
check("main menu is not a session", fresh().session_ok() == false)
GetSingleton = function() error("no singleton") end
check("a failing menu check never blocks the run", fresh().session_ok() == true)
Game.GetPlayer = function() return nil end
check("no player, no session", fresh().session_ok() == false)
Game.GetPlayer = function() return { IsAttached = function() return false end } end
check("detached player, no session", fresh().session_ok() == false)
-- equipped(): CET's ItemID global has no IsValid; empty slots are told apart by the inventory
ItemID = {}
local held = { gun = true, sandy = true }
Game.GetPlayer = function() return player end
Game.GetTransactionSystem = function() return { HasItem = function(_, p, id) return held[id] == true end } end
gamedataEquipmentArea = { Weapon = 1, SystemReplacementCW = 2 }
EquipmentSystem = { GetData = function() return {
  GetNumberOfSlots = function(_, a) return a == 1 and 3 or 1 end,
  GetItemInEquipSlot = function(_, a, i) if a == 1 then return ({ [0] = "gun", [1] = "empty", [2] = "empty" })[i] end return "sandy" end,
} end }
local g2 = fresh()
local w = g2.equipped("Weapon")
check("equipped weapon found without ItemID.IsValid", w[0] == "gun" and w[1] == nil and w[2] == nil)
check("equipped cyberware found", fresh().equipped("SystemReplacementCW")[0] == "sandy")
-- spawn_npc sets only the fields Entity Spawner sets; anything else must not sneak back in
local allowed = { recordID = true, position = true, orientation = true, alwaysSpawned = true }
DynamicEntitySpec = { new = function()
  return setmetatable({}, { __newindex = function(t, k, v)
    if not allowed[k] then error("bad field " .. k) end rawset(t, k, v) end })
end }
Vector4 = { new = function(x, y, z, w) return { x = x, y = y, z = z, w = w } end }
EulerAngles = { new = function() return { ToQuat = function() return "quat" end } end }
local made
Game.GetDynamicEntitySystem = function() return { CreateEntity = function(_, spec) made = spec return 42 end } end
local id, err = fresh().spawn_npc("Character.x", { x = 1, y = 2, z = 3 }, 0)
check("spawn_npc uses only known spec fields", id == 42 and made.recordID == "Character.x", tostring(err))
Game.GetDynamicEntitySystem = function() return { CreateEntity = function() error("boom") end } end
local id2, err2 = fresh().spawn_npc("Character.x", { x = 1, y = 2, z = 3 }, 0)
check("spawn error is returned for the log", id2 == nil and err2:find("boom") ~= nil)
print(string.format("%d passed, %d failed", pass, fail))
os.exit(fail == 0 and 0 or 1)

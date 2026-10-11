-- Plays a whole match of the CET mod against stand-ins for Cyberpunk's scripting API, to catch Lua
-- runtime errors (nil fields, typos, wrong call shapes) before anyone launches the game.
-- Run: luajit tools/cetsim/sim.lua   (from the cyberkino folder)
package.path = "cet/cyberkino/?.lua;" .. package.path
local clock = 0
os.clock = function() return clock end

local hotkeys, events, logs, errors = {}, {}, {}, {}
function registerHotkey(id, label, fn) hotkeys[id] = fn end
function registerForEvent(ev, fn) events[ev] = fn end
local realprint = print
print = function(s) logs[#logs + 1] = s end

-- CET ships a json module; a tiny stand-in that round-trips the layout table
json = {
	encode = function(t) _G.__saved = t return "saved" end,
	decode = function(s) return _G.__saved end,
}

local function stub(name)
	return setmetatable({}, { __index = function(t, k) return function(...) return nil end end })
end

Vector4 = { new = function(x, y, z, w) return { x = x, y = y, z = z, w = w } end }
EulerAngles = { new = function(r, p, y) return { roll = r, pitch = p, yaw = y } end }
CName = { new = function(s) return s end }
TweakDBID = { new = function(s) return { hash = #s * 7919 % 100003 } end }
ItemID = { IsValid = function(id) return id ~= nil end }
WorldTransform = { new = function() local t = {} function t:SetPosition(p) t.p = p end function t:SetOrientationEuler(e) t.e = e end return t end }
GameplayEquipRequest = { new = function() return {} end }
UnequipRequest = { new = function() return {} end }
gamedataEquipmentArea = setmetatable({}, { __index = function(_, k) return k end })
gamedataStatType = setmetatable({}, { __index = function(_, k) return k end })
gamedataStatPoolType = { Health = "Health" }
gameStatModifierType = { Additive = 0 }
EAIAttitude = { AIA_Hostile = 2 }
RPGManager = { CreateStatModifier = function(s, t, v) return { s = s, v = v } end }
ImGuiCond = { Always = 1 }
ImGuiCol = { WindowBg = 2 }
ImGuiWindowFlags = { NoTitleBar = 1, AlwaysAutoResize = 2, NoMove = 4, NoInputs = 8 }
local drawn = {}
local press = nil -- label prefix of the button to "click" on the next draw
ImGui = setmetatable({ Begin = function() return true end, Text = function(t) drawn[#drawn + 1] = t end,
	TextColored = function(r, g, b, a, t) drawn[#drawn + 1] = t end,
	Button = function(label) if press and label:sub(1, #press) == press then press = nil return true end return false end },
	{ __index = function() return function() end end })
gamedataItemCategory = { Weapon = "Weapon" }

-- world: V at the origin of a 10 m x 30 m corridor running along Y
local V = { x = 0, y = 0, z = 123 }
local health = 100
local inventory, nextSeed = {}, 1
local entities, nextId = {}, 1
local function entity(kind, p)
	local e = { kind = kind, p = p, dead = false, attitude = nil }
	function e:GetWorldPosition() return self.p end
	function e:IsDead() return self.dead end
	function e:GetAttitudeAgent() local s = self return { SetAttitudeGroup = function(_, g) s.group = g end, SetAttitudeTowards = function() end } end
	function e:GetEntityID() return self.id end
	return e
end
local playerEnt = entity("player", V)
stashInv = {}
stashEnt = entity("stash", { x = -1393, y = 1268, z = 123 })
stashEnt.id = 4242
entities[4242] = stashEnt
function stashEnt:GetEntityID() return { hash = 4242 } end
function stashEnt:GetClassName() return "Stash" end
entEntityID = { new = function(t) return tonumber(t.hash) end }
RPGManager.GetItemCategory = function(id) return (id.rec or ""):find("Preset") and "Weapon" or "Other" end
function playerEnt:GetWorldForward() return { x = 0, y = 1, z = 0 } end
function playerEnt:GetWorldPosition() return { x = V.x, y = V.y, z = V.z } end
playerEnt.GetAttitudeAgent = function() return {} end

exEntitySpawner = {
	Spawn = function(path, t) local id = nextId nextId = nextId + 1 entities[id] = entity(path, t.p) entities[id].id = id return id end,
	SpawnRecord = function(rec, t) local id = nextId nextId = nextId + 1 entities[id] = entity(rec, t.p) entities[id].id = id entities[id].npc = true return id end,
	Despawn = function(e) entities[e.id] = nil end,
}

Game = {
	GetPlayer = function() return playerEnt end,
	FindEntityByID = function(id) return entities[id] end,
	AddToInventory = function(rec, n)
		if rec:sub(1, 5) == "Items" then
			inventory[#inventory + 1] = { id = { hash = TweakDBID.new(rec).hash }, rngSeed = nextSeed, rec = rec }
			nextSeed = nextSeed + 1
		end
	end,
	GetTargetingSystem = function() return { GetLookAtObject = function() return stashEnt end } end,
	GetTransactionSystem = function() return {
		GetItemList = function(_, p) local l = {} for _, it in ipairs(inventory) do l[#l + 1] = { GetID = function() return it end } end return true, l end,
		RemoveItem = function(_, p, id) for i, it in ipairs(inventory) do if it == id then table.remove(inventory, i) return end end end,
		TransferItem = function(_, from, to, id)
			local src = from == playerEnt and inventory or stashInv
			local dst = to == playerEnt and inventory or stashInv
			for i, it in ipairs(src) do if it == id then table.remove(src, i) dst[#dst + 1] = it return true end end
			return false
		end,
	} end,
	GetScriptableSystemsContainer = function() return { Get = function() return {
		QueueRequest = function() end,
		GetPlayerData = function() return { GetItemInEquipSlot = function(_, area, slot) return (slot == 0 and (area == "Weapon" or area == "LegsCW")) and { id = { hash = 1 }, rngSeed = 999 } or nil end } end,
	} end } end,
	GetSpatialQueriesSystem = function() return { SyncRaycastByCollisionGroup = function(_, a, b)
		-- a corridor 10 m wide along Y around the apartment: walls at x = ox ± 5
		local ox = -1391.87
		if b.x > ox + 5 then local t = (ox + 5 - a.x) / (b.x - a.x) return true, { position = { x = ox + 5, y = a.y + (b.y - a.y) * t, z = a.z } } end
		if b.x < ox - 5 then local t = (ox - 5 - a.x) / (b.x - a.x) return true, { position = { x = ox - 5, y = a.y + (b.y - a.y) * t, z = a.z } } end
		return false, nil
	end } end,
	GetStatsSystem = function() return { AddModifier = function() end, RemoveModifier = function() end } end,
	GetStatPoolsSystem = function() return { GetStatPoolValue = function() return health end, RequestSettingStatPoolValue = function() health = 100 end } end,
	GetTimeSystem = function() return { SetTimeDilation = function() end, UnsetTimeDilation = function() end, SetIgnoreTimeDilationOnLocalPlayerZero = function() end } end,
	GetTeleportationFacility = function() return { Teleport = function(_, p, pos) V.x, V.y = pos.x, pos.y end } end,
	GetPreventionSpawnSystem = function() return stub() end,
}

local f = io.open("cyberkino.log", "w") f:close()
dofile("cet/cyberkino/init.lua")
events.onInit()

local function step(seconds)
	for _ = 1, math.floor(seconds * 10) do
		clock = clock + 0.1
		events.onUpdate(0.1)
		events.onDraw()
	end
end
local function killAll()
	for _, e in pairs(entities) do if e.npc then e.dead = true end end
end
local function goTo(kind)
	for _, line in ipairs(logs) do end
end

Game.AddToInventory("Items.Preset_Overture_Default", 1)
Game.AddToInventory("Items.Preset_Kenshin_Default", 1)
local own = #inventory
local function click(label) press = label events.onDraw() assert(press == nil, "no button " .. label) end
local function at(x, y) V.x, V.y = x, y end
events.onOverlayOpen()
at(-1391.87, 1271.69) click("Match start")
at(-1391.87, 1276) click("Barricade")            -- zone 1 -> 2, north
click(" + ")
at(-1391.87, 1284) click("Barricade")            -- zone 2 -> 3
click(" - ")
at(-1388, 1270) click("Wall-buy")
click(" > ") at(-1395, 1270) click("Wall-buy")
at(-1390, 1268) click("Mystery Box")
at(-1386, 1266) click("Mystery Box")
at(-1391.87, 1262) click("Zombie spawn")
click(" + ") at(-1391.87, 1281) click("Zombie spawn")
click(" + ") at(-1391.87, 1290) click("Zombie spawn")
click("V's stash")
click("Undo last") click("V's stash")
events.onOverlayClose()
at(0, 0)
hotkeys.start()
step(3)
assert(#stashInv == 2, "V's own weapons should be in the stash, found " .. #stashInv) -- teleport, then the arena after the apartment settles
assert(#inventory >= 1, "the Unity was not given")
step(6) -- round 1 starts
local rounds = 0
for r = 1, 6 do
	step(20)
	killAll()
	step(6)
	-- walk to a chip if one dropped and pick it up
	for _, e in pairs(entities) do
		if e.kind:find("shard") then V.x, V.y = e.p.x, e.p.y hotkeys.use() end
	end
	V.x, V.y = -1391.87, 1271.69
	step(10)
	-- walk into the closed zone 1 barricade: V must be pushed back south of it
	if r == 2 then V.x, V.y = -1391.87, 1277.0 step(0.2) assert(V.y < 1276.5, "barricade did not hold") V.x, V.y = -1391.87, 1271.69 end
end
-- buy things: stand on every spawned wall case / box / barricade and press F
for _, e in pairs(entities) do
	if e.kind:find("weapon_case") or e.kind:find("road_barrier") then
		V.x, V.y = e.p.x, e.p.y
		step(0.2)
		hotkeys.use()
		step(3)
	end
end
hotkeys.sandevistan()
step(1)
health = 10
step(0.5)
print = realprint
local f = io.open("cyberkino.log") local text = f:read("*a") f:close()
io.write(text)
local errs = 0
for line in text:gmatch("[^\n]+") do if line:find("failed") or line:find("error") then errs = errs + 1 end end
print(string.format("\nsimulation: %d log lines, %d errors, %d items left in inventory", select(2, text:gsub("\n", "")), errs, #inventory))
assert(#stashInv == 0, "weapons left in the stash")
assert(#inventory == own, "V should have exactly their own items back, has " .. #inventory)
os.exit(errs == 0 and 0 or 1)
